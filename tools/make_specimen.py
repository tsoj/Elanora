"""Fill the specimen template with the current web fonts (base64) -> specimen HTML."""
import base64, shutil, sys
from pathlib import Path

spec = Path(sys.argv[1])  # directory holding template.html and the reference woff2 files
fonts = {
    "elanor-r": "dist/fonts/webfonts/Elanor[wght].woff2",
    "elanor-i": "dist/fonts/webfonts/Elanor-Italic[wght].woff2",
}
for k, src in fonts.items():
    shutil.copy(src, spec / f"{k}.woff2")
t = (spec / "template.html").read_text()
for k in ("elanor-r", "elanor-i", "lora-r", "lora-i", "bryg-r", "bryg-i"):
    t = t.replace("{{%s}}" % k, base64.b64encode((spec / f"{k}.woff2").read_bytes()).decode())
assert "{{" not in t
(spec / "elanor-specimen.html").write_text(t)
shutil.copy(spec / "elanor-specimen.html", "dist/specimen.html")
print("ok", len(t))
