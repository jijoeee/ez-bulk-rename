"""Rename rules. Each rule turns (name, extension) into a new (name, extension).

Rules are applied top to bottom, so they stack: "replace spaces with _", then
"add a number", then "lower case" gives a different result from the same rules
in another order — exactly what the preview shows.

No UI imports. A rule with a bad setting (an invalid regular expression, say)
raises RenameError with a sentence the user can act on.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class RenameError(Exception):
    """Something the user can fix. ``str(exc)`` is shown as is."""


@dataclass(frozen=True)
class FileInfo:
    """What a rule may look at besides the name: position in the list and file dates."""

    index: int            # 0-based position in the list, for numbering
    modified: float       # timestamps
    created: float


# The name is split as Windows Explorer shows it: "report.final.pdf" -> ("report.final", ".pdf").
def split_name(filename: str) -> tuple[str, str]:
    stem, ext = os.path.splitext(filename)
    return stem, ext


# ================================================================ the rules
@dataclass
class Rule:
    """Base class. ``enabled`` lets the user switch a rule off without losing it."""

    enabled: bool = True
    KIND = "rule"
    TITLE = "Rule"

    def apply(self, stem: str, ext: str, info: FileInfo) -> tuple[str, str]:  # pragma: no cover
        raise NotImplementedError

    def check(self) -> None:
        """Raise RenameError if a setting can't work. Called before every preview."""


@dataclass
class ReplaceRule(Rule):
    find: str = ""
    replace: str = ""
    match_case: bool = False
    regex: bool = False
    KIND = "replace"
    TITLE = "Find and replace"

    def _pattern(self) -> Optional[re.Pattern]:
        if not self.find:
            return None
        flags = 0 if self.match_case else re.IGNORECASE
        try:
            return re.compile(self.find if self.regex else re.escape(self.find), flags)
        except re.error as exc:
            where = f" (at character {exc.pos + 1})" if exc.pos is not None else ""
            raise RenameError(f"The find pattern has a mistake: {exc.msg}{where}.") from None

    def check(self) -> None:
        pattern = self._pattern()
        if pattern is not None and self.regex:
            try:
                pattern.sub(self.replace, "")
            except (re.error, IndexError) as exc:
                raise RenameError(f"The replacement has a mistake: {exc}.") from None

    def apply(self, stem, ext, info):
        pattern = self._pattern()
        if pattern is None:
            return stem, ext
        if self.regex:
            return pattern.sub(self.replace, stem), ext
        # Plain text replaces literally: a "\" or "$" typed by the user is just a character.
        return pattern.sub(lambda _m: self.replace, stem), ext


@dataclass
class AddTextRule(Rule):
    prefix: str = ""
    suffix: str = ""
    KIND = "add"
    TITLE = "Add text"

    def apply(self, stem, ext, info):
        return f"{self.prefix}{stem}{self.suffix}", ext


@dataclass
class NumberRule(Rule):
    start: int = 1
    step: int = 1
    digits: int = 3
    position: str = "before"      # before | after | replace
    separator: str = "_"
    KIND = "number"
    TITLE = "Numbering"

    def check(self) -> None:
        if self.digits < 1 or self.digits > 10:
            raise RenameError("Numbering: digits must be between 1 and 10.")
        if self.step == 0:
            raise RenameError("Numbering: the step can't be 0, or every file gets the same number.")

    def number(self, index: int) -> str:
        n = self.start + index * self.step
        sign = "-" if n < 0 else ""
        return sign + str(abs(n)).zfill(self.digits)

    def apply(self, stem, ext, info):
        n = self.number(info.index)
        if self.position == "replace":
            return n, ext
        if self.position == "after":
            return f"{stem}{self.separator}{n}", ext
        return f"{n}{self.separator}{stem}", ext


DATE_FORMATS = {
    "2026-10-15": "%Y-%m-%d",
    "20261015": "%Y%m%d",
    "15-10-2026": "%d-%m-%Y",
    "2026-10-15_0930": "%Y-%m-%d_%H%M",
}


