"""Splice sections of Brygada's outlines into the Lora-based glyphs.

A section is the part of a contour between two cuts. A cut is where a straight line (y = v or
x = v) crosses the contour, choosing the crossing nearest to a reference coordinate (usually a
stem edge measured from ink runs). Lora's section is replaced by Brygada's corresponding
section, mapped into Lora's coordinates (piecewise-linear x map on stem edges, or a translation),
with its end points snapped onto Lora's cut points. Same rules in every master, so the result
stays point-compatible.
"""
import math

import numpy as np

from .geom import explicitize, segments


def crossings(c, axis, v):
    """All crossings of explicitized contour c with the line axis=v.
    Returns [(pos_along_line, seg_start, ctrl, seg_end, t)]."""
    k = 1 if axis == "y" else 0  # coordinate that is constant on the line
    o = 1 - k
    out = []
    for a, ctrl, b in segments(c):
        P0, P2 = np.array(c[a][:2]), np.array(c[b][:2])
        if ctrl is None:
            if P0[k] == P2[k] or (P0[k] - v) * (P2[k] - v) > 0:
                continue
            t = (v - P0[k]) / (P2[k] - P0[k])
            if not (0 <= t < 1):
                continue
            out.append((P0[o] + t * (P2[o] - P0[o]), a, None, b, t))
        else:
            P1 = np.array(c[ctrl][:2])
            A = P0[k] - 2 * P1[k] + P2[k]
            B = 2 * (P1[k] - P0[k])
            C = P0[k] - v
            ts = np.roots([A, B, C]) if abs(A) > 1e-9 else (np.array([-C / B]) if abs(B) > 1e-12 else [])
            for t in np.atleast_1d(ts):
                if abs(np.imag(t)) > 1e-9:
                    continue
                t = float(np.real(t))
                if 0 <= t < 1:
                    q = (1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t * t * P2
                    out.append((q[o], a, ctrl, b, t))
    return out


def split(c, cut):
    """Insert an on-curve point at the crossing. Returns (new contour, index of the point)."""
    pos, a, ctrl, b, t = cut
    c = [list(p) for p in c]
    if ctrl is None:
        P0, P2 = np.array(c[a][:2]), np.array(c[b][:2])
        S = P0 + (P2 - P0) * t
        if t < 1e-6:
            return c, a
        idx = a + 1 if b != 0 else len(c)
        c.insert(idx, [S[0], S[1], 1])
        return c, idx
    P0, P1, P2 = (np.array(c[i][:2]) for i in (a, ctrl, b))
    if t < 1e-6:
        return c, a
    Q0 = P0 + (P1 - P0) * t
    Q1 = P1 + (P2 - P1) * t
    S = Q0 + (Q1 - Q0) * t
    c[ctrl] = [Q0[0], Q0[1], 0]
    c.insert(ctrl + 1, [S[0], S[1], 1])
    c.insert(ctrl + 2, [Q1[0], Q1[1], 0])
    return c, ctrl + 1


def cut_at(c, spec):
    """spec: (axis, value, ref). Split c at the crossing nearest ref. Returns (c, index)."""
    axis, v, ref = spec
    cr = crossings(c, axis, v)
    if not cr:
        raise ValueError(f"no crossing for {spec}")
    best = min(cr, key=lambda q: abs(q[0] - ref))
    return split(c, best)


def section(c, i, j):
    n = len(c)
    return [c[(i + k) % n] for k in range((j - i) % n + 1)]


def splice_section(lc, bc, lcuts, bcuts, mapping):
    """Replace lc's section between lcuts (in contour order) by bc's section between bcuts.
    mapping: function (x, y) -> (x, y) from Brygada to Lora coordinates."""
    lc = explicitize(lc)
    bc = explicitize(bc)
    lc, ia = cut_at(lc, lcuts[0])
    A = list(lc[ia])
    lc, ib = cut_at(lc, lcuts[1])
    ia = _find(lc, lcuts[0][0], lcuts[0][1], A)
    bc, ja = cut_at(bc, bcuts[0])
    Ab = list(bc[ja])
    bc, jb = cut_at(bc, bcuts[1])
    ja = _find(bc, bcuts[0][0], bcuts[0][1], Ab)
    bsec = section(bc, ja, jb)
    mapped = [[*mapping(p[0], p[1]), p[2]] for p in bsec]
    # snap ends exactly onto Lora's cut points
    mapped[0][:2] = lc[ia][:2]
    mapped[-1][:2] = lc[ib][:2]
    n = len(lc)
    rest = section(lc, ib, ia)[1:-1]  # the part of Lora's contour we keep
    return [list(lc[ia])] + mapped[1:-1] + [list(lc[ib])] + rest


def _find(c, axis, v, P):
    """Index of the on-curve point lying on the cut line closest to P."""
    k = 1 if axis == "y" else 0
    cands = [i for i, p in enumerate(c) if p[2] and abs(p[k] - v) < 1e-6]
    if P is None or not cands:
        return cands[0]
    return min(cands, key=lambda i: (c[i][0] - P[0]) ** 2 + (c[i][1] - P[1]) ** 2)


def pw_linear(pairs):
    """Piecewise-linear 1-D map through (src, dst) pairs, constant-offset extrapolation."""
    pairs = sorted(pairs)
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    def f(x):
        if x <= xs[0]:
            return x + (ys[0] - xs[0])
        if x >= xs[-1]:
            return x + (ys[-1] - xs[-1])
        return float(np.interp(x, xs, ys))
    return f


def smooth_joint(c, i, side="after"):
    """Make the joint at on-curve c[i] G1: align the off-curve on the given side with the
    tangent of the other side (keeping its distance)."""
    n = len(c)
    P = np.array(c[i][:2])
    prev, nxt = c[(i - 1) % n], c[(i + 1) % n]
    if side == "after":
        ref, mov = np.array(prev[:2]), (i + 1) % n
    else:
        ref, mov = np.array(nxt[:2]), (i - 1) % n
    if c[mov][2]:
        return c
    d = P - ref
    L = np.hypot(*d)
    if L < 1e-6:
        return c
    d /= L
    dist = np.hypot(*(np.array(c[mov][:2]) - P))
    Q = P + d * dist
    c[mov][0], c[mov][1] = Q[0], Q[1]
    return c


# ---------------------------------------------------------------- structure-locked cuts
def locate(c, spec):
    """Reference-master cut: (a, ctrl, b, t) of the chosen crossing (c explicitized).
    Degenerate crossings at segment ends are nudged inside the segment."""
    axis, v, ref = spec
    cr = crossings(c, axis, v)
    if not cr:
        raise ValueError(f"no crossing for {spec}")
    pos, a, ctrl, b, t = min(cr, key=lambda q: abs(q[0] - ref))
    return (a, ctrl, b, min(max(t, 0.02), 0.98), axis, v)


def relocate(c, loc):
    """Same segment in another master: parameter where it crosses the same line (clamped)."""
    a, ctrl, b, t0, axis, v = loc
    k = 1 if axis == "y" else 0
    P0, P2 = np.array(c[a][:2]), np.array(c[b][:2])
    if ctrl is None:
        t = (v - P0[k]) / (P2[k] - P0[k]) if P2[k] != P0[k] else t0
    else:
        P1 = np.array(c[ctrl][:2])
        A = P0[k] - 2 * P1[k] + P2[k]
        B = 2 * (P1[k] - P0[k])
        C = P0[k] - v
        ts = np.roots([A, B, C]) if abs(A) > 1e-9 else (np.array([-C / B]) if abs(B) > 1e-12 else np.array([t0]))
        ts = [float(np.real(q)) for q in np.atleast_1d(ts) if abs(np.imag(q)) < 1e-9]
        t = min(ts, key=lambda q: abs(q - t0)) if ts else t0
    return (a, ctrl, b, min(max(t, 0.02), 0.98), axis, v)


def split_loc(c, loc):
    a, ctrl, b, t, axis, v = loc
    return split(c, (0, a, ctrl, b, t))


def splice_locked(lc, bc, lloc, bloc, mapping, blend=70.0, tangents=False):
    """lc, bc explicitized; lloc/bloc: (loc_A, loc_B) for this master (same structure in all)."""
    # split B first when it lies after A in index order so A's indices stay valid (and vice versa)
    def two_cuts(c, la, lb):
        first, second = (la, lb) if la[0] > lb[0] else (lb, la)
        c, i1 = split_loc(c, first)
        c, i2 = split_loc(c, second)
        # the second insertion happened at a lower index -> first point moved by +1 (or +2 for curves)
        shift = (2 if second[1] is not None else 1)
        i1 += shift
        return (c, i1, i2) if first is la else (c, i2, i1)
    lc, ia, ib = two_cuts(lc, *lloc)
    bc, ja, jb = two_cuts(bc, *bloc)
    bsec = section(bc, ja, jb)
    mapped = [[*mapping(p[0], p[1]), p[2]] for p in bsec]
    blend_ends(mapped, lc[ia][:2], lc[ib][:2], blend)
    rest = section(lc, ib, ia)[1:-1]
    out = [list(lc[ia])] + mapped[1:-1] + [list(lc[ib])] + rest
    if tangents:
        n_sec = len(mapped)
        out = smooth_joint(out, 0, "after")
        out = smooth_joint(out, n_sec - 1, "before")
    return out


def blend_ends(pts, A, B, S0):
    """Snap the section's ends onto A and B, fading each correction out along the section
    (arc length S0) instead of moving only the end point."""
    import numpy as np
    xy = np.array([p[:2] for p in pts], float)
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    total = seg[-1] if len(seg) else 0
    dA = np.array(A) - xy[0]
    dB = np.array(B) - xy[-1]
    for i, p in enumerate(pts):
        sa, sb = seg[i], total - seg[i]
        wa = max(0.0, 1 - sa / S0) ** 2 if S0 > 0 else (1.0 if i == 0 else 0.0)
        wb = max(0.0, 1 - sb / S0) ** 2 if S0 > 0 else (1.0 if i == len(pts) - 1 else 0.0)
        p[0] += dA[0] * wa + dB[0] * wb
        p[1] += dA[1] * wa + dB[1] * wb
    pts[0][:2] = list(A)
    pts[-1][:2] = list(B)
