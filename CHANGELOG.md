# Changelog

## 1.0.0 — not released yet

First version, built to the EZKerja tool standard from EZ Text Compare's source.

**Add files**
- Drag files and folders onto the window, use Add files / Add folder, or right-click in
  Explorer > Send to > EZ Bulk Rename (optional, ticked in the installer).
- Include subfolders; only these extensions; number in order of name, date modified, date
  created or size. Files sort as Explorer does (file2 before file10).

**Rules** — stacked, reordered with arrows, switched off without deleting
- Find and replace (plain text or regular expression, match case optional).
- Add text before or after the name.
- Numbering: start, step, digits (zero padding), before / after / instead of the name.
- Insert date: date modified or created, four formats, before or after.
- Change case: lower, UPPER, Title, Sentence.
- Remove / clean up: characters, spaces to _ or - or removed, trim the ends, collapse repeats.
- Change extension, or only its case.
- Names from a list: old name → new name from an Excel or CSV file (e.g. staff ID → name).

**Safety**
- Live preview of every new name. Rows that would fail are red with the reason, and Rename stays
  off until they are fixed: duplicate names, characters and names Windows refuses, a file already
  there, path or name too long, an empty name.
- Two-step rename with full rollback on any failure. Files are never deleted, copied or opened.
- An undo log (CSV) for every batch, written before the first rename. Undo the last rename
  (also Ctrl+Z), or any older batch from its log.
- After a rename the table shows what was renamed, and Rename stays off until something changes,
  so the same rules can't be applied twice by accident.

**Everything else**
- The last rules are remembered (a loaded name list is not — it can hold personal data).
- EZKerja look: light and dark mode, Segoe UI, teal 182°, REN icon, status bar.
- Installer without admin rights, and a portable zip. No registry keys in Explorer menus.
