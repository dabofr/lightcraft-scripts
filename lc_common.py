# -*- coding: utf-8 -*-
r"""Shared helpers for the LightCraft scripts. Keep this file next to the scripts.

Settings that depend on your machine live in config.txt (created from config.example.txt on
first run). Every script runs as a DRY RUN by default and only changes something with --apply:
    uv run lc_xxx.py
    uv run lc_xxx.py --apply
Settings written at the top of a script can be overridden on the command line (this is how the
GUI passes them):
    uv run lc_relink.py --FOLDER="D:\Photos\2026\10" --TARGET=all

Only one program at a time can open a LightCraft library. If LightCraft is running and listens
on its control port, the scripts send their commands to it; otherwise they open the library
themselves (LightCraft must then be closed).
"""
import datetime
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# config.txt (TOML format, plain text: opens in Notepad); an older config.toml is still read
CONFIG_FILE = os.path.join(HERE, "config.txt")
if not os.path.exists(CONFIG_FILE) and os.path.exists(os.path.join(HERE, "config.toml")):
    CONFIG_FILE = os.path.join(HERE, "config.toml")
CONFIG_EXAMPLE = os.path.join(HERE, "config.example.txt")


# ------------------------------------------------------------------------------------ config
def _load_config():
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        sys.exit("STOP: Python 3.11 or later is required (tomllib).")
    created = False
    if not os.path.exists(CONFIG_FILE) and os.path.exists(CONFIG_EXAMPLE):
        shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)
        created = True
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f), created
    except FileNotFoundError:
        sys.exit("STOP: config.txt not found next to the scripts.")
    except tomllib.TOMLDecodeError as e:
        sys.exit("STOP: config.txt is not valid: %s\n(Tip: write Windows paths between single "
                 "quotes, e.g. 'D:\\Photos'.)" % e)


CONFIG, CONFIG_CREATED = _load_config()
CLI = CONFIG.get("cli", "")
# the GUI passes the chosen library and photos root through these variables
LIBRARY = os.environ.get("LC_LIBRARY") or CONFIG.get("library", "")
_root = os.environ.get("LC_PHOTOS_ROOT") or CONFIG.get("photos_root", "")
ROOT = os.path.normpath(_root) if _root else ""
ROOT_FILTER = ROOT.replace("\\", "/")          # the root as LightCraft declares folders
CONNECTION = CONFIG.get("connection", "auto")   # "auto", "app" or "library"
PORT = ("127.0.0.1", int(CONFIG.get("control_port", 7980)))
PLACES_BRANCH = CONFIG.get("places_branch", "Places|")
MUSEUMS_BRANCH = CONFIG.get("museums_branch", "Type|Museums|")
PLACES_TABLE = os.path.join(HERE, CONFIG.get("places_table", "places_table.csv"))
OUTPUT_DIR = os.path.join(HERE, CONFIG.get("output_folder", "Output"))
PAGE = 2000                                     # photos per listing request

APPLY = "--apply" in sys.argv
USE_PLAN = "--use-plan" in sys.argv   # with --apply: reuse the last dry run if the catalogue is unchanged


# ------------------------------------------------------------------------------- translation
def _language():
    wanted = str(CONFIG.get("language", "auto")).lower()
    if wanted != "auto":
        return wanted
    code = None
    if os.name == "nt":
        try:
            import ctypes
            code = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage())
        except Exception:
            code = None
    if not code:
        try:
            code = locale.getlocale()[0]
        except ValueError:
            code = None
    return (code or "en")[:2].lower()


LANGUAGE = _language()
_TRANSLATIONS = {}
if LANGUAGE != "en":
    try:
        with open(os.path.join(HERE, "lang", LANGUAGE + ".json"), encoding="utf-8") as _f:
            _TRANSLATIONS = {k: v for k, v in json.load(_f).items() if not k.startswith("_")}
    except (OSError, ValueError):
        _TRANSLATIONS = {}


def _(text, **values):
    """Translated text (English if no translation exists), with {named} values filled in."""
    t = _TRANSLATIONS.get(text) or text
    return t.format(**values) if values else t


# ------------------------------------------------------------------------- connection to LC
def app_running():
    """Is LightCraft running and listening on its control port?"""
    import socket
    try:
        with socket.create_connection(PORT, timeout=0.5):
            return True
    except OSError:
        return False


CONNECTED = CONNECTION == "app" or (CONNECTION == "auto" and app_running())
LINK = ["--connect", "%s:%d" % PORT] if CONNECTED else ["--library", LIBRARY]


