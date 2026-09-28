"""Kerning for transplanted figures: transfer Lora's pair spacing intent onto the new shapes."""
import io

import numpy as np
import uharfbuzz as hb
from fontTools.otlLib import builder as otl
from fontTools.pens.basePen import BasePen
from fontTools.ttLib.tables import otTables as ot

FIGS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
OTHER_CHARS = ".,:;-–—)(/%°'\"’”‘“AVWTYLPJ"
YS = np.arange(-300, 820, 8)


class _Edges(BasePen):
    def __init__(self, gs):
        super().__init__(gs)
        self.segs, self.cur, self.start = [], None, None

    def _moveTo(self, p):
        self.cur = self.start = p

    def _lineTo(self, p):
        self.segs.append((self.cur, p))
        self.cur = p

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur
        prev = p0
        for t in np.linspace(0, 1, 9)[1:]:
            q = ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            self.segs.append((prev, q))
            prev = q
        self.cur = p2

    def _curveToOne(self, p1, p2, p3):
        raise NotImplementedError

    def _closePath(self):
        if self.cur != self.start:
            self.segs.append((self.cur, self.start))

    _endPath = _closePath


def profile(gs, name):
    """(left, right) ink extents per scanline in YS (nan where no ink)."""
    pen = _Edges(gs)
    gs[name].draw(pen)
    L = np.full(len(YS), np.nan)
    R = np.full(len(YS), np.nan)
    if not pen.segs:
        return L, R
    S = np.array([(a[0], a[1], b[0], b[1]) for a, b in pen.segs], float)
    for i, y in enumerate(YS):
        m = (S[:, 1] <= y) != (S[:, 3] <= y)
        if not m.any():
            continue
        s = S[m]
        xs = s[:, 0] + (y - s[:, 1]) * (s[:, 2] - s[:, 0]) / (s[:, 3] - s[:, 1])
        L[i], R[i] = xs.min(), xs.max()
    return L, R


def min_gap(gs, a, b, kern, cache):
    for n in (a, b):
        if n not in cache:
            cache[n] = profile(gs, n)
    _, Ra = cache[a]
    Lb, _ = cache[b]
    gaps = gs[a].width + kern + Lb - Ra
    gaps = gaps[~np.isnan(gaps)]
    if not len(gaps):
        return None
    tau = 18.0  # smooth minimum: weighs the whole near region, not one scanline
    m = gaps.min()
    return float(m - tau * np.log(np.mean(np.exp(-(gaps - m) / tau))))


def current_kerning(font, pairs):
    buf = io.BytesIO()
    font.save(buf)
    face = hb.Face(buf.getvalue())
    hfont = hb.Font(face)
    order = font.getGlyphOrder()
    cmap = font.getBestCmap()
    rev = {v: k for k, v in cmap.items()}
    out = {}
    for a, b in pairs:
        b_ = hb.Buffer()
        b_.add_codepoints([rev[a], rev[b]])
        b_.guess_segment_properties()
        hb.shape(hfont, b_, {"kern": True, "liga": False, "calt": False})
        pos = b_.glyph_positions
        names = [order[i.codepoint] for i in b_.glyph_infos]
        if names != [a, b]:
            continue
        out[(a, b)] = pos[0].x_advance - font["hmtx"][a][0]
    return out


def stage_kern_figures(M, M_orig, bry_kern):
    """M: modified masters; M_orig: untouched Lora masters (same glyph names);
    bry_kern: {master: {(a, b): value}} Brygada kerning for figure-figure pairs (already scaled)."""
    cmap = M[400].getBestCmap()
    others = [cmap[ord(c)] for c in OTHER_CHARS if ord(c) in cmap]
    ff = [(a, b) for a in FIGS for b in FIGS]
    fo = [(a, b) for a in FIGS for b in others] + [(b, a) for a in FIGS for b in others]
    deltas = {}
    for w in M:
        f, fo_ = M[w], M_orig[w]
        cur = current_kerning(f, ff + fo)
        old = current_kerning(fo_, fo)
        gs, gso = f.getGlyphSet(), fo_.getGlyphSet()
        cache, cacheo = {}, {}
        d = {}
        for p in ff:
            want = bry_kern[w].get(p, 0)
            d[p] = want - cur.get(p, 0)
        for p in fo:
            if p not in cur:
                continue
            k_old = old.get(p, 0)
            bk = bry_kern[w].get(p, 0)
            if k_old == 0 and bk == 0:
                continue  # neither design kerned it: leave the sidebearings alone
            g0 = min_gap(gso, p[0], p[1], k_old, cacheo)
            g1 = min_gap(gs, p[0], p[1], 0, cache)
            if g0 is None or g1 is None:
                continue
            want = round(g0 - g1)
            ref = k_old if k_old else bk
            want = int(np.clip(want, ref - 45, ref + 45))
            d[p] = want - cur.get(p, 0)
        deltas[w] = d
    # same pair set in every master (varLib needs structurally identical lookups)
    keys = sorted(set().union(*[{p for p, v in d.items() if abs(v) >= 3} for d in deltas.values()]))
    for w, f in M.items():
        pairs = {p: deltas[w].get(p, 0) for p in keys}
        _add_pair_lookup(f, pairs)
    return {w: {p: deltas[w].get(p, 0) for p in keys} for w in M}


def _add_pair_lookup(font, pairs):
    gpos = font["GPOS"].table
    vr = {}
    for (a, b), v in pairs.items():
        v1 = ot.ValueRecord()
        v1.XAdvance = int(v)
        vr[(a, b)] = (v1, None)
    st = otl.buildPairPosGlyphsSubtable(vr, font.getReverseGlyphMap())
    lk = otl.buildLookup([st])
    gpos.LookupList.Lookup.append(lk)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)
    idx = len(gpos.LookupList.Lookup) - 1
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "kern":
            fr.Feature.LookupListIndex.append(idx)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
