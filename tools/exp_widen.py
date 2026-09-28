import sys, copy, json; sys.path.insert(0,"."); sys.path.insert(0,"tools")
from fontmix.masters import load_masters
from fontmix.geom import glyph_contours
from fontmix.widen import auto_zones, Field, apply_field
from cmpplot import cmp_plot
M=load_masters("src/lora_Lora[wght].ttf"); O={w:copy.deepcopy(f) for w,f in M.items()}
S=45; B=5
spec={ # name: (y_ref, {400:[deltas],700:[deltas]}, margins)
 "n":(250,{400:[17],700:[21]},[(S,S)]),
 "h":(250,{400:[17],700:[21]},[(S,S)]),
 "m":(250,{400:[24,24],700:[27,27]},[(S,S),(S,S)]),
 "u":(250,{400:[15],700:[21]},[(S,S)]),
 "b":(250,{400:[24],700:[32]},[(S,B)]),
 "d":(250,{400:[24],700:[32]},[(B,S)]),
 "p":(250,{400:[24],700:[32]},[(S,B)]),
 "q":(250,{400:[24],700:[32]},[(B,S)]),
 "a":(150,{400:[30],700:[36]},[(B,30)]),
}
zones_used={}
for n,(y,ds,ms) in spec.items():
    for w in M:
        zs,runs=auto_zones(glyph_contours(M[w]['glyf'],n),y,ds[w],ms)
        zones_used[(w,n)]=zs
        apply_field(M[w]['glyf'],M[w]['hmtx'],n,Field(zs))
pairs=[(w,O[w]['glyf'],M[w]['glyf'],n,(-20,-290,760,780)) for n in spec for w in M]
cmp_plot(pairs,"proofs/widen1.png",cell=300,cols=6,show_points=False)
print({k:[tuple(round(v) for v in z) for z in zs] for k,zs in zones_used.items() if k[0]==400})
