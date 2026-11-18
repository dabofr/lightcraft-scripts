# -*- coding: utf-8 -*-
"""Gives a RAW and its twin(s) of the same name the same metadata.
   uv run lc_mirror.py   then   uv run lc_mirror.py --apply

What is mirrored (each part can be switched off below):
  - keywords;
  - text and place fields: title, caption, alt text, extended description, copyright notice,
    creator, location, city, state, country, GPS position;
  - rating, flag (pick / reject) and colour label.

Rules for keywords:
  1. Union of both sides' keywords.
  2. The more precise wins: if one side has `A|B` and the other only has the parent `A`, the
     parent is removed and both get `A|B`. A parent kept on both sides stays.
  3. Contradiction = each side has, in the same top-level branch, a keyword the other lacks that
     is neither its parent nor its child (two different places, two different people...).
     The pair's keywords are NOT touched.
Rules for the other fields: a value filled on one side only is copied to the side(s) where it is
empty (a rating of 0, no flag or no label count as empty). Two different values = contradiction:
that field of that pair is NOT touched.
Contradictions are listed in mirror_conflicts.csv for you to decide; mirror_plan.csv lists every
change, photo by photo.

Not mirrored: copyright status, usage terms and copyright URL (this version of LightCraft does not
give them back when a photo is read, so they cannot be compared), face regions, edits, albums."""
from lc_common import (_, options, write_csv, relative, CONNECTED, APPLY, run, photos_by_folder,
                       pairs, batches, dry_run_end, catalog_seq, save_plan, load_plan, forget_plan,
                       DeferredSidecars)

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
KEYWORDS = True            # mirror keywords
FIELDS = True              # mirror text, place and GPS fields (slower: one detailed read per photo)
RATING_FLAG_LABEL = True   # mirror rating, flag and colour label
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)

# field read by photo.inspect (meta) -> parameter of photo.setMeta
TEXT_FIELDS = [("title", "title"), ("caption", "caption"), ("alt_text", "altText"),
               ("extended_description", "extendedDescription"), ("copyright", "copyright"),
               ("creator", "creator"), ("location", "location"), ("city", "city"),
               ("state", "state"), ("country", "country"), ("gps", "gps")]
# field of catalog.query -> (command, parameter, empty value)
MARKS = [("rating", "photo.rate", "rating", 0), ("flag", "photo.flag", "flag", "none"),
         ("label", "photo.label", "label", None)]


def label(field):
    names = {"title": _("title"), "caption": _("caption"), "alt_text": _("alt text"),
             "extended_description": _("extended description"), "copyright": _("copyright"),
             "creator": _("creator"), "location": _("location"), "city": _("city"), "state": _("state"),
             "country": _("country"), "gps": _("GPS"), "rating": _("rating"), "flag": _("flag"),
             "label": _("colour label")}
    return names.get(field, field)


def parent_of(a, b):
    """Is a a strict ancestor of b?"""
    return b.startswith(a + "|")


def related(a, b):
    return a == b or parent_of(a, b) or parent_of(b, a)


def target(ka, kb):
    """(keywords both sides should have, conflicts) for two keyword sets."""
    only_a, only_b = ka - kb, kb - ka
    conflicts = [(x, y) for x in only_a for y in only_b
                 if x.split("|")[0] == y.split("|")[0] and not related(x, y)]
    if conflicts:
        return None, conflicts
    union, common = ka | kb, ka & kb
    # a parent is removed only if it is not on both sides and a descendant exists
    return {k for k in union if k in common or not any(parent_of(k, o) for o in union)}, []


def gps_value(v):
    """GPS as [lat, lon] rounded to ~1 cm, whatever form LightCraft gives it in; None if empty."""
    if v in (None, "", [], {}):
        return None
    if isinstance(v, dict):
        lat, lon = v.get("lat", v.get("latitude")), v.get("lon", v.get("lng", v.get("longitude")))
    elif isinstance(v, (list, tuple)) and len(v) >= 2:
        lat, lon = v[0], v[1]
    elif isinstance(v, str) and "," in v:
        lat, lon = v.split(",", 1)
    else:
        return None
    try:
        return [round(float(lat), 7), round(float(lon), 7)]
    except (TypeError, ValueError):
        return None


def norm(field, v):
    """Comparable value, or None when the field counts as empty."""
    if field == "gps":
        return gps_value(v)
    if isinstance(v, str):
        return v.strip() or None
    return v


def shown(v):
    return "" if v is None else (", ".join(map(str, v)) if isinstance(v, list) else str(v))


def read_meta(ids):
    """{id: meta} through photo.inspect."""
    result = {}
    for batch in batches(ids, 500):
        rep = run([{"command": "photo.inspect", "params": {"id": i}} for i in batch])
        for i, x in zip(batch, rep):
            result[i] = ((x.get("result") or {}).get("meta")) or {}
        print(_("  detailed read: {done} / {total}", done=len(result), total=len(ids)))
    return result


def build_steps(actions):
    """[[command, params, ids]] -> commands; small batches through the open app (60 s limit)."""
    steps = []
    for command, params, ids in actions:
        for batch in batches(ids, 50 if CONNECTED else 500):
            p = dict(params)
            p["ids"] = batch
            steps.append({"command": command, "params": p})
    return steps


