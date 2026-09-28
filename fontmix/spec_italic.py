"""Design parameters for the italic (Lora Italic keeps its proportions)."""
import math

R = {400: 50, 700: 70}
RS = {400: 44, 700: 62}

BALLS = {
    # terminals are spliced from Brygada's italic (fontmix/splice_jobs.py);
    # g, v, w, fi, fl, з keep Lora's own teardrops
}

FIG_WEIGHTS = {400: 400, 700: 628}
FIG_SHEAR = math.tan(math.radians(3.0)) - math.tan(math.radians(8.0))
