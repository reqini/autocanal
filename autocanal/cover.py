#!/usr/bin/env python3
"""Portada 1080x1920 con la marca del canal (config.json → marca).

cover.py FRAME.jpg CENTRO_X OUT.jpg "ETIQUETA" "LINEA1" "LINEA2" ["LINEA3"] ["TAG"] [COLOR_ETIQUETA]
  CENTRO_X: centro horizontal del recorte en el frame original (px de 1920).
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .paths import FD
W, H, IMG_H = 1080, 1920, 1380
YEL, CEL, NAVY, WHITE = (255, 212, 0), (108, 172, 228), (8, 16, 38), (255, 255, 255)
LABEL_COLORS = {"red": (226, 35, 26), "yel": YEL, "cel": CEL, "orange": (255, 122, 0)}


def font(name, size, var=None):
    f = ImageFont.truetype(FD + name, size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


def fit(d, text, name, maxw, start, var=None):
    s = start
    while s > 20:
        f = font(name, s, var)
        if d.textlength(text, font=f) <= maxw:
            return f
        s -= 4
    return font(name, s, var)


def make(frame, cx, out, label, l1, l2, l3="", tag="", lcol="red"):
    src = Image.open(frame).convert("RGB")
    sw, sh = src.size
    top = int(sh * 0.10)  # saca la placa del marcador
    ch = sh - top
    cw = int(ch * W / IMG_H)
    x0 = max(0, min(sw - cw, int(cx * sw / 1920 - cw / 2)))
    img = src.crop((x0, top, x0 + cw, sh)).resize((W, IMG_H), Image.LANCZOS)

    canvas = Image.new("RGB", (W, H), NAVY)
    canvas.paste(img, (0, 0))
    # degradé inferior hacia el azul del canal + viñeta superior
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        a = 0
        if y > 760:
            a = min(255, int(255 * ((y - 760) / (IMG_H - 760)) ** 1.4))
        if y < 220:
            a = max(a, int(150 * (1 - y / 220)))
        grad.putpixel((0, y), a)
    canvas = Image.composite(Image.new("RGB", (W, H), NAVY), canvas, grad.resize((W, H)))

    # franjas de marca abajo a la derecha
    st = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    for x0s, w, col, al in [(1180, 46, CEL, 140), (1240, 16, YEL, 230), (1080, 10, WHITE, 60)]:
        sd.polygon([(x0s, 1500), (x0s + w, 1500), (x0s + w - 420 * 0.55, 1920), (x0s - 420 * 0.55, 1920)],
                   fill=col + (al,))
    canvas.paste(st, (0, 0), st)

    d = ImageDraw.Draw(canvas)
    # marca del canal arriba
    fb = font("Oswald.ttf", 38, "SemiBold")
    from .paths import cfg
    brand = cfg().get("marca", "MI CANAL").upper()
    acc = brand.split()[-1]
    bw = d.textlength(brand, font=fb)
    d.rounded_rectangle((W / 2 - bw / 2 - 26, 64, W / 2 + bw / 2 + 26, 124), radius=30, fill=(8, 16, 38, 220))
    d.text((W / 2 - bw / 2, 68), brand[:-len(acc)], font=fb, fill=WHITE)
    d.text((W / 2 - bw / 2 + d.textlength(brand[:-len(acc)], font=fb), 68), acc, font=fb, fill=YEL)

    # bloque de texto
    y = 1150
    fl = font("Oswald.ttf", 46, "Bold")
    lw = d.textlength(label, font=fl)
    lc = LABEL_COLORS.get(lcol, LABEL_COLORS["red"])
    d.rounded_rectangle((60, y, 60 + lw + 48, y + 72), radius=10, fill=lc)
    d.text((84, y + 4), label, font=fl, fill=NAVY if lcol in ("yel", "cel") else WHITE)
    y += 96

    def big(text, size, col, y):
        f = fit(d, text, "Anton-Regular.ttf", W - 120, size)
        bb = d.textbbox((0, 0), text, font=f)
        sh_ = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh_).text((66, y - bb[1] + 8), text, font=f, fill=(0, 0, 0, 200))
        sh_ = sh_.filter(ImageFilter.GaussianBlur(8))
        canvas.paste(sh_, (0, 0), sh_)
        ImageDraw.Draw(canvas).text((60, y - bb[1]), text, font=f, fill=col, stroke_width=4, stroke_fill=(0, 0, 0))
        return y + (bb[3] - bb[1]) + 26

    y = big(l1, 150, WHITE, y)
    y = big(l2, 210, YEL, y)
    d = ImageDraw.Draw(canvas)
    if l3:
        f3 = fit(d, l3, "Oswald.ttf", W - 120, 64, "SemiBold")
        d.text((60, y), l3, font=f3, fill=WHITE)
        y += 84
    if tag:
        ft = fit(d, tag, "Oswald.ttf", W - 160, 44, "Medium")
        tw = d.textlength(tag, font=ft)
        ty = max(y + 6, 1790)
        d.rectangle((60, ty + 8, 66, ty + 52), fill=YEL)
        d.text((84, ty), tag, font=ft, fill=CEL)
    canvas.save(out, quality=92)


if __name__ == "__main__":
    a = sys.argv[1:]
    make(a[0], float(a[1]), a[2], a[3], a[4], a[5], *a[6:])
