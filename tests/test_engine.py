"""Collecting, preview checks, safe renaming, undo — on real files in a temp folder."""

import os

import pytest

from ezrename import engine
from ezrename.engine import BLOCKED, OK, SAME, apply_preview, build_preview, collect, read_log, undo
from ezrename.rules import AddTextRule, CaseRule, NumberRule, RenameError, ReplaceRule


def make(folder, *names):
    for name in names:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"content of {name}".encode())
    return folder


def names(folder):
    return sorted(p.name for p in folder.iterdir() if p.is_file())


def content(folder, name):
    return (folder / name).read_bytes().decode()


# ---------------------------------------------------------------- collecting
def test_collect_folder_natural_order_and_filters(tmp_path):
    make(tmp_path, "file10.pdf", "file2.pdf", "file1.jpg", "sub/deep.pdf")
    items = collect([str(tmp_path)])
    assert [i.name for i in items] == ["file1.jpg", "file2.pdf", "file10.pdf"]
    assert [i.name for i in collect([str(tmp_path)], extensions=engine.parse_extensions("PDF"))] == \
        ["file2.pdf", "file10.pdf"]
    assert "deep.pdf" in [i.name for i in collect([str(tmp_path)], include_subfolders=True)]


def test_collect_dedupes_and_skips_temp_files(tmp_path):
    make(tmp_path, "a.txt", ".ezrename-1234-0.tmp")
    items = collect([str(tmp_path), str(tmp_path / "a.txt")])
    assert [i.name for i in items] == ["a.txt"]


def test_parse_extensions():
    assert engine.parse_extensions("pdf, .JPG docx") == frozenset({".pdf", ".jpg", ".docx"})
    assert engine.parse_extensions("  ") == frozenset()


# ---------------------------------------------------------------- preview checks
def test_preview_marks_changed_and_unchanged(tmp_path):
    make(tmp_path, "scan 1.pdf", "report.pdf")
    p = build_preview(collect([str(tmp_path)]), [ReplaceRule(find="scan", replace="Invoice")])
    status = {r.item.name: (r.status, r.new_name) for r in p.rows}
    assert status["scan 1.pdf"] == (OK, "Invoice 1.pdf")
    assert status["report.pdf"] == (SAME, "report.pdf")
    assert p.can_apply


def test_duplicate_new_names_are_blocked(tmp_path):
    make(tmp_path, "a1.txt", "a2.txt")
    p = build_preview(collect([str(tmp_path)]), [ReplaceRule(find=r"\d", replace="", regex=True)])
    assert [r.status for r in p.rows] == [BLOCKED, BLOCKED]
    assert "same name" in p.rows[0].problem
    assert not p.can_apply


def test_existing_file_is_never_replaced(tmp_path):
    make(tmp_path, "a.txt", "b.txt")
    items = [i for i in collect([str(tmp_path)]) if i.name == "a.txt"]
    p = build_preview(items, [ReplaceRule(find="a", replace="b")])
    assert p.rows[0].status == BLOCKED
    assert "already in the folder" in p.rows[0].problem


def test_name_freed_in_the_same_batch_is_allowed(tmp_path):
    # a -> b while b -> c: b's name is free by the end, so this is fine.
    make(tmp_path, "a.txt", "b.txt")
    items = collect([str(tmp_path)])
    p = build_preview(items, [ReplaceRule(find="b", replace="c"), ReplaceRule(find="a", replace="b")])
    assert [r.new_name for r in p.rows] == ["b.txt", "c.txt"]
    assert p.can_apply


@pytest.mark.parametrize("bad,reason", [
    ("a?b", "doesn't allow"), ("CON", "reserves"), ("nul", "reserves")])
def test_illegal_windows_names_are_blocked(tmp_path, bad, reason):
    make(tmp_path, "file.txt")
    rule = ReplaceRule(find="file", replace=bad)
    p = build_preview(collect([str(tmp_path)]), [rule])
    assert p.rows[0].status == BLOCKED, p.rows[0].new_name
    assert reason in p.rows[0].problem


def test_name_ending_in_space_is_blocked(tmp_path):
    # "x .txt" is fine on Windows; a space or dot at the very end of the whole name is not.
    make(tmp_path, "file")
    p = build_preview(collect([str(tmp_path)]), [AddTextRule(suffix=" ")])
    assert p.rows[0].status == BLOCKED
    assert "end with" in p.rows[0].problem


