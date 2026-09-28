"""Build the fonts: uv run python build_font.py [roman|italic|all]"""
import os, sys, time
from fontTools.ttLib import TTFont
from fontmix.masters import load_masters
from fontmix.build import build_vf
from fontmix.stages import stage_widen, stage_balls
from fontmix.figures import stage_figures
from fontmix.numerics import stage_numerics, add_numeric_features
from fontmix.letters import stage_brygada_letters
from fontmix.tweaks import bracket_chamfers as bracket_feet
from fontmix.kerning import stage_kern_figures, current_kerning, FIGS
from fontTools.varLib import instancer


def brygada_fig_kerning(path, weights, scale=1.05):
    out = {}
    for w, bw in weights.items():
        B = instancer.instantiateVariableFont(TTFont(path), {"wght": bw})
        k = current_kerning(B, [(a, b) for a in FIGS for b in FIGS])
        out[w] = {p: round(v * scale) for p, v in k.items() if v}
    return out


LORA = {"roman": "src/lora_Lora[wght].ttf", "italic": "src/lora_Lora-Italic[wght].ttf"}
BRYG = {"roman": "src/brygada1918_Brygada1918[wght].ttf", "italic": "src/brygada1918_Brygada1918-Italic[wght].ttf"}
OUT = {"roman": "out/Roman-VF.ttf", "italic": "out/Italic-VF.ttf"}


BOLD_FIGURES_FROM_LORA = False
# bold figures: a lighter Brygada, thickened evenly -> Lora-like contrast (stems ~144, hairlines ~72)
FIG_WEIGHTS = {"roman": {400: 400, 700: 400}, "italic": {400: 400, 700: 400}}  # bold figures derived from the regular (figures.CONTRAST_BOLD)
FIG_EMB = {700: 17}
ARCH_GLYPHS = ["n", "h", "m", "u", "b", "p", "d", "q", "hbar", "thorn", "dcroat", "dcaron"]
ARCH_FACTOR = 1.0  # main: how far Lora's arches move toward Brygada's join heights
# first entry = the Elanora build; further entries are extra variants (dist/fonts/versions).
# Arch changes are retired (2026-09-28): Elanora keeps Lora's arches and bowls as they are
# ("classic"); "main" (smooth arch morph) and "literal" (spliced Brygada arches) remain available.
VARIANTS = {"roman": ["classic"], "italic": ["main"]}
# bold a (and æ, ª): "brygada" = Brygada's own bold; "transfer" = Elanora Regular + Lora's
# Regular->Bold movement, like most other letters. A hand-edited version of the chosen one is
# read from manual/a-bold-<mode>.ufo when that file exists (see tools/export_bold_a.py).
BOLD_A_MODE = os.environ.get("ELANORA_BOLD_A", "brygada")


def manual_figs(M, style, src):
    """Hand-edited bold figures: export with ELANORA_DUMP_FIGS=<dir>, read back from
    manual/figures-bold-<style>.ufo when that file exists (tools/export_bold_figures.py)."""
    from fontmix import manual
    if os.environ.get("ELANORA_DUMP_FIGS"):
        manual.dump_figs_ufo(M, os.path.join(os.environ["ELANORA_DUMP_FIGS"], f"figures-bold-{style}.ufo"),
                             style, lora=load_masters(src)[700])
    elif os.path.exists(f"manual/figures-bold-{style}.ufo"):
        print(f"hand-edited bold figures ({style}):", manual.apply_manual_figs(M, f"manual/figures-bold-{style}.ufo"))


