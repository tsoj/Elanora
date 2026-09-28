"""Widen counters: smooth horizontal displacement field; stems/serifs move rigidly."""
import numpy as np

from .geom import glyph_contours, point_in_glyph, sample, set_glyph_contours


def ink_runs(contours, y, step=0.5):
    xs = np.arange(-200, 1400, step)
    P = np.c_[xs, np.full_like(xs, y)]
    ins = point_in_glyph(P, [sample(c, 16) for c in contours])
    out, st = [], None
    for x, v in zip(xs, ins):
        if v and st is None:
            st = x
        if not v and st is not None:
            out.append((st, x))
            st = None
    return out


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


class Field:
    """Sum of zone displacements. zone = (xa, xb, delta); optional y-limits (y0, y1) outside of
    which the zone acts as a hard split at its midpoint (for serif bands)."""

    def __init__(self, zones):
        self.zones = zones

    def dx(self, x, y=None):
        total = 0.0
        for z in self.zones:
            xa, xb, d = z[:3]
            total += d * float(smoothstep((x - xa) / (xb - xa)))
        return total

    def total(self):
        return sum(z[2] for z in self.zones)


def auto_zones(contours, y_ref, deltas, margins):
    """Zones in the gaps between ink runs at y_ref. deltas: list per gap (None = skip).
    margins: list of (left_margin, right_margin) per gap."""
    runs = ink_runs(contours, y_ref)
    zones = []
    for i, d in enumerate(deltas):
        if not d:
            continue
        ml, mr = margins[i]
        xa, xb = runs[i][1] + ml, runs[i + 1][0] - mr
        zones.append((xa, xb, d))
    return zones, runs


def apply_field(glyf, hmtx, name, field):
    cs = glyph_contours(glyf, name)
    for c in cs:
        for p in c:
            p[0] += field.dx(p[0], p[1])
    set_glyph_contours(glyf, name, cs)
    adv, lsb = hmtx[name]
    hmtx[name] = (int(round(adv + field.total())), glyf[name].xMin)
