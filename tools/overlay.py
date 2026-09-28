"""Overlay outlines of glyphs from several fonts (colored), aligned at left bbox or advance-centered."""
import sys; sys.path.insert(0, "tools")
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.boundsPen import BoundsPen
from PIL import Image, ImageDraw
from proof import _FlattenPen
import pathops

COLORS=[(0,0,0),(220,40,40),(30,90,220),(20,150,60)]
def glyph_polys(gs, name, tf):
    pen=_FlattenPen(gs, tf, steps=16); gs[name].draw(pen); return pen.polys

def overlay(specs, out, cell=360, cols=6, upm_box=(-280, 1000), fill_first=True, points=False):
    """specs: list of glyph groups; each group: list of (TTFont|glyphset, name, scale, dx) """
    rows=(len(specs)+cols-1)//cols
    lo,hi=upm_box; k=cell/(hi-lo)
    img=Image.new("RGB",(cols*cell,rows*cell),"white"); d=ImageDraw.Draw(img)
    for i,group in enumerate(specs):
        cx,cy=(i%cols)*cell,(i//cols)*cell
        # guides
        for yv,c in ((0,(200,200,200)),(500,(200,200,255)),(700,(255,210,210))):
            y=cy+(hi-yv)*k; d.line([(cx,y),(cx+cell,y)],fill=c)
        # center each glyph on its bbox center
        for j,(gs,name,s,dx) in enumerate(group):
            bp=BoundsPen(gs); gs[name].draw(bp); b=bp.bounds
            mid=(b[0]+b[2])/2*s
            tf=lambda p,s=s,mid=mid,dx=dx:(cx+cell/2+(p[0]*s-mid+dx)*k, cy+(hi-p[1]*s)*k)
            polys=glyph_polys(gs,name,tf)
            col=COLORS[j%len(COLORS)]
            if j==0 and fill_first:
                for poly in polys: pass
                m=Image.new("L",img.size,0); md=ImageDraw.Draw(m)
                pp=pathops.Path(); gs[name].draw(pathops.PathPen(pp,gs)); pp.simplify(fix_winding=True)
                pen=_FlattenPen(gs,tf,steps=16); pp.draw(pen)
                # even-odd fill
                import numpy as np
                acc=np.zeros((img.size[1],img.size[0]),bool)
                for poly in pen.polys:
                    mm=Image.new("1",img.size,0); ImageDraw.Draw(mm).polygon(poly,fill=1); acc^=np.asarray(mm)
                img.paste((225,225,225),(0,0),Image.fromarray((acc*255).astype("uint8")))
            for poly in polys: d.line(poly+[poly[0]],fill=col,width=2)
        d.text((cx+4,cy+4)," / ".join(n for _,n,_,_ in group[:1]),fill=(0,0,0))
    img.save(out); return out