@dataclass
class DateRule(Rule):
    source: str = "modified"      # modified | created
    format: str = "2026-10-15"    # a key of DATE_FORMATS, shown as an example
    position: str = "before"      # before | after
    separator: str = "_"
    KIND = "date"
    TITLE = "Insert date"

    def apply(self, stem, ext, info):
        ts = info.created if self.source == "created" else info.modified
        text = datetime.fromtimestamp(ts).strftime(DATE_FORMATS.get(self.format, "%Y-%m-%d"))
        if self.position == "after":
            return f"{stem}{self.separator}{text}", ext
        return f"{text}{self.separator}{stem}", ext


@dataclass
class CaseRule(Rule):
    mode: str = "lower"           # lower | upper | title | sentence
    KIND = "case"
    TITLE = "Change case"

    def apply(self, stem, ext, info):
        if self.mode == "upper":
            return stem.upper(), ext
        if self.mode == "title":
            # Capitalise each word; "invoice_march-2026" -> "Invoice_March-2026".
            return re.sub(r"[^\W_]+", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), stem), ext
        if self.mode == "sentence":
            lowered = stem.lower()
            m = re.search(r"[^\W\d_]", lowered)
            if m:
                lowered = lowered[:m.start()] + lowered[m.start()].upper() + lowered[m.start() + 1:]
            return lowered, ext
        return stem.lower(), ext


@dataclass
class RemoveRule(Rule):
    characters: str = ""         # every one of these characters is removed
    spaces: str = "keep"          # keep | remove | underscore | dash
    trim: bool = True             # remove spaces, dots, dashes and underscores at the ends
    collapse: bool = True         # "a  b" -> "a b", "a__b" -> "a_b"
    KIND = "remove"
    TITLE = "Remove / clean up"

    def apply(self, stem, ext, info):
        if self.characters:
            stem = "".join(ch for ch in stem if ch not in self.characters)
        replacement = {"remove": "", "underscore": "_", "dash": "-"}.get(self.spaces)
        if replacement is not None:
            stem = re.sub(r"\s+", replacement, stem)
        if self.collapse:
            stem = re.sub(r"([ _\-.])\1+", r"\1", stem)
        if self.trim:
            stem = stem.strip(" ._-")
        return stem, ext


@dataclass
class ExtensionRule(Rule):
    new_extension: str = ""       # "" keeps the extension; "pdf" or ".pdf" changes it
    case: str = "keep"            # keep | lower | upper
    KIND = "extension"
    TITLE = "Change extension"

    def check(self) -> None:
        if re.search(r'[<>:"/\\|?*\s]', self.new_extension.strip(".")):
            raise RenameError("The new extension can't contain spaces or any of < > : \" / \\ | ? *")

    def apply(self, stem, ext, info):
        new = self.new_extension.strip()
        if new:
            ext = "." + new.lstrip(".")
        if self.case == "lower":
            ext = ext.lower()
        elif self.case == "upper":
            ext = ext.upper()
        return stem, ext


@dataclass
class ListRule(Rule):
    """Rename from a list: old name -> new name, loaded from Excel or CSV.

    Matching ignores upper/lower case (as Windows does) and, unless the list has
    extensions, the extension too. A new name without an extension keeps the
    file's own extension.
    """

    mapping: dict[str, str] = field(default_factory=dict)   # lower-case old name -> new name
    source: str = ""                                          # file the list came from, for display
    KIND = "list"
    TITLE = "Names from a list"

    def apply(self, stem, ext, info):
        new = self.mapping.get((stem + ext).lower()) or self.mapping.get(stem.lower())
        if new is None:
            return stem, ext
        new_stem, new_ext = split_name(new)
        # "John Tan" has no extension; "John Tan.pdf" has one. A dot inside a name such as
        # "A. Rahman" is not an extension unless it looks like one.
        if new_ext and re.fullmatch(r"\.[A-Za-z0-9]{1,8}", new_ext):
            return new_stem, new_ext
        return new, ext


RULE_TYPES: dict[str, type[Rule]] = {
    cls.KIND: cls for cls in (ReplaceRule, AddTextRule, NumberRule, DateRule, CaseRule, RemoveRule,
                              ExtensionRule, ListRule)
}


def apply_rules(filename: str, rules: list[Rule], info: FileInfo) -> str:
    """The new file name after every enabled rule, top to bottom."""
    stem, ext = split_name(filename)
    for rule in rules:
        if rule.enabled:
            stem, ext = rule.apply(stem, ext, info)
    return stem + ext
