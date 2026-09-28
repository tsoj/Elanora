"""Which Brygada sections go where (roman). Cut specs: (axis, value, ref) where ref is
("run", i, side) -> x of ink run i's left(0)/right(1) edge on that line, or ("at", v)."""
import numpy as np

from .figures import brygada_contours
from .geom import explicitize, glyph_contours, set_glyph_contours
from .splice import pw_linear, splice_section, smooth_joint, cut_at, section
from .transplant import bry_instance
from .widen import ink_runs


def _resolve(spec, contours):
    axis, v, ref = spec
    if ref[0] == "run":
        runs = ink_runs(contours, v) if axis == "y" else None
        r = runs[ref[1]]
        return (axis, v, r[ref[2]])
    return (axis, v, ref[1])


def _stem_map(lcs, bcs, y, which=None):
    lr, br = ink_runs(lcs, y), ink_runs(bcs, y)
    if which is not None:
        lr = [lr[i] for i in which]
        br = [br[i] for i in which]
    assert len(lr) == len(br), (lr, br)
    pairs = []
    for (a, b), (c, d) in zip(br, lr):
        pairs += [(a, c), (b, d)]
    fx = pw_linear(pairs)
    return lambda x, yy: (fx(x), yy)


# arches / bowls: sections whose cuts sit on straight stems
ARCH_JOBS = {
    # n: outer arch (left stem right edge @490 -> right stem outer edge @250), inner arch
    "n": [dict(l=[("y", 490, ("run", 0, 1)), ("y", 250, ("run", 1, 1))],
               b=[("y", 490, ("run", 0, 1)), ("y", 250, ("run", 1, 1))]),
          dict(l=[("y", 250, ("run", 1, 0)), ("y", 250, ("run", 0, 1))],
               b=[("y", 250, ("run", 1, 0)), ("y", 250, ("run", 0, 1))])],
}
ARCH_JOBS["h"] = ARCH_JOBS["n"]
ARCH_JOBS["m"] = [dict(l=[("y", 490, ("run", 0, 1)), ("y", 250, ("run", 2, 1))],
                       b=[("y", 490, ("run", 0, 1)), ("y", 250, ("run", 2, 1))]),
                  dict(l=[("y", 250, ("run", 2, 0)), ("y", 250, ("run", 1, 1))],
                       b=[("y", 250, ("run", 2, 0)), ("y", 250, ("run", 1, 1))]),
                  dict(l=[("y", 250, ("run", 1, 0)), ("y", 250, ("run", 0, 1))],
                       b=[("y", 250, ("run", 1, 0)), ("y", 250, ("run", 0, 1))])]
# u: outer (right stem inner edge @20 below the join -> left stem outer edge @300), inner counter
ARCH_JOBS["u"] = [dict(l=[("y", 20, ("run", 1, 0)), ("y", 300, ("run", 0, 0))],
                       b=[("y", 20, ("run", 1, 0)), ("y", 300, ("run", 0, 0))]),
                  dict(l=[("y", 300, ("run", 0, 1)), ("y", 300, ("run", 1, 0))],
                       b=[("y", 300, ("run", 0, 1)), ("y", 300, ("run", 1, 0))])]


def stage_splice_arches(M, bry, weights, scale, jobs=None, map_y=250, log=None):
    jobs = jobs or ARCH_JOBS
    for name, secs in jobs.items():
        for w, f in M.items():
            glyf = f["glyf"]
            B = bry_instance(bry, weights[w])
            lcs = glyph_contours(glyf, name)
            bcs = brygada_contours(B, name, scale)
            mp = _stem_map(lcs, bcs, map_y)
            li = 0  # outer contour
            for s in secs:
                lc = lcs[s.get("lc", 0)]
                bc = bcs[s.get("bc", 0)]
                lcuts = [_resolve(c, lcs) for c in s["l"]]
                bcuts = [_resolve(c, bcs) for c in s["b"]]
                lcs[s.get("lc", 0)] = splice_section(lc, bc, lcuts, bcuts, mp)
            set_glyph_contours(glyf, name, lcs)
            f["hmtx"][name] = (f["hmtx"][name][0], glyf[name].xMin)
    if log is not None:
        log.append(("splice-arches", {n: [len(c) for c in glyph_contours(M[400]['glyf'], n)] for n in jobs}))


