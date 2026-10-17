"""Las aventuras de Lolo, el patito de hule — 6 shorts de una historia continua (1080x1920, ~20 s c/u).
Todo generado por código: dibujos, animación, "voz" de burbujitas, música y efectos.
En el bot: `autocanal lolo nuevo` arma un short nuevo (historia distinta cada día) y `autocanal lolo diario` lo arma y lo sube."""
import math, os, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = "."
W, H, FPS = 1080, 1920, 30
GROUND = 1460
DUCK_X = 380
SR = 44100
from .paths import FD


def F(name, size):
    p = FD + name
    return ImageFont.truetype(p if os.path.exists(p) else FD + "Poppins-Medium.ttf", size)


EMO = F("NotoColorEmoji.ttf", 109)
NAVY = (28, 36, 84)

# ================================================================= escenarios (capas pre-dibujadas, antialias 2x)
THEMES = {
    "casa":    dict(sky=((92, 182, 255), (214, 240, 255)), mnt=(150, 170, 220), hill=(118, 204, 102), hill2=(96, 180, 86),
                    grass=(98, 190, 72), dirt=(150, 104, 62), trees=0.3, sun=True),
    "bosque":  dict(sky=((120, 200, 230), (220, 245, 230)), mnt=(120, 160, 150), hill=(70, 150, 80), hill2=(52, 125, 64),
                    grass=(70, 160, 60), dirt=(120, 86, 52), trees=1.0, sun=True),
    "rio":     dict(sky=((80, 175, 250), (205, 238, 255)), mnt=(140, 165, 215), hill=(110, 196, 110), hill2=(90, 172, 92),
                    grass=(96, 186, 76), dirt=(146, 104, 64), trees=0.4, sun=True),
    "tormenta": dict(sky=((70, 82, 110), (150, 160, 180)), mnt=(90, 100, 125), hill=(80, 130, 90), hill2=(64, 112, 76),
                     grass=(76, 140, 70), dirt=(110, 80, 52), trees=0.5, sun=False),
    "montana": dict(sky=((110, 170, 240), (230, 236, 255)), mnt=(130, 130, 170), hill=(150, 170, 110), hill2=(128, 150, 96),
                    grass=(140, 170, 90), dirt=(140, 110, 80), trees=0.2, sun=True),
    "meta":    dict(sky=((255, 150, 110), (255, 220, 150)), mnt=(200, 130, 140), hill=(150, 190, 100), hill2=(126, 168, 88),
                    grass=(120, 180, 80), dirt=(150, 104, 62), trees=0.3, sun=True),
}


def darker(c, k=0.75):
    return tuple(int(v * k) for v in c[:3])


def lighter(c, k=0.25):
    return tuple(int(v + (255 - v) * k) for v in c[:3])


