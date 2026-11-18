# -*- coding: utf-8 -*-
"""Writes the .xmp sidecars from the catalogue (one way: catalogue -> files). LightCraft merges into
the existing sidecar and keeps what other programs put there.
   uv run lc_sidecars.py   then   uv run lc_sidecars.py --apply
WARNING: run lc_relink.py first, otherwise a JPG twin may overwrite its raw's sidecar."""
import json
from lc_common import (_, options, output, CONNECTED, APPLY, run, one, photos_by_folder, pairs,
                       batches, size, dry_run_end)

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
TARGET = "all_but_twins"   # "raw": raws only
                           # "all_but_twins": everything except the JPG twins of a raw
                           # "twins": only the JPG twins of a raw (creates IMG.JPG.xmp)
                           # "all": every photo, JPG twins included (safe once relinked)
BATCH = 500
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)
if CONNECTED:              # through the open app, each command must finish within 60 s
    BATCH = min(BATCH, 50)


def main():
    if TARGET not in ("raw", "all_but_twins", "twins", "all"):
        raise SystemExit(_("STOP: unknown TARGET: {target}", target=TARGET))
    print(_("XMP preferences: {prefs}", prefs=json.dumps(one("library.xmpPreferences"))))
    pf = photos_by_folder(FOLDER)
    ids = []
    for photos in pf.values():
        twins = {t["id"] for _r, ts in pairs(photos) for t in ts if t["kind"] != "raw"}
        for p in photos:
            if TARGET == "raw" and p["kind"] != "raw":
                continue
            if TARGET == "all_but_twins" and p["id"] in twins:
                continue
            if TARGET == "twins" and p["id"] not in twins:
                continue
            ids.append(p["id"])
    ids = sorted(set(ids))
    print(_("{count} sidecars to write ({target})", count=len(ids), target=TARGET))
    if not APPLY:
        return dry_run_end()
    total = {"written": 0, "merged": 0, "backups": 0, "failed": 0}
    done, errors = 0, 0
    with open(output("sidecars_log.jsonl"), "w", encoding="utf-8") as log:
        for batch in batches(ids, BATCH):
            x = run([{"command": "photo.saveMetadataToFile", "params": {"ids": batch}}])[0]
            log.write(json.dumps(x, ensure_ascii=False) + "\n")
            done += len(batch)
            if not x.get("ok"):
                errors += 1
                print(_("  batch FAILED: {error}", error=x.get("error")))
                continue
            for k in total:
                total[k] += size((x.get("result") or {}).get(k, 0))
            print(_("  {done} / {total}  (failures so far: {failed})",
                    done=done, total=len(ids), failed=total["failed"]))
    print(_("Done: {written} written, of which {merged} merged, {backups} safety backups, "
            "{failed} failures.", **total))
    if errors:
        print(_("{count} batches failed: see the sidecars_log file in the output folder", count=errors))


if __name__ == "__main__":
    main()
