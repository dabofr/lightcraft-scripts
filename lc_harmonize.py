# -*- coding: utf-8 -*-
"""Mirror RAW <-> JPG metadata, then fill the place fields, with ONE sidecar write at the end.
   uv run lc_harmonize.py   then   uv run lc_harmonize.py --apply

Same as running lc_mirror.py then lc_places.py, but the sidecars of every photo changed by either
of them are written once, in one grouped pass, after both: faster on a large library (automatic
writing is paused meanwhile and switched back on whatever happens).
The dry run writes the CSV files of both scripts. Note that the places dry run cannot yet see the
keywords the mirror is about to add: a photo may show up a second time in the places plan after
applying. When in doubt, run it twice."""
import lc_mirror
import lc_places
from lc_common import _, options, APPLY, DeferredSidecars

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


def title(text):
    print("\n" + "=" * 78 + "\n" + text + "\n" + "=" * 78)


def main():
    lc_mirror.FOLDER = FOLDER
    lc_places.FOLDER = FOLDER
    with DeferredSidecars() as d:
        title(_("1. Mirror RAW <-> JPG"))
        lc_mirror.main(d)
        title(_("2. Place fields"))
        lc_places.main(d)
        if APPLY:
            title(_("3. Sidecars"))
    title(_("Finished") if APPLY else _("Dry run finished: run again with --apply"))


if __name__ == "__main__":
    main()
