"""Each rename rule on its own, and stacked."""

from datetime import datetime

import pytest

from ezrename.rules import (AddTextRule, CaseRule, DateRule, ExtensionRule, FileInfo, ListRule, NumberRule,
                            RemoveRule, RenameError, ReplaceRule, apply_rules, split_name)

TS = datetime(2026, 10, 15, 9, 30).timestamp()
INFO = FileInfo(index=0, modified=TS, created=TS)


def run(name, *rules, index=0):
    return apply_rules(name, list(rules), FileInfo(index=index, modified=TS, created=TS))


def test_split_name_keeps_dots_in_the_name():
    assert split_name("report.final.pdf") == ("report.final", ".pdf")
    assert split_name("README") == ("README", "")


def test_replace_plain_text_ignores_case_by_default():
    assert run("Scan 001.PDF", ReplaceRule(find="scan", replace="Invoice")) == "Invoice 001.PDF"
    assert run("Scan 001.pdf", ReplaceRule(find="scan", replace="Invoice", match_case=True)) == "Scan 001.pdf"


def test_replace_never_touches_the_extension():
    assert run("pdf notes.pdf", ReplaceRule(find="pdf", replace="x")) == "x notes.pdf"


def test_replace_plain_text_is_literal():
    assert run("a+b.txt", ReplaceRule(find="+", replace="$1\\n")) == "a$1\\nb.txt"


def test_replace_regex():
    rule = ReplaceRule(find=r"IMG_(\d+)", replace=r"Photo \1", regex=True)
    assert run("IMG_0042.jpg", rule) == "Photo 0042.jpg"


def test_bad_regex_is_explained():
    with pytest.raises(RenameError, match="find pattern has a mistake"):
        ReplaceRule(find="([a-z", regex=True).check()


def test_add_text():
    assert run("report.pdf", AddTextRule(prefix="2026_", suffix="_final")) == "2026_report_final.pdf"


@pytest.mark.parametrize("position,expected", [
    ("before", "007_photo.jpg"), ("after", "photo_007.jpg"), ("replace", "007.jpg")])
def test_numbering_positions(position, expected):
    rule = NumberRule(start=1, step=2, digits=3, position=position)
    assert run("photo.jpg", rule, index=3) == expected


def test_numbering_step_zero_is_refused():
    with pytest.raises(RenameError, match="step can't be 0"):
        NumberRule(step=0).check()


def test_date_from_modified():
    assert run("scan.pdf", DateRule(format="2026-10-15")) == "2026-10-15_scan.pdf"
    assert run("scan.pdf", DateRule(format="20261015", position="after", separator="-")) == "scan-20261015.pdf"
    assert run("scan.pdf", DateRule(format="2026-10-15_0930")) == "2026-10-15_0930_scan.pdf"


@pytest.mark.parametrize("mode,expected", [
    ("lower", "invoice march.PDF"), ("upper", "INVOICE MARCH.PDF"),
    ("title", "Invoice March.PDF"), ("sentence", "Invoice march.PDF")])
def test_case(mode, expected):
    assert run("inVOICE march.PDF", CaseRule(mode=mode)) == expected


def test_remove_and_clean_up():
    rule = RemoveRule(characters="#()", spaces="underscore")
    assert run("  Scan (copy)  #2 .pdf", rule) == "Scan_copy_2.pdf"
    assert run("a   b.txt", RemoveRule()) == "a b.txt"


def test_extension():
    assert run("photo.JPEG", ExtensionRule(new_extension="jpg")) == "photo.jpg"
    assert run("photo.JPG", ExtensionRule(case="lower")) == "photo.jpg"
    with pytest.raises(RenameError):
        ExtensionRule(new_extension="p df").check()


def test_rename_from_a_list():
    rule = ListRule(mapping={"s001": "John Tan", "s002.pdf": "Siti Aminah.pdf", "s003": "A. Rahman"})
    assert run("S001.pdf", rule) == "John Tan.pdf"            # keeps the file's extension
    assert run("S002.PDF", rule) == "Siti Aminah.pdf"         # the list's extension wins
    assert run("S003.pdf", rule) == "A. Rahman.pdf"           # "A." is not an extension
    assert run("S999.pdf", rule) == "S999.pdf"                # not on the list: unchanged


def test_rules_stack_in_order():
    rules = [RemoveRule(spaces="underscore"), NumberRule(digits=2), CaseRule(mode="lower")]
    assert run("My Scan.PDF", *rules, index=4) == "05_my_scan.PDF"
    # Same rules, case first: the number is added after, nothing else changes.
    assert run("My Scan.PDF", CaseRule(mode="lower"), RemoveRule(spaces="underscore"), NumberRule(digits=2),
               index=4) == "05_my_scan.PDF"


def test_disabled_rule_is_skipped():
    assert run("a.txt", AddTextRule(prefix="x", enabled=False)) == "a.txt"