def same_path(a, b):
    return os.path.normcase(os.path.normpath(a or "")) == os.path.normcase(os.path.normpath(b or ""))


def check_setup():
    if CONFIG_CREATED:
        sys.exit(_("STOP: config.txt has just been created from the example. Edit it (LightCraft "
                   "CLI, library, photos root), then run again."))
    if not CLI or not os.path.isfile(CLI):
        sys.exit(_("STOP: lightcraft-cli not found at {path}. Set 'cli' in config.txt.", path=CLI))
    if not ROOT:
        sys.exit(_("STOP: no photos root: set 'photos_root' in config.txt or choose it in the window."))
    if CONNECTED:
        # the open app works on ITS library: make sure it is the one chosen
        info = one("library.info") or {}
        opened = info.get("path") if isinstance(info, dict) else None
        if opened and LIBRARY and not same_path(opened, LIBRARY):
            sys.exit(_("STOP: LightCraft has another library open ({opened}) than the one chosen "
                       "({chosen}). Open the right one, or close LightCraft.", opened=opened, chosen=LIBRARY))
    elif not os.path.isdir(LIBRARY):
        sys.exit(_("STOP: library not found at {path}.", path=LIBRARY))
    recover_sidecars()


def options(g):
    """Replace a script's settings with those given on the command line as --NAME=value. Without
    options, the values written in the script apply. For a list setting, repeat the option:
    --FOLDERS=a --FOLDERS=b. Only the script that was launched refuses an unknown name (a module
    called by another one ignores options that are not its own)."""
    main = g.get("__name__") == "__main__"
    if main:
        print(_("Link: LightCraft is open (port {port}) - keep its window visible", port=PORT[1])
              if CONNECTED else _("Link: library opened directly (LightCraft must be closed)"))
        check_setup()
    lists, seen = {}, []
    for arg in sys.argv[1:]:
        if not arg.startswith("--") or "=" not in arg:
            continue
        name, val = arg[2:].split("=", 1)
        if name not in g or not name.isupper():
            if main:
                sys.exit(_("STOP: unknown setting for this script: {name}", name=name))
            continue
        current = g[name]
        if isinstance(current, bool):
            if val.lower() not in ("1", "0", "true", "false", "yes", "no"):
                sys.exit(_("STOP: {name} expects 1 or 0, not {value}", name=name, value=val))
            g[name] = val.lower() in ("1", "true", "yes")
        elif isinstance(current, int):
            g[name] = int(val)
        elif isinstance(current, list):
            lists.setdefault(name, []).append(val)
        else:
            g[name] = val
        if name not in seen:
            seen.append(name)
    g.update(lists)
    if main and seen:
        print(_("Settings received: {settings}",
                settings=" ; ".join("%s = %s" % (n, g[n]) for n in seen)))


def run(steps, tolerate_failures=True):
    """Run a list of {command, params} in one process; one reply per command."""
    if not steps:
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for s in steps:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
        path = f.name
    try:
        r = subprocess.run([CLI, "run"] + LINK + ["--script", path, "--keep-going"],
                           capture_output=True, encoding="utf-8", errors="replace")
    finally:
        os.unlink(path)
    lines = [json.loads(l) for l in r.stdout.splitlines() if l.strip().startswith("{")]
    if len(lines) != len(steps):
        print(r.stderr[-2000:])
        if CONNECTED:
            sys.exit(_("STOP: {got} replies for {sent} commands through the open LightCraft. Was "
                       "LightCraft closed meanwhile?", got=len(lines), sent=len(steps)))
        sys.exit(_("STOP: {got} replies for {sent} commands. Is the library already open elsewhere "
                   "(LightCraft started without its control port, or another program)?",
                   got=len(lines), sent=len(steps)))
    if not tolerate_failures:
        for s, x in zip(steps, lines):
            if not x.get("ok"):
                sys.exit(_("STOP: {command} refused: {error}", command=s["command"], error=x.get("error")))
    return lines


def one(command, params=None):
    """A single command; returns its result or stops the script."""
    return run([{"command": command, "params": params or {}}], tolerate_failures=False)[0].get("result")


def command_doc(ident):
    """Parameter documentation of a command, as the installed LightCraft describes it."""
    r = subprocess.run([CLI, "commands", "--json"], capture_output=True, encoding="utf-8", errors="replace")
    try:
        for c in json.loads(r.stdout):
            if c.get("id") == ident:
                return c.get("params") or _("(no documented parameter)")
    except ValueError:
        pass
    return _("(command {command} not found in this version)", command=ident)


