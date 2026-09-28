import sys; sys.path.insert(0, "tools")
from proof import render
L="src/lora_Lora[wght].ttf"; LI="src/lora_Lora-Italic[wght].ttf"
B="src/brygada1918_Brygada1918[wght].ttf"; BI="src/brygada1918_Brygada1918-Italic[wght].ttf"
s=500/460
rows=[]
for t in ["acefgjrsty oebdpq nmhu", "fi fl ffi ffl fj ft RQGJK", "0123456789 $%&?"]:
    rows += [dict(path=L,text=t,label="Lora"), dict(path=B,text=t,label="Brygada",scale=s)]
render(rows,"proofs/cmp_roman.png",size=90,label_w=70)
rows=[]
for t in ["acefgjrsty oebdpq nmhu", "fi fl ffi ffl fj 0123456789"]:
    rows += [dict(path=LI,text=t,label="Lora It"), dict(path=BI,text=t,label="Bryg It",scale=s)]
render(rows,"proofs/cmp_italic.png",size=90,label_w=70)
