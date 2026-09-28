"""Transplant Brygada figures into the Lora-based masters (scaled, weight-matched, re-slanted)."""
import math

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from .geom import set_glyph_contours

FIGS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def brygada_contours(font, name, scale, dx=0.0, dy=0.0, shear=0.0):
    glyf = font["glyf"]
    coords, ends, flags = glyf[name].getCoordinates(glyf)
    out, s = [], 0
    for e in ends:
        c = []
        for i in range(s, e + 1):
            x, y = coords[i]
            x, y = x * scale, y * scale
            c.append([x + shear * y + dx, y + dy, flags[i] & 1])
        out.append(c)
        s = e + 1
    return out


def stage_figures(M, bry_path, bry_weights, scale=1.05, tab_width=650, sup_dy=-40, shear=0.0, emb=None):
    """M: {400: TTFont, 700: TTFont}; bry_weights: {400: user wght in Brygada, 700: ...}"""
    for w, f in M.items():
        B = instancer.instantiateVariableFont(TTFont(bry_path), {"wght": bry_weights[w]})
        glyf, hmtx = f["glyf"], f["hmtx"]
        old_adv = {n: hmtx[n][0] for n in ("uni00B9", "uni00B2", "uni00B3", "uni2074")}
        jobs = [(n, n, None, 0) for n in FIGS]
        jobs += [(n + ".tf", n + ".tf", tab_width, 0) for n in FIGS]
        jobs += [(n, n, None, sup_dy) for n in ("uni00B9", "uni00B2", "uni00B3", "uni2074")]
        for tgt, src, fixed, dy in jobs:
            d = (emb or {}).get(w, 0) * (0.6 if tgt.startswith("uni") else 1.0)
            cs, d = figure_contours(bry_path, bry_weights, w, src, scale, dy, shear, d, fallback=648)
            set_glyph_contours(glyf, tgt, cs)
            g = glyf[tgt]
            adv = round(B["hmtx"][src][0] * scale + 2 * d)
            if fixed:
                # centre the tabular figure
                ink = g.xMax - g.xMin
                bl, br = g.xMin, adv - g.xMax
                shift = round((fixed - adv) / 2)
                for c in cs:
                    for p in c:
                        p[0] += shift
                set_glyph_contours(glyf, tgt, cs)
                adv = fixed
            hmtx[tgt] = (adv, glyf[tgt].xMin)
        # re-lay Lora's fraction composites
        for name in ("onehalf", "onequarter", "threequarters"):
            g = glyf[name]
            num, frac, den = g.components
            d = hmtx[num.glyphName][0] - old_adv[num.glyphName]
            frac.x += d
            den.x += d
            dd = hmtx[den.glyphName][0] - old_adv[den.glyphName]
            g.recalcBounds(glyf)
            hmtx[name] = (hmtx[name][0] + d + dd, g.xMin)


_UNTANGLE = {}
UNION_FIGS = {"two", "three", "four", "five", "six", "nine"}


def _self_intersects(cs):
    """True only if some single contour crosses itself (separate overlapping pieces are fine)."""
    import pathops
    from .geom import explicitize
    for c in cs:
        p = pathops.Path()
        pen = p.getPen()
        ec = explicitize(c)
        pen.moveTo(tuple(ec[0][:2]))
        i, n = 1, len(ec)
        while i <= n:
            q = ec[i % n]
            if q[2]:
                pen.lineTo(tuple(q[:2])); i += 1
            else:
                pen.qCurveTo(tuple(q[:2]), tuple(ec[(i + 1) % n][:2])); i += 2
        pen.closePath()
        a0, n0 = abs(p.area), len(list(p.contours))
        p.simplify(fix_winding=True)
        if abs(abs(p.area) - a0) > 2 or len(list(p.contours)) != n0:
            return True
    return False


def _compatible(css):
    vals = list(css.values())
    sig = lambda cs: [tuple(p[2] for p in c) for c in cs]
    return all(sig(v) == sig(vals[0]) for v in vals)


def _clean_thickening(reg, bold):
    """The thickened outline must keep the regular's topology (same number of pieces after
    removing overlaps) - otherwise the offset folded over itself somewhere."""
    from .geom import pathops_contours
    try:
        return len(pathops_contours(reg)) == len(pathops_contours(bold))
    except Exception:
        return False


