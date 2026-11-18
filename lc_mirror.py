# -*- coding: utf-8 -*-
"""Gives a RAW and its twin(s) of the same name the same keywords.
   uv run lc_mirror.py   then   uv run lc_mirror.py --apply

Rules:
  1. Union of both sides' keywords.
  2. The more precise wins: if one side has `A|B` and the other only has the parent `A`, the
     parent is removed and both get `A|B`. A parent kept on both sides stays.
  3. Contradiction = each side has, in the same top-level branch, a keyword the other lacks that
     is neither its parent nor its child (two different places, two different people...). The
     pair is NOT touched; it is listed in mirror_conflicts.csv for you to decide.
Ratings and flags are not concerned. Writes mirror_plan.csv (what will be done)."""
from lc_common import (_, options, write_csv, relative, CONNECTED, APPLY, run, photos_by_folder,
                       pairs, batches, dry_run_end, catalog_seq, save_plan, load_plan, forget_plan, DeferredSidecars)

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


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


def build_steps(actions):
    """[(added, removed, ids)] -> photo.setMeta commands; small batches through the open app."""
    steps = []
    for add, rem, ids in actions:
        for batch in batches(ids, 50 if CONNECTED else 500):
            p = {"ids": batch}
            if add:
                p["addKeywords"] = list(add)
            if rem:
                p["removeKeywords"] = list(rem)
            steps.append({"command": "photo.setMeta", "params": p})
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
    key = {"folder": FOLDER}
    plan_saved = load_plan("lc_mirror", key)
    if plan_saved:
        apply(plan_saved["steps"], plan_saved["summary"]["photos"], deferred)
        return forget_plan("lc_mirror", key)
    seq = catalog_seq()
    pf = photos_by_folder(FOLDER)
    plan, conflicts, ok = [], [], 0
    actions = {}     # (added, removed) -> [ids]
    for d in sorted(pf):
        for r, ts in pairs(pf[d]):
            members = [r] + ts
            want, problem = set(members[0].get("keywords") or []), []
            for m in members[1:]:
                want, problem = target(want, set(m.get("keywords") or []))
                if problem:
                    break
            rel = relative(d)
            if problem:
                conflicts.append([rel, r["fileName"], " ; ".join(sorted({x for x, _y in problem})),
                                  " ; ".join(sorted({y for _x, y in problem}))])
                continue
            changed = False
            for m in members:
                k = set(m.get("keywords") or [])
                add, rem = tuple(sorted(want - k)), tuple(sorted(k - want))
                if add or rem:
                    changed = True
                    actions.setdefault((add, rem), []).append(m["id"])
                    # for each removal, the more precise keyword that justifies it
                    cause = " ; ".join(sorted({x for y in rem for x in want if parent_of(y, x)}))
                    plan.append([rel, m["fileName"], " ; ".join(add), " ; ".join(rem), cause,
                                 " ; ".join(sorted(want))])
            ok += 0 if changed else 1

    write_csv("mirror_plan.csv", [_("folder"), _("file"), _("added"), _("removed"),
                                  _("removed because replaced by"), _("keywords after")], plan)
    write_csv("mirror_conflicts.csv", [_("folder"), _("RAW"), _("only on the RAW"), _("only on the twin")],
              conflicts)
    print(_("{ok} pairs already matching, {photos} photos to change, {conflicts} pairs in contradiction "
            "(left untouched)", ok=ok, photos=len(plan), conflicts=len(conflicts)))
    actions = [[list(add), list(rem), ids] for (add, rem), ids in actions.items()]
    if not APPLY:
        save_plan("lc_mirror", key, seq, actions, {"photos": len(plan)})
        return dry_run_end()
    apply(actions, len(plan), deferred)
    forget_plan("lc_mirror", key)


if __name__ == "__main__":
    main()
