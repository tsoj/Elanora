"""Plot Elanor-base (widened Lora) and scaled Brygada glyphs with point indices side by side."""
import sys, copy; sys.path.insert(0,"."); sys.path.insert(0,"tools")
from fontmix.masters import load_masters
from fontmix.stages import stage_widen
from fontmix import spec_roman as S
from fontmix.transplant import bry_instance
from fontmix.figures import brygada_contours
from fontmix.geom import glyph_contours, sample
from PIL import Image, ImageDraw, ImageFont

def draw(cs, out_img, off, cell, box, title):
    d=ImageDraw.Draw(out_img); F=ImageFont.truetype("DejaVuSans.ttf",10)
    x0,y0,x1,y1=box; k=min(cell/(x1-x0),cell/(y1-y0))
    tf=lambda x,y:(off[0]+(x-x0)*k, off[1]+(y1-y)*k)
    for ci,c in enumerate(cs):
        pts=[tf(x,y) for x,y in sample(c,10)]
        d.line(pts+[pts[0]],fill=(0,0,0),width=1)
        for i,(x,y,on) in enumerate(c):
            X,Y=tf(x,y)
            if on: d.rectangle([X-2,Y-2,X+2,Y+2],fill=(220,30,30))
            else: d.ellipse([X-2,Y-2,X+2,Y+2],outline=(30,90,220))
            d.text((X+3,Y-10),f"{i}" if ci==0 else f"{ci}.{i}",fill=(0,120,0) if on else (30,90,220),font=F)
    d.text((off[0]+4,off[1]+4),title,fill=(0,0,0),font=F)

def pairplot(names, out, style="roman", cell=520, box=None, w=400):
    if style=="roman":
        M=load_masters("src/lora_Lora[wght].ttf"); stage_widen(M,S.WIDEN)
        B=bry_instance("src/brygada1918_Brygada1918[wght].ttf",400 if w==400 else 660)
    else:
        M=load_masters("src/lora_Lora-Italic[wght].ttf")
        B=bry_instance("src/brygada1918_Brygada1918-Italic[wght].ttf",400 if w==400 else 640)
    img=Image.new("RGB",(2*cell,len(names)*cell),"white")
    for r,n in enumerate(names):
        bx=box[n] if isinstance(box,dict) else (box or (-60,-300,760,800))
        draw(glyph_contours(M[w]['glyf'],n),img,(0,r*cell),cell,bx,f"Elanor base {n}")
        draw(brygada_contours(B,n,500/460,shear=(0.0 if style=="roman" else -0.0424)),img,(cell,r*cell),cell,bx,f"Brygada {n} (x500)")
    img.save(out)
