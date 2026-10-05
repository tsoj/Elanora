"""Export the bold f for hand editing: manual/f-bold.ufo (regular f in the background layer,
Lora Bold's f as a grey reference). Edit glyph 'f' (move points only), then rebuild; the build
reads the file back. An existing file is not overwritten unless --force is given."""
import os, subprocess, sys

path = "manual/f-bold.ufo"
if os.path.exists(path) and "--force" not in sys.argv:
    sys.exit(f"keeping {path} (use --force to overwrite)")
os.makedirs("manual", exist_ok=True)
subprocess.run([sys.executable, "build_font.py", "roman"], env=dict(os.environ, ELANORA_DUMP_F=path),
               check=True, stdout=subprocess.DEVNULL)
print("wrote", path)
