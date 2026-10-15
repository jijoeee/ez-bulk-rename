# EZ Bulk Rename — source

Rename hundreds of files at once with simple rules, a live preview and undo. Offline.
Free, MIT licence. The public tool page is `../README.md`.

## Build the Windows installer

1. Install **Python 3.12 64-bit** from python.org (3.13 also works) and, for the installer,
   **Inno Setup** (free): https://jrsoftware.org/isdl.php
2. Double-click **`build.bat`**. It makes a clean `.venv`, installs the pinned packages, runs the
   tests (the build stops if any fail), builds the app and the installer.
3. In `dist\` you get:
   - `EZ-Bulk-Rename-Setup-1.0.0.exe` — the installer to publish
   - `EZ-Bulk-Rename-1.0.0-portable.zip` — the no-install version
   - `sandbox-test.wsb` — double-click to test on a clean Windows Sandbox
   - the SHA-256 of each file is printed at the end

Then work through `RELEASE_CHECKLIST.md` and `ANTIVIRUS.md`.

## Run from source

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python main.py                 & rem or: main.py "C:\Scans"
.venv\Scripts\python -m pytest -q
python check_palette.py ezrename\theme.py    & rem 34/34 must pass
```

## Layout

```
main.py                 entry point: logging, crash handler, paths from "Send to"
ezrename/
  __init__.py           version and identity (the only place the version lives)
  rules.py              the eight rename rules; each turns (name, extension) into a new one. No UI.
  engine.py             collecting files, preview checks, two-step rename with rollback, undo logs. No UI.
  mapping.py            "Rename from list": reading .xlsx / .csv. No UI.
  tools.py              the rename screen: preview table, files options, rule cards, undo menu
  widgets.py            buttons, drop zone, result panel, preview table, rule card
  app.py                main window: header, status bar, drag and drop, keys, About
  theme.py              colours (teal 182°), fonts, icons
  system.py             paths, settings, logging, OS helpers
tests/                  pytest: rules, engine (real files in a temp folder), mapping, palette
assets/, brand/         generated icons and the EZKerja logo master
installer/installer.iss Inno Setup script (per-user, no admin; optional "Send to" shortcut)
```

## How renaming stays safe

- **Preview first.** Nothing is renamed while any row is red: two files getting the same name,
  a name Windows refuses (`< > : " / \ | ? *`, `CON`, `NUL`..., a trailing space or dot), a file
  already in the folder, a path longer than 259 characters, or an empty name.
- **Only renames.** Files are never deleted, copied, moved to another folder or opened.
- **Two steps.** Every file goes to a temporary name in its own folder first, then to its new
  name. That makes swaps (`a`→`b`, `b`→`a`) and case-only changes work. If any step fails — a file
  open in Excel, say — every file already moved is put back and nothing has changed.
- **Undo log first.** Each batch is written to a CSV in `%APPDATA%\EZKerja\EZ Bulk Rename\undo-logs`
  *before* the first rename, so even a power cut halfway can be undone from the log. Undo puts back
  every file it still can and lists the ones that were moved or deleted since.
- **Names are compared ignoring case**, as Windows does, on every OS — so the tests on the Pi
  check the same rules Windows applies.

## Notes

- **"Rename from list"** reads the first two filled-in columns of the first sheet. A header row
  ("Old name | New name", "Staff ID | Nama") is skipped. The list itself is never saved in
  settings: it often holds staff names.
- **The last rules are remembered** between sessions (in `settings.json`), so a monthly job is one
  drop and one click.
- **No Explorer context-menu registry keys.** EZ File Searcher's first installer, which added
  them, was flagged by Microsoft Defender. "Send to" gives the same right-click route with only a
  shortcut file.
