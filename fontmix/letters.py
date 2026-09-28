"""Brygada letter features the user asked for, worked into the Lora-based roman."""
from .transplant import match_weight, transplant, reanchor, rebuild_accented
from .tweaks import slant_terminals, stretch_top, q_with_brygada_tail

LC = 500 / 460  # Brygada x-height -> Elanor
UC = 700 / 670  # Brygada cap height -> Elanor
# t's ascender: 85% of the way from Lora's t to Brygada's, measured as the position between
# x-height and ascender (Lora 55%, Brygada 76% -> 73%; Brygada's ascenders are taller than
# Lora's, so absolute heights would overshoot): 500 + 0.73 * (755 - 500) = 686.
# Then raised by 5% of the remaining distance to Lora's t (640): 686 + 0.05 * (686 - 640) = 688
T_TOP = 688
Z_SLANT = 12.5  # degrees, measured on Brygada's z


def stage_brygada_letters(M, bry, log=None):
    wl = {w: match_weight(M[w], bry, "n", 250, LC) for w in M}
    wu = {w: match_weight(M[w], bry, "H", 200, UC) for w in M}
    if log is not None:
        log.append(("brygada-weights", {"lowercase": wl, "caps": wu}))
    for g in ("a", "ae", "ordfeminine", "s"):
        info = transplant(M, bry, g, scale=LC, weights=wl)
        reanchor(M, g, info)
        rebuild_accented(M, g)
    for g in ("z",):
        info = transplant(M, bry, g, scale=LC, weights=wl)
        reanchor(M, g, info)
        rebuild_accented(M, g)
    for g in ("S", "Z"):
        info = transplant(M, bry, g, scale=UC, weights=wu)
        reanchor(M, g, info)
        rebuild_accented(M, g, case=True)
    q_with_brygada_tail(M, bry, wu, UC)
    # taller t
    for g in ("t", "tcaron", "tbar"):
        stretch_top(M, g, 505, T_TOP, xmax={w: 250 if w == 400 else 275 for w in M})
    return wl, wu


def italic_tall_t(M, top=T_TOP):
    """The italic t gets the same taller ascender as the roman, stretched along the slant."""
    import math
    angle = M[400]["post"].italicAngle
    shear = math.tan(math.radians(-angle))
    stretch_top(M, "t", 505, top, shear=shear)
