"""Glyph-level shape tweaks (all point-compatible across masters)."""
import math

import numpy as np

from .geom import explicitize, glyph_contours, set_glyph_contours, signed_area
from .transplant import bry_instance
from .figures import brygada_contours


def _refit_metrics(f, name, old_adv, old_lsb, keep="centre"):
    """Keep the glyph's sidebearings balanced after its outline grew sideways."""
    g = f["glyf"][name]
    cs = glyph_contours(f["glyf"], name)
    return cs


def slant_terminals(M, name, edges, drops=(), balance=True):
    """edges: [(fixed_idx, moving_idx, angle_deg, direction)] — move point moving_idx
    horizontally so the edge fixed->moving leans by angle (direction -1: moving point goes left).
    drops: [(idx, dy)] extra vertical moves (in units at 400, scaled by stem ratio in bold)."""
    for w, f in M.items():
        glyf, hmtx = f["glyf"], f["hmtx"]
        old_adv, _ = hmtx[name]
        g = glyf[name]
        x0, x1 = g.xMin, g.xMax
        cs = glyph_contours(glyf, name)
        flat = [p for c in cs for p in c]
        for fi, mi, ang, dirn in edges:
            P, Q = flat[fi], flat[mi]
            Q[0] = P[0] + dirn * abs(P[1] - Q[1]) * math.tan(math.radians(ang))
        for idx, dy in drops:
            flat[idx][1] += dy
        set_glyph_contours(glyf, name, cs)
        g = glyf[name]
        if balance:
            grow_l, grow_r = max(0, x0 - g.xMin), max(0, g.xMax - x1)
            shift = round(grow_l * 0.5)
            for c in cs:
                for p in c:
                    p[0] += shift
            set_glyph_contours(glyf, name, cs)
            hmtx[name] = (old_adv + round((grow_l + grow_r) * 0.5), glyf[name].xMin)
        else:
            hmtx[name] = (old_adv, glyf[name].xMin)


def stretch_top(M, name, y0, new_top, xmax=None, shear=0.0):
    """Stretch everything above y0 so the glyph's top reaches new_top (t's ascender).
    shear (= tan of the italic angle) moves points along the slant, so slanted stems stay straight."""
    for w, f in M.items():
        glyf = f["glyf"]
        cs = glyph_contours(glyf, name)
        pts = [p for c in cs for p in c if xmax is None or p[0] <= xmax[w] if True]
        top = max(p[1] for c in cs for p in c if xmax is None or p[0] <= xmax[w])
        k = (new_top - y0) / (top - y0)
        for c in cs:
            for p in c:
                if p[1] > y0 and (xmax is None or p[0] <= xmax[w]):
                    ny = y0 + (p[1] - y0) * k
                    p[0] += (ny - p[1]) * shear
                    p[1] = ny
        set_glyph_contours(glyf, name, cs)
        f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)


def bracket_feet(M, names, size_v=40, size_h=26, zone=120, ref_height=700):
    """Replace concave line-line corners near the foot (stem meets slab) with a quadratic
    bracket, like Lora's serifs. Sizes scale with the glyph's height relative to ref_height."""
    first = next(iter(M))
    for name in names:
        # detect corners on the first master, apply the same indices everywhere
        f0 = M[first]
        cs0 = [explicitize(c) for c in glyph_contours(f0["glyf"], name)]
        g0 = f0["glyf"][name]
        h = g0.yMax - g0.yMin
        sc = min(1.0, h / ref_height) if h > 0 else 1.0
        corners = {}
        for ci, c in enumerate(cs0):
            n = len(c)
            orient = 1 if signed_area(c) > 0 else -1
            for i, p in enumerate(c):
                a, b = c[i - 1], c[(i + 1) % n]
                if not (p[2] and a[2] and b[2]):
                    continue
                if not (g0.yMin + 5 < p[1] < g0.yMin + zone * sc):
                    continue
                v1 = (p[0] - a[0], p[1] - a[1])
                v2 = (b[0] - p[0], b[1] - p[1])
                l1, l2 = math.hypot(*v1), math.hypot(*v2)
                if l1 < 1 or l2 < 1:
                    continue
                cross = v1[0] * v2[1] - v1[1] * v2[0]
                cosang = (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)
                ang = math.degrees(math.acos(max(-1, min(1, cosang))))
                concave = cross * orient < 0
                if concave and 55 < ang < 125:
                    # which neighbour is the (near-vertical) stem edge?
                    vert_prev = abs(v1[0]) < abs(v1[1])
                    corners.setdefault(ci, []).append((i, vert_prev))
        for w, f in M.items():
            glyf = f["glyf"]
            cs = [explicitize(c) for c in glyph_contours(glyf, name)]
            wsc = 1.0 if w == first else 1.1
            for ci, lst in corners.items():
                c = cs[ci]
                for i, vert_prev in sorted(lst, reverse=True):
                    p, a, b = c[i], c[i - 1], c[(i + 1) % len(c)]
                    dp, dn = (size_v, size_h) if vert_prev else (size_h, size_v)
                    dp, dn = dp * sc * wsc, dn * sc * wsc
                    la = math.hypot(a[0] - p[0], a[1] - p[1])
                    lb = math.hypot(b[0] - p[0], b[1] - p[1])
                    dp, dn = min(dp, la * 0.6), min(dn, lb * 0.6)
                    A = [p[0] + (a[0] - p[0]) * dp / la, p[1] + (a[1] - p[1]) * dp / la, 1]
                    B = [p[0] + (b[0] - p[0]) * dn / lb, p[1] + (b[1] - p[1]) * dn / lb, 1]
                    c[i:i + 1] = [A, [p[0], p[1], 0], B]
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
    return None


def q_with_brygada_tail(M, bry_path, weights, cap_scale):
    """Elanora's Q = Elanora's O + Brygada's calligraphic tail, fitted to the O."""
    for w, f in M.items():
        glyf, hmtx = f["glyf"], f["hmtx"]
        B = bry_instance(bry_path, weights[w])
        bq = brygada_contours(B, "Q", 1.0)
        bo = B["glyf"]["O"]
        tail = bq[0]  # Brygada draws the tail as the first, separate contour
        lo = glyf["O"]
        sx = (lo.xMax - lo.xMin) / (bo.xMax - bo.xMin)
        sy = (lo.yMax - lo.yMin) / (bo.yMax - bo.yMin)
        s = (sx + sy) / 2
        tail = [[lo.xMin + (x - bo.xMin) * sx, lo.yMin + (y - bo.yMin) * sy, on] for x, y, on in tail]
        ocs = glyph_contours(glyf, "O")
        set_glyph_contours(glyf, "Q", [tail] + ocs)
        extra = (B["hmtx"]["Q"][0] - B["hmtx"]["O"][0]) * s
        hmtx["Q"] = (round(hmtx["O"][0] + extra), glyf["Q"].xMin)


def _foot_corners(f, name, zone):
    """Junctions where a (near-)vertical stem edge meets the top of a foot slab.
    Returns [(x, y, side)] where side=-1 means the bracket goes to the left of the stem edge."""
    from .geom import point_in_glyph, sample
    glyf = f["glyf"]
    g = glyf[name]
    cs = glyph_contours(glyf, name)
    polys = [sample(c, 12) for c in cs]
    segs, tops = [], []
    for c in cs:
        ec = explicitize(c)
        n = len(ec)
        for i in range(n):
            a, b = ec[i], ec[(i + 1) % n]
            if not (a[2] and b[2]):
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            if abs(dy) > 40 and abs(dx) < 0.3 * abs(dy):
                segs.append((a, b))
            if abs(dx) > 20 and abs(dy) < 0.15 * abs(dx) and g.yMin < a[1] < g.yMin + zone:
                tops.append((min(a[0], b[0]), max(a[0], b[0]), (a[1] + b[1]) / 2))
    out = []
    for x0, x1, ys in tops:
        # a slab top: glyph ink just below, air just above (somewhere along it)
        for a, b in segs:
            lo, hi = sorted((a[1], b[1]))
            if not (lo < ys < hi):
                continue
            t = (ys - a[1]) / (b[1] - a[1])
            xs = a[0] + t * (b[0] - a[0])
            if not (x0 - 2 <= xs <= x1 + 2):
                continue
            for side in (-1, 1):
                probe = np.array([[xs + side * 6, ys + 6]])
                below = np.array([[xs + side * 6, ys - 6]])
                if not point_in_glyph(probe, polys)[0] and point_in_glyph(below, polys)[0]:
                    out.append((xs, ys, side, (b[0] - a[0]) / (b[1] - a[1])))
    # de-duplicate
    res = []
    for p in sorted(out):
        if not any(abs(p[0] - q[0]) < 3 and abs(p[1] - q[1]) < 3 and p[2] == q[2] for q in res):
            res.append(p)
    return res


def bracket_feet_v2(M, names, size_v=46, size_h=24, zone=120, ref_height=716, bold_k=1.12):
    """Add a Lora-like bracket (concave fillet) where each stem meets its foot slab."""
    first = next(iter(M))
    report = {}
    for name in names:
        per = {w: _foot_corners(f, name, zone * (1 if w == first else 1.2)) for w, f in M.items()}
        counts = {w: len(v) for w, v in per.items()}
        if len(set(counts.values())) != 1 or not counts[first]:
            report[name] = counts
            continue
        report[name] = counts[first]
        for w, f in M.items():
            glyf = f["glyf"]
            g = glyf[name]
            h = g.yMax - g.yMin
            sc = min(1.0, h / ref_height) * (1 if w == first else bold_k)
            cs = glyph_contours(glyf, name)
            orient_ref = signed_area(cs[0]) if cs else -1
            for xs, ys, side, slope in per[w]:
                sv, sh = size_v * sc, size_h * sc
                # corner slightly inside the ink so the bracket overlaps cleanly
                C = (xs - side * 3, ys - 3)
                A = (xs + slope * sv, ys + sv)
                B = (xs + side * sh, ys)
                K = (xs + slope * sv * 0.08, ys + sv * 0.08)
                con = [[C[0], C[1], 1], [A[0], A[1], 1], [K[0], K[1], 0], [B[0], B[1], 1]]
                if (signed_area(con) > 0) != (orient_ref > 0):
                    con = [con[0]] + con[1:][::-1]
                cs.append(con)
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
    return report


