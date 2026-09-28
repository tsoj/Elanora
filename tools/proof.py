"""Proofing helpers: shape with HarfBuzz, draw outlines with PIL (supersampled)."""
import io
import sys
from functools import lru_cache

import pathops
import uharfbuzz as hb
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

SS = 3  # supersampling


@lru_cache(maxsize=None)
def _load(path):
    data = open(path, "rb").read()
    return data, TTFont(io.BytesIO(data))


class _FlattenPen(BasePen):
    def __init__(self, glyphSet, tf, steps=12):
        super().__init__(glyphSet)
        self.tf, self.steps, self.polys, self.cur = tf, steps, [], []

    def _moveTo(self, p):
        self.cur = [self.tf(p)]

    def _lineTo(self, p):
        self.cur.append(self.tf(p))

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            t = i / self.steps
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
            self.cur.append(self.tf((x, y)))

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            x = mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
            y = mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
            self.cur.append(self.tf((x, y)))

    def _closePath(self):
        if len(self.cur) > 2:
            self.polys.append(self.cur)
        self.cur = []

    _endPath = _closePath


def _signed_area(poly):
    a = 0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return a / 2


def fill_polys(img_size, polys):
    """Nonzero fill via per-polygon winding accumulation."""
    import numpy as np

    w, h = img_size
    acc = np.zeros((h, w), dtype=np.int16)
    for poly in polys:
        m = Image.new("L", img_size, 0)
        ImageDraw.Draw(m).polygon(poly, fill=1)
        arr = np.asarray(m, dtype=np.int16)
        # screen coords flip y, so area sign flips
        acc += arr if _signed_area(poly) < 0 else -arr
    return Image.fromarray(((acc != 0) * 255).astype("uint8"))


def shape(path, text, variations=None, features=None):
    data, tt = _load(path)
    face = hb.Face(data)
    font = hb.Font(face)
    if variations:
        font.set_variations(variations)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or {})
    order = tt.getGlyphOrder()
    return [(order[i.codepoint], p.x_advance, p.x_offset, p.y_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]


def line_polys(path, text, size, x0, baseline, variations=None, features=None, scale=1.0):
    data, tt = _load(path)
    gs = tt.getGlyphSet(location=variations) if variations else tt.getGlyphSet()
    upm = tt["head"].unitsPerEm
    k = size * SS / upm * scale
    polys = []
    x = x0 * SS
    for name, adv, dx, dy in shape(path, text, variations, features):
        ox, oy = x + dx * k, baseline * SS - dy * k
        pen = _FlattenPen(gs, lambda p, ox=ox, oy=oy: (ox + p[0] * k, oy - p[1] * k))
        pp = pathops.Path()
        gs[name].draw(pathops.PathPen(pp, gs))
        pp.simplify(fix_winding=True)
        pp.draw(pen)
        polys += pen.polys
        x += adv * k
    return polys, x / SS


def render(lines, out, size=64, width=None, pad=24, label_w=0, gap=1.45):
    """lines: list of dicts with keys path,text,[var],[feat],[label],[scale]."""
    measured = []
    for ln in lines:
        _, xe = line_polys(ln["path"], ln["text"], size, 0, 0, ln.get("var"), ln.get("feat"), ln.get("scale", 1.0))
        measured.append(xe)
    W = int(width or (pad * 2 + label_w + max(measured)))
    lh = int(size * gap)
    H = pad * 2 + lh * len(lines)
    polys = []
    for i, ln in enumerate(lines):
        base = pad + lh * i + size
        p, _ = line_polys(ln["path"], ln["text"], size, pad + label_w, base, ln.get("var"), ln.get("feat"), ln.get("scale", 1.0))
        polys += p
    mask = fill_polys((W * SS, H * SS), polys)
    mask = mask.resize((W, H), Image.LANCZOS)
    img = Image.new("L", (W, H), 255)
    img.paste(0, (0, 0), mask)
    if label_w:
        d = ImageDraw.Draw(img)
        try:
            f = ImageFont.truetype("DejaVuSans.ttf", 13)
        except OSError:
            f = ImageFont.load_default()
        for i, ln in enumerate(lines):
            d.text((6, pad + lh * i + size * 0.55), ln.get("label", ""), fill=90, font=f)
    img.save(out)
    return out


if __name__ == "__main__":
    print(render([{"path": sys.argv[1], "text": sys.argv[2]}], sys.argv[3]))