# ---------------------------------------------------------------- generalized cuts
def resolve(spec, contours, c=None):
    """Cut spec -> (axis, value, ref along the line).
    value: number, or ("run", y, i, side, off) = x of ink run i edge at height y (+off),
           or ("bbox", frac) = xMin + frac * width of the given contour set.
    ref: ("run", i, side) | ("at", v) | ("rank", k) (k-th crossing along the line, sorted)."""
    from .splice import crossings
    axis, v, ref = spec
    if isinstance(v, tuple):
        if v[0] == "run":
            _, yy, i, side, off = v
            v = ink_runs(contours, yy)[i][side] + off
        elif v[0] == "bbox":
            xs = [p[0] for cc in contours for p in cc]
            ys = [p[1] for cc in contours for p in cc]
            lo, hi = (min(xs), max(xs)) if axis == "x" else (min(ys), max(ys))
            v = lo + v[1] * (hi - lo)
    if ref[0] == "run":
        r = ink_runs(contours, v)[ref[1]]
        return (axis, v, r[ref[2]])
    if ref[0] == "rank":
        cr = sorted(q[0] for q in crossings(explicitize(c), axis, v))
        return (axis, v, cr[ref[1]])
    return (axis, v, ref[1])


def remove_section(lc, lcuts):
    from .splice import cut_at, _find
    lc = explicitize(lc)
    lc, ia = cut_at(lc, lcuts[0])
    A = list(lc[ia])
    lc, ib = cut_at(lc, lcuts[1])
    ia = _find(lc, lcuts[0][0], lcuts[0][1], A)
    rest = section(lc, ib, ia)[1:-1]
    return [list(lc[ia]), list(lc[ib])] + rest


def translate_map(dx, dy):
    return lambda x, y: (x + dx, y + dy)


def _centre_at(c, y):
    from .splice import crossings
    xs = sorted(q[0] for q in crossings(explicitize(c), "y", y))
    return (xs[0] + xs[-1]) / 2 if len(xs) >= 2 else None


def _slope_map(lc, bc, y0, y1):
    """Match a slanted stroke: translate so the stroke centres meet at y0 and shear so the
    stroke directions (centre at y0 -> y1) agree."""
    l0, l1 = _centre_at(lc, y0), _centre_at(lc, y1)
    b0, b1 = _centre_at(bc, y0), _centre_at(bc, y1)
    sl = (l1 - l0) / (y1 - y0)
    sb = (b1 - b0) / (y1 - y0)
    k = sl - sb
    return lambda x, y: (x + (l0 - b0) + k * (y - y0), y)


def _largest(cs):
    return max(range(len(cs)), key=lambda i: len(cs[i]))


