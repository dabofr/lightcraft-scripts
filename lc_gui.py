# -*- coding: utf-8 -*-
"""Window to launch the LightCraft scripts.
   double-click Launch-GUI.bat (no console), or  uv run lc_gui.py

It only launches the lc_*.py scripts of this folder with the chosen settings and shows what they
print. The scripts stay usable on their own, with the values written at their top. If LightCraft
is running with its control port, the scripts go through it; otherwise they open the library."""
import ast
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import lc_common as C  # noqa: E402
    from lc_common import _  # noqa: E402
except SystemExit as e:      # invalid config.txt, or Python too old
    tk.Tk().withdraw()
    messagebox.showerror("LightCraft scripts", str(e))
    raise

# -------------------------------------------------------------------------------- the scripts
# folder: None (whole library), "one" (a single folder: the script writes one set of CSV files),
#         "several" (one run per folder, one after the other), "list" (the script takes them all)
# settings: (NAME, "bool", label) or (NAME, "choice", label, [(value, explanation), ...])
SCRIPTS = [
    (_("Checks (read only)"), [
        dict(file="lc_inventory.py", title=_("Inventory"), read_only=True, folder="one",
             summary=_("Counts photos, raws and RAW + JPG pairs, and lists the photos without a sidecar "
                       "on disk.\nWrites inventory.csv and no_sidecar.txt."),
             settings=[]),
        dict(file="lc_audit.py", title=_("RAW / JPG and places audit"), read_only=True, folder="one",
             summary=_("Compares each raw with its JPG (keywords, place, rating, flag) and finds photos "
                       "with a place keyword but neither city nor country.\nWrites audit_pairs.csv and "
                       "audit_places.csv. With places: slow on a whole library (a detailed read per photo)."),
             settings=[("PLACES", "bool", _("Also audit places (slower)"))]),
    ]),
    (_("Paths and sidecars"), [
        dict(file="lc_relink.py", title=_("Relink paths"), folder="several",
             summary=_("Rewrites photo paths with backslashes, so that RAW and JPG are recognised as a "
                       "pair and do not write the same sidecar.\nTouches no file. Run after each import, "
                       "before writing sidecars."),
             settings=[("TARGET", "choice", _("Photos targeted"),
                        [("twins", _("only the JPG of pairs")),
                         ("all", _("every photo (advised after an import)"))])]),
        dict(file="lc_sidecars.py", title=_("Write sidecars"), folder="several",
             summary=_("Writes the .xmp files from the catalogue (one way). LightCraft merges into the "
                       "existing sidecar.\nSeldom needed when automatic writing is on. Relink first."),
             settings=[("TARGET", "choice", _("Photos targeted"),
                        [("raw", _("raws only")),
                         ("all_but_twins", _("everything except the JPG twins of a raw")),
                         ("twins", _("only the JPG twins (creates IMG.JPG.xmp)")),
                         ("all", _("every photo (safe once relinked)"))])]),
        dict(file="lc_reload.py", title=_("Reload from disk"), folder="several",
             summary=_("Reads the EXIF again to fill empty camera and lens fields. Keeps keywords and "
                       "edits.\nMay bring unnamed faces back: the script counts them before and after."),
             settings=[("TARGET", "choice", _("Photos targeted"),
                        [("all", _("every photo")), ("raw", _("raws only"))])]),
    ]),
    (_("Stacks and faces"), [
        dict(file="lc_stacks.py", title=_("Stack RAW + JPG pairs"), folder="several",
             summary=_("Puts each raw and its JPG in a collapsed stack, raw on top. Tests one pair "
                       "first and checks every stack."),
             settings=[]),
        dict(file="lc_collapse_stacks.py", title=_("Collapse all stacks"), folder=None,
             summary=_("Collapses every expanded stack of the library (View > Stacks). Changes neither "
                       "their content nor their order."),
             settings=[]),
        dict(file="lc_unnamed_faces.py", title=_("Remove unnamed faces"), folder=None,
             summary=_("Removes the faces found by automatic detection that nobody named, in the whole "
                       "library. Named faces are never touched.\nTurn face recognition off in "
                       "LightCraft first, otherwise they come back."),
             settings=[("ONLY_DETECTED", "bool", _("Only « Detected by » regions (keep checked)"))]),
    ]),
    (_("Metadata"), [
        dict(file="lc_mirror.py", title=_("Mirror RAW ↔ JPG"), folder="one",
             summary=_("Gives a raw and its JPG the same keywords (the more precise one wins), text, "
                       "place and GPS fields, rating, flag and colour label: a value filled on one side "
                       "only is copied to the other. Contradictions are left untouched.\nDry run: read "
                       "mirror_plan.csv and mirror_conflicts.csv before applying."),
             settings=[("KEYWORDS", "bool", _("Keywords")),
                       ("FIELDS", "bool", _("Text, place and GPS fields (slower)")),
                       ("RATING_FLAG_LABEL", "bool", _("Rating, flag and colour label"))]),
        dict(file="lc_harmonize.py", title=_("Mirror, then places (one write)"), folder="one",
             summary=_("Runs the mirror, then the place fields, and writes the sidecars of all changed "
                       "photos once at the end: faster than running both separately.\nDry run: read the "
                       "CSV files of both."),
             settings=[]),
        dict(file="lc_places.py", title=_("Place fields"), folder="one",
             summary=_("Fills location, city, state and country from the keywords and the places table. "
                       "Never replaces a value typed by hand, never empties a field.\nRun after the "
                       "mirror. Dry run: read places_plan.csv and places_to_check.csv."),
             settings=[], open=[os.path.basename(C.PLACES_TABLE)]),
    ]),
    (_("Sequence"), [
        dict(file="lc_after_import.py", title=_("After an import"), folder="list",
             summary=_("In order, on the chosen folders: relink, reload, unnamed faces, stacks, "
                       "sidecars.\nDoes not mirror keywords nor fill places: run those afterwards."),
             settings=[("RELOAD", "bool", _("Reload from disk")),
                       ("PURGE_FACES", "bool", _("Remove detected unnamed faces")),
                       ("RELINK_TARGET", "choice", _("Relink"),
                        [("all", _("every photo (advised)")), ("twins", _("only the JPG of pairs"))]),
                       ("SIDECARS_TARGET", "choice", _("Sidecars"),
                        [("all", _("every photo (safe once relinked)")),
                         ("all_but_twins", _("everything except the JPG twins")), ("raw", _("raws only"))])]),
    ]),
]
PRODUCTS = (".csv", ".txt", ".jsonl")
STATE_FILE = os.path.join(HERE, "gui_state.json")
CURRENT = {"root": C.ROOT}       # photos root of the library chosen in the window
FONT = ("Consolas", 10) if os.name == "nt" else ("Courier", 10)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# started without a console (pythonw), the GUI runs the scripts with python.exe, hidden as well
PYTHON = sys.executable
if os.path.basename(PYTHON).lower() == "pythonw.exe":
    _console = os.path.join(os.path.dirname(PYTHON), "python.exe")
    if os.path.exists(_console):
        PYTHON = _console
