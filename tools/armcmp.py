"""Overlay Elanora vs Brygada arms, aligned at the joining stem edge."""
import sys; sys.path.insert(0,"."); sys.path.insert(0,"tools")
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontmix.geom import glyph_contours, sample
from fontmix.widen import ink_runs
def arm_overlay(elanora_paths, names, out, w=400, bw=None, cell=420, box=(-40,-60,560,560)):
    bw = bw or (400 if w==400 else 660)
    B = instancer.instantiateVariableFont(TTFont("src/brygada1918_Brygada1918[wght].ttf"), {"wght": bw})
    Ps = [instancer.instantiateVariableFont(TTFont(p), {"wght": w}) for p in elanora_paths]
    s = 500/460
    cols=len(names); img=Image.new("RGB",(cols*cell,cell),"white")
    F=ImageFont.truetype("DejaVuSans.ttf",11)
    cols_rgb=[(0,0,0),(40,110,230),(20,150,60)]
    for i,(n,(ri,edge)) in enumerate(names):
        sub=Image.new("RGB",(cell,cell),"white"); d=ImageDraw.Draw(sub)
        x0,y0,x1,y1=box; k=min(cell/(x1-x0),cell/(y1-y0))
        tf=lambda x,y:((x-x0)*k,(y1-y)*k)
        # reference alignment: the chosen stem edge of the first Elanora font at mid x-height
        ref=ink_runs(glyph_contours(Ps[0]['glyf'],n),250)[ri][edge]
        bcs=[[[x*s,y*s,on] for x,y,on in c] for c in glyph_contours(B['glyf'],n)]
        bref=ink_runs(bcs,250)[ri][edge]
        # brygada filled (light red)
        acc=np.zeros((cell,cell),bool)
        for c in bcs:
            m=Image.new("1",(cell,cell),0); ImageDraw.Draw(m).polygon([tf(x-bref+ref-ref+ (ref-bref) + bref - ref + ref - ref, y) for x,y in sample([[p[0]+ (ref-bref),p[1],p[2]] for p in c],12)] if False else [tf(x,y) for x,y in sample([[p[0]+(ref-bref),p[1],p[2]] for p in c],12)],fill=1); acc^=np.asarray(m)
        sub.paste((250,200,200),(0,0),Image.fromarray((acc*255).astype("uint8")))
        d=ImageDraw.Draw(sub)
        for j,P in enumerate(Ps):
            for c in glyph_contours(P['glyf'],n):
                pts=[tf(x,y) for x,y in sample(c,12)]
                d.line(pts+[pts[0]],fill=cols_rgb[j%3],width=2)
        d.text((4,4),f"{n} {w}",fill=(0,0,0),font=F)
        img.paste(sub,(i*cell,0))
    img.save(out)