def apply(actions, photos, deferred=None):
    """Applies the changes; sidecars written once at the end (or by the caller's `deferred`)."""
    if deferred is None:
        with DeferredSidecars() as d:
            return apply(actions, photos, d)
    steps = build_steps(actions)
    failed, done = 0, 0
    for batch in batches(steps, 50):
        deferred.add(i for s in batch for i in s["params"]["ids"])
        failed += sum(1 for x in run(batch) if not x.get("ok"))
        done += len(batch)
        print(_("  {done} / {total} commands", done=done, total=len(steps)))
    print(_("Done: {photos} photos changed in {commands} commands, {failed} commands refused.",
            photos=photos, commands=len(steps), failed=failed))
    print(_("Run the script again as a dry run to check: it should announce 0 photos to change."))


def main(deferred=None):
    key = {"folder": FOLDER, "keywords": KEYWORDS, "fields": FIELDS, "marks": RATING_FLAG_LABEL}
    plan_saved = load_plan("lc_mirror", key)
    if plan_saved:
        apply(plan_saved["steps"], plan_saved["summary"]["photos"], deferred)
        return forget_plan("lc_mirror", key)
    seq = catalog_seq()
    pf = photos_by_folder(FOLDER)
    groups = [(d, [r] + ts) for d in sorted(pf) for r, ts in pairs(pf[d])]
    meta = read_meta([m["id"] for _d, ms in groups for m in ms]) if FIELDS else {}

    plan, conflicts, changed_ids, ok = [], [], set(), 0
    actions = {}     # (command, frozen params) -> [ids]

    def change(m, rel, command, params, field, before, after, detail=""):
        actions.setdefault((command, tuple(sorted((k, tuple(v) if isinstance(v, list) else v)
                                                  for k, v in params.items()))), []).append(m["id"])
        plan.append([rel, m["fileName"], field, before, after, detail])
        changed_ids.add(m["id"])

    for d, members in groups:
        rel, raw = relative(d), members[0]
        before = len(plan)
        # keywords
        if KEYWORDS:
            want, problem = set(raw.get("keywords") or []), []
            for m in members[1:]:
                want, problem = target(want, set(m.get("keywords") or []))
                if problem:
                    break
            if problem:
                conflicts.append([rel, raw["fileName"], _("keywords"),
                                  " ; ".join(sorted({x for x, _y in problem})),
                                  " ; ".join(sorted({y for _x, y in problem}))])
            else:
                for m in members:
                    k = set(m.get("keywords") or [])
                    add, rem = sorted(want - k), sorted(k - want)
                    if add or rem:
                        p = {}
                        if add:
                            p["addKeywords"] = add
                        if rem:
                            p["removeKeywords"] = rem
                        cause = " ; ".join(sorted({x for y in rem for x in want if parent_of(y, x)}))
                        change(m, rel, "photo.setMeta", p, _("keywords"), " ; ".join(rem), " ; ".join(add),
                               _("removed because replaced by") + " : " + cause if cause else "")
        # text, place and GPS fields
        for field, param in (TEXT_FIELDS if FIELDS else []):
            values = [norm(field, meta[m["id"]].get(field)) for m in members]
            filled = [v for v in values if v is not None]
            distinct = {repr(v) for v in filled}
            if len(distinct) > 1:
                conflicts.append([rel, raw["fileName"], label(field), shown(values[0]),
                                  " | ".join(shown(v) for v in values[1:])])
            elif filled:
                for m, v in zip(members, values):
                    if v is None:
                        change(m, rel, "photo.setMeta", {param: filled[0]}, label(field), "", shown(filled[0]))
        # rating, flag, colour label
        for field, command, param, empty in (MARKS if RATING_FLAG_LABEL else []):
            values = [m.get(field) if m.get(field) not in (empty, None, "") else None for m in members]
            filled = [v for v in values if v is not None]
            if len(set(filled)) > 1:
                conflicts.append([rel, raw["fileName"], label(field), shown(values[0]),
                                  " | ".join(shown(v) for v in values[1:])])
            elif filled:
                for m, v in zip(members, values):
                    if v is None:
                        change(m, rel, command, {param: filled[0]}, label(field), "", shown(filled[0]))
        ok += 1 if len(plan) == before else 0

    write_csv("mirror_plan.csv", [_("folder"), _("file"), _("field"), _("before / removed"),
                                  _("after / added"), _("detail")], plan)
    write_csv("mirror_conflicts.csv", [_("folder"), _("RAW"), _("field"), _("on the RAW"), _("on the twin(s)")],
              conflicts)
    print(_("{ok} pairs already matching, {photos} photos to change ({changes} changes), {conflicts} "
            "contradictions (left untouched)", ok=ok, photos=len(changed_ids), changes=len(plan),
            conflicts=len(conflicts)))
    actions = [[command, {k: list(v) if isinstance(v, tuple) else v for k, v in params}, ids]
               for (command, params), ids in actions.items()]
    if not APPLY:
        save_plan("lc_mirror", key, seq, actions, {"photos": len(changed_ids)})
        return dry_run_end()
    apply(actions, len(changed_ids), deferred)
    forget_plan("lc_mirror", key)


if __name__ == "__main__":
    main()
