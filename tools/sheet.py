import sys; sys.path.insert(0,"."); sys.path.insert(0,"tools")
import numpy as np, pathops
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from proof import _FlattenPen
def glyph_sheet(path, names, out, loc, cell=90, cols=22):
    f=TTFont(path); gs=f.getGlyphSet(location=loc)
    rows=(len(names)+cols-1)//cols
    img=Image.new("L",(cols*cell,rows*cell),255); d=ImageDraw.Draw(img); F=ImageFont.truetype("DejaVuSans.ttf",8)
    k=cell/1300
    for i,n in enumerate(names):
        cx,cy=(i%cols)*cell,(i//cols)*cell
        pp=pathops.Path(); gs[n].draw(pathops.PathPen(pp,gs)); pp.simplify(fix_winding=True)
        w=gs[n].width
        pen=_FlattenPen(gs,lambda p:(cx+cell/2+(p[0]-w/2)*k*3, cy+(1000-p[1])*k*3/ (3) *1 ),12)
        # scale: upm 1300 -> cell
        pen=_FlattenPen(gs,lambda p:(cx+cell/2+(p[0]-w/2)*k, cy+cell*0.05+(1000-p[1])*k),12)
        pp.draw(pen)
        acc=np.zeros((img.size[1],img.size[0]),bool)
        for poly in pen.polys:
            m=Image.new("1",img.size,0); ImageDraw.Draw(m).polygon(poly,fill=1); acc^=np.asarray(m)
        img.paste(0,(0,0),Image.fromarray((acc*255).astype("uint8")))
        d.text((cx+2,cy+cell-10),n[:16],fill=120,font=F)
        d.rectangle([cx,cy,cx+cell-1,cy+cell-1],outline=225)
    img.save(out)
