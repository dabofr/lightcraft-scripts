# Scripts de traitement par lots pour LightCraft

Des scripts Python, avec une petite fenêtre pour les lancer, pour mettre de l'ordre dans une grosse bibliothèque [LightCraft](https://github.com/storytold/lightcraft) sous Windows : paires RAW + JPG, sidecars, piles, visages sans nom, mots-clés et champs de lieu.

![LightCraft scripts GUI](LC%20Scripts%20GUI%20Fr.jpg)

**Fournis tels quels, sans support.** Ils ont été écrits pour une bibliothèque et sont partagés comme point de départ : copiez-les, modifiez-les, gardez ce qui vous sert. Testés avec LightCraft 0.21.1 sous Windows. Une version ultérieure pourra changer une commande et casser un script.

## Ce qu'ils font

| Script | Rôle |
|---|---|
| `lc_inventory.py` | Lecture seule. Compte photos, RAW et paires RAW + JPG par dossier ; liste les photos sans sidecar sur le disque. |
| `lc_audit.py` | Lecture seule. Liste les paires dont les mots-clés, la note, le drapeau ou les champs de lieu diffèrent, et les photos qui ont un mot-clé de lieu sans ville ni pays. |
| `lc_relink.py` | Re-pointe les photos sur leur chemin écrit en antislashs. Contourne un problème de comparaison des chemins qui peut faire écrire le RAW et son JPG dans le **même** sidecar sous Windows. Ne touche à aucun fichier. |
| `lc_sidecars.py` | Écrit les sidecars `.xmp` depuis le catalogue (sens unique). |
| `lc_reload.py` | « Recharger depuis le disque » en masse, pour remplir les champs appareil et objectif vides. |
| `lc_stacks.py` | Empile chaque paire RAW + JPG, RAW en tête, pile repliée. |
| `lc_collapse_stacks.py` | Replie toutes les piles ouvertes. |
| `lc_unnamed_faces.py` | Supprime les visages sans nom détectés automatiquement. Les visages nommés ne sont jamais touchés. |
| `lc_mirror.py` | Donne les mêmes mots-clés au RAW et à son JPG ; le plus précis l'emporte ; les contradictions sont listées, pas touchées. |
| `lc_places.py` | Remplit lieu, ville, province et pays depuis les mots-clés, grâce à une table (`places_table.csv`). |
| `lc_after_import.py` | Relink, rechargement, visages sans nom, piles et sidecars d'un coup, sur un ou plusieurs dossiers. |
| `lc_gui.py` | La fenêtre : choisir un script, des dossiers et des réglages, puis *Essai à blanc* et *Appliquer*. |

`lc_common.py` regroupe ce qu'ils partagent.

## Sécurité d'abord

- **Chaque script tourne à blanc par défaut** : il compte, liste et écrit ses CSV, sans rien modifier. Il n'agit qu'avec `--apply` (ou le bouton *Appliquer*, qui demande confirmation).
- **Le catalogue fait foi** ; les sidecars en sont la copie, jamais relue en masse. Aucun script ne supprime de photo ni de fichier.
- **Sauvegardez votre bibliothèque** avant le premier vrai lancement, et lisez les CSV d'un essai à blanc avant d'appliquer.
- Le miroir et les lieux reposent sur **votre** hiérarchie de mots-clés : réglez les branches dans `config.txt`, et voyez ces deux scripts comme des exemples à adapter.

## Installation

1. Installer [uv](https://docs.astral.sh/uv/) (ou Python 3.11 ou plus). Les scripts n'utilisent que la bibliothèque standard.
2. Mettre les fichiers dans un dossier et lancer une fois `uv run lc_inventory.py` : il crée `config.txt` à partir de `config.example.txt` et s'arrête.
3. Remplir `config.txt` (texte simple, s'ouvre dans le Bloc-notes) : chemin de `lightcraft-cli.exe`, langue, branches de mots-clés, et une bibliothèque et une racine des photos par défaut.
4. Facultatif mais pratique : poser la variable d'environnement `LIGHTCRAFT_CONTROL_PORT=7980` (`setx LIGHTCRAFT_CONTROL_PORT 7980`, puis relancer LightCraft). Les scripts peuvent alors travailler **LightCraft ouvert**.
5. Double-cliquer sur `Launch-GUI.bat`, ou lancer `uv run lc_gui.py`. En haut de la fenêtre, choisir la **bibliothèque** et sa **racine des photos** : la fenêtre retient chaque bibliothèque utilisée, avec sa racine, dans une liste déroulante.

## Comment ils joignent LightCraft

Un seul programme à la fois peut ouvrir une bibliothèque.

- **LightCraft ouvert** (et à l'écoute sur son port de contrôle) : les scripts lui envoient leurs commandes, et on voit les changements en direct. Ils vérifient d'abord que LightCraft a bien ouvert la bibliothèque choisie, et s'arrêtent sinon. Idéal pour les petits traitements. Ne pas se servir de LightCraft pendant qu'un script tourne, et garder sa fenêtre visible.
- **LightCraft fermé** : les scripts ouvrent la bibliothèque eux-mêmes. Plus rapide pour les gros traitements sur toute la bibliothèque.

Le choix est automatique ; la première ligne affichée indique la voie prise (`connection` dans `config.txt` permet de la forcer).

## Appliquer après un essai à blanc

L'essai à blanc du miroir, des lieux, des piles ou des visages sans nom garde la liste exacte des modifications trouvées, avec le compteur de modifications du catalogue. Quand on clique ensuite sur *Appliquer* (ou qu'on lance avec `--apply --use-plan`), le script réutilise cette liste **seulement si le catalogue n'a pas changé du tout depuis** et que les réglages sont les mêmes ; il évite alors de relire chaque photo, ce qui fait gagner des minutes sur une grosse bibliothèque. Si quelque chose a changé entre-temps (une retouche dans LightCraft, un autre script), il le signale et revérifie tout, comme avant.

## Fichiers produits

Les CSV et journaux vont dans le dossier `Output` (réglable), sans jamais s'écraser : `places_plan 2026-11-18 1.csv`, puis `… 2.csv`. Ils sont en UTF-8 avec séparateur `;` et s'ouvrent dans Excel.

## La table des lieux

`places_table.csv` fait correspondre un mot-clé aux quatre champs de lieu :

```
keyword;location;city;state;country
Places|France|Porquerolles;Porquerolles;Hyères;Provence-Alpes-Côte d'Azur;France
Type|Museums|Louvre;Musée du Louvre;Paris;Île-de-France;France
```

Un mot-clé de musée l'emporte sur un mot-clé de lieu (le lieu devient le musée). Les photos dont les mots-clés manquent dans la table sont listées dans `places_to_check.csv` : ajouter des lignes, relancer.

## Traductions

Les textes sont écrits en anglais et traduits par `lang/<code>.json` (`lang/fr.json` est fourni). Pour ajouter une langue : copier `fr.json` en `it.json` par exemple, traduire la partie droite en gardant les `{noms}` entre accolades, et mettre `language = "it"` (ou `"auto"`). Un texte manquant reste en anglais.

## En ligne de commande

```
uv run lc_relink.py                                   # essai à blanc avec les valeurs écrites dans le script
uv run lc_relink.py --FOLDER="D:\Photos\2026\10" --TARGET=all --apply
```

## Licence

MIT. Voir `LICENSE`.
