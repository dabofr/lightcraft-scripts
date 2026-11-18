# -*- coding: utf-8 -*-
"""Everything to do after an import, in order, on one or several folders:
   1. relink (backslash paths, so RAW + JPG pairs are recognised)
   2. reload from disk (camera / lens fields)                          [optional]
   3. removal of unnamed faces found by automatic detection            [optional]
   4. RAW + JPG stacks, raw on top
   5. sidecars written from the catalogue
Keywords mirroring and places are not done here: run lc_mirror.py then lc_places.py afterwards.
   uv run lc_after_import.py              (dry run: counts, changes nothing)
   uv run lc_after_import.py --apply"""
import os
import sys
import lc_relink
import lc_reload
import lc_unnamed_faces
import lc_stacks
import lc_sidecars
from lc_common import _, options, APPLY

# ---------------------------------------------------------------------------------- settings
FOLDERS = [
    r"D:\Photos\2026\10",
    # r"D:\Photos\2026\11",      # one line per folder; subfolders included
]
RELOAD = True              # step 2: False if camera / lens fields are already filled
PURGE_FACES = True         # step 3: False to keep detected faces (to name them later)
RELINK_TARGET = "all"      # "all" (advised after an import) or "twins"
SIDECARS_TARGET = "all"    # "all" (safe once relinked), "all_but_twins" or "raw"
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


def title(text):
    print("\n" + "=" * 78 + "\n" + text + "\n" + "=" * 78)


def main():
    for d in FOLDERS:
        if not os.path.isdir(d):
            sys.exit(_("STOP: folder not found: {folder}", folder=d))
    print(_("Mode: {mode}", mode=_("APPLY") if APPLY else _("dry run")))
    lc_relink.TARGET = RELINK_TARGET
    lc_sidecars.TARGET = SIDECARS_TARGET

    for d in FOLDERS:
        title(_("1. Relink - {folder}", folder=d))
        lc_relink.FOLDER = d
        lc_relink.main()
    if RELOAD:
        for d in FOLDERS:
            title(_("2. Reload - {folder}", folder=d))
            lc_reload.FOLDER = d
            lc_reload.TARGET = "all"
            lc_reload.main()
    if PURGE_FACES:
        title(_("3. Unnamed faces (whole library)"))
        lc_unnamed_faces.main()
    for d in FOLDERS:
        title(_("4. Stacks - {folder}", folder=d))
        lc_stacks.FOLDER = d
        lc_stacks.main()
    for d in FOLDERS:
        title(_("5. Sidecars - {folder}", folder=d))
        lc_sidecars.FOLDER = d
        lc_sidecars.main()
    title(_("Finished") if APPLY else _("Dry run finished: run again with --apply"))


if __name__ == "__main__":
    main()