def run_jobs(M, bry, weights, scale, jobs, shear=0.0, log=None):
    """Splice Brygada sections into every master with cuts locked to the first master's
    segment structure (see splice.locate / relocate)."""
    from .splice import locate, relocate, splice_locked, crossings
    import copy as _copy
    keys = list(M)
    done, failed = {}, {}
    for name, job in jobs.items():
        if name not in M[keys[0]]["glyf"].keys():
            continue
        backup = {w: _copy.deepcopy((M[w]["glyf"][name], M[w]["hmtx"][name])) for w in keys}
        try:
            src = job.get("src", name)
            jscale = job.get("scale", scale)
            jweights = job.get("weights", weights)
            L = {w: glyph_contours(M[w]["glyf"], name) for w in keys}
            Bc = {w: brygada_contours(bry_instance(bry, jweights[w]), src, jscale, shear=shear) for w in keys}
            if job.get("fit_top"):
                # move Brygada's shape so its top matches Lora's (e.g. f's hook height)
                for w in keys:
                    ly = max(p[1] for c in L[w] for p in c)
                    by = max(p[1] for c in Bc[w] for p in c)
                    Bc[w] = [[[p[0], p[1] + (ly - by), p[2]] for p in c] for c in Bc[w]]
            mk = job.get("map", ("stems", 250))
            for s in job.get("sections", []):
                li = s.get("lc", _largest(L[keys[0]]))
                bi = s.get("bc", _largest(Bc[keys[0]]))
                lx = {w: explicitize(L[w][li]) for w in keys}
                bx = {w: explicitize(Bc[w][bi]) for w in keys}
                if s.get("fit") in ("top", "bottom"):
                    for w in keys:
                        pick = max if s["fit"] == "top" else min
                        dy = pick(p[1] for c in L[w] for p in c) - pick(p[1] for p in bx[w])
                        bx[w] = [[p[0], p[1] + dy, p[2]] for p in bx[w]]
                    Bw = {w: [bx[w] if i == bi else c for i, c in enumerate(Bc[w])] for w in keys}
                else:
                    Bw = Bc
                # locate on the reference master
                w0 = keys[0]
                lcut0 = [resolve(c, L[w0], L[w0][li]) for c in s["l"]]
                bcut0 = [resolve(c, Bw[w0], bx[w0]) for c in s["b"]]
                lref = [locate(lx[w0], c) for c in lcut0]
                bref = [locate(bx[w0], c) for c in bcut0]
                if s.get("hint"):
                    # make sure Lora's A->B section is the one containing the hint point
                    from .splice import split_loc
                    hx, hy = s["hint"]
                    def contains(c, la, lb):
                        c1, i1 = split_loc(c, la)
                        c2, i2 = split_loc(c, lb)
                        ia = min(range(len(c)), key=lambda k: (c[k][0] - c1[i1][0]) ** 2 + (c[k][1] - c1[i1][1]) ** 2)
                        ib = min(range(len(c)), key=lambda k: (c[k][0] - c2[i2][0]) ** 2 + (c[k][1] - c2[i2][1]) ** 2)
                        sec = section(c, ia, ib)
                        other = section(c, ib, ia)
                        d = lambda pts: min((p[0] - hx) ** 2 + (p[1] - hy) ** 2 for p in pts)
                        return d(sec) < d(other)
                    if not contains(lx[w0], lref[0], lref[1]):
                        lref, bref = lref[::-1], bref[::-1]
                for w in keys:
                    if mk[0] == "stems":
                        mp = _stem_map(L[w], Bw[w], mk[1], mk[2] if len(mk) > 2 else None)
                    elif mk[0] == "slope":
                        mp = _slope_map(L[w][li], Bc[w][bi], mk[1], mk[2])
                    lloc = [relocate(lx[w], r) for r in lref] if w != w0 else lref
                    bloc = [relocate(bx[w], r) for r in bref] if w != w0 else bref
                    if mk[0] == "translate":
                        from .splice import split_loc
                        pa = split_loc(lx[w], lloc[0]); pb = split_loc(lx[w], lloc[1])
                        qa = split_loc(bx[w], bloc[0]); qb = split_loc(bx[w], bloc[1])
                        la, lb = pa[0][pa[1]], pb[0][pb[1]]
                        ba, bb = qa[0][qa[1]], qb[0][qb[1]]
                        mp = translate_map((la[0] + lb[0]) / 2 - (ba[0] + bb[0]) / 2,
                                           (la[1] + lb[1]) / 2 - (ba[1] + bb[1]) / 2)
                    new = splice_locked(lx[w], bx[w], lloc, bloc, mp, blend=s.get("blend", 70.0),
                                        tangents=s.get("smooth", False))
                    L[w][li] = new
            for r in job.get("remove", []):
                li = r.get("lc", _largest(L[keys[0]]))
                w0 = keys[0]
                lx0 = explicitize(L[w0][li])
                lref = [locate(lx0, resolve(c, L[w0], L[w0][li])) for c in r["l"]]
                for w in keys:
                    lx = explicitize(L[w][li])
                    lloc = [relocate(lx, q) for q in lref] if w != w0 else lref
                    L[w][li] = _remove_locked(lx, lloc)
            for li, bi in job.get("counters", []):
                for w in keys:
                    mp = _stem_map(L[w], Bc[w], mk[1], mk[2] if len(mk) > 2 else None)
                    L[w][li] = [[*mp(p[0], p[1]), p[2]] for p in Bc[w][bi]]
            for a in job.get("add", []):
                bi = a["bc"]
                kind, yy, into = a["attach"]
                for w in keys:
                    lr, br = ink_runs(L[w], yy), ink_runs(Bc[w], yy)
                    dx = lr[0][1] - br[0][1]
                    edge = br[0][1]
                    L[w].append([[p[0] + dx - (into if p[0] <= edge + 3 else 0), p[1], p[2]] for p in Bc[w][bi]])
            sizes = {w: sum(len(c) for c in L[w]) for w in keys}
            if len(set(sizes.values())) != 1:
                raise ValueError(f"masters incompatible {sizes}")
            for w in keys:
                glyf = M[w]["glyf"]
                set_glyph_contours(glyf, name, L[w])
                M[w]["hmtx"][name] = (M[w]["hmtx"][name][0], glyf[name].xMin)
            done[name] = sizes[keys[0]]
        except Exception as e:
            import traceback
            failed[name] = repr(e)[:160]
            for w, (g, m) in backup.items():
                M[w]["glyf"].glyphs[name] = g
                M[w]["hmtx"][name] = m
    if log is not None:
        log.append(("splice-failed", failed))
    return done


