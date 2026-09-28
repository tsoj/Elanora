"""Propagate horizontal changes of base glyphs to composites and GPOS anchors."""


def _subtables(font, tag, types):
    if tag not in font:
        return
    for lk in font[tag].table.LookupList.Lookup:
        for st in lk.SubTable:
            t = lk.LookupType
            if t == 9:  # extension
                t = st.ExtensionLookupType
                st = st.ExtSubTable
            if t in types:
                yield t, st


def propagate(font, fields):
    """fields: {glyphname: obj with .dx(x, y) and .total()} for glyphs whose outlines were
    already changed (and hmtx updated). Updates composites (advance + mark offsets) and the
    GPOS base anchors of all affected glyphs. Returns dict of effective fields incl. composites."""
    glyf, hmtx = font["glyf"], font["hmtx"]
    eff = dict(fields)
    # composites in dependency order (iterate until stable)
    changed = True
    done = set()
    while changed:
        changed = False
        for name in font.getGlyphOrder():
            g = glyf[name]
            if name in done or not g.isComposite():
                continue
            base = g.components[0]
            if base.glyphName not in eff:
                continue
            if any(c.glyphName in eff and i > 0 for i, c in enumerate(g.components)):
                pass
            fld = eff[base.glyphName]
            ox = base.x
            for c in g.components[1:]:
                cg = glyf[c.glyphName]
                cg.recalcBounds(glyf)
                if cg.numberOfContours == 0 and not cg.isComposite():
                    continue
                cx = (cg.xMin + cg.xMax) / 2 + c.x - ox
                cy = (cg.yMin + cg.yMax) / 2 + c.y - base.y
                c.x = int(round(c.x + fld.dx(cx, cy)))
            adv, lsb = hmtx[name]
            hmtx[name] = (int(round(adv + fld.total())), lsb)
            g.recalcBounds(glyf)
            hmtx[name] = (hmtx[name][0], g.xMin)
            eff[name] = _Shifted(fld, ox)
            done.add(name)
            changed = True
    # GPOS base / ligature anchors
    for t, st in _subtables(font, "GPOS", (4, 5)):
        if t == 4:
            for gname, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if gname in eff:
                    for a in rec.BaseAnchor:
                        if a is not None:
                            a.XCoordinate = int(round(a.XCoordinate + eff[gname].dx(a.XCoordinate, a.YCoordinate)))
        elif t == 5:
            for gname, lig in zip(st.LigatureCoverage.glyphs, st.LigatureArray.LigatureAttach):
                if gname in eff:
                    for comp in lig.ComponentRecord:
                        for a in comp.LigatureAnchor:
                            if a is not None:
                                a.XCoordinate = int(round(a.XCoordinate + eff[gname].dx(a.XCoordinate, a.YCoordinate)))
    return eff


class _Shifted:
    def __init__(self, fld, ox):
        self.fld, self.ox = fld, ox

    def dx(self, x, y=None):
        return self.fld.dx(x - self.ox, y)

    def total(self):
        return self.fld.total()
