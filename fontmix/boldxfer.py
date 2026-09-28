"""Build the bold master of Brygada-derived glyphs as: Elanora Regular + Lora's own Regular->Bold
movement, transferred point by point from the nearest matching spot on Lora's outline.

Lora thickens hairlines as well as stems; Brygada keeps its hairlines thin. Transferring Lora's
deltas gives the Brygada-shaped parts Lora's weight distribution in bold, and keeps the bold
master point-compatible with the regular one."""
import numpy as np

from .geom import explicitize, glyph_contours, segments, set_glyph_contours


def _samples(reg_cs, bold_cs, n=28):
    """Positions, deltas and outward normals sampled along Lora's (regular) outline."""
    P, D, N = [], [], []
    for cr, cb in zip(reg_cs, bold_cs):
        er, eb = explicitize(cr), explicitize(cb)
        assert len(er) == len(eb)
        for a, ctrl, b in segments(er):
            A0, A2 = np.array(er[a][:2]), np.array(er[b][:2])
            B0, B2 = np.array(eb[a][:2]), np.array(eb[b][:2])
            ts = np.linspace(0, 1, n, endpoint=False)
            if ctrl is None:
                pr = A0[None] + (A2 - A0)[None] * ts[:, None]
                pb = B0[None] + (B2 - B0)[None] * ts[:, None]
                tan = np.repeat((A2 - A0)[None], n, axis=0)
            else:
                A1, B1 = np.array(er[ctrl][:2]), np.array(eb[ctrl][:2])
                t = ts[:, None]
                pr = (1 - t) ** 2 * A0 + 2 * (1 - t) * t * A1 + t * t * A2
                pb = (1 - t) ** 2 * B0 + 2 * (1 - t) * t * B1 + t * t * B2
                tan = 2 * (1 - t) * (A1 - A0) + 2 * t * (A2 - A1)
            nrm = np.c_[-tan[:, 1], tan[:, 0]]
            nrm /= np.maximum(1e-9, np.hypot(nrm[:, 0], nrm[:, 1]))[:, None]
            P.append(pr), D.append(pb - pr), N.append(nrm)
    return np.concatenate(P), np.concatenate(D), np.concatenate(N)


def _outline(reg_cs, bold_cs, n=40):
    """Per Lora contour: sample positions, deltas, normals and cumulative arc length."""
    out = []
    for cr, cb in zip(reg_cs, bold_cs):
        P, D, N = _samples([cr], [cb], n)
        seg = np.hypot(*np.diff(np.vstack([P, P[:1]]), axis=0).T)
        s = np.r_[0, np.cumsum(seg[:-1])]
        out.append(dict(P=P, D=D, N=N, s=s, L=s[-1] + seg[-1]))
    return out


def _delta_at(o, arc):
    s, L, D = o["s"], o["L"], o["D"]
    arc = arc % L
    k = int(np.searchsorted(s, arc, side="right") - 1)
    k2 = (k + 1) % len(s)
    s1 = s[k2] if k2 else L
    t = 0.0 if s1 == s[k] else (arc - s[k]) / (s1 - s[k])
    return D[k] * (1 - t) + D[k2] * t


def _seg_dist(outl, p):
    """Distance from p to Lora's outline (polyline through the dense samples) and nearest index."""
    best, bi = np.inf, 0
    off = 0
    for o in outl:
        A = o["P"]
        B = np.roll(A, -1, axis=0)
        AB = B - A
        t = np.clip(((p - A) * AB).sum(1) / np.maximum(1e-9, (AB * AB).sum(1)), 0, 1)
        Q = A + AB * t[:, None]
        d = np.hypot(Q[:, 0] - p[0], Q[:, 1] - p[1])
        k = int(np.argmin(d))
        if d[k] < best:
            best, bi = d[k], off + k
        off += len(A)
    return best, bi


def _signed_area(xy):
    return 0.5 * float(np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1]))


