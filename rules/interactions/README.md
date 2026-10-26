# Drug-drug interactions (DDInter subset)

`ddinter-subset.csv` holds the DDInter 2.0 interaction pairs where both drugs are ingredients in
`rules/terminology/ingredients.json`. It is produced by `scripts/import_ddinter.py` from the files at
https://ddinter2.scbdd.com/download/. The coverage figures for each import are in `ddinter-import-report.json`.

- **Source:** DDInter 2.0, Computational Biology & Drug Design Group.
- **Licence:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0).
  This subset is shared under the same licence.
- **Changes made:** rows were filtered to our ingredients, and DDInter's international names were replaced
  with the ingredient names used in this project (for example acetylsalicylic acid becomes aspirin, and
  acetaminophen becomes paracetamol). Each pair is stored once. The severity level is unchanged.
- **Disclaimer (from DDInter):** DDInter cannot guarantee accuracy or completeness, and the absence of an
  interaction does not mean that no interaction exists.
- **Use:** final year project, non-commercial. A real deployment needs a licensed source or written permission.