def bracket_chamfers(M, names, size_v=46, size_h=26, zone=120, ref_height=716, bold_k=1.12,
                     slope=0.0):
    """Brygada joins stem and foot slab with a tiny 45-degree chamfer. Turn every such chamfer
    into a Lora-like bracket: the stem point slides up the stem, the slab point slides out
    along the slab, and a quadratic through the virtual corner joins them.
    slope: stem lean (dx/dy), 0 for roman."""
    first = next(iter(M))
    report = {}
    for name in names:
        f0 = M[first]
        g0 = f0["glyf"][name]
        cs0 = [explicitize(c) for c in glyph_contours(f0["glyf"], name)]
        found = []
        for ci, c in enumerate(cs0):
            n = len(c)
            for i in range(n):
                a, b = c[i], c[(i + 1) % n]
                if not (a[2] and b[2]):
                    continue
                dx, dy = b[0] - a[0], b[1] - a[1]
                if not (2 <= abs(dx) <= 11 and 2 <= abs(dy) <= 11):
                    continue
                lo_i, hi_i = (i, (i + 1) % n) if a[1] < b[1] else ((i + 1) % n, i)
                lo = c[lo_i]
                if not (g0.yMin - 1 <= lo[1] <= g0.yMin + zone):
                    continue
                # the low point must continue into a horizontal slab top
                nb = c[(lo_i - 1) % n] if lo_i == (i + 1) % n and False else None
                cand = [c[(lo_i - 1) % n], c[(lo_i + 1) % n]]
                other = [p for p in cand if p is not c[hi_i]]
                if not other:
                    continue
                o = other[0]
                if not (o[2] and abs(o[1] - lo[1]) < 3 and abs(o[0] - lo[0]) > 15):
                    continue
                found.append((ci, lo_i, hi_i))
        report[name] = len(found)
        for w, f in M.items():
            glyf = f["glyf"]
            g = glyf[name]
            h = g.yMax - g.yMin
            sc = min(1.0, max(0.35, h / ref_height)) * (1 if w == first else bold_k)
            cs = [explicitize(c) for c in glyph_contours(glyf, name)]
            inserts = {}
            for ci, lo_i, hi_i in found:
                c = cs[ci]
                lo, hi = c[lo_i], c[hi_i]
                K = (hi[0] - slope * (hi[1] - lo[1]), lo[1])
                away = 1 if lo[0] > hi[0] else -1
                hi[0], hi[1] = K[0] + slope * size_v * sc, K[1] + size_v * sc
                lo[0], lo[1] = K[0] + away * size_h * sc, K[1]
                # insert the control between lo and hi (in contour order)
                pos = max(lo_i, hi_i) if abs(lo_i - hi_i) == 1 else 0
                inserts.setdefault(ci, []).append((pos, [K[0], K[1], 0]))
            for ci, lst in inserts.items():
                for pos, pt in sorted(lst, key=lambda t: -t[0]):
                    if pos == 0:
                        cs[ci].append(pt)
                    else:
                        cs[ci].insert(pos, pt)
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
    return report


def _split_at_y(c, y_cut, pick="right"):
    """c explicitized. Split the segment crossing y_cut (rightmost or leftmost crossing) and
    insert an on-curve point there. Returns (new contour, index of inserted point)."""
    from .geom import segments
    n = len(c)
    best = None
    for a, ctrl, b in segments(c):
        P0, P2 = np.array(c[a][:2]), np.array(c[b][:2])
        if ctrl is None:
            if (P0[1] - y_cut) * (P2[1] - y_cut) > 0 or P0[1] == P2[1]:
                continue
            t = (y_cut - P0[1]) / (P2[1] - P0[1])
            x = P0[0] + t * (P2[0] - P0[0])
        else:
            P1 = np.array(c[ctrl][:2])
            A = P0[1] - 2 * P1[1] + P2[1]
            Bq = 2 * (P1[1] - P0[1])
            C = P0[1] - y_cut
            ts = np.roots([A, Bq, C]) if abs(A) > 1e-9 else np.array([-C / Bq])
            ts = [t.real for t in np.atleast_1d(ts) if abs(t.imag) < 1e-9 and 0 < t.real < 1]
            if not ts:
                continue
            t = ts[0]
            x = (1 - t) ** 2 * P0[0] + 2 * (1 - t) * t * P1[0] + t * t * P2[0]
        if best is None or (x > best[0] if pick == "right" else x < best[0]):
            best = (x, a, ctrl, b, t)
    x, a, ctrl, b, t = best
    out = [list(p) for p in c]
    if ctrl is None:
        out.insert(a + 1, [x, y_cut, 1])
        return out, a + 1
    P0, P1, P2 = (np.array(out[i][:2]) for i in (a, ctrl, b))
    Q0 = P0 + (P1 - P0) * t
    Q1 = P1 + (P2 - P1) * t
    S = Q0 + (Q1 - Q0) * t
    # replace [P0, P1, P2] with [P0, Q0, S, Q1, P2]
    out[ctrl] = [Q0[0], Q0[1], 0]
    out.insert(ctrl + 1, [S[0], S[1], 1])
    out.insert(ctrl + 2, [Q1[0], Q1[1], 0])
    return out, ctrl + 1


def _nearest_on(c, P):
    best = min((i for i, p in enumerate(c) if p[2]), key=lambda i: (c[i][0] - P[0]) ** 2 + (c[i][1] - P[1]) ** 2)
    return best


def italic_y_from_u_g(M, y_cut=240, u_crotch=(397, 216), g_crotch=(358, 215)):
    """Brygada-shaped italic y in Lora's hand: Lora's italic u (entry stroke, bowl, right stem)
    with the descender and ball of Elanora's italic g grafted onto the right stem."""
    from .transplant import base_anchors
    first = next(iter(M))
    idx = {}
    info = {}
    for w, f in M.items():
        glyf, hmtx = f["glyf"], f["hmtx"]
        u = explicitize(glyph_contours(glyf, "u")[0])
        g = explicitize(glyph_contours(glyf, "g")[0])
        u, iu = _split_at_y(u, y_cut)
        g, ig = _split_at_y(g, y_cut)
        if w == first:
            idx["uc"] = _nearest_on(u, u_crotch)
            idx["gc"] = _nearest_on(g, g_crotch)
            idx["iu"], idx["ig"], idx["lu"], idx["lg"] = iu, ig, len(u), len(g)
        assert (iu, ig, len(u), len(g)) == (idx["iu"], idx["ig"], idx["lu"], idx["lg"]), "masters differ"
        dx = u[iu][0] - g[ig][0]
        gs = [[x + dx, y, on] for x, y, on in g]
        uc, gc = idx["uc"], idx["gc"]
        # u: ... right edge down to the cut | g: cut -> descender -> ball -> inner edge up to crotch | u: crotch -> bowl
        n_g = len(gs)
        g_part = [gs[(ig + 1 + k) % n_g] for k in range((gc - ig - 1) % n_g)]
        # join at the graft's own crotch; drop u's crotch (and any duplicate of it)
        tail = u[uc + 1:]
        while tail and abs(tail[0][0] - u[uc][0]) < 2 and abs(tail[0][1] - u[uc][1]) < 2:
            tail = tail[1:]
        new = u[: iu + 1] + g_part + [list(gs[gc])] + tail
        old_anchors = base_anchors(f).get("y", {})
        old_adv = hmtx["y"][0]
        set_glyph_contours(glyf, "y", [new])
        # width: u's stem plus g's right sidebearing
        u_top_right = max(p[0] for p in u if p[1] > 440)
        g_top_right = max(p[0] for p in g if p[1] > 440)
        adv = round(u_top_right + (hmtx["g"][0] - g_top_right))
        hmtx["y"] = (adv, glyf["y"].xMin)
        new_anchors = {k: v for k, v in base_anchors(f).get("u", {}).items() if k in ("acutecomb", "gravecomb")}
        info[w] = (old_anchors, new_anchors, old_adv)
    return info


# ---------------------------------------------------------------- arch / bowl joins
def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


ARCH_JOINS = {
    # glyph: [(stem-edge selector, side, zone)] ; selector (run index, 0=left edge / 1=right edge)
    "n": [((0, 1), +1, "top")],
    "h": [((0, 1), +1, "top")],
    "m": [((0, 1), +1, "top"), ((1, 1), +1, "top")],
    "r": [((0, 1), +1, "top")],
    "eng": [((0, 1), +1, "top")],
    "hbar": [((0, 1), +1, "top")],
    "u": [((1, 0), -1, "bottom")],
    "uni03BC": [((1, 0), -1, "bottom")],
    "b": [((0, 1), +1, "top"), ((0, 1), +1, "bottom")],
    "p": [((0, 1), +1, "top"), ((0, 1), +1, "bottom")],
    "thorn": [((0, 1), +1, "top"), ((0, 1), +1, "bottom")],
    "d": [((1, 0), -1, "top"), ((1, 0), -1, "bottom")],
    "q": [((1, 0), -1, "top"), ((1, 0), -1, "bottom")],
    "dcroat": [((1, 0), -1, "top"), ((1, 0), -1, "bottom")],
    "dcaron": [((1, 0), -1, "top"), ((1, 0), -1, "bottom")],
}


