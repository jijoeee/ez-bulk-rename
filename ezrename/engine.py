"""Collect files, preview new names, rename safely, undo.

No UI imports. The rules are in rules.py; this module decides what is allowed
and does the renaming.

Safety, in order of importance:
  * Nothing is renamed while any row has a problem (duplicate name, illegal
    character, a file already there, path too long).
  * Files are never deleted, copied or overwritten — only renamed in their own
    folder. File contents are never opened.
  * Renaming happens in two steps (every file to a temporary name first, then to
    its new name), so swaps like a -> b, b -> a and case-only changes work. If
    any step fails, every file already moved is put back.
  * Every batch is written to an undo log (CSV) BEFORE the first rename, so even
    a power cut halfway can be undone from the log.
"""

from __future__ import annotations

import csv
import os
import re
import tempfile
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Optional

from .rules import FileInfo, RenameError, Rule, apply_rules

Cancel = Optional[threading.Event]

# Windows limits (the target platform), applied on every OS so tests match Windows.
ILLEGAL_CHARS = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                  *(f"LPT{i}" for i in range(1, 10))}
MAX_PATH = 259          # longest full path most Windows programs accept
MAX_NAME = 255          # longest single file name
TEMP_PREFIX = ".ezrename-"
# Files Windows and Office keep in folders for themselves. Renaming them breaks things
# (desktop.ini holds a folder's icon and name; ~$ files are Office's open-document locks),
# so they are never listed, even when chosen one by one.
SYSTEM_NAMES = {"desktop.ini", "thumbs.db", "ehthumbs.db", ".ds_store"}
_HIDDEN, _SYSTEM = 0x2, 0x4      # os.stat().st_file_attributes on Windows
LOG_HEADER = ["Old path", "New path"]

OK, SAME, BLOCKED = "ok", "same", "blocked"


# ================================================================ data
@dataclass(frozen=True)
class FileItem:
    path: str
    folder: str
    name: str
    size: int
    modified: float
    created: float


@dataclass
class PreviewRow:
    item: FileItem
    new_name: str
    status: str = OK            # ok | same | blocked
    problem: str = ""           # short, for the Status column: "Duplicate name (3 files)"
    detail: str = ""            # the full explanation, shown when the row is clicked

    def block(self, problem: str, detail: str) -> None:
        self.status, self.problem, self.detail = BLOCKED, problem, detail

    @property
    def new_path(self) -> str:
        return os.path.join(self.item.folder, self.new_name)


@dataclass
class Preview:
    rows: list[PreviewRow]
    changing: int = 0
    unchanged: int = 0
    blocked: int = 0

    @property
    def can_apply(self) -> bool:
        return self.changing > 0 and self.blocked == 0


@dataclass
class RenameResult:
    renamed: int
    log_path: str
    failed: list[tuple[str, str]] = field(default_factory=list)   # (path, reason)


@dataclass
class UndoResult:
    restored: int
    skipped: list[tuple[str, str]] = field(default_factory=list)    # (path, reason)


