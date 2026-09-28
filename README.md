# Perla

A text serif derived from **Lora** and **Brygada 1918**.

Lora is the base. Its skeleton, x-height, spacing, wedge serifs, ligatures (fi, fl) and italic
carry most of what you liked, including its clarity on screens. Brygada's traits are then worked
*into* Lora's letters rather than pasted in:

| Trait (from Brygada) | How it was applied |
| --- | --- |
| Ball / teardrop terminals | Brygada's own paths. The terminals of c, f, ſ, j, r, y, J, є, э and the tail of ŋ are cut out of Brygada and spliced onto Lora's strokes (`fontmix/splice.py`, `fontmix/splice_jobs.py`); the joint is blended so the stroke tapers smoothly. The r's ball is shrunk 14% and its spacing restored. The italic keeps Lora's own terminals. g, ǥ, fi, fl, з, ƒ keep Lora's teardrops. |
| Bold | The bold master of Brygada-derived glyphs is Perla Regular + Lora's own Regular→Bold movement (`fontmix/boldxfer.py`): spliced sections are matched along the Lora path they replaced (stem stretches keep the stem's movement), replaced counters around their loop, whole-copied glyphs (S, z, Z, Q) by nearest point. f and a keep Brygada's own bold (the bold a, æ and ª hand-adjusted, `manual/a-bold-brygada.ufo`); s and the figures are a lighter Brygada thickened evenly (ink-aware offset); figures with ball terminals are merged into one outline first. |
| Arches and bowls | Lora's own, unchanged (n h m u b d p q and relatives are identical to Lora in every weight). Brygada-style arches are retired for now; the code is kept (`VARIANTS` in `build_font.py`: `main` = smooth morph of Lora's arches to Brygada's joins, `literal` = spliced Brygada paths). |
| Brygada letters | The Q's tail (laid onto Perla's O), Brygada's Z/z terminal serifs, a taller t, and Brygada's s, S, a/æ/ª, z, Z (copied, scaled to Perla's metrics; accents re-anchored). |
| Italic y | Brygada's u-shaped italic y: Lora's italic u (right arm straightened) with the tail of Lora's g. |
| Figures | Brygada's lining, tabular and oldstyle figures, numerators/denominators, superiors/inferiors and fraction bar, scaled to Lora's figure height, weight-matched per master by interpolating Brygada's weight axis, and (italic) re-slanted from 8° to Lora's 3°. Figure kerning is re-derived for the new shapes. The 1 and 4 stand on Lora's own foot (long flared bracket left, near-square right, shorter slab). |

## Files

- `dist/fonts/variable/`: `Perla[wght].ttf`, `Perla-Italic[wght].ttf` (weight 400–700)
- `dist/fonts/ttf/`: static Regular, Medium, SemiBold, Bold and their italics (overlaps removed, ttfautohinted)
- `dist/fonts/webfonts/`: WOFF2 versions of all of the above
- `dist/specimen.html`: the specimen page
- `dist/OFL.txt`: license

OpenType features: `liga` `kern` `onum` `lnum` `tnum` `pnum` `frac` `numr` `dnom` `sups` `subs` `sinf`
plus everything Lora already had (`case`, `locl`, `ordn`, …).

## Rebuild

```sh
uv run python build_font.py all   # edits Lora's masters, rebuilds the variable fonts into out/
uv run python finalize.py         # naming, static instances, hinting, woff2 -> dist/
```

All design decisions are data in `fontmix/spec_roman.py` and `fontmix/spec_italic.py` (counter
widening per glyph), `fontmix/splice_jobs.py` (which Brygada sections are spliced where: cut lines,
alignment, blending), `fontmix/letters.py` (Brygada letters, t height). The build variant (first entry of `VARIANTS` in `build_font.py`) selects the arch treatment. Figure weights and slant live in the same files
and in `build_font.py`. Change a number and rebuild. The font name is set in `fontmix/naming.py`.

How it works: both Lora masters (400 and 700) are extracted from the variable font. Every change
keeps the two masters point-compatible, so the result is again a true variable font
(`fontmix/build.py`). The ball construction is in `fontmix/balls.py`, the counter widening in
`fontmix/widen.py`, and accent/anchor propagation in `fontmix/propagate.py`.

## Hand-editing the bold a

The bold a (and with it æ, ª and all accented a's) can be edited by hand in any font editor
that opens UFO files (FontForge, Fontra, Glyphs, RoboFont, …).

- `manual/a-bold-brygada.ufo`: Brygada's own bold a, as Perla has it now
- `manual/a-bold-transfer.ufo`: Perla Regular a + Lora's Regular→Bold movement (the approach used for most letters)

Edit glyph `a` (the regular a is in its background layer; `a.regular`, `a.lora-bold`,
`a.brygada-bold`, `ae`, `ordfeminine` are references and are not read back). **Move points and
handles only; do not add, delete or convert points**, because the bold must stay
point-compatible with the regular for the variable font. A changed start point or contour
direction is fine. Changing the advance width is fine too.

Pick the approach with `BOLD_A_MODE` in `build_font.py` (`"brygada"` or `"transfer"`, or
`PERLA_BOLD_A=transfer` for a single build), then rebuild. The build replaces the bold a with the
edited one, moves the matching points of æ and ª by the same amounts (ª scaled), and the accented
a's follow as composites. The intermediate weights interpolate automatically. It prints how far
the points moved (`hand-edited bold a: …`) or refuses an incompatible file with an explanation.
`uv run python tools/export_bold_a.py --force` re-exports fresh, unedited files.

## License

SIL Open Font License 1.1. "Lora" is a Reserved Font Name, which is why this derivative has
its own name. Copyright notices of both source projects are retained in the fonts and in `OFL.txt`.
