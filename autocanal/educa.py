"""Videos educativos infantiles: letras y números con ojitos, brazos y piernas que bailan, con voz y música.
Formato "aprendé las vocales / los números / el abecedario" (2D, colores planos, fondo de cielo y pasto).
Personajes y canción propios: la voz la pone la Mac (comando `say`), la música se genera acá.

    atr lolo aprende vocales            video horizontal (~1 min) + short vertical
    atr lolo aprende numeros | abecedario
"""
import math, os, random, re, shutil, subprocess, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from . import lolo as L

FPS, SR = 24, 44100
NAVY = (28, 36, 84)
COLS = [(239, 59, 54), (255, 153, 0), (250, 204, 21), (34, 197, 94), (14, 165, 233), (124, 58, 237), (236, 72, 153)]

TEMAS = {
    "vocales": dict(titulo="¡APRENDE LAS VOCALES!", hola="¡Hola, amigos! ¡Vamos a aprender las vocales!",
                    chau="¡Muy bien! ¡Ya sabes las vocales!", items=[
                        ("A", "abeja", "🐝"), ("E", "elefante", "🐘"), ("I", "iguana", "🦎"), ("O", "oso", "🐻"),
                        ("U", "uvas", "🍇")]),
    "numeros": dict(titulo="¡APRENDE A CONTAR!", hola="¡Hola, amigos! ¡Vamos a contar del uno al diez!",
                    chau="¡Excelente! ¡Ya sabes contar hasta diez!", items=[
                        ("1", "uno", "🍎"), ("2", "dos", "⭐"), ("3", "tres", "🐟"), ("4", "cuatro", "🌸"),
                        ("5", "cinco", "🎈"), ("6", "seis", "🍓"), ("7", "siete", "🐞"), ("8", "ocho", "🍪"),
                        ("9", "nueve", "🦋"), ("10", "diez", "🍌")]),
    "letras": dict(titulo="¡APRENDE LAS LETRAS!", hola="¡Hola, amigos! ¡Vamos a aprender las letras!",
                   chau="¡Muy bien! ¡Ya conoces las letras!", items=[
                       ("A", "abeja", "🐝"), ("B", "ballena", "🐋"), ("C", "casa", "🏠"), ("D", "dado", "🎲"),
                       ("E", "elefante", "🐘")]),
    "colores": dict(titulo="¡APRENDE LOS COLORES!", hola="¡Hola, amigos! ¡Vamos a aprender los colores!",
                    chau="¡Excelente! ¡Ya sabes los colores!", items=[
                        ("ROJO", "manzana", "🍎"), ("AZUL", "ballena", "🐳"), ("AMARILLO", "banana", "🍌"),
                        ("VERDE", "rana", "🐸"), ("NARANJA", "naranja", "🍊")]),
    "abecedario": dict(titulo="¡EL ABECEDARIO!", hola="¡Hola, amigos! ¡Vamos a aprender el abecedario!",
                       chau="¡Bravo! ¡Ya sabes todo el abecedario!", items=[
                           ("A", "abeja", "🐝"), ("B", "ballena", "🐋"), ("C", "casa", "🏠"), ("D", "dado", "🎲"),
                           ("E", "elefante", "🐘"), ("F", "foca", "🦭"), ("G", "gato", "🐱"), ("H", "helado", "🍦"),
                           ("I", "iguana", "🦎"), ("J", "jirafa", "🦒"), ("K", "kiwi", "🥝"), ("L", "león", "🦁"),
                           ("M", "mono", "🐵"), ("N", "nube", "☁️"), ("Ñ", "ñu", "🐃"), ("O", "oso", "🐻"),
                           ("P", "pato", "🦆"), ("Q", "queso", "🧀"), ("R", "ratón", "🐭"), ("S", "sol", "🌞"),
                           ("T", "tortuga", "🐢"), ("U", "uvas", "🍇"), ("V", "vaca", "🐮"), ("W", "waffle", "🧇"),
                           ("X", "xilófono", "🎹"), ("Y", "yoyó", "🪀"), ("Z", "zorro", "🦊")]),
}


