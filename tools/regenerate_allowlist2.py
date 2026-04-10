from pathlib import Path
import os

root = Path("C:/Francis").resolve()
skip_roots = [root / "data" / "logs" / "operations", root / "data" / "quarantine", root / ".ruff_cache"]
skip_files = {root / "tools" / "regenerate_allowlist2.py", root / "tools" / "append_stub_comments.py"}
entries = set()
for dirpath, dirnames, filenames in os.walk(root):
    path = Path(dirpath)
    if any(path == skip or skip in path.parents for skip in skip_roots):
        dirnames[:] = []
        continue
    entries.add(str(path))
    clean_dirs = []
    for d in dirnames:
        candidate = path / d
        rel = candidate.relative_to(root)
        if ".vite" in rel.parts:
            continue
        clean_dirs.append(d)
    dirnames[:] = clean_dirs
    for fname in filenames:
        candidate = path / fname
        if candidate in skip_files:
            continue
        rel = candidate.relative_to(root)
        if ".vite" in rel.parts:
            continue
        entries.add(str(candidate))
for stub in [
    "src/francis/agent/local_actions.py",
    "src/francis/api/routes/domain_learner.py",
    "src/francis/api/routes/supervised_exec.py",
    "src/francis/kernel/services.py",
    "src/francis/kernel/stack.py",
]:
    candidate = root / stub
    if candidate.exists():
        entries.add(str(candidate))
with open("data/target_tree_allowlist.txt", "w", encoding="utf-8", newline="\n") as handle:
    for entry in sorted(entries):
        handle.write(str(Path(entry).as_posix().replace("/", "\\")) + "\n")
