# -*- coding: utf-8 -*-
"""Removes the UNNAMED faces found by automatic detection (description "Detected by ...") from the
whole library. Named faces and regions read from a sidecar are never touched. Changes the
catalogue only.   uv run lc_unnamed_faces.py   then   --apply
Turn face recognition off in LightCraft first, otherwise they come back."""
import json
import sys
from lc_common import _, options, APPLY, run, one, batches, command_doc, dry_run_end

# ---------------------------------------------------------------------------------- settings
ONLY_DETECTED = True       # True: only "Detected by ..." regions; False: every region without a name
# -------------------------------------------------------------------------------------------
options(globals())         # settings possibly given on the command line (GUI)


def photo_id(face):
    for k in ("photo", "photoId", "photo_id", "id"):
        if isinstance(face.get(k), int):
            return face[k]
    return None


def regions_to_remove(pid):
    x = run([{"command": "photo.inspect", "params": {"id": pid}}])[0]
    regs = (((x.get("result") or {}).get("meta") or {}).get("regions")) or []
    result = []
    for i, r in enumerate(regs):
        if (r.get("name") or "").strip():
            continue
        if ONLY_DETECTED and not (r.get("description") or "").startswith("Detected by"):
            continue
        result.append(i)
    return result


def main():
    # without an explicit limit, LightCraft returns only 600
    state = one("faces.unnamed", {"limit": 100000}) or {}
    faces = state.get("faces") or []
    print(_("Unnamed faces: {count}", count=state.get("total")))
    if not faces:
        return print(_("Nothing to do."))
    photos = sorted({photo_id(f) for f in faces} - {None})
    if not photos:
        print(json.dumps(faces[0], ensure_ascii=False)[:600])
        sys.exit(_("STOP: format of faces.unnamed not recognised."))
    plan = {p: regions_to_remove(p) for p in photos}
    total = sum(len(v) for v in plan.values())
    print(_("{regions} regions to remove on {photos} photos", regions=total, photos=len(photos)))
    if not APPLY:
        return dry_run_end()

    # from the last index to the first, so the remaining indexes do not shift
    steps = [{"command": "photo.removeRegion", "params": {"id": p, "index": i}}
             for p, idx in plan.items() for i in sorted(idx, reverse=True)]
    if not steps:
        return print(_("Nothing to do."))
    test = run(steps[:1])[0]
    if not test.get("ok"):
        print(_("photo.removeRegion documentation in this version: {doc}",
                doc=command_doc("photo.removeRegion")))
        sys.exit(_("STOP: the first removal was refused ({error}).", error=test.get("error")))
    failed = 0
    for batch in batches(steps[1:], 500):
        failed += sum(1 for x in run(batch) if not x.get("ok"))
    left = (one("faces.unnamed") or {}).get("total")
    print(_("Done: {count} removals requested, {failed} refused. Unnamed faces left: {left}",
            count=len(steps), failed=failed, left=left))
    if left:
        print(_("Some are left: run the script again (a removal does not always succeed the first time)."))


if __name__ == "__main__":
    main()