# ------------------------------------------------------------------------------------ photos
def folder_filter(folder):
    rel = os.path.relpath(folder, ROOT)
    if rel.startswith(".."):
        sys.exit(_("STOP: {folder} is not under {root}", folder=folder, root=ROOT))
    return ROOT_FILTER if rel == "." else ROOT_FILTER + "/" + rel.replace("\\", "/")


def photos_by_folder(folder):
    """{exact folder: [photos]} for the folder and its subfolders (trash and virtual copies
    excluded). Each photo belongs to the deepest folder that holds it."""
    folder = os.path.normpath(folder)
    if not os.path.isdir(folder):
        sys.exit(_("STOP: {folder} not found (drive disconnected?)", folder=folder))
    folders = sorted((d for d, _d, _f in os.walk(folder)), key=lambda d: d.count(os.sep), reverse=True)
    rep = run([{"command": "catalog.query",
                "params": {"filter": {"libraryFolder": folder_filter(d)}, "limit": 1}}
               for d in folders], tolerate_failures=False)
    totals = {d: x["result"]["total"] for d, x in zip(folders, rep)}
    steps, plan = [], []
    for d in folders:
        for off in range(0, totals[d], PAGE):
            steps.append({"command": "catalog.query",
                          "params": {"filter": {"libraryFolder": folder_filter(d)},
                                     "offset": off, "limit": PAGE}})
            plan.append(d)
    rep = run(steps, tolerate_failures=False)
    seen, result, received = set(), {}, {d: 0 for d in folders}
    for d, x in zip(plan, rep):
        for p in x["result"]["photos"]:
            received[d] += 1
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            if p.get("deleted") or p.get("copyOf") is not None:
                continue
            result.setdefault(d, []).append(p)
    for d in folders:
        if received[d] != totals[d]:
            sys.exit(_("STOP: incomplete list for {folder} ({got} of {total})",
                       folder=d, got=received[d], total=totals[d]))
    return result


def pairs(photos):
    """[(raw, [twins])] among the photos of ONE folder: same name without extension. With several
    raws (DNG + RAF), the first one by name is the owner and the others count as twins."""
    groups = {}
    for p in photos:
        groups.setdefault(os.path.splitext(p["fileName"])[0].lower(), []).append(p)
    result = []
    for g in groups.values():
        raws = sorted((p for p in g if p["kind"] == "raw"), key=lambda p: p["fileName"].lower())
        others = [p for p in g if p["kind"] != "raw"]
        if raws and others:
            result.append((raws[0], raws[1:] + others))
    return result


def batches(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def size(v):
    return len(v) if isinstance(v, (list, dict)) else (v if isinstance(v, int) else (1 if v else 0))


def relative(folder):
    return os.path.relpath(folder, ROOT)


# ------------------------------------------------------------------------------------ output
def output(name):
    """Path of a new output file in the output folder, never overwriting one:
    "places_plan.csv" becomes "places_plan 2026-11-18 1.csv", then "... 2.csv", and so on."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base, ext = os.path.splitext(name)
    day = datetime.date.today().isoformat()
    n = 1
    while os.path.exists(os.path.join(OUTPUT_DIR, "%s %s %d%s" % (base, day, n, ext))):
        n += 1
    path = os.path.join(OUTPUT_DIR, "%s %s %d%s" % (base, day, n, ext))
    print(_("File: {path}", path=os.path.relpath(path, HERE)))
    return path


def write_csv(name, header, rows):
    import csv
    with open(output(name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


# ------------------------------------------------------------------------- dry-run plans
# A dry run saves the exact commands it would send, with the catalogue's change counter (seq of
# library.info) read BEFORE reading the photos. An apply run with --use-plan reuses them only if
# the counter has not moved since and the settings are the same: the catalogue is then exactly as
# the dry run saw it. Otherwise it reads everything again, as without the option.
PLANS_DIR = os.path.join(OUTPUT_DIR, ".plans")


def catalog_seq():
    """The catalogue's change counter, or None if this LightCraft does not give it."""
    try:
        x = run([{"command": "library.info", "params": {}}])[0]
    except SystemExit:
        return None
    r = x.get("result") if x.get("ok") else None
    return r.get("seq") if isinstance(r, dict) and isinstance(r.get("seq"), int) else None


def _plan_path(script, settings):
    import hashlib
    key = json.dumps({"script": script, "library": os.path.normcase(os.path.normpath(LIBRARY or "")),
                      "settings": settings}, sort_keys=True, ensure_ascii=False)
    return os.path.join(PLANS_DIR, "%s-%s.json" % (script, hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]))