def _extremes(xy):
    """Indices of topmost, rightmost, bottommost, leftmost points (in contour order)."""
    ids = [int(np.argmax(xy[:, 1])), int(np.argmax(xy[:, 0])), int(np.argmin(xy[:, 1])), int(np.argmin(xy[:, 0]))]
    return ids


def _loop_map(c, outl, on_tol=1.2, iou_min=0.55):
    """A counter (hole contour) that is entirely new: map it around the loop onto the Lora
    counter it replaced, piecewise by arc length between the four extreme points, so corners
    land on corners. Returns new contour or None if not applicable."""
    xy = np.array([p[:2] for p in c], float)
    if _signed_area(xy) <= 0:  # only holes (counter-clockwise in TrueType)
        return None
    if any(_seg_dist(outl, p)[0] < on_tol for p in xy):
        return None  # touches Lora's outline: handled by the anchor/run mapping
    def box(a):
        return a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()
    bx = box(xy)
    best, bi = 0, None
    for i, o in enumerate(outl):
        if _signed_area(o["P"]) <= 0:
            continue
        ob = box(o["P"])
        ix = max(0, min(bx[2], ob[2]) - max(bx[0], ob[0])) * max(0, min(bx[3], ob[3]) - max(bx[1], ob[1]))
        un = (bx[2] - bx[0]) * (bx[3] - bx[1]) + (ob[2] - ob[0]) * (ob[3] - ob[1]) - ix
        if un > 0 and ix / un > best:
            best, bi = ix / un, i
    if bi is None or best < iou_min:
        return None
    o = outl[bi]
    # arc length along the (dense) Elanora contour polyline
    n = len(xy)
    seg = np.hypot(*np.diff(np.vstack([xy, xy[:1]]), axis=0).T)
    sp = np.r_[0, np.cumsum(seg[:-1])]
    Lp = sp[-1] + seg[-1]
    pe = _extremes(xy)
    le = _extremes(o["P"])
    ps = [sp[i] for i in pe]
    ls = [o["s"][i] for i in le]
    out = []
    for i in range(n):
        s = sp[i]
        # which extreme interval (cyclic, in contour order) contains s
        k = max(range(4), key=lambda j: -((s - ps[j]) % Lp))
        k2 = (k + 1) % 4
        span_p = (ps[k2] - ps[k]) % Lp or Lp
        span_l = (ls[k2] - ls[k]) % o["L"] or o["L"]
        f = ((s - ps[k]) % Lp) / span_p
        d = _delta_at(o, ls[k] + f * span_l)
        out.append([xy[i, 0] + d[0], xy[i, 1] + d[1], c[i][2]])
    return out


