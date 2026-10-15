"""Reusable widgets: buttons, inputs, drop zone, result panel, preview table, rule cards."""

from __future__ import annotations

import logging
import os
import tkinter.ttk as ttk
from typing import Callable, Optional

import customtkinter as ctk

from . import engine
from . import rules as R
from . import theme as T
from .engine import BLOCKED, OK, SAME, PreviewRow

log = logging.getLogger("ezrename.ui")


# ======================================================================
# Buttons and inputs
# ======================================================================

def primary_button(parent, text, command, icon=None, height=44, **kw):
    return ctk.CTkButton(
        parent, text=text, command=command, height=height, corner_radius=T.RADIUS_M,
        fg_color=T.PRIMARY, hover_color=T.PRIMARY_HOVER, text_color=T.ON_PRIMARY,
        text_color_disabled=("#F5E8F0", "#AB8FA2"), font=T.font(14, True),
        image=T.icon(icon, 18, T.ON_PRIMARY) if icon else None, compound="left", **kw)


def secondary_button(parent, text, command, icon=None, height=34, danger=False, **kw):
    color = T.DANGER if danger else T.TEXT
    return ctk.CTkButton(
        parent, text=text, command=command, height=height, corner_radius=T.RADIUS_S,
        fg_color=T.SURFACE, hover_color=T.HOVER, border_width=1, border_color=T.BORDER,
        text_color=color, text_color_disabled=T.TEXT_3, font=T.font(12),
        image=T.icon(icon, 16, T.DANGER if danger else T.TEXT_2) if icon else None,
        compound="left", **kw)


def icon_button(parent, icon, command, size=18, color=T.TEXT_2, **kw):
    kw.setdefault("width", 34)
    kw.setdefault("height", 34)
    kw.setdefault("hover_color", T.HOVER)
    return ctk.CTkButton(
        parent, text="", corner_radius=T.RADIUS_S, command=command,
        fg_color="transparent", image=T.icon(icon, size, color), **kw)


def divider(parent, **pack):
    # height=2: CustomTkinter skips drawing 1px frames on some scalings
    line = ctk.CTkFrame(parent, height=2, fg_color=T.BORDER, corner_radius=0)
    line.pack(fill="x", **pack)
    return line


def section_label(parent, text, top=T.SPACE_3):
    label = ctk.CTkLabel(parent, text=text, font=T.font(12, True), text_color=T.TEXT_2, anchor="w")
    label.pack(fill="x", pady=(top, T.SPACE_1))
    return label


def text_entry(parent, placeholder: str, **kw) -> ctk.CTkEntry:
    """A text box. No textvariable on purpose: with one, CTkEntry never shows its placeholder."""
    kw.setdefault("height", 36)
    kw.setdefault("fg_color", T.SURFACE_2)
    entry = ctk.CTkEntry(parent, placeholder_text=placeholder, corner_radius=T.RADIUS_S,
                         border_width=1, border_color=T.BORDER,
                         text_color=T.TEXT, placeholder_text_color=T.TEXT_3, font=T.font(13), **kw)
    entry.bind("<FocusIn>", lambda e: entry.configure(border_color=T.PRIMARY_TEXT), add="+")
    entry.bind("<FocusOut>", lambda e: entry.configure(border_color=T.BORDER), add="+")
    return entry


def set_entry_text(entry: ctk.CTkEntry, text: str) -> None:
    entry.delete(0, "end")
    if text:
        entry.insert(0, text)


def checkbox(parent, text: str, value: bool, command=None) -> tuple[ctk.CTkCheckBox, ctk.BooleanVar]:
    var = ctk.BooleanVar(value=value)
    box = ctk.CTkCheckBox(parent, text=text, variable=var, command=command, font=T.font(13),
                          text_color=T.TEXT, fg_color=T.PRIMARY, hover_color=T.PRIMARY_HOVER,
                          border_color=T.TEXT_3, checkmark_color=T.ON_PRIMARY, border_width=2,
                          checkbox_width=18, checkbox_height=18, corner_radius=4)
    box.pack(fill="x", pady=(T.SPACE_1, T.SPACE_1))
    return box, var


