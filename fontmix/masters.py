from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

def load_masters(vf_path, locs=(400, 700)):
    vf = TTFont(vf_path)
    return {w: instancer.instantiateVariableFont(TTFont(vf_path), {"wght": w}) for w in locs}
