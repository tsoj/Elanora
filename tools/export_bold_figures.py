"""Export the bold figures for hand editing:

    manual/figures-bold-roman.ufo    manual/figures-bold-italic.ufo

Edit the lining (0-9) and oldstyle (.osf) figures there (move points only), save as UFO, and
rebuild. Tabular, numerator, denominator, superior and inferior figures follow automatically.
Existing files are not overwritten unless --force is given.
"""
import os, subprocess, sys

force = "--force" in sys.argv
os.makedirs("manual", exist_ok=True)
for style in ("roman", "italic"):
    path = f"manual/figures-bold-{style}.ufo"
    if os.path.exists(path) and not force:
        print("keeping", path, "(use --force to overwrite)")
        continue
    env = dict(os.environ, ELANORA_DUMP_FIGS="manual")
    subprocess.run([sys.executable, "build_font.py", style], env=env, check=True, stdout=subprocess.DEVNULL)
    print("wrote", path)
