"""Hand-edited outlines for the bold master.

The bold `a` can be exported to a UFO, edited in any font editor, and read back by the build.
The edit must stay point-compatible with the regular `a` (same contours, same points, same
on/off-curve pattern; moving points is fine, adding or deleting them is not), because the
variable font interpolates between the two. A rotated start point or reversed contour direction
(which some editors introduce on save) is undone automatically.

The displacement of every point (edited - original bold) is carried over to the bold æ and ª,
which share the a's shape: each of their points moves like the nearby a points (for ª after
mapping it onto the a's bounding box). Accented a's are composites and follow by themselves.
"""
import math
import os

import numpy as np

from .geom import glyph_contours, set_glyph_contours

REF_NOTE = ("Edit glyph 'a' (bold master). Keep every point: move points and handles, but do not "
            "add, delete or convert them. Other glyphs are references only and are not read back.")


# ------------------------------------------------------------------ glyf <-> UFO
def _glyf_to_ufo(ufo_glyph, f, name, dx=0.0, contours=None):
    pen = ufo_glyph.getPointPen()
    cs = contours if contours is not None else glyph_contours(f["glyf"], name)
    for c in cs:
        pen.beginPath()
        n = len(c)
        for i, (x, y, on) in enumerate(c):
            if on:
                # segment type of an on-curve point = kind of the segment that ends here
                seg = "qcurve" if not c[i - 1][2] else "line"
                pen.addPoint((round(x + dx), round(y)), segmentType=seg)
            else:
                pen.addPoint((round(x + dx), round(y)), segmentType=None)
        pen.endPath()


def dump_a_ufo(M, path, mode, lora=None, bry=None):
    """Write the current bold a (plus references) to a UFO for hand editing."""
    import ufoLib2
    lo, hi = M[400], M[700]
    ufo = ufoLib2.Font()
    ufo.info.familyName = f"Perla a-edit ({mode})"
    ufo.info.styleName = "Bold"
    ufo.info.unitsPerEm = hi["head"].unitsPerEm
    ufo.info.ascender, ufo.info.descender = hi["hhea"].ascent, hi["hhea"].descent
    ufo.info.xHeight, ufo.info.capHeight = 500, 700
    ufo.info.note = REF_NOTE
    order = []

    def add(name, f, src, ref=True, contours=None):
        g = ufo.newGlyph(name)
        _glyf_to_ufo(g, f, src, contours=contours)
        g.width = f["hmtx"][src][0]
        if ref:
            g.markColor = "0.6,0.6,0.6,1"
        order.append(name)
        return g

    a = add("a", hi, "a", ref=False)
    a.unicodes = [0x61]
    # the regular a in the background layer of the editable glyph, for orientation
    bg = ufo.newLayer("public.background")
    _glyf_to_ufo(bg.newGlyph("a"), lo, "a")
    add("a.regular", lo, "a")
    add("ae", hi, "ae")
    add("ordfeminine", hi, "ordfeminine")
    if lora is not None:
        add("a.lora-bold", lora, "a")
    if bry is not None:
        g = ufo.newGlyph("a.brygada-bold")
        _glyf_to_ufo(g, None, None, contours=bry[0])
        g.width = bry[1]
        g.markColor = "0.6,0.6,0.6,1"
        order.append("a.brygada-bold")
    ufo.glyphOrder = order
    ufo.lib["public.openTypeCategories"] = {}
    ufo.save(path, overwrite=True)
    return path


def load_ufo_glyph(path, name="a"):
    """Contours [[x, y, on]] and advance of `name` in a UFO (TrueType point structure)."""
    import ufoLib2
    from fontTools.pens.pointPen import AbstractPointPen
    ufo = ufoLib2.Font.open(path)
    g = ufo[name]
    cs = []

    class Rec(AbstractPointPen):
        def beginPath(self, identifier=None, **kw):
            cs.append([])

        def endPath(self):
            pass

        def addPoint(self, pt, segmentType=None, smooth=False, name=None, identifier=None, **kw):
            if segmentType == "curve" or segmentType == "move":
                raise SystemExit(f"{path}: glyph '{name or 'a'}' has cubic or open contours; "
                                 "keep the TrueType (quadratic) curves and closed contours")
            cs[-1].append([float(pt[0]), float(pt[1]), 0 if segmentType is None else 1])

        def addComponent(self, base, transformation, identifier=None, **kw):
            raise SystemExit(f"{path}: glyph 'a' must be outlines, not components")

    g.drawPoints(Rec())
    return cs, g.width


