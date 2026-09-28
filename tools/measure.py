import sys; sys.path.insert(0,".")
from fontmix.geom import glyph_contours, sample, point_in_glyph
import numpy as np
def runs_at(f,g,y,step=0.5):
    cs=glyph_contours(f['glyf'],g); xs=np.arange(-100,1200,step); P=np.c_[xs,np.full_like(xs,y)]
    ins=point_in_glyph(P,[sample(c,16) for c in cs]); out=[];st=None
    for x,v in zip(xs,ins):
        if v and st is None: st=x
        if not v and st is not None: out.append((st,x)); st=None
    return out
def gaps(r):
    return [round(r[i+1][0]-r[i][1]) for i in range(len(r)-1)]
