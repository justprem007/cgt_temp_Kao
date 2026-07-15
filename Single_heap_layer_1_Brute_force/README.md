# Brute-Force Mean and Temperature

Kao's algorithm for the **mean** and **temperature** of a combinatorial game:
build the whole game tree and work out each node's value bottom-up. 

## Install
 
Python 3. The core runs on the standard library alone.
 
Other packages are needed for additional purposes:
 
1) treelib (`heapgo_to_tree.py`): required for visualization of the tree
2) openpyxl (`generate_random_games.py` and `cgsuite_to_excel.py`): required for generating and editing the Excel file
3) pandas (`export_to_cgsuite.py` and `cgsuite_to_excel.py`): required for reading the Excel file

## Run it

Open `main.py`, set your game near the top of `main()`, and run:

```bash
python main.py 
```
in a terminal or directly hit the Run button in `main.py`.

You can give the game in three forms — `main.py` figures out which:

```python
G = [(2, 'red'), (3, 'red'), (5, 'blue')]   # a Heapgo heap (single heap)
G = "{11 | {8 | 0}}"                         # CGSuite notation
G = [11, [8, 0]]                             # nested list
```

Set `VERBOSE` / `TRACE` in `main()` for more detail (one line per node, or the
full step-by-step). Long output can be saved with `python main.py > output.txt` or `python -X utf8 main.py > output.txt`.

## Visualization of the tree structure of the Heapgo game

In `heapgo_to_tree.py`, write the Heapgo game at the bottom and run the file; it
prints the game tree in ASCII format in the terminal.

## The files

**The pipeline** — `main.py` runs the code:

- `main.py` — entry point. Detects the input format, validates it, converts it
  to a nested list, runs the solver, and prints the mean and temperature of the game along with the timings to convert the game to a nested list and to get the mean and temperature from the nested list.
- `validate.py` — the place where the input game format is checked. `main.py` calls it before
  anything else, so every other file can assume its input is already valid.
- `heapgo.py` — the Heapgo rules for a single heap.
- `heapgo_to_tree.py` — expands a Heapgo heap into a nested-list game tree.
- `brute_force.py` — from a nested-list game, it builds the tree and computes mean/temperature bottom-up.
- `stable_pair.py` — Kao's stable-pair theorem, applied at each node while determining mean and temperature. Also defines `ColdGameError` (raised when a game is cold).
So the flow is: **input -> validate -> (heapgo_to_tree, or straight through) ->
brute_force -> stable_pair.**
 
**Testing** (independent of a single run):

- `generate_random_games.py` — makes random Heapgo games, converts them into nested lists via `heapgo_to_tree.py`, then calculates mean and temperature via `brute_force.py` and `stable_pair.py`. Then it writes them to an Excel file (one game per row, reproducible from its seed). The Excel file contains: seed, the Heapgo game, its curly-form game format, mean, temperature, the time taken to convert the Heapgo game to a nested list, and the time taken for the nested-list game to get the mean and temperature via the brute-force method.
- `export_to_cgsuite.py` and `cgsuite_to_excel.py` — a two-step bridge to get the CGSuite result for testing. Run `export_to_cgsuite.py`; it generates a CGSuite script `cgsuite_input.txt` from the Excel file generated via `generate_random_games.py`. Copy the whole content of `cgsuite_input.txt` and paste it into the CGSuite Worksheet. Run it and you will get the output. Copy that output and paste it into `cgsuite_output.txt`. Then run `cgsuite_to_excel.py`. It matches each game by seed and inserts extra columns for the CGSuite mean and temperature, then compares them (green = match, red = mismatch).
