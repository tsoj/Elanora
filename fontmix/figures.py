"""Transplant Brygada figures into the Lora-based masters (scaled, weight-matched, re-slanted)."""
import math
import numpy as np

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
# bold figures: each point of the regular figure moves outward by Lora's own Regular->Bold growth
# for a stroke of that width (hairlines and stems each grow like Lora's), see contrast_figure
CONTRAST_BOLD = True
FIG_PIECES = False  # keep overlapping pieces apart (tried; freezes visible parts)
FIG_SAFETY = False  # handle-outlier smoothing (superseded by split_creases)
_GROWTH = {}
_SMALL = ("numr", "dnom", "sups", "subs", "sinf")


def lora_growth(italic):
    """Stroke growth (bold width - regular width) as a function of regular width, learned from
    Lora's figures (its two masters are point-compatible, so every point is one sample)."""
    if italic not in _GROWTH:
        from fontTools.varLib import instancer
        from .geom import glyph_contours, stroke_widths
        path = "src/lora_Lora-Italic[wght].ttf" if italic else "src/lora_Lora[wght].ttf"
        L = {w: instancer.instantiateVariableFont(TTFont(path), {"wght": w}) for w in (400, 700)}
        A, B = [], []
        for g in FIGS:
            for a, b in zip(stroke_widths(glyph_contours(L[400]["glyf"], g)),
                            stroke_widths(glyph_contours(L[700]["glyf"], g))):
                A += list(a)
                B += list(b)
        A, B = np.array(A), np.array(B)
        edges = np.quantile(A, np.linspace(0, 1, 9))
        xs, gs = [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (A >= lo) & (A <= hi)
            xs.append(float(np.median(A[m])))
            gs.append(float(np.median(B[m] - A[m])))
        gs = list(np.maximum.accumulate(gs))  # thicker strokes never grow less
        _GROWTH[italic] = (xs, gs)
    return _GROWTH[italic]


def match_tangents(reg, bold):
    """Put every bold handle back on the tangent directions the regular has at its on-curve
    neighbours (what a designer does by hand): a control point between two on-curve points goes
    where the two end tangents meet; one next to a single on-curve point slides onto that point's
    tangent. Removes kinks at smooth points and keeps the approach angles at creases."""
    out = []
    for c, b in zip(reg, bold):
        n = len(c)
        R = np.array([p[:2] for p in c], float)
        Bo = np.array([p[:2] for p in b], float)
        new = [list(p) for p in b]
        crease = set()
        for i in range(n):
            j = (i + 1) % n
            if c[i][2] and c[j][2] and abs(c[i][0] - c[j][0]) < 1e-6 and abs(c[i][1] - c[j][1]) < 1e-6:
                crease |= {i, j}
        for i in range(n):
            if c[i][2]:
                continue
            ons = [j % n for j in (i - 1, i + 1) if c[j % n][2]]
            if not crease.intersection(ons):
                continue  # only the handles next to a (split) crease
            dirs = []
            for j in ons:
                v = R[i] - R[j]
                L = np.hypot(*v)
                if L > 1e-6:
                    dirs.append((j, v / L, L))
            if len(dirs) == 2:
                (j1, u1, L1), (j2, u2, L2) = dirs
                M = np.array([u1, -u2]).T
                if abs(np.linalg.det(M)) > 0.05:
                    s = np.linalg.solve(M, Bo[j2] - Bo[j1])
                    X = Bo[j1] + s[0] * u1
                    if 0.25 * L1 < s[0] < 3 * L1 and 0.25 * L2 < s[1] < 3 * L2:
                        new[i][0], new[i][1] = float(X[0]), float(X[1])
                continue
            for j, u, L in dirs[:1] if len(dirs) == 1 else []:
                tt = max(0.3 * L, float((Bo[i] - Bo[j]) @ u))
                X = Bo[j] + tt * u
                new[i][0], new[i][1] = float(X[0]), float(X[1])
        out.append(new)
    return out


def split_creases(contours, min_turn=35.0):
    """Duplicate every sharp inner corner (crease) into two coincident points. The regular does
    not change; in the bold each copy then follows only its own edge, instead of both edges
    being forced to meet (which spikes or flattens where strokes join at an angle)."""
    out = []
    for c in contours:
        xy = np.array([p[:2] for p in c], float)
        area = 0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1])
        n = len(c)
        new = []
        for i, p in enumerate(c):
            new.append(list(p))
            if not p[2]:
                continue
            v1, v2 = xy[i] - xy[i - 1], xy[(i + 1) % n] - xy[i]
            l1, l2 = np.hypot(*v1), np.hypot(*v2)
            if l1 < 1e-6 or l2 < 1e-6:
                continue
            turn = math.degrees(math.acos(float(np.clip(v1 @ v2 / l1 / l2, -1, 1))))
            concave = (v1[0] * v2[1] - v1[1] * v2[0]) * np.sign(area) < 0
            if concave and turn > min_turn:
                new.append([p[0], p[1], 1])
        out.append(new)
    return out