def save_plan(script, settings, seq, steps, summary):
    """Keep the commands of a dry run for a later --apply --use-plan."""
    if seq is None:
        return
    os.makedirs(PLANS_DIR, exist_ok=True)
    with open(_plan_path(script, settings), "w", encoding="utf-8") as f:
        json.dump({"seq": seq, "created": datetime.datetime.now().isoformat(timespec="minutes"),
                   "summary": summary, "steps": steps}, f, ensure_ascii=False)


def load_plan(script, settings):
    """The saved plan if --use-plan was asked and the catalogue has not changed since, else None."""
    if not (APPLY and USE_PLAN):
        return None
    path = _plan_path(script, settings)
    try:
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
    except (OSError, ValueError):
        print(_("No dry-run plan for these settings: full check."))
        return None
    seq = catalog_seq()
    if seq is None or seq != plan.get("seq"):
        print(_("The catalogue changed since the dry run of {time}: full check.", time=plan.get("created")))
        return None
    print(_("Catalogue unchanged since the dry run of {time}: its plan is used, without reading the "
            "photos again.", time=plan.get("created")))
    return plan


def forget_plan(script, settings):
    try:
        os.unlink(_plan_path(script, settings))
    except OSError:
        pass


def file_hash(path):
    import hashlib
    try:
        with open(path, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()
    except OSError:
        return None


# ------------------------------------------------------------------- deferred sidecar writes
# Measured on a real library: with automatic writing on, writing the sidecar takes about 80 % of
# the time of a metadata change, and one grouped explicit write costs about half as much per photo.
# So the big scripts switch automatic writing off, remember the photos they change, write their
# sidecars in one go at the end, and switch it back on WHATEVER HAPPENS. LightCraft does NOT catch
# up on its own when automatic writing is switched back on (tested), hence the list of photos and a
# marker file: if a script is killed meanwhile, the next script to run finishes the job first.
STATE_DIR = os.path.join(HERE, ".state")


def _marker():
    import hashlib
    lib = os.path.normcase(os.path.normpath(LIBRARY or ""))
    return os.path.join(STATE_DIR, "sidecars-%s.json" % hashlib.sha1(lib.encode("utf-8")).hexdigest()[:12])


def _write_sidecars(ids):
    ids = sorted(set(ids))
    if not ids:
        return
    print(_("Writing the sidecars of {count} changed photos...", count=len(ids)))
    total = {"written": 0, "failed": 0}
    for batch in batches(ids, 50 if CONNECTED else 500):
        x = run([{"command": "photo.saveMetadataToFile", "params": {"ids": batch}}])[0]
        r = x.get("result") or {}
        total["written"] += size(r.get("written", 0))
        total["failed"] += size(r.get("failed", 0)) if x.get("ok") else len(batch)
    print(_("Sidecars: {written} written, {failed} failures.", **total))


def _set_auto_write(on):
    one("library.xmpPreferences", {"autoWrite": bool(on)})


def recover_sidecars():
    """If a previous run was interrupted with automatic writing off, finish its work now."""
    path = _marker()
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    print(_("A previous run was interrupted while sidecar writing was deferred: finishing it first."))
    _write_sidecars(state.get("ids") or [])
    _set_auto_write(True)
    os.unlink(path)
    print(_("Automatic sidecar writing is on again."))


class DeferredSidecars:
    """with DeferredSidecars() as d: ... d.add(ids) before changing photos ...
    Does nothing if automatic writing was already off (the user's choice is kept)."""

    def __init__(self):
        self.ids, self.active = set(), False

    def __enter__(self):
        prefs = one("library.xmpPreferences") or {}
        if APPLY and prefs.get("autoWrite"):
            os.makedirs(STATE_DIR, exist_ok=True)
            self.active = True
            self._save()
            _set_auto_write(False)
            print(_("Automatic sidecar writing paused; the sidecars will be written once at the end."))
        return self

    def add(self, ids):
        if self.active:
            self.ids.update(ids)
            self._save()               # saved BEFORE the change, so nothing is lost on a crash

    def _save(self):
        with open(_marker(), "w", encoding="utf-8") as f:
            json.dump({"library": LIBRARY, "ids": sorted(self.ids),
                       "since": datetime.datetime.now().isoformat(timespec="seconds")}, f)

    def __exit__(self, *exc):
        if not self.active:
            return False
        try:
            _write_sidecars(self.ids)
        finally:
            _set_auto_write(True)
            try:
                os.unlink(_marker())
            except OSError:
                pass
            print(_("Automatic sidecar writing is on again."))
        return False


def dry_run_end():
    print(_("Dry run: nothing was changed. Run again with --apply."))
