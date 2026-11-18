# -*- coding: utf-8 -*-
"""Bulk "Reload from disk" (photo.reload): reads the files' EXIF again and fills empty camera and
lens fields, keeping keywords and edits. Does NOT replace a camera or lens name already in the
catalogue.   uv run lc_reload.py   then   uv run lc_reload.py --apply
Reloading may start face detection again: the script counts unnamed faces before and after. If
some appear, run lc_unnamed_faces.py."""
from lc_common import _, options, CONNECTED, APPLY, run, one, photos_by_folder, batches, dry_run_end

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
TARGET = "all"             # "all" or "raw"
BATCH = 200
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)
if CONNECTED:              # through the open app, each command must finish within 60 s
    BATCH = min(BATCH, 50)


def main():
    pf = photos_by_folder(FOLDER)
    ids = sorted(p["id"] for ps in pf.values() for p in ps if TARGET == "all" or p["kind"] == "raw")
    before = (one("faces.unnamed") or {}).get("total")
    print(_("{count} photos to reload ({target}); unnamed faces now: {faces}",
            count=len(ids), target=TARGET, faces=before))
    if not APPLY:
        return dry_run_end()
    done, reloaded, failed = 0, 0, 0
    for batch in batches(ids, BATCH):
        x = run([{"command": "photo.reload", "params": {"ids": batch, "wait": True}}])[0]
        done += len(batch)
        if x.get("ok"):
            r = (x.get("result") or {}).get("reloaded")
            reloaded += len(r) if isinstance(r, list) else (r or 0)
        else:
            failed += 1
            print(_("  batch FAILED: {error}", error=x.get("error")))
        print("  %d / %d" % (done, len(ids)))
    after = (one("faces.unnamed") or {}).get("total")
    print(_("Done: {count} reloaded according to LightCraft, {failed} batches failed.",
            count=reloaded, failed=failed))
    print(_("Unnamed faces: {before} before, {after} after.", before=before, after=after))


if __name__ == "__main__":
    main()