def L_last(new, lloc, lx):
    """Coordinates of Lora's B cut point in the spliced contour (to find its index)."""
    from .splice import split_loc
    c2, i = split_loc(lx, lloc[1])
    return c2[i][:2]


def _remove_locked(lx, lloc):
    from .splice import split_loc
    la, lb = lloc
    first, second = (la, lb) if la[0] > lb[0] else (lb, la)
    c, i1 = split_loc(lx, first)
    c, i2 = split_loc(c, second)
    i1 += 2 if second[1] is not None else 1
    ia, ib = (i1, i2) if first is la else (i2, i1)
    return [list(c[ia]), list(c[ib])] + section(c, ib, ia)[1:-1]


def _is_cut(p, cut):
    axis, v, ref = cut
    k = 1 if axis == "y" else 0
    return abs(p[k] - v) < 1e-6


R = lambda y, i, side: ("y", y, ("run", i, side))  # cut on a stem edge at height y

ROMAN_JOBS = {
    "n": dict(sections=[dict(l=[R(490, 0, 1), R(250, 1, 1)], b=[R(490, 0, 1), R(250, 1, 1)]),
                        dict(l=[R(250, 1, 0), R(250, 0, 1)], b=[R(250, 1, 0), R(250, 0, 1)])]),
    "m": dict(sections=[dict(l=[R(490, 0, 1), R(250, 2, 1)], b=[R(490, 0, 1), R(250, 2, 1)]),
                        dict(l=[R(250, 2, 0), R(250, 1, 1)], b=[R(250, 2, 0), R(250, 1, 1)]),
                        dict(l=[R(250, 1, 0), R(250, 0, 1)], b=[R(250, 1, 0), R(250, 0, 1)])]),
    "u": dict(sections=[dict(l=[R(20, 1, 0), R(300, 0, 0)], b=[R(20, 1, 0), R(300, 0, 0)]),
                        dict(l=[R(300, 0, 1), R(300, 1, 0)], b=[R(300, 0, 1), R(300, 1, 0)])]),
    # bowls: outer section + the whole counter
    "b": dict(sections=[dict(l=[R(490, 0, 1), ("x", ("run", 250, 0, 0, 8), ("at", 0))],
                             b=[R(490, 0, 1), ("x", ("run", 250, 0, 0, 8), ("at", 0))])],
              counters=[(1, 1)]),
    "p": dict(sections=[dict(l=[R(490, 0, 1), R(-40, 0, 1)], b=[R(490, 0, 1), R(-40, 0, 1)])],
              counters=[(1, 1)]),
    "d": dict(sections=[dict(l=[R(20, 1, 0), R(540, 0, 0)], b=[R(20, 1, 0), R(540, 0, 0)])],
              counters=[(1, 1)]),
    "q": dict(sections=[dict(l=[R(-40, 0, 0), R(300, 1, 1)], b=[R(-40, 0, 0), R(300, 1, 1)])],
              counters=[(1, 1)]),
    # r: Lora's arm out, Brygada's separate arm+ball contour in
    "r": dict(remove=[dict(l=[R(480, 0, 1), R(300, 0, 1)])], add=[dict(bc=0, attach=("stem_right", 300, 15))]),
}
ROMAN_JOBS["h"] = ROMAN_JOBS["n"]

X = lambda frac, k: ("x", ("bbox", frac), ("rank", k))  # vertical cut at a bbox fraction, k-th crossing by height
Y = lambda y, k: ("y", y, ("rank", k))                  # horizontal cut, k-th crossing from the left
# c: cut through the thick left stroke (weights match there) and take the whole upper half
C_TOP = dict(map=("stems", 250), sections=[dict(l=[R(250, 0, 0), R(250, 0, 1)], b=[R(250, 0, 0), R(250, 0, 1)], blend=90)])
# f: Brygada's hook, lowered to Lora's f height
F_TOP = dict(map=("stems", 560),
             sections=[dict(l=[R(560, 0, 0), R(560, 0, 1)], b=[R(560, 0, 0), R(560, 0, 1)], bc=0, blend=90, fit="top")])
