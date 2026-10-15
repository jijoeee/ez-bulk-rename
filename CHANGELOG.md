# Changelog

## 1.0.0 — not released yet

First version, built to the EZKerja tool standard from EZ Text Compare's source.

**Add files**
- Drag files and folders onto the window, use Add files / Add folder, or right-click in
  Explorer > Send to > EZ Bulk Rename (optional, ticked in the installer).
- Include subfolders; tick the file types to rename (detected from the files, with counts);
  number in order of name, date modified, date
  created or size. Files sort as Explorer does (file2 before file10).

**Rules** — stacked, reordered with arrows, switched off without deleting
- Find and replace (plain text or regular expression, match case optional).
- Add text before or after the name.
- Numbering: start, step, digits (zero padding), before / after / instead of the name.
- Insert date: date modified or created, four formats, before or after.
- Change case: lower, UPPER, Title, Sentence.
- Clean up: characters, spaces to _ or - or removed, trim the ends, collapse repeats.
- Change extension, or only its case.
- Rename from list: old name → new name from an Excel or CSV file (e.g. staff ID → name).

**Safety**
- Live preview of every new name. Rows that would fail are red with the reason, and Rename stays
  off until they are fixed: duplicate names, characters and names Windows refuses, a file already
  there, path or name too long, an empty name.
- Two-step rename with full rollback on any failure. Files are never deleted, copied or opened.
- An undo log (CSV) for every batch, written before the first rename. Undo the last rename
  (also Ctrl+Z), or any older batch from its log.
- After a rename the table shows what was renamed, and Rename stays off until something changes,
  so the same rules can't be applied twice by accident.

**Polish (after the Boss's first review, 2026-10-15)**
- File types as tick boxes instead of typing extensions.
- "+ Add a rule" returns to its place after the last rule is removed.
- Light mode has a deep teal header bar and table header instead of all white.
- Professional wording: All / To rename / Issues; short reasons in the table, the full
  explanation when a row is clicked; no file count on the button while issues remain.
- Fixed: clearing the list while a preview was being built could re-enable Rename; a folder
  scan could be cancelled by a preview started meanwhile; desktop.ini, Thumbs.db and ~$
  Office lock files were listed for renaming.

**Everything else**
- The last rules are remembered (a loaded name list is not — it can hold personal data).
- EZKerja look: light and dark mode, Segoe UI, teal 182°, REN icon, status bar.
- Installer without admin rights, and a portable zip. No registry keys in Explorer menus.