def arch_joins(M, amount_top, amount_bottom, glyphs=None, bold_k=0.75, y_top=516, y_bot=-16):
    """Let arches and bowls run further along the stem before they merge (Brygada-like):
    the thin join slides toward mid x-height and approaches the stem more steeply, while the
    top/bottom of the curve stays put. A smooth vertical displacement field around each join."""
    from .geom import point_in_glyph, sample
    from .widen import ink_runs
    first = next(iter(M))
    for name, joins in ARCH_JOINS.items():
        if glyphs and name not in glyphs:
            continue
        for w, f in M.items():
            glyf = f["glyf"]
            cs = glyph_contours(glyf, name)
            runs = ink_runs(cs, 250)
            polys = [sample(c, 12) for c in cs]
            k = 1.0 if w == first else bold_k
            fields = []
            for (ri, edge), side, zone in joins:
                xe = runs[ri][edge]
                stem_w = runs[ri][1] - runs[ri][0]
                # counter width next to this edge
                nb = runs[ri + side] if 0 <= ri + side < len(runs) else None
                cw = abs((nb[0] if side > 0 else nb[1]) - xe) if nb else 250
                # find the join height: first ink along the stem edge, going up/down from mid x-height
                probe_x = xe + side * 6
                ys = np.arange(250, 560, 2) if zone == "top" else np.arange(250, -60, -2)
                ins = point_in_glyph(np.c_[np.full(len(ys), probe_x), ys], polys)
                yj = float(ys[np.argmax(ins)]) if ins.any() else (420 if zone == "top" else 80)
                A = (amount_top if zone == "top" else amount_bottom) * k
                fields.append((xe, side, zone, yj, A, stem_w, cw))
            for c in cs:
                for p in c:
                    dy = 0.0
                    for xe, side, zone, yj, A, stem_w, cw in fields:
                        d = side * (p[0] - xe)
                        if d < 0:
                            wx = _smooth((d + 30) / 22)
                        else:
                            wx = 1 - _smooth(d / (0.6 * cw))
                        if wx <= 0:
                            continue
                        if zone == "top":
                            if p[1] <= yj:
                                wy = _smooth((p[1] - (yj - 160)) / 80)
                            else:
                                wy = 1 - _smooth((p[1] - yj) / (y_top - yj))
                            dy -= A * wx * wy
                        else:
                            if p[1] >= yj:
                                wy = 1 - _smooth((p[1] - (yj + 80)) / 80)
                            else:
                                wy = _smooth((p[1] - y_bot) / (yj - y_bot))
                            dy += A * wx * wy
                    p[1] += dy
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)


# ---------------------------------------------------------------- Lora feet on Brygada figures
LORA_FOOT_RUNS = {
    "roman": {"one": [11, 12, 13, 14, 15, 16, 17, 18, 0, 1, 2, 3, 4, 5], "four": list(range(0, 15)),
              "uni00B9": [10, 11, 12, 13, 14, 15, 16, 17, 0, 1, 2, 3, 4],
              "uni2074": [13, 14, 15, 16, 17, 18, 19, 20, 0, 1, 2, 3, 4]},
    "italic": {"one": list(range(1, 15)), "four": [15, 16, 17, 18, 19, 20, 0, 1, 2, 3, 4, 5],
               "uni00B9": [10, 11, 12, 13, 14, 15, 16, 17, 0, 1, 2, 3, 4],
               "uni2074": [13, 14, 15, 16, 0, 1, 2, 3, 4]},
}
FOOT_DONORS = {"one": "one", "one.tf": "one", "one.osf": "one", "one.tosf": "one",
               "four": "four", "four.tf": "four",
               "one.numr": "uni00B9", "one.dnom": "uni00B9", "uni00B9": "uni00B9", "uni2081": "uni00B9",
               "four.numr": "uni2074", "four.dnom": "uni2074", "uni2074": "uni2074", "uni2084": "uni2074"}


def _slab(cs, yMin):
    ys = [round(p[1]) for c in cs for p in c if p[2] and yMin + 8 < p[1] < yMin + 90]
    if not ys:
        return None
    from collections import Counter
    return Counter(ys).most_common(1)[0][0]


def graft_lora_feet(M, M_lora, style="roman", donors=FOOT_DONORS):
    """Give Brygada's 1 and 4 Lora's own foot: Brygada's square slab is pulled in under the
    stem and Lora's asymmetric foot (long flared bracket on the left, near-square on the right)
    is laid over it, each side shifted so its bracket meets Brygada's stem edge."""
    from .widen import ink_runs
    runs_idx = LORA_FOOT_RUNS[style]
    report = {}
    for name, donor in donors.items():
        for w, f in M.items():
            glyf = f["glyf"]
            if name not in glyf.keys():
                continue
            cs = glyph_contours(glyf, name)
            g = glyf[name]
            slab = _slab(cs, g.yMin)
            if slab is None:
                report[name] = "no slab"
                break
            size = (g.yMax - g.yMin) / 716
            lg = M_lora[w]["glyf"]
            lcs = glyph_contours(lg, donor)
            run = [list(lcs[0][i]) for i in runs_idx[donor]]
            dy = g.yMin - lg[donor].yMin
            lr, ll = run[0][0], run[-1][0]  # Lora's stem edges where its foot attaches
            y_att = (run[0][1] + run[-1][1]) / 2 + dy
            # Brygada's stem edges just above its slab, extrapolated to the attach height
            y1, y2 = slab + 22 * size + 4, slab + 44 * size + 4

            def edges(y):
                rr = [r for r in ink_runs(cs, y) if r[1] - r[0] > 12]
                return rr[-1] if donor in ("one", "uni00B9") else max(rr, key=lambda r: r[0])

            (a1, b1), (a2, b2) = edges(y1), edges(y2)
            sl = a1 + (a2 - a1) * (y_att - y1) / (y2 - y1)
            sr = b1 + (b2 - b1) * (y_att - y1) / (y2 - y1)
            # 1) pull Brygada's slab in under the stem
            for c in cs:
                for p in c:
                    if p[1] <= slab + 8:
                        if p[0] < a1:
                            p[0] = a1 - (a1 - p[0]) * 0.1
                        elif p[0] > b1:
                            p[0] = b1 + (p[0] - b1) * 0.1
            # 2) Lora's foot, each side moved onto Brygada's stem edge
            mid = (ll + lr) / 2
            foot = [[p[0] + ((sl - ll) if p[0] < mid else (sr - lr)), p[1] + dy, p[2]] for p in run]
            cs.append(foot)
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
        report.setdefault(name, "ok")
    return report


# whole-arm joins, calibrated on Brygada (offsets at Elanora's scale, Regular): (inner, outer)
ARM_OFFSETS = {"top_n": (60, 10), "bot_u": (60, 45), "top_b": (70, 15), "bot_b": (45, 8),
               "top_d": (70, 15), "bot_d": (50, 25)}
ARMS = {
    "n": [((0, 1), +1, "top", "top_n")], "h": [((0, 1), +1, "top", "top_n")],
    "m": [((0, 1), +1, "top", "top_n"), ((1, 1), +1, "top", "top_n")],
    "r": [((0, 1), +1, "top", "top_n")], "eng": [((0, 1), +1, "top", "top_n")],
    "hbar": [((0, 1), +1, "top", "top_n")],
    "u": [((1, 0), -1, "bottom", "bot_u")], "uni03BC": [((1, 0), -1, "bottom", "bot_u")],
    "b": [((0, 1), +1, "top", "top_b"), ((0, 1), +1, "bottom", "bot_b")],
    "p": [((0, 1), +1, "top", "top_b"), ((0, 1), +1, "bottom", "bot_b")],
    "thorn": [((0, 1), +1, "top", "top_b"), ((0, 1), +1, "bottom", "bot_b")],
    "d": [((1, 0), -1, "top", "top_d"), ((1, 0), -1, "bottom", "bot_d")],
    "q": [((1, 0), -1, "top", "top_d"), ((1, 0), -1, "bottom", "bot_d")],
    "dcroat": [((1, 0), -1, "top", "top_d"), ((1, 0), -1, "bottom", "bot_d")],
    "dcaron": [((1, 0), -1, "top", "top_d"), ((1, 0), -1, "bottom", "bot_d")],
}


