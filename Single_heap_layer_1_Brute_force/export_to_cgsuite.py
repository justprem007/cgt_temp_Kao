"""
Getting mean and temperature from CGSuite requires two steps

export_to_cgsuite.py  (Part 1 of 2)

Read the Excel file of random games, pull the `seed` and `curly` columns, and
write a CGScript batch block to a .txt file.

HOW TO USE
----------
Step 1 (here):
    Just run this file:   python export_to_cgsuite.py
    It reads the Excel file named below (XLSX_NAME), pulls the `seed` and
    `curly` columns, and writes a CGScript batch block to a text file
    (TXT_NAME, default "cgsuite_input.txt").

Step 2 (in CGSuite):
    Open that text file, select ALL of it, copy it, paste it into the CGSuite
    Worksheet, and press Enter. 

    Select that output, copy it, and paste it into "cgsuite_output.txt" for the
    next script (cgsuite_to_excel.py; part 2 of 2) to read.

Settings (which Excel file, which columns, the output name) are in the CONFIG
block below.

Requires pandas and openpyxl.
"""

import os
import sys

import pandas as pd


# ===========================================================================
# CONFIG — edit here
# ===========================================================================
XLSX_NAME     = "random_heapgo_games.xlsx"   # Excel file to read
TXT_NAME      = "cgsuite_input.txt"          # CGScript file to write

SEED_COL      = "seed"                       # column holding the seed
CURLY_COL     = "curly"                      # column holding the {L | R} game
SHEET         = 0                            # sheet name, or 0 for the first one
INCLUDE_APPLY = True                         # add the .Apply(...) line at the end

# Both files live next to THIS script, not in whatever directory you happen to
# run Python from.
_HERE     = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(_HERE, XLSX_NAME)
TXT_PATH  = os.path.join(_HERE, TXT_NAME)


# ===========================================================================
def build_script(df, include_apply=True):
    """Turn the (seed, curly) rows into a CGScript batch block."""
    lines = [
        "// Auto-generated CGScript batch block.",
        "// Paste into the CGSuite Worksheet and press Enter.",
        "",
        "data := [",
    ]
    n = len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        seed = int(row[SEED_COL])
        game = str(row[CURLY_COL]).strip()
        comma = "," if i < n - 1 else ""
        lines.append(f"  [{seed}, {game}]{comma}")
    lines.append("];")

    if include_apply:
        lines.append("")
        lines.append(
            'data.Apply(row -> row[1].ToString + "," + '
            'row[2].Mean.ToString + "," + row[2].Temperature.ToString)'
        )
    return "\n".join(lines) + "\n"


def main():
    print(f"Reading  {XLSX_PATH}")
    try:
        df = pd.read_excel(XLSX_PATH, sheet_name=SHEET)
    except Exception as e:
        sys.exit(f"ERROR reading '{XLSX_PATH}': {e}")

    for col in (SEED_COL, CURLY_COL):
        if col not in df.columns:
            sys.exit(f"ERROR: column '{col}' not found. Columns are: {list(df.columns)}")

    sub = df[[SEED_COL, CURLY_COL]].dropna()
    if len(sub) == 0:
        sys.exit("ERROR: no rows with both a seed and a curly game.")

    script = build_script(sub, include_apply=INCLUDE_APPLY)
    with open(TXT_PATH, "w") as f:
        f.write(script)

    print(f"Wrote    {TXT_PATH}  ({len(sub)} games)")
    print("Open it, copy everything, paste into the CGSuite Worksheet, press Enter.")


if __name__ == "__main__":
    main()