def build(style, log=None, variant="main", out=None):
    src = LORA[style]
    M = load_masters(src)
    import copy as _copy
    if style == "roman":
        from fontmix import spec_roman as S
        # classic keeps Lora's arches and bowls exactly, including their proportions
        fields = stage_widen(M, S.WIDEN) if variant in ("main", "literal") else {}
        L_ref = _copy.deepcopy(M)  # Lora (widened): source of the reg->bold movement
        from fontmix.splice_jobs import run_jobs, ROMAN_JOBS
        from fontmix.tweaks import arm_joins_measured
        jobs = dict(ROMAN_JOBS)
        if variant in ("main", "classic"):
            # arches stay Lora's own paths: moved smoothly to Brygada's joins (main) or untouched (classic)
            for g in ARCH_GLYPHS:
                jobs.pop(g, None)
        run_jobs(M, BRYG[style], {400: 400, 700: 660}, 500 / 460, jobs, log=log)
        if variant == "main":
            from fontmix.tweaks import arch_morph
            rep = arch_morph(M, BRYG[style], {400: 400, 700: 660}, 500 / 460, ARCH_FACTOR,
                             glyphs=ARCH_GLYPHS + ["eng", "uni03BC"], thick={400: 1.0, 700: 1.15})

        elif variant == "literal":
            rep = arm_joins_measured(M, BRYG[style], {400: 400, 700: 660}, 500 / 460, 1.0,
                                     glyphs=["eng", "uni03BC"])
        else:
            rep = {}
        if log is not None:
            log.append(("splice-armjoins", rep))
        stage_balls(M, S.BALLS, fields, log=log)
        stage_brygada_letters(M, BRYG[style], log=log)
        from fontmix.geom import fix_coincident, glyph_contours as _gc, set_glyph_contours as _sc, embolden
        for w in M:  # Brygada's a / æ / ª: bowl piece touches the stem piece edge-to-edge -> overlap it
            for g in ("a", "ae", "ordfeminine"):
                _sc(M[w]["glyf"], g, fix_coincident(_gc(M[w]["glyf"], g)))
        from fontmix.tweaks import match_spacing
        match_spacing(M, L_ref, "z", ["y", "x", "o", "a", "e", "n"], ["y", "o", "a", "e", "n"], left_bias=6)
        # r: smaller Brygada ball, and Lora's right sidebearing back
        from fontmix.tweaks import shrink_ball, respace
        shrink_ball(M[400], "r", (430, 440), 70, 0.86)
        g = M[400]["glyf"]["r"]
        M[400]["hmtx"]["r"] = (g.xMax + 8, g.xMin)
        stage_figures(M, BRYG[style], FIG_WEIGHTS["roman"], emb=FIG_EMB)
        stage_numerics(M, BRYG[style], FIG_WEIGHTS["roman"], emb=FIG_EMB)
        from fontmix.tweaks import graft_lora_feet
        rep = graft_lora_feet(M, load_masters(src), "roman")
        from fontmix.numerics import OSF, NUMR, DNOM, SUPS, SUBS
        from fontmix.figures import FIGS
        for w in M:
            respace(M[w], FIGS + OSF, 0.75)
            respace(M[w], NUMR + DNOM + SUPS + SUBS, 0.85)
        from fontmix.boldxfer import stage_bold_transfer
        # f and a keep Brygada's own bold (user preference); s gets a thickened lighter Brygada
        keep_bry = {"f", "longs", "a", "ae", "ordfeminine"}
        a_family = ["a", "ae", "ordfeminine"]
        if BOLD_A_MODE == "transfer":
            keep_bry -= set(a_family)
        xfer = [g for g in list(ROMAN_JOBS) + ["S", "z", "Z", "Q"] if g not in keep_bry]
        if BOLD_A_MODE == "transfer":
            xfer += a_family
        if variant in ("main", "classic"):
            xfer = [g for g in xfer if g not in ARCH_GLYPHS]  # bold arches are Lora Bold's own
        from fontmix.transplant import bry_instance
        from fontmix.figures import brygada_contours as _bc
        Bs = bry_instance(BRYG[style], 500)
        cs = [[[p[0] + 19, p[1], p[2]] for p in c] for c in embolden(_bc(Bs, "s", 500 / 460), 19)]
        # the thickening also grows the s up and down: bring its extremes back to the regular s's
        rys = [p[1] for c in _gc(M[400]["glyf"], "s") for p in c]
        bys = [p[1] for c in cs for p in c]
        k = (max(rys) - min(rys)) / (max(bys) - min(bys))
        cs = [[[p[0], min(rys) + (p[1] - min(bys)) * k, p[2]] for p in c] for c in cs]
        _sc(M[700]["glyf"], "s", cs)
        M[700]["hmtx"]["s"] = (round(Bs["hmtx"]["s"][0] * 500 / 460 + 38), M[700]["glyf"]["s"].xMin)
        if BOLD_FIGURES_FROM_LORA:
            xfer += FIGS + [f + ".tf" for f in FIGS]
        stage_bold_transfer(M, L_ref, xfer, log=log, nearest={"S", "z", "Z", "Q", "a", "ae", "ordfeminine"})
        from fontmix import manual
        if os.environ.get("ELANORA_DUMP_A"):
            from fontmix.transplant import bry_instance as _bi
            _B = _bi(BRYG[style], 660)
            manual.dump_a_ufo(M, os.environ["ELANORA_DUMP_A"], BOLD_A_MODE, lora=load_masters(src)[700],
                              bry=(_bc(_B, "a", 500 / 460), round(_B["hmtx"]["a"][0] * 500 / 460)))
        elif os.path.exists(f"manual/a-bold-{BOLD_A_MODE}.ufo"):
            print("hand-edited bold a:", manual.apply_manual_a(M, f"manual/a-bold-{BOLD_A_MODE}.ufo"))
        if variant == "literal":
            # spliced Brygada arches: repair the bold joins the Lora reg->bold transfer leaves thin
            from fontmix.tweaks import uniform_joins, restore_top_join
            from fontmix.tweaks import restore_join
            for g, zs in (("b", ("top", "bottom")), ("p", ("top", "bottom")), ("thorn", ("top", "bottom")),
                          ("d", ("top", "bottom")), ("q", ("top", "bottom")), ("dcroat", ("top", "bottom")),
                          ("dcaron", ("top", "bottom"))):
                for z in zs:
                    restore_join(M[400], M[700], g, z)
            jr = None
            from fontmix.tweaks import offset_joins
            for it in range(int(os.environ.get("UJ_ITERS", "4"))):
                jr = offset_joins(M[700], L_ref[700], M[400], handle_cap=float(os.environ.get("HCAP", "25")) if it == 0 else 0.0)
            from fontmix.tweaks import straighten_stems
            for g in ("n", "h", "m", "u", "b", "p", "d", "q", "r", "hbar", "thorn", "dcroat", "dcaron", "eng"):
                straighten_stems(M[400], M[700], g)
            from fontmix.tweaks import restore_smooth
            for g in ("n", "h", "m", "u", "b", "p", "d", "q", "hbar", "thorn", "dcroat", "dcaron", "eng", "uni03BC"):
                if not os.environ.get("NOSMOOTH") and g in M[700]["glyf"].keys() and not M[700]["glyf"][g].isComposite():
                    restore_smooth(M[400], M[700], g)
            if log is not None:
                log.append(("bold-joins", jr))
        if log is not None:
            log.append(("brygada-feet", rep))
        manual_figs(M, style, src)
        kern_log = stage_kern_figures(M, load_masters(src), brygada_fig_kerning(BRYG[style], {400: 400, 700: 648}))
    else:
        from fontmix import spec_italic as S
        from fontmix.tweaks import italic_y_from_u_g, straighten_y_arm
        from fontmix.transplant import reanchor
        from fontmix.splice_jobs import run_jobs, ITALIC_JOBS, IT_SHEAR
        reanchor(M, "y", italic_y_from_u_g(M))
        straighten_y_arm(M)
        from fontmix.letters import italic_tall_t
        italic_tall_t(M)
        if variant == "balls":
            run_jobs(M, BRYG[style], {400: 400, 700: 640}, 500 / 460, ITALIC_JOBS, shear=IT_SHEAR, log=log)
            from fontmix.transplant import transplant, match_weight
            wx = {w: match_weight(M[w], BRYG[style], "n", 250, 500 / 460) for w in M}
            reanchor(M, "x", transplant(M, BRYG[style], "x", scale=500 / 460, weights=wx, shear=IT_SHEAR))
        stage_balls(M, S.BALLS, None, log=log)
        stage_figures(M, BRYG[style], FIG_WEIGHTS["italic"], shear=S.FIG_SHEAR, emb=FIG_EMB)
        stage_numerics(M, BRYG[style], FIG_WEIGHTS["italic"], shear=S.FIG_SHEAR, emb=FIG_EMB)
        from fontmix.spec_roman import FEET
        import math as _m
        from fontmix.tweaks import graft_lora_feet
        rep = graft_lora_feet(M, load_masters(src), "italic")
        from fontmix.tweaks import respace
        from fontmix.numerics import OSF, NUMR, DNOM, SUPS, SUBS
        from fontmix.figures import FIGS
        for w in M:
            respace(M[w], FIGS + OSF, 0.75)
            respace(M[w], NUMR + DNOM + SUPS + SUBS, 0.85)
        if log is not None:
            log.append(("brygada-feet", rep))
        manual_figs(M, style, src)
        kern_log = stage_kern_figures(M, load_masters(src), brygada_fig_kerning(BRYG[style], S.FIG_WEIGHTS))
    if log is not None:
        log.append(("kern-deltas", {w: len(v) for w, v in kern_log.items()}))
        log.append(("kern-sample", {w: {a+'/'+b_: d for (a, b_), d in list(v.items())[:12]} for w, v in kern_log.items()}))
    vf = build_vf(M, TTFont(src))
    add_numeric_features(vf)
    if style == "roman":
        # no fi / fl ligatures in the roman (the italic keeps Lora's): the roman f has a ball
        # terminal. The encoded characters U+FB01 / U+FB02 stay in the font.
        from fontmix.tweaks import remove_gsub_feature
        remove_gsub_feature(vf, "liga")
    out = out or OUT[style]
    vf.save(out)
    return out


if __name__ == "__main__":
    os.makedirs("out", exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "versions"):
        for style, vs in VARIANTS.items():
            for v in vs[1:]:
                print("built", build(style, variant=v, out=f"out/{style.capitalize()}-VF-{v}.ttf"))
        if which == "versions":
            sys.exit()
    for style in (["roman", "italic"] if which == "all" else [which]):
        t = time.time()
        log = []
        out = build(style, log=log, variant=VARIANTS[style][0])
        for name, circ in log:
            if name.startswith(("kern", "brygada", "splice", "bold")):
                print(" ", name, circ)
            else:
                print(" ", name, {w: tuple(round(v) for v in c) for w, c in circ.items()})
        print("built", out, round(time.time() - t, 1), "s")
