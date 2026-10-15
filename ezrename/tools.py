"""The rename screen: the preview table on the left, files and rules on the right."""

from __future__ import annotations

import copy
import dataclasses
import logging
import os
import threading
import tkinter as tk
import tkinter.filedialog as fd
from typing import Optional

import customtkinter as ctk

from . import engine
from . import rules as R
from . import theme as T
from .engine import FileItem, Preview
from .mapping import load_mapping
from .rules import RenameError
from .system import app_data_dir, open_path, reveal_in_folder
from .widgets import (AutoScrollFrame, DropZone, PreviewTable, ResultPanel, RuleCard, checkbox, divider,
                      primary_button, secondary_button, section_label, set_entry_text, text_entry)

log = logging.getLogger("ezrename.tools")

ORDER_OPTIONS = [("Name", "name"), ("Date modified", "modified"), ("Date created", "created"), ("Size", "size")]
VIEW_OPTIONS = [("All files", "all"), ("Will change", "changes"), ("Problems", "problems")]
ADD_RULE_LABEL = "+ Add a rule"


def undo_log_dir() -> str:
    path = os.path.join(app_data_dir(), "undo-logs")
    os.makedirs(path, exist_ok=True)
    return path


class RenameTool(ctk.CTkFrame):
    title = "Bulk rename"
    icon = "rename"
    description = ("Rename many files at once with simple rules. Check the preview, then click "
                   "Rename. Every batch can be undone.")

    def __init__(self, master, app):
        super().__init__(master, fg_color=T.BG, corner_radius=0)
        self.app = app
        self.busy = False
        self.added_paths: list[str] = []          # what the user dropped or chose (files and folders)
        self.items: list[FileItem] = []           # the files, in numbering order
        self.rules: list[R.Rule] = []
        self.cards: list[RuleCard] = []
        self.preview: Optional[Preview] = None
        self._gen = 0
        self._preview_job = None
        self._just_renamed = False                # Rename stays off until something changes
        self._renamed_paths: set[str] = set()     # new paths of the last rename, for the table

        # The sidebar is packed first so it always keeps its width; the work area gets the rest.
        self._build_sidebar()
        self._build_work_area()
        self._load_settings()
        self.show_empty()

    # ================================================================ layout
    def _build_work_area(self):
        self.work = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=0)
        self.work.pack(side="left", fill="both", expand=True)
        self.drop_zone = DropZone(self.work, self.choose_files)

        self.toolbar = ctk.CTkFrame(self.work, fg_color=T.BG, corner_radius=0, height=56)
        self.toolbar.pack_propagate(False)
        # Buttons are packed before the labels so a long heading can never squeeze them.
        right = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        right.pack(side="right", fill="y", padx=(0, T.SPACE_4))
        # Sized to their text (CustomTkinter's default is 140 px each): the heading needs the room.
        secondary_button(right, "Clear", self.clear, icon="remove", width=76).pack(side="right", pady=11)
        self.undo_btn = secondary_button(right, "Undo", self.show_undo_menu, icon="undo", width=76)
        self.undo_btn.pack(side="right", pady=11, padx=(0, T.SPACE_2))
        secondary_button(right, "Add folder", self.choose_folder, icon="folder_add", width=110).pack(
            side="right", pady=11, padx=(0, T.SPACE_2))
        secondary_button(right, "Add files", self.choose_files, icon="file_add", width=100).pack(
            side="right", pady=11, padx=(0, T.SPACE_2))
        left = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(T.SPACE_4, T.SPACE_3))
        self.heading = ctk.CTkLabel(left, text="", font=T.font(14, True), text_color=T.TEXT)
        self.heading.pack(side="left", pady=T.SPACE_3)

        self.viewbar = ctk.CTkFrame(self.work, fg_color=T.BG, corner_radius=0)
        self.view = ctk.CTkSegmentedButton(
            self.viewbar, values=[t for t, _v in VIEW_OPTIONS], command=lambda _v: self._show_rows(),
            font=T.font(12), height=28, fg_color=T.BORDER, selected_color=T.SURFACE,
            selected_hover_color=T.SURFACE, unselected_color=T.BORDER, unselected_hover_color=T.HOVER,
            text_color=T.TEXT, corner_radius=T.RADIUS_S)
        self.view.set(VIEW_OPTIONS[0][0])
        self.view.pack(side="left")
        self.counts = ctk.CTkLabel(self.viewbar, text="", font=T.font(12), text_color=T.TEXT_2)
        self.counts.pack(side="left", padx=(T.SPACE_3, 0))

        self.table = PreviewTable(self.work)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=T.SIDEBAR_W, fg_color=T.SURFACE, corner_radius=0)
        self.sidebar.pack(side="right", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkFrame(self, width=2, fg_color=T.BORDER, corner_radius=0).pack(side="right", fill="y")

        # Footer stays pinned to the bottom: summary, progress, main action
        self.footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=T.SPACE_4, pady=T.SPACE_4)
        self.summary = ctk.CTkLabel(self.footer, text="", font=T.font(12), text_color=T.TEXT_2,
                                    justify="left", anchor="w", wraplength=T.SIDEBAR_W - 2 * T.SPACE_4)
        self.summary.pack(fill="x", pady=(0, T.SPACE_2))
        self.progress = ctk.CTkProgressBar(self.footer, height=6, corner_radius=3,
                                           fg_color=T.BORDER, progress_color=T.PRIMARY_TEXT)
        self.action_btn = primary_button(self.footer, "Rename", self.run, icon="rename")
        self.action_btn.pack(fill="x")

        # Everything else scrolls, so small laptop screens never clip the rules or the result
        self.side_scroll = AutoScrollFrame(self.sidebar, fg_color=T.SURFACE, corner_radius=0)
        self.side_scroll.pack(side="top", fill="both", expand=True, padx=(T.SPACE_4, T.SPACE_2),
                              pady=(T.SPACE_4, 0))
        head = ctk.CTkFrame(self.side_scroll, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="", image=T.icon(self.icon, 22, T.PRIMARY_TEXT)).pack(side="left", padx=(0, T.SPACE_2))
        ctk.CTkLabel(head, text=self.title, font=T.font(16, True), text_color=T.TEXT).pack(side="left")
        ctk.CTkLabel(self.side_scroll, text=self.description, font=T.font(12), text_color=T.TEXT_2,
                     justify="left", anchor="w", wraplength=T.CONTENT_W).pack(fill="x", pady=(T.SPACE_2, T.SPACE_3))
        divider(self.side_scroll, padx=(0, T.SPACE_3))
        self.options = ctk.CTkFrame(self.side_scroll, fg_color="transparent", width=T.CONTENT_W, height=1)
        self.options.pack(fill="x", pady=(T.SPACE_1, 0), padx=(0, T.SPACE_3))
        self.result_panel = ResultPanel(self.side_scroll)
        self.result_panel.pack(fill="x", pady=(T.SPACE_3, 0), padx=(0, T.SPACE_3))
        self._build_options()

    def _build_options(self):
        o = self.options
        section_label(o, "Files")
        self.sub_box, self.include_sub = checkbox(o, "Include subfolders", False, command=self.files_changed)
        ctk.CTkLabel(o, text="Only these extensions", font=T.font(12), text_color=T.TEXT, anchor="w").pack(
            fill="x", pady=(T.SPACE_2, T.SPACE_1))
        self.ext_entry = text_entry(o, "e.g. pdf jpg (empty = all files)")
        self.ext_entry.pack(fill="x")
        self.ext_entry.bind("<KeyRelease>", lambda e: self._later(self.files_changed, 400), add="+")
        ctk.CTkLabel(o, text="Number in this order", font=T.font(12), text_color=T.TEXT, anchor="w").pack(
            fill="x", pady=(T.SPACE_2, T.SPACE_1))
        self.order = ctk.CTkOptionMenu(
            o, values=[t for t, _v in ORDER_OPTIONS], command=lambda _v: self.reorder(), height=32,
            corner_radius=T.RADIUS_S, font=T.font(12), dropdown_font=T.font(12), fg_color=T.SURFACE_2,
            button_color=T.SURFACE_2, button_hover_color=T.HOVER, text_color=T.TEXT,
            dropdown_fg_color=T.SURFACE, dropdown_text_color=T.TEXT, dropdown_hover_color=T.HOVER)
        self.order.pack(fill="x")

        section_label(o, "Rules", top=T.SPACE_4)
        ctk.CTkLabel(o, text="Applied from top to bottom.", font=T.font(11), text_color=T.TEXT_2,
                     anchor="w").pack(fill="x")
        self.rules_box = ctk.CTkFrame(o, fg_color="transparent", height=1)
        self.rules_box.pack(fill="x")
        self.add_rule = ctk.CTkOptionMenu(
            o, values=[cls.TITLE for cls in R.RULE_TYPES.values()], command=self._add_rule_chosen,
            height=34, corner_radius=T.RADIUS_S, font=T.font(13, True), dropdown_font=T.font(12),
            fg_color=T.PRIMARY_SOFT, button_color=T.PRIMARY_SOFT, button_hover_color=T.HOVER,
            text_color=T.PRIMARY_TEXT, dropdown_fg_color=T.SURFACE, dropdown_text_color=T.TEXT,
            dropdown_hover_color=T.HOVER)
        self.add_rule.set(ADD_RULE_LABEL)
        self.add_rule.pack(fill="x", pady=(T.SPACE_2, 0))

    # ================================================================ look
    def apply_style(self) -> None:
        """Colours for the plain Tk parts. Called again whenever the theme changes."""
        self.table.apply_style()
        self._show_rows()

    # ================================================================ settings
    def _load_settings(self):
        s = self.app.settings
        self.include_sub.set(bool(s.get("include_subfolders", False)))
        set_entry_text(self.ext_entry, s.get("extensions", ""))
        by_value = {v: t for t, v in ORDER_OPTIONS}
        self.order.set(by_value.get(s.get("order", "name"), "Name"))
        # The last rules come back, so the same monthly job is one drop and one click.
        for saved in s.get("rules", []) or []:
            cls = R.RULE_TYPES.get(saved.get("kind", ""))
            if not cls:
                continue
            fields = {f.name for f in dataclasses.fields(cls)}
            try:
                rule = cls(**{k: v for k, v in saved.items() if k in fields})
            except (TypeError, ValueError):
                continue
            self._add_card(rule, refresh=False)

    def _save_settings(self):
        s = self.app.settings
        s.set("include_subfolders", self.include_sub.get())
        s.set("extensions", self.ext_entry.get())
        s.set("order", self.order_value())
        saved = []
        for rule in self.rules:
            data = dataclasses.asdict(rule)
            if isinstance(rule, R.ListRule):        # the list itself is personal data: never stored
                data.update(mapping={}, source="")
            data["kind"] = rule.KIND
            saved.append(data)
        s.set("rules", saved)

    def order_value(self) -> str:
        return dict(ORDER_OPTIONS).get(self.order.get(), "name")

    # ================================================================ states
    def show_empty(self):
        self.toolbar.pack_forget()
        self.viewbar.pack_forget()
        self.table.pack_forget()
        self.drop_zone.pack(fill="both", expand=True)
        self.refresh()

    def show_content(self):
        if self.toolbar.winfo_manager():
            return  # already showing; re-packing would reorder the widgets
        self.drop_zone.pack_forget()
        self.toolbar.pack(fill="x")
        self.viewbar.pack(fill="x", padx=T.SPACE_4, pady=(0, T.SPACE_2))
        self.table.pack(fill="both", expand=True, padx=T.SPACE_4, pady=(0, T.SPACE_4))

    def refresh(self):
        """The main button and the summary line, from the current state."""
        p = self.preview
        if self.busy:
            self.action_btn.configure(state="disabled", fg_color=T.PRIMARY_DISABLED)
            return
        ready = p is not None and p.can_apply and not self._just_renamed
        n = p.changing if p else 0
        self.action_btn.configure(
            text=f"Rename {engine.plural(n, 'file')}" if n else "Rename",
            state="normal" if ready else "disabled",
            fg_color=T.PRIMARY if ready else T.PRIMARY_DISABLED, hover_color=T.PRIMARY_HOVER)
        if not self.items:
            self.summary.configure(text="Add files or a folder, then add a rule.")
        elif self._just_renamed:
            self.summary.configure(text="Done. Change a rule or add files to rename again.")
            self.action_btn.configure(text="Renamed", state="disabled", fg_color=T.PRIMARY_DISABLED)
        elif not self.rules:
            self.summary.configure(text="Add a rule to see the new names.")
        elif p is None:
            self.summary.configure(text="Working out the new names...")
        elif p.blocked:
            self.summary.configure(text=f"Fix the {engine.plural(p.blocked, 'problem')} shown in red first.")
        elif not p.changing:
            self.summary.configure(text="No file would change with these rules.")
        else:
            self.summary.configure(text="Check the New name column, then click Rename. You can undo it.")

    def set_drop_highlight(self, on: bool):
        if self.drop_zone.winfo_ismapped():
            self.drop_zone.set_highlight(on)

    # ================================================================ adding files
    def _start_dir(self) -> str:
        last = self.app.settings.get("last_dir", "")
        return last if last and os.path.isdir(last) else os.path.expanduser("~")

    def choose_files(self):
        paths = fd.askopenfilenames(title="Add files to rename", initialdir=self._start_dir())
        if paths:
            self.load(list(paths))

    def choose_folder(self):
        path = fd.askdirectory(title="Add a folder", initialdir=self._start_dir(), mustexist=True)
        if path:
            self.load([path])

    def load(self, paths: list[str]):
        """Files or folders were dropped, chosen, or passed in by "Send to"."""
        paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
        if not paths:
            self.app.set_status("error", "Those files can't be found.")
            return
        first = paths[0]
        self.app.settings.set("last_dir", first if os.path.isdir(first) else os.path.dirname(first))
        known = {os.path.normcase(p) for p in self.added_paths}
        self.added_paths += [p for p in paths if os.path.normcase(p) not in known]
        self.files_changed()

    def clear(self):
        if self.busy:
            return
        self.added_paths, self.items, self.preview = [], [], None
        self._just_renamed = False
        self.result_panel.clear()
        self.show_empty()
        self.app.set_status("info", "List cleared. No file was changed.")

    def files_changed(self):
        """The user added files or changed which files count: Rename may be used again."""
        self._just_renamed = False
        self.result_panel.clear()
        self.recollect()

    def recollect(self):
        """List the files again (after adding paths, or changing subfolders / extensions)."""
        self._save_settings()
        if not self.added_paths:
            self.items = []
            self.show_empty()
            return
        paths, sub = list(self.added_paths), self.include_sub.get()
        exts, order = engine.parse_extensions(self.ext_entry.get()), self.order_value()
        self._gen += 1
        gen = self._gen

        def work():
            try:
                items = engine.sort_items(engine.collect(paths, sub, exts), order)
            except Exception:
                log.exception("Listing files failed")
                items = []
            self.app.call_soon(lambda: self._collected(gen, items))

        self.app.set_status("busy", "Listing files...")
        threading.Thread(target=work, daemon=True).start()

    def _collected(self, gen: int, items: list[FileItem]):
        if gen != self._gen:
            return
        self.items = items
        self.show_content()
        self.app.set_status("ready", "Ready.")
        if not items:
            self.preview = None
            self.heading.configure(text="No files")
            self.counts.configure(text="")
            self.table.show_empty("No files here match. Check “Only these extensions” or tick "
                                  "“Include subfolders”.")
            self.refresh()
            return
        self.heading.configure(text=engine.plural(len(items), "file"))
        if self._just_renamed:
            # Show the result, not the rules applied a second time to the new names.
            self.preview = None
            self.table.show_done(items, self._renamed_paths)
            self.counts.configure(text=f"{engine.plural(len(self._renamed_paths), 'file')} renamed",
                                  text_color=T.TEXT_2)
            self.refresh()
            return
        self.update_preview()

    def reorder(self):
        self._save_settings()
        self.items = engine.sort_items(self.items, self.order_value())
        self.changed()

    # ================================================================ rules
    def _add_rule_chosen(self, title: str):
        self.add_rule.set(ADD_RULE_LABEL)
        cls = next(c for c in R.RULE_TYPES.values() if c.TITLE == title)
        self._add_card(cls())
        self.changed()

    def _add_card(self, rule: R.Rule, refresh: bool = True):
        card = RuleCard(self.rules_box, rule, on_change=self.changed, on_move=self._move_card,
                        on_remove=self._remove_card, on_pick_list=self._pick_list)
        card.pack(fill="x", pady=(T.SPACE_2, 0))
        self.rules.append(rule)
        self.cards.append(card)
        if refresh:
            self.changed()

    def _move_card(self, card: RuleCard, step: int):
        i = self.cards.index(card)
        j = i + step
        if not 0 <= j < len(self.cards):
            return
        self.cards[i], self.cards[j] = self.cards[j], self.cards[i]
        self.rules[i], self.rules[j] = self.rules[j], self.rules[i]
        for c in self.cards:            # re-pack in the new order
            c.pack_forget()
        for c in self.cards:
            c.pack(fill="x", pady=(T.SPACE_2, 0))
        self.changed()

    def _remove_card(self, card: RuleCard):
        i = self.cards.index(card)
        self.cards.pop(i).destroy()
        self.rules.pop(i)
        self.changed()

    def _pick_list(self, card: RuleCard):
        path = fd.askopenfilename(title="Choose the list of names", initialdir=self._start_dir(),
                                  filetypes=[("Excel or CSV", "*.xlsx *.xlsm *.csv *.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            mapping, dupes = load_mapping(path)
        except RenameError as exc:
            self._show_error("Can't use that list", str(exc))
            return
        except Exception:
            log.exception("Loading list failed")
            self._show_error("Can't use that list", "Something unexpected went wrong. The details were saved "
                                                    "to the log file.")
            return
        card.rule.mapping, card.rule.source = mapping, path
        card.update_list_status()
        note = f" {engine.plural(dupes, 'repeated name')} ignored." if dupes else ""
        self.app.set_status("success", f"Loaded {engine.plural(len(mapping), 'name')}.{note}")
        self.changed()

    # ================================================================ preview
    def _later(self, fn, ms: int):
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(ms, fn)

    def changed(self):
        """Any rule, file or option changed: work out the new names again, shortly."""
        self._just_renamed = False
        self.result_panel.clear()
        self.after_idle(self.side_scroll.fit)
        self._save_settings()
        self.preview = None
        self.refresh()
        self._later(self.update_preview, 150)

    def update_preview(self):
        self._preview_job = None
        if not self.items:
            self.refresh()
            return
        items, rules = list(self.items), copy.deepcopy(self.rules)   # the worker gets its own copy
        self._gen += 1
        gen = self._gen

        def work():
            try:
                preview = engine.build_preview(items, rules)
            except RenameError as exc:
                message = str(exc)        # copied: Python deletes ``exc`` when this block ends
                self.app.call_soon(lambda: self._preview_failed(gen, message))
            except Exception:
                log.exception("Preview failed")
                self.app.call_soon(lambda: self._preview_failed(
                    gen, "Something unexpected went wrong. The details were saved to the log file."))
            else:
                self.app.call_soon(lambda: self._preview_done(gen, preview))

        threading.Thread(target=work, daemon=True).start()

    def _preview_failed(self, gen: int, message: str):
        if gen != self._gen:
            return
        self.preview = None
        self.table.show_empty(message)
        self.counts.configure(text="")
        self._show_error("Check the rules", message)
        self.refresh()

    def _preview_done(self, gen: int, preview: Preview):
        if gen != self._gen:
            return
        self.preview = preview
        self._show_rows()
        parts = [f"{engine.plural(preview.changing, 'file')} will change"]
        if preview.blocked:
            parts.append(engine.plural(preview.blocked, "problem"))
        if preview.unchanged:
            parts.append(f"{preview.unchanged:,} unchanged")
        self.counts.configure(text=" · ".join(parts), text_color=T.DANGER if preview.blocked else T.TEXT_2)
        self.refresh()

    def _show_rows(self):
        if self.preview is None:
            return
        view = dict(VIEW_OPTIONS).get(self.view.get(), "all")
        self.table.show(self.preview.rows, view)

    # ================================================================ rename
    def run(self):
        if self.busy or not self.preview or not self.preview.can_apply or self._just_renamed:
            return
        preview = self.preview
        self.busy = True
        self.refresh()
        self.progress.configure(mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, T.SPACE_2), before=self.action_btn)
        self.progress.start()
        self.app.set_status("busy", f"Renaming {engine.plural(preview.changing, 'file')}...")

        def work():
            try:
                result = engine.apply_preview(preview, undo_log_dir())
            except RenameError as exc:
                message = str(exc)
                self.app.call_soon(lambda: self._rename_failed(message))
            except Exception:
                log.exception("Rename failed")
                self.app.call_soon(lambda: self._rename_failed(
                    "Something unexpected went wrong. Nothing was renamed. The details were saved to the log file."))
            else:
                self.app.call_soon(lambda: self._renamed(preview, result))

        threading.Thread(target=work, daemon=True).start()

    def _finish(self):
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()

    def _rename_failed(self, message: str):
        self._finish()
        self._show_error("Nothing was renamed", message)
        self.refresh()
        self.update_preview()     # the folder may have changed: check again

    def _renamed(self, preview: Preview, result: engine.RenameResult):
        self._finish()
        self.app.settings.set("last_log", result.log_path)
        moved = {os.path.normcase(r.item.path): r.new_path for r in preview.rows if r.status == engine.OK}
        self._renamed_paths = {os.path.normcase(p) for p in moved.values()}
        self._just_renamed = True
        self._follow_moves(moved)
        self.result_panel.show(
            "success", f"{engine.plural(result.renamed, 'file')} renamed",
            "The old names are saved in an undo log.",
            [("Undo this rename", "undo", lambda: self.undo_from(result.log_path)),
             ("Show the undo log", "history", lambda: reveal_in_folder(result.log_path))])
        self.app.set_status("success", f"{engine.plural(result.renamed, 'file')} renamed.")
        self.refresh()

    def _follow_moves(self, moved: dict[str, str]):
        """Files dropped one by one are listed by path: point those paths at the new names."""
        self.added_paths = [moved.get(os.path.normcase(p), p) for p in self.added_paths]
        self.recollect()

    # ================================================================ undo
    def show_undo_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=T.pick(T.SURFACE), fg=T.pick(T.TEXT), bd=0,
                       activebackground=T.pick(T.PRIMARY_SOFT), activeforeground=T.pick(T.TEXT),
                       font=T.tk_font(12, ctk.ScalingTracker.get_widget_scaling(self)))
        last = self.app.settings.get("last_log")
        menu.add_command(label="Undo the last rename", command=lambda: self.undo_from(last),
                         state="normal" if last and os.path.exists(last) else "disabled")
        menu.add_command(label="Undo from a log file...", command=self.undo_choose)
        menu.add_separator()
        menu.add_command(label="Open the undo logs folder", command=lambda: open_path(undo_log_dir()))
        x = self.undo_btn.winfo_rootx()
        y = self.undo_btn.winfo_rooty() + self.undo_btn.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def undo_choose(self):
        path = fd.askopenfilename(title="Choose an undo log", initialdir=undo_log_dir(),
                                  filetypes=[("EZ Bulk Rename undo log", "*.csv")])
        if path:
            self.undo_from(path)

    def undo_from(self, path: Optional[str]):
        if self.busy or not path:
            return
        self.busy = True
        self.refresh()
        self.app.set_status("busy", "Putting the old names back...")

        def work():
            try:
                pairs = engine.read_log(path)
                result = engine.undo(pairs)
            except RenameError as exc:
                message = str(exc)
                self.app.call_soon(lambda: self._undo_failed(message))
            except Exception:
                log.exception("Undo failed")
                self.app.call_soon(lambda: self._undo_failed(
                    "Something unexpected went wrong. The details were saved to the log file."))
            else:
                self.app.call_soon(lambda: self._undone(path, pairs, result))

        threading.Thread(target=work, daemon=True).start()

    def _undo_failed(self, message: str):
        self.busy = False
        self._show_error("Not undone", message)
        self.refresh()

    def _undone(self, path: str, pairs: list[tuple[str, str]], result: engine.UndoResult):
        self.busy = False
        if self.app.settings.get("last_log") == path and result.restored:
            self.app.settings.set("last_log", "")
        detail = ""
        if result.skipped:
            shown = "\n".join(f"• {os.path.basename(p)} {why}" for p, why in result.skipped[:5])
            more = f"\n…and {len(result.skipped) - 5:,} more." if len(result.skipped) > 5 else ""
            detail = f"Not put back:\n{shown}{more}"
        kind = "success" if result.restored else "info"
        self.result_panel.show(kind, f"{engine.plural(result.restored, 'file')} back to the old name", detail)
        self.app.set_status(kind, f"Undone: {engine.plural(result.restored, 'file')} renamed back.")
        if self.added_paths:
            back = {os.path.normcase(new): old for old, new in pairs}
            self._just_renamed = False
            self._follow_moves(back)
        self.refresh()

    # ================================================================ errors
    def _show_error(self, title: str, message: str) -> None:
        self.result_panel.show("error", title, message)
        self.app.set_status("error", message)