# ================================================================ collecting files
def natural_key(text: str) -> list:
    """Sort "file2" before "file10", as Explorer does."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def parse_extensions(text: str) -> frozenset[str]:
    """"pdf, .JPG docx" -> {".pdf", ".jpg", ".docx"}. Empty means every file."""
    return frozenset("." + p.lower().lstrip(".") for p in re.split(r"[\s,;]+", text) if p.strip(". "))


def _item(path: str) -> Optional[FileItem]:
    try:
        st = os.stat(path)
    except OSError:
        return None
    created = getattr(st, "st_birthtime", None) or st.st_ctime   # ctime IS creation time on Windows
    return FileItem(path=os.path.abspath(path), folder=os.path.dirname(os.path.abspath(path)),
                    name=os.path.basename(path), size=st.st_size, modified=st.st_mtime, created=created)


def is_system_file(name: str) -> bool:
    """desktop.ini, Thumbs.db, Office lock files (~$...) and our own temporary files."""
    lower = name.lower()
    return lower in SYSTEM_NAMES or name.startswith(("~$", TEMP_PREFIX))


def _hidden_or_system(path: str) -> bool:
    """Hidden or system files in a scanned folder are skipped (Windows attributes, or a leading dot)."""
    if os.path.basename(path).startswith("."):
        return True
    try:
        attrs = getattr(os.stat(path), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attrs & (_HIDDEN | _SYSTEM))


def collect(paths: Iterable[str], include_subfolders: bool = False,
            extensions: frozenset[str] = frozenset(), cancel: Cancel = None) -> list[FileItem]:
    """Files from dropped or chosen paths. A folder adds the files in it (and below, if asked).

    Never listed: system files (desktop.ini, Thumbs.db, ~$ Office lock files, our own
    temporary files) and, inside scanned folders, hidden files. A file chosen one by
    one is listed even if hidden — the user picked it.
    """
    found: dict[str, FileItem] = {}

    def add(path: str, scanned: bool) -> None:
        name = os.path.basename(path)
        if is_system_file(name) or (scanned and _hidden_or_system(path)):
            return
        if extensions and extension_of(name) not in extensions:
            return
        item = _item(path)
        if item is not None:
            found.setdefault(os.path.normcase(item.path), item)

    for path in paths:
        if cancel is not None and cancel.is_set():
            break
        if os.path.isfile(path):
            add(path, scanned=False)
        elif os.path.isdir(path):
            if include_subfolders:
                for root, dirs, files in os.walk(path):
                    dirs.sort(key=natural_key)
                    dirs[:] = [d for d in dirs if not _hidden_or_system(os.path.join(root, d))]
                    for f in sorted(files, key=natural_key):
                        add(os.path.join(root, f), scanned=True)
                    if cancel is not None and cancel.is_set():
                        break
            else:
                try:
                    names = sorted(os.listdir(path), key=natural_key)
                except OSError:
                    continue
                for f in names:
                    full = os.path.join(path, f)
                    if os.path.isfile(full):
                        add(full, scanned=True)
    return list(found.values())


def extension_of(name: str) -> str:
    """".pdf" for "Report.PDF"; "" for a file without an extension."""
    return os.path.splitext(name)[1].lower()


def extension_counts(items: Iterable[FileItem]) -> list[tuple[str, int]]:
    """The file types present, most common first: [(".pdf", 12), (".jpg", 3), ("", 1)]."""
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[extension_of(item.name)] += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def extension_label(ext: str) -> str:
    """"PDF" for ".pdf"; "No extension" for ""."""
    return ext.lstrip(".").upper() if ext else "No extension"


def sort_items(items: list[FileItem], by: str = "name") -> list[FileItem]:
    """The order numbering follows: name, modified date, created date or size."""
    keys: dict[str, Callable[[FileItem], object]] = {
        "name": lambda i: (natural_key(i.folder), natural_key(i.name)),
        "modified": lambda i: (i.modified, natural_key(i.name)),
        "created": lambda i: (i.created, natural_key(i.name)),
        "size": lambda i: (i.size, natural_key(i.name)),
    }
    return sorted(items, key=keys.get(by, keys["name"]))


# ================================================================ checking names
def name_problem(name: str) -> tuple[str, str]:
    """Why Windows would refuse this file name: (short label, full explanation), or ("", "")."""
    if not name or not name.strip():
        return "Empty name", "The rules leave this file without a name."
    bad = sorted({ch for ch in name if ch in ILLEGAL_CHARS})
    if bad:
        shown = " ".join("(control character)" if ord(ch) < 32 else ch for ch in bad)
        return (f"Not allowed: {shown}",
                'Windows doesn\'t allow these characters in file names: < > : " / \\ | ? *')
    if name.endswith((" ", ".")):
        return "Ends with a space or dot", "Windows doesn't allow a file name to end with a space or a dot."
    stem = os.path.splitext(name)[0]
    if stem.upper().rstrip(" .") in RESERVED_NAMES or name.upper() in RESERVED_NAMES:
        return (f"Reserved name: {stem}",
                f"“{stem}” is reserved by Windows for devices (CON, PRN, AUX, NUL, COM1–9, LPT1–9).")
    if name.startswith(TEMP_PREFIX):
        return ("Reserved name",
                f"Names starting with {TEMP_PREFIX} are used for temporary files while renaming.")
    if len(name) > MAX_NAME:
        return (f"Name too long ({len(name)})",
                f"The name has {len(name)} characters; Windows allows {MAX_NAME}.")
    return "", ""


def _folder_names(folder: str, cache: dict[str, set[str]]) -> set[str]:
    key = os.path.normcase(folder)
    if key not in cache:
        try:
            cache[key] = {n.lower() for n in os.listdir(folder)}
        except OSError:
            cache[key] = set()
    return cache[key]


def build_preview(items: list[FileItem], rules: list[Rule], cancel: Cancel = None) -> Preview:
    """New name for every file, and every reason a rename would fail.

    Names are compared ignoring upper/lower case, as Windows does.
    """
    for rule in rules:
        if rule.enabled:
            rule.check()

    rows: list[PreviewRow] = []
    for index, item in enumerate(items):
        if cancel is not None and index % 500 == 0 and cancel.is_set():
            raise RenameError("Stopped.")
        info = FileInfo(index=index, modified=item.modified, created=item.created)
        new = apply_rules(item.name, rules, info)
        row = PreviewRow(item=item, new_name=new, status=SAME if new == item.name else OK)
        if row.status == OK:
            problem, detail = name_problem(new)
            ext = os.path.splitext(item.name)[1]
            if not problem and ext and new.lower() == ext.lower():
                problem, detail = "Empty name", f"Only the extension would be left ({new})."
            if not problem and len(row.new_path) > MAX_PATH:
                problem = f"Path too long ({len(row.new_path)})"
                detail = (f"The full path would be {len(row.new_path)} characters; most Windows programs "
                          f"accept up to {MAX_PATH}.")
            if problem:
                row.block(problem, detail)
        rows.append(row)

    # Two files must not end up with the same name in the same folder.
    targets: dict[tuple[str, str], list[PreviewRow]] = defaultdict(list)
    for row in rows:
        targets[(os.path.normcase(row.item.folder), row.new_name.lower())].append(row)
    for group in targets.values():
        if len(group) > 1:
            for row in group:
                if row.status != BLOCKED or not row.problem:
                    row.block(f"Duplicate name ({len(group)} files)",
                              f"{len(group)} files in this folder would get the same name. Add a numbering "
                              "or date rule to keep them apart.")

    # A file that is already there (and is not itself being renamed away) can't be replaced.
    cache: dict[str, set[str]] = {}
    leaving: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.status != SAME:
            leaving[os.path.normcase(row.item.folder)].add(row.item.name.lower())
    for row in rows:
        if row.status != OK:
            continue
        folder = os.path.normcase(row.item.folder)
        occupied = _folder_names(row.item.folder, cache) - leaving[folder]
        if row.new_name.lower() in occupied:
            row.block("Name already in use",
                      "Another file in this folder already has this name. EZ Bulk Rename never replaces a file.")

    return Preview(rows=rows,
                   changing=sum(r.status == OK for r in rows),
                   unchanged=sum(r.status == SAME for r in rows),
                   blocked=sum(r.status == BLOCKED for r in rows))


# ================================================================ renaming
def _human_error(path: str, exc: OSError) -> str:
    name = os.path.basename(path)
    if isinstance(exc, PermissionError):
        return f"{name} is open in another program or is read-only. Close it and try again."
    if isinstance(exc, FileNotFoundError):
        return f"{name} is no longer there. It was moved, renamed or deleted."
    if isinstance(exc, FileExistsError):
        return f"Something named {name} appeared in the folder meanwhile."
    return f"{name} could not be renamed: {exc.strerror or 'disk error'}."


def _move(src: str, dst: str) -> None:
    """Rename, refusing to replace anything (os.rename would overwrite on Linux and macOS)."""
    if os.path.lexists(dst) and os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(dst)):
        raise FileExistsError(17, "exists", dst)
    os.rename(src, dst)


def rename_pairs(pairs: list[tuple[str, str]], cancel: Cancel = None) -> list[tuple[str, str]]:
    """Rename every (old, new) pair, all or nothing.

    Step 1 moves every file to a unique temporary name in its own folder; step 2
    moves each temporary file to its new name. If anything fails, every file is
    moved back to where it started and RenameError explains which file and why.
    Returns the pairs that were renamed.
    """
    batch = uuid.uuid4().hex[:8]
    # Where each file is right now, so a failure can put it back.
    moves: list[dict] = []
    try:
        for n, (old, new) in enumerate(pairs):
            if cancel is not None and cancel.is_set():
                raise RenameError("Stopped. Nothing was renamed.")
            tmp = os.path.join(os.path.dirname(old), f"{TEMP_PREFIX}{batch}-{n}.tmp")
            try:
                _move(old, tmp)
            except OSError as exc:
                raise RenameError(_human_error(old, exc) + " Nothing was renamed.") from None
            moves.append({"old": old, "new": new, "at": tmp})
        for move in moves:
            try:
                _move(move["at"], move["new"])
            except OSError as exc:
                raise RenameError(_human_error(move["new"], exc) + " Nothing was renamed.") from None
            move["at"] = move["new"]
    except BaseException:
        _put_back(moves)
        raise
    return [(m["old"], m["new"]) for m in moves]


def _put_back(moves: list[dict]) -> None:
    """Best effort: every file back to its original name, last moved first.

    Two passes: in a swap (a -> b, b -> a), one file's original name is only free
    once the other file has moved back.
    """
    for _pass in range(2):
        for move in reversed(moves):
            if move["at"] == move["old"]:
                continue
            if os.path.lexists(move["at"]) and not os.path.lexists(move["old"]):
                try:
                    os.rename(move["at"], move["old"])
                    move["at"] = move["old"]
                except OSError:
                    pass


def write_log(pairs: list[tuple[str, str]], log_dir: str) -> str:
    """Save the batch as a CSV that opens in Excel. Written before anything is renamed."""
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(log_dir, f"rename_{stamp}_{len(pairs)}-files.csv")
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(log_dir, f"rename_{stamp}_{len(pairs)}-files_{n}.csv")
    fd, tmp = tempfile.mkstemp(prefix=".ezrename-log-", suffix=".tmp", dir=log_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(LOG_HEADER)
            writer.writerows(pairs)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise RenameError(f"Can't write the undo log in {log_dir}: {exc.strerror or 'disk error'}. "
                          "Nothing was renamed.") from None
    return path


def apply_preview(preview: Preview, log_dir: str, cancel: Cancel = None) -> RenameResult:
    """Rename every row marked OK. Refuses while any row is blocked."""
    if preview.blocked:
        raise RenameError(f"Fix the {preview.blocked} problem{'s' if preview.blocked != 1 else ''} "
                          "shown in red first. Nothing was renamed.")
    pairs = [(r.item.path, r.new_path) for r in preview.rows if r.status == OK]
    if not pairs:
        raise RenameError("No file would change. Add or change a rule first.")
    log = write_log(pairs, log_dir)
    try:
        done = rename_pairs(pairs, cancel)
    except RenameError:
        # Nothing changed, so the log would only confuse a later undo.
        try:
            os.remove(log)
        except OSError:
            pass
        raise
    return RenameResult(renamed=len(done), log_path=log)


# ================================================================ undo
def read_log(path: str) -> list[tuple[str, str]]:
    """(old path, new path) pairs from an undo log."""
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    except OSError as exc:
        raise RenameError(f"Can't open {name}: {exc.strerror or 'disk error'}.") from None
    except UnicodeDecodeError:
        raise RenameError(f"{name} is not an EZ Bulk Rename undo log.") from None
    if not rows or [c.strip() for c in rows[0][:2]] != LOG_HEADER:
        raise RenameError(f"{name} is not an EZ Bulk Rename undo log.")
    pairs = [(r[0], r[1]) for r in rows[1:] if len(r) >= 2 and r[0] and r[1]]
    if not pairs:
        raise RenameError(f"{name} has no renames in it.")
    return pairs


def undo(pairs: list[tuple[str, str]], cancel: Cancel = None) -> UndoResult:
    """Rename every file in a log back to its old name, where that is still possible.

    A file that was moved, renamed again or deleted since is skipped with a
    reason; everything else goes back, all or nothing.
    """
    back: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    for old, new in pairs:
        if os.path.lexists(new) and not os.path.lexists(old):
            back.append((new, old))
        elif os.path.lexists(old) and not os.path.lexists(new):
            skipped.append((old, "already has its old name"))
        elif os.path.lexists(old) and os.path.lexists(new):
            if os.path.normcase(old) == os.path.normcase(new) or os.path.samefile(old, new):
                back.append((new, old))          # case-only rename on a case-insensitive disk
            else:
                skipped.append((new, f"a file named {os.path.basename(old)} is there again"))
        else:
            skipped.append((new, "is no longer there (moved or deleted)"))
    done = rename_pairs(back, cancel) if back else []
    return UndoResult(restored=len(done), skipped=skipped)


# ================================================================ formatting
def plural(n: int, word: str, many: str = "") -> str:
    return f"{n:,} {word if n == 1 else (many or word + 's')}"


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if n >= 10 else f"{n:.1f} {unit}"
    return f"{n:.1f} GB"


def format_time(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""
