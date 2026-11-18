# LightCraft batch scripts

Python scripts, with a small window to launch them, to tidy up a large [LightCraft](https://github.com/storytold/lightcraft) library on Windows: RAW + JPG pairs, sidecars, stacks, unnamed faces, keywords and place fields.

![LightCraft scripts GUI](LC%20Scripts%20GUI.jpg)


**Provided as is, without support.** They were written for one library and shared as a starting point: fork them, change them, keep what suits you. Tested with LightCraft 0.21.1 on Windows. A later version may change a command and break a script.

## What they do

| Script | Purpose |
|---|---|
| `lc_inventory.py` | Read only. Counts photos, raws and RAW + JPG pairs per folder; lists photos without a sidecar on disk. |
| `lc_audit.py` | Read only. Lists pairs whose keywords, rating, flag or place fields differ, and photos with a place keyword but no city or country. |
| `lc_relink.py` | Re-points photos to their path written with backslashes. Works around a path comparison issue that can make a RAW and its JPG write the **same** sidecar on Windows. Touches no file. |
| `lc_sidecars.py` | Writes `.xmp` sidecars from the catalogue (one way). |
| `lc_reload.py` | Bulk "Reload from disk", to fill empty camera / lens fields. |
| `lc_stacks.py` | Stacks each RAW + JPG pair, raw on top, collapsed. |
| `lc_collapse_stacks.py` | Collapses every expanded stack. |
| `lc_unnamed_faces.py` | Removes unnamed faces found by automatic detection. Named faces are never touched. |
| `lc_mirror.py` | Gives a raw and its JPG the same keywords; the more precise keyword wins; contradictions are listed, not touched. |
| `lc_places.py` | Fills location / city / state / country from keywords, through a table (`places_table.csv`). |
| `lc_after_import.py` | Relink, reload, unnamed faces, stacks and sidecars in one go, on one or several folders. |
| `lc_gui.py` | The window: pick a script, folders and settings, then *Dry run* and *Apply*. |

`lc_common.py` holds what they share.


## Safety first

- **Every script is a dry run by default.** It counts, lists and writes its CSV files, and changes nothing. Changes only happen with `--apply` (or the *Apply* button, which asks for confirmation).
- **The catalogue is the reference**; sidecars are written from it, never read back in bulk. No script deletes a photo or a file.
- **Back up your library** before the first real run, and read the CSV files a dry run produces before applying.
- Mirror and places use **your** keyword hierarchy: set the branches in `config.txt`, and treat these two scripts as examples to adapt.

## Setup

1. Install [uv](https://docs.astral.sh/uv/) (or Python 3.11+). The scripts use only the standard library.
2. Put the files in a folder, run `uv run lc_inventory.py` once: it creates `config.txt` from `config.example.txt` and stops.
3. Fill in `config.txt` (plain text, opens in Notepad): path of `lightcraft-cli.exe`, language, keyword branches, and a default library and photos root.
4. Optional but handy: set the environment variable `LIGHTCRAFT_CONTROL_PORT=7980` (`setx LIGHTCRAFT_CONTROL_PORT 7980`, then restart LightCraft). The scripts can then work **while LightCraft is open**.
5. Double-click `Launch-GUI.bat`, or run `uv run lc_gui.py`. At the top of the window, choose the **library** and its **photos root**: the window remembers every library used, with its root, in a drop-down list.

## How they reach LightCraft

Only one program at a time can open a library.

- **LightCraft open** (and listening on its control port): the scripts send their commands to it, and you see the changes live. They first check that LightCraft has the chosen library open, and stop otherwise. Good for quick jobs. Don't use LightCraft while a script runs; keep its window visible.
- **LightCraft closed**: the scripts open the library themselves. Faster for big jobs on a whole library.

The choice is automatic; the first line printed says which way is used (`connection` in `config.txt` can force it).

## Output files

CSV files and logs go to the `Output` folder, never overwriting one another: `places_plan 2026-11-18 1.csv`, then `… 2.csv`. They are UTF-8 with `;` separators and open in Excel.

## The places table

`places_table.csv` maps a keyword to the four place fields:

```
keyword;location;city;state;country
Places|France|Porquerolles;Porquerolles;Hyères;Provence-Alpes-Côte d'Azur;France
Type|Museums|Louvre;Musée du Louvre;Paris;Île-de-France;France
```

A museum keyword wins over a place keyword (the location becomes the museum). Photos whose keywords are missing from the table are listed in `places_to_check.csv`: add lines, run again.

## Translations

Texts are written in English and translated through `lang/<code>.json` (`lang/fr.json` is included). To add a language, copy `fr.json` to, say, `it.json`, translate the right-hand side, keep the `{names}` in braces, and set `language = "it"` (or `"auto"`). Missing texts stay in English.

## Command line

```
uv run lc_relink.py                                   # dry run with the values written in the script
uv run lc_relink.py --FOLDER="D:\Photos\2026\10" --TARGET=all --apply
```

## Licence

MIT. See `LICENSE`.