def figure_contours(bry_path, weights, w, src, scale, dy, shear, d, fallback=None):
    """Brygada figure outline for master w, thickened by d. Self-crossing outlines (Brygada's 8)
    are untangled first, identically in every master; if that breaks compatibility, the glyph
    is not thickened and (for the bold master) taken from `fallback` weight instead."""
    from .transplant import bry_instance
    from .geom import canonical, embolden, pathops_contours, explicitize
    key = (bry_path, src, scale, dy, shear, tuple(sorted(weights.items())))
    if key not in _UNTANGLE:
        raw = {m: brygada_contours(bry_instance(bry_path, weights[m]), src, scale, 0, dy, shear) for m in weights}
        first = sorted(weights)[0]
        ok, use = True, raw
        if False and _self_intersects(raw[first]):  # ink-aware thickening handles self-crossings
            try:
                simp = {m: canonical(pathops_contours(raw[m])) for m in raw}
                if _compatible(simp):
                    use = simp
                else:
                    ok = False
            except ValueError:
                ok = False
        _UNTANGLE[key] = (use, ok)
    use, ok = _UNTANGLE[key]
    base = src.split(".")[0]
    if base == "eight" and "Italic" in bry_path:
        # Brygada's italic 8 is one self-crossing contour and its own bold keeps a hairline
        # diagonal: merge it into outer + counters, and derive the bold by thickening that same
        # outline (Brygada's 400 -> 500 growth, measured as area gained per unit of outline,
        # plus d), so both masters stay point-compatible and the 8 matches the other figures
        first = sorted(weights)[0]
        ekey = ("eight-union",) + key
        if ekey not in _UNTANGLE:
            import numpy as np
            from .geom import sample, signed_area
            reg_u = [explicitize(c) for c in canonical(pathops_contours(use[first]))]
            others = [m for m in weights if m != first]
            grow = {}
            for m in others:
                big = canonical(pathops_contours(use[m]))
                area = lambda cs: abs(sum(signed_area(c) for c in cs))
                perim = sum(float(np.hypot(*np.diff(np.vstack([s, s[:1]]), axis=0).T).sum())
                            for s in (sample(c, 12) for c in reg_u))
                grow[m] = (area(big) - area(reg_u)) / perim
            _UNTANGLE[ekey] = (reg_u, grow)
        reg_u, grow = _UNTANGLE[ekey]
        if w == first:
            return [[list(p) for p in c] for c in reg_u], 0
        g = grow.get(w, 0.0) + d
        cs = [[[p[0] + g, p[1], p[2]] for p in c] for c in embolden(reg_u, g)]
        return [explicitize(c) for c in cs], g
    if base in UNION_FIGS:
        first = sorted(weights)[0]
        ukey = ("union",) + key
        if ukey not in _UNTANGLE:
            try:
                reg_u = [explicitize(c) for c in canonical(pathops_contours(use[first]))]
                _UNTANGLE[ukey] = reg_u
            except Exception:
                _UNTANGLE[ukey] = None
        reg_u = _UNTANGLE[ukey]
        if reg_u is not None:
            if w == first or not d:
                return [[list(p) for p in c] for c in reg_u], 0
            from .boldxfer import transfer_glyph
            emb = [[[p[0] + d, p[1], p[2]] for p in c] for c in embolden(use[w], d)]
            # carry the regular -> bold movement of Brygada's pieces over to the merged outline
            ref_reg = [[list(p) for p in c] for c in use[first]]
            if len(ref_reg) == len(emb) and all(len(a) == len(b) for a, b in zip(ref_reg, emb)):
                bold = transfer_glyph(reg_u, ref_reg, emb, mode="nearest", smooth_passes=1)
                return bold, d
    if d and ok:
        cs = [[[p[0] + d, p[1], p[2]] for p in c] for c in embolden(use[w], d)]
        if _clean_thickening(use[sorted(weights)[0]], cs):
            from .tweaks import fix_touch_points
            reg_shift = [[[p[0] + d, p[1], p[2]] for p in c] for c in use[w]]
            _, cs = fix_touch_points(reg_shift, cs)
            return cs, d
        # ink test ambiguous (e.g. Brygada's italic 8): try untangling this glyph
        try:
            simp = {m: canonical(pathops_contours(use[m])) for m in use}
            if _compatible(simp):
                cs = [[[p[0] + d, p[1], p[2]] for p in c] for c in embolden(simp[w], d, ink_aware=False)]
                if _clean_thickening(simp[sorted(weights)[0]], cs):
                    _UNTANGLE[key] = (simp, True)
                    return cs, d
        except ValueError:
            pass
        _UNTANGLE[key] = (use, False)
    from .geom import explicitize
    if d and fallback:
        return [explicitize(c) for c in brygada_contours(bry_instance(bry_path, fallback), src, scale, 0, dy, shear)], 0
    return [explicitize([list(p) for p in c]) for c in use[w]], 0