# ======================================================================
# Scroll frame that hides its scrollbar when everything fits
# ======================================================================

class AutoScrollFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kw):
        kw.setdefault("scrollbar_button_color", T.BORDER)
        kw.setdefault("scrollbar_button_hover_color", T.TEXT_3)
        super().__init__(master, **kw)
        self._sb_shown = True
        self._sb_job = None
        self.bind("<Configure>", self._queue_sb_check, add="+")
        self._parent_canvas.bind("<Configure>", self._queue_sb_check, add="+")

    def fit(self) -> None:
        """Re-measure after content was removed.

        CustomTkinter only grows the scroll region; when content shrinks (a rule card
        removed) the old, taller region stays and the view can sit on blank space.
        """
        self.update_idletasks()
        canvas = self._parent_canvas
        height = max(self.winfo_reqheight(), canvas.winfo_height())
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), height))
        canvas.yview_moveto(canvas.yview()[0])     # clamps the position to the new region
        self._queue_sb_check()

    def _queue_sb_check(self, _event=None):
        if self._sb_job is None:
            self._sb_job = self.after(50, self._sb_check)

    def _sb_check(self):
        self._sb_job = None
        need = self.winfo_reqheight() > self._parent_canvas.winfo_height() + 1
        if need and not self._sb_shown:
            self._scrollbar.grid()
        elif not need and self._sb_shown:
            self._scrollbar.grid_remove()
            self._parent_canvas.yview_moveto(0)
        self._sb_shown = need


# ======================================================================
# Drop zone (empty state)
# ======================================================================

class DropZone(ctk.CTkFrame):
    """Empty state: the one place the glossy orb appears."""

    def __init__(self, master, on_browse: Callable[[], None]):
        super().__init__(master, fg_color=T.BG, corner_radius=0)
        self.panel = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=T.RADIUS_L,
                                  border_width=2, border_color=T.BORDER)
        self.panel.pack(expand=True, fill="both", padx=T.SPACE_4 * 2, pady=T.SPACE_4 * 2)
        inner = ctk.CTkFrame(self.panel, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text="", image=T.asset_image("drop_orb.png", 112)).pack(pady=(0, T.SPACE_3))
        self.title = ctk.CTkLabel(inner, text="", font=T.font(22, True), text_color=T.TEXT)
        self.title.pack()
        self.subtitle = ctk.CTkLabel(inner, text="", font=T.font(13), text_color=T.TEXT_2,
                                     wraplength=440, justify="center")
        self.subtitle.pack(pady=T.SPACE_2)
        self.button = primary_button(inner, "", on_browse, width=220)
        self.button.pack()
        hint = ctk.CTkFrame(inner, fg_color="transparent")
        hint.pack(pady=(T.SPACE_4, 0))
        ctk.CTkLabel(hint, text="", image=T.icon("shield", 14, T.TEXT_3)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(hint, text="Files are renamed on this computer. Nothing is uploaded.",
                     font=T.font(11), text_color=T.TEXT_3).pack(side="left")
        self.title.configure(text="Drop files or folders here")
        self.subtitle.configure(text="Scans, photos, invoices, reports — any files. Nothing changes until "
                                     "you check the preview and click Rename.")
        self.button.configure(text="Add files")

    def set_highlight(self, on: bool) -> None:
        self.panel.configure(border_color=T.PRIMARY_TEXT if on else T.BORDER,
                             fg_color=T.PRIMARY_SOFT if on else T.SURFACE)


# ======================================================================
# Result panel (sidebar)
# ======================================================================

class ResultPanel(ctk.CTkFrame):
    """Shows the outcome of the last search. Only the latest result is kept."""

    STYLES = {
        "success": (T.SUCCESS_SOFT, T.SUCCESS, "success"),
        "error": (T.DANGER_SOFT, T.DANGER, "error"),
        "info": (T.PRIMARY_SOFT, T.PRIMARY_TEXT, "info"),
    }

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", height=1)

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def show(self, kind: str, title: str, detail: str = "",
             actions: Optional[list[tuple[str, str, Callable]]] = None):
        self.clear()
        bg, fg, ico = self.STYLES[kind]
        box = ctk.CTkFrame(self, fg_color=bg, corner_radius=T.RADIUS_M)
        box.pack(fill="x")
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=T.SPACE_3, pady=(T.SPACE_3, 0))
        ctk.CTkLabel(head, text="", image=T.icon(ico, 18, fg)).pack(side="left", padx=(0, T.SPACE_2))
        ctk.CTkLabel(head, text=title, font=T.font(13, True), text_color=fg,
                     wraplength=T.CONTENT_W - 70, justify="left", anchor="w").pack(side="left", fill="x")
        if detail:
            ctk.CTkLabel(box, text=detail, font=T.font(12), text_color=T.TEXT_2, justify="left",
                         anchor="w", wraplength=T.CONTENT_W - 2 * T.SPACE_3 - 6).pack(fill="x", padx=T.SPACE_3, pady=(T.SPACE_1, 0))
        if actions:
            for n, (label, ic, cmd) in enumerate(actions):
                secondary_button(box, label, cmd, icon=ic, height=32, anchor="w").pack(
                    fill="x", padx=T.SPACE_3, pady=(T.SPACE_3 if n == 0 else T.SPACE_1, 0))
        ctk.CTkFrame(box, height=T.SPACE_3, fg_color="transparent").pack()
        canvas = getattr(self.master, "_parent_canvas", None)
        if canvas is not None:  # make sure the new result is visible on short screens
            self.after(120, lambda: canvas.yview_moveto(1.0))