def transfer_glyph(reg_cs, lora_reg, lora_bold, exact_tol=0.6, on_tol=1.2, smooth_passes=2, mode="splice"):
    """New bold contours for reg_cs (same structure) from Lora's reg->bold deltas.
    Points on Lora's outline take Lora's delta there; runs of new points between two such
    anchors (a spliced section) are mapped by position along the path onto the Lora section
    they replaced; anything else takes the delta of the nearest same-facing spot."""
    outl = _outline(lora_reg, lora_bold)
    P = np.concatenate([o["P"] for o in outl]); N = np.concatenate([o["N"] for o in outl])
    D = np.concatenate([o["D"] for o in outl])
    cid = np.concatenate([np.full(len(o["P"]), i) for i, o in enumerate(outl)])
    sid = np.concatenate([np.arange(len(o["P"])) for o in outl])
    lpts = np.array([p[:2] for c in lora_reg for p in c], float)
    ldel = np.array([q[:2] for c in lora_bold for q in c], float) - lpts
    out = []
    for c in reg_cs:
        loop = _loop_map(c, outl) if mode == "splice" else None
        if loop is not None:
            out.append(loop)
            continue
        n = len(c)
        xy = np.array([p[:2] for p in c], float)
        tan = np.roll(xy, -1, axis=0) - np.roll(xy, 1, axis=0)
        nrm = np.c_[-tan[:, 1], tan[:, 0]]
        nrm /= np.maximum(1e-9, np.hypot(nrm[:, 0], nrm[:, 1]))[:, None]
        delta = np.zeros_like(xy)
        exact = np.zeros(n, bool)
        onl = np.zeros(n, bool)
        near = np.zeros(n, int)
        for i in range(n):
            d_pts = np.hypot(lpts[:, 0] - xy[i, 0], lpts[:, 1] - xy[i, 1])
            j = int(np.argmin(d_pts))
            dist = np.hypot(P[:, 0] - xy[i, 0], P[:, 1] - xy[i, 1])
            k = int(np.argmin(dist))
            if d_pts[j] <= exact_tol:
                delta[i], exact[i], onl[i], near[i] = ldel[j], True, True, k
                continue
            sd, sk = _seg_dist(outl, xy[i])
            if sd <= on_tol:
                delta[i], onl[i], near[i] = D[sk], True, sk
                continue
            ok = (N @ nrm[i]) > 0.2
            dd = np.where(ok, dist, np.inf) if ok.any() else dist
            delta[i] = D[int(np.argmin(dd))]
        # spliced runs between on-outline anchors: map along the replaced Lora section
        if mode == "splice" and onl.any() and not onl.all():
            start = int(np.argmax(onl))
            i = start
            visited = 0
            while visited < n:
                if onl[i] and not onl[(i + 1) % n]:
                    a = i
                    b = (i + 1) % n
                    run = []
                    while not onl[b]:
                        run.append(b)
                        b = (b + 1) % n
                    ka, kb = near[a], near[b]
                    if a != b and cid[ka] == cid[kb]:
                        o = outl[cid[ka]]
                        sa, sb = o["s"][sid[ka]], o["s"][sid[kb]]
                        Lf = (sb - sa) % o["L"]
                        Lper = float(np.sum(np.hypot(*np.diff(np.vstack([xy, xy[:1]]), axis=0).T)))
                        runpts = [xy[a]] + [xy[r] for r in run] + [xy[b]]
                        Lrun = float(np.sum(np.hypot(*np.diff(np.array(runpts), axis=0).T)))
                        if 1.0 < Lf and abs(Lf / o["L"] - Lrun / Lper) < 0.25:
                            # straight stem-edge stretches at either end keep the stem's movement
                            def on_line(p, anchor, t):
                                v = p - anchor
                                return abs(v[0] * t[1] - v[1] * t[0]) < 1.5
                            ta = o["N"][sid[ka]][[1, 0]] * np.array([1, -1])
                            tb = o["N"][sid[kb]][[1, 0]] * np.array([1, -1])
                            i0, i1 = 0, len(run)
                            while i0 < i1 and on_line(xy[run[i0]], xy[a], ta):
                                delta[run[i0]] = delta[a]; i0 += 1
                            while i1 > i0 and on_line(xy[run[i1 - 1]], xy[b], tb):
                                delta[run[i1 - 1]] = delta[b]; i1 -= 1
                            # same trimming on Lora's section (walk samples along the stem line)
                            P0 = o["P"]
                            m = len(P0)
                            ja = sid[ka]
                            while on_line(P0[(ja + 1) % m], P0[sid[ka]], ta) and (o["s"][(ja + 1) % m] - sa) % o["L"] < Lf:
                                ja = (ja + 1) % m
                            jb = sid[kb]
                            while on_line(P0[(jb - 1) % m], P0[sid[kb]], tb) and (sb - o["s"][(jb - 1) % m]) % o["L"] < Lf:
                                jb = (jb - 1) % m
                            sa2, sb2 = o["s"][ja], o["s"][jb]
                            Lf2 = (sb2 - sa2) % o["L"]
                            if Lf2 <= 1.0 or Lf2 > Lf:
                                sa2, Lf2 = sa, Lf
                            ea = xy[run[i0 - 1]] if i0 > 0 else xy[a]
                            eb = xy[run[i1]] if i1 < len(run) else xy[b]
                            mid = run[i0:i1]
                            if mid:
                                pts = [ea] + [xy[r] for r in mid] + [eb]
                                cum = np.r_[0, np.cumsum(np.hypot(*np.diff(np.array(pts), axis=0).T))]
                                for q, r in enumerate(mid):
                                    delta[r] = _delta_at(o, sa2 + Lf2 * cum[q + 1] / cum[-1])
                    visited += len(run) + 1
                    i = b
                else:
                    i = (i + 1) % n
                    visited += 1
        for _ in range(smooth_passes):
            sm = (np.roll(delta, 1, axis=0) + 2 * delta + np.roll(delta, -1, axis=0)) / 4
            delta = np.where(exact[:, None], delta, sm)
        out.append([[xy[i, 0] + delta[i, 0], xy[i, 1] + delta[i, 1], c[i][2]] for i in range(n)])
    return out


