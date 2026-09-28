"""Rebuild a variable font from edited static masters (same glyph order / point structure)."""
import copy

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, InstanceDescriptor, SourceDescriptor
from fontTools.ttLib import TTFont
from fontTools import varLib


def build_vf(masters, orig_vf, italic=False):
    """masters: {400: TTFont, 700: TTFont}. orig_vf: TTFont (for name/STAT/fvar instances)."""
    for w, f in masters.items():
        if w != 400:
            f["GSUB"] = copy.deepcopy(masters[400]["GSUB"])
    ds = DesignSpaceDocument()
    ax = AxisDescriptor()
    ax.tag, ax.name, ax.minimum, ax.default, ax.maximum = "wght", "Weight", 400, 400, 700
    ds.addAxis(ax)
    for w, f in sorted(masters.items()):
        s = SourceDescriptor()
        s.font = f
        s.location = {"Weight": w}
        s.name = f"master{w}"
        if w == 400:
            s.copyInfo = s.copyLib = s.copyGroups = s.copyFeatures = True
        ds.addSource(s)
    for inst in orig_vf["fvar"].instances:
        i = InstanceDescriptor()
        i.location = {"Weight": inst.coordinates["wght"]}
        i.styleName = orig_vf["name"].getDebugName(inst.subfamilyNameID)
        ds.addInstance(i)
    vf, _, _ = varLib.build(ds, exclude=["STAT", "GSUB"], optimize=True)
    vf["GSUB"] = copy.deepcopy(orig_vf["GSUB"])
    # flag overlaps for renderers that need the hint (harmless elsewhere)
    glyf = vf["glyf"]
    for gname in vf.getGlyphOrder():
        g = glyf[gname]
        if g.isComposite():
            g.components[0].flags |= 0x0400
        elif g.numberOfContours > 0:
            g.flags[0] |= 0x40
    # restore original naming / STAT / fvar instance names
    vf["name"] = copy.deepcopy(orig_vf["name"])
    vf["STAT"] = copy.deepcopy(orig_vf["STAT"])
    vf["fvar"].axes[0].axisNameID = orig_vf["fvar"].axes[0].axisNameID
    for a, b in zip(vf["fvar"].instances, orig_vf["fvar"].instances):
        a.subfamilyNameID = b.subfamilyNameID
        a.postscriptNameID = b.postscriptNameID
    return vf
