# Elanora

A text serif derived from **Lora** and **Brygada 1918**.

Lora is the base: its skeleton, x-height, spacing, wedge serifs, italic (with its fi and fl
ligatures) and clarity on screens. Brygada's traits are worked *into* Lora's letters rather than
pasted in:

| Trait (from Brygada) | How it was applied |
| --- | --- |
| Ball / teardrop terminals | Brygada's own paths. The terminals of c, f, ſ, j, r, y, J, є, э and the tail of ŋ are cut out of Brygada and spliced onto Lora's strokes (`fontmix/splice.py`, `fontmix/splice_jobs.py`); the joint is blended so the stroke tapers smoothly. The r's ball is shrunk 14% and its spacing restored. The italic keeps Lora's own terminals. g, ǥ, fi, fl, з, ƒ keep Lora's teardrops. |
| Bold | The bold master of Brygada-derived glyphs is Elanora Regular + Lora's own Regular→Bold movement (`fontmix/boldxfer.py`): spliced sections are matched along the Lora path they replaced (stem stretches keep the stem's movement), replaced counters around their loop, whole-copied glyphs (S, z, Z, Q) by nearest point. f and a keep Brygada's own bold (the bold a, æ and ª hand-adjusted, `manual/a-bold-brygada.ufo`); s is a lighter Brygada thickened evenly. Bold figures: the regular figure (overlaps merged) with every outline edge offset by Lora's own Regular→Bold growth for a stroke of that width (hairlines +32, stems +52 units; `contrast_figure` in `fontmix/figures.py`), so both weights stay point-compatible. |
| Arches and bowls | Lora's own, unchanged (n h m u b d p q and relatives are identical to Lora in every weight). Brygada-style arches are retired for now; the code is kept (`VARIANTS` in `build_font.py`: `main` = smooth morph of Lora's arches to Brygada's joins, `literal` = spliced Brygada paths). |
| Brygada letters | The Q's tail (laid onto Elanora's O), Brygada's Z/z terminal serifs, a taller t (roman and italic, 85% of the way from Lora's t to Brygada's, relative to the ascender), and Brygada's s, S, a/ª, z, Z (copied, scaled to Elanora's metrics; accents re-anchored). The æ is Brygada's a half joined to Lora's e half, the same e as the letter e (`ae_with_lora_e` in `fontmix/tweaks.py`). |
| Italic y | Brygada's u-shaped italic y: Lora's italic u (right arm straightened) with the tail of Lora's g. |
| Figures | Brygada's lining, tabular and oldstyle figures, numerators/denominators, superiors/inferiors and fraction bar, scaled to Lora's figure height, weight-matched per master by interpolating Brygada's weight axis, and (italic) re-slanted from 8° to Lora's 3°. Figure kerning is re-derived for the new shapes. The 1 and 4 stand on Lora's own foot (long flared bracket left, near-square right, shorter slab). |

## Files

- `dist/fonts/variable/`: `Elanora[wght].ttf`, `Elanora-Italic[wght].ttf` (weight 400–700)
- `dist/fonts/ttf/`: static Regular, Medium, SemiBold, Bold and their italics (overlaps removed, ttfautohinted)
- `dist/fonts/webfonts/`: WOFF2 versions of all of the above
- `dist/specimen.html`: the specimen page (source: `specimen/`)
- `dist/OFL.txt`: the font license (copy that ships with the fonts)
- `OFL.txt`, `LICENSE`: licenses of the fonts (OFL 1.1) and of the code (GPL 3.0 or later)
- `src/`: the Lora and Brygada 1918 variable fonts the build starts from, with their license files
- `manual/`: hand-edited bold a and bold figures (UFO), read back by the build

OpenType features: `liga` (italic only: fi, fl; the roman has no ligatures, its f keeps the ball terminal) `kern` `onum` `lnum` `tnum` `pnum` `frac` `numr` `dnom` `sups` `subs` `sinf`
plus everything Lora already had (`case`, `locl`, `ordn`, …).

## Rebuild

Needs Python 3.14 and [uv](https://docs.astral.sh/uv/); `uv sync` installs the dependencies
(fontTools, skia-pathops, ttfautohint-py, …).

```sh
uv sync
uv run python build_font.py all   # edits Lora's masters, rebuilds the variable fonts into out/
uv run python finalize.py         # naming, static instances, hinting, woff2 -> dist/
uv run python tools/make_specimen.py   # specimen/template.html + dist fonts -> dist/specimen.html
```

All design decisions are data in `fontmix/spec_roman.py` and `fontmix/spec_italic.py` (counter
widening per glyph, used only by the retired arch variants), `fontmix/splice_jobs.py` (which Brygada sections are spliced where: cut lines,
alignment, blending), `fontmix/letters.py` (Brygada letters, t height). The build variant (first entry of `VARIANTS` in `build_font.py`) selects the arch treatment. Figure weights and slant live in the same files
and in `build_font.py`. Change a number and rebuild. The font name is set in `fontmix/naming.py`.

How it works: both Lora masters (400 and 700) are extracted from the variable font. Every change
keeps the two masters point-compatible, so the result is again a true variable font
(`fontmix/build.py`). The ball construction is in `fontmix/balls.py`, the counter widening in
`fontmix/widen.py`, and accent/anchor propagation in `fontmix/propagate.py`.

## Hand-editing the bold a

The bold a (and with it æ, ª and all accented a's) can be edited by hand in any font editor
that opens UFO files (FontForge, Fontra, Glyphs, RoboFont, …).

- `manual/a-bold-brygada.ufo`: Brygada's own bold a, as Elanora has it now
- `manual/a-bold-transfer.ufo`: Elanora Regular a + Lora's Regular→Bold movement (the approach used for most letters)

Edit glyph `a` (the regular a is in its background layer; `a.regular`, `a.lora-bold`,
`a.brygada-bold`, `ae`, `ordfeminine` are references and are not read back). **Move points and
handles only; do not add, delete or convert points**, because the bold must stay
point-compatible with the regular for the variable font. A changed start point or contour
direction is fine. Changing the advance width is fine too.

Pick the approach with `BOLD_A_MODE` in `build_font.py` (`"brygada"` or `"transfer"`, or
`ELANORA_BOLD_A=transfer` for a single build), then rebuild. The build replaces the bold a with the
edited one, moves the matching points of æ and ª by the same amounts (ª scaled), and the accented
a's follow as composites. The intermediate weights interpolate automatically. It prints how far
the points moved (`hand-edited bold a: …`) or refuses an incompatible file with an explanation.
`uv run python tools/export_bold_a.py --force` re-exports fresh, unedited files.

## Hand-editing the bold f

`manual/f-bold.ufo` holds the bold f (the regular f is in the background layer, `f.regular` and
`f.lora-bold` are grey references). Edit glyph `f` the same way as the bold a: move points and
handles, never add, delete or convert them; the advance width may change. Save as UFO *over the
same file* (some editors save a copy under a new name) and rebuild; the build prints
`hand-edited bold f: …`. The roman `fi`, `fl` and `longs` have their own outlines and do not
follow. `uv run python tools/export_bold_f.py --force` re-exports a fresh file.

## Hand-editing the bold figures

`manual/figures-bold-roman.ufo` and `manual/figures-bold-italic.ufo` hold the bold lining (0–9)
and oldstyle (`.osf`) figures, with the regular figure in each glyph's background layer and Lora
Bold's figures as grey references. Edit them the same way as the bold a: move points and handles,
never add or delete them. Sharp inner corners (where a ball meets its stroke, the 8's waist) are
two points on top of each other, so each side can be moved on its own. Save as UFO
(FontForge: File › Generate Fonts… › Unified Font Object) and rebuild. Each edit is carried to that
figure's tabular, numerator, denominator, superior and inferior versions; the build prints which
glyphs moved. `uv run python tools/export_bold_figures.py --force` re-exports fresh files.

## License

- **Fonts and everything font-related** (`dist/`, `manual/`): SIL Open Font License 1.1, see
  `OFL.txt`. "Lora" is a Reserved Font Name, which is why this derivative has its own name. The
  copyright notices of both source projects are retained in the fonts and in `OFL.txt`. The source
  fonts in `src/` stay under their own license files.
- **Code** (`build_font.py`, `finalize.py`, `fontmix/`, `tools/`, `specimen/template.html`): GNU
  General Public License, version 3 or later, see `LICENSE`.

Derived from [Lora](https://github.com/cyrealtype/Lora-Cyrillic) (Olga Karpushina, Alexei
Vanyashin, Cyreal) and [Brygada 1918](https://github.com/kosmynkab/Brygada-1918) (Mateusz
Machalski, Borys Kosmynka, Przemek Hoffer).
