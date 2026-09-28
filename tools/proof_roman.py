import sys; sys.path.insert(0,"."); sys.path.insert(0,"tools")
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from cmpplot import cmp_plot
from proof import render
L="src/lora_Lora[wght].ttf"; N=sys.argv[1] if len(sys.argv)>1 else "out/Roman-VF.ttf"
names=sys.argv[2].split(",") if len(sys.argv)>2 else "a c r f g y n m b d p q J ae florin eng".split()
O={w:instancer.instantiateVariableFont(TTFont(L),{"wght":w}) for w in (400,700)}
X={w:instancer.instantiateVariableFont(TTFont(N),{"wght":w}) for w in (400,700)}
pairs=[(w,O[w]['glyf'],X[w]['glyf'],n,(-130,-300,830,800)) for n in names for w in (400,700)]
cmp_plot(pairs,"proofs/glyphs.png",cell=300,cols=8,show_points=False)
txt=["handgloves quick abcdefghijklmnopqrstuvwxyz","The five boxing wizards jump; affluent fjord"]
rows=[]
for w in (400,700):
    for t in txt:
        rows += [dict(path=L,text=t,var={"wght":w},label=f"Lora {w}"),dict(path=N,text=t,var={"wght":w},label=f"New {w}")]
render(rows,"proofs/text.png",size=40,label_w=70)
