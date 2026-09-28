import sys; sys.path.insert(0,"tools")
from overlay import overlay
from fontTools.ttLib import TTFont
L=TTFont("src/lora_Lora[wght].ttf").getGlyphSet(); B=TTFont("src/brygada1918_Brygada1918[wght].ttf").getGlyphSet()
s=500/460
names="o c e a n h b d p s r g f j y t".split()
overlay([[(L,n,1,0),(B,n,s,0)] for n in names],"proofs/overlay_lc.png",cell=300,cols=6)
