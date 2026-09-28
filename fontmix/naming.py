"""Family naming / metadata for the derived font."""
FAMILY = "Elanora"
PS_FAMILY = "Elanora"
VERSION = "1.000"
YEAR = 2026

COPYRIGHT = (
    'Copyright 2011 The Lora Project Authors (https://github.com/cyrealtype/Lora-Cyrillic), '
    'with Reserved Font Name "Lora". '
    "Copyright 2020 The Brygada 1918 Project Authors (https://github.com/kosmynkab/Brygada-1918)."
)
DESIGNER = (
    f"{FAMILY}: derived from Lora (Olga Karpushina, Alexei Vanyashin / Cyreal) and "
    "Brygada 1918 (Mateusz Machalski, Borys Kosmynka, Przemek Hoffer)"
)
DESCRIPTION = (
    f"{FAMILY} is a text serif built on Lora's skeleton, wedge serifs, ligatures and italic, "
    "reshaped with the round ball terminals, wider circular counters and figures of Brygada 1918."
)
LICENSE = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at: https://openfontlicense.org"
)
LICENSE_URL = "https://openfontlicense.org"


def rename_vf(font, italic):
    name = font["name"]
    style = "Italic" if italic else "Regular"
    ps_style = "Italic" if italic else "Regular"
    recs = {
        0: COPYRIGHT,
        1: FAMILY,
        2: style,
        3: f"{VERSION};NONE;{PS_FAMILY}-{ps_style}",
        4: f"{FAMILY} {style}",
        5: f"Version {VERSION}",
        6: f"{PS_FAMILY}-{ps_style}",
        9: DESIGNER,
        10: DESCRIPTION,
        13: LICENSE,
        14: LICENSE_URL,
        25: PS_FAMILY + ("Italic" if italic else ""),
    }
    for nid in (7, 8, 11, 12, 16, 17):
        name.removeNames(nameID=nid)
    for nid, s in recs.items():
        name.removeNames(nameID=nid)
        name.setName(s, nid, 3, 1, 0x409)
    # the reserved font name must not appear in any naming field (credits are fine)
    for r in name.names:
        if (r.nameID in (1, 3, 4, 6, 16, 17, 18, 21, 22, 25) or r.nameID >= 256) and "Lora" in r.toUnicode():
            raise ValueError(f"reserved name left in name ID {r.nameID}: {r.toUnicode()}")
    font["OS/2"].achVendID = "NONE"
    font["head"].fontRevision = float(VERSION)
