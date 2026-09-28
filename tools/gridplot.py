import sys; sys.path.insert(0,"."); sys.path.insert(0,"tools")
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontmix.geom import glyph_contours, sample
def grid_plot(glyf, names, out, cell=360, cols=6, box=(-120,-300,820,800), step=50, marks=None):
    rows=(len(names)+cols-1)//cols
    full=Image.new("RGB",(cols*cell,rows*cell),"white")
    F=ImageFont.truetype("DejaVuSans.ttf",9); F2=ImageFont.truetype("DejaVuSans.ttf",12)
    for i,n in enumerate(names):
        img=Image.new("RGB",(cell,cell),"white"); d=ImageDraw.Draw(img)
        x0,y0,x1,y1=box; k=min(cell/(x1-x0),cell/(y1-y0))
        tf=lambda x,y:((x-x0)*k,(y1-y)*k)
        acc=np.zeros((cell,cell),bool)
        from fontTools.pens.recordingPen import DecomposingRecordingPen
        g=glyf[n]
        cs=glyph_contours(glyf,n)
        for c in cs:
            m=Image.new("1",(cell,cell),0); ImageDraw.Draw(m).polygon([tf(x,y) for x,y in sample(c,10)],fill=1); acc^=np.asarray(m)
        img.paste((190,190,190),(0,0),Image.fromarray((acc*255).astype("uint8")))
        for gx in range(int(x0//step*step),int(x1)+1,step):
            X,_=tf(gx,0); d.line([(X,0),(X,cell)],fill=(255,200,200) if gx%100 else (230,120,120))
            if gx%100==0: d.text((X+1,cell-11),str(gx),fill=(200,0,0),font=F)
        for gy in range(int(y0//step*step),int(y1)+1,step):
            _,Y=tf(0,gy); d.line([(0,Y),(cell,Y)],fill=(200,200,255) if gy%100 else (120,120,230))
            if gy%100==0: d.text((1,Y+1),str(gy),fill=(0,0,200),font=F)
        if marks and n in marks:
            for (x,y,r) in marks[n]:
                X,Y=tf(x,y); d.ellipse([X-r*k,Y-r*k,X+r*k,Y+r*k],outline=(0,150,0),width=2)
        d.text((cell/2,4),n,fill=(0,0,0),font=F2)
        full.paste(img,((i%cols)*cell,(i//cols)*cell))
    full.save(out)