ZONES = (0, 500, 700, -16, 516, 716)
TOUCH_FIX = {"y", "uni0237", "J"}


def stage_bold_transfer(M, L, glyphs, ref=None, lo=400, hi=700, log=None, nearest=()):
    """M: final masters; L: Lora masters (after widening) as the source of reg->bold movement.
    ref: {glyph: Lora glyph to take the movement from} (default: same name)."""
    ref = ref or {}
    done = []
    for g in glyphs:
        src = ref.get(g, g)
        if g not in M[lo]["glyf"].keys() or src not in L[lo]["glyf"].keys():
            continue
        if M[lo]["glyf"][g].isComposite() or L[lo]["glyf"][src].isComposite():
            continue
        reg = glyph_contours(M[lo]["glyf"], g)
        if g in TOUCH_FIX:
            # merge overlapping / self-overlapping pieces (tail loop into the ball) first
            from .geom import pathops_contours, explicitize as _ex
            reg = [_ex(c) for c in pathops_contours(reg)]
            set_glyph_contours(M[lo]["glyf"], g, reg)
            M[lo]["hmtx"][g] = (M[lo]["hmtx"][g][0], M[lo]["glyf"][g].xMin)
        lr, lb = glyph_contours(L[lo]["glyf"], src), glyph_contours(L[hi]["glyf"], src)
        bold = transfer_glyph(reg, lr, lb, mode="nearest" if g in nearest else "splice")
        # points on the baseline / x-height / cap height (and their overshoots) keep their height
        for cr, cb in zip(reg, bold):
            for pr, pb in zip(cr, cb):
                if any(abs(pr[1] - z) < 1.0 for z in ZONES):
                    pb[1] = pr[1]
        glyf = M[hi]["glyf"]
        set_glyph_contours(glyf, g, bold)
        adv = M[lo]["hmtx"][g][0] + (L[hi]["hmtx"][src][0] - L[lo]["hmtx"][src][0])
        M[hi]["hmtx"][g] = (round(adv), glyf[g].xMin)
        done.append(g)
    # composites built on these glyphs: bold offsets = regular offsets + Lora's offset change
    for name in M[lo].getGlyphOrder():
        gr, gb = M[lo]["glyf"][name], M[hi]["glyf"][name]
        if not gr.isComposite() or gr.components[0].glyphName not in done:
            continue
        if name in L[lo]["glyf"].keys() and L[lo]["glyf"][name].isComposite():
            lr_c, lb_c = L[lo]["glyf"][name].components, L[hi]["glyf"][name].components
            if [c.glyphName for c in lr_c] == [c.glyphName for c in gr.components]:
                for cr, cb, lcr, lcb in zip(gr.components, gb.components, lr_c, lb_c):
                    cb.x = cr.x + (lcb.x - lcr.x)
                    cb.y = cr.y + (lcb.y - lcr.y)
        base = gr.components[0].glyphName
        M[hi]["hmtx"][name] = (M[hi]["hmtx"][base][0] if M[lo]["hmtx"][name][0] == M[lo]["hmtx"][base][0]
                               else M[hi]["hmtx"][name][0], M[hi]["hmtx"][name][1])
        gb.recalcBounds(M[hi]["glyf"])
    if log is not None:
        log.append(("bold-transfer", len(done)))
    return done
