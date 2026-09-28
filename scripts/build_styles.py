"""Compile le SCSS de l'interface (pip install -r requirements-dev.txt)."""
from pathlib import Path
import sass

root = Path(__file__).resolve().parents[1]
source = root / "projects/static/projects/manage.scss"
source.with_suffix(".css").write_text(
    "/* Généré depuis manage.scss : python scripts/build_styles.py */\n"
    + sass.compile(filename=str(source), output_style="expanded"), encoding="utf-8",
)