# ------------------------------------------------------------------ matching
def _align(base, new):
    """Match edited contours to the original ones (same structure), undoing contour reordering,
    start-point rotation and direction reversal. Returns aligned contours or raises."""
    left = list(range(len(new)))
    out = []
    for bi, b in enumerate(base):
        pat = [p[2] for p in b]
        B = np.array([p[:2] for p in b])
        best = None
        for ni in left:
            c = new[ni]
            if len(c) != len(b):
                continue
            for rev in (False, True):
                cc = c[::-1] if rev else c
                for r in range(len(cc)):
                    rot = cc[r:] + cc[:r]
                    if [p[2] for p in rot] != pat:
                        continue
                    err = float(np.sum((np.array([p[:2] for p in rot]) - B) ** 2))
                    if best is None or err < best[0]:
                        best = (err, ni, rot)
        if best is None:
            raise SystemExit(
                f"hand-edited bold a is not point-compatible with the regular a: original contour "
                f"{bi} has {len(b)} points ({sum(pat)} on-curve), edited contours have "
                f"{[len(c) for c in new]} points. Move points only; do not add or delete them.")
        left.remove(best[1])
        out.append([list(p) for p in best[2]])
    if left:
        raise SystemExit(f"hand-edited bold a has {len(new)} contours, the original has {len(base)}")
    return out


def _carry(targets, src_pts, deltas, radius):
    """Move each target point like the source points near it (inverse-distance weights),
    fading out with the distance to the nearest source point."""
    moved = 0.0
    for c in targets:
        for p in c:
            d = np.hypot(*(src_pts - np.array(p[:2])).T)
            dmin = float(d.min())
            if dmin > radius:
                continue
            idx = np.argsort(d)[:4]
            w = 1.0 / (d[idx] + 2.0) ** 2
            dv = (w[:, None] * deltas[idx]).sum(0) / w.sum()
            fall = 1.0 if dmin < 0.4 * radius else max(0.0, 1 - (dmin - 0.4 * radius) / (0.6 * radius))
            p[0] += dv[0] * fall
            p[1] += dv[1] * fall
            moved = max(moved, float(np.hypot(*dv)) * fall)
    return moved


def apply_manual_a(M, path, log=None):
    """Replace the bold a by the hand-edited one and carry the edit over to æ and ª."""
    hi = M[700]
    glyf, hmtx = hi["glyf"], hi["hmtx"]
    base = glyph_contours(glyf, "a")
    new, adv = load_ufo_glyph(path, "a")
    try:
        new = _align(base, new)
    except SystemExit:
        # editors (FontForge) may turn implied on-curve points (between two off-curves) into
        # real ones, and the designer may then move them: make every implied point explicit in
        # both masters (the outlines do not change), and compare again
        from .geom import explicitize
        lo = M[400]
        reg = [explicitize(c) for c in glyph_contours(lo["glyf"], "a")]
        set_glyph_contours(lo["glyf"], "a", reg)
        lo["hmtx"]["a"] = (lo["hmtx"]["a"][0], lo["glyf"]["a"].xMin)
        base = [explicitize(c) for c in base]
        set_glyph_contours(glyf, "a", base)
        new = _align(base, [explicitize(c) for c in new])
    B = np.array([p[:2] for c in base for p in c])
    N = np.array([p[:2] for c in new for p in c])
    deltas = N - B
    old_adv = hmtx["a"][0]
    set_glyph_contours(glyf, "a", new)
    hmtx["a"] = (int(round(adv)), glyf["a"].xMin)
    rep = {"a": round(float(np.hypot(*deltas.T).max()), 1)}
    # æ: its a-part sits where the a is
    if "ae" in glyf.keys() and not glyf["ae"].isComposite():
        cs = glyph_contours(glyf, "ae")
        rep["ae"] = round(_carry(cs, B, deltas, radius=40.0), 1)
        set_glyph_contours(glyf, "ae", cs)
        hmtx["ae"] = (hmtx["ae"][0], glyf["ae"].xMin)
    # ª: a small a; map it onto the a's bounding box, carry, map back (deltas scaled)
    if "ordfeminine" in glyf.keys() and not glyf["ordfeminine"].isComposite():
        cs = glyph_contours(glyf, "ordfeminine")
        P = np.array([p[:2] for c in cs for p in c])
        lo_o, hi_o = P.min(0), P.max(0)
        lo_a, hi_a = B.min(0), B.max(0)
        k = (hi_a - lo_a) / np.maximum(hi_o - lo_o, 1e-6)
        mapped = [[[(p[0] - lo_o[0]) * k[0] + lo_a[0], (p[1] - lo_o[1]) * k[1] + lo_a[1], p[2]] for p in c] for c in cs]
        before = [[list(p) for p in c] for c in mapped]
        rep["ordfeminine"] = round(_carry(mapped, B, deltas, radius=40.0) / float(k.mean()), 1)
        for c, cb, cm in zip(cs, before, mapped):
            for p, pb, pm in zip(c, cb, cm):
                p[0] += (pm[0] - pb[0]) / k[0]
                p[1] += (pm[1] - pb[1]) / k[1]
        set_glyph_contours(glyf, "ordfeminine", cs)
        hmtx["ordfeminine"] = (hmtx["ordfeminine"][0], glyf["ordfeminine"].xMin)
    # composites on a that share its advance follow a width change
    if int(round(adv)) != old_adv:
        for name in hi.getGlyphOrder():
            g = glyf[name]
            if g.isComposite() and g.components[0].glyphName == "a" and hmtx[name][0] == old_adv:
                hmtx[name] = (int(round(adv)), hmtx[name][1])
    if log is not None:
        log.append(("manual-bold-a", {"file": path, "max move": rep}))
    return rep