def arm_joins(M, factor, bold_k=0.8, y_top=516, y_bot=-16, offsets=ARM_OFFSETS):
    """Move the whole arm (both edges) of arches and bowls further along the stem before it
    merges, like Brygada. factor scales Brygada's measured offsets (1.0 = as far as Brygada)."""
    from .geom import point_in_glyph, sample
    from .widen import ink_runs
    first = next(iter(M))
    for name, joins in ARMS.items():
        for w, f in M.items():
            glyf = f["glyf"]
            if name not in glyf.keys():
                continue
            cs = glyph_contours(glyf, name)
            runs = ink_runs(cs, 250)
            polys = [sample(c, 12) for c in cs]
            k = factor * (1.0 if w == first else bold_k)
            specs = []
            for (ri, edge), side, zone, key in joins:
                xe = runs[ri][edge]
                nb = runs[ri + side] if 0 <= ri + side < len(runs) else None
                cw = abs((nb[0] if side > 0 else nb[1]) - xe) if nb else 250
                px = xe + side * 4
                ys = np.arange(250, 600, 2) if zone == "top" else np.arange(250, -60, -2)
                ins = point_in_glyph(np.c_[np.full(len(ys), px), ys], polys)
                if not ins.any():
                    continue
                a = int(np.argmax(ins))
                b = a + int(np.argmax(~ins[a:])) if (~ins[a:]).any() else len(ys) - 1
                y_ic, y_oj = float(ys[a]), float(ys[b])
                ain, aout = offsets[key]
                specs.append((xe, side, zone, y_ic, y_oj, ain * k, aout * k, cw))
            for c in cs:
                for p in c:
                    dy = 0.0
                    for xe, side, zone, y_ic, y_oj, ain, aout, cw in specs:
                        d = side * (p[0] - xe)
                        S = _smooth((d + 30) / 18) if d < -12 else (1.0 if d <= 0 else 1 - _smooth(d / (0.9 * cw)))
                        if S <= 0:
                            continue
                        if zone == "top":
                            if d < 8 and p[1] > y_oj + 6:
                                continue  # the stem above the arm stays put
                            r = 1 - _smooth((p[1] - y_ic) / max(1.0, y_oj - y_ic))
                            T = _smooth((p[1] - (y_ic - 150)) / 100)
                            if d >= 8:
                                T *= 1 - _smooth((p[1] - y_oj) / max(1.0, y_top - y_oj))
                            dy -= (aout + (ain - aout) * r) * S * T
                        else:
                            if d < 8 and p[1] < y_oj - 6:
                                continue
                            r = 1 - _smooth((y_ic - p[1]) / max(1.0, y_ic - y_oj))
                            T = _smooth(((y_ic + 150) - p[1]) / 100)
                            if d >= 8:
                                T *= 1 - _smooth((y_oj - p[1]) / max(1.0, y_oj - y_bot))
                            dy += (aout + (ain - aout) * r) * S * T
                    p[1] += dy
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)


def straighten_y_arm(M, y_lo=250, y_hi=470):
    """The italic y's right stem (from Lora's u) bends slightly left towards the top; make both
    of its edges straight between y_lo and y_hi (points pulled onto the chord)."""
    from .widen import ink_runs
    for w, f in M.items():
        glyf = f["glyf"]
        cs = glyph_contours(glyf, "y")
        c = cs[0]
        runs_lo, runs_hi = ink_runs(cs, y_lo), ink_runs(cs, y_hi)
        (l0, r0), (l1, r1) = runs_lo[-1], runs_hi[-1]
        for p in c:
            if y_lo < p[1] < y_hi + 20:
                t = (p[1] - y_lo) / (y_hi - y_lo)
                el, er = l0 + (l1 - l0) * t, r0 + (r1 - r0) * t
                if abs(p[0] - er) < 25:
                    p[0] = er
                elif abs(p[0] - el) < 25:
                    p[0] = el
        set_glyph_contours(glyf, "y", cs)
        f["hmtx"]["y"] = (f["hmtx"]["y"][0], glyf["y"].xMin)


def _joins(cs, xe, side, zone, polys=None):
    """(y_inner, y_outer) of an arm meeting the stem edge xe (scan just off the edge)."""
    from .geom import point_in_glyph, sample
    polys = polys or [sample(c, 12) for c in cs]
    px = xe + side * 4
    ys = np.arange(250, 600, 2) if zone == "top" else np.arange(250, -60, -2)
    ins = point_in_glyph(np.c_[np.full(len(ys), px), ys], polys)
    if not ins.any():
        return None
    a = int(np.argmax(ins))
    b = a + int(np.argmax(~ins[a:])) if (~ins[a:]).any() else len(ys) - 1
    return float(ys[a]), float(ys[b])


def arm_joins_measured(M, bry, weights, scale, factor, glyphs=None, y_top=516, y_bot=-16):
    """Move Lora's arms (both edges) toward Brygada's join heights by `factor` (0.5 = half
    way), with the inner and outer offsets measured per glyph and master."""
    from .geom import sample
    from .widen import ink_runs
    from .transplant import bry_instance
    from .figures import brygada_contours
    report = {}
    for name, joins in ARMS.items():
        if glyphs and name not in glyphs:
            continue
        for w, f in M.items():
            glyf = f["glyf"]
            B = bry_instance(bry, weights[w])
            if name not in glyf.keys() or name not in B["glyf"].keys():
                break
            cs = glyph_contours(glyf, name)
            bcs = brygada_contours(B, name, scale)
            runs, bruns = ink_runs(cs, 250), ink_runs(bcs, 250)
            specs = []
            for (ri, edge), side, zone, key in joins:
                try:
                    xe, bxe = runs[ri][edge], bruns[ri][edge]
                except IndexError:
                    continue
                lj, bj = _joins(cs, xe, side, zone), _joins(bcs, bxe, side, zone)
                if not lj or not bj:
                    continue
                if zone == "top":
                    ain, aout = (lj[0] - bj[0]) * factor, (lj[1] - bj[1]) * factor
                else:
                    ain, aout = (bj[0] - lj[0]) * factor, (bj[1] - lj[1]) * factor
                nb = runs[ri + side] if 0 <= ri + side < len(runs) else None
                cw = abs((nb[0] if side > 0 else nb[1]) - xe) if nb else 250
                specs.append((xe, side, zone, lj[0], lj[1], ain, aout, cw))
                report.setdefault(name, {})[(w, zone)] = (round(ain), round(aout))
            for c in cs:
                for p in c:
                    dy = 0.0
                    for xe, side, zone, y_ic, y_oj, ain, aout, cw in specs:
                        d = side * (p[0] - xe)
                        S = _smooth((d + 30) / 18) if d < -12 else (1.0 if d <= 0 else 1 - _smooth(d / (0.9 * cw)))
                        if S <= 0:
                            continue
                        if zone == "top":
                            if d < 8 and p[1] > y_oj + 6:
                                continue
                            r = 1 - _smooth((p[1] - y_ic) / max(1.0, y_oj - y_ic))
                            T = _smooth((p[1] - (y_ic - 150)) / 100)
                            if d >= 8:
                                T *= 1 - _smooth((p[1] - y_oj) / max(1.0, y_top - y_oj))
                            dy -= (aout + (ain - aout) * r) * S * T
                        else:
                            if d < 8 and p[1] < y_oj - 6:
                                continue
                            r = 1 - _smooth((y_ic - p[1]) / max(1.0, y_ic - y_oj))
                            T = _smooth(((y_ic + 150) - p[1]) / 100)
                            if d >= 8:
                                T *= 1 - _smooth((y_oj - p[1]) / max(1.0, y_oj - y_bot))
                            dy += (aout + (ain - aout) * r) * S * T
                    p[1] += dy
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
    return report


def shrink_ball(f, name, D, Rd, factor, ci=None):
    """Scale a ball terminal toward its centre (smooth falloff into the neck). One master."""
    from .geom import inscribed_circle
    glyf = f["glyf"]
    cs = glyph_contours(glyf, name)
    cx, cy, r = inscribed_circle(cs, D, Rd)
    for i, c in enumerate(cs):
        if ci is not None and i != ci:
            continue
        for p in c:
            d = math.hypot(p[0] - cx, p[1] - cy)
            w = 1.0 if d <= r * 1.05 else max(0.0, 1 - (d - r * 1.05) / (r * 0.9))
            k = 1 - (1 - factor) * w
            p[0], p[1] = cx + (p[0] - cx) * k, cy + (p[1] - cy) * k
    set_glyph_contours(glyf, name, cs)
    f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
    return (cx, cy, r)


def respace(f, names, k):
    """Scale both sidebearings of the given glyphs by k (one master)."""
    glyf, hmtx = f["glyf"], f["hmtx"]
    for n in names:
        if n not in glyf.keys() or glyf[n].isComposite():
            continue
        g = glyf[n]
        adv, lsb = hmtx[n]
        if g.numberOfContours <= 0:
            continue
        rsb = adv - g.xMax
        nl, nr = round(g.xMin * k), round(rsb * k)
        dx = nl - g.xMin
        cs = glyph_contours(glyf, n)
        for c in cs:
            for p in c:
                p[0] += dx
        set_glyph_contours(glyf, n, cs)
        hmtx[n] = (glyf[n].xMax + nr, glyf[n].xMin)


def match_spacing(M, L, name, lefts, rights, left_bias=0, right_bias=0):
    """Shift/advance `name` so its average smoothed gap to typical neighbours equals Lora's."""
    from .kerning import min_gap
    for w, f in M.items():
        gs, gl = f.getGlyphSet(), L[w].getGlyphSet()
        cache, cachel = {}, {}
        dl = [min_gap(gl, a, name, 0, cachel) - min_gap(gs, a, name, 0, cache) for a in lefts]
        dr = [min_gap(gl, name, b, 0, cachel) - min_gap(gs, name, b, 0, cache) for b in rights]
        dl = [v for v in dl if v is not None]
        dr = [v for v in dr if v is not None]
        sl = (round(np.mean(dl)) if dl else 0) + left_bias
        sr = (round(np.mean(dr)) if dr else 0) + right_bias
        glyf = f["glyf"]
        cs = glyph_contours(glyf, name)
        for c in cs:
            for p in c:
                p[0] += sl
        set_glyph_contours(glyf, name, cs)
        f["hmtx"][name] = (f["hmtx"][name][0] + sl + sr, glyf[name].xMin)


JOIN_GLYPHS = {"b": "left", "p": "left", "thorn": "left", "d": "right", "q": "right", "dcroat": "right", "dcaron": "right"}
JOIN_K = (20, 40, 70, 110, 150)


