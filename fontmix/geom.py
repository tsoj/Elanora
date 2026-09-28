"""Geometry on TrueType quadratic contours.

A contour is a list of [x, y, on] (on: 1 = on-curve, 0 = off-curve).
"""
import math

import numpy as np


# ---------------------------------------------------------------- contour io
def glyph_contours(glyf, name):
    g = glyf[name]
    coords, ends, flags = g.getCoordinates(glyf)
    out, s = [], 0
    for e in ends:
        out.append([[float(coords[i][0]), float(coords[i][1]), flags[i] & 1] for i in range(s, e + 1)])
        s = e + 1
    return out


def set_glyph_contours(glyf, name, contours):
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates, flagOnCurve

    g = glyf[name]
    if g.isComposite():
        del g.components
        if hasattr(g, "flags"):
            pass
    coords, flags, ends = [], [], []
    for c in contours:
        for x, y, on in c:
            coords.append((round(x), round(y)))
            flags.append(flagOnCurve if on else 0)
        ends.append(len(coords) - 1)
    g.coordinates = GlyphCoordinates(coords)
    g.flags = bytearray(flags)
    g.endPtsOfContours = ends
    g.numberOfContours = len(contours)
    g.program = None
    if hasattr(g, "program"):
        from fontTools.ttLib.tables import ttProgram

        g.program = ttProgram.Program()
        g.program.fromBytecode(b"")
    g.recalcBounds(glyf)


def explicitize(c):
    """Insert implied on-curve points so every off-curve sits between two on-curves."""
    n = len(c)
    out = []
    for i in range(n):
        p, q = c[i], c[(i + 1) % n]
        out.append(list(p))
        if not p[2] and not q[2]:
            out.append([(p[0] + q[0]) / 2, (p[1] + q[1]) / 2, 1])
    # rotate so contour starts on an on-curve point
    k = next(i for i, p in enumerate(out) if p[2])
    return out[k:] + out[:k]


def signed_area(c, steps=8):
    pts = sample(c, steps)
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2


def segments(c):
    """Yield (i_start, i_ctrl or None, i_end) for an explicitized contour."""
    n = len(c)
    i = 0
    while i < n:
        j = (i + 1) % n
        if c[j][2]:
            yield i, None, j
            i += 1
        else:
            yield i, j, (i + 2) % n
            i += 2


