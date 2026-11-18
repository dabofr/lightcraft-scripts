# -*- coding: utf-8 -*-
"""Fills the location / city / state / country fields from the keywords and the places table
(places_table.csv, or the file named in config.txt).
   uv run lc_places.py   then   uv run lc_places.py --apply
Run AFTER lc_mirror.py, otherwise a JPG that has not yet received its raw's keyword is missed.

Rules:
  1. A museum of the table (keyword under museums_branch) gives the location; its city, state
     and country come from its line (the state may come from the place keyword).
  2. Otherwise the most precise place keyword (under places_branch) gives the four fields.
  3. A field is replaced only if it is empty or holds a name already found in the keywords or in
     the table for this photo. Any other value (typed by hand) is kept. A field is never emptied.
  4. Not processed but listed in places_to_check.csv: keyword missing from the table, several
     unrelated places, several museums, museum and place that disagree, typed value kept.
Writes places_plan.csv (final value of the four fields and the fields that change)."""
import csv
import sys
from lc_common import (_, options, write_csv, relative, CONNECTED, APPLY, run, photos_by_folder,
                       batches, dry_run_end, PLACES_BRANCH, MUSEUMS_BRANCH, PLACES_TABLE)

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)

FIELDS = ("location", "city", "state", "country")


def read_table():
    for enc in ("utf-8-sig", "cp1252"):      # Excel often saves as cp1252
        try:
            with open(PLACES_TABLE, encoding=enc, newline="") as f:
                lines = list(csv.reader(f, delimiter=";"))
            break
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            sys.exit(_("STOP: places table not found: {path}", path=PLACES_TABLE))
    else:
        sys.exit(_("STOP: encoding of {path} not recognised", path=PLACES_TABLE))
    table = {}
    for line in lines[1:]:                    # first line = column titles
        if len(line) >= 5 and line[0].strip() and not line[0].startswith("#"):
            table[line[0].strip()] = tuple(x.strip() for x in line[1:5])
    if not table:
        sys.exit(_("STOP: empty or unreadable table: {path}", path=PLACES_TABLE))
    return table


def finest(keywords):
    return [k for k in keywords if not any(a.startswith(k + "|") for a in keywords)]


def main():
    table = read_table()
    print(_("{count} lines in the table", count=len(table)))
    pf = photos_by_folder(FOLDER)
    photos = [(d, p) for d in sorted(pf) for p in pf[d]
              if any(k.startswith(PLACES_BRANCH) or k.startswith(MUSEUMS_BRANCH)
                     for k in (p.get("keywords") or []))]
    print(_("{count} photos with a place or museum keyword; detailed read...", count=len(photos)))
    current = {}
    for batch in batches([p["id"] for _d, p in photos], 500):
        rep = run([{"command": "photo.inspect", "params": {"id": i}} for i in batch])
        for i, x in zip(batch, rep):
            m = ((x.get("result") or {}).get("meta")) or {}
            current[i] = tuple((m.get(c) or "").strip() for c in FIELDS)
        print("  %d / %d" % (len(current), len(photos)))

    names = {"location": _("location"), "city": _("city"), "state": _("state"), "country": _("country")}
    plan, to_check, actions, kept = [], [], {}, 0
    for d, p in photos:
        rel, name = relative(d), p["fileName"]
        kw = p.get("keywords") or []
        places = finest([k for k in kw if k.startswith(PLACES_BRANCH)])
        museums = [k for k in kw if k.startswith(MUSEUMS_BRANCH)]
        unknown = [k for k in places + museums if k not in table]
        if unknown:
            to_check.append([rel, name, _("not in the table"), " ; ".join(unknown)])
            continue
        if len(places) > 1:
            to_check.append([rel, name, _("several places"), " ; ".join(places)])
            continue
        if len(museums) > 1:
            to_check.append([rel, name, _("several museums"), " ; ".join(museums)])
            continue
        P = table[places[0]] if places else None
        M = table[museums[0]] if museums else None
        if M and P:
            if (M[3] and P[3] and M[3] != P[3]) or (M[1] and P[1] and M[1] != P[1]):
                to_check.append([rel, name, _("museum and place disagree"), museums[0] + " ; " + places[0]])
                continue
            want = (M[0], M[1] or P[1], M[2] or P[2], M[3] or P[3])
        else:
            want = M or P
        # names we may replace: keyword segments and table values along the keyword path
        known = set()
        for k in places + museums:
            parts = k.split("|")
            known.update(s.casefold() for s in parts)
            for n in range(1, len(parts) + 1):
                known.update(v.casefold() for v in table.get("|".join(parts[:n]), ()) if v)
        change = {}
        for field, cur, v in zip(FIELDS, current[p["id"]], want):
            if not v or cur == v:
                continue
            if cur and cur.casefold() not in known:
                kept += 1
                to_check.append([rel, name, _("typed value kept ({field})", field=names[field]),
                                 _("{current} (proposed: {value})", current=cur, value=v)])
                continue
            change[field] = v
        if change:
            actions.setdefault(tuple(sorted(change.items())), []).append(p["id"])
            after = [change.get(c, cur) for c, cur in zip(FIELDS, current[p["id"]])]
            plan.append([rel, name] + after + [" ; ".join(names[c] for c in FIELDS if c in change)])

    write_csv("places_plan.csv", [_("folder"), _("file"), _("location after"), _("city after"),
                                  _("state after"), _("country after"), _("fields changed")], plan)
    write_csv("places_to_check.csv", [_("folder"), _("file"), _("reason"), _("detail")], to_check)
    print(_("{photos} photos to complete, {lines} lines to check (of which {kept} typed values kept)",
            photos=len(plan), lines=len(to_check), kept=kept))
    if not APPLY:
        return dry_run_end()

    steps = []
    for change, ids in actions.items():
        for batch in batches(ids, 50 if CONNECTED else 500):
            p = {"ids": batch}
            p.update(dict(change))
            steps.append({"command": "photo.setMeta", "params": p})
    failed, done = 0, 0
    for batch in batches(steps, 20):
        failed += sum(1 for x in run(batch) if not x.get("ok"))
        done += len(batch)
        print(_("  {done} / {total} commands", done=done, total=len(steps)))
    print(_("Done: {photos} photos completed in {commands} commands, {failed} commands refused.",
            photos=len(plan), commands=len(steps), failed=failed))


if __name__ == "__main__":
    main()
