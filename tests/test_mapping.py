"""Rename lists from CSV and Excel.

CSV test files are written with write_bytes: write_text() would change the
line endings on Windows.
"""

import pytest
from openpyxl import Workbook

from ezrename.mapping import load_mapping
from ezrename.rules import RenameError


def test_csv_with_header(tmp_path):
    path = tmp_path / "staff.csv"
    path.write_bytes("Staff ID,Nama\r\nS001,John Tan\r\nS002,Siti Aminah\r\n".encode("utf-8-sig"))
    mapping, dupes = load_mapping(str(path))
    assert mapping == {"s001": "John Tan", "s002": "Siti Aminah"}
    assert dupes == 0


def test_csv_semicolon_without_header(tmp_path):
    path = tmp_path / "list.csv"
    path.write_bytes(b"IMG_001.jpg;Front door.jpg\nIMG_002.jpg;Back door.jpg\n")
    mapping, _ = load_mapping(str(path))
    assert mapping["img_001.jpg"] == "Front door.jpg"


def test_excel_and_duplicates(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Old name", "New name"])
    ws.append(["S001", "John Tan"])
    ws.append(["s001", "Someone Else"])
    ws.append([1002, "Number in Excel"])
    path = tmp_path / "staff.xlsx"
    wb.save(path)
    mapping, dupes = load_mapping(str(path))
    assert mapping == {"s001": "John Tan", "1002": "Number in Excel"}
    assert dupes == 1


def test_empty_list_is_explained(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_bytes(b"only one column\n")
    with pytest.raises(RenameError, match="two filled-in columns"):
        load_mapping(str(path))


def test_wrong_file_type(tmp_path):
    path = tmp_path / "list.docx"
    path.write_bytes(b"x")
    with pytest.raises(RenameError, match="Excel workbook"):
        load_mapping(str(path))