# ------------------------------------------------------------------ voz
def _voz_mac():
    if not shutil.which("say"):
        return None
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout.splitlines()
    except Exception:
        return None
    for loc in ("es_MX", "es_US", "es_AR", "es_ES"):
        cand = [l for l in out if loc in l]
        if cand:
            best = next((l for l in cand if re.search(r"premium|enhanced|mejorad", l, re.I)), cand[0])
            return re.split(r" {2,}", best.strip())[0]
    return None


def hablar(texto, path):
    """Graba `texto` con la voz de la Mac (WAV mono). Devuelve la duración, o None si no hay voz."""
    v = _voz_mac()
    if not v:
        return None
    aiff = path + ".aiff"
    subprocess.run(["say", "-v", v, "-r", "165", "-o", aiff, texto], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", aiff, "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,asetrate=44100*1.06,aresample=44100",
                    "-ac", "1", "-ar", str(SR), path], check=True)
    os.remove(aiff)
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def _leer(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return x


# ------------------------------------------------------------------ dibujo
def fondo(W, H, seed=3):
    r = random.Random(seed)
    g = np.linspace(0, 1, H)[:, None]
    top, bot = np.array((110, 196, 255)), np.array((200, 236, 255))
    im = Image.fromarray(np.repeat((top * (1 - g) + bot * g)[:, None, :], W, 1).astype(np.uint8)).convert("RGBA")
    S = 2
    big = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    gy = int(H * 0.74) * S
    d.ellipse((-W * S * 0.2, gy - H * S * 0.16, W * S * 0.7, gy + H * S * 0.3), fill=(132, 214, 112))
    d.ellipse((W * S * 0.45, gy - H * S * 0.12, W * S * 1.3, gy + H * S * 0.3), fill=(120, 204, 100))
    d.rectangle((0, gy, W * S, H * S), fill=(104, 196, 84))
    d.rectangle((0, gy, W * S, gy + 10 * S), fill=(88, 176, 70))
    for _ in range(int(W / 30)):  # florcitas
        x, y = r.uniform(0, W * S), r.uniform(gy + 30 * S, H * S)
        c = r.choice([(255, 255, 255), (255, 214, 10), (255, 120, 170)])
        d.ellipse((x - 7 * S, y - 7 * S, x + 7 * S, y + 7 * S), fill=c)
    tx = W * S * 0.07  # árbol
    d.rectangle((tx - 22 * S, gy - 170 * S, tx + 22 * S, gy + 10 * S), fill=(130, 84, 50))
    for dx, dy, rr in [(0, -230, 110), (-80, -180, 80), (80, -180, 80), (0, -320, 85)]:
        d.ellipse((tx + (dx - rr) * S, gy + (dy - rr) * S, tx + (dx + rr) * S, gy + (dy + rr) * S), fill=(46, 160, 68))
    sx, sy, sr = W * S * 0.9, H * S * 0.14, H * S * 0.07  # sol
    for k in range(12):
        a = k * math.pi / 6
        d.line((sx + math.cos(a) * sr * 1.3, sy + math.sin(a) * sr * 1.3, sx + math.cos(a) * sr * 1.8,
                sy + math.sin(a) * sr * 1.8), fill=(255, 200, 40), width=8 * S)
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 214, 40))
    im.alpha_composite(big.resize((W, H), Image.LANCZOS))
    return im


_GLY = {}


def glifo(ch, alto, color):
    """La letra/número como 'cuerpo' del personaje (relleno de color, borde oscuro, brillo)."""
    k = (ch, alto, color)
    if k not in _GLY:
        f = L.F("Anton-Regular.ttf", int(alto * 1.25))
        tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
        bb = tmp.textbbox((0, 0), ch, font=f, stroke_width=16)
        w, h = bb[2] - bb[0] + 20, bb[3] - bb[1] + 20
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.text((10 - bb[0], 10 - bb[1]), ch, font=f, fill=color + (255,), stroke_width=16, stroke_fill=NAVY + (255,))
        hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(hl).text((10 - bb[0] - 10, 10 - bb[1] - 12), ch, font=f, fill=(255, 255, 255, 70))
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).text((10 - bb[0], 10 - bb[1]), ch, font=f, fill=255)
        im.alpha_composite(Image.composite(hl, Image.new("RGBA", (w, h), (0, 0, 0, 0)), mask.filter(ImageFilter.MinFilter(9))))
        _GLY[k] = im
    return _GLY[k]


