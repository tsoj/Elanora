"""Plot TrueType glyph points with indices. glyphs from a (possibly instanced) TTFont."""
import sys; sys.path.insert(0,"tools")
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

def contours_of(font, name):
    glyf=font['glyf']; g=glyf[name]
    coords,ends,flags=g.getCoordinates(glyf)
    out=[];s=0
    for e in ends:
        out.append([(coords[i][0],coords[i][1],flags[i]&1,i) for i in range(s,e+1)]); s=e+1
    return out

def plot(font, names, out, cell=700, cols=3, box=(-300,1050), crop=None, extra=None):
    rows=(len(names)+cols-1)//cols
    img=Image.new("RGB",(cols*cell,rows*cell),"white"); d=ImageDraw.Draw(img)
    try: F=ImageFont.truetype("DejaVuSans.ttf",11)
    except: F=ImageFont.load_default()
    for n_i,name in enumerate(names):
        cx,cy=(n_i%cols)*cell,(n_i//cols)*cell
        cs=contours_of(font,name)
        xs=[p[0] for c in cs for p in c]; ys=[p[1] for c in cs for p in c]
        if crop: x0,y0,x1,y1=crop[n_i] if isinstance(crop,list) else crop
        else: x0,x1=min(xs)-30,max(xs)+30; y0,y1=box
        k=min(cell/(x1-x0),cell/(y1-y0))
        tf=lambda x,y:(cx+(x-x0)*k, cy+(y1-y)*k)
        for c in cs:
            # draw quadratic outline
            pts=c; n=len(pts)
            # build on-curve list w/ implied
            seq=[]
            for i in range(n):
                p=pts[i]; q=pts[(i+1)%n]; seq.append(p)
                if not p[2] and not q[2]: seq.append(((p[0]+q[0])/2,(p[1]+q[1])/2,1,-1))
            # rotate to start with on-curve
            st=next(i for i,p in enumerate(seq) if p[2]); seq=seq[st:]+seq[:st]
            poly=[];m=len(seq);i=0
            while i<m:
                p=seq[i]; q=seq[(i+1)%m]
                if q[2]: poly+= [tf(p[0],p[1])]; i+=1
                else:
                    r=seq[(i+2)%m]
                    for t in [j/10 for j in range(10)]:
                        x=(1-t)**2*p[0]+2*(1-t)*t*q[0]+t*t*r[0]; y=(1-t)**2*p[1]+2*(1-t)*t*q[1]+t*t*r[1]
                        poly.append(tf(x,y))
                    i+=2
            d.line(poly+[poly[0]],fill=(0,0,0),width=2)
            for x,y,on,idx in pts:
                X,Y=tf(x,y)
                if on: d.rectangle([X-3,Y-3,X+3,Y+3],fill=(220,30,30))
                else: d.ellipse([X-3,Y-3,X+3,Y+3],outline=(30,90,220),width=2)
                d.text((X+4,Y-12),str(idx),fill=(0,120,0) if on else (30,90,220),font=F)
        if extra and name in extra:
            for (x,y,r) in extra[name]:
                X,Y=tf(x,y); d.ellipse([X-r*k,Y-r*k,X+r*k,Y+r*k],outline=(255,140,0),width=2)
        d.text((cx+5,cy+5),name,fill=(0,0,0),font=F)
    img.save(out); return out
if __name__=="__main__":
    f=TTFont(sys.argv[1]); plot(f,sys.argv[3].split(","),sys.argv[2])
