# -*- coding: utf-8 -*-
"""Stacks each RAW + JPG pair of the same name, raw on top, collapsed. Pairs already stacked are
left as they are.   uv run lc_stacks.py   then   uv run lc_stacks.py --apply
A test pair is stacked and checked first; if the result is not as expected, the script stops."""
import sys
from lc_common import _, options, APPLY, run, photos_by_folder, pairs, batches, command_doc, dry_run_end

# ---------------------------------------------------------------------------------- settings
FOLDER = r"D:\Photos"     # folder to process, subfolders included
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


def stacks_of(groups):
    """Photos of the stack of each group's first photo."""
    rep = run([{"command": "photo.inspect", "params": {"id": ids[0]}} for ids in groups])
    return [((x.get("result") or {}).get("stack") or {}).get("photos") or [] for x in rep]


def group(ids):
    # top: without it, LightCraft puts the active photo on top, not necessarily the raw
    return {"command": "stack.group", "params": {"ids": ids, "top": ids[0], "collapsed": True}}


def main():
    pf = photos_by_folder(FOLDER)
    every = [[r["id"]] + [t["id"] for t in ts] for photos in pf.values() for r, ts in pairs(photos)]
    print(_("{count} pairs found; reading their state...", count=len(every)))
    todo = []
    for batch in batches(every, 500):
        for ids, s in zip(batch, stacks_of(batch)):
            if not set(ids) <= set(s):
                todo.append(ids)
    print(_("{todo} pairs to stack, {done} already stacked", todo=len(todo), done=len(every) - len(todo)))
    if not APPLY:
        return dry_run_end()
    if not todo:
        return print(_("Nothing to do."))

    test = todo[0]
    run([group(test)])
    s = stacks_of([test])[0]
    if not (set(test) <= set(s) and s[0] == test[0]):
        print(_("stack.group documentation in this version: {doc}", doc=command_doc("stack.group")))
        sys.exit(_("STOP: the test pair was not stacked as expected (stack: {stack}).", stack=s))

    done, wrong = 1, []
    for batch in batches(todo[1:], 200):
        run([group(ids) for ids in batch])
        for ids, s in zip(batch, stacks_of(batch)):
            if not (set(ids) <= set(s) and s[0] == ids[0]):
                wrong.append(ids)
        done += len(batch)
        print(_("  {done} / {total}  (not as expected: {wrong})", done=done, total=len(todo), wrong=len(wrong)))
    print(_("Done: {ok} stacks created and checked, {wrong} not as expected.",
            ok=len(todo) - len(wrong), wrong=len(wrong)))
    if wrong:
        print(_("Ids of the pairs not as expected (raw first): {ids}", ids=wrong[:50]))


if __name__ == "__main__":
    main()
