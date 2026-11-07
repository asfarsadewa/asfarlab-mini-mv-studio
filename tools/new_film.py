# Starts a new film folder from the template. An existing film is kept.
# Usage: python tools/new_film.py <id> "<title>"
import json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if len(sys.argv) < 3:
    sys.exit('Usage: python tools/new_film.py <id> "<title>"')
film, title = sys.argv[1], sys.argv[2]
out = ROOT / "mvs" / film
if out.exists():
    sys.exit(f"{out} exists.")
shutil.copytree(ROOT / "templates/film", out)
path = out / "brief.json"
brief = json.loads(path.read_text(encoding="utf-8"))
brief.update(id=film, title=title)
path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {out}. Follow docs/PRODUCTION.md from step 1.")