ROMAN_JOBS.update({
    "c": C_TOP,
    "uni0454": dict(map=("stems", 150), counters=[(0, 1)],
                    sections=[dict(l=[R(150, 0, 0), R(150, 0, 1)], b=[R(150, 0, 0), R(150, 0, 1)], blend=90)]),
    "f": F_TOP,
    "longs": dict(F_TOP, src="f"),
    "uni0237": dict(map=("stems", 100), sections=[dict(l=[R(0, 0, 1), R(0, 0, 0)], b=[R(0, 0, 1), R(0, 0, 0)])]),
    "y": dict(map=("slope", -40, -110), sections=[dict(l=[Y(-40, -1), Y(-40, -2)], b=[Y(-40, -1), Y(-40, -2)], bc=1, blend=90)]),
    "J": dict(map=("stems", 300), scale=700 / 670, weights={400: 400, 700: 654},
              sections=[dict(l=[R(250, 0, 1), R(250, 0, 0)], b=[R(250, 0, 1), R(250, 0, 0)])]),
    "uni044D": dict(map=("stems", 150, [-1]), counters=[(1, 1)], sections=[dict(l=[Y(150, -1), Y(150, -2)], b=[Y(150, -1), Y(150, -2)], blend=90)]),
    "hbar": ROMAN_JOBS["n"],
    "thorn": ROMAN_JOBS["p"],
    "dcroat": ROMAN_JOBS["d"],
    "dcaron": dict(ROMAN_JOBS["d"], counters=[(2, 1)]),
    "eng": dict(map=("stems", 100, [-1]), sections=[dict(l=[R(60, 1, 1), R(60, 1, 0)], b=[R(60, 1, 1), R(60, 1, 0)], bc=0, blend=90)]),
})

# Z / z: Brygada's own terminal serifs (top-left and bottom-right), spliced across the bars
Z_TERMS = dict(map=("translate",), sections=[
    dict(l=[X(0.35, -2), X(0.35, -1)], b=[X(0.35, -2), X(0.35, -1)], blend=80),
    dict(l=[X(0.65, 1), X(0.65, 0)], b=[X(0.65, 1), X(0.65, 0)], blend=80)])


# ---------------------------------------------------------------- italic
IT_SHEAR = -0.0424  # Brygada italic 8 deg -> Lora italic lowercase ~5.6 deg
IT_F = dict(map=("stems", 560), sections=[
    dict(l=[R(560, 0, 0), R(560, 0, 1)], b=[R(560, 0, 0), R(560, 0, 1)], bc=2, blend=90, fit="top"),
    dict(l=[R(-60, 0, 1), R(-60, 0, 0)], b=[R(-60, 0, 1), R(-60, 0, 0)], bc=0, blend=90, fit="bottom")])
ITALIC_JOBS = {
    "c": dict(map=("stems", 250), sections=[dict(l=[R(250, 0, 0), R(250, 0, 1)], b=[R(250, 0, 0), R(250, 0, 1)], blend=90)]),
    "uni0454": dict(map=("stems", 150, [0]), counters=[(0, 1)],
                    sections=[dict(l=[R(150, 0, 0), R(150, 0, 1)], b=[R(150, 0, 0), R(150, 0, 1)], blend=90)]),
    "uni044D": dict(map=("stems", 150, [-1]), counters=[(1, 1)],
                    sections=[dict(l=[Y(150, -1), Y(150, -2)], b=[Y(150, -1), Y(150, -2)], blend=90)]),
    "f": IT_F,
    "longs": dict(IT_F, src="f"),
    "germandbls": dict(src="f", map=("stems", 100, [0]), sections=[
        dict(l=[R(-60, 0, 1), R(-60, 0, 0)], b=[R(-60, 0, 1), R(-60, 0, 0)], bc=0, blend=90, fit="bottom")]),
    "eng": dict(map=("stems", 100, [-1]), sections=[dict(l=[R(60, 1, 1), R(60, 1, 0)], b=[R(60, 1, 1), R(60, 1, 0)], blend=90)]),
    "uni0237": dict(map=("stems", 100), sections=[dict(l=[R(0, 0, 1), R(0, 0, 0)], b=[R(0, 0, 1), R(0, 0, 0)], blend=90)]),
    "r": dict(map=("stems", 250), sections=[dict(l=[R(470, 0, 1), R(300, 0, 1)], b=[R(470, 0, 1), R(300, 0, 1)], blend=90)]),
    "J": dict(map=("stems", 300), scale=700 / 670, weights={400: 400, 700: 640},
              sections=[dict(l=[R(250, 0, 1), R(250, 0, 0)], b=[R(250, 0, 1), R(250, 0, 0)], blend=90)]),
    # y: keep the u-shaped y (Lora u + graft) but give it Brygada's italic tail
    "y": dict(map=("stems", -40, [-1]), sections=[dict(l=[Y(-40, -1), Y(-40, -2)], b=[Y(-40, -1), Y(-40, -2)], blend=90)]),
}
