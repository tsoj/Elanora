"""Design parameters for the roman."""
S, B = 45, 5  # zone margins near serifed stems / bowls

WIDEN = {
    "n": dict(y=250, d={400: [17], 700: [21]}, m=[(S, S)]),
    "h": dict(y=250, d={400: [17], 700: [21]}, m=[(S, S)]),
    "m": dict(y=250, d={400: [24, 24], 700: [27, 27]}, m=[(S, S), (S, S)]),
    "u": dict(y=250, d={400: [15], 700: [21]}, m=[(S, S)]),
    "b": dict(y=250, d={400: [24], 700: [32]}, m=[(S, B)]),
    "d": dict(y=250, d={400: [24], 700: [32]}, m=[(B, S)]),
    "p": dict(y=250, d={400: [24], 700: [32]}, m=[(S, B)]),
    "q": dict(y=250, d={400: [24], 700: [32]}, m=[(B, S)]),
    "eng": dict(y=250, d={400: [17], 700: [21]}, m=[(S, S)]),
    "hbar": dict(y=250, d={400: [17], 700: [21]}, m=[(S, S)]),
    "thorn": dict(y=250, d={400: [24], 700: [32]}, m=[(S, B)]),
    "dcroat": dict(y=250, d={400: [24], 700: [32]}, m=[(B, S)]),
    "dcaron": dict(y=250, d={400: [24], 700: [32]}, m=[(B, S)]),
    "uni03BC": dict(y=250, d={400: [15], 700: [21]}, m=[(S, S)]),
    # Cyrillic with the same n-rhythm
    "uni043F": dict(y=250, d={400: [17], 700: [21]}, m=[(S, S)]),  # п
    "uni043D": dict(y=120, d={400: [17], 700: [21]}, m=[(S, S)]),  # н
    "uni0438": dict(y=120, d={400: [17], 700: [21]}, m=[(S, S)], span=True),  # и
    "uni0446": dict(y=250, d={400: [15], 700: [21]}, m=[(S, S)]),  # ц
    "uni045F": dict(y=250, d={400: [15], 700: [21]}, m=[(S, S)]),  # џ
    "uni0448": dict(y=250, d={400: [14, 14], 700: [17, 17]}, m=[(S, S), (S, S)]),  # ш
    "uni0449": dict(y=250, d={400: [14, 14], 700: [17, 17]}, m=[(S, S), (S, S)]),  # щ
}

R_MAIN = {400: 56, 700: 78}
R_EAR = {400: 46, 700: 63}
R_SMALL = {400: 36, 700: 51}

BALLS = {
    # terminals are spliced from Brygada (fontmix/splice_jobs.py); g, ǥ, fi, fl, з, ƒ stay Lora's
}

FEET = ["one", "four", "one.tf", "four.tf", "one.osf", "four.osf", "one.tosf", "four.tosf",
        "one.numr", "four.numr", "one.dnom", "four.dnom", "uni00B9", "uni2074", "uni2081", "uni2084"]