def contrast_figure(bry_path, weights, w, src, scale, dy, shear, smooth=6):
    """Regular: Brygada's figure with overlaps merged. Bold: the same outline, every point moved
    outward by half of Lora's growth for the stroke width at that point (smoothed along the
    contour), then brought back to the regular's height. Returns (contours, d) where 2*d is the
    added width."""
    from .transplant import bry_instance
    from .geom import canonical, pathops_contours, explicitize, stroke_widths, embolden_var
    first = sorted(weights)[0]
    key = ("contrast", bry_path, src, scale, dy, shear, weights[first])
    if key not in _UNTANGLE:
        raw = brygada_contours(bry_instance(bry_path, weights[first]), src, scale, 0, dy, shear)
        merged = [explicitize(c) for c in canonical(pathops_contours(raw))]
        pieces = [explicitize(c) for c in raw]
        if FIG_PIECES and len(pieces) > len(merged) and not _self_intersects(pieces) and src.split(".")[0] != "one":
            # separate overlapping pieces (a ball on its stroke): keep them apart, so each is
            # thickened on its own and the crease is simply where they overlap
            _UNTANGLE[key] = (pieces, merged)
        else:
            _UNTANGLE[key] = (split_creases(merged), None)
    reg, ink = _UNTANGLE[key]
    if w == first:
        return [[list(p) for p in c] for c in reg], 0
    # Lora's figures, measured on their actual strokes: hairlines 39 -> 71 (+32), stems
    # 88 -> 144 and 103 -> 152 (about +52); linear in between, held flat outside
    xs, gs = [39.0, 95.0], [32.0, 52.0]
    ys = [p[1] for c in reg for p in c]
    # small figures (superiors, numerators...): Lora's growth scaled to their size
    k = 1.0
    if any(s in src for s in _SMALL) or src.startswith("uni"):
        k = (max(ys) - min(ys)) / (716.0 * scale / 1.05)
    from .geom import edge_widths, offset_edges
    deltas = []
    for c, wd in zip(reg, edge_widths(reg, ink=ink)):
        d = np.array([0.5 * k * float(np.interp(v / k, xs, gs)) for v in wd])
        # smooth the offsets along each run of smoothly connected curve (never across a crease
        # or a real corner), so a curve's offset changes gradually and its points stay on it
        n = len(c)
        xy = np.array([p[:2] for p in c], float)
        joint = np.zeros(n, bool)  # joint[i]: edges i-1 and i meet smoothly at point i
        for i in range(n):
            v1, v2 = xy[i] - xy[i - 1], xy[(i + 1) % n] - xy[i]
            l1, l2 = np.hypot(*v1), np.hypot(*v2)
            if l1 < 1e-6 or l2 < 1e-6:
                continue
            joint[i] = (not c[i][2]) or v1 @ v2 / l1 / l2 > math.cos(math.radians(25))
        for _ in range(smooth):
            nd = d.copy()
            for i in range(n):
                acc, wsum = 0.5 * d[i], 0.5
                if joint[i]:
                    acc += 0.25 * d[i - 1]; wsum += 0.25
                if joint[(i + 1) % n]:
                    acc += 0.25 * d[(i + 1) % n]; wsum += 0.25
                nd[i] = acc / wsum
            d = nd
        deltas.append(d)
    bold = offset_edges(reg, deltas)
    bold = match_tangents(reg, bold)
    if ink is not None:
        # separate pieces: points hidden inside another piece stay put (their offset corners
        # would otherwise poke out of the growing ball)
        from .geom import point_in_glyph, sample
        for ci, (c, b) in enumerate(zip(reg, bold)):
            others = [sample(o, 12) for oi, o in enumerate(reg) if oi != ci]
            if not others:
                continue
            P = np.array([p[:2] for p in c], float)
            probes = [P + np.array(v) for v in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3))]
            hidden = np.any([point_in_glyph(q, others) for q in probes], axis=0)  # inside or touching
            for i in np.where(hidden)[0]:
                b[i][0], b[i][1] = c[i][0], c[i][1]
    # safety net: a point that moves very differently from both neighbours (a handle flipped at
    # a sharp junction) takes their average movement instead, so no loops or spikes remain
    for c, b in zip(reg, bold) if FIG_SAFETY else ():
        n = len(c)
        for _ in range(3):
            mv = np.array([[q[0] - p[0], q[1] - p[1]] for p, q in zip(c, b)])
            for i in range(n):
                if c[i][2]:
                    continue  # corners may legitimately move more than their neighbours
                avg = (mv[i - 1] + mv[(i + 1) % n]) / 2
                if np.hypot(*(mv[i] - avg)) > 25:
                    b[i][0], b[i][1] = c[i][0] + avg[0], c[i][1] + avg[1]
    # same height as the regular figure (Lora's bold figures keep their height)
    by = [p[1] for c in bold for p in c]
    kk = (max(ys) - min(ys)) / (max(by) - min(by))
    bold = [[[p[0], min(ys) + (p[1] - min(by)) * kk, p[2]] for p in c] for c in bold]
    rx = [p[0] for c in reg for p in c]
    bx = [p[0] for c in bold for p in c]
    d = ((max(bx) - min(bx)) - (max(rx) - min(rx))) / 2
    shift = (min(rx) + max(rx)) / 2 - (min(bx) + max(bx)) / 2 + d
    bold = [[[p[0] + shift, p[1], p[2]] for p in c] for c in bold]
    return bold, d
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
    if CONTRAST_BOLD:
        return contrast_figure(bry_path, weights, w, src, scale, dy, shear)
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