def _arm_profile(cs, stem_side, zone, ks=JOIN_K, perp=False):
    from .geom import point_in_glyph, sample
    from .widen import ink_runs
    polys = [sample(c, 12) for c in cs]
    # stem edge where the stem is narrowest (at y=250 a counter may already be curving away)
    edges = []
    for yy in (150, 200, 250, 300, 350):
        runs = [r for r in ink_runs(cs, yy) if r[1] - r[0] > 20]
        if len(runs) >= 2:
            edges.append(runs[0][1] if stem_side == "left" else runs[-1][0])
    if not edges:
        runs = [r for r in ink_runs(cs, 250) if r[1] - r[0] > 20]
        edges = [runs[0][1] if stem_side == "left" else runs[-1][0]]
    xe = min(edges) if stem_side == "left" else max(edges)
    sgn = 1 if stem_side == "left" else -1
    ys = np.arange(250, 620) if zone == "top" else np.arange(250, -120, -1)
    def run(k):
        ins = point_in_glyph(np.c_[np.full(len(ys), xe + sgn * k), ys], polys)
        if not ins.any():
            return None
        a = int(np.argmax(ins))
        b = a + int(np.argmax(~ins[a:])) if (~ins[a:]).any() else len(ys) - 1
        return float(ys[a]), float(ys[b])
    prof = []
    inner = None
    if perp:
        # inner edge of the arm as a polyline (lower edge for a top arm, upper for a bottom one);
        # the stroke width at k is the distance from the outer edge point to that polyline
        kk = np.arange(2, max(ks) + 140, 2)
        inner = np.array([(xe + sgn * q, r[0]) for q in kk for r in [run(q)] if r is not None])
    for k in ks:
        r = run(k)
        if r is None:
            prof.append(None)
            continue
        v = abs(r[1] - r[0])
        if perp and len(inner):
            O = np.array([xe + sgn * k, r[1]])
            v = min(v, float(np.min(np.hypot(*(inner - O).T))))
        prof.append(v)
    return xe, sgn, prof


def thicken_joins(f, fl, glyphs=JOIN_GLYPHS, ks=JOIN_K, fade=220):
    """Bold master only: where a bowl's arm is thinner next to the stem than Lora Bold's arm,
    move the counter's edge inward (toward the bowl centre) by the shortfall, fading out with
    distance from the stem. Point-preserving, so the masters stay compatible."""
    from .geom import signed_area
    report = {}
    for g, side in glyphs.items():
        if g not in f["glyf"].keys() or g not in fl["glyf"].keys():
            continue
        cs = glyph_contours(f["glyf"], g)
        lcs = glyph_contours(fl["glyf"], g)
        holes = [i for i, c in enumerate(cs) if signed_area(c) > 0]
        if not holes:
            continue
        hi = max(holes, key=lambda i: len(cs[i]))
        ys_h = [p[1] for p in cs[hi]]
        mid = (min(ys_h) + max(ys_h)) / 2
        for zone in ("top", "bottom"):
            xe, sgn, pp = _arm_profile(cs, side, zone, ks)
            _, _, lp = _arm_profile(lcs, side, zone, ks)
            deficit = [max(0.0, (l or 0) - (p or 0)) if p is not None and l is not None else 0.0 for p, l in zip(pp, lp)]
            if max(deficit) < 2:
                continue
            report[(g, zone)] = [round(d) for d in deficit]
            dir_y = 1 if zone == "bottom" else -1
            for p in cs[hi]:
                if (zone == "bottom" and p[1] > mid) or (zone == "top" and p[1] < mid):
                    continue
                d = sgn * (p[0] - xe)
                if d < -8:
                    continue
                if d <= ks[-1]:
                    dy = float(np.interp(max(d, ks[0]), ks, deficit))
                else:
                    dy = deficit[-1] * max(0.0, 1 - (d - ks[-1]) / (fade - ks[-1]))
                # stay out of the middle of the counter
                span = (max(ys_h) - min(ys_h)) / 2
                wy = min(1.0, abs(p[1] - mid) / (0.5 * span))
                p[1] += dir_y * dy * wy
        set_glyph_contours(f["glyf"], g, cs)
    return report


