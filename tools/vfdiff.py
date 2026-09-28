import sys
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
def vfdiff(pa_,pb_,loc,tol=1.01):
    a=TTFont(pa_); b=TTFont(pb_)
    ga=a.getGlyphSet(location=loc); gb=b.getGlyphSet(location=loc)
    diff=[]
    for g in a.getGlyphOrder():
        ra=DecomposingRecordingPen(ga); rb=DecomposingRecordingPen(gb); ga[g].draw(ra); gb[g].draw(rb)
        va=[p for op,args in ra.value for p in args]; vb=[p for op,args in rb.value for p in args]
        if len(va)!=len(vb) or (va and max((abs(x[0]-y[0])+abs(x[1]-y[1])) for x,y in zip(va,vb))>tol) or abs(ga[g].width-gb[g].width)>tol: diff.append(g)
    return diff
if __name__=="__main__":
    for w in (400,550,700):
        d=vfdiff(sys.argv[1],sys.argv[2],{"wght":w}); print(w,len(d),d[:15])
