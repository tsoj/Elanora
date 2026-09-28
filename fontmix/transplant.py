"""Bring individual Brygada letters into the Lora-based masters: scaled to Elanora's metrics,
weight-matched per master through Brygada's weight axis, with accents and anchors re-derived."""
import unicodedata
from functools import lru_cache

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.varLib import instancer

from .figures import brygada_contours
from .geom import glyph_contours, set_glyph_contours
from .widen import ink_runs

REP_MARKS = ["acutecomb", "gravecomb", "dotbelowcomb", "uni0328", "uni0327", "uni031B", "uni0326"]


@lru_cache(maxsize=None)
def bry_instance(path, wght):
    return instancer.instantiateVariableFont(TTFont(path), {"wght": wght})


def stem(font, glyph, y):
    runs = ink_runs(glyph_contours(font["glyf"], glyph), y)
    return runs[0][1] - runs[0][0]


def match_weight(lora_font, bry_path, glyph, y_lora, scale, lo=400, hi=700):
    """Brygada user weight whose scaled stem equals Lora's stem (bisection, clamped to axis)."""
    target = stem(lora_font, glyph, y_lora)
    f = lambda w: stem(bry_instance(bry_path, round(w)), glyph, y_lora / scale) * scale
    if f(lo) >= target:
        return lo
    if f(hi) <= target:
        return hi
    for _ in range(12):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2)


# ---------------------------------------------------------------- anchors
def _markbase_subtables(font):
    gpos = font["GPOS"].table
    for lk in gpos.LookupList.Lookup:
        for st in lk.SubTable:
            t = lk.LookupType
            if t == 9:
                t, st = st.ExtensionLookupType, st.ExtSubTable
            if t == 4:
                yield st


def base_anchors(font):
    """{base glyph: {class key: (x, y)}} with class keys named by a representative mark."""
    out = {}
    for st in _markbase_subtables(font):
        marks = st.MarkCoverage.glyphs
        cls_marks = {}
        for m, rec in zip(marks, st.MarkArray.MarkRecord):
            cls_marks.setdefault(rec.Class, set()).add(m)
        keys = {}
        for c, ms in cls_marks.items():
            rep = next((r for r in REP_MARKS if r in ms), None) or sorted(ms)[0]
            keys[c] = rep
        for g, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
            for c, a in enumerate(rec.BaseAnchor):
                if a is not None and c in keys:
                    out.setdefault(g, {})[keys[c]] = (a.XCoordinate, a.YCoordinate)
    return out


def mark_class_key(font):
    """{mark glyph: class key} (first subtable wins)."""
    out = {}
    for st in _markbase_subtables(font):
        cls_marks = {}
        for m, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
            cls_marks.setdefault(rec.Class, set()).add(m)
        for c, ms in cls_marks.items():
            rep = next((r for r in REP_MARKS if r in ms), None) or sorted(ms)[0]
            for m in ms:
                out.setdefault(m, rep)
    return out


def mark_anchor(font, mark):
    for st in _markbase_subtables(font):
        if mark in st.MarkCoverage.glyphs:
            a = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(mark)].MarkAnchor
            return a.XCoordinate, a.YCoordinate
    return None


def set_base_anchors(font, glyph, anchors):
    for st in _markbase_subtables(font):
        if glyph not in st.BaseCoverage.glyphs:
            continue
        cls_marks = {}
        for m, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
            cls_marks.setdefault(rec.Class, set()).add(m)
        rec = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index(glyph)]
        for c, ms in cls_marks.items():
            rep = next((r for r in REP_MARKS if r in ms), None) or sorted(ms)[0]
            a = rec.BaseAnchor[c] if c < len(rec.BaseAnchor) else None
            if a is not None and rep in anchors:
                a.XCoordinate, a.YCoordinate = (int(round(v)) for v in anchors[rep])