def sample(c, steps=8, run=None):
    """Sample points along the (explicitized) contour; optional run=(s,e) index range (cyclic)."""
    c = c if all(c[i][2] or (c[i - 1][2] and c[(i + 1) % len(c)][2]) for i in range(len(c))) else explicitize(c)
    pts = []
    n = len(c)
    for a, ctrl, b in segments(c):
        if run is not None and not in_run(a, run, n):
            continue
        P0, P2 = np.array(c[a][:2]), np.array(c[b][:2])
        if ctrl is None:
            for t in np.linspace(0, 1, steps, endpoint=False):
                pts.append(P0 + (P2 - P0) * t)
        else:
            P1 = np.array(c[ctrl][:2])
            for t in np.linspace(0, 1, steps, endpoint=False):
                pts.append((1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t * t * P2)
    return np.array(pts)


def in_run(i, run, n):
    s, e = run
    return (i - s) % n < (e - s) % n


# ---------------------------------------------------------------- circles
def fit_circle(pts):
    """Kasa least-squares circle fit -> (cx, cy, r)."""
    x, y = pts[:, 0], pts[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    b = x * x + y * y
    (cx, cy, k), *_ = np.linalg.lstsq(A, b, rcond=None)
    return cx, cy, math.sqrt(k + cx * cx + cy * cy)


def tangent_points(Q, C, r):
    """Two tangent points from external point Q to circle (C, r)."""
    dx, dy = Q[0] - C[0], Q[1] - C[1]
    d = math.hypot(dx, dy)
    if d <= r * 1.0001:
        return None
    base = math.atan2(dy, dx)
    alpha = math.acos(r / d)
    return [(C[0] + r * math.cos(base + s * alpha), C[1] + r * math.sin(base + s * alpha), base + s * alpha) for s in (1, -1)]


def arc_points(C, r, th0, sweep, n_off):
    """Off-curve points of a quadratic B-spline approximating an arc (implied on-curves on circle).
    sweep is signed (radians). Returns list of off-curve (x, y)."""
    d = sweep / n_off
    R = r / math.cos(abs(d) / 2)
    return [(C[0] + R * math.cos(th0 + (k + 0.5) * d), C[1] + R * math.sin(th0 + (k + 0.5) * d)) for k in range(n_off)]


def ang_norm(a):
    return a % (2 * math.pi)


def _polys(contours, steps=16):
    return [sample(c, steps) for c in contours]


def point_in_glyph(P, polys):
    """Nonzero winding test for array of points P (N,2)."""
    wind = np.zeros(len(P), int)
    x, y = P[:, 0][:, None], P[:, 1][:, None]
    for poly in polys:
        x0, y0 = poly[:, 0][None, :], poly[:, 1][None, :]
        x1, y1 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
        up = (y0 <= y) & (y1 > y)
        down = (y0 > y) & (y1 <= y)
        cross = (x1 - x0) * (y - y0) - (x - x0) * (y1 - y0)
        wind += np.sum(up & (cross > 0), axis=1) - np.sum(down & (cross < 0), axis=1)
    return wind != 0


def inscribed_circle(contours, D, search_R, step=3.0):
    """Largest circle inside the glyph whose centre lies within search_R of D."""
    polys = _polys(contours)
    allpts = np.concatenate(polys)
    best = None
    cx, cy, R, st = D[0], D[1], search_R, step
    for _ in range(3):
        g = np.arange(-R, R + st, st)
        X, Y = np.meshgrid(cx + g, cy + g)
        P = np.c_[X.ravel(), Y.ravel()]
        P = P[np.hypot(P[:, 0] - D[0], P[:, 1] - D[1]) <= search_R]
        P = P[point_in_glyph(P, polys)]
        if not len(P):
            break
        dist = np.min(np.hypot(P[:, None, 0] - allpts[None, :, 0], P[:, None, 1] - allpts[None, :, 1]), axis=1)
        i = int(np.argmax(dist))
        best = (P[i, 0], P[i, 1], dist[i])
        cx, cy, R, st = P[i, 0], P[i, 1], st * 3, st / 3
    return best


def embolden(contours, delta, miter_limit=1.15, concave_limit=4.0, ink_aware=True):
    """Offset every contour outward (away from the ink) by delta, moving each point along its
    corner bisector. Convex corners are miter-limited (no spikes); concave corners take the
    full miter so the offset edges meet instead of crossing. Keeps the point structure."""
    ink_polys = [sample(c, 12) for c in contours] if ink_aware else None
    out = []
    for c in contours:
        n = len(c)
        xy = np.array([p[:2] for p in c], float)
        area = 0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1])
        prev = xy - np.roll(xy, 1, axis=0)
        nxt = np.roll(xy, -1, axis=0) - xy

        def nrm(v):
            L = np.maximum(1e-9, np.hypot(v[:, 0], v[:, 1]))[:, None]
            v = v / L
            return np.c_[-v[:, 1], v[:, 0]]
        n1, n2 = nrm(prev), nrm(nxt)
        bis = n1 + n2
        bl = np.hypot(bis[:, 0], bis[:, 1])
        bis = np.where(bl[:, None] < 1e-6, n1, bis / np.maximum(bl, 1e-9)[:, None])
        cross = prev[:, 0] * nxt[:, 1] - prev[:, 1] * nxt[:, 0]
        if ink_polys is not None:
            # self-crossing contours: parts run the "wrong" way, so ask where the ink is
            fwd = point_in_glyph(xy + bis * 3, ink_polys)
            back = point_in_glyph(xy - bis * 3, ink_polys)
            flip = fwd & ~back
            bis = np.where(flip[:, None], -bis, bis)
            n1 = np.where(flip[:, None], -n1, n1)
            area_sign = np.where(flip, -np.sign(area), np.sign(area))
        else:
            area_sign = np.sign(area)
        convex = cross * area_sign > 0
        lim = np.where(convex, miter_limit, concave_limit)
        cosh = np.clip((bis * n1).sum(axis=1), 1 / lim, 1.0)
        off = bis * (delta / cosh)[:, None]
        out.append([[xy[i, 0] + off[i, 0], xy[i, 1] + off[i, 1], c[i][2]] for i in range(n)])
    return out