def personaje(base, ch, cx, piso, alto, color, t, fase=0.0, hablando=False, feliz=1.0):
    """Dibuja la letra con piernas, brazos que se mueven, ojos que miran y parpadean, y boca."""
    g = glifo(ch, alto, color)
    rebote = abs(math.sin((t + fase) * math.pi * 2.2))
    sy = 1 - 0.05 * (1 - rebote)
    gw, gh = g.width, int(g.height * sy)
    gi = g.resize((gw, gh), Image.BILINEAR) if sy != 1 else g
    pierna = alto * 0.16
    top = piso - pierna - gh - rebote * alto * 0.08
    d = ImageDraw.Draw(base)
    lw = max(6, int(alto * 0.03))
    # piernas y zapatitos
    for s in (-1, 1):
        x0 = cx + s * gw * 0.18
        d.line((x0, top + gh - 10, x0 + s * 6, piso - 10), fill=NAVY, width=lw)
        d.ellipse((x0 + s * 6 - alto * 0.07, piso - 22, x0 + s * 6 + alto * 0.07, piso + 4), fill=NAVY)
    # brazos (saludan / bailan)
    for s in (-1, 1):
        sh = (cx + s * gw * 0.42, top + gh * 0.5)
        a = -0.5 + 0.9 * math.sin((t + fase) * 5 + (0 if s < 0 else math.pi))
        ln = alto * 0.42
        hx, hy = sh[0] + s * ln * math.cos(a), sh[1] - ln * math.sin(a)
        d.line((sh[0], sh[1], hx, hy), fill=NAVY, width=lw)
        d.ellipse((hx - lw * 1.4, hy - lw * 1.4, hx + lw * 1.4, hy + lw * 1.4), fill=NAVY)
    base.alpha_composite(gi, (int(cx - gw / 2), int(top)))
    # ojos saltones (encima de la letra, como en los dibujos infantiles)
    er = alto * 0.11
    ey = top + er * 0.6
    blink = ((t + fase * 3) % 3.4) < 0.13
    mira = math.sin((t + fase) * 0.9) * er * 0.35
    for s in (-1, 1):
        ex = cx + s * er * 1.05
        if blink:
            d.line((ex - er, ey, ex + er, ey), fill=NAVY, width=lw)
            continue
        d.ellipse((ex - er, ey - er * 1.1, ex + er, ey + er * 1.1), fill=(255, 255, 255), outline=NAVY, width=max(3, lw // 2))
        pr = er * 0.48
        d.ellipse((ex + mira - pr, ey - pr + er * 0.1, ex + mira + pr, ey + pr + er * 0.1), fill=(20, 20, 30))
        d.ellipse((ex + mira - pr * 0.35, ey - pr * 0.6, ex + mira + pr * 0.05, ey - pr * 0.2), fill=(255, 255, 255))
        for k in (-1, 0, 1):  # pestañas
            d.line((ex + k * er * 0.5, ey - er * 1.05, ex + k * er * 0.7, ey - er * 1.45), fill=NAVY, width=max(3, lw // 2))
    # boca: sonrisa, o abierta cuando habla
    my = top + gh * 0.62
    mw = gw * 0.22
    if hablando and math.sin(t * 22) > -0.2:
        o = alto * 0.05 * (0.6 + 0.4 * abs(math.sin(t * 17)))
        d.ellipse((cx - mw * 0.45, my - o, cx + mw * 0.45, my + o * 1.6), fill=(120, 20, 40), outline=NAVY, width=4)
    else:
        d.arc((cx - mw, my - mw * 0.9 * feliz, cx + mw, my + mw * 0.6), 20, 160, fill=NAVY, width=lw)


def emoji(base, ch, cx, cy, size):
    L.emoji_at(base, ch, cx - size / 2, cy - size / 2, size)


def texto(base, s, cx, y, size, fill, stroke=8):
    f = L.F("Anton-Regular.ttf", size)
    d = ImageDraw.Draw(base)
    w = d.textlength(s, font=f)
    d.text((cx - w / 2, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=NAVY)


def ease(u):
    u = max(0.0, min(1.0, u))
    return 1 - (1 - u) ** 3


# ------------------------------------------------------------------ guion, audio y render
def guion(tema, tmp):
    """Arma las frases y sus tiempos. Con voz de la Mac usa la duración real; sin voz, tiempos fijos."""
    T = TEMAS[tema]
    frases = [("intro", T["hola"])]
    for ch, pal, _ in T["items"]:
        if tema == "numeros":
            frases += [(ch, f"¡El {pal}!"), (ch, f"¡{pal.capitalize()}!")]
        else:
            frases += [(ch, f"¡La {ch.lower()}!"), (ch, f"{ch.lower()}... de {pal}.")]
    frases.append(("final", T["chau"]))
    t, out = 0.6, []
    for i, (k, s) in enumerate(frases):
        p = os.path.join(tmp, f"v{i}.wav")
        dur = hablar(s, p)
        if dur is None:
            p, dur = None, max(1.2, len(s) / 13)
        out.append(dict(clave=k, texto=s, t=t, dur=dur, wav=p))
        t += dur + (0.9 if k in ("intro", "final") else 0.55)
    return out, t + 2.5


def musica(D, path, voces, sfx=()):
    a = np.zeros(int(SR * D) + SR, np.float32)
    bpm = 112
    b = 60 / bpm
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    prog = [(60, 64, 67), (65, 69, 72), (67, 71, 74), (60, 64, 67)]
    mel = [72, 74, 76, 72, 76, 77, 79, 79, 77, 76, 74, 72, 74, 76, 72, 67]
    for k in range(int(D / b)):
        t0 = k * b
        ch = prog[(k // 4) % 4]
        L.add(a, L.tone(hz(ch[0] - 24), b * 0.9, "sine", 0.18, 3), t0)  # bajo
        if k % 2 == 1:
            for m in ch:
                L.add(a, L.tone(hz(m), b * 0.5, "tri", 0.035, 6), t0)
        L.add(a, L.tone(hz(mel[k % len(mel)]), b * 0.8, "sq", 0.03, 5), t0)  # melodía alegre
        nz = np.random.default_rng(k).standard_normal(int(SR * 0.04))
        L.add(a, nz * np.exp(-np.arange(len(nz)) / SR * 90) * 0.04, t0 + b / 2)  # platillo
    v = np.zeros_like(a)
    for f in voces:
        if f["wav"]:
            x = _leer(f["wav"])
            L.add(v, x / max(1e-6, np.abs(x).max()) * 0.9, f["t"])
        else:  # sin voz: "canto" de burbujitas
            for j in range(int(f["dur"] / 0.16)):
                L.add(v, L.tone(hz(76 + (j * 5) % 7), 0.12, "sine", 0.2, 9), f["t"] + j * 0.16)
    for t0, k in sfx:  # efectos: tic (cuenta regresiva), tada (festejo), pop (aparece algo)
        if k == "tic":
            L.add(v, L.tone(hz(84), 0.12, "sine", 0.35, 25), t0)
        elif k == "pop":
            tt = np.arange(int(SR * 0.09)) / SR
            L.add(v, np.sin(2 * np.pi * (500 + 2500 * tt) * tt) * np.exp(-tt * 40) * 0.3, t0)
        elif k == "tada":
            for j, m in enumerate((72, 76, 79, 84)):
                L.add(v, L.tone(hz(m), 0.5, "tri", 0.18, 4), t0 + j * 0.09)
    env = np.convolve(np.abs(v), np.ones(SR // 5) / (SR // 5), "same")
    a = a * (1 - 0.65 * np.clip(env / 0.06, 0, 1)) + v
    a[-int(SR * 2):] *= np.linspace(1, 0, int(SR * 2))
    a = a / max(1e-6, np.abs(a).max()) * 0.92
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def render(tema, out, vertical=False, log=print):
    T = TEMAS[tema]
    W, H = (1080, 1920) if vertical else (1920, 1080)
    with tempfile.TemporaryDirectory() as tmp:
        frases, D = guion(tema, tmp)
        wav = os.path.join(tmp, "audio.wav")
        musica(D, wav, frases)
        bg = fondo(W, H)
        nubes = [L.cloud_sprite(s) for s in (1.0, 0.8, 1.2)]
        items = T["items"]
        col = {ch: COLS[i % len(COLS)] for i, (ch, _, _) in enumerate(items)}
        # cuándo aparece cada personaje
        ini = {}
        for f in frases:
            ini.setdefault(f["clave"], f["t"])
        t_fin = next(f["t"] for f in frases if f["clave"] == "final")
        piso = H * (0.80 if vertical else 0.86)
        alto = H * (0.26 if vertical else 0.42)
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
                              out], stdin=subprocess.PIPE)
        n = int(D * FPS)
        for i in range(n):
            t = i / FPS
            im = bg.copy()
            for k, c in enumerate(nubes):
                x = (k * W * 0.4 + t * 18 * (1 + k * 0.3)) % (W + c.width) - c.width
                im.alpha_composite(c, (int(x), int(H * (0.08 + 0.07 * k))))
            habla = next((f for f in frases if f["t"] <= t <= f["t"] + f["dur"]), None)
            if t < ini.get(items[0][0], 99):  # intro: Lolo presenta
                s = ease(t / 0.6)
                texto(im, T["titulo"], W / 2, H * 0.12 - (1 - s) * 200, int(H * (0.065 if vertical else 0.11)), (255, 214, 10), 10)
                dk = L.duck_sprite(walk=t * 3, mouth=abs(math.sin(t * 20)) if habla else 0, blink=(t % 3) < 0.12,
                                   look=True, walking=False)
                sc = (H * 0.45) / dk.height
                dk = dk.resize((int(dk.width * sc), int(dk.height * sc)), Image.LANCZOS)
                im.alpha_composite(dk, (int(W / 2 - dk.width / 2), int(piso - dk.height * 0.92)))
            elif t < t_fin:  # una letra/número por vez
                ch = next(c for c, _, _ in reversed(items) if ini.get(c, 99) <= t)
                _, pal, em = next(it for it in items if it[0] == ch)
                u = t - ini[ch]
                ent = ease(u / 0.45)
                if vertical:
                    lx, ex, ey, es = W / 2, W / 2, H * 0.36, int(W * 0.30)
                else:
                    lx, ex, ey, es = W * 0.36, W * 0.72, H * 0.44, int(H * 0.36)
                personaje(im, ch, lx + (1 - ent) * W * 0.6, piso, alto, col[ch], t,
                          hablando=bool(habla and habla["clave"] == ch))
                if u > 0.9:  # el dibujo y la palabra
                    s2 = ease((u - 0.9) / 0.35)
                    if tema == "numeros":
                        cnt = int(ch)
                        cols = min(5, cnt)
                        rows = math.ceil(cnt / cols)
                        es2 = int(es / max(cols, rows) * 1.5)
                        for j in range(cnt):
                            cx = ex + ((j % cols) - (cols - 1) / 2) * es2 * 1.05
                            cy = ey + ((j // cols) - (rows - 1) / 2) * es2 * 1.05
                            if u > 0.9 + j * 0.12:
                                emoji(im, em, cx, cy, int(es2 * s2))
                    else:
                        emoji(im, em, ex, ey - (0 if vertical else 30), int(es * s2))
                    pw = pal.upper()
                    texto(im, pw, ex, ey + es * (0.55 if not vertical else 0.62), int(H * (0.05 if vertical else 0.09)),
                          col[ch], 9)
            else:  # final: todos bailan juntos
                u = t - t_fin
                m = len(items)
                fila = items if m <= 10 else items[::max(1, m // 9)]
                k = len(fila)
                aw = alto * (0.55 if k > 5 else 0.75)
                for j, (ch, _, _) in enumerate(fila):
                    x = W * (j + 0.5) / k
                    personaje(im, ch, x, piso, aw, col[ch], t, fase=j * 0.37, hablando=False)
                texto(im, "¡MUY BIEN!", W / 2, H * 0.10, int(H * (0.07 if vertical else 0.12)), (255, 214, 10), 10)
                if u > 2.0:
                    texto(im, "¡SUSCRÍBETE!", W / 2, H * (0.22 if vertical else 0.27), int(H * (0.04 if vertical else 0.07)),
                          (255, 255, 255), 8)
            p.stdin.write(im.convert("RGB").tobytes())
            if i % (FPS * 10) == 0:
                log(f"  {t:.0f}/{D:.0f} s")
        p.stdin.close()
        p.wait()
    return out, D


def nuevo(tema, dest, log=print, vertical_tambien=True, modo="2d", calidad="normal"):
    import json
    if tema not in TEMAS:
        raise SystemExit(f"Tema desconocido: {tema}. Opciones: {', '.join(TEMAS)}")
    os.makedirs(dest, exist_ok=True)
    T = TEMAS[tema]
    base = f"aprende_{tema}"
    log(f"• Video educativo: {T['titulo']} (horizontal)…")
    rend = (lambda tm, o, v, lg: render3d(tm, o, v, lg, calidad=calidad)) if modo == "3d" else render
    if modo == "3d":
        base += "_3d"
    out_h, D = rend(tema, os.path.join(dest, base + ".mp4"), False, log)
    archivos = [(os.path.basename(out_h), "largo")]
    if vertical_tambien and D <= 170:
        log("• Versión vertical (short)…")
        out_v, _ = rend(tema, os.path.join(dest, base + "_short.mp4"), True, log)
        archivos.append((os.path.basename(out_v), "short"))
    nombre = {"vocales": "Las vocales A E I O U", "numeros": "Los números del 1 al 10",
              "abecedario": "El abecedario de la A a la Z"}[tema]
    desc = (f"{nombre} 🎶 ¡Aprende cantando con Lolo y sus amigos! Canción infantil animada para aprender jugando.\n\n"
            "🦆 Suscríbete para más canciones y aventuras de Lolo.\n\n"
            "#CancionesInfantiles #AprendeJugando #VideosParaNiños #Educativo")
    pj = os.path.join(dest, "publicar.json")
    items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
    for a, tipo in archivos:
        titulo = f"{nombre} 🎶 Aprende cantando | Canción infantil" if tipo == "largo" else f"{nombre} 🎶 #shorts"
        items = [i for i in items if i["archivo"] != a] + [{
            "archivo": a, "tipo": tipo, "ninos": True, "categoria": "27", "titulo": titulo[:100], "descripcion": desc,
            "tags": ["canciones infantiles", "aprende jugando", tema, "videos para niños", "educativo", "lolo el patito"]}]
    json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"✓ Listo en {dest}")
    return archivos


# ------------------------------------------------------------------ versión 3D (Blender)
def blender_bin():
    for p in (shutil.which("blender"), "/Applications/Blender.app/Contents/MacOS/Blender",
              os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender")):
        if p and os.path.exists(p):
            return p
    return None


def render3d(tema, out, vertical=False, log=print, calidad="normal", solo=None, blender=None, interactivo=True,
             corto=False):
    """Video 3D con Blender: Lolo presenta, cada letra/número se presenta con su dibujo y, si interactivo=True,
    después vienen los juegos para chicos de hasta 5 años: '¿Dónde está la…?' (3, 2, 1… ¡acá está!) y '¿Cuántos hay?'."""
    import json
    blender = blender or blender_bin()
    if not blender:
        raise SystemExit("No encuentro Blender. Instalalo desde blender.org (o con: brew install --cask blender).")
    T = TEMAS[tema]
    W, H = (1080, 1920) if vertical else (1920, 1080)
    if calidad == "rapida":
        W, H = W // 2, H // 2
    rnd = random.Random(tema)
    with tempfile.TemporaryDirectory() as tmp:
        ev, voces, sfx, habla = [], [], [], {}
        t = [0.5]

        def di(actor, texto, pausa=0.45):
            p = os.path.join(tmp, f"v{len(voces)}.wav")
            d = hablar(texto, p)
            if d is None:
                p, d = None, max(0.8, len(texto) / 13)
            voces.append(dict(clave=actor, texto=texto, t=t[0], dur=d, wav=p))
            habla.setdefault(actor, []).append((t[0], t[0] + d))
            t0 = t[0]
            t[0] += d + pausa
            return t0, d

        def emo_png(i, em):
            img = os.path.join(tmp, f"emoji_{i}.png")
            if not os.path.exists(img):
                e = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
                L.emoji_at(e, em, 6, 6, 500)
                e.save(img)
            return img

        items = T["items"][:5] if corto else T["items"]
        colores = {ch: COLOR_REAL.get(ch, COLS[i % len(COLS)]) for i, (ch, _, _) in enumerate(items)}
        # 1) presentación
        a = t[0]
        di("lolo", T["hola"], 0.8)
        ev += [dict(tipo="titulo", texto=T["titulo"], t0=a, t1=t[0]), dict(tipo="anfitrion", quien="lolo", lugar="centro", t0=a, t1=t[0])]
        # 2) aprendemos cada una
        for i, (ch, pal, em) in enumerate(items):
            a = t[0]
            sfx.append((a, "pop"))
            if tema == "numeros":
                di(ch, f"¡El {pal}!", 0.35)
            elif tema == "colores":
                di(ch, f"¡El {ch.lower()}!", 0.35)
                di(ch, f"{ch.capitalize()}, como la {pal}.", 0.35)
            else:
                di(ch, f"¡La {ch.lower()}!", 0.35)
                di(ch, f"{ch.lower()}... de {pal}.", 0.35)
            t[0] += 0.5
            ev.append(dict(tipo="item", ch=ch, palabra=ch if tema == "colores" else pal, img=emo_png(i, em),
                           color=colores[ch], t0=a, t1=t[0]))
        # 3) ¡a jugar! (interactivo)
        if interactivo:
            a = t[0]
            di("lolo", "¡Ahora juguemos! ¿Me ayudas?", 0.6)
            ev.append(dict(tipo="anfitrion", quien="lolo", lugar="centro", t0=a, t1=t[0]))
            preguntas = rnd.sample(items, 2 if corto else min(len(items), 5 if tema != "abecedario" else 6))
            for k, (ch, pal, em) in enumerate(preguntas):
                if tema == "numeros" and k % 2 == 1:  # juego de contar
                    n = int(ch)
                    plural = PLURAL.get(em, "cositas")
                    a = t[0]
                    cuant = "Cuántas" if plural.endswith("as") or plural == "flores" else "Cuántos"
                    di("lolo", f"¿{cuant} {plural} hay? ¡Contemos juntos!", 0.4)
                    t_objs = []
                    for j in range(n):
                        t0, _ = di("lolo", TEMAS["numeros"]["items"][j][1], 0.25)
                        t_objs.append(t0)
                        sfx.append((t0, "pop"))
                    tr = t[0]
                    sfx.append((tr, "tada"))
                    di("lolo", f"¡{pal.capitalize()}! ¡Muy bien!", 1.0)
                    ev.append(dict(tipo="contar", n=n, img=emo_png(items.index((ch, pal, em)), em), color=colores[ch],
                                   t0=a, t_objs=t_objs, t_resp=tr, t1=t[0]))
                    ev.append(dict(tipo="anfitrion", quien="lolo", t0=a, t1=t[0]))
                    continue
                otros = rnd.sample([c for c, _, _ in items if c != ch], 2)
                ops = otros + [ch]
                rnd.shuffle(ops)
                a = t[0]
                q = (f"¿Dónde está el {pal}?" if tema == "numeros" else f"¿Dónde está el {ch.lower()}?"
                     if tema == "colores" else f"¿Dónde está la {ch.lower()}?")
                di("lolo", q + " ¡Señálala con tu dedito!", 0.5)
                tc = t[0]
                for j, num in enumerate(("Tres", "Dos", "Uno")):
                    t[0] = tc + j * 1.0
                    sfx.append((t[0], "tic"))
                    di("lolo", num, 0)
                t[0] = tc + 3.0
                tr = t[0]
                sfx.append((tr, "tada"))
                di(ch, f"¡Aquí estoy! ¡El {pal}!" if tema == "numeros" else f"¡Aquí estoy! ¡El {ch.lower()}!"
                   if tema == "colores" else f"¡Aquí estoy! ¡La {ch.lower()}!", 0.2)
                di("lolo", rnd.choice(["¡Muy bien!", "¡Excelente!", "¡Genial!", "¡Lo lograste!"]), 0.9)
                ev.append(dict(tipo="pregunta", texto=q.upper(), opciones=ops, colores=[colores[c] for c in ops],
                               correcta=ch, t0=a, t_cuenta=tc, t_resp=tr, t1=t[0], paso=1.0))
                ev.append(dict(tipo="anfitrion", quien="lolo", t0=a, t1=t[0]))
        # 4) final
        a = t[0]
        sfx.append((a + 0.3, "tada"))
        di("lolo", T["chau"] + " ¡Chau, amigos!", 1.0)
        D = t[0] + 2.5
        ev.append(dict(tipo="final", chars=[(c, colores[c]) for c, _, _ in items], t0=a, t1=D))
        wav = os.path.join(tmp, "audio.wav")
        musica(D, wav, voces, sfx)
        frames = os.path.join(tmp, "frames")
        os.makedirs(frames)
        plan = dict(w=W, h=H, fps=FPS, dur=D, eventos=ev, habla=habla, frames=frames, anfitriones=["lolo"],
                    libdir=os.path.dirname(os.path.abspath(__file__)), fuente=os.path.join(L.FD, "Anton-Regular.ttf"),
                    motor="EEVEE", muestras=16 if calidad == "rapida" else 48, solo=solo)
        pj = os.path.join(tmp, "plan.json")
        json.dump(plan, open(pj, "w"))
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escena3d.py")
        log(f"• Blender renderizando {int(D * FPS)} cuadros en 3D ({D:.0f} s de video; puede tardar un rato)…")
        subprocess.run([blender, "-b", "-P", script, "--", pj], check=True,
                       stdout=subprocess.DEVNULL if calidad != "debug" else None)
        if solo:
            for f in sorted(os.listdir(frames)):
                shutil.copy(os.path.join(frames, f), os.path.join(os.path.dirname(out), f))
            return out, D
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames, "f%04d.png"),
                        "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], check=True)
    return out, D


PLURAL = {"🍎": "manzanas", "⭐": "estrellas", "🐟": "peces", "🌸": "flores", "🎈": "globos", "🍓": "frutillas",
          "🐞": "vaquitas", "🍪": "galletitas", "🦋": "mariposas", "🍌": "bananas"}

COLOR_REAL = {"ROJO": (230, 40, 40), "AZUL": (30, 110, 235), "AMARILLO": (250, 205, 20), "VERDE": (40, 175, 70),
              "NARANJA": (255, 135, 20), "VIOLETA": (140, 70, 220), "ROSA": (240, 100, 170)}


def shorts3d(temas, dest, log=print, calidad="normal"):
    """Arma shorts verticales 3D interactivos (≈1 min) de cada tema y los deja en la cola de Lolo."""
    import json
    os.makedirs(dest, exist_ok=True)
    nombres = {"letras": "Aprende las letras", "numeros": "Aprende los números", "colores": "Aprende los colores",
               "vocales": "Aprende las vocales", "abecedario": "El abecedario"}
    pj = os.path.join(dest, "publicar.json")
    for tema in temas:
        out = os.path.join(dest, f"short3d_{tema}.mp4")
        log(f"• Short 3D: {nombres.get(tema, tema)}…")
        render3d(tema, out, True, log, calidad=calidad, corto=True)
        items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
        a = os.path.basename(out)
        items = [i for i in items if i["archivo"] != a] + [{
            "archivo": a, "tipo": "short", "ninos": True, "categoria": "27",
            "titulo": f"{nombres.get(tema, tema)} con Lolo 🦆 ¡Juega y aprende! #shorts"[:100],
            "descripcion": (f"{nombres.get(tema, tema)} jugando con Lolo y sus amigos 🎶 ¿Encontrás la respuesta antes "
                            "de que termine la cuenta? 3, 2, 1… 🦆\n\nVideo educativo para chicos de hasta 5 años.\n\n"
                            "#AprendeJugando #VideosParaNiños #Educativo #Shorts"),
            "tags": ["aprende jugando", tema, "videos para niños", "educativo", "lolo el patito", "preescolar"]}]
        json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"  ✓ {out}")