def layer_far(th, width, seed):
    S = 2
    im = Image.new("RGBA", (width * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = random.Random(seed)
    x = -200
    while x < width * S:
        w = r.uniform(500, 900) * S / 2 * 2
        h = r.uniform(380, 620) * S
        base = (GROUND - 180) * S
        col = th["mnt"]
        d.polygon([(x, base), (x + w / 2, base - h), (x + w, base)], fill=col + (255,))
        d.polygon([(x + w / 2, base - h), (x + w, base), (x + w * 0.62, base)], fill=darker(col, 0.86) + (255,))
        if th is not THEMES["meta"]:
            d.polygon([(x + w / 2, base - h), (x + w / 2 - w * 0.09, base - h + h * 0.18),
                       (x + w / 2 + w * 0.09, base - h + h * 0.18)], fill=(250, 250, 255, 255))
        x += w * r.uniform(0.55, 0.8)
    return im.resize((width, H), Image.LANCZOS)


def tree(d, x, base, s, th, S):
    d.rounded_rectangle((x - 18 * s, base - 170 * s, x + 18 * s, base), radius=8 * s, fill=(120, 80, 45), outline=(80, 52, 30), width=3 * S)
    for dx, dy, rr in [(-55, -200, 75), (55, -200, 75), (0, -265, 90), (0, -180, 80)]:
        d.ellipse((x + (dx - rr) * s, base + (dy - rr) * s, x + (dx + rr) * s, base + (dy + rr) * s),
                  fill=th["hill2"], outline=darker(th["hill2"], 0.7), width=3 * S)
    d.ellipse((x - 50 * s, base - 320 * s, x + 10 * s, base - 270 * s), fill=lighter(th["hill2"], 0.3))


def layer_mid(th, width, seed):
    S = 2
    im = Image.new("RGBA", (width * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = random.Random(seed)
    x = -300
    while x < width * S:
        rx, ry = r.uniform(380, 620) * S, r.uniform(200, 330) * S
        cy = (GROUND + 60) * S
        d.ellipse((x - rx, cy - ry, x + rx, cy + ry), fill=th["hill"] + (255,), outline=darker(th["hill"], 0.8) + (255,), width=4 * S)
        d.ellipse((x - rx * 0.6, cy - ry * 0.9, x - rx * 0.1, cy - ry * 0.6), fill=lighter(th["hill"], 0.25) + (255,))
        if r.random() < th["trees"]:
            tree(d, x + r.uniform(-rx * 0.4, rx * 0.4), cy - ry * 0.75, r.uniform(0.8, 1.2) * S, th, S)
        x += rx * r.uniform(1.0, 1.5)
    return im.resize((width, H), Image.LANCZOS)


def layer_ground(th, width, seed, water=None):
    S = 2
    im = Image.new("RGBA", (width * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = random.Random(seed)
    g0 = GROUND * S
    d.rectangle((0, g0, width * S, H * S), fill=th["dirt"])
    for y in range(g0 + 80 * S, H * S, 60 * S):
        d.line((0, y, width * S, y), fill=darker(th["dirt"], 0.93), width=6 * S)
    for _ in range(width // 30):
        px, py = r.uniform(0, width * S), r.uniform(g0 + 70 * S, H * S)
        rr = r.uniform(8, 20) * S
        d.ellipse((px - rr, py - rr * 0.6, px + rr, py + rr * 0.6), fill=darker(th["dirt"], 0.82))
    d.rectangle((0, g0 - 6 * S, width * S, g0 + 46 * S), fill=th["grass"])
    d.rectangle((0, g0 + 38 * S, width * S, g0 + 52 * S), fill=darker(th["grass"], 0.8))
    for k in range(int(width / 26)):
        gx = k * 26 * S + r.uniform(-6, 6) * S
        h = r.uniform(18, 40) * S
        d.polygon([(gx, g0 + 4 * S), (gx + 9 * S, g0 - h), (gx + 18 * S, g0 + 4 * S)], fill=darker(th["grass"], 0.85))
    for _ in range(width // 260):
        fx = r.uniform(0, width * S)
        c = r.choice([(255, 90, 120), (255, 220, 60), (255, 255, 255), (170, 120, 255)])
        for a in range(5):
            ang = a * 2 * math.pi / 5
            d.ellipse((fx + math.cos(ang) * 12 * S - 9 * S, g0 - 20 * S + math.sin(ang) * 12 * S - 9 * S,
                       fx + math.cos(ang) * 12 * S + 9 * S, g0 - 20 * S + math.sin(ang) * 12 * S + 9 * S), fill=c)
        d.ellipse((fx - 7 * S, g0 - 27 * S, fx + 7 * S, g0 - 13 * S), fill=(255, 200, 40))
    if water:
        a, b = water
        d.rectangle((a * S, g0 - 10 * S, b * S, H * S), fill=(64, 150, 230))
        d.rectangle((a * S, g0 - 10 * S, b * S, g0 + 20 * S), fill=(120, 190, 250))
        for k in range(int((b - a) / 90)):
            wx = (a + 40 + k * 90) * S
            d.arc((wx, g0 + 60 * S, wx + 60 * S, g0 + 90 * S), 200, 340, fill=(200, 230, 255), width=5 * S)
    return im.resize((width, H), Image.LANCZOS)


def sky_img(th, seed):
    top, bot = np.array(th["sky"][0]), np.array(th["sky"][1])
    g = np.linspace(0, 1, H)[:, None, None]
    arr = (top * (1 - g) + bot * g).repeat(W, 1).astype(np.uint8)
    im = Image.fromarray(arr).convert("RGBA")
    if th["sun"]:
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((700, 120, 1000, 420), fill=(255, 245, 190, 150))
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
        d = ImageDraw.Draw(im)
        d.ellipse((780, 200, 920, 340), fill=(255, 232, 110), outline=(255, 200, 70), width=6)
    return im


def cloud_sprite(s, dark=False):
    S = 2
    im = Image.new("RGBA", (int(380 * s) * S, int(200 * s) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    base, shade = ((236, 240, 248), (205, 212, 228)) if not dark else ((120, 128, 150), (95, 102, 125))
    for dx, dy, r in [(90, 120, 70), (170, 90, 90), (260, 120, 70), (175, 135, 75)]:
        d.ellipse(((dx - r) * s * S, (dy - r + 10) * s * S, (dx + r) * s * S, (dy + r + 10) * s * S), fill=shade)
    for dx, dy, r in [(90, 115, 66), (170, 85, 86), (260, 115, 66), (175, 128, 70)]:
        d.ellipse(((dx - r) * s * S, (dy - r) * s * S, (dx + r) * s * S, (dy + r) * s * S), fill=base)
    return im.resize((im.width // S, im.height // S), Image.LANCZOS)


# ================================================================= personajes (antialias 2x)
YEL, YEL_D, YEL_L, ORA, ORA_D = (255, 210, 20), (226, 168, 0), (255, 240, 140), (255, 140, 20), (210, 95, 10)


def body_shade(mask, base, dark, light, lx=0.3, ly=0.25):
    w, h = mask.size
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.sqrt(((xx / w) - lx) ** 2 + ((yy / h) - ly) ** 2)
    k = np.clip(dist / 0.95, 0, 1)[..., None]
    arr = (np.array(light) * (1 - k) * 0.35 + np.array(base) * (1 - abs(k - 0.4)) * 0 + np.array(base) * 0.65 * (1 - k) +
           np.array(dark) * k)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr).convert("RGBA")
    img.putalpha(mask)
    return img


_SHADE = {}


_DCACHE = {}


def duck_sprite(walk=0.0, mouth=0.0, blink=False, look=False, sad=False, walking=True):
    k = (round(walk * 4) / 4, round(mouth * 4) / 4, blink, look, sad, walking)
    if k not in _DCACHE:
        _DCACHE[k] = _duck_sprite(*k)
    return _DCACHE[k]


def _duck_sprite(walk=0.0, mouth=0.0, blink=False, look=False, sad=False, walking=True):
    S = 2
    Z = 440 * S
    im = Image.new("RGBA", (Z, Z), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    o = 6 * S
    if walking:
        for k, ph in ((0, walk), (1, -walk)):
            fx = (190 + k * 46 + ph * 26) * S
            d.ellipse((fx - 34 * S, 384 * S, fx + 38 * S, 410 * S), fill=ORA, outline=ORA_D, width=o)
    # cuerpo con sombreado
    key = "body"
    if key not in _SHADE:
        m = Image.new("L", (Z, Z), 0)
        md = ImageDraw.Draw(m)
        md.ellipse((60 * S, 200 * S, 350 * S, 395 * S), fill=255)
        md.polygon([(70 * S, 270 * S), (18 * S, 196 * S), (110 * S, 245 * S)], fill=255)
        md.ellipse((205 * S, 58 * S, 365 * S, 218 * S), fill=255)
        _SHADE[key] = (m, body_shade(m, YEL, YEL_D, YEL_L))
    m, sh = _SHADE[key]
    if "ol" not in _SHADE:
        ol = Image.new("RGBA", (Z, Z), (190, 120, 0, 255))
        ol.putalpha(m.filter(ImageFilter.MaxFilter(13)))
        _SHADE["ol"] = ol
    im.alpha_composite(_SHADE["ol"])
    im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    d.ellipse((150 * S, 240 * S, 290 * S, 330 * S), fill=(246, 190, 0), outline=(205, 140, 0), width=o)  # ala
    d.arc((170 * S, 255 * S, 270 * S, 315 * S), 200, 330, fill=(255, 226, 90), width=5 * S)
    d.ellipse((222 * S, 76 * S, 262 * S, 104 * S), fill=(255, 250, 210))                                  # brillo
    # pico (abre al hablar)
    a = 10 + 26 * mouth
    bx, by = 352 * S, 150 * S
    up = [(bx - 12 * S, by - 22 * S), (bx + 70 * S, by - 4 * S - a * 0.3 * S), (bx - 4 * S, by + 4 * S)]
    lo = [(bx - 10 * S, by + 2 * S), (bx + 58 * S, by + 10 * S + a * 0.8 * S), (bx - 8 * S, by + 24 * S)]
    if mouth > 0.15:
        d.polygon([(bx - 8 * S, by), (bx + 55 * S, by + a * 0.4 * S), (bx - 6 * S, by + 12 * S)], fill=(150, 40, 40))
    d.polygon(lo, fill=ORA_D, outline=(170, 70, 0))
    d.polygon(up, fill=ORA, outline=(170, 70, 0))
    # ojo
    ex, ey = 300 * S, 118 * S
    if blink:
        d.arc((ex - 22 * S, ey - 14 * S, ex + 22 * S, ey + 16 * S), 10, 170, fill=(30, 30, 50), width=7 * S)
    else:
        d.ellipse((ex - 26 * S, ey - 30 * S, ex + 26 * S, ey + 30 * S), fill=(255, 255, 255), outline=(40, 40, 60), width=4 * S)
        px = ex + (2 if look else 8) * S
        d.ellipse((px - 16 * S, ey - 18 * S, px + 16 * S, ey + 20 * S), fill=(30, 30, 50))
        d.ellipse((px - 9 * S, ey - 12 * S, px + 1 * S, ey - 2 * S), fill=(255, 255, 255))
        d.ellipse((px + 4 * S, ey + 6 * S, px + 9 * S, ey + 11 * S), fill=(255, 255, 255))
    if sad:
        d.line((ex - 26 * S, ey - 42 * S, ex + 22 * S, ey - 30 * S), fill=(120, 80, 0), width=6 * S)
    else:
        d.arc((ex - 26 * S, ey - 52 * S, ex + 24 * S, ey - 30 * S), 200, 340, fill=(150, 100, 0), width=6 * S)
    d.ellipse((262 * S, 150 * S, 300 * S, 176 * S), fill=(255, 150, 140))
    return im.resize((Z // S, Z // S), Image.LANCZOS)


_FCACHE = {}


def frog_sprite(mouth=0.0, blink=False):
    k = (round(mouth * 4) / 4, blink)
    if k not in _FCACHE:
        _FCACHE[k] = _frog_sprite(*k)
    return _FCACHE[k]


def _frog_sprite(mouth=0.0, blink=False):
    S = 2
    Z = 320 * S
    im = Image.new("RGBA", (Z, Z), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    G, GD, GL = (90, 190, 80), (50, 130, 50), (150, 225, 120)
    o = 6 * S
    d.ellipse((40 * S, 150 * S, 280 * S, 300 * S), fill=G, outline=GD, width=o)
    d.ellipse((90 * S, 200 * S, 230 * S, 290 * S), fill=GL)
    for ex in (100, 220):
        d.ellipse(((ex - 46) * S, 92 * S, (ex + 46) * S, 184 * S), fill=G, outline=GD, width=o)
        if blink:
            d.line(((ex - 22) * S, 140 * S, (ex + 22) * S, 140 * S), fill=(30, 30, 40), width=7 * S)
        else:
            d.ellipse(((ex - 28) * S, 110 * S, (ex + 28) * S, 166 * S), fill=(255, 255, 255))
            d.ellipse(((ex - 13) * S, 124 * S, (ex + 13) * S, 152 * S), fill=(30, 30, 40))
            d.ellipse(((ex - 8) * S, 128 * S, (ex - 1) * S, 136 * S), fill=(255, 255, 255))
    h = 8 + 30 * mouth
    d.chord((110 * S, (190 - h / 2) * S, 210 * S, (200 + h) * S), 0, 180, fill=(170, 40, 60), outline=GD, width=4 * S)
    d.ellipse((70 * S, 200 * S, 100 * S, 220 * S), fill=(255, 150, 150))
    d.ellipse((220 * S, 200 * S, 250 * S, 220 * S), fill=(255, 150, 150))
    d.rectangle((0, 0, 1, 1), fill=(0, 0, 0, 0))
    # moño
    d.polygon([(130 * S, 80 * S), (160 * S, 98 * S), (130 * S, 116 * S)], fill=(255, 80, 140))
    d.polygon([(190 * S, 80 * S), (160 * S, 98 * S), (190 * S, 116 * S)], fill=(255, 80, 140))
    d.ellipse((150 * S, 88 * S, 170 * S, 108 * S), fill=(255, 120, 170))
    return im.resize((Z // S, Z // S), Image.LANCZOS)


# ================================================================= utilería
def prop(d, kind, x, t=0.0):
    G = GROUND
    o = 5
    if kind == "piedra":
        d.ellipse((x - 90, G - 120, x + 90, G + 20), fill=(132, 132, 146), outline=(80, 80, 95), width=o)
        d.ellipse((x - 58, G - 104, x + 4, G - 64), fill=(170, 170, 184))
    elif kind == "piedrita":
        d.ellipse((x - 55, G - 70, x + 55, G + 12), fill=(132, 132, 146), outline=(80, 80, 95), width=o)
    elif kind == "tronco":
        d.rounded_rectangle((x - 130, G - 100, x + 130, G + 6), radius=44, fill=(156, 98, 50), outline=(96, 58, 30), width=o)
        for k in range(3):
            d.line((x - 100 + k * 60, G - 70, x - 60 + k * 60, G - 70), fill=(120, 74, 38), width=5)
        d.ellipse((x + 80, G - 100, x + 176, G + 6), fill=(214, 160, 104), outline=(96, 58, 30), width=o)
        d.ellipse((x + 104, G - 74, x + 152, G - 20), outline=(156, 98, 50), width=6)
    elif kind == "conos":
        for k in (-80, 0, 80):
            d.polygon([(x + k - 44, G), (x + k + 44, G), (x + k, G - 140)], fill=(255, 112, 30), outline=(190, 70, 10))
            d.polygon([(x + k - 26, G - 58), (x + k + 26, G - 58), (x + k + 18, G - 80), (x + k - 18, G - 80)], fill=(255, 255, 255))
            d.rectangle((x + k - 52, G - 8, x + k + 52, G + 6), fill=(230, 90, 20))
    elif kind == "hoja":
        d.ellipse((x - 120, G - 24, x + 120, G + 26), fill=(80, 180, 80), outline=(40, 120, 50), width=o)
        d.pieslice((x - 120, G - 24, x + 120, G + 26), 330, 350, fill=(64, 150, 230))
        d.line((x - 90, G, x + 60, G), fill=(60, 150, 60), width=4)
    elif kind == "cartel":
        d.rectangle((x - 12, G - 420, x + 12, G), fill=(130, 86, 46), outline=(90, 56, 30), width=4)
        d.rounded_rectangle((x - 200, G - 520, x + 200, G - 280), radius=18, fill=(255, 246, 220), outline=(130, 86, 46), width=8)
        f1, f2 = F("Anton-Regular.ttf", 56), F("Poppins-Bold.ttf", 34)
        for txt, f, yy, c in [("GRAN CARRERA", f1, G - 500, (230, 60, 60)), ("al Lago Dorado", f2, G - 420, NAVY),
                              ("¡Todos invitados!", f2, G - 370, NAVY)]:
            w = d.textlength(txt, font=f)
            d.text((x - w / 2, yy), txt, font=f, fill=c)
    elif kind == "hongo":
        d.rounded_rectangle((x - 45, G - 300, x + 45, G), radius=20, fill=(250, 240, 220), outline=(170, 150, 120), width=o)
        d.pieslice((x - 260, G - 470, x + 260, G - 150), 180, 360, fill=(230, 50, 60), outline=(150, 20, 30), width=o)
        for dx, dy, r in [(-150, -360, 34), (-30, -420, 40), (110, -370, 32), (190, -320, 22)]:
            d.ellipse((x + dx - r, G + dy - r, x + dx + r, G + dy + r), fill=(255, 255, 255))
    elif kind == "estanque":
        d.ellipse((x - 260, G - 30, x + 260, G + 70), fill=(64, 150, 230), outline=(40, 110, 190), width=o)
        d.ellipse((x - 180, G - 14, x - 40, G + 16), fill=(150, 210, 255))
    elif kind == "meta":
        for side in (-280, 280):
            d.rectangle((x + side - 16, G - 660, x + side + 16, G), fill=(96, 96, 110), outline=(60, 60, 70), width=4)
        sq = 40
        for i in range(14):
            for j in range(3):
                c = (25, 25, 30) if (i + j) % 2 == 0 else (255, 255, 255)
                d.rectangle((x - 280 + i * sq, G - 660 + j * sq, x - 280 + (i + 1) * sq, G - 660 + (j + 1) * sq), fill=c)
        f = F("Anton-Regular.ttf", 96)
        tw = d.textlength("META", font=f)
        d.rounded_rectangle((x - tw / 2 - 34, G - 560, x + tw / 2 + 34, G - 420), radius=26, fill=(230, 40, 60), outline=(150, 20, 30), width=6)
        d.text((x - tw / 2, G - 556), "META", font=f, fill=(255, 255, 255))
    elif kind == "flor":
        d.rectangle((x - 8, G - 300, x + 8, G), fill=(60, 150, 60))
        d.ellipse((x - 70, G - 170, x, G - 130), fill=(80, 180, 80))
        for a in range(8):
            ang = a * math.pi / 4 + t * 0.5
            px, py = x + math.cos(ang) * 70, G - 330 + math.sin(ang) * 70
            d.ellipse((px - 48, py - 48, px + 48, py + 48), fill=(255, 120, 190), outline=(200, 60, 140), width=4)
        d.ellipse((x - 46, G - 376, x + 46, G - 284), fill=(255, 220, 60), outline=(220, 160, 20), width=5)
    elif kind == "torta":
        d.rounded_rectangle((x - 170, G - 170, x + 170, G), radius=20, fill=(255, 200, 220), outline=(200, 110, 140), width=6)
        d.rounded_rectangle((x - 120, G - 290, x + 120, G - 160), radius=18, fill=(255, 235, 245), outline=(200, 110, 140), width=6)
        for k in (-60, 0, 60):
            d.rectangle((x + k - 8, G - 360, x + k + 8, G - 290), fill=(120, 190, 255))
            fl = 10 + 4 * math.sin(t * 12 + k)
            d.ellipse((x + k - 10, G - 360 - fl * 2, x + k + 10, G - 356), fill=(255, 190, 40))
        for k in range(-150, 160, 50):
            d.ellipse((x + k - 12, G - 100, x + k + 12, G - 76), fill=(255, 90, 140))
    elif kind == "lago":
        d.ellipse((x - 100, G - 70, x + 900, G + 90), fill=(255, 200, 60), outline=(220, 150, 20), width=o)
        d.ellipse((x + 40, G - 50, x + 400, G), fill=(255, 236, 150))


def text_c(im, txt, y, size, fill, stroke=10, font="Anton-Regular.ttf"):
    d = ImageDraw.Draw(im)
    f = F(font, size)
    while d.textlength(txt, font=f) > W - 90 and size > 40:
        size -= 4
        f = F(font, size)
    w = d.textlength(txt, font=f)
    d.text(((W - w) / 2, y), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=NAVY)


def emoji_at(im, ch, x, y, size):
    e = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
    ImageDraw.Draw(e).text((0, 0), ch, font=EMO, embedded_color=True)
    e = e.crop(e.getbbox()).resize((size, size), Image.LANCZOS)
    im.alpha_composite(e, (int(x), int(y)))


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    lines.append(cur)
    return lines


def bubble(im, text, hx, hy, appear):
    """Globo de diálogo arriba del personaje, con cola hacia (hx, hy)."""
    d = ImageDraw.Draw(im)
    f = F("Poppins-Bold.ttf", 60)
    emo = None
    if text and ord(text[-1]) > 0x2500:
        text, emo = text[:-1].rstrip(), text[-1]
    lines = wrap(d, text, f, 780)
    lh = 76
    bw = max(d.textlength(l, font=f) for l in lines) + 90 + (90 if emo else 0)
    bh = len(lines) * lh + 60
    s = min(1.0, appear / 0.15)
    bw2, bh2 = bw * (0.7 + 0.3 * s), bh * (0.7 + 0.3 * s)
    cx = min(max(hx + 60, bw2 / 2 + 40), W - bw2 / 2 - 40)
    by1 = hy - 120
    x0, y0, x1, y1 = cx - bw2 / 2, by1 - bh2, cx + bw2 / 2, by1
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.rounded_rectangle((x0 + 8, y0 + 12, x1 + 8, y1 + 12), radius=46, fill=(0, 0, 0, 60))
    ld.polygon([(hx + 30, y1 - 4), (hx + 110, y1 - 4), (hx + 30, hy - 40)], fill=(255, 255, 255, 255), outline=NAVY)
    ld.rounded_rectangle((x0, y0, x1, y1), radius=46, fill=(255, 255, 255, 255), outline=NAVY, width=7)
    ld.polygon([(hx + 36, y1 - 9), (hx + 104, y1 - 9), (hx + 36, hy - 52)], fill=(255, 255, 255, 255))
    im.alpha_composite(lay)
    if s >= 1:
        d = ImageDraw.Draw(im)
        for k, l in enumerate(lines):
            d.text((x0 + 45, y0 + 28 + k * lh), l, font=f, fill=NAVY)
        if emo:
            emoji_at(im, emo, x1 - 120, (y0 + y1) / 2 - 40, 80)


# ================================================================= episodios (guion)
EPIS = [
    dict(n=1, titulo="¡HOLA, SOY LOLO!", tema="casa", dur=21.0, sig="Capítulo 2: El bosque",
         moves=[(0, 9.0, 0), (9.0, 18.4, 330)],
         saltos=[(14.6, "piedrita")],
         props=[(DUCK_X + 470, "cartel"), (DUCK_X - 330, "estanque")],
         dice=[(0.4, 3.4, "lolo", "¡Hola! Soy Lolo, un patito de hule. 🦆"),
               (3.6, 6.2, "lolo", "¡Mira lo que encontré!"),
               (6.4, 9.0, "lolo", "¡Una carrera hasta el Lago Dorado! 🏆"),
               (9.6, 12.6, "lolo", "¡Voy a llegar a la meta! ¿Me acompañas?"),
               (15.6, 18.0, "lolo", "¡Allá voy! 💪")]),
    dict(n=2, titulo="EL BOSQUE", tema="bosque", dur=21.0, sig="Capítulo 3: El río",
         moves=[(0, 9.2, 340), (9.2, 15.2, 0), (15.2, 18.6, 340)],
         saltos=[(3.0, "tronco"), (6.6, "piedra")],
         frog=("rita_fija", 9.2),
         dice=[(0.3, 2.8, "lolo", "¡Este bosque es enorme! 🌲"),
               (3.4, 5.6, "lolo", "¡Hop! ¡Un tronco!"),
               (9.4, 12.2, "rita", "¡Hola, Lolo! Soy Rita. El río está cerca."),
               (12.3, 15.0, "rita", "¡Salta con cuidado! 🐸"),
               (15.3, 18.0, "lolo", "¡Gracias, Rita! ¡Nos vemos en la meta!")]),
    dict(n=3, titulo="EL RÍO", tema="rio", dur=21.0, sig="Capítulo 4: La tormenta",
         moves=[(0, 2.4, 340), (2.4, 7.2, 0), (7.2, 13.6, 300), (13.6, 15.8, 0), (15.8, 18.6, 340)],
         saltos=[(8.2, "hoja"), (9.9, "hoja"), (11.6, "hoja")],
         rio=True, splash=11.95,
         dice=[(2.5, 4.8, "lolo", "¡Uy! Un río... ¡y no hay puente!"),
               (4.9, 7.1, "lolo", "¡Ya sé! Saltaré por las hojas. 🍃"),
               (12.2, 14.2, "lolo", "¡Uf! ¡Casi me mojo!"),
               (14.3, 17.8, "lolo", "¡Ah, verdad! Yo soy de hule... ¡yo floto! 😄")]),
    dict(n=4, titulo="LA TORMENTA", tema="tormenta", dur=21.0, sig="Capítulo 5: Los obstáculos",
         moves=[(0, 3.6, 330), (3.6, 15.2, 0), (15.2, 18.6, 330)],
         props_rel=[(4.2, "hongo")], lluvia=(4.6, 13.0), truenos=[2.6, 7.4], arcoiris=13.4,
         dice=[(0.3, 2.4, "lolo", "¡Qué nubes tan grises!"),
               (2.8, 4.4, "lolo", "¿Oyeron eso? ⚡"),
               (5.0, 8.4, "lolo", "¡Qué lluvia! Me escondo bajo este hongo. 🍄"),
               (13.6, 16.4, "lolo", "¡Mira! ¡Un arcoíris! 🌈"),
               (16.5, 18.6, "lolo", "¡Sigo adelante!")]),
    dict(n=5, titulo="LOS OBSTÁCULOS", tema="montana", dur=21.0, sig="Capítulo 6: ¡La meta!",
         moves=[(0, 7.4, 340), (7.4, 12.4, 0), (12.4, 18.6, 340)],
         saltos=[(2.2, "conos"), (4.6, "tronco"), (14.0, "piedra")],
         caida=(7.0, 9.6, "piedrita"),
         dice=[(0.3, 2.0, "lolo", "¡Cuántos obstáculos!"),
               (7.6, 9.4, "lolo", "Ay... me caí. 😢"),
               (9.8, 12.2, "lolo", "¡Pero no me rindo! 💪"),
               (15.0, 18.4, "lolo", "¡Ya veo el Lago Dorado! ✨")]),
    dict(n=6, titulo="¡LA META!", tema="meta", dur=22.0, sig=None,
         moves=[(0, 9.0, 430), (9.0, 22.0, 0)],
         props_rel=[(9.0, "meta"), (11.0, "lago")], frog=("rita_meta", 9.0), festejo=9.0,
         dice=[(0.3, 2.6, "lolo", "¡Ahí está la meta! ¡A toda velocidad! 🏁"),
               (9.4, 12.0, "lolo", "¡LO LOGRÉ! 🏆"),
               (12.2, 14.8, "rita", "¡Bravo, Lolo! ¡Nunca te rendiste! 🐸"),
               (15.0, 18.4, "lolo", "¡Gracias por acompañarme en esta aventura! 💛")]),
]
JUMP_D, JUMP_H = 0.8, 330


def cam_fn(ep):
    def cam(t):
        x = 0.0
        for a, b, v in ep["moves"]:
            if t > a:
                x += v * (min(t, b) - a)
        return x
    return cam


def moving(ep, t):
    return any(a <= t < b and v > 0 for a, b, v in ep["moves"])


# ================================================================= audio
NOTE = {n: 261.63 * 2 ** (k / 12) for k, n in enumerate("C C# D D# E F F# G G# A A# B".split())}


def tone(f, d, kind="tri", vol=0.2, decay=3.0):
    t = np.arange(int(SR * d)) / SR
    if kind == "tri":
        s = 2 * np.abs(2 * (t * f % 1) - 1) - 1
    elif kind == "sq":
        s = np.sign(np.sin(2 * np.pi * f * t)) * 0.45
    else:
        s = np.sin(2 * np.pi * f * t)
    return s * np.minimum(1, t / 0.008) * np.exp(-t * decay) * vol


def add(a, s, t0):
    i0 = int(t0 * SR)
    if i0 >= len(a):
        return
    s = s[: len(a) - i0]
    a[i0:i0 + len(s)] += s


def audio(ep, path):
    D = ep["dur"]
    a = np.zeros(int(SR * D))
    rnd = random.Random(ep["n"])
    keys = [0, 5, 7, 2, 9, 0]
    tr = keys[(ep["n"] - 1) % len(keys)]
    mel = [0, 4, 7, 4, 5, 9, 7, 4, 2, 5, 4, 0, 2, 7, 0, 7] if ep["tema"] != "tormenta" else [0, 3, 7, 3, 5, 8, 7, 3]
    prog = [0, 5, 7, 0]
    beat = 0.36 if ep["tema"] != "tormenta" else 0.42
    vol_m = 0.06
    for k in range(int((D - 0.5) / beat)):
        t0 = k * beat
        speaking = any(s0 <= t0 <= s1 for s0, s1, _, _ in ep["dice"])
        v = vol_m * (0.5 if speaking else 1)
        n = mel[k % len(mel)] + tr
        add(a, tone(NOTE["C"] * 2 ** (n / 12) * 2, beat * 0.9, "sq", v), t0)
        if k % 2 == 0:
            add(a, tone(NOTE["C"] * 2 ** ((prog[(k // 8) % 4] + tr) / 12) / 2, beat * 1.8, "tri", 0.16 * (0.7 if speaking else 1), 2), t0)
    for s0, s1, who, txt in ep["dice"]:                                   # voz de burbujitas
        n_syl = max(3, int(len(txt) / 3.2))
        dt = min(0.11, (s1 - s0 - 0.4) / n_syl)
        base = 760 if who == "lolo" else 520
        for k in range(n_syl):
            f = base * (1 + rnd.uniform(-0.18, 0.25))
            t = np.arange(int(SR * dt * 0.8)) / SR
            s = np.sin(2 * np.pi * f * t + 3 * np.sin(2 * np.pi * f * 2 * t)) * np.sin(np.pi * t / t[-1]) * 0.22
            add(a, s, s0 + 0.15 + k * dt)
    for t0, _ in ep.get("saltos", []):
        t = np.arange(int(SR * 0.35)) / SR
        f = 230 + 900 * t / 0.35
        add(a, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 0.32, t0)
    for t0 in ep.get("truenos", []):
        nz = np.random.default_rng(int(t0 * 10)).normal(0, 1, int(SR * 2.2))
        nz = np.convolve(nz, np.ones(160) / 160, "same") * np.exp(-np.arange(len(nz)) / SR * 1.6) * 3.0
        add(a, nz, t0)
    if ep.get("lluvia"):
        r0, r1 = ep["lluvia"]
        nz = np.random.default_rng(3).normal(0, 0.05, int(SR * (r1 - r0)))
        env = np.minimum(1, np.minimum(np.arange(len(nz)), len(nz) - np.arange(len(nz))) / SR / 0.8)
        add(a, nz * env, r0)
    if ep.get("splash"):
        nz = np.random.default_rng(9).normal(0, 0.3, int(SR * 0.6)) * np.exp(-np.arange(int(SR * 0.6)) / SR * 6)
        add(a, np.convolve(nz, np.ones(8) / 8, "same"), ep["splash"])
    if ep.get("caida"):
        t = np.arange(int(SR * 0.5)) / SR
        add(a, np.sin(2 * np.pi * (700 - 500 * t / 0.5) * t) * np.exp(-t * 4) * 0.3, ep["caida"][0] + 0.3)
    if ep.get("festejo") is not None or ep.get("arcoiris"):
        t0 = ep.get("festejo") or ep["arcoiris"]
        for k, n in enumerate(["C", "E", "G", "C"]):
            add(a, tone(NOTE[n] * (4 if k == 3 else 2), 1.0 if k == 3 else 0.2, "sq", 0.12), t0 + k * 0.14)
    add(a, tone(NOTE["G"] * 2, 0.15, "sq", 0.1), D - 2.3)                  # cierre
    add(a, tone(NOTE["C"] * 4, 0.6, "sq", 0.1), D - 2.15)
    a = np.clip(a / max(1e-6, np.abs(a).max()) * 0.85, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


# ================================================================= render de un episodio
def render(ep):
    th = THEMES[ep["tema"]]
    cam = cam_fn(ep)
    D = ep["dur"]
    total = cam(D) + W + 600
    far = layer_far(th, int(total * 0.25) + W + 400, ep["n"] * 7)
    mid = layer_mid(th, int(total * 0.55) + W + 400, ep["n"] * 11)
    water = None
    if ep.get("rio"):
        a = DUCK_X + cam(7.6) + 60
        b = DUCK_X + cam(13.0) + 40
        water = (a, b)
    gnd = layer_ground(th, int(total) + W, ep["n"] * 13, water)
    sky = sky_img(th, ep["n"])
    clouds = [(random.Random(ep["n"] * 3 + k).uniform(0, 2400), 240 + k * 150 + random.Random(k).uniform(-60, 60),
               cloud_sprite(random.Random(k).uniform(0.7, 1.2), ep["tema"] == "tormenta")) for k in range(5)]
    # utilería ubicada en el mundo
    props = list(ep.get("props", []))
    for t0, kind in ep.get("saltos", []):
        props.append((DUCK_X + cam(t0 + JUMP_D / 2) + 120, kind))
    for t0, kind in ep.get("props_rel", []):
        props.append((DUCK_X + cam(t0) + {"hongo": 60, "meta": 260, "flor": 300, "torta": 330}.get(kind, 600), kind))
    if ep.get("caida"):
        props.append((DUCK_X + cam(ep["caida"][0]) + 150, ep["caida"][2]))
    frog_x = None
    if ep.get("frog"):
        kind, t0 = ep["frog"]
        frog_x = DUCK_X + cam(t0) + (330 if kind == "rita_fija" else 560)
    rng = random.Random(ep["n"])
    conf = [(rng.uniform(0, W), rng.uniform(-1200, 0), rng.uniform(-80, 80), rng.uniform(280, 560),
             rng.choice([(255, 80, 80), (80, 200, 255), (255, 214, 10), (120, 220, 120), (200, 120, 255)])) for _ in range(160)]
    drops = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(900, 1300)) for _ in range(220)]
    wav = os.path.join(OUT, f"lolo_cap{ep['n']}.wav")
    audio(ep, wav)
    out = os.path.join(OUT, f"{ep.get('pref', 'lolo_cap')}{ep['n']}.mp4")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    vign = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vign).rectangle((0, 0, W, H), fill=0)
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip(((xx / W - 0.5) ** 2 + (yy / H - 0.45) ** 2 * 0.6) * 1.6 - 0.15, 0, 1) * 110
    vign = Image.fromarray(v.astype(np.uint8))
    vlay = Image.new("RGBA", (W, H), (10, 10, 40, 255))
    vlay.putalpha(vign)
    for i in range(int(D * FPS)):
        t = i / FPS
        cx = cam(t)
        im = sky.copy()
        if ep["tema"] == "tormenta" and any(abs(t - tt) < 0.12 for tt in ep.get("truenos", [])):
            im = Image.new("RGBA", (W, H), (235, 240, 255, 255))
        for x0, y0, cs in clouds:
            im.alpha_composite(cs, (int((x0 - cx * 0.08 + t * 12) % (W + 600) - 400), int(y0)))
        if ep.get("arcoiris") and t >= ep["arcoiris"]:
            al = min(1, (t - ep["arcoiris"]) / 1.2)
            rb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            rd = ImageDraw.Draw(rb)
            for k, c in enumerate([(255, 70, 70), (255, 160, 40), (255, 230, 60), (90, 210, 90), (70, 150, 255), (150, 90, 230)]):
                r = 760 - k * 34
                rd.arc((W / 2 - r, 1100 - r, W / 2 + r, 1100 + r), 180, 360, fill=c + (int(200 * al),), width=36)
            im.alpha_composite(rb)
        im.alpha_composite(far, (-int(cx * 0.25) - 200, 0))
        im.alpha_composite(mid, (-int(cx * 0.55) - 200, 0))
        im.alpha_composite(gnd, (-int(cx), 0))
        d = ImageDraw.Draw(im)
        for px, kind in props:
            sx = px - cx
            if -1000 < sx < W + 1000:
                prop(d, kind, sx, t)
        # estado del pato
        jy, jumping, squash = 0.0, False, 1.0
        for t0, _ in ep.get("saltos", []):
            if t0 <= t <= t0 + JUMP_D:
                u = (t - t0) / JUMP_D
                jy, jumping = JUMP_H * 4 * u * (1 - u), True
                squash = 1.08 if u < 0.5 else 0.96
            elif t0 + JUMP_D < t < t0 + JUMP_D + 0.12:
                squash = 0.85                                              # aterriza
        fest = ep.get("festejo")
        if fest is not None and t > fest + 0.2:
            u = ((t - fest - 0.2) % 0.7) / 0.7
            jy, jumping = 170 * 4 * u * (1 - u), True
        fall = ep.get("caida")
        fallen = fall and fall[0] + 0.3 <= t <= fall[1]
        speaking = next(((s0, s1, w_, tx) for s0, s1, w_, tx in ep["dice"] if s0 <= t <= s1), None)
        mouth = 0.0
        if speaking and speaking[2] == "lolo":
            mouth = 0.5 + 0.5 * math.sin((t - speaking[0]) * 2 * math.pi * 5.5)
        walk = math.sin(t * 2 * math.pi * 3.2) if moving(ep, t) and not jumping else 0
        floatbob = 0
        if ep["tema"] == "casa" and t < 9.0:
            floatbob = 8 * math.sin(t * 2.2)
        dk = duck_sprite(walk, mouth, blink=(t % 2.8) < 0.13, look=bool(speaking), sad=bool(fallen),
                         walking=not jumping)
        ang = 0 if jumping else 5 * walk
        if jumping:
            ang = -12
        if fallen:
            ang = 75
        if abs(squash - 1) > 0.01:
            dk = dk.resize((int(dk.width / squash ** 0.5), int(dk.height * squash)), Image.LANCZOS)
        dk = dk.rotate(ang, resample=Image.BICUBIC, center=(dk.width // 2, dk.height - 40), expand=False)
        shw = max(0.4, 1 - jy / 520)
        d.ellipse((DUCK_X - 150 * shw, GROUND - 16, DUCK_X + 150 * shw, GROUND + 20), fill=darker(th["grass"], 0.6))
        dy = GROUND - dk.height + 30 - jy + floatbob
        if fallen:
            dy += 70
        im.alpha_composite(dk, (int(DUCK_X - dk.width / 2), int(dy)))
        if fallen:                                                         # estrellitas
            for k in range(3):
                ang2 = t * 5 + k * 2.1
                emoji_at(im, "⭐", DUCK_X + 40 + math.cos(ang2) * 90, dy + 60 + math.sin(ang2) * 30, 52)
        # aterrizaje: polvito
        for t0, _ in ep.get("saltos", []):
            if t0 + JUMP_D <= t < t0 + JUMP_D + 0.35:
                u = (t - t0 - JUMP_D) / 0.35
                for k in range(-3, 4):
                    rr = 14 * (1 - u)
                    d.ellipse((DUCK_X + k * 40 * (0.5 + u) - rr, GROUND - 10 - u * 30 - rr, DUCK_X + k * 40 * (0.5 + u) + rr,
                               GROUND - 10 - u * 30 + rr), fill=(240, 230, 210))
        if ep.get("splash") and ep["splash"] <= t < ep["splash"] + 0.6:
            u = (t - ep["splash"]) / 0.6
            for k in range(14):
                a2 = math.pi * (0.15 + 0.7 * k / 13)
                rr = 16 * (1 - u)
                px = DUCK_X + 60 + math.cos(a2) * 260 * u
                py = GROUND - math.sin(a2) * 300 * u + 400 * u * u
                d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(140, 200, 255))
        # rana
        if frog_x is not None:
            fx = frog_x - cx
            if -300 < fx < W + 300:
                fm = 0.0
                if speaking and speaking[2] == "rita":
                    fm = 0.5 + 0.5 * math.sin((t - speaking[0]) * 2 * math.pi * 5)
                hop = 0
                if fest is not None and t > fest + 0.5:
                    u = ((t - fest) % 0.55) / 0.55
                    hop = 90 * 4 * u * (1 - u)
                if ep["frog"][0] == "rita_fija":
                    d.rounded_rectangle((fx - 130, GROUND - 110, fx + 130, GROUND + 8), radius=20, fill=(156, 98, 50), outline=(96, 58, 30), width=5)
                    d.ellipse((fx - 130, GROUND - 140, fx + 130, GROUND - 80), fill=(214, 160, 104), outline=(96, 58, 30), width=5)
                fr = frog_sprite(fm, blink=(t % 3.1) < 0.12)
                base = GROUND - 110 if ep["frog"][0] == "rita_fija" else GROUND + 20
                im.alpha_composite(fr, (int(fx - 160), int(base - 300 - hop)))
        # lluvia
        if ep.get("lluvia") and ep["lluvia"][0] <= t <= ep["lluvia"][1]:
            for x0, y0, sp in drops:
                yy0 = (y0 + t * sp) % H
                d.line((x0, yy0, x0 - 12, yy0 + 44), fill=(200, 215, 255), width=4)
        # confeti
        if fest is not None and t > fest:
            for x0, y0, vx, vy, c in conf:
                tt = t - fest
                px, py = x0 + vx * tt, y0 + vy * tt * 1.5
                if 0 < py < H:
                    d.rectangle((px, py, px + 18, py + 30), fill=c)
            if t > fest + 0.3:
                emoji_at(im, ep.get("premio", "🏆"), W / 2 - 100, 520, 200)
        # diálogo
        if speaking:
            s0, s1, who, txt = speaking
            if who == "lolo":
                hx, hy = DUCK_X + 80, dy + 70
            else:
                hx, hy = (frog_x - cx) - 40, (GROUND - 110 if ep["frog"][0] == "rita_fija" else GROUND + 20) - 260
            bubble(im, txt, min(max(hx, 120), W - 220), max(hy, 760), t - s0)
        im.alpha_composite(vlay)
        # marca y títulos
        d = ImageDraw.Draw(im)
        f2 = F("Poppins-Bold.ttf", 40)
        tag = "LAS AVENTURAS DE LOLO"
        w2 = d.textlength(tag, font=f2)
        d.rounded_rectangle((W / 2 - w2 / 2 - 34, 64, W / 2 + w2 / 2 + 34, 136), radius=36, fill=(255, 255, 255, 230), outline=(255, 170, 30), width=5)
        d.text((W / 2 - w2 / 2, 74), tag, font=f2, fill=(240, 120, 10))
        if t < 2.6:
            al = 1 if t < 2.2 else (2.6 - t) / 0.4
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            text_c(lay, ep.get("etiqueta", f"CAPÍTULO {ep['n']}"), 190, 70, (255, 214, 10), 8)
            text_c(lay, ep["titulo"], 280, 120, (255, 255, 255), 11)
            if al < 1:
                lay.putalpha(lay.getchannel("A").point(lambda v: int(v * al)))
            im.alpha_composite(lay)
        if t > D - 2.4:
            u = min(1, (t - (D - 2.4)) / 0.35)
            ov = Image.new("RGBA", (W, H), (20, 26, 70, int(170 * u)))
            im.alpha_composite(ov)
            if u >= 1:
                if ep["sig"]:
                    text_c(im, "CONTINUARÁ...", 640, 130, (255, 214, 10), 11)
                    text_c(im, ep["sig"], 820, 76, (255, 255, 255), 8)
                    text_c(im, "¡Sígueme para ver qué pasa!", 960, 58, (255, 255, 255), 6, "Poppins-Bold.ttf")
                else:
                    text_c(im, "¡FIN!", 600, 170, (255, 214, 10), 12)
                    text_c(im, "¿Quieres más aventuras de Lolo?", 840, 62, (255, 255, 255), 6, "Poppins-Bold.ttf")
                    text_c(im, "¡SUSCRÍBETE! 💛"[:-2], 940, 100, (255, 255, 255), 9)
                emoji_at(im, "🦆", W / 2 - 90, 1120, 180)
        p.stdin.write(im.convert("RGB").tobytes())
    p.stdin.close()
    p.wait()
    os.remove(wav)
    print("ok", out, flush=True)


EPIS2 = [
    dict(n=1, titulo="UNA SORPRESA PARA RITA", tema="casa", dur=20.0, sig="Parte 2: El río otra vez",
         moves=[(0, 9.6, 0), (9.6, 17.6, 330)], saltos=[(13.6, "piedrita")],
         props=[(DUCK_X - 330, "estanque")],
         dice=[(0.3, 3.0, "lolo", "¡Hola, amigos! ¡Hoy es el cumple de Rita! 🎂"),
               (3.2, 6.2, "lolo", "Quiero regalarle algo muy especial..."),
               (6.4, 9.4, "lolo", "¡Ya sé! ¡La flor mágica del Valle Rosa! 🌸"),
               (10.0, 13.0, "lolo", "¡Vamos a buscarla juntos!"),
               (14.6, 17.4, "lolo", "¡Hop! ¡Nada me detiene! 💪")]),
    dict(n=2, titulo="EL RÍO OTRA VEZ", tema="rio", dur=20.0, sig="Parte 3: La montaña de las flores",
         moves=[(0, 2.4, 340), (2.4, 6.4, 0), (6.4, 12.8, 300), (12.8, 17.6, 340)],
         saltos=[(7.4, "hoja"), (9.1, "hoja"), (10.8, "hoja")], rio=True,
         dice=[(2.5, 4.4, "lolo", "¡El río otra vez!"),
               (4.5, 6.4, "lolo", "Pero ahora ya sé saltar. 😎"),
               (12.9, 15.3, "lolo", "¡Lo crucé sin miedo!"),
               (15.4, 17.6, "lolo", "¡La práctica hace al maestro! ⭐")]),
    dict(n=3, titulo="LA MONTAÑA DE LAS FLORES", tema="montana", dur=20.0, sig="Parte 4: ¡Feliz cumple, Rita!",
         moves=[(0, 8.6, 340), (8.6, 14.6, 0), (14.6, 17.6, 340)],
         saltos=[(2.4, "conos"), (5.4, "tronco")], props_rel=[(8.6, "flor")],
         dice=[(0.3, 2.2, "lolo", "¡Qué alta es esta montaña!"),
               (8.8, 11.4, "lolo", "¡Ahí está! ¡La flor mágica! 🌸"),
               (11.6, 14.4, "lolo", "¡Es perfecta para Rita! 💖"),
               (14.8, 17.6, "lolo", "¡Rápido, que empieza la fiesta!")]),
    dict(n=4, titulo="¡FELIZ CUMPLE, RITA!", tema="meta", dur=21.0, sig=None, premio="🎂",
         moves=[(0, 7.0, 400), (7.0, 21.0, 0)], props_rel=[(7.0, "torta")], frog=("rita_meta", 7.0), festejo=7.2,
         dice=[(0.3, 2.8, "lolo", "¡Ya llego! ¡Ya llego! 🎈"),
               (7.4, 10.0, "lolo", "¡Sorpresa! ¡Feliz cumpleaños, Rita! 🌸"),
               (10.2, 13.0, "rita", "¡Gracias, Lolo! ¡Es la flor más linda! 🐸"),
               (13.2, 16.6, "lolo", "¡Los amigos son el mejor regalo! 💛")]),
]
for e in EPIS2:
    e["pref"] = "lolo_cumple_parte"
    e["etiqueta"] = f"EL CUMPLE DE RITA · PARTE {e['n']}"



# ================================================================= historias nuevas cada día (generador)
MISIONES = [
    ("LA FLOR PARA MAMÁ", "flor", "🌸", "¡Hola! Hoy quiero sorprender a mamá. 💛", "¡Voy a buscarle una flor!",
     "¡Encontré la flor más linda! 🌸", "¡Dar con amor nos hace felices! 💛"),
    ("LA TORTA ESCONDIDA", "torta", "🎂", "¡Mmm! ¿Huelen eso? 🎂", "¡Hay una torta por aquí cerca!",
     "¡La encontré! ¡La voy a compartir!", "¡Compartir es lo más dulce! 🍰"),
    ("EL HONGO GIGANTE", "hongo", "🍄", "Dicen que hay un hongo gigante...", "¡Vamos a buscarlo juntos!",
     "¡Wow! ¡Es enorme! 🍄", "¡Explorar es una gran aventura! ✨"),
    ("LA GRAN CARRERA", "meta", "🏆", "¡Hoy es la gran carrera! 🏁", "¿Me ayudas a llegar a la meta?",
     "¡LLEGUÉ! ¡LO LOGRÉ! 🏆", "¡Si lo intentas, lo logras! 💪"),
    ("CONTAMOS HASTA TRES", "meta", "⭐", "¡Hoy vamos a contar juntos! 🔢", "¡Cada salto es un número!",
     "¡Contamos hasta tres! ⭐", "¡Qué bien cuentas! ¡Bravo! 👏"),
    ("EL TESORO DEL CAMINO", "flor", "💎", "¡Encontré un mapa del tesoro! 🗺️", "¡Sigamos el camino!",
     "¡El tesoro! ¡Una flor brillante! 💎", "¡La aventura es el mejor tesoro! ✨"),
    ("LA FIESTA SORPRESA", "torta", "🎉", "¡Shhh! Hoy hay fiesta sorpresa. 🎉", "¡Tengo que llegar a tiempo!",
     "¡Sorpresa! ¡Llegué a la fiesta! 🎈", "¡Con amigos todo es más lindo! 💛"),
    ("NO ME RINDO", "meta", "💪", "Hoy el camino es difícil...", "¡Pero yo no me rindo!",
     "¡Lo logré paso a paso! 💪", "¡Nunca te rindas! ⭐"),
]
OBS_TXT = {"tronco": "¡Hop! ¡Un tronco!", "piedra": "¡Una piedra! ¡Salto!", "conos": "¡Conos! ¡Arriba!",
           "piedrita": "¡Hop! ¡Qué fácil!"}
TEMAS_DIA = ["bosque", "montana", "casa", "meta"]


def historia_del_dia(fecha=None):
    import datetime as dt
    fecha = fecha or dt.date.today()
    k = fecha.toordinal()
    r = random.Random(k)
    tit, goal, premio, i1, i2, hall, moral = MISIONES[k % len(MISIONES)]
    tema = TEMAS_DIA[(k + k // len(MISIONES)) % len(TEMAS_DIA)]
    amiga = r.random() < 0.5
    obs = [r.choice(list(OBS_TXT)) for _ in range(3)]
    contar = tit.startswith("CONTAMOS")
    if contar:
        saltos = [(6.6, obs[0]), (8.4, obs[1]), (10.2, obs[2])]
        dice = [(6.6, 7.9, "lolo", "¡UNO! ☝️"), (8.4, 9.7, "lolo", "¡DOS! ✌️"), (10.2, 11.7, "lolo", "¡TRES! 🎉")]
    else:
        saltos = [(7.0, obs[0]), (9.8, obs[1])]
        dice = [(6.0, 8.4, "lolo", OBS_TXT[obs[0]]),
                (9.0, 11.6, "lolo", r.choice(["¡Nada me detiene! 💪", "¡Casi llego!", "¡Qué divertido! 😄"]))]
    dice = [(0.3, 2.9, "lolo", i1), (3.1, 5.5, "lolo", i2)] + dice + [
        (12.4, 14.9, "lolo", hall), (15.1, 17.5, "rita" if amiga else "lolo", moral)]
    ep = dict(n=k % 6 + 1, titulo=tit, tema=tema, dur=20.0, sig=None, premio=premio,
              moves=[(0, 5.6, 0), (5.6, 12.0, 340), (12.0, 20.0, 0)], saltos=saltos,
              props_rel=[(12.0, goal)], festejo=12.2, dice=dice,
              pref=f"lolo_{fecha.isoformat()}_", etiqueta="UNA NUEVA AVENTURA")
    if amiga:
        ep["frog"] = ("rita_meta", 12.0)
    return ep


def nuevo(dest, log=print, fecha=None):
    """Arma el short del día y lo deja en la cola de subida (publicar.json) del canal infantil."""
    import json
    global OUT
    OUT = dest
    os.makedirs(dest, exist_ok=True)
    ep = historia_del_dia(fecha)
    log(f"• Lolo: «{ep['titulo']}» ({ep['tema']})… (tarda unos minutos)")
    render(ep)
    arch = f"{ep['pref']}{ep['n']}.mp4"
    t = ep["titulo"].capitalize()
    pj = os.path.join(dest, "publicar.json")
    items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
    items = [i for i in items if i["archivo"] != arch] + [{
        "archivo": arch, "tipo": "short", "ninos": True, "categoria": "1",
        "titulo": f"{t} 🦆 | {__import__('autocanal.paths', fromlist=['cfg']).cfg()['infantil_canal']} #shorts"[:100],
        "descripcion": f"{t}: una nueva aventura de Lolo, el patito de hule más valiente. 🦆\n\n"
                       "🦆 Suscríbete: ¡hay una aventura nueva de Lolo todos los días!\n\n"
                       "#CuentosInfantiles #Patito #DibujosAnimados #Shorts",
        "tags": ["lolo el patito", "cuentos infantiles", "dibujos animados", "patito", "historias para niños",
                 "videos para niños"]}]
    json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"✓ Listo: {os.path.join(dest, arch)}")
    return arch


# ================================================================= historias desde un .md (secuencias de N shorts)
OBJ_TXT = {"flor": "la flor mágica", "torta": "una torta deliciosa", "hongo": "el hongo gigante", "meta": "la meta"}
OBJ_PREMIO = {"flor": "🌸", "torta": "🎂", "hongo": "🍄", "meta": "🏆"}
CLAVES_OBJ = {"flor": ["flor", "regalo", "tesoro"], "torta": ["torta", "pastel", "cumple", "fiesta"],
              "hongo": ["hongo", "seta"], "meta": ["carrera", "meta", "llegar", "competencia"]}
ESC = {"casa": "casa", "bosque": "bosque", "montaña": "montana", "montana": "montana", "meta": "meta",
       "pradera": "meta", "campo": "meta", "rio": "bosque", "río": "bosque", "lago": "casa"}
TIT_MEDIO = ["EN CAMINO", "UN NUEVO DESAFÍO", "SIN RENDIRSE", "¡QUÉ AVENTURA!", "MÁS ALLÁ DEL BOSQUE",
             "EL GRAN SALTO", "PASO A PASO", "¡NO ME DETENGO!"]
L_INICIO = ["¡Seguimos la aventura! 🦆", "¡Hola de nuevo, amigos! 👋", "¡Vamos, que falta poco!", "¡Aquí estoy otra vez!"]
L_FIN = ["¿Qué pasará después? 🤔", "¡Mañana seguimos! 💪", "¡Uf! ¡Qué camino!", "¡Ya falta menos!"]


import re


def leer_historia(path, cantidad=None):
    """Lee un .md: puede ser un guion con campos (ver historias/EJEMPLO.md) o un texto libre.
    Campos: '# Título', 'cantidad:', 'objetivo:', 'mision:', 'moraleja:', 'amiga:', 'escenarios:',
    y secciones '## Parte N: Título' con 'escenario:', 'obstaculos:' y líneas 'lolo: …' / 'rita: …'."""
    txt = re.sub(r"<!--.*?-->", "", open(os.path.expanduser(path), encoding="utf-8").read(), flags=re.S)
    h = {"partes": {}}
    cur = None
    for ln in txt.splitlines():
        s = ln.strip()
        m = re.match(r"^##\s*(?:parte|cap[ií]tulo|short)?\s*(\d+)\s*[:.\-–]?\s*(.*)$", s, re.I)
        if m:
            cur = h["partes"].setdefault(int(m.group(1)), {"dice": []})
            if m.group(2):
                cur["titulo"] = m.group(2).strip()
            continue
        if s.startswith("# ") and "titulo" not in h:
            h["titulo"] = s[2:].strip()
            continue
        m = re.match(r"^[-*]?\s*(lolo|rita)\s*:\s*(.+)$", s, re.I)
        if m and cur is not None:
            cur["dice"].append((m.group(1).lower(), m.group(2).strip()))
            continue
        m = re.match(r"^[-*]?\s*([a-záéíóúñ ]+?)\s*:\s*(.+)$", s, re.I)
        if m:
            k = m.group(1).lower().replace("ó", "o").replace("í", "i").replace("á", "a").strip()
            (cur if cur is not None else h)[k] = m.group(2).strip()
    low = txt.lower()
    if not h.get("titulo"):
        h["titulo"] = next((l.strip("# ").strip() for l in txt.splitlines() if l.strip()), "Una aventura de Lolo")
    n = cantidad or h.get("cantidad")
    if not n:
        m = re.search(r"(\d+)\s*(?:shorts?|partes?|cap[ií]tulos?|videos?|episodios?)", low)
        n = m.group(1) if m else (max(h["partes"]) if h["partes"] else 3)
    h["cantidad"] = max(1, min(int(n), 20))
    obj = (h.get("objetivo") or "").lower()
    if obj not in OBJ_TXT:
        obj = next((o for o, ks in CLAVES_OBJ.items() if any(k in (obj or low) for k in ks)), "meta")
    h["objetivo"] = obj
    if len(h["titulo"]) > 38 or not h["titulo"]:
        h["titulo"] = {"flor": "La flor mágica", "torta": "La torta de la fiesta", "hongo": "El hongo gigante",
                       "meta": "La gran carrera"}[obj]
    h["amiga"] = (h.get("amiga", "").lower().startswith(("s", "y")) if "amiga" in h else "rita" in low)
    return h


def episodios_de(h):
    import re, unicodedata
    N, obj = h["cantidad"], h["objetivo"]
    slug = re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", h["titulo"].lower()).encode("ascii", "ignore").decode()).strip("_")[:30]
    escs = [ESC.get(e.strip().lower(), "bosque") for e in h.get("escenarios", "").split(",") if e.strip()] or \
           (["casa", "bosque", "montana"] + ["bosque", "montana"] * 9)[:max(1, N - 1)] + ["meta"]
    r = random.Random(h["titulo"])
    tits = []
    for k in range(1, N + 1):
        p = h["partes"].get(k, {})
        if p.get("titulo"):
            tits.append(p["titulo"].upper())
        elif k == 1:
            tits.append(h["titulo"].upper())
        elif k == N:
            tits.append("¡LO LOGRAMOS!")
        else:
            tits.append(TIT_MEDIO[(k - 2) % len(TIT_MEDIO)])
    eps = []
    for k in range(1, N + 1):
        p = h["partes"].get(k, {})
        ultimo = k == N
        tema = ESC.get(p.get("escenario", "").lower(), None) or escs[min(k - 1, len(escs) - 1)]
        obs = [o.strip().lower() for o in p.get("obstaculos", "").split(",") if o.strip().lower() in OBS_TXT] or \
              [r.choice(list(OBS_TXT)) for _ in range(2)]
        obs = (obs * 2)[:2]
        lolo_l = [t for w, t in p.get("dice", []) if w == "lolo"]
        rita_l = [t for w, t in p.get("dice", []) if w == "rita"]
        if k == 1:
            base = ["¡Hola! Soy Lolo, un patito de hule. 🦆", h.get("mision") or f"¡Hoy voy a buscar {OBJ_TXT[obj]}! {OBJ_PREMIO[obj]}"]
        else:
            base = [r.choice(L_INICIO), "¡Tengo que llegar a la meta! 🏁" if obj == "meta" else f"¡Tengo que encontrar {OBJ_TXT[obj]}! {OBJ_PREMIO[obj]}"]
        fin = ([f"¡Lo logré! ¡{OBJ_TXT[obj][0].upper() + OBJ_TXT[obj][1:]}! {OBJ_PREMIO[obj]}", h.get("moraleja") or "¡Nunca te rindas! ⭐"]
               if ultimo else [r.choice(L_FIN[1:]), "¿Qué pasará después? 🤔"])
        lin = (lolo_l + base + fin)[:4] if lolo_l else base + fin
        if len(lolo_l) in (1, 2):
            lin = lolo_l + base[len(lolo_l):] + fin
        if len(lolo_l) >= 3:
            lin = (lolo_l + fin)[:4]
        quien = ["lolo"] * 4
        amiga_aqui = bool(rita_l) or (ultimo and h["amiga"])
        if rita_l:
            lin[3] = rita_l[0]
            quien[3] = "rita"
            if len(rita_l) > 1:
                lin[2], quien[2] = rita_l[1], "rita"
        elif ultimo and h["amiga"]:
            quien[3] = "rita"
        dice = [(0.3, 2.9, quien[0], lin[0]), (3.1, 5.5, quien[1], lin[1]),
                (6.0, 8.4, "lolo", OBS_TXT[obs[0]]),
                (9.0, 11.6, "lolo", r.choice(["¡Nada me detiene! 💪", "¡Qué divertido! 😄", "¡Otra vez! ¡Hop!"])),
                (12.4, 14.9, quien[2], lin[2]), (15.1, 17.5, quien[3], lin[3])]
        ep = dict(n=k, titulo=tits[k - 1], tema=tema, dur=20.0,
                  sig=None if ultimo else f"Parte {k + 1}: {tits[k].capitalize()}",
                  moves=[(0, 5.6, 0), (5.6, 12.0, 340), (12.0, 20.0, 0)], saltos=[(7.0, obs[0]), (9.8, obs[1])],
                  dice=dice, pref=f"lolo_{slug}_parte", etiqueta=f"{h['titulo'].upper()} · PARTE {k}")
        if ultimo:
            ep.update(props_rel=[(12.0, obj)], festejo=12.2, premio=h.get("premio") or OBJ_PREMIO[obj])
        if amiga_aqui:
            ep["frog"] = ("rita_meta", 12.0)
        eps.append(ep)
    return eps


def desde_md(path, dest, cantidad=None, log=print):
    import json
    global OUT
    OUT = dest
    os.makedirs(dest, exist_ok=True)
    h = leer_historia(path, cantidad)
    eps = episodios_de(h)
    log(f"• Lolo: «{h['titulo']}» en {len(eps)} shorts (objetivo: {h['objetivo']}). Unos 2 min por short…")
    pj = os.path.join(dest, "publicar.json")
    items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
    N = len(eps)
    for ep in eps:
        log(f"  Parte {ep['n']}/{N}: {ep['titulo']}")
        render(ep)
        arch = f"{ep['pref']}{ep['n']}.mp4"
        sig = f"\n\n👉 Sigue la historia en la {ep['sig']}." if ep["sig"] else "\n\n⭐ ¡Fin de la historia!"
        items = [i for i in items if i["archivo"] != arch] + [{
            "archivo": arch, "tipo": "short", "ninos": True, "categoria": "1",
            "titulo": f"{ep['titulo'].capitalize()} 🦆 {h['titulo']} · Parte {ep['n']} #shorts"[:100],
            "descripcion": f"{h['titulo']} · Parte {ep['n']} de {N}: una aventura de Lolo, el patito de hule.{sig}\n"
                           "🦆 Suscríbete para ver todas las aventuras de Lolo.\n\n"
                           "#CuentosInfantiles #Patito #DibujosAnimados #Shorts",
            "tags": ["lolo el patito", "cuentos infantiles", "dibujos animados", "patito", "historias para niños"]}]
        json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"✓ {N} shorts listos en {dest}")
