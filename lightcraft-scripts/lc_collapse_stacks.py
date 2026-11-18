# -*- coding: utf-8 -*-
"""Collapses every expanded stack of the library (stack.collapseAll, the same as the menu
View > Stacks > Collapse All Stacks). Changes neither the content nor the order of the stacks.
   uv run lc_collapse_stacks.py --apply"""
from lc_common import _, options, APPLY, one, dry_run_end

options(globals())


def main():
    if not APPLY:
        print(_("Would collapse every expanded stack of the library."))
        return dry_run_end()
    n = (one("stack.collapseAll") or {}).get("changed")
    print(_("Stacks collapsed: {count}", count=n))
    left = (one("stack.collapseAll") or {}).get("changed")
    print(_("Check (second call, should be 0): {count}", count=left))


if __name__ == "__main__":
    main()
