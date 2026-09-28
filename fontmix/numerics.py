"""Extended numerals from Brygada: oldstyle, numerators/denominators, superiors/inferiors,
fraction bar, prebuilt fractions — plus the OpenType features that reach them."""
import copy

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.varLib import instancer

from .figures import FIGS, brygada_contours
from .geom import set_glyph_contours

SUPS = ["uni2070", "uni00B9", "uni00B2", "uni00B3", "uni2074", "uni2075", "uni2076", "uni2077", "uni2078", "uni2079"]
SUBS = [f"uni208{i}" for i in range(10)]
OSF = [f + ".osf" for f in FIGS]
TOSF = [f + ".tosf" for f in FIGS]
TF = [f + ".tf" for f in FIGS]
NUMR = [f + ".numr" for f in FIGS]
DNOM = [f + ".dnom" for f in FIGS]
PREBUILT = {"onehalf": ("one", "two"), "onequarter": ("one", "four"), "threequarters": ("three", "four")}


def add_glyph(font, name):
    order = font.getGlyphOrder()
    if name in order:
        return
    order = order + [name]
    font.setGlyphOrder(order)
    glyf = font["glyf"]
    g = Glyph()
    g.numberOfContours = 0
    glyf.glyphs[name] = g
    glyf.glyphOrder = order
    font["hmtx"].metrics[name] = (0, 0)


def stage_numerics(M, bry_path, bry_weights, scale=1.05, tab_width=650, sup_dy=-40, shear=0.0, emb=None):
    new = OSF + TOSF + NUMR + DNOM + [s for s in SUPS if s not in ("uni00B9", "uni00B2", "uni00B3", "uni2074")] + SUBS
    for w, f in M.items():
        B = instancer.instantiateVariableFont(TTFont(bry_path), {"wght": bry_weights[w]})
        for n in new:
            add_glyph(f, n)
        glyf, hmtx = f["glyf"], f["hmtx"]
        jobs = [(o, o, None, 0) for o in OSF]
        jobs += [(t, t, tab_width, 0) for t in TOSF]
        jobs += [(n, n, None, 0) for n in NUMR + DNOM]
        jobs += [(s, fg + ".sups", None, sup_dy) for s, fg in zip(SUPS, FIGS) if s not in ("uni00B9", "uni00B2", "uni00B3", "uni2074")]
        jobs += [(s, fg + ".subs", None, 0) for s, fg in zip(SUBS, FIGS)]
        jobs += [("fraction", "fraction", None, 0)]
        from .figures import figure_contours
        for tgt, src, fixed, dy in jobs:
            full = tgt.endswith((".osf", ".tosf"))
            d = (emb or {}).get(w, 0) * (1.0 if full else 0.6)
            cs, d = figure_contours(bry_path, bry_weights, w, src, scale, dy, shear, d, fallback=648)
            adv = round(B["hmtx"][src][0] * scale + 2 * d)
            if fixed:
                shift = round((fixed - adv) / 2)
                for c in cs:
                    for p in c:
                        p[0] += shift
                adv = fixed
            set_glyph_contours(glyf, tgt, cs)
            hmtx[tgt] = (adv, glyf[tgt].xMin)
        # prebuilt fractions as composites of numerator / fraction bar / denominator
        bg = B["glyf"]
        for name, (a, b) in PREBUILT.items():
            comps = bg[name].components  # roman layout: numr, fraction, dnom
            xs = [round(c.x * scale) for c in comps]
            g = Glyph()
            g.numberOfContours = -1
            g.components = []
            for gname, x in zip((a + ".numr", "fraction", b + ".dnom"), xs):
                c = GlyphComponent()
                c.glyphName, c.x, c.y, c.flags = gname, x, 0, 0x4  # ROUND_XY_TO_GRID
                g.components.append(c)
            glyf.glyphs[name] = g
            g.recalcBounds(glyf)
            hmtx[name] = (round(B["hmtx"][name][0] * scale), g.xMin)
        # cmap for the new superiors / inferiors
        for t in f["cmap"].tables:
            if t.isUnicode():
                for s in SUPS + SUBS:
                    cp = int(s[3:], 16)
                    t.cmap[cp] = s


FEA = """
@FIG = [{figs}];
@TF = [{tf}];
@OSF = [{osf}];
@TOSF = [{tosf}];
@NUMR = [{numr}];
@DNOM = [{dnom}];
@SUPS = [{sups}];
@SUBS = [{subs}];

lookup ONUM {{ sub @FIG by @OSF; sub @TF by @TOSF; }} ONUM;
lookup LNUM {{ sub @OSF by @FIG; sub @TOSF by @TF; }} LNUM;
lookup TNUM2 {{ sub @OSF by @TOSF; }} TNUM2;
lookup PNUM2 {{ sub @TOSF by @OSF; }} PNUM2;
lookup NUMR {{ sub @FIG by @NUMR; sub @TF by @NUMR; sub @OSF by @NUMR; sub @TOSF by @NUMR; }} NUMR;
lookup DNOM {{ sub @FIG by @DNOM; sub @TF by @DNOM; sub @OSF by @DNOM; sub @TOSF by @DNOM; }} DNOM;
lookup SUPS {{ sub @FIG by @SUPS; sub @TF by @SUPS; sub @OSF by @SUPS; sub @TOSF by @SUPS; }} SUPS;
lookup SUBS {{ sub @FIG by @SUBS; sub @TF by @SUBS; sub @OSF by @SUBS; sub @TOSF by @SUBS; }} SUBS;
lookup FRAC1 {{ sub slash by fraction; }} FRAC1;
lookup FRAC2 {{ sub [fraction @DNOM] @NUMR' by @DNOM; }} FRAC2;

feature onum {{ lookup ONUM; }} onum;
feature lnum {{ lookup LNUM; }} lnum;
feature tnum {{ lookup TNUM2; }} tnum;
feature pnum {{ lookup PNUM2; }} pnum;
feature numr {{ lookup NUMR; }} numr;
feature dnom {{ lookup DNOM; }} dnom;
feature sups {{ lookup SUPS; }} sups;
feature subs {{ lookup SUBS; }} subs;
feature sinf {{ lookup SUBS; }} sinf;
feature frac {{ lookup FRAC1; lookup NUMR; lookup FRAC2; }} frac;
"""


