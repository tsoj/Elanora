"""Export bold glyphs for hand editing, e.g.

    uv run python tools/export_bold_glyphs.py manual/JQy-bold.ufo J,Q,y [--force]
    uv run python tools/export_bold_glyphs.py manual/f-bold.ufo f [--force]

Edit the glyphs in the UFO (move points only), save over the same file, rebuild. The file must be
listed in MANUAL_GLYPHS in build_font.py. An existing file is not overwritten without --force."""
import os, subprocess, sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
path, names = args
if os.path.exists(path) and "--force" not in sys.argv:
    sys.exit(f"keeping {path} (use --force to overwrite)")
subprocess.run([sys.executable, "build_font.py", "roman"],
               env=dict(os.environ, ELANORA_DUMP_GLYPHS=f"{path}:{names}"), check=True, stdout=subprocess.DEVNULL)
print("wrote", path)
