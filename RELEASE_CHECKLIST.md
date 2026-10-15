# Release checklist

Work through this for every public release. It takes about 30 minutes.

## 1. Version
- [ ] Bump `__version__` in `ezrename/__init__.py` (the only place it's defined).
- [ ] Add an entry to `CHANGELOG.md`.

## 2. Build
- [ ] Inno Setup installed? Without it no installer is produced, only the app folder.
      Free from https://jrsoftware.org/isdl.php
- [ ] Double-click `build.bat`. Tests must pass or the build stops.
- [ ] Confirm `dist\EZ-Bulk-Rename-Setup-<version>.exe` exists. That single file is
      what you publish, not the `dist\EZ Bulk Rename\` folder.
- [ ] Confirm `dist\EZ-Bulk-Rename-<version>-portable.zip` exists (the no-install version).
- [ ] Note the SHA-256 checksums it prints.

## 3. Test on a clean Windows (no Python installed)
Windows Sandbox is free on Windows 10/11 Pro. Turn it on once via
"Turn Windows features on or off" > Windows Sandbox.

- [ ] Double-click `dist\sandbox-test.wsb`. The release folder opens inside the sandbox.
- [ ] Run the installer. No admin prompt should appear.
- [ ] Check the Start menu icon, taskbar icon and title-bar icon all show the EZKerja logo.
- [ ] Right-click the .exe > Properties > Details: publisher and version are filled in.
Use **copies** of real files (scans, photos, invoices) in a test folder.

- [ ] Drag a folder onto the window, then a few loose files: all are listed, nothing duplicated.
- [ ] "Include subfolders" and "Only these extensions" change the list as expected.
- [ ] Stack three rules (e.g. spaces to _, numbering, lower case); reorder them with the
      arrows: the preview changes accordingly before anything is renamed.
- [ ] Make two files get the same name: both rows turn red, Rename stays disabled.
- [ ] Type a name with  ?  or  :  and a name like CON: blocked with a clear reason.
- [ ] Rename. Open the folder in Explorer: names changed, contents and dates unchanged.
- [ ] Undo > Undo the last rename: every name back. Ctrl+Z does the same.
- [ ] Rename a file that is open in Word or Excel: a clear message, and NOTHING was renamed
      (check the other files too).
- [ ] Swap two names (a to b, b to a) and a case-only change (invoice.pdf to INVOICE.pdf).
- [ ] Names from a list: load an .xlsx and a .csv (Excel "CSV UTF-8") with a header row;
      Malay names with spaces come out correctly.
- [ ] Install with "Send to" ticked: right-click files in Explorer > Send to > EZ Bulk Rename
      opens them in the app.
- [ ] 2,000 files in one folder: the window stays responsive while the preview updates.
- [ ] Close and reopen the app: the last rules come back (the list in "Names from a list" does
      not — it is never saved).
- [ ] At 125% and 150% display scaling, the table and rule cards are sharp and nothing in the
      toolbar is clipped.
- [ ] Switch light/dark mode.
- [ ] Uninstall from Settings > Apps. Nothing should be left in Program Files, and the Send to
      shortcut is gone.

If Windows Sandbox isn't available, use a spare PC or a free Windows VM (VirtualBox).

## 4. Antivirus and SmartScreen

**Scan the installer, not a zip of the folder.** A zip of `dist\EZ Bulk Rename\`
makes scanners inspect dozens of loose DLLs out of context and inflates detections.
The installer is also what customers actually download.

- [ ] Upload the installer to https://www.virustotal.com and save the report link.
- [ ] Confirm the tags show `contains-pe` only. If `contains-elf` or `contains-macho`
      appears, another platform's binaries leaked in; check the filter in
      `ez_bulk_rename.spec`.
- [ ] Read the decision table in `ANTIVIRUS.md` and act on it. Short version:
      Defender clean and under about 3 small-engine hits is normal and publishable;
      Defender flagging it is a blocker.
- [ ] Submit any false positives (free): https://www.microsoft.com/en-us/wdsi/filesubmission
- [ ] Record the result in the submission log at the bottom of `ANTIVIRUS.md`.

## 5. Publish
- [ ] Upload the installer to the download location (keep a copy off the Orange Pi).
- [ ] Publish the SHA-256 checksum and VirusTotal link on the download page.
- [ ] Also upload the portable zip, with its own SHA-256.