# -------------------------------------------------------------------------------------------


def read_defaults(file):
    """Values written at the top of the script (module constants)."""
    try:
        with open(os.path.join(HERE, file), encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError):
        return {}
    result = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            try:
                result[n.targets[0].id] = ast.literal_eval(n.value)
            except ValueError:
                pass
    return result


def load_state():
    import json
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    import json
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def looks_like_library(path):
    return any(os.path.exists(os.path.join(path, n)) for n in ("catalog.snap", "catalog.log"))


def under_root(folder):
    r = os.path.normcase(os.path.normpath(CURRENT["root"]))
    d = os.path.normcase(os.path.normpath(folder))
    return d == r or d.startswith(r + os.sep)


def default_folder(value):
    """A script's default folder if it lies under the photos root, else the root itself."""
    root = CURRENT["root"]
    return value if value and root and under_root(value) else root


def lightcraft_processes():
    """Names of running LightCraft app processes, on Windows. lightcraft-cli is left out: it is
    usually an MCP server in connect mode, which locks nothing."""
    if os.name != "nt":
        return []
    try:
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                           errors="replace", creationflags=NO_WINDOW)
    except OSError:
        return []
    names = {l.split('","')[0].strip('"') for l in r.stdout.splitlines() if l.strip()}
    return sorted(n for n in names if "lightcraft" in n.lower() and "cli" not in n.lower())