def test_path_too_long_is_blocked(tmp_path):
    make(tmp_path, "a.txt")
    p = build_preview(collect([str(tmp_path)]), [AddTextRule(prefix="x" * 250)])
    assert p.rows[0].status == BLOCKED
    assert "too long" in p.rows[0].problem


def test_empty_name_is_blocked(tmp_path):
    make(tmp_path, "abc.txt")
    p = build_preview(collect([str(tmp_path)]), [ReplaceRule(find="abc", replace="")])
    assert p.rows[0].status == BLOCKED


# ---------------------------------------------------------------- renaming
def test_apply_renames_and_writes_a_log(tmp_path):
    folder, logs = make(tmp_path / "docs", "scan1.pdf", "scan2.pdf"), tmp_path / "logs"
    p = build_preview(collect([str(folder)]), [NumberRule(digits=2), ReplaceRule(find="scan", replace="inv")])
    result = apply_preview(p, str(logs))
    assert result.renamed == 2
    assert names(folder) == ["01_inv1.pdf", "02_inv2.pdf"]
    assert content(folder, "01_inv1.pdf") == "content of scan1.pdf"      # contents untouched
    assert len(read_log(result.log_path)) == 2


def test_swap_two_names(tmp_path):
    folder = make(tmp_path, "a.txt", "b.txt")
    items = collect([str(folder)])
    p = build_preview(items, [ReplaceRule(find="a", replace="TMP"), ReplaceRule(find="b", replace="a"),
                              ReplaceRule(find="TMP", replace="b")])
    apply_preview(p, str(tmp_path / "logs"))
    assert content(folder, "a.txt") == "content of b.txt"
    assert content(folder, "b.txt") == "content of a.txt"


def test_case_only_rename(tmp_path):
    folder = make(tmp_path / "d", "invoice.pdf")
    apply_preview(build_preview(collect([str(folder)]), [CaseRule(mode="upper")]), str(tmp_path / "logs"))
    assert names(folder) == ["INVOICE.pdf"]


def test_blocked_preview_renames_nothing(tmp_path):
    folder = make(tmp_path / "d", "a1.txt", "a2.txt")
    p = build_preview(collect([str(folder)]), [ReplaceRule(find=r"\d", replace="", regex=True)])
    with pytest.raises(RenameError, match="Fix the 2 problems"):
        apply_preview(p, str(tmp_path / "logs"))
    assert names(folder) == ["a1.txt", "a2.txt"]


def test_failure_halfway_puts_everything_back(tmp_path, monkeypatch):
    folder = make(tmp_path / "d", "a.txt", "b.txt", "c.txt")
    p = build_preview(collect([str(folder)]), [AddTextRule(prefix="x_")])
    real_rename = os.rename
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 5:            # fail during the second step
            raise PermissionError(13, "Permission denied", src)
        return real_rename(src, dst)

    monkeypatch.setattr(engine.os, "rename", flaky)
    with pytest.raises(RenameError, match="open in another program"):
        apply_preview(p, str(tmp_path / "logs"))
    monkeypatch.setattr(engine.os, "rename", real_rename)
    assert names(folder) == ["a.txt", "b.txt", "c.txt"]
    assert content(folder, "b.txt") == "content of b.txt"
    assert not list((tmp_path / "logs").glob("*.csv"))     # nothing renamed, so no log kept


# ---------------------------------------------------------------- undo
def test_undo_puts_names_back(tmp_path):
    folder = make(tmp_path / "d", "a.txt", "b.txt")
    result = apply_preview(build_preview(collect([str(folder)]), [AddTextRule(prefix="new_")]),
                           str(tmp_path / "logs"))
    assert names(folder) == ["new_a.txt", "new_b.txt"]
    u = undo(read_log(result.log_path))
    assert u.restored == 2 and not u.skipped
    assert names(folder) == ["a.txt", "b.txt"]


def test_undo_skips_files_changed_since(tmp_path):
    folder = make(tmp_path / "d", "a.txt", "b.txt")
    result = apply_preview(build_preview(collect([str(folder)]), [AddTextRule(prefix="new_")]),
                           str(tmp_path / "logs"))
    (folder / "new_b.txt").unlink()                      # someone deleted it meanwhile
    u = undo(read_log(result.log_path))
    assert u.restored == 1
    assert len(u.skipped) == 1 and "no longer there" in u.skipped[0][1]
    assert names(folder) == ["a.txt"]


def test_read_log_refuses_other_csv(tmp_path):
    other = tmp_path / "other.csv"
    other.write_bytes(b"Name,Age\nA,1\n")
    with pytest.raises(RenameError, match="not an EZ Bulk Rename undo log"):
        read_log(str(other))
