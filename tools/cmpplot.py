"""Plot original (gray fill) vs modified (black outline + points) glyphs, zoomable."""
import sys; sys.path.insert(0,"."); sys.path.insert(0,"tools")
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontmix.geom import glyph_contours, sample, explicitize

def _poly(c, tf):
    return [tf(x,y) for x,y in sample(c,12)]

def cmp_plot(pairs, out, cell=500, cols=4, show_points=True, circles=None):
    """pairs: list of (label, glyf_orig, glyf_new, name, crop(x0,y0,x1,y1))"""
    rows=(len(pairs)+cols-1)//cols
    img=Image.new("RGB",(cols*cell,rows*cell),"white"); d=ImageDraw.Draw(img)
    F=ImageFont.truetype("DejaVuSans.ttf",11)
    full=img
    for i,(label,go,gn,name,crop) in enumerate(pairs):
        img=Image.new("RGB",(cell,cell),"white"); d=ImageDraw.Draw(img)
        cx,cy=0,0
        x0,y0,x1,y1=crop; k=min(cell/(x1-x0),cell/(y1-y0))
        tf=lambda x,y:(cx+(x-x0)*k, cy+(y1-y)*k)
        # orig fill (even-odd)
        acc=np.zeros((img.size[1],img.size[0]),bool)
        for c in glyph_contours(go,name):
            m=Image.new("1",img.size,0); ImageDraw.Draw(m).polygon(_poly(c,tf),fill=1); acc^=np.asarray(m)
        img.paste((215,215,215),(0,0),Image.fromarray((acc*255).astype("uint8")))
        d=ImageDraw.Draw(img)
        if gn is not None:
            for c in glyph_contours(gn,name):
                p=_poly(c,tf); d.line(p+[p[0]],fill=(0,0,0),width=2)
                if show_points:
                    for j,(x,y,on) in enumerate(c):
                        X,Y=tf(x,y)
                        if on: d.rectangle([X-3,Y-3,X+3,Y+3],fill=(220,30,30))
                        else: d.ellipse([X-3,Y-3,X+3,Y+3],outline=(30,90,220),width=2)
        if circles and (label,name) in circles:
            for (x,y,r) in circles[(label,name)]:
                X,Y=tf(x,y); d.ellipse([X-r*k,Y-r*k,X+r*k,Y+r*k],outline=(255,140,0),width=1)
        d.rectangle([cx,cy,cx+cell-1,cy+cell-1],outline=(230,230,230))
        d.text((cx+5,cy+5),f"{label} {name}",fill=(0,0,0),font=F)
        full.paste(img,((i%cols)*cell,(i//cols)*cell))
    full.save(out); return out
