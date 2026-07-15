# Brute-Force Mean and Temperature

Kao's algorithm for the **mean** and **temperature** of a combinatorial game,
done the simple way: build the whole game tree, evaluate it bottom-up. Slow but
easy to check by hand — it's the reference the faster incremental version is
tested against.

## Run it

Set your game near the top of `main()` in `main.py`, then:

```bash
python main.py
```

```
FINAL RESULT:  Mean = 1.0 ,  Temperature = 7.0
```

## Input

Three formats, auto-detected:

```python
G = [(2, 'red'), (3, 'red'), (5, 'blue')]   # Heapgo heap (single heap only)
G = "{11 | {8 | 0}}"                         # CGSuite notation
G = [11, [8, 0]]                             # nested list
```

## Files

| | |
|---|---|
| `main.py` | entry point — validate, convert, solve |
| `validate.py` | the only file that checks input |
| `heapgo.py` | Heapgo rules |
| `heapgo_to_tree.py` | heap → nested list |
| `brute_force.py` | the search |
| `stable_pair.py` | Kao's stable theorem |
| `generate_random_games.py` | random games → Excel |
| `thermo_oracle.py` | independent check (thermographs) |

## Notes

- Kao's algorithm is for **hot** games. A cold position raises `ColdGameError`.
- A terminal has temperature **0** here. Classical thermography gives a number
  temperature −1 — worth knowing when comparing.
- Results can be cross-checked against `thermo_oracle.py` or CGSuite, both of
  which compute mean/temperature a completely different way.

Python 3, standard library only (`generate_random_games.py` needs `openpyxl`).