def open_text(path):
    """Text files (config.txt) open in Notepad on Windows, whatever the file associations."""
    if os.name == "nt":
        try:
            subprocess.Popen(["notepad", path])
            return
        except OSError:
            pass
    open_path(path)


def open_path(path):
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        try:
            subprocess.Popen(["notepad", path])
        except OSError:
            messagebox.showerror(_("Cannot open"), path)


class Form(ttk.Frame):
    """Settings of one script: folder(s), choices, check boxes."""

    def __init__(self, parent, s):
        super().__init__(parent)
        self.s = s
        self.defaults = read_defaults(s["file"])
        self.vars = {}
        row = 0
        if s["folder"] == "one":
            ttk.Label(self, text=_("Folder (subfolders included):")).grid(row=row, column=0, sticky="w")
            self.v_folder = tk.StringVar(value=default_folder(self.defaults.get("FOLDER")))
            ttk.Entry(self, textvariable=self.v_folder, width=70).grid(row=row, column=1, sticky="we", padx=4)
            ttk.Button(self, text=_("Browse…"), command=self.choose_one).grid(row=row, column=2)
            row += 1
        elif s["folder"] in ("several", "list"):
            ttk.Label(self, text=_("Folders (subfolders included):")).grid(row=row, column=0, sticky="nw")
            self.list = tk.Listbox(self, height=4, width=70, selectmode="extended", exportselection=False)
            self.list.grid(row=row, column=1, sticky="we", padx=4)
            start = self.defaults.get("FOLDERS") or [self.defaults.get("FOLDER")]
            for d in dict.fromkeys(default_folder(x) for x in start):
                if d:
                    self.list.insert("end", d)
            buttons = ttk.Frame(self)
            buttons.grid(row=row, column=2, sticky="n")
            ttk.Button(buttons, text=_("Add…"), command=self.add).pack(fill="x")
            ttk.Button(buttons, text=_("Remove"), command=self.remove).pack(fill="x", pady=2)
            ttk.Button(buttons, text=_("Clear all"), command=lambda: self.list.delete(0, "end")).pack(fill="x")
            row += 1
            if s["folder"] == "several":
                ttk.Label(self, text=_("The script runs once per folder, one after the other."),
                          foreground="gray").grid(row=row, column=1, sticky="w", padx=4)
                row += 1
        else:
            ttk.Label(self, text=_("Works on the whole library: no folder to choose."),
                      foreground="gray").grid(row=row, column=0, columnspan=3, sticky="w")
            row += 1

        for r in s["settings"]:
            name, kind, label = r[0], r[1], r[2]
            if kind == "bool":
                v = tk.BooleanVar(value=bool(self.defaults.get(name, True)))
                ttk.Checkbutton(self, text=label, variable=v).grid(row=row, column=1, sticky="w", padx=4, pady=2)
                self.vars[name] = ("bool", v, None)
            else:
                choices = r[3]
                default = self.defaults.get(name, choices[0][0])
                pos = next((i for i, c in enumerate(choices) if c[0] == default), 0)
                ttk.Label(self, text=label + " :").grid(row=row, column=0, sticky="w")
                cb = ttk.Combobox(self, values=["%s — %s" % c for c in choices], state="readonly", width=60)
                cb.current(pos)
                cb.grid(row=row, column=1, sticky="w", padx=4, pady=2)
                self.vars[name] = ("choice", cb, choices)
            row += 1

        if s.get("open"):
            f = ttk.Frame(self)
            f.grid(row=row, column=1, sticky="w", padx=4, pady=4)
            for name in s["open"]:
                ttk.Button(f, text=_("Open {file}", file=name),
                           command=lambda n=name: open_path(os.path.join(HERE, n))).pack(side="left")
        self.columnconfigure(1, weight=1)

    def ask_folder(self, start):
        d = filedialog.askdirectory(initialdir=start if os.path.isdir(start) else CURRENT["root"],
                                    mustexist=True, title=_("Choose a photo folder"))
        if not d:
            return None
        d = os.path.normpath(d)          # backslashes: the spelling LightCraft expects
        if not under_root(d):
            messagebox.showerror(_("Folder refused"), _("The folder must be under {root}.", root=CURRENT["root"]))
            return None
        return d

    def choose_one(self):
        d = self.ask_folder(self.v_folder.get())
        if d:
            self.v_folder.set(d)

    def add(self):
        existing = self.list.get(0, "end")
        d = self.ask_folder(existing[-1] if existing else CURRENT["root"])
        if d and d not in existing:
            self.list.insert("end", d)

    def remove(self):
        for i in reversed(self.list.curselection()):
            self.list.delete(i)

    def runs(self):
        """[(label, [arguments])], or raises ValueError with a message."""
        args = []
        for name, (kind, w, choices) in self.vars.items():
            if kind == "bool":
                args.append("--%s=%d" % (name, 1 if w.get() else 0))
            else:
                args.append("--%s=%s" % (name, choices[w.current()][0]))
        kind = self.s["folder"]
        if kind is None:
            return [("", args)]
        folders = [self.v_folder.get().strip()] if kind == "one" else list(self.list.get(0, "end"))
        if not folders or not all(folders):
            raise ValueError(_("No folder chosen."))
        for d in folders:
            if not under_root(d):
                raise ValueError(_("Folder outside {root}:\n{folder}", root=CURRENT["root"], folder=d))
            if not os.path.isdir(d):
                raise ValueError(_("Folder not found (drive disconnected?):\n{folder}", folder=d))
        if kind == "list":
            return [("", ["--FOLDERS=%s" % d for d in folders] + args)]
        if kind == "one":
            return [("", ["--FOLDER=%s" % folders[0]] + args)]
        return [(d, ["--FOLDER=%s" % d] + args) for d in folders]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(_("LightCraft scripts"))
        self.geometry("1180x780")
        self.minsize(900, 600)
        self.proc = None
        self.queue_runs = []
        self.stream = queue.Queue()
        self.dry_ok = set()
        self.signature = None
        self.applying = False
        self.start = 0.0

        self.state_data = load_state()
        self.build_library_bar()
        top = ttk.Frame(self, padding=6)
        top.pack(fill="both", expand=False)
        self.tree = ttk.Treeview(top, show="tree", height=17, selectmode="browse")
        self.tree.column("#0", width=290)
        self.tree.pack(side="left", fill="y")
        self.forms, self.specs = {}, {}
        right = ttk.Frame(top, padding=(10, 0))
        right.pack(side="left", fill="both", expand=True)
        for group, items in SCRIPTS:
            g = self.tree.insert("", "end", text=group, open=True)
            for s in items:
                if os.path.exists(os.path.join(HERE, s["file"])):
                    self.tree.insert(g, "end", text=s["title"], iid=s["file"])
                    self.specs[s["file"]] = s
        self.tree.bind("<<TreeviewSelect>>", self.select)

        self.v_title = tk.StringVar()
        ttk.Label(right, textvariable=self.v_title, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self.v_summary = tk.StringVar()
        ttk.Label(right, textvariable=self.v_summary, wraplength=820, justify="left").pack(anchor="w", pady=(2, 8))
        self.form_frame = ttk.Frame(right)
        self.form_frame.pack(fill="x")
        buttons = ttk.Frame(right, padding=(0, 10, 0, 0))
        buttons.pack(fill="x")
        self.b_dry = ttk.Button(buttons, text=_("Dry run"), command=lambda: self.launch(False))
        self.b_dry.pack(side="left")
        self.b_apply = ttk.Button(buttons, text=_("Apply"), command=lambda: self.launch(True))
        self.b_apply.pack(side="left", padx=6)
        self.b_stop = ttk.Button(buttons, text=_("Stop"), command=self.stop, state="disabled")
        self.b_stop.pack(side="left")
        ttk.Button(buttons, text=_("Help"), command=self.help).pack(side="right")
        ttk.Button(buttons, text=_("Settings"), command=lambda: open_text(C.CONFIG_FILE)).pack(side="right", padx=6)
        ttk.Button(buttons, text=_("Output folder"), command=self.open_output).pack(side="right")
        self.v_state = tk.StringVar(value=_("Ready."))
        ttk.Label(buttons, textvariable=self.v_state, foreground="gray").pack(side="left", padx=12)

        bottom = ttk.Frame(self, padding=(6, 0, 6, 6))
        bottom.pack(fill="both", expand=True)
        self.out = ScrolledText(bottom, font=FONT, wrap="word", height=18)
        self.out.pack(fill="both", expand=True)
        self.out.tag_config("title", foreground="#1f4e9e", font=FONT + ("bold",))
        self.out.tag_config("stop", foreground="#b00020", font=FONT + ("bold",))
        self.out.tag_config("done", foreground="#1b7a2f", font=FONT + ("bold",))
        self.out.configure(state="disabled")
        foot = ttk.Frame(bottom)
        foot.pack(fill="x", pady=(4, 0))
        ttk.Label(foot, text=_("Files written (double-click to open):")).pack(side="left", anchor="n")
        self.products = tk.Listbox(foot, height=3)
        self.products.pack(side="left", fill="x", expand=True, padx=6)
        self.products.bind("<Double-Button-1>", self.open_product)
        ttk.Button(foot, text=_("Clear the display"), command=self.clear).pack(side="right", anchor="n")

        self.protocol("WM_DELETE_WINDOW", self.close)
        first = next(iter(self.specs), None)
        if first:
            self.tree.selection_set(first)
        self.after(100, self.poll)
        self.after(500, self.interrupted_run)
        if C.CONFIG_CREATED or not os.path.isfile(C.CLI):
            self.after(300, self.first_run)

    def interrupted_run(self):
        if os.path.isdir(C.STATE_DIR) and any(n.startswith("sidecars-") for n in os.listdir(C.STATE_DIR)):
            messagebox.showwarning(
                _("Sidecars to finish"),
                _("A previous run was interrupted while sidecar writing was paused: some sidecars are "
                  "not written yet, and automatic writing may still be off in LightCraft.\n\nRun any "
                  "script (the Inventory, for instance): it finishes the job before anything else."))

    def first_run(self):
        messagebox.showinfo(_("Settings needed"),
                            _("Fill in config.txt (LightCraft CLI, language, and the default library and photos root), "
                              "save it, then restart this window.\n\nIt will open now."))
        open_text(C.CONFIG_FILE)

    # --- library and photos root, remembered between sessions
    def build_library_bar(self):
        bar = ttk.Frame(self, padding=(6, 6, 6, 0))
        bar.pack(fill="x")
        libs = self.state_data.get("libraries") or []
        last = self.state_data.get("last") or C.LIBRARY
        root = next((l.get("root") for l in libs if l.get("path") == last), None) or C.ROOT
        ttk.Label(bar, text=_("Library:")).grid(row=0, column=0, sticky="w")
        self.v_library = tk.StringVar(value=last)
        self.cb_library = ttk.Combobox(bar, textvariable=self.v_library, width=60,
                                       values=[l.get("path") for l in libs if l.get("path")])
        self.cb_library.grid(row=0, column=1, sticky="we", padx=4)
        self.cb_library.bind("<<ComboboxSelected>>", self.library_chosen)
        ttk.Button(bar, text=_("Browse…"), command=self.browse_library).grid(row=0, column=2)
        ttk.Label(bar, text=_("Photos root:")).grid(row=0, column=3, sticky="w", padx=(12, 0))
        self.v_root = tk.StringVar(value=root)
        ttk.Entry(bar, textvariable=self.v_root, width=34).grid(row=0, column=4, sticky="we", padx=4)
        ttk.Button(bar, text=_("Browse…"), command=self.browse_root).grid(row=0, column=5)
        bar.columnconfigure(1, weight=2)
        bar.columnconfigure(4, weight=1)
        CURRENT["root"] = root
        self.v_root.trace_add("write", lambda *a: self.root_changed())

    def library_chosen(self, _evt=None):
        for l in self.state_data.get("libraries") or []:
            if l.get("path") == self.v_library.get() and l.get("root"):
                self.v_root.set(l["root"])

    def browse_library(self):
        d = filedialog.askdirectory(title=_("Choose a LightCraft library"), mustexist=True,
                                    initialdir=self.v_library.get() or os.path.expanduser("~"))
        if d:
            self.v_library.set(os.path.normpath(d))
            self.library_chosen()

    def browse_root(self):
        d = filedialog.askdirectory(title=_("Choose the folder that holds the photos"), mustexist=True,
                                    initialdir=self.v_root.get() or os.path.expanduser("~"))
        if d:
            self.v_root.set(os.path.normpath(d))

    def root_changed(self):
        CURRENT["root"] = os.path.normpath(self.v_root.get().strip()) if self.v_root.get().strip() else ""
        # forms keep folders of the old root: rebuild them with the new one
        for f in self.forms.values():
            f.destroy()
        self.forms.clear()
        self.select()

    def remember_library(self, lib, root):
        libs = [l for l in self.state_data.get("libraries") or [] if l.get("path") != lib]
        self.state_data["libraries"] = ([{"path": lib, "root": root}] + libs)[:12]
        self.state_data["last"] = lib
        save_state(self.state_data)
        self.cb_library.configure(values=[l["path"] for l in self.state_data["libraries"]])

    def check_library(self):
        """(library, root) chosen in the window, or None after telling what is wrong."""
        lib = os.path.normpath(self.v_library.get().strip()) if self.v_library.get().strip() else ""
        root = CURRENT["root"]
        if not lib or not os.path.isdir(lib):
            messagebox.showerror(_("Library"), _("Library folder not found:\n{path}", path=lib))
            return None
        if not looks_like_library(lib) and not messagebox.askyesno(
                _("Library"), _("This folder does not look like a LightCraft library (no catalog.snap):"
                                "\n{path}\n\nUse it anyway?", path=lib), icon="warning", default="no"):
            return None
        if not root or not os.path.isdir(root):
            messagebox.showerror(_("Photos root"), _("Photos root not found:\n{path}", path=root))
            return None
        return lib, root

    def help(self):
        for name in ("README.%s.md" % C.LANGUAGE, "README.md"):
            if os.path.exists(os.path.join(HERE, name)):
                return open_path(os.path.join(HERE, name))

    def select(self, _evt=None):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.specs:
            return
        s = self.specs[sel[0]]
        for f in self.forms.values():
            f.pack_forget()
        if sel[0] not in self.forms:
            self.forms[sel[0]] = Form(self.form_frame, s)
        self.forms[sel[0]].pack(fill="x")
        self.v_title.set("%s   (%s)" % (s["title"], s["file"]))
        self.v_summary.set(s["summary"])
        self.update_buttons()

    def current(self):
        sel = self.tree.selection()
        return sel[0] if sel and sel[0] in self.specs else None

    def update_buttons(self):
        busy = self.proc is not None
        iid = self.current()
        ro = bool(iid and self.specs[iid].get("read_only"))
        self.b_dry.configure(text=_("Run (read only)") if ro else _("Dry run"),
                             state="disabled" if busy or not iid else "normal")
        self.b_apply.configure(state="disabled" if busy or ro or not iid else "normal")
        self.b_stop.configure(state="normal" if busy else "disabled")
        self.tree.state(["disabled"] if busy else ["!disabled"])

    def launch(self, apply):
        iid = self.current()
        if not iid or self.proc is not None:
            return
        s = self.specs[iid]
        chosen = self.check_library()
        if not chosen:
            return
        self.lib_env = {"LC_LIBRARY": chosen[0], "LC_PHOTOS_ROOT": chosen[1]}
        try:
            runs = self.forms[iid].runs()
        except ValueError as e:
            messagebox.showerror(_("Incomplete settings"), str(e))
            return
        signature = (iid, chosen, tuple(tuple(a) for _l, a in runs))
        via_app = C.CONNECTION != "library" and C.app_running()
        running = [] if via_app else lightcraft_processes()
        if running and not messagebox.askyesno(
                _("LightCraft seems to be open"),
                _("Running: {names}\n\nLightCraft does not answer on its control port ({port}): the "
                  "script will open the library itself, which fails while it is open elsewhere.\n\n"
                  "Run anyway?", names=", ".join(running), port=C.PORT[1]), icon="warning", default="no"):
            return
        if apply:
            details = "\n".join("  " + " ".join(a) for _l, a in runs) or "  " + _("(no setting)")
            text = (_("Apply {title}?", title=s["title"]) + "\n\n" + _("Library: {path}", path=chosen[0])
                    + "\n\n" + details + "\n")
            if signature not in self.dry_ok:
                text += "\n⚠ " + _("No successful dry run with exactly these settings since this window "
                                   "was opened.") + "\n"
            else:
                text += "\n" + _("If the catalogue has not changed since the dry run, its plan is reused "
                                  "without reading the photos again.") + "\n"
            text += "\n" + _("This time, the catalogue will be changed.")
            if not messagebox.askyesno(_("Confirm"), text, icon="warning", default="no"):
                return
        self.remember_library(*chosen)
        self.applying, self.signature, self.start = apply, signature, time.time()
        self.products.delete(0, "end")
        script = os.path.join(HERE, s["file"])
        # --use-plan: the script reuses its dry run's plan if the catalogue has not changed since
        self.queue_runs = [(label, [PYTHON, "-u", script] + args + (["--apply", "--use-plan"] if apply else []))
                           for label, args in runs]
        mode = _("APPLY") if apply else (_("READ") if s.get("read_only") else _("DRY RUN"))
        way = _("through the open LightCraft") if via_app else _("library opened directly")
        self.write("\n%s  %s — %s  (%s)\n" % (time.strftime("%H:%M:%S"), mode, s["title"], way), "title")
        self.next_run()

    def next_run(self):
        if not self.queue_runs:
            return self.finish(True)
        label, cmd = self.queue_runs.pop(0)
        if label:
            self.write("--- %s\n" % label, "title")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", **self.lib_env)
        try:
            self.proc = subprocess.Popen(cmd, cwd=HERE, env=env, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         encoding="utf-8", errors="replace", bufsize=1,
                                         creationflags=NO_WINDOW)
        except OSError as e:
            self.write(_("Cannot start: {error}", error=e) + "\n", "stop")
            return self.finish(False)
        self.v_state.set(_("Running…"))
        self.update_buttons()
        threading.Thread(target=self.read, args=(self.proc,), daemon=True).start()

    def read(self, proc):
        for line in proc.stdout:
            self.stream.put(("line", line))
        proc.wait()
        self.stream.put(("end", proc.returncode))

    def poll(self):
        try:
            while True:
                kind, val = self.stream.get_nowait()
                if kind == "line":
                    tag = "stop" if val.startswith((_("STOP"), "STOP", "Traceback")) else (
                        "done" if val.startswith((_("Done"), _("Finished"))) else None)
                    self.write(val, tag)
                else:
                    self.proc = None
                    if val != 0:
                        self.write(_("The script stopped (code {code}).", code=val) + "\n", "stop")
                        self.queue_runs = []
                        self.finish(False)
                    else:
                        self.next_run()
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def finish(self, ok):
        self.proc = None
        if ok and not self.applying:
            self.dry_ok.add(self.signature)
        self.v_state.set(_("Finished.") if ok else _("Stopped."))
        if ok:
            self.write(_("Finished.") + "\n", "done")
        self.list_products()
        self.update_buttons()

    def stop(self):
        if self.proc is None:
            return
        if not messagebox.askyesno(_("Stop"), _("Stop the running script?\n\nCommands already sent to "
                                                "LightCraft will complete; run a dry run afterwards to "
                                                "see where things stand."), icon="warning", default="no"):
            return
        self.queue_runs = []
        try:
            self.proc.terminate()
        except OSError:
            pass

    def write(self, text, tag=None):
        self.out.configure(state="normal")
        self.out.insert("end", text, tag)
        self.out.see("end")
        self.out.configure(state="disabled")

    def clear(self):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.configure(state="disabled")

    def list_products(self):
        self.products.delete(0, "end")
        if not os.path.isdir(C.OUTPUT_DIR):
            return
        for name in sorted(os.listdir(C.OUTPUT_DIR)):
            p = os.path.join(C.OUTPUT_DIR, name)
            if name.lower().endswith(PRODUCTS) and os.path.getmtime(p) >= self.start - 1:
                self.products.insert("end", os.path.relpath(p, HERE))

    def open_output(self):
        os.makedirs(C.OUTPUT_DIR, exist_ok=True)
        open_path(C.OUTPUT_DIR)

    def open_product(self, _evt=None):
        sel = self.products.curselection()
        if sel:
            open_path(os.path.join(HERE, self.products.get(sel[0])))

    def close(self):
        if self.proc is not None and not messagebox.askyesno(
                _("Script running"), _("A script is still running. Close anyway (it will be stopped)?"),
                icon="warning", default="no"):
            return
        if self.proc is not None:
            try:
                self.proc.terminate()
            except OSError:
                pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
