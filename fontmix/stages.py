"""Design stages applied to a dict of point-compatible masters {400: TTFont, 700: TTFont}."""
import math

import numpy as np

from .balls import ball_terminal, ball_terminal_v2
from .geom import explicitize, glyph_contours, sample, set_glyph_contours
from .propagate import propagate
from .widen import Field, apply_field, auto_zones


def stage_widen(M, spec):
    """spec: {glyph: dict(y=.., d={400:[..],700:[..]}, m=[(l,r),..]) or dict(zones={400:[(xa,xb,d)],..})}"""
    fields = {w: {} for w in M}
    for name, sp in spec.items():
        for w, f in M.items():
            if "zones" in sp:
                zs = sp["zones"][w]
            elif sp.get("span"):
                from .widen import ink_runs
                runs = ink_runs(glyph_contours(f["glyf"], name), sp["y"])
                (ml, mr), = sp["m"]
                zs = [(runs[0][1] + ml, runs[-1][0] - mr, sp["d"][w][0])]
            else:
                zs, _ = auto_zones(glyph_contours(f["glyf"], name), sp["y"], sp["d"][w], sp["m"])
            fld = Field(zs)
            apply_field(f["glyf"], f["hmtx"], name, fld)
            fields[w][name] = fld
    eff = {w: propagate(M[w], fields[w]) for w in M}
    return eff


def _nearest_contour(cs, D):
    best, bi = None, 0
    for i, c in enumerate(cs):
        pts = sample(c, 8)
        d = np.min(np.hypot(pts[:, 0] - D[0], pts[:, 1] - D[1]))
        if best is None or d < best:
            best, bi = d, i
    return bi


def stage_balls(M, spec, fields=None, log=None):
    """spec: {glyph: [dict(D=(x,y), R=60, r={400:54,700:76}, out=0.6, shift=(0,0)), ...]}
    D is in original (pre-widening) coordinates of the first master."""
    keys = list(M)
    for name, terms in spec.items():
        CS = {w: glyph_contours(M[w]["glyf"], name) for w in keys}
        for t in terms:
            D = t["D"]
            if fields and name in fields[keys[0]]:
                D = (D[0] + fields[keys[0]][name].dx(D[0], D[1]), D[1])
            ci = t.get("ci", _nearest_contour(CS[keys[0]], D))
            others = {w: [c for j, c in enumerate(CS[w]) if j != ci] for w in keys}
            if t.get("v", 2) == 2:
                new, info = ball_terminal_v2(
                    {w: explicitize(CS[w][ci]) for w in keys}, D, t.get("R", 60), t["r"],
                    hang=t.get("hang", 0.0), shift=t.get("shift", (0, 0)), others=others,
                    run_k=t.get("run_k", 1.25))
            else:
                new, info = ball_terminal(
                    {w: explicitize(CS[w][ci]) for w in keys}, D, t.get("R", 60),
                    rtarget=t.get("r"), out_shift=t.get("out", 0.6), shift=t.get("shift", (0, 0)),
                    others=others, run_k=t.get("run_k", 1.25))
            for w in keys:
                CS[w][ci] = new[w]
            if log is not None:
                log.append((name, {w: info[w]["circle"] for w in keys}))
        for w in keys:
            set_glyph_contours(M[w]["glyf"], name, CS[w])
            adv = M[w]["hmtx"][name][0]
            M[w]["hmtx"][name] = (adv, M[w]["glyf"][name].xMin)
