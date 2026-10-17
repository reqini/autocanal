"""Cierre animado "¿Te gustó? · Me gusta · Suscribite · @tucanal" generado con tu marca (config.json).
Se crea solo la primera vez en assets/outro/ (78 cuadros PNG transparentes + sonido)."""
import math, os, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .paths import FD, OUTRO, cfg

W, H, N, SR = 1080, 1920, 78, 44100
YEL, DARK, NAVY = (255, 214, 10), (70, 72, 80), (8, 16, 38)


def _f(name, size):
    return ImageFont.truetype(FD + name, size)


def _pop(t, t0, d=0.35):
    """Escala con rebote: 0 antes de t0, ~1.15 a mitad, 1 al final."""
    if t < t0:
        return 0.0
    u = min(1.0, (t - t0) / d)
    return u * (1 + 0.25 * math.sin(u * math.pi))


def _pastilla(texto, fondo, color, w=640, h=150):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=fondo)
    f = _f("Anton-Regular.ttf", 78)
    tw = d.textlength(texto, font=f)
    d.text(((w - tw) / 2, h / 2 - 50), texto, font=f, fill=color)
    return im


def _pegar(base, im, cx, cy, s):
    if s <= 0.02:
        return
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def asegurar():
    fr = os.path.join(OUTRO, "frames")
    if os.path.exists(os.path.join(fr, f"f{N - 1:03d}.png")) and os.path.exists(os.path.join(OUTRO, "pops.wav")):
        return
    os.makedirs(fr, exist_ok=True)
    handle = cfg().get("handle", "@MiCanal")
    tit = Image.new("RGBA", (1000, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(tit)
    f = _f("Anton-Regular.ttf", 190)
    tw = d.textlength("¿TE GUSTÓ?", font=f)
    d.text(((1000 - tw) / 2, 0), "¿TE GUSTÓ?", font=f, fill=(255, 255, 255), stroke_width=10, stroke_fill=(0, 0, 0))
    like = _pastilla("👍 ME GUSTA"[2:], YEL, NAVY)
    sub = _pastilla("SUSCRIBITE", (220, 30, 40), (255, 255, 255))
    subd = _pastilla("SUSCRIPTO ✓"[:-2], DARK, (255, 255, 255))
    han = Image.new("RGBA", (1000, 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(han)
    fh = _f("Oswald.ttf", 64)
    hw = d.textlength(handle, font=fh)
    d.text(((1000 - hw) / 2, 0), handle, font=fh, fill=(120, 180, 240), stroke_width=3, stroke_fill=(0, 0, 0))
    for i in range(N):
        t = i / 30
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _pegar(im, tit, W / 2, 700, _pop(t, 0.0))
        _pegar(im, like, W / 2, 980, _pop(t, 0.5))
        _pegar(im, subd if t > 1.6 else sub, W / 2, 1220, _pop(t, 0.9))
        _pegar(im, han, W / 2, 1520, _pop(t, 1.3))
        im.save(os.path.join(fr, f"f{i:03d}.png"))
    a = np.zeros(int(SR * 2.8), np.float32)
    for t0 in (0.0, 0.5, 0.9, 1.6):
        tt = np.arange(int(SR * 0.12)) / SR
        s = np.sin(2 * np.pi * (900 - 2500 * tt) * tt) * np.exp(-tt * 45) * 0.5
        i0 = int(t0 * SR)
        a[i0:i0 + len(s)] += s
    with wave.open(os.path.join(OUTRO, "pops.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
