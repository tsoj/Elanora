"""Try ball parameter variants on the roman masters and plot them next to Brygada."""
import sys, copy, json; sys.path.insert(0,"."); sys.path.insert(0,"tools")
from fontmix.masters import load_masters
from fontmix.stages import stage_widen, stage_balls
from fontmix import spec_roman as S
from cmpplot import cmp_plot
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontmix.geom import glyph_contours, set_glyph_contours
import numpy as np

def run(variants, names, out, w=400, crops=None):
    base = load_masters("src/lora_Lora[wght].ttf")
    fields = stage_widen(base, S.WIDEN)
    B = instancer.instantiateVariableFont(TTFont("src/brygada1918_Brygada1918[wght].ttf"), {"wght": 400 if w == 400 else 659})
    # scale brygada into a scratch glyf for plotting
    sc = 500 / 460
    pairs = []
    for vi, var in enumerate(variants):
        M = copy.deepcopy(base)
        spec = {n: [dict(t, **var.get(n, {})) for t in S.BALLS[n]] for n in names}
        stage_balls(M, spec, fields)
        for n in names:
            pairs.append((f"v{vi}", M[w]['glyf'], M[w]['glyf'], n, crops[n]))
    cmp_plot(pairs, out, cell=300, cols=len(names), show_points=False)
