# Restore Target Tree

`tools/restore_tree.py` reads a canonical allowlist (`data/target_tree_allowlist.txt`) and compares it against the current repository state. It reports:

- Missing files/directories that must be restored.
- Extra files/directories that are not on the allowlist.
- Optional apply mode that quarantines extras and restores missing entries (using `git restore` or reconstruction).

## Allowlist

1. Populate `data/target_tree_allowlist.txt` with one repository-relative path per line.
2. Absolute paths must be rooted at `D:\francis\`.
3. Blank lines and `#` comments are ignored.
4. The tool refuses to run (even in dry-run) until this file contains the exact inventory to enforce.

## Usage

- Dry-run (default): `python tools/restore_tree.py`. This only reports differences and writes reports to `data/logs/operations/restore_tree_report_<timestamp>.*`.
- Apply mode: `python tools/restore_tree.py --apply --yes`. Extras are moved to `data/quarantine/restore_<timestamp>` and missing items are restored or recreated.
- For convenience use the wrapper: `.\scripts\restore-target-tree.ps1` (dry-run) or `.\scripts\restore-target-tree.ps1 -Apply -Yes`.

## Quarantine & Reports

- Extras are moved under `data/quarantine/restore_<timestamp>/`.
- Reports (text + JSON) live in `data/logs/operations/restore_tree_report_<timestamp>.*`.

## Restoring from Quarantine

Restore individual items by copying them out of the quarantine directory. The tool never removes quarantine contents automatically; you may replay the restoration manually if needed.
