import sys, math, json, copy; sys.path.insert(0,"."); sys.path.insert(0,"tools")
from fontmix.masters import load_masters
from fontmix.geom import glyph_contours, explicitize, set_glyph_contours
from fontmix.balls import ball_terminal
from cmpplot import cmp_plot
src=sys.argv[3] if len(sys.argv)>3 else "src/lora_Lora[wght].ttf"
M=load_masters(src)
O={w:copy.deepcopy(f) for w,f in M.items()}
spec=json.loads(open(sys.argv[1]).read())
circles={}
for n,sp in spec.items():
    CS={w:glyph_contours(M[w]['glyf'],n) for w in M}
    for t in sp["t"]:
        dx,dy,Rd,ci=t[:4]; grow=t[4] if len(t)>4 else 1; sh=(t[5],t[6]) if len(t)>6 else (0,0)
        new,info=ball_terminal({w:explicitize(CS[w][ci]) for w in M},(dx,dy),Rd,grow,sh,others={w:[c for j,c in enumerate(CS[w]) if j!=ci] for w in M})
        for w in M:
            CS[w][ci]=new[w]; circles.setdefault((w,n),[]).append(info[w]["circle"])
            print(w,n,{k:(tuple(round(v) for v in val) if isinstance(val,tuple) else round(val)) for k,val in info[w].items()})
    for w in M: set_glyph_contours(M[w]['glyf'],n,CS[w])
pairs=[]
for n,sp in spec.items():
    for w in M: pairs.append((w,O[w]['glyf'],M[w]['glyf'],n,sp["crop"]))
cmp_plot(pairs,sys.argv[2],cell=450,cols=4,circles=circles)
