"""Render text with FreeType (hinting on, grayscale AA) at pixel sizes, like a screen."""
import sys, freetype, numpy as np
from PIL import Image, ImageDraw, ImageFont
def line(path, text, px, hint=True, var=None):
    face=freetype.Face(path); face.set_pixel_sizes(0,px)
    if var: face.set_var_design_coords(var)
    flags=freetype.FT_LOAD_RENDER | (freetype.FT_LOAD_TARGET_LIGHT if hint else freetype.FT_LOAD_NO_HINTING)
    pen=0; glyphs=[]
    W=int(px*len(text)*0.7)+20; H=int(px*1.6)
    img=np.zeros((H,W),np.uint8); base=int(px*1.15)
    prev=None
    for ch in text:
        face.load_char(ch,flags); g=face.glyph; bm=g.bitmap
        a=np.array(bm.buffer,np.uint8).reshape(bm.rows,bm.width) if bm.rows else None
        x=pen//64 + g.bitmap_left; y=base-g.bitmap_top
        if a is not None:
            y0=max(0,y); x0=max(0,x)
            sub=a[y0-y:min(H-y,a.shape[0]), x0-x:min(W-x,a.shape[1])]
            img[y0:y0+sub.shape[0], x0:x0+sub.shape[1]]=np.maximum(img[y0:y0+sub.shape[0], x0:x0+sub.shape[1]],sub)
        pen+=g.advance.x
    return img[:, :pen//64+4]
def sheet(rows, out):
    ims=[(lbl,line(*a)) for lbl,a in rows]
    W=max(i.shape[1] for _,i in ims)+120; H=sum(i.shape[0] for _,i in ims)+10
    canvas=Image.new("L",(W,H),255); y=5; d=ImageDraw.Draw(canvas); F=ImageFont.truetype("DejaVuSans.ttf",10)
    for lbl,i in ims:
        canvas.paste(Image.fromarray(255-i),(115,y)); d.text((4,y+i.shape[0]//3),lbl,fill=100,font=F); y+=i.shape[0]
    canvas.save(out)
