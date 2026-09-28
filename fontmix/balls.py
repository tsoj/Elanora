"""Turn teardrop terminals into round ball terminals (point-structure deterministic)."""
import math

import numpy as np

from .geom import arc_points, explicitize, fit_circle, inscribed_circle, sample, signed_area, tangent_points


def rotate_to(c, k):
    return c[k:] + c[:k]


def find_run(c, D, Rd):
    """c explicitized. Return (s, e): on-curve indices bounding the maximal cyclic run of
    points within Rd of D. Points strictly between s and e belong to the terminal."""
    n = len(c)
    inside = [math.hypot(p[0] - D[0], p[1] - D[1]) < Rd for p in c]
    if all(inside) or not any(inside):
        raise ValueError("bad terminal detection radius")
    # longest cyclic run
    best, cur, best_start = 0, 0, 0
    for i in range(2 * n):
        if inside[i % n]:
            cur += 1
            if cur > best and cur <= n:
                best, best_start = cur, i - cur + 1
        else:
            cur = 0
    a, b = best_start % n, (best_start + best - 1) % n
    s = (a - 1) % n
    while not c[s][2]:
        s = (s - 1) % n
    e = (b + 1) % n
    while not c[e][2]:
        e = (e + 1) % n
    return s, e


def terminal_circle(c, s, e, trim=0.2):
    """Fit a circle to the far part of the terminal between s and e."""
    n = len(c)
    sub = rotate_to(c, s)[: (e - s) % n + 1]
    pts = []
    for i in range(len(sub) - 1):
        pass
    # sample along the run
    run_c = sub
    samples = []
    i = 0
    while i < len(run_c) - 1:
        P0 = np.array(run_c[i][:2])
        if run_c[i + 1][2]:
            P2 = np.array(run_c[i + 1][:2])
            for t in np.linspace(0, 1, 6, endpoint=False):
                samples.append(P0 + (P2 - P0) * t)
            i += 1
        else:
            P1, P2 = np.array(run_c[i + 1][:2]), np.array(run_c[i + 2][:2])
            for t in np.linspace(0, 1, 10, endpoint=False):
                samples.append((1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t * t * P2)
            i += 2
    samples = np.array(samples)
    k = int(len(samples) * trim)
    far = samples[k : len(samples) - k] if len(samples) - 2 * k > 5 else samples
    return fit_circle(far)


def _unit(v):
    d = math.hypot(v[0], v[1])
    return (v[0] / d, v[1] / d)


def _line_isect(P, u, Q, v):
    """P + t u = Q + s v -> (t, s) or None."""
    det = u[0] * (-v[1]) - u[1] * (-v[0])
    if abs(det) < 1e-9:
        return None
    rx, ry = Q[0] - P[0], Q[1] - P[1]
    t = (rx * (-v[1]) - ry * (-v[0])) / det
    s = (u[0] * ry - u[1] * rx) / det
    return t, s


def _join(P, u, C, r, sigma, entering, window=math.radians(75)):
    """Quadratic P-K-T joining a stroke end P (G1 with direction u) to the circle (C, r) at T
    (G1 with the circle). entering: stroke -> circle (u = travel dir at P).
    not entering: circle -> stroke (u = reversed travel dir at P)."""
    dP = math.hypot(P[0] - C[0], P[1] - C[1])
    th0 = math.atan2(P[1] - C[1], P[0] - C[0])
    lim = 1.3 * max(r, dP - r) + r * 0.3
    best = None
    N = 300
    for k in range(-N, N + 1):
        th = th0 + window * k / N
        T = (C[0] + r * math.cos(th), C[1] + r * math.sin(th))
        tan = (-math.sin(th) * sigma, math.cos(th) * sigma)
        res = _line_isect(P, u, T, (-tan[0], -tan[1]) if entering else tan)
        if res is None:
            continue
        a, b = res
        if a <= 0.5 or b <= 0.5 or a > lim or b > lim:
            continue
        K = (P[0] + a * u[0], P[1] + a * u[1])
        if math.hypot(K[0] - C[0], K[1] - C[1]) < r:
            continue
        score = abs(math.log(a / b)) + 0.3 * (a + b) / lim
        if best is None or score < best[0]:
            best = (score, th, T, K)
    return best


def ballify(c, s, e, C, r, n_off=None, max_step=math.radians(38)):
    """Replace points strictly between on-curve s and e with: a smooth join from P_s onto the
    circle (C, r), an arc around the far side, and a smooth join back to P_e."""
    n = len(c)
    sigma = -1 if signed_area(c) < 0 else 1
    Ps, Pe = c[s], c[e]
    Qp, Qn = c[(s - 1) % n], c[(e + 1) % n]
    u_in = _unit((Ps[0] - Qp[0], Ps[1] - Qp[1]))  # travel direction arriving at Ps
    u_out = _unit((Pe[0] - Qn[0], Pe[1] - Qn[1]))  # reversed travel direction leaving Pe
    th_s = math.atan2(Ps[1] - C[1], Ps[0] - C[0])
    th_e = math.atan2(Pe[1] - C[1], Pe[0] - C[0])
    js = _join(Ps[:2], u_in, C, r, sigma, True)
    je = _join(Pe[:2], u_out, C, r, sigma, False)
    if js is None or je is None:
        raise ValueError("no smooth join found")
    _, ths, Ts, Ks = js
    _, the, Te, Ke = je
    sweep = (sigma * (the - ths)) % (2 * math.pi)
    if n_off is None:
        n_off = max(3, math.ceil(sweep / max_step))
    offs = arc_points(C, r, ths, sigma * sweep, n_off)
    c2 = rotate_to([list(p) for p in c], s)
    m = (e - s) % n
    rest = c2[m:]  # starts at e
    new = ([list(Ps), [Ks[0], Ks[1], 0], [Ts[0], Ts[1], 1]] + [[x, y, 0] for x, y in offs]
           + [[Te[0], Te[1], 1], [Ke[0], Ke[1], 0]] + rest)
    return new, n_off, math.degrees(sweep)


def _prev_on(c, i):
    n = len(c)
    i = (i - 1) % n
    while not c[i][2]:
        i = (i - 1) % n
    return i


def _next_on(c, i):
    n = len(c)
    i = (i + 1) % n
    while not c[i][2]:
        i = (i + 1) % n
    return i


def ball_terminal(cs, D, Rd, rtarget=None, grow=1.0, shift=(0.0, 0.0), out_shift=0.6, margin=1.08,
                  others=None, run_k=1.25):
    """cs: {master: explicitized contour} (point-compatible). Detection uses the first master.
    D: rough terminal centre (first master), Rd: search radius for the inscribed circle.
    rtarget: {master: radius} (else inscribed radius * grow). The ball grows outward (away from
    the stroke) by out_shift * (r_new - r_inscribed); shift is an extra offset in font units
    (scaled per master by r_new / r_new_first).
    Returns ({master: new contour}, info)."""
    keys = list(cs)
    ref = cs[keys[0]]
    others = others or {k: [] for k in keys}
    ix, iy, ir = inscribed_circle([ref] + others[keys[0]], D, Rd)
    s, e = find_run(ref, (ix, iy), ir * run_k)
    n = len(ref)
    circ = {}
    r0 = None
    for k in keys:
        if k == keys[0]:
            cx, cy, r = ix, iy, ir
        else:
            idx = [(s + j) % n for j in range((e - s) % n + 1)]
            dx = np.mean([cs[k][i][0] - ref[i][0] for i in idx])
            dy = np.mean([cs[k][i][1] - ref[i][1] for i in idx])
            cx, cy, r = inscribed_circle([cs[k]] + others[k], (ix + dx, iy + dy), Rd * 1.4)
        rn = rtarget[k] if rtarget else r * grow
        if r0 is None:
            r0 = rn
        c = cs[k]
        mx, my = (c[s][0] + c[e][0]) / 2, (c[s][1] + c[e][1]) / 2
        ux, uy = cx - mx, cy - my
        d = math.hypot(ux, uy) or 1.0
        g = out_shift * (rn - r)
        sc = rn / r0
        circ[k] = (cx + ux / d * g + shift[0] * sc, cy + uy / d * g + shift[1] * sc, rn)
    # extend run until neighbours are safely outside every master's ball
    for _ in range(20):
        ok = True
        for k in keys:
            c = cs[k]
            cx, cy, r = circ[k]
            if math.hypot(c[(s - 1) % n][0] - cx, c[(s - 1) % n][1] - cy) < r * margin:
                s = _prev_on(ref, s)
                ok = False
                break
            if math.hypot(c[(e + 1) % n][0] - cx, c[(e + 1) % n][1] - cy) < r * margin:
                e = _next_on(ref, e)
                ok = False
                break
        if ok:
            break
    out, n_off, info = {}, None, {}
    for k in keys:
        cx, cy, r = circ[k]
        new, n_off, sweep = ballify(cs[k], s, e, (cx, cy), r, n_off=n_off)
        out[k] = new
        info[k] = dict(run=(s, e), circle=(cx, cy, r), sweep=sweep, n_off=n_off)
    return out, info


# ---------------------------------------------------------------- Brygada-style balls (v2)
def _ray_circle(P, d, C, r):
    """Smallest t > 0 with |P + t d - C| = r, or None."""
    fx, fy = P[0] - C[0], P[1] - C[1]
    b = fx * d[0] + fy * d[1]
    c = fx * fx + fy * fy - r * r
    disc = b * b - c
    if disc < 0:
        return None
    s = math.sqrt(disc)
    ts = [t for t in (-b - s, -b + s) if t > 1e-6]
    return min(ts) if ts else None


def ballify_v2(c, s, e, C, r, n_off=None, max_step=math.radians(36)):
    """Brygada construction: the outer edge (arriving at on-curve s) flows tangentially onto the
    circle; the arc runs round the far side; the inner edge (leaving from on-curve e) enters the
    circle in a straight line, leaving a sharp inner corner where it meets the ball."""
    n = len(c)
    sigma = -1 if signed_area(c) < 0 else 1
    Ps, Pe = c[s], c[e]
    Qp, Qn = c[(s - 1) % n], c[(e + 1) % n]
    u_in = _unit((Ps[0] - Qp[0], Ps[1] - Qp[1]))
    js = _join(Ps[:2], u_in, C, r, sigma, True)
    if js is None:
        raise ValueError("no smooth outer join")
    _, ths, Ts, Ks = js
    d = _unit((Pe[0] - Qn[0], Pe[1] - Qn[1]))  # from the inner edge towards the ball
    t = _ray_circle(Pe[:2], d, C, r)
    if t is None:  # inner edge misses the ball: aim at the nearest point of the circle
        a = math.atan2(Pe[1] - C[1], Pe[0] - C[0])
        X = (C[0] + r * math.cos(a), C[1] + r * math.sin(a))
    else:
        X = (Pe[0] + t * d[0], Pe[1] + t * d[1])
    thx = math.atan2(X[1] - C[1], X[0] - C[0])
    sweep = (sigma * (thx - ths)) % (2 * math.pi)
    if n_off is None:
        n_off = max(3, math.ceil(sweep / max_step))
    offs = arc_points(C, r, ths, sigma * sweep, n_off)
    c2 = rotate_to([list(p) for p in c], s)
    m = (e - s) % n
    rest = c2[m:]
    new = ([list(Ps), [Ks[0], Ks[1], 0], [Ts[0], Ts[1], 1]] + [[x, y, 0] for x, y in offs]
           + [[X[0], X[1], 1]] + rest)
    return new, n_off, math.degrees(sweep)


def _outer_contact(c, s, e, C, r_in):
    """Point where the inscribed circle touches the outer edge (the side arriving at s)."""
    n = len(c)
    m = (e - s) % n
    idx = [(s - 4 + j) % n for j in range(4 + m // 2 + 1)]
    sub = [c[i] for i in idx]
    pts = []
    for i in range(len(sub) - 1):
        a, b = np.array(sub[i][:2]), np.array(sub[i + 1][:2])
        for t in np.linspace(0, 1, 12):
            pts.append(a + (b - a) * t)
    pts = np.array(pts)
    dd = np.hypot(pts[:, 0] - C[0], pts[:, 1] - C[1])
    return pts[int(np.argmin(dd))]


def ball_terminal_v2(cs, D, Rd, rtarget, hang=0.0, shift=(0.0, 0.0), margin=1.06, others=None,
                     run_k=1.25):
    """Grow the teardrop's inscribed circle to rtarget while staying tangent to the outer edge
    (the ball grows into the curl, like Brygada's), then build it with ballify_v2.
    hang: extra move of the centre away from the outer edge, in units of the new radius."""
    keys = list(cs)
    ref = cs[keys[0]]
    others = others or {k: [] for k in keys}
    ix, iy, ir = inscribed_circle([ref] + others[keys[0]], D, Rd)
    s, e = find_run(ref, (ix, iy), ir * run_k)
    n = len(ref)
    circ = {}
    r0 = rtarget[keys[0]]
    for k in keys:
        if k == keys[0]:
            cx, cy, r = ix, iy, ir
        else:
            idx = [(s + j) % n for j in range((e - s) % n + 1)]
            dx = np.mean([cs[k][i][0] - ref[i][0] for i in idx])
            dy = np.mean([cs[k][i][1] - ref[i][1] for i in idx])
            cx, cy, r = inscribed_circle([cs[k]] + others[k], (ix + dx, iy + dy), Rd * 1.4)
        X = _outer_contact(cs[k], s, e, (cx, cy), r)
        ux, uy = cx - X[0], cy - X[1]
        dl = math.hypot(ux, uy) or 1.0
        ux, uy = ux / dl, uy / dl
        R = rtarget[k]
        sc = R / r0
        circ[k] = (X[0] + ux * R * (1 + hang) + shift[0] * sc, X[1] + uy * R * (1 + hang) + shift[1] * sc, R)
    for _ in range(25):
        ok = True
        for k in keys:
            c = cs[k]
            cx, cy, r = circ[k]
            near = lambda i: math.hypot(c[i % n][0] - cx, c[i % n][1] - cy) < r * margin
            if near(s) or near(s - 1):
                s = _prev_on(ref, s)
                ok = False
                break
            if near(e) or near(e + 1):
                e = _next_on(ref, e)
                ok = False
                break
        if ok:
            break
    out, n_off, info = {}, None, {}
    for k in keys:
        cx, cy, r = circ[k]
        new, n_off, sweep = ballify_v2(cs[k], s, e, (cx, cy), r, n_off=n_off)
        out[k] = new
        info[k] = dict(run=(s, e), circle=(cx, cy, r), sweep=sweep, n_off=n_off)
    return out, info