def _fea():
    j = " ".join
    return FEA.format(figs=j(FIGS), tf=j(TF), osf=j(OSF), tosf=j(TOSF), numr=j(NUMR), dnom=j(DNOM),
                      sups=j(SUPS), subs=j(SUBS))


def add_numeric_features(vf):
    """Compile the numeric features separately and merge them into vf's GSUB (appending)."""
    tmp = TTFont()
    tmp.setGlyphOrder(vf.getGlyphOrder())
    addOpenTypeFeaturesFromString(tmp, _fea(), tables=["GSUB"])
    new = tmp["GSUB"].table
    gsub = vf["GSUB"].table
    n0 = len(gsub.LookupList.Lookup)
    def _records(obj, seen=None):
        """All SubstLookupRecords reachable from a subtable (any contextual format)."""
        out = []
        if isinstance(obj, list):
            for o in obj:
                out += _records(o)
            return out
        if not hasattr(obj, "__dict__"):
            return out
        for k, v in vars(obj).items():
            if k == "SubstLookupRecord":
                out += list(v or [])
            elif isinstance(v, (list, ot.BaseTable)) and k not in ("Coverage", "BacktrackCoverage",
                                                                   "InputCoverage", "LookAheadCoverage"):
                out += _records(v)
        return out

    for lk in new.LookupList.Lookup:
        if lk.LookupType in (5, 6):
            for st in lk.SubTable:
                for r in _records(st):
                    r.LookupListIndex += n0
        gsub.LookupList.Lookup.append(lk)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)

    replace = {"frac", "sups"}
    extend = {"tnum", "pnum"}
    feats = gsub.FeatureList.FeatureRecord
    all_langsys = []
    for sr in gsub.ScriptList.ScriptRecord:
        if sr.Script.DefaultLangSys:
            all_langsys.append(sr.Script.DefaultLangSys)
        all_langsys += [lr.LangSys for lr in sr.Script.LangSysRecord]
    for fr in new.FeatureList.FeatureRecord:
        idx = [i + n0 for i in fr.Feature.LookupListIndex]
        existing = [f for f in feats if f.FeatureTag == fr.FeatureTag]
        if existing and fr.FeatureTag in replace:
            for f in existing:
                f.Feature.LookupListIndex = list(idx)
                f.Feature.LookupCount = len(idx)
        elif existing and fr.FeatureTag in extend:
            for f in existing:
                f.Feature.LookupListIndex = list(f.Feature.LookupListIndex) + idx
                f.Feature.LookupCount = len(f.Feature.LookupListIndex)
        else:
            rec = ot.FeatureRecord()
            rec.FeatureTag = fr.FeatureTag
            rec.Feature = ot.Feature()
            rec.Feature.FeatureParams = None
            rec.Feature.LookupListIndex = idx
            rec.Feature.LookupCount = len(idx)
            feats.append(rec)
            fi = len(feats) - 1
            for ls in all_langsys:
                ls.FeatureIndex.append(fi)
                ls.FeatureCount = len(ls.FeatureIndex)
    gsub.FeatureList.FeatureCount = len(feats)
    sort_features(gsub)


def sort_features(gsub_table):
    """Sort FeatureList by tag (stable) and remap every reference to feature indices."""
    feats = gsub_table.FeatureList.FeatureRecord
    order = sorted(range(len(feats)), key=lambda i: (feats[i].FeatureTag, i))
    remap = {old: new for new, old in enumerate(order)}
    gsub_table.FeatureList.FeatureRecord = [feats[i] for i in order]
    for sr in gsub_table.ScriptList.ScriptRecord:
        systems = ([sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []) + [lr.LangSys for lr in sr.Script.LangSysRecord]
        for ls in systems:
            ls.FeatureIndex = sorted(remap[i] for i in ls.FeatureIndex)
            if ls.ReqFeatureIndex != 0xFFFF:
                ls.ReqFeatureIndex = remap[ls.ReqFeatureIndex]
    fv = getattr(gsub_table, "FeatureVariations", None)
    if fv:
        for rec in fv.FeatureVariationRecord:
            for sub in rec.FeatureTableSubstitution.SubstitutionRecord:
                sub.FeatureIndex = remap[sub.FeatureIndex]
