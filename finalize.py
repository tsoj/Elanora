"""Name, instance, hint and package the fonts into dist/."""
import glob, io, os, shutil, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.varLib.instancer import OverlapMode
import ttfautohint
from fontmix.naming import FAMILY, VERSION, rename_vf, COPYRIGHT

DIST = sys.argv[1] if len(sys.argv) > 1 else "dist"
WEIGHTS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}


def main():
    for d in ("variable", "ttf", "webfonts"):
        os.makedirs(f"{DIST}/fonts/{d}", exist_ok=True)
    for style, src in (("roman", "out/Roman-VF.ttf"), ("italic", "out/Italic-VF.ttf")):
        italic = style == "italic"
        vf = TTFont(src)
        rename_vf(vf, italic)
        vname = f"{FAMILY}{'-Italic' if italic else ''}[wght]"
        vf.save(f"{DIST}/fonts/variable/{vname}.ttf")
        vf.flavor = "woff2"
        vf.save(f"{DIST}/fonts/webfonts/{vname}.woff2")
        for w, wn in WEIGHTS.items():
            inst = instancer.instantiateVariableFont(
                TTFont(f"{DIST}/fonts/variable/{vname}.ttf"), {"wght": w},
                updateFontNames=True, overlap=OverlapMode.REMOVE)
            sn = (wn if wn != "Regular" else "") + ("Italic" if italic else "")
            sn = sn or "Regular"
            nm = inst["name"]
            nm.removeNames(nameID=25)
            for nid, s in ((6, f"{FAMILY}-{sn}"), (3, f"{VERSION};NONE;{FAMILY}-{sn}")):
                nm.removeNames(nameID=nid)
                nm.setName(s, nid, 3, 1, 0x409)
            buf = io.BytesIO()
            inst.save(buf)
            hinted = ttfautohint.ttfautohint(in_buffer=buf.getvalue(), default_script="latn",
                                             fallback_script="latn")
            path = f"{DIST}/fonts/ttf/{FAMILY}-{sn}.ttf"
            open(path, "wb").write(hinted)
            f = TTFont(path)
            f.flavor = "woff2"
            f.save(f"{DIST}/fonts/webfonts/{FAMILY}-{sn}.woff2")
            print("wrote", path)
    # variants (installable next to Elanora under their own family names)
    os.makedirs(f"{DIST}/fonts/versions", exist_ok=True)
    for vf_path in sorted(glob.glob("out/Roman-VF-*.ttf") + glob.glob("out/Italic-VF-*.ttf")):
        italic = "Italic" in vf_path
        v = vf_path.rsplit("-", 1)[1].split(".")[0].capitalize()
        vf = TTFont(vf_path)
        rename_vf(vf, italic)
        fam = f"{FAMILY} {v}"
        st = "Italic" if italic else "Regular"
        ps = f"{FAMILY}{v}-{st}"
        nm = vf["name"]
        for nid, s in ((1, fam), (4, f"{fam} {st}"), (6, ps), (3, f"{VERSION};NONE;{ps}"), (25, f"{FAMILY}{v}" + ("Italic" if italic else ""))):
            nm.removeNames(nameID=nid)
            nm.setName(s, nid, 3, 1, 0x409)
        fn = f"{FAMILY}{v}{'-Italic' if italic else ''}[wght]"
        vf.save(f"{DIST}/fonts/versions/{fn}.ttf")
        vf.flavor = "woff2"
        vf.save(f"{DIST}/fonts/versions/{fn}.woff2")
        print("wrote variant", fn)
    lic = open("src/lora_OFL.txt").read().split("\n", 1)[1]
    ofl = COPYRIGHT.replace(". Copyright", ".\nCopyright") + "\n" + lic
    open(f"{DIST}/OFL.txt", "w").write(ofl)
    open("OFL.txt", "w").write(ofl)  # repository root: the license of the fonts and font sources


if __name__ == "__main__":
    main()