def pathops_contours(contours):
    """Simplify (remove overlaps / self-intersections) with skia-pathops, back to TT contours."""
    import pathops
    from fontTools.pens.recordingPen import RecordingPen
    p = pathops.Path()
    pen = p.getPen()
    for c in contours:
        ec = explicitize(c)
        pen.moveTo(tuple(ec[0][:2]))
        i = 1
        n = len(ec)
        while i <= n:
            q = ec[i % n]
            if q[2]:
                pen.lineTo(tuple(q[:2]))
                i += 1
            else:
                pen.qCurveTo(tuple(q[:2]), tuple(ec[(i + 1) % n][:2]))
                i += 2
        pen.closePath()
    p.simplify(fix_winding=True)
    rec = RecordingPen()
    p.draw(rec)
    out, cur = [], None
    for op, args in rec.value:
        if op == "moveTo":
            cur = [[args[0][0], args[0][1], 1]]
        elif op == "lineTo":
            cur.append([args[0][0], args[0][1], 1])
        elif op == "qCurveTo":
            if cur is None:
                cur = []
            for q in args[:-1]:
                cur.append([q[0], q[1], 0])
            if args[-1] is not None:
                cur.append([args[-1][0], args[-1][1], 1])
        elif op == "curveTo":
            raise ValueError("cubic in pathops output")
        elif op in ("closePath", "endPath"):
            if cur is None:
                continue
            if not any(p[2] for p in cur):
                cur = explicitize(cur)
            if len(cur) > 1 and cur[-1][:2] == cur[0][:2]:
                cur.pop()
            out.append(cur)
            cur = None
    # TrueType orientation: outer contours clockwise (negative area), holes counter-clockwise
    def area(c):
        pts = sample(c, 8)
        return 0.5 * float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1]))
    if out and area(max(out, key=lambda c: abs(area(c)))) > 0:
        out = [[c[0]] + c[1:][::-1] for c in out]
    return out


def canonical(contours):
    """Deterministic contour order / start points so two masters can be compared."""
    res = []
    for c in contours:
        ons = [i for i, p in enumerate(c) if p[2]]
        k = min(ons, key=lambda i: (round(c[i][1]), round(c[i][0])))
        res.append(c[k:] + c[:k])
    res.sort(key=lambda c: (round(min(p[0] for p in c)), round(min(p[1] for p in c))))
    return res


def fix_coincident(contours, push=12.0, tol=1.5):
    """Points of one contour lying on another contour's edge are pushed into that contour, so
    touching pieces overlap instead of meeting edge-to-edge (avoids hairline seams)."""
    polys = [sample(c, 16) for c in contours]
    out = [[list(p) for p in c] for c in contours]
    for i, c in enumerate(out):
        for p in c:
            for j, poly in enumerate(polys):
                if j == i:
                    continue
                d = np.hypot(poly[:, 0] - p[0], poly[:, 1] - p[1])
                k = int(np.argmin(d))
                if d[k] < tol:
                    a, b = poly[k - 1], poly[(k + 1) % len(poly)]
                    t = b - a
                    nrm_out = np.array([-t[1], t[0]]) / max(1e-9, np.hypot(*t))
                    p[0] -= nrm_out[0] * push
                    p[1] -= nrm_out[1] * push
                    break
    return out