# ---------------------------------------------------------------- transplant
def transplant(M, bry_path, tgt, src=None, scale=1.0, weights=None, dx=0.0, dy=0.0, adv_extra=0,
               contours=None, shear=0.0):
    """Replace glyph tgt in every master with Brygada's src (decomposed, scaled).
    contours: optional list of contour indices to take. Returns {master: (old_anchors, new_anchors, old_adv)}."""
    src = src or tgt
    res = {}
    for w, f in M.items():
        B = bry_instance(bry_path, weights[w])
        cs = brygada_contours(B, src, scale, dx, dy, shear)
        if contours is not None:
            cs = [cs[i] for i in contours]
        old_adv = f["hmtx"][tgt][0]
        old_anchors = base_anchors(f).get(tgt, {})
        bra = base_anchors(B).get(src, {})
        new_anchors = {k: (x * scale + dx, y * scale + dy) for k, (x, y) in bra.items()}
        # keep Lora's anchor heights (accent placement is tuned to Lora's marks)
        for k in list(new_anchors):
            if k in old_anchors:
                new_anchors[k] = (new_anchors[k][0], old_anchors[k][1])
        set_glyph_contours(f["glyf"], tgt, cs)
        f["hmtx"][tgt] = (round(B["hmtx"][src][0] * scale) + adv_extra, f["glyf"][tgt].xMin)
        # missing classes: shift old anchors by the bbox-centre change
        res[w] = (old_anchors, new_anchors, old_adv)
    return res


def reanchor(M, base, info):
    """After base glyph outlines changed: move its GPOS base anchors and the marks of every
    composite built on it. info: {master: (old_anchors, new_anchors, old_adv)}."""
    for w, f in M.items():
        old, new, old_adv = info[w]
        glyf, hmtx = f["glyf"], f["hmtx"]
        mk = mark_class_key(f)
        full = dict(old)
        full.update({k: v for k, v in new.items() if k in old or True})
        delta = {k: (full[k][0] - old[k][0], full[k][1] - old[k][1]) for k in old if k in full}
        new_adv = hmtx[base][0]
        set_base_anchors(f, base, full)
        for name in f.getGlyphOrder():
            g = glyf[name]
            if not g.isComposite() or g.components[0].glyphName != base:
                continue
            for c in g.components[1:]:
                key = mk.get(c.glyphName)
                if key is None and c.glyphName.endswith(".case"):
                    key = mk.get(c.glyphName[:-5])
                d = delta.get(key)
                if d is None:  # fall back to the top-mark shift
                    d = delta.get("acutecomb", (0, 0))
                c.x = int(round(c.x + d[0]))
            if hmtx[name][0] == old_adv:
                hmtx[name] = (new_adv, hmtx[name][1])
            g.recalcBounds(glyf)
            hmtx[name] = (hmtx[name][0], g.xMin)
            # anchors of the composite (for stacking marks) follow the base
            ca = base_anchors(f).get(name)
            if ca:
                set_base_anchors(f, name, {k: (v[0] + delta.get(k, (0, 0))[0], v[1]) for k, v in ca.items()})


def rebuild_accented(M, base, case=False):
    """Outline glyphs that are base + one combining mark (e.g. Sacute drawn as one outline)
    become composites again, positioned by anchors, so they follow the new base."""
    f0 = M[next(iter(M))]
    cmap = f0.getBestCmap()
    rev = {g: cp for cp, g in cmap.items()}
    bcp = rev.get(base)
    todo = []
    for cp, g in cmap.items():
        dec = unicodedata.decomposition(chr(cp)).split()
        if len(dec) == 2 and not dec[0].startswith("<") and int(dec[0], 16) == bcp:
            if not f0["glyf"][g].isComposite():
                mcp = int(dec[1], 16)
                mark = cmap.get(mcp)
                if mark and case and mark + ".case" in f0.getGlyphOrder():
                    mark = mark + ".case"
                todo.append((g, mark))
    for w, f in M.items():
        glyf, hmtx = f["glyf"], f["hmtx"]
        ba = base_anchors(f).get(base, {})
        mk = mark_class_key(f)
        for g, mark in todo:
            key = mk.get(mark) or mk.get(mark.replace(".case", ""))
            ma = mark_anchor(f, mark)
            if key not in ba or ma is None:
                continue
            nx, ny = ba[key][0] - ma[0], ba[key][1] - ma[1]
            new = Glyph()
            new.numberOfContours = -1
            new.components = []
            for gname, x, y in ((base, 0, 0), (mark, nx, ny)):
                c = GlyphComponent()
                c.glyphName, c.x, c.y, c.flags = gname, int(round(x)), int(round(y)), 0x4
                new.components.append(c)
            glyf.glyphs[g] = new
            new.recalcBounds(glyf)
            hmtx[g] = (hmtx[base][0], new.xMin)
    return [g for g, _ in todo]
