"""Export the bold a for hand editing, for both approaches:

    manual/a-bold-brygada.ufo    Brygada's own bold a (current Elanora)
    manual/a-bold-transfer.ufo   Elanora Regular a + Lora's Regular->Bold movement

Edit glyph 'a' in either file (move points only), then choose the approach with BOLD_A_MODE in
build_font.py (or ELANORA_BOLD_A=transfer) and rebuild. Existing files are not overwritten unless
--force is given.
"""
import os, subprocess, sys

force = "--force" in sys.argv
os.makedirs("manual", exist_ok=True)
for mode in ("brygada", "transfer"):
    path = f"manual/a-bold-{mode}.ufo"
    if os.path.exists(path) and not force:
        print("keeping", path, "(use --force to overwrite)")
        continue
    env = dict(os.environ, ELANORA_BOLD_A=mode, ELANORA_DUMP_A=path)
    subprocess.run([sys.executable, "build_font.py", "roman"], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    print("wrote", path)
