# -*- coding: utf-8 -*-
"""Inventory of a folder (read only): photos, raws, RAW + JPG pairs, sidecars missing on disk.
A photo on its own counts as having a sidecar with IMG.xmp or IMG.JPG.xmp; a JPG twin of a raw
needs its own IMG.JPG.xmp (IMG.xmp belongs to the raw).
Writes inventory.csv and no_sidecar.txt to the output folder.   uv run lc_inventory.py"""
import os
from lc_common import _, options, output, write_csv, relative, photos_by_folder, pairs

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to inventory, subfolders included
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


def has_sidecar(folder, name):
    base = os.path.splitext(name)[0]
    for cand in (base + ".xmp", base + ".XMP", name + ".xmp", name + ".XMP"):
        if os.path.isfile(os.path.join(folder, cand)):
            return True
    return False


def has_own_sidecar(folder, name):
    return any(os.path.isfile(os.path.join(folder, name + ext)) for ext in (".xmp", ".XMP"))


def main():
    pf = photos_by_folder(FOLDER)
    rows, missing_all = [], []
    tot = [0, 0, 0, 0, 0]
    for d in sorted(pf):
        photos = pf[d]
        ps = pairs(photos)
        twins = {t["id"] for _r, ts in ps for t in ts}
        raws = [p for p in photos if p["kind"] == "raw"]
        # a JPG twin without its own sidecar is normal: only the others are checked
        missing = [p["fileName"] for p in photos
                   if p["id"] not in twins and not has_sidecar(d, p["fileName"])]
        twins_missing = [p["fileName"] for p in photos
                         if p["id"] in twins and p["kind"] != "raw" and not has_own_sidecar(d, p["fileName"])]
        missing_all += [os.path.join(d, n) for n in missing]
        missing_all += [os.path.join(d, n) + "   (" + _("twin") + ")" for n in twins_missing]
        counts = (len(photos), len(raws), len(ps), len(missing), len(twins_missing))
        rows.append([relative(d)] + list(counts))
        tot = [a + b for a, b in zip(tot, counts)]
    write_csv("inventory.csv", [_("folder"), _("photos"), _("raw"), _("pairs"),
                                _("without sidecar (twins excluded)"), _("twins without own sidecar")], rows)
    with open(output("no_sidecar.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(missing_all))
    print(_("{photos} photos, {raws} raw, {pairs} pairs, {missing} without sidecar (JPG twins excluded)",
            photos=tot[0], raws=tot[1], pairs=tot[2], missing=tot[3]))
    print(_("JPG twins without their own sidecar (IMG.JPG.xmp): {count}", count=tot[4]))


if __name__ == "__main__":
    main()
