# -*- coding: utf-8 -*-
"""Re-points photos to their path written with backslashes, so that the RAW and JPG of a shot are
recognised as a pair (otherwise, on Windows, both may write the same sidecar). Touches no file.
Run after each import or folder synchronisation.   uv run lc_relink.py   then   --apply"""
import os
from lc_common import _, options, APPLY, run, photos_by_folder, pairs, batches, dry_run_end

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
TARGET = "twins"           # "twins": only the non-raw files of pairs ; "all": every photo
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


def main():
    pf = photos_by_folder(FOLDER)
    steps, absent = [], 0
    for d, photos in pf.items():
        if TARGET == "all":
            targets = photos
        else:
            targets = [t for _r, ts in pairs(photos) for t in ts if t["kind"] != "raw"]
        for p in targets:
            path = os.path.join(d, p["fileName"])
            if not os.path.isfile(path):
                absent += 1
                print(_("  not found on disk: {path}", path=path))
                continue
            steps.append({"command": "photo.relink", "params": {"id": p["id"], "path": path}})
    print(_("{count} photos to re-point ({target}), {absent} files not found",
            count=len(steps), target=TARGET, absent=absent))
    if not APPLY:
        return dry_run_end()
    failed, done = 0, 0
    for batch in batches(steps, 1000):
        failed += sum(1 for x in run(batch) if not x.get("ok"))
        done += len(batch)
        print("  %d / %d" % (done, len(steps)))
    print(_("Done: {ok} re-pointed, {failed} failed.", ok=len(steps) - failed, failed=failed))


if __name__ == "__main__":
    main()
