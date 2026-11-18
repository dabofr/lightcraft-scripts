# -*- coding: utf-8 -*-
"""READ-ONLY audit of RAW / JPG consistency and of places. Only writes CSV files.
   uv run lc_audit.py

Writes:
  audit_pairs.csv    one line per pair whose keywords, place fields, rating or flag differ
  audit_places.csv   photos with a keyword of the places branch but neither city nor country,
                     or with a named face that has no keyword of the same name
                     (only with PLACES = True: slower, one detailed read per photo)"""
from lc_common import (_, options, write_csv, relative, run, photos_by_folder, pairs, batches,
                       PLACES_BRANCH)

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to audit, subfolders included
PLACES = True              # False: pairs only (fast)
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


def details(ids):
    """{id: (location, city, state, country, [names of named faces])} through photo.inspect."""
    result = {}
    for batch in batches(ids, 500):
        rep = run([{"command": "photo.inspect", "params": {"id": i}} for i in batch])
        for i, x in zip(batch, rep):
            m = ((x.get("result") or {}).get("meta")) or {}
            names = sorted({(r.get("name") or "").strip() for r in (m.get("regions") or [])} - {""})
            result[i] = (m.get("location") or "", m.get("city") or "", m.get("state") or "",
                         m.get("country") or "", names)
        print(_("  detailed read: {done} / {total}", done=len(result), total=len(ids)))
    return result


def main():
    pf = photos_by_folder(FOLDER)
    every = [p for ps in pf.values() for p in ps]
    print(_("{count} photos", count=len(every)))
    det = details([p["id"] for p in every]) if PLACES else {}

    cases = {"same": _("identical"), "raw": _("RAW richer"), "jpg": _("JPG richer"), "diff": _("diverging")}
    counts = {k: 0 for k in cases}
    rows = []
    for d in sorted(pf):
        for r, ts in pairs(pf[d]):
            for t in ts:
                if t["kind"] == "raw":
                    continue
                kr, kt = set(r.get("keywords") or []), set(t.get("keywords") or [])
                case = "same" if kr == kt else "raw" if kr > kt else "jpg" if kt > kr else "diff"
                counts[case] += 1
                other = []
                if r.get("rating") != t.get("rating"):
                    other.append(_("rating {raw}/{twin}", raw=r.get("rating"), twin=t.get("rating")))
                if r.get("flag") != t.get("flag"):
                    other.append(_("flag {raw}/{twin}", raw=r.get("flag"), twin=t.get("flag")))
                if det and det[r["id"]][:4] != det[t["id"]][:4]:
                    other.append(_("place {raw} / {twin}", raw=" ; ".join(det[r["id"]][:4]),
                                   twin=" ; ".join(det[t["id"]][:4])))
                if case != "same" or other:
                    rows.append([relative(d), r["fileName"], t["fileName"], cases[case],
                                 " ; ".join(sorted(kr - kt)), " ; ".join(sorted(kt - kr)), " | ".join(other)])
    write_csv("audit_pairs.csv", [_("folder"), _("RAW"), _("twin"), _("keywords"), _("only on the RAW"),
                                  _("only on the twin"), _("other differences")], rows)
    print(_("Pairs: {summary}", summary=", ".join("%s %d" % (cases[k], counts[k]) for k in cases)))
    print(_("{count} lines in the pairs file", count=len(rows)))

    if det:
        lines, no_place = [], 0
        for d in sorted(pf):
            for p in pf[d]:
                kw = p.get("keywords") or []
                places = sorted(k for k in kw if k.startswith(PLACES_BRANCH))
                location, city, state, country, names = det[p["id"]]
                missing = sorted(n for n in names if not any(k.split("|")[-1] == n for k in kw))
                if (places and not (city or country)) or missing:
                    lines.append([relative(d), p["fileName"], " ; ".join(places),
                                  location, city, country, " ; ".join(missing)])
                if not places and not (location or city or country):
                    no_place += 1
        write_csv("audit_places.csv", [_("folder"), _("file"), _("place keywords"), _("location"), _("city"),
                                       _("country"), _("named faces without keyword")], lines)
        print(_("{count} lines in the places file (place keyword without city or country, or named "
                "face without keyword)", count=len(lines)))
        print(_("{count} photos without any place information", count=no_place))


if __name__ == "__main__":
    main()