# ======================================================================
# Preview table: current name -> new name, before anything changes
# ======================================================================

class PreviewTable(ctk.CTkFrame):
    """One row per file: number, current name, new name, what will happen, folder.

    A ttk.Treeview rather than one widget per row: it stays fast with thousands
    of files. It is not drawn by CustomTkinter, so its colours and fonts are
    applied here and again whenever the theme or scaling changes.
    """

    # key, heading, width (px at 100%), anchor, stretches
    COLUMNS = (
        ("num", "#", 50, "e", False),
        ("old", "Current name", 230, "w", True),
        ("new", "New name", 230, "w", True),
        ("status", "Status", 220, "w", True),
        ("folder", "Folder", 120, "w", True),
    )
    STYLE = "EZRename.Treeview"

    def __init__(self, master, on_select: Optional[Callable[[Optional[PreviewRow]], None]] = None):
        super().__init__(master, fg_color=T.SURFACE, bg_color=T.BG, corner_radius=T.RADIUS_M,
                         border_width=1, border_color=T.BORDER)
        self._rows: dict[str, PreviewRow] = {}
        self.tree = ttk.Treeview(self, columns=[c[0] for c in self.COLUMNS], show="headings",
                                 style=self.STYLE, selectmode="browse")
        for key, title, _width, anchor, stretch in self.COLUMNS:
            self.tree.heading(key, text=title, anchor=anchor)
            self.tree.column(key, anchor=anchor, stretch=stretch)
        scroll = ctk.CTkScrollbar(self, command=self.tree.yview, button_color=T.BORDER,
                                  button_hover_color=T.TEXT_3, fg_color="transparent")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=6)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.empty = ctk.CTkLabel(self, text="", font=T.font(13), text_color=T.TEXT_2,
                                  justify="center", wraplength=420)
        self.tree.bind("<Configure>", lambda e: self._fit_columns(e.width), add="+")
        if on_select is not None:
            self.tree.bind("<<TreeviewSelect>>", lambda e: on_select(self.selected()))
        self.apply_style()
        ctk.ScalingTracker.add_widget(lambda *_: self.apply_style(), self)

    def selected(self) -> Optional[PreviewRow]:
        sel = self.tree.selection()
        return self._rows.get(sel[0]) if sel else None

    def apply_style(self) -> None:
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        style = ttk.Style(self)
        if style.theme_use() != "clam":
            style.theme_use("clam")  # the only built-in theme that honours custom colours everywhere
        surface = T.pick(T.SURFACE)
        style.layout(self.STYLE, [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure(self.STYLE, background=surface, fieldbackground=surface,
                        foreground=T.pick(T.TEXT), font=T.tk_font(13, scale),
                        rowheight=round(28 * scale), borderwidth=0, relief="flat")
        style.map(self.STYLE, background=[("selected", T.pick(T.HOVER))],
                  foreground=[("selected", T.pick(T.TEXT))])
        head = T.pick(T.TABLE_HEAD)
        style.configure(f"{self.STYLE}.Heading", background=head, foreground=T.pick(T.TABLE_HEAD_TEXT),
                        font=T.tk_font(12, scale, semibold=True), relief="flat", borderwidth=0,
                        bordercolor=head, lightcolor=head, darkcolor=head,
                        padding=(round(8 * scale), round(6 * scale)))
        style.map(f"{self.STYLE}.Heading", background=[("active", head)])
        self.tree.tag_configure(OK, background=T.pick(T.CHANGE_ROW), foreground=T.pick(T.TEXT))
        self.tree.tag_configure(SAME, foreground=T.pick(T.UNCHANGED_TEXT))
        self.tree.tag_configure(BLOCKED, background=T.pick(T.BLOCKED_ROW), foreground=T.pick(T.TEXT))
        self._fit_columns(self.tree.winfo_width())

    def _fit_columns(self, available: int) -> None:
        """Fixed columns keep their width; the others share what is left (Tk never shrinks them)."""
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        fixed = {k: round(w * scale) for k, _t, w, _a, stretch in self.COLUMNS if not stretch}
        flexible = {k: w for k, _t, w, _a, stretch in self.COLUMNS if stretch}
        spare = max(available - sum(fixed.values()), 0)
        total = sum(flexible.values())
        for key, width in fixed.items():
            self.tree.column(key, width=width, minwidth=width, stretch=False)
        for key, width in flexible.items():
            share = spare * width // total if available > 1 else round(width * scale)
            self.tree.column(key, width=max(share, round(80 * scale)), minwidth=round(60 * scale), stretch=True)

    @staticmethod
    def _status(row: PreviewRow) -> str:
        if row.status == BLOCKED:
            return row.problem
        return "Ready to rename" if row.status == OK else "Unchanged"

    def show(self, rows: list[PreviewRow], view: str = "all") -> None:
        """Fill the table. ``view``: all | changes | issues."""
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        self.empty.place_forget()
        shown = 0
        for n, row in enumerate(rows, start=1):
            if view == "changes" and row.status != OK:
                continue
            if view == "issues" and row.status != BLOCKED:
                continue
            folder = engine_short(row.item.folder)
            iid = self.tree.insert("", "end", values=(n, row.item.name, row.new_name if row.status != SAME else "—",
                                                      self._status(row), folder), tags=(row.status,))
            self._rows[iid] = row
            shown += 1
        if not shown and rows:
            self.show_empty("No issues found. Every file is ready to rename." if view == "issues"
                            else "No changes yet. Add a rule on the right to build the new names.")

    def show_done(self, items, renamed: set[str]) -> None:
        """After a rename: every file under its name now, the renamed ones marked."""
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        self.empty.place_forget()
        for n, item in enumerate(items, start=1):
            done = os.path.normcase(item.path) in renamed
            self.tree.insert("", "end", values=(n, item.name, "—", "Renamed" if done else "Unchanged",
                                                engine_short(item.folder)), tags=(OK if done else SAME,))

    def show_empty(self, message: str) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        self.empty.configure(text=message)
        self.empty.place(relx=0.5, rely=0.45, anchor="center")


def engine_short(path: str, limit: int = 40) -> str:
    """Last folders of a path, for a narrow column."""
    if len(path) <= limit:
        return path
    return "…" + path[-(limit - 1):]


# ======================================================================
# Rule cards: one editable card per rule in the sidebar
# ======================================================================

class RuleCard(ctk.CTkFrame):
    """Edits one rule in place. Every change calls ``on_change`` so the preview follows.

    Header: on/off tick box with the rule's name, move up, move down, remove.
    Body: the rule's own settings.
    """

    def __init__(self, master, rule: R.Rule, on_change: Callable[[], None],
                 on_move: Callable[["RuleCard", int], None], on_remove: Callable[["RuleCard"], None],
                 on_pick_list: Optional[Callable[["RuleCard"], None]] = None):
        super().__init__(master, fg_color=T.SURFACE_2, corner_radius=T.RADIUS_M, border_width=1,
                         border_color=T.BORDER)
        self.rule = rule
        self._notify = on_change
        self._pick_list = on_pick_list

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=T.SPACE_2, pady=(T.SPACE_2, 0))
        icon_button(head, "close", lambda: on_remove(self), size=14, width=26, height=26).pack(side="right")
        icon_button(head, "down", lambda: on_move(self, 1), size=14, width=26, height=26).pack(side="right")
        icon_button(head, "up", lambda: on_move(self, -1), size=14, width=26, height=26).pack(side="right")
        self.enabled = ctk.BooleanVar(value=rule.enabled)
        ctk.CTkCheckBox(head, text=rule.TITLE, variable=self.enabled, command=self._toggle,
                        font=T.font(12, True), text_color=T.TEXT, fg_color=T.PRIMARY,
                        hover_color=T.PRIMARY_HOVER, border_color=T.TEXT_3, checkmark_color=T.ON_PRIMARY,
                        border_width=2, checkbox_width=16, checkbox_height=16, corner_radius=4).pack(side="left")

        self.body = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self.body.pack(fill="x", padx=T.SPACE_3, pady=(T.SPACE_1, T.SPACE_3))
        builder = getattr(self, f"_build_{rule.KIND}", None)
        if builder:
            builder()

    # -------------------------------------------------------------- field helpers
    def _toggle(self) -> None:
        self.rule.enabled = self.enabled.get()
        self._notify()

    def _label(self, text: str, parent=None) -> None:
        ctk.CTkLabel(parent or self.body, text=text, font=T.font(12), text_color=T.TEXT_2,
                     anchor="w").pack(fill="x", pady=(T.SPACE_1, 0))

    def _text(self, label: str, attr: str, placeholder: str = "", parent=None) -> ctk.CTkEntry:
        if label:
            self._label(label, parent)
        entry = text_entry(parent or self.body, placeholder, height=30, fg_color=T.SURFACE)
        set_entry_text(entry, getattr(self.rule, attr))
        entry.pack(fill="x")

        def changed(_e=None):
            if getattr(self.rule, attr) != entry.get():
                setattr(self.rule, attr, entry.get())
                self._notify()
        entry.bind("<KeyRelease>", changed, add="+")
        return entry

    def _number(self, parent, label: str, attr: str) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(side="left", fill="x", expand=True, padx=(0, T.SPACE_1))
        ctk.CTkLabel(box, text=label, font=T.font(12), text_color=T.TEXT_2, anchor="w").pack(fill="x")
        entry = text_entry(box, "", height=30, width=60, fg_color=T.SURFACE)
        set_entry_text(entry, str(getattr(self.rule, attr)))
        entry.pack(fill="x")

        def changed(_e=None):
            try:
                value = int(entry.get().strip())
            except ValueError:
                entry.configure(border_color=T.DANGER)
                return
            entry.configure(border_color=T.PRIMARY_TEXT)
            if getattr(self.rule, attr) != value:
                setattr(self.rule, attr, value)
                self._notify()
        entry.bind("<KeyRelease>", changed, add="+")

    def _choice(self, label: str, attr: str, options: list[tuple[str, str]]) -> None:
        """A drop-down. ``options`` are (shown text, stored value)."""
        if label:
            self._label(label)
        by_text = dict(options)
        by_value = {v: t for t, v in options}
        var = ctk.StringVar(value=by_value.get(getattr(self.rule, attr), options[0][0]))

        def chosen(text: str) -> None:
            setattr(self.rule, attr, by_text[text])
            self._notify()
        ctk.CTkOptionMenu(self.body, values=[t for t, _v in options], variable=var, command=chosen,
                          height=30, corner_radius=T.RADIUS_S, font=T.font(12), dropdown_font=T.font(12),
                          fg_color=T.SURFACE, button_color=T.SURFACE, button_hover_color=T.HOVER,
                          text_color=T.TEXT, dropdown_fg_color=T.SURFACE, dropdown_text_color=T.TEXT,
                          dropdown_hover_color=T.HOVER).pack(fill="x")

    def _tick(self, label: str, attr: str) -> None:
        var = ctk.BooleanVar(value=getattr(self.rule, attr))

        def changed() -> None:
            setattr(self.rule, attr, var.get())
            self._notify()
        ctk.CTkCheckBox(self.body, text=label, variable=var, command=changed, font=T.font(12),
                        text_color=T.TEXT, fg_color=T.PRIMARY, hover_color=T.PRIMARY_HOVER,
                        border_color=T.TEXT_3, checkmark_color=T.ON_PRIMARY, border_width=2,
                        checkbox_width=16, checkbox_height=16, corner_radius=4).pack(fill="x", pady=(T.SPACE_1, 0))

    # -------------------------------------------------------------- one builder per rule
    def _build_replace(self) -> None:
        self._text("Find", "find", "text to find")
        self._text("Replace with", "replace", "leave empty to remove it")
        self._tick("Match case", "match_case")
        self._tick("Regular expression", "regex")

    def _build_add(self) -> None:
        self._text("Before the name", "prefix", "e.g. 2026_")
        self._text("After the name", "suffix", "e.g. _signed")

    def _build_number(self) -> None:
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x")
        self._number(row, "Start", "start")
        self._number(row, "Step", "step")
        self._number(row, "Digits", "digits")
        self._choice("Where", "position", [("Before the name", "before"), ("After the name", "after"),
                                           ("Replace the name", "replace")])
        self._text("Separator", "separator", "e.g. _ or -")

    def _build_date(self) -> None:
        self._choice("Date", "source", [("Date modified", "modified"), ("Date created", "created")])
        self._choice("Format", "format", [(k, k) for k in R.DATE_FORMATS])
        self._choice("Where", "position", [("Before the name", "before"), ("After the name", "after")])
        self._text("Separator", "separator", "e.g. _ or -")

    def _build_case(self) -> None:
        self._choice("", "mode", [("lower case", "lower"), ("UPPER CASE", "upper"),
                                  ("Title Case", "title"), ("Sentence case", "sentence")])

    def _build_remove(self) -> None:
        self._choice("Spaces", "spaces", [("Keep spaces", "keep"), ("Spaces to _", "underscore"),
                                          ("Spaces to -", "dash"), ("Remove spaces", "remove")])
        self._text("Remove these characters", "characters", "e.g. #()[]")
        self._tick("Trim spaces, dots, _ and - at the ends", "trim")
        self._tick("Collapse repeats (a__b to a_b)", "collapse")

    def _build_extension(self) -> None:
        self._text("New extension", "new_extension", "e.g. jpg (empty keeps it)")
        self._choice("Case", "case", [("Keep as it is", "keep"), ("lower case", "lower"), ("UPPER CASE", "upper")])

    def _build_list(self) -> None:
        self.list_status = ctk.CTkLabel(self.body, text="", font=T.font(12), text_color=T.TEXT_2,
                                        anchor="w", justify="left", wraplength=T.CONTENT_W - 40)
        self.list_status.pack(fill="x")
        secondary_button(self.body, "Load Excel or CSV...", lambda: self._pick_list and self._pick_list(self),
                         icon="list", height=30).pack(fill="x", pady=(T.SPACE_1, 0))
        self.update_list_status()

    def update_list_status(self) -> None:
        rule = self.rule
        if isinstance(rule, R.ListRule) and rule.mapping:
            name = rule.source.replace("\\", "/").rsplit("/", 1)[-1]
            self.list_status.configure(text=f"{engine.plural(len(rule.mapping), 'name')} from {name}.\n"
                                            "Column 1: current name. Column 2: new name.")
        else:
            self.list_status.configure(text="Column 1: current name (with or without extension).\n"
                                            "Column 2: new name.")