def fix_touch_points(reg_cs, bold_cs, tol=2.5, inset=3.0, excl=4):
    """Points that in the regular sit on another part of the outline (a stroke's flat end on a
    ball, a diagonal's end on a crossbar) are pulled back just inside that part in bold, so
    thickening can't make them poke out. Works on explicitized, point-compatible contours."""
    from .geom import point_in_glyph, sample, segments
    R = [explicitize(c) for c in reg_cs]
    Bc = [explicitize(c) for c in bold_cs]
    assert [len(c) for c in R] == [len(c) for c in Bc]
    ts = np.linspace(0, 1, 26)

    def seg_pts(c, a, ctrl, b):
        P0, P2 = np.array(c[a][:2]), np.array(c[b][:2])
        if ctrl is None:
            return P0[None] + (P2 - P0)[None] * ts[:, None], np.repeat((P2 - P0)[None], len(ts), 0)
        P1 = np.array(c[ctrl][:2]); t = ts[:, None]
        return (1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t * t * P2, 2 * (1 - t) * (P1 - P0) + 2 * t * (P2 - P1)

    segs = [list(segments(c)) for c in R]
    for i, c in enumerate(R):
        n = len(c)
        for k, p in enumerate(c):
            if not p[2]:
                continue
            best = None
            for j, cj in enumerate(R):
                for si, (a, ctrl, b) in enumerate(segs[j]):
                    if j == i:
                        near = min(min((a - k) % n, (k - a) % n), min((b - k) % n, (k - b) % n))
                        if near <= excl:
                            continue
                    pts, _ = seg_pts(cj, a, ctrl, b)
                    d = np.hypot(pts[:, 0] - p[0], pts[:, 1] - p[1])
                    m = int(np.argmin(d))
                    if d[m] < tol and (best is None or d[m] < best[0]):
                        best = (d[m], j, si, m)
            if best is None:
                continue
            _, j, si, m = best
            a, ctrl, b = segs[j][si]
            pts, tan = seg_pts(Bc[j], a, ctrl, b)
            Q, t = pts[m], tan[m]
            nrm = np.array([-t[1], t[0]]) / max(1e-9, np.hypot(*t))  # outward (away from ink)
            bp = np.array(Bc[i][k][:2])
            if np.dot(bp - Q, nrm) > -inset:  # sticking out (or barely inside)
                tgt = Q - nrm * inset
                Bc[i][k][0], Bc[i][k][1] = tgt[0], tgt[1]
    return R, Bc


def uniform_joins(f, fl, fr, glyphs=None, ks=JOIN_K, fade=220, clamp=60, factor=(1.2, 1.2, 1.1, 1.0, 1.0)):
    """Bold master only: make the arm thickness next to the stem the same for all bowls and
    arches (target = median of Lora Bold's arms), thickening or thinning the inner edge."""
    from .geom import point_in_glyph, sample
    glyphs = glyphs or {"b": ("left", ("top", "bottom")), "p": ("left", ("top", "bottom")),
                        "thorn": ("left", ("top", "bottom")), "d": ("right", ("top", "bottom")),
                        "q": ("right", ("top", "bottom")), "dcroat": ("right", ("top", "bottom")),
                        "dcaron": ("right", ("top", "bottom")), "h": ("left", ("top",)),
                        "n": ("left", ("top",)), "hbar": ("left", ("top",)), "u": ("right", ("bottom",))}
    lprofs = []
    for g, (side, zones) in glyphs.items():
        if g in fl["glyf"].keys():
            for z in zones:
                lprofs.append(_arm_profile(glyph_contours(fl["glyf"], g), side, z, ks, perp=True)[2])
    fac = factor if isinstance(factor, (tuple, list)) else [factor] * len(ks)
    target = [fac[i] * float(np.median([p[i] for p in lprofs if p[i] is not None])) for i in range(len(ks))]
    report = {"target": [round(v) for v in target]}
    for g, (side, zones) in glyphs.items():
        if g not in f["glyf"].keys():
            continue
        cs = glyph_contours(f["glyf"], g)
        polys = [sample(c, 12) for c in cs]
        for zone in zones:
            xe, sgn, pp = _arm_profile(cs, side, zone, ks, perp=True)
            _, _, pv = _arm_profile(cs, side, zone, ks)
            # perpendicular shortfall, converted to a vertical move with the local slope
            delta = [float(np.clip((t - p) * (v / p), -clamp, clamp)) if p else 0.0 for t, p, v in zip(target, pp, pv)]
            report[(g, zone)] = [round(d) for d in delta]
            dir_y = 1 if zone == "bottom" else -1
            # arm inner-edge height next to the stem (k=20)
            ys = np.arange(250, 620) if zone == "top" else np.arange(250, -120, -1)
            ins = point_in_glyph(np.c_[np.full(len(ys), xe + sgn * ks[0]), ys], polys)
            if not ins.any():
                continue
            y_in = float(ys[int(np.argmax(ins))])
            span = abs(y_in - 250)
            moves = []
            for ci, c in enumerate(cs):
                for pi, p in enumerate(c):
                    d = sgn * (p[0] - xe)
                    if d < -8 or d > fade:
                        continue
                    if (zone == "top" and p[1] <= 250) or (zone == "bottom" and p[1] >= 250):
                        continue
                    px = p[0] if d >= 4 else xe + sgn * 4
                    insx = point_in_glyph(np.c_[np.full(len(ys), px), ys], polys)
                    if not insx.any():
                        continue
                    ia = int(np.argmax(insx))
                    ib = ia + int(np.argmax(~insx[ia:])) if (~insx[ia:]).any() else len(ys) - 1
                    a, bb = float(ys[ia]), float(ys[ib])
                    if abs(p[1] - a) > abs(p[1] - bb):
                        continue  # nearer the outer edge
                    if d < 4 and abs(p[1] - a) > 60:
                        continue
                    dd = float(np.interp(max(d, ks[0]), ks, delta)) if d <= ks[-1] else delta[-1] * max(0.0, 1 - (d - ks[-1]) / (fade - ks[-1]))
                    wy = min(1.0, abs(p[1] - 250) / max(1.0, 0.5 * span))
                    moves.append((ci, pi, 0.0, dir_y * dd * wy))
            for ci, pi, dx, dy in moves:
                cs[ci][pi][0] += dx
                cs[ci][pi][1] += dy
            polys = [sample(c, 12) for c in cs]
        set_glyph_contours(f["glyf"], g, cs)
    return report


def straighten_stems(fr, fb, name, y_lo=90, y_hi=470, probes=(140, 220), tol=1.6):
    """Bold master: points that sit on a straight stem edge in the regular are put back on the
    bold stem's straight edge (the arch changes must not warp the trunk)."""
    from .widen import ink_runs
    rcs, bcs = glyph_contours(fr["glyf"], name), glyph_contours(fb["glyf"], name)
    rr = [[r for r in ink_runs(rcs, y) if r[1] - r[0] > 50] for y in probes]
    br = [[r for r in ink_runs(bcs, y) if r[1] - r[0] > 50] for y in probes]
    if not (len(rr[0]) == len(rr[1]) == len(br[0]) == len(br[1])):
        return
    for si in range(len(rr[0])):
        for e in (0, 1):
            r0, r1 = rr[0][si][e], rr[1][si][e]
            b0, b1 = br[0][si][e], br[1][si][e]
            for cr, cb in zip(rcs, bcs):
                for pr, pb in zip(cr, cb):
                    if not (y_lo < pr[1] < y_hi):
                        continue
                    xr = r0 + (r1 - r0) * (pr[1] - probes[0]) / (probes[1] - probes[0])
                    if abs(pr[0] - xr) < tol:
                        xb = b0 + (b1 - b0) * (pb[1] - probes[0]) / (probes[1] - probes[0])
                        if abs(pb[0] - xb) < 8:
                            pb[0] = xb
    set_glyph_contours(fb["glyf"], name, bcs)


def restore_top_join(fr, fb, name):
    """Bold master: put the join of a d-type top arm back at the regular's height. The Lora
    Regular->Bold movement drags d's join far down the stem, leaving the arm point-thin at the
    stem; q (same regular shape) keeps its join, so d follows q's bold proportions."""
    cr, cb = glyph_contours(fr["glyf"], name), glyph_contours(fb["glyf"], name)
    outer = max(range(len(cr)), key=lambda i: len(cr[i]))
    c, b = cr[outer], cb[outer]
    n = len(c)
    J = None
    for i, p in enumerate(c):
        q = c[(i + 1) % n]
        if p[2] and q[2] and abs(q[0] - p[0]) < 2 and q[1] > p[1] + 100 and not c[i - 1][2] and 300 < p[1] < 480:
            J = i
    if J is None:
        return None
    xj = c[J][0]
    b[J][1] = c[J][1]
    # counter corner: on-curve point on the stem side, highest on that vertical edge
    for ci, (k, kb) in enumerate(zip(cr, cb)):
        if ci == outer:
            continue
        m = len(k)
        cand = [i for i, p in enumerate(k) if p[2] and abs(p[0] - xj) < 3 and 250 < p[1] < c[J][1]
                and not k[(i + 1) % m][2]]
        if not cand:
            continue
        C = max(cand, key=lambda i: k[i][1])
        nxt = (C + 1) % m
        kb[C][1] = k[C][1]
        # arm meets the stem where the counter edge is (no notch), with the regular's entry angle
        b[J][0] = kb[C][0]
        b[J - 1][0], b[J - 1][1] = b[J][0] + (c[J - 1][0] - c[J][0]), b[J][1] + (c[J - 1][1] - c[J][1])
        kb[nxt][0] = kb[C][0] - (k[C][0] - k[nxt][0]) * 0.7
        kb[nxt][1] = k[nxt][1] - 17
        set_glyph_contours(fb["glyf"], name, cb)
        return (J, C)
    return None


def restore_smooth(fr, fb, name, tol_deg=4.0):
    """Bold master: on-curve points that are smooth (handles collinear) in the regular get
    collinear handles again, along the bold's average tangent. Point-wise edits such as the
    join thickening can leave a small kink where neighbouring points moved by different amounts."""
    cr, cb = glyph_contours(fr["glyf"], name), glyph_contours(fb["glyf"], name)
    fixed = 0
    for c, b in zip(cr, cb):
        n = len(c)
        for i, p in enumerate(c):
            a, z = c[i - 1], c[(i + 1) % n]
            if not p[2] or a[2] or z[2]:
                continue
            u = np.array(p[:2]) - np.array(a[:2])
            v = np.array(z[:2]) - np.array(p[:2])
            nu, nv = np.hypot(*u), np.hypot(*v)
            if nu < 1e-6 or nv < 1e-6:
                continue
            ang = math.degrees(math.acos(float(np.clip(u @ v / nu / nv, -1, 1))))
            if ang > tol_deg:
                continue
            P = np.array(b[i][:2])
            A, Z = np.array(b[i - 1][:2]), np.array(b[(i + 1) % n][:2])
            la, lz = np.hypot(*(P - A)), np.hypot(*(Z - P))
            if la < 1e-6 or lz < 1e-6:
                continue
            # horizontal/vertical tangents in the regular stay exactly that
            t = (P - A) / la + (Z - P) / lz
            if abs(u[1]) < 1e-6 and abs(v[1]) < 1e-6:
                t = np.array([np.sign(t[0]) or 1.0, 0.0])
            elif abs(u[0]) < 1e-6 and abs(v[0]) < 1e-6:
                t = np.array([0.0, np.sign(t[1]) or 1.0])
            t /= max(1e-9, np.hypot(*t))
            A2, Z2 = P - t * la, P + t * lz
            b[i - 1][0], b[i - 1][1] = float(A2[0]), float(A2[1])
            b[(i + 1) % n][0], b[(i + 1) % n][1] = float(Z2[0]), float(Z2[1])
            fixed += 1
    set_glyph_contours(fb["glyf"], name, cb)
    return fixed


ARCHES = {"n", "h", "hbar", "u", "m", "eng"}


def offset_joins(f, fl, fr, glyphs=None, ks=JOIN_K, fade=230, factor=(1.2, 1.2, 1.1, 1.0, 1.0),
                 lo=-20, hi=30, handle_cap=0.0):
    """Bold master only: bring the arm width next to the stem to a common target (Lora Bold's
    median arm, times `factor`) by offsetting the arm's inner edge along its normal. Each on-curve
    point moves with its handles as one rigid piece, so curves stay smooth; the offset fades out
    with distance from the stem. Points on the stem edge itself only slide along the stem."""
    from .geom import point_in_glyph, sample
    glyphs = glyphs or {"b": ("left", ("top", "bottom")), "p": ("left", ("top", "bottom")),
                        "thorn": ("left", ("top", "bottom")), "d": ("right", ("top", "bottom")),
                        "q": ("right", ("top", "bottom")), "dcroat": ("right", ("top", "bottom")),
                        "dcaron": ("right", ("top", "bottom")), "h": ("left", ("top",)),
                        "n": ("left", ("top",)), "hbar": ("left", ("top",)), "u": ("right", ("bottom",))}
    lprofs = []
    for g, (side, zones) in glyphs.items():
        if g in fl["glyf"].keys():
            for z in zones:
                lprofs.append(_arm_profile(glyph_contours(fl["glyf"], g), side, z, ks, perp=True)[2])
    target = [factor[i] * float(np.median([p[i] for p in lprofs if p[i] is not None])) for i in range(len(ks))]
    report = {"target": [round(v) for v in target]}
    for g, (side, zones) in glyphs.items():
        if g not in f["glyf"].keys() or f["glyf"][g].isComposite():
            continue
        cs = glyph_contours(f["glyf"], g)
        for zone in zones:
            polys = [sample(c, 12) for c in cs]
            xe, sgn, pp = _arm_profile(cs, side, zone, ks, perp=True)
            prof = [float(np.clip(t - p, lo, hi)) if p else 0.0 for t, p in zip(target, pp)]
            # only the join itself: no change from k=110 on (crest and counter top stay as they are)
            arch = g in ARCHES
            report[(g, zone)] = [round(v) for v in prof]
            from .widen import ink_runs as _ir
            _gaps = [abs(r2[0] - r1[1]) for r1, r2 in zip(_ir(cs, 250)[:-1], _ir(cs, 250)[1:])]
            _near = [g2 for g2, (r1, r2) in zip(_gaps, zip(_ir(cs, 250)[:-1], _ir(cs, 250)[1:]))
                     if abs((r1[1] if sgn > 0 else r2[0]) - xe) < 30]
            W = _near[0] if _near else 250.0
            if arch:
                # arches: the join's value fades linearly to zero at the far stem (the crest and
                # the counter's far shoulder keep their shape)
                D = lambda d: (float(np.interp(max(d, ks[0]), ks[:3], prof[:3])) if d <= ks[2]
                               else prof[2] * max(0.0, (W - d) / (W - ks[2])))
            else:
                D = lambda d: (float(np.interp(max(d, ks[0]), ks, prof)) if d <= ks[-1]
                               else prof[-1] * max(0.0, 1 - (d - ks[-1]) / (fade - ks[-1])))
            ys = np.arange(250, 640) if zone == "top" else np.arange(250, -140, -1)
            dir_y = -1 if zone == "top" else 1  # toward the counter
            moves, hextra = {}, {}
            for ci, c in enumerate(cs):
                n = len(c)
                for pi, p in enumerate(c):
                    if not p[2]:
                        continue
                    d = sgn * (p[0] - xe)
                    if d < -8 or d > fade:
                        continue
                    if (zone == "top" and p[1] <= 250) or (zone == "bottom" and p[1] >= 250):
                        continue
                    px = p[0] if d >= 4 else xe + sgn * 4
                    ins = point_in_glyph(np.c_[np.full(len(ys), px), ys], polys)
                    if not ins.any():
                        continue
                    ia = int(np.argmax(ins))
                    ib = ia + int(np.argmax(~ins[ia:])) if (~ins[ia:]).any() else len(ys) - 1
                    a, b = float(ys[ia]), float(ys[ib])
                    if abs(p[1] - a) > abs(p[1] - b):
                        continue  # outer edge of the arm
                    probe = np.array([p[0] + sgn * 3, p[1] + dir_y * 3])
                    if point_in_glyph(probe[None], polys)[0]:
                        continue  # ink toward the counter: outer edge (thin arm)
                    if d < 4:
                        if abs(p[1] - a) > 60:
                            continue
                        mv = np.array([0.0, dir_y * D(ks[0])])
                        # the corner's handle on the arm side is offset like the arm's edge
                        for nb in (pi - 1, (pi + 1) % n):
                            h = c[nb]
                            dh = sgn * (h[0] - xe)
                            if h[2] or dh < 4:
                                continue
                            far = c[(nb + 1) % n] if nb == (pi + 1) % n else c[nb - 1]
                            tv = np.array(far[:2]) - np.array(p[:2])
                            L = np.hypot(*tv)
                            if L < 1e-6:
                                continue
                            nv = np.array([-tv[1], tv[0]]) / L
                            if nv[0] * sgn + nv[1] * dir_y < 0:  # toward the counter, away from the stem
                                nv = -nv
                            hextra[(ci, nb)] = nv * float(np.clip(D(dh), 0.0, handle_cap))
                    else:
                        # normal from the neighbours (handles or on-curves), pointing into the white
                        A, Z = np.array(c[pi - 1][:2]), np.array(c[(pi + 1) % n][:2])
                        t = Z - A
                        L = np.hypot(*t)
                        if L < 1e-6:
                            continue
                        nv = np.array([-t[1], t[0]]) / L
                        probe = np.array(p[:2]) + 3 * nv
                        if point_in_glyph(probe[None], polys)[0]:
                            nv = -nv
                        wy = min(1.0, abs(p[1] - 250) / 60.0)
                        wf = 1.0 if arch else float(np.clip((W - d) / 90.0, 0.0, 1.0))  # taper to zero at the far side
                        mv = nv * D(d) * wy * wf
                    moves[(ci, pi)] = mv
            for (ci, pi), mv in hextra.items():
                cs[ci][pi][0] += mv[0]
                cs[ci][pi][1] += mv[1]
            for (ci, pi), mv in moves.items():
                c = cs[ci]
                n = len(c)
                c[pi][0] += mv[0]
                c[pi][1] += mv[1]
                for nb in (pi - 1, (pi + 1) % n):
                    if c[nb][2]:
                        continue
                    other = (nb - 1) % n if nb == (pi + 1) % n else (nb + 1) % n  # on the far side
                    far = other if c[other][2] else None
                    if far is not None and (ci, far) in moves:  # quadratic shared handle: average
                        m2 = moves[(ci, far)]
                        c[nb][0] += 0.5 * mv[0] if (ci, far) else 0
                        c[nb][1] += 0.5 * mv[1]
                    elif far is not None:
                        c[nb][0] += 0.5 * mv[0]
                        c[nb][1] += 0.5 * mv[1]
                    else:
                        c[nb][0] += mv[0]
                        c[nb][1] += mv[1]
        set_glyph_contours(f["glyf"], g, cs)
    return report


def restore_join(fr, fb, name, zone):
    """Bold master: put a bowl's join back at the regular's heights. Lora's Regular->Bold
    movement drags the outer junction and the counter corner toward each other along the stem
    (Lora's joins sit elsewhere), leaving the arm point-thin at the stem. The outer junction
    goes back onto the counter's stem edge; handles move rigidly with their points."""
    cr, cb = glyph_contours(fr["glyf"], name), glyph_contours(fb["glyf"], name)
    outer = max(range(len(cr)), key=lambda i: len(cr[i]))
    c, b = cr[outer], cb[outer]
    n = len(c)
    top = zone == "top"
    J = None
    for i, p in enumerate(c):
        if not p[2] or not ((300 < p[1] < 480) if top else (20 < p[1] < 200)):
            continue
        for nb, other in ((c[(i + 1) % n], c[i - 1]), (c[i - 1], c[(i + 1) % n])):
            if nb[2] and not other[2] and abs(nb[0] - p[0]) < 3 and ((nb[1] > p[1] + 60) if top else (nb[1] < p[1] - 60)):
                J = i
    if J is None:
        return None
    xj, yj = c[J][0], c[J][1]
    for ci, (k, kb) in enumerate(zip(cr, cb)):
        if ci == outer:
            continue
        m = len(k)
        cand = [i for i, p in enumerate(k) if p[2] and abs(p[0] - xj) < 3
                and ((250 < p[1] < yj) if top else (yj < p[1] < 250))]
        if not cand:
            continue
        C = max(cand, key=lambda i: k[i][1]) if top else min(cand, key=lambda i: k[i][1])
        dC = k[C][1] - kb[C][1]
        kb[C][1] += dC
        for nb in (C - 1, (C + 1) % m):
            if not k[nb][2]:
                kb[nb][1] += dC
        nx, ny = kb[C][0] - b[J][0], yj - b[J][1]
        b[J][0] += nx
        b[J][1] += ny
        for nb in (J - 1, (J + 1) % n):
            if not c[nb][2]:
                b[nb][0] += nx
                b[nb][1] += ny
        set_glyph_contours(fb["glyf"], name, cb)
        return (J, C, round(dC), round(ny))
    return None


E_EXP = 1.0


def arch_morph(M, bry, weights, scale, factor=1.0, glyphs=None, reach=1.0, thick=None, iters=4, max_move=65):
    """Move Lora's own arches and bowls so they meet the stem where Brygada's do, as one smooth
    deformation per arm edge: each point moves vertically by D * (1 - u)^2, u = d / R (d: distance
    from the stem edge, R: distance to the arm's crest), i.e. steepest at the stem and flat (zero)
    at the crest, so the arm bends one way only and the crest keeps its height. Handles next to
    smooth points move with them, so no tangent breaks. D (per master) is the mean of Brygada's
    inner and outer join offsets, times `factor`. The inner edge gets an extra E (same falloff),
    solved so the arm's perpendicular width at the stem is Lora's own times thick[w]."""
    from .geom import sample, point_in_glyph
    from .widen import ink_runs
    from .transplant import bry_instance
    from .figures import brygada_contours
    thick = thick or {w: 1.0 for w in M}
    report = {}
    for name, joins in ARMS.items():
        if glyphs is not None and name not in glyphs:
            continue
        for w, f in M.items():
            glyf = f["glyf"]
            B = bry_instance(bry, weights[w])
            if name not in glyf.keys() or name not in B["glyf"].keys() or glyf[name].isComposite():
                continue
            cs0 = glyph_contours(glyf, name)
            bcs = brygada_contours(B, name, scale)
            polys = [sample(c, 12) for c in cs0]
            runs, bruns = ink_runs(cs0, 250), ink_runs(bcs, 250)
            specs = []
            for (ri, edge), side, zone, key in joins:
                try:
                    xe, bxe = runs[ri][edge], bruns[ri][edge]
                except IndexError:
                    continue
                lj, bj = _joins(cs0, xe, side, zone, polys), _joins(bcs, bxe, side, zone)
                if not lj or not bj:
                    continue
                D = factor * 0.5 * ((bj[0] - lj[0]) + (bj[1] - lj[1]))
                D = float(np.clip(D, -max_move, max_move))  # d top, p bottom: Brygada is very far off
                # crest: extreme on-curve point of the arm within the x-height band
                arm = [(side * (p[0] - xe), p[1]) for c in cs0 for p in c
                       if p[2] and side * (p[0] - xe) > 10
                       and ((250 < p[1] < 560) if zone == "top" else (-60 < p[1] < 250))]
                if not arm:
                    continue
                ext = max(arm, key=lambda q: q[1]) if zone == "top" else min(arm, key=lambda q: q[1])
                R = max(40.0, ext[0] * reach)
                # the join on the outline: stem-edge on-curve points with a handle on the arm side
                jy = []
                for c in cs0:
                    n_ = len(c)
                    for i, p in enumerate(c):
                        if not p[2] or abs(p[0] - xe) > 3 or not ((p[1] > 250) if zone == "top" else (p[1] < 250)):
                            continue
                        for nb in (c[i - 1], c[(i + 1) % n_]):
                            if not nb[2] and side * (nb[0] - xe) > 3:
                                jy.append(p[1])
                if not jy:
                    continue
                y_ic, y_oj = (min(jy), max(jy)) if zone == "top" else (max(jy), min(jy))
                specs.append(dict(xe=xe, side=side, zone=zone, D=D, R=R, y_ic=y_ic, y_oj=y_oj, E=0.0))
            if not specs:
                continue
            # inner (counter-side) edge vs outer edge, per on-curve point and join; off-curves
            # take the class of their neighbouring on-curve point
            inner = []
            for c in cs0:
                n_ = len(c)
                row = []
                for i, p in enumerate(c):
                    q = p if p[2] else (c[i - 1] if c[i - 1][2] else c[(i + 1) % n_])
                    cl = []
                    for sp in specs:
                        dirv = -1 if sp["zone"] == "top" else 1
                        probe = np.array([[q[0] + sp["side"] * 3, q[1] + dirv * 3]])
                        cl.append(not point_in_glyph(probe, polys)[0])
                    row.append(cl)
                inner.append(row)

            def apply():
                cs = [[list(p) for p in c] for c in cs0]
                for ci, c in enumerate(cs):
                    moves = []
                    for pi, p in enumerate(c):
                        dy = 0.0
                        for si, sp in enumerate(specs):
                            d = sp["side"] * (p[0] - sp["xe"])
                            if d < -8:
                                continue  # the stem itself and everything beyond it
                            top = sp["zone"] == "top"
                            if (top and p[1] > 580) or (not top and p[1] < -80):
                                continue
                            Ep = sp["E"] if inner[ci][pi][si] else 0.0
                            if d <= 3:  # stem edge: only the join itself (incl. Lora's small notch)
                                lo_, hi_ = ((sp["y_ic"] - 3, sp["y_oj"] + 3) if top else (sp["y_oj"] - 3, sp["y_ic"] + 3))
                                if lo_ <= p[1] <= hi_:
                                    dy += sp["D"] + Ep
                                continue
                            y_ic = sp["y_ic"]
                            if top:
                                T = 1.0 if p[1] >= y_ic - 10 else _smooth((p[1] - 250) / max(1.0, y_ic - 10 - 250))
                                T *= 1 - _smooth((p[1] - 540) / 40)
                            else:
                                T = 1.0 if p[1] <= y_ic + 10 else _smooth((250 - p[1]) / max(1.0, 250 - (y_ic + 10)))
                                T *= 1 - _smooth((-40 - p[1]) / 40)
                            u = min(1.0, d / sp["R"])
                            # the join move falls off quadratically, the inner edge's extra width
                            # linearly (spread over the whole arm, no tight turn in the counter)
                            dy += (sp["D"] * (1 - u) ** 2 + Ep * (1 - u) ** E_EXP) * T
                        moves.append(dy)
                    n_ = len(c)
                    final = list(moves)
                    for i, p in enumerate(c):
                        if p[2]:
                            continue
                        owners = []
                        for j in (i - 1, (i + 1) % n_):
                            q = cs0[ci][j]
                            if not q[2]:
                                continue
                            a, b = cs0[ci][j - 1], cs0[ci][(j + 1) % n_]
                            uu = np.array(q[:2]) - np.array(a[:2])
                            vv = np.array(b[:2]) - np.array(q[:2])
                            nu, nv = np.hypot(*uu), np.hypot(*vv)
                            if nu > 1e-6 and nv > 1e-6 and uu @ vv / nu / nv > math.cos(math.radians(10)):
                                owners.append(moves[j])
                        if owners:
                            final[i] = float(np.mean(owners))
                    for p, dy in zip(c, final):
                        p[1] += dy
                return cs

            # arm width at the stem (k = 20, 40): Lora's own, times thick[w]
            def width(cs, sp):
                prof = _arm_profile(cs, "left" if sp["side"] > 0 else "right", sp["zone"], perp=True)[2]
                v = [x for x in prof[:2] if x]
                return float(np.mean(v)) if v else None
            tgt = [width(cs0, sp) for sp in specs]
            for _ in range(iters):
                cs = apply()
                for sp, t0 in zip(specs, tgt):
                    wv = width(cs, sp)
                    if t0 is None or wv is None:
                        continue
                    dirv = -1 if sp["zone"] == "top" else 1
                    sp["E"] = float(np.clip(sp["E"] + dirv * 1.3 * (t0 * thick[w] - wv), -40, 80) if dirv > 0
                                    else np.clip(sp["E"] + dirv * 1.3 * (t0 * thick[w] - wv), -80, 40))
            cs = apply()
            for sp, t0 in zip(specs, tgt):
                report.setdefault(name, {})[(w, sp["zone"])] = (round(sp["D"]), round(sp["E"]), round(t0 or 0), round(width(cs, sp) or 0))
            set_glyph_contours(glyf, name, cs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
    return report


def remove_gsub_feature(font, tag):
    """Remove every feature record with this tag from GSUB, including its references in all
    script/language systems (remaining feature indices are renumbered). The lookups it used
    stay in the LookupList, unreferenced, so lookup indices elsewhere do not change.
    Returns the number of feature records removed."""
    gsub = font["GSUB"].table
    fl = gsub.FeatureList
    drop = {i for i, fr in enumerate(fl.FeatureRecord) if fr.FeatureTag == tag}
    if not drop:
        return 0
    keep = [i for i in range(len(fl.FeatureRecord)) if i not in drop]
    remap = {old: new for new, old in enumerate(keep)}
    fl.FeatureRecord = [fl.FeatureRecord[i] for i in keep]
    fl.FeatureCount = len(fl.FeatureRecord)

    def fix(ls):
        ls.FeatureIndex = [remap[i] for i in ls.FeatureIndex if i in remap]
        ls.FeatureCount = len(ls.FeatureIndex)
        if ls.ReqFeatureIndex in drop:
            ls.ReqFeatureIndex = 0xFFFF
        elif ls.ReqFeatureIndex != 0xFFFF:
            ls.ReqFeatureIndex = remap[ls.ReqFeatureIndex]
    for sr in gsub.ScriptList.ScriptRecord:
        if sr.Script.DefaultLangSys is not None:
            fix(sr.Script.DefaultLangSys)
        for lr in sr.Script.LangSysRecord:
            fix(lr.LangSys)
    return len(drop)


def lower_top_hump(font, name, x_from, x_to, target_top):
    """Lower the right-hand part of a glyph (points right of x_to fully, blended in over
    x_from..x_to) so its highest point reaches target_top, by scaling y about the baseline.
    Used for the bold æ, whose e half (Brygada's bold) overshoots 12 units above Lora's e while
    its a half follows the hand-edited a. One master; returns the scale applied."""
    from .geom import sample
    cs = glyph_contours(font["glyf"], name)
    top = max(float(q[1]) for c in cs for q in sample(c, 16) if q[0] >= x_to)
    if top <= target_top:
        return 1.0
    k = target_top / top
    for c in cs:
        for p in c:
            w = _smooth((p[0] - x_from) / (x_to - x_from))
            p[1] = p[1] * (1 - (1 - k) * w)
    set_glyph_contours(font["glyf"], name, cs)
    font["hmtx"][name] = (font["hmtx"][name][0], font["glyf"][name].xMin)
    return k


def ae_with_lora_e(M, L, top=(48, 32), bottom=(11, 55), blend=90.0):
    """Give the æ Lora's e (the same e as the letter e) instead of Brygada's.

    In both æ's the a half and the e half meet at two sharp notches (top and bottom), which are
    on-curve corners of the outer contour. The new outer contour is our a half (bottom notch ->
    a -> top notch; it carries the hand-edited a) followed by Lora's e half (top notch -> e ->
    bottom notch, index ranges in `top` / `bottom` = (ours, Lora's)); Lora's separate e-eye
    contour is added. Lora's e is only moved sideways (never vertically, so it keeps its exact
    height); the ends of our a half are blended onto Lora's notch points. The advance keeps
    Lora's right sidebearing. Every master gets the same point structure.
    Returns {master: (dx, xMax, advance)}."""
    from .splice import blend_ends
    rep = {}
    for w, f in M.items():
        glyf, hmtx = f["glyf"], f["hmtx"]
        ours = glyph_contours(glyf, "ae")
        lora = glyph_contours(L[w]["glyf"], "ae")
        assert [len(c) for c in lora] == [58, 15, 9] and len(ours) == 2 and len(ours[0]) == 68, "unexpected æ structure"
        oc, lc = ours[0], lora[0]
        it, jt = top
        ib, jb = bottom
        for c, i in ((oc, it), (oc, ib), (lc, jt), (lc, jb)):
            assert c[i][2], "notch is not an on-curve point"
        dx = ((oc[it][0] + oc[ib][0]) - (lc[jt][0] + lc[jb][0])) / 2
        e_sec = [[p[0] + dx, p[1], p[2]] for p in lc[jt:jb + 1]]        # top notch .. bottom notch
        a_sec = [list(p) for p in oc[ib:it + 1]]                          # bottom notch .. top notch
        blend_ends(a_sec, e_sec[-1][:2], e_sec[0][:2], blend)             # a half onto Lora's notches
        outer = a_sec + e_sec[1:-1]
        eye = [[p[0] + dx, p[1], p[2]] for p in lora[2]]
        set_glyph_contours(glyf, "ae", [outer, ours[1], eye])
        g = glyf["ae"]
        lg = L[w]["glyf"]["ae"]
        lg.recalcBounds(L[w]["glyf"])
        rsb = L[w]["hmtx"]["ae"][0] - lg.xMax
        adv = int(round(g.xMax + rsb))
        hmtx["ae"] = (adv, g.xMin)
        rep[w] = (round(dx, 1), g.xMax, adv)
    return rep
