"""Canal para dormir (nombre en config.json → relax_canal): videos largos con pantalla negra y sonidos 100% originales, generados acá mismo.
Sonidos: ruido blanco, lluvia suave (sintetizada) y música ambiente (acordes generados al azar cada día).
Nada se descarga de terceros: no hay derechos de autor de nadie más."""
import datetime as dt, json, math, os, random, subprocess, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from .paths import FD, ROOT, cfg

SR = 44100
NOMBRE = {"blanco": "Ruido Blanco", "lluvia": "Lluvia Suave", "ambiente": "Música Ambiente"}
ACENTO = {"blanco": (226, 232, 255), "lluvia": (120, 170, 255), "ambiente": (190, 150, 255)}
CANAL = cfg().get("relax_canal", "Mi Canal para Dormir")


def _ff(*a):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *a], check=True)


# ---------------------------------------------------------------- sonidos
def _filtro_ruido(tipo, seed):
    """Grafo de ffmpeg que genera el ruido en estéreo (dos fuentes independientes)."""
    r = random.Random(seed)
    if tipo == "blanco":
        lp = r.choice([8000, 9000, 10000])
        ch = "anoisesrc=color=white:amplitude=0.22:seed={s}:sample_rate=44100,highpass=f=40,lowpass=f=%d" % lp
    else:  # lluvia: colchón rosa + gotitas (ruido 'velvet') con intensidad que respira lento
        per = r.uniform(35, 70)
        ch = ("anoisesrc=color=pink:amplitude=0.32:seed={s}:sample_rate=44100,highpass=f=250,lowpass=f=6500,"
              f"volume='0.85+0.15*sin(2*PI*t/{per:.1f})':eval=frame[p{{k}}];"
              "anoisesrc=color=velvet:amplitude=0.5:seed={s2}:sample_rate=44100,highpass=f=1800,lowpass=f=9000,"
              "volume=0.22[v{k}];[p{k}][v{k}]amix=inputs=2:normalize=0")
    left = ch.format(s=seed % 2 ** 31, s2=(seed * 7 + 3) % 2 ** 31, k="L")
    right = ch.format(s=(seed * 3 + 1) % 2 ** 31, s2=(seed * 11 + 5) % 2 ** 31, k="R")
    return f"{left}[l];{right}[r];[l][r]amerge=inputs=2,volume=0.9[a]"


NOTAS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9}
# progresiones suaves (grados en semitonos desde la tónica, acordes con 7ma/9na)
PROG = [[0, 9, 5, 7], [0, 5, 9, 7], [0, 7, 9, 5], [9, 5, 0, 7], [0, 4, 5, 7]]
CALIDAD = {0: [0, 4, 7, 11, 14], 2: [0, 3, 7, 10, 14], 4: [0, 3, 7, 10], 5: [0, 4, 7, 11, 14], 7: [0, 4, 7, 10, 14],
           9: [0, 3, 7, 10, 14]}


def _ambiente_loop(seed, path, acordes=8, dur_acorde=45.0, fundido=12.0):
    """Pieza ambiental que se repite sin corte (loop perfecto) de acordes*dur_acorde segundos."""
    r = random.Random(seed)
    T = acordes * dur_acorde
    N = int(T * SR)
    buf = np.zeros((N, 2), np.float32)
    raiz = 110.0 * 2 ** (NOTAS[r.choice(list(NOTAS))] / 12)          # tónica entre A2 y G3
    prog = r.choice(PROG)
    W = int((dur_acorde + fundido) * SR)
    tl = np.arange(W) / SR
    env = np.ones(W, np.float32)
    fa = int(fundido * SR)
    env[:fa] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fa))
    env[-fa:] = env[:fa][::-1]
    for k in range(acordes):
        grado = prog[k % len(prog)]
        notas = CALIDAD.get(grado % 12, [0, 4, 7, 11])
        voces = r.sample(notas, min(4, len(notas)))
        start = int((k * dur_acorde - fundido / 2) * SR) % N
        chord = np.zeros((W, 2), np.float32)
        for v in voces:
            f = raiz * 2 ** ((grado + v) / 12) * r.choice([1, 1, 2])
            lfo = 0.6 + 0.4 * np.sin(2 * np.pi * tl / r.uniform(6, 13) + r.uniform(0, 6.28))
            for c, det in enumerate((1.0, 1.0 + r.uniform(0.0008, 0.002))):
                ph = r.uniform(0, 6.28)
                s = np.sin(2 * np.pi * f * det * tl + ph) + 0.18 * np.sin(4 * np.pi * f * det * tl + ph)
                chord[:, c] += (s * lfo * 0.08).astype(np.float32)
        chord *= env[:, None]
        idx = (np.arange(W) + start) % N
        if start + W > N:
            np.add.at(buf, idx, chord)
        else:
            buf[start:start + W] += chord
    # bajo pedal (periódico exacto en T)
    fb = round(raiz / 2 * T) / T
    t = np.arange(N) / SR
    pedal = 0.05 * np.sin(2 * np.pi * fb * t) * (0.8 + 0.2 * np.sin(2 * np.pi * t / T * 6))
    buf += pedal[:, None].astype(np.float32)
    buf /= max(1e-6, np.abs(buf).max()) / 0.5
    pcm = (buf * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return T


# ---------------------------------------------------------------- imágenes
def _font(name, size, var=None):
    f = ImageFont.truetype(FD + name, size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


def _cielo(Wd, Hd, seed, acento, luna=(0.78, 0.30), estrellas=160, rad=0.13):
    r = random.Random(seed)
    im = Image.new("RGB", (Wd, Hd))
    top, bot = np.array((3, 5, 12)), np.array((10, 16, 38))
    g = np.linspace(0, 1, Hd)[:, None] ** 1.3
    arr = (top * (1 - g) + bot * g)[:, None, :].repeat(Wd, 1)
    im = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for _ in range(estrellas):
        x, y = r.uniform(0, Wd), r.uniform(0, Hd * 0.85)
        s = r.choice([1, 1, 1, 2, 2, 3]) * Wd / 1280
        a = r.randint(90, 230)
        d.ellipse((x - s / 2, y - s / 2, x + s / 2, y + s / 2), fill=(a, a, min(255, a + 15)))
    cx, cy, R = Wd * luna[0], Hd * luna[1], Hd * rad
    glow = Image.new("L", (Wd, Hd), 0)
    ImageDraw.Draw(glow).ellipse((cx - R * 2.6, cy - R * 2.6, cx + R * 2.6, cy + R * 2.6), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(R * 1.1))
    im = Image.composite(Image.new("RGB", (Wd, Hd), tuple(int(c * 0.55) for c in acento)), im, glow)
    moon = Image.new("L", (Wd, Hd), 0)
    md = ImageDraw.Draw(moon)
    md.ellipse((cx - R, cy - R, cx + R, cy + R), fill=255)
    md.ellipse((cx - R * 0.55, cy - R * 1.12, cx + R * 1.35, cy + R * 0.78), fill=0)       # media luna
    im = Image.composite(Image.new("RGB", (Wd, Hd), (246, 240, 222)), im, moon.filter(ImageFilter.GaussianBlur(1.2)))
    return im


def _centrado(d, cx, y, txt, f, fill):
    w = d.textlength(txt, font=f)
    d.text((cx - w / 2, y), txt, font=f, fill=fill)


def miniatura(tipo, horas, seed, out, etiqueta=None):
    Wd, Hd = 1280, 720
    ac = ACENTO[tipo]
    im = _cielo(Wd, Hd, seed, ac, luna=(0.80, 0.30))
    d = ImageDraw.Draw(im)
    if tipo == "lluvia":
        r = random.Random(seed + 1)
        for _ in range(260):
            x, y, L = r.uniform(0, Wd), r.uniform(0, Hd), r.uniform(18, 46)
            d.line((x, y, x - L * 0.25, y + L), fill=(110, 140, 200), width=1)
    fl = _font("Poppins-Medium.ttf", 30)
    lab = etiqueta or f"{horas} HORAS  ·  PANTALLA NEGRA"
    w = d.textlength(lab, font=fl)
    d.rounded_rectangle((70, 196, 70 + w + 44, 250), radius=27, outline=ac, width=2)
    d.text((92, 202), lab, font=fl, fill=ac)
    big = NOMBRE[tipo].upper()
    fs = 120
    while fs > 60 and d.textlength(big, font=_font("Poppins-Medium.ttf", fs)) > 760:
        fs -= 4
    d.text((66, 280), big, font=_font("Poppins-Medium.ttf", fs), fill=(245, 245, 250))
    sub = {"blanco": "para dormir profundo", "lluvia": "para dormir y relajarte", "ambiente": "para dormir profundamente"}[tipo]
    d.text((70, 280 + fs + 30), sub, font=_font("Lora-Italic-Variable.ttf", 52),
           fill=(200, 205, 225))
    d.text((70, Hd - 92), CANAL, font=_font("Lora-Variable.ttf", 34, "SemiBold"), fill=ac)
    im.save(out, quality=92)


def perfil(out):
    S = 800
    im = _cielo(S * 2, S * 2, 7, ACENTO["ambiente"], luna=(0.56, 0.5), estrellas=90, rad=0.27)
    im.resize((S, S), Image.LANCZOS).save(out, quality=94)


def banner(out):
    Wd, Hd = 2560, 1440
    im = _cielo(Wd, Hd, 11, ACENTO["ambiente"], luna=(0.75, 0.45), estrellas=420)
    d = ImageDraw.Draw(im)
    cx = Wd / 2 - 160
    _centrado(d, cx, 548, CANAL, _font("Lora-Variable.ttf", 128, "SemiBold"), (244, 242, 252))
    _centrado(d, cx, 718, "Ruido blanco · Lluvia · Música para dormir", _font("Poppins-Light.ttf", 46), (205, 208, 230))
    _centrado(d, cx, 786, "Pantalla negra · Videos de 8 horas · Uno nuevo cada día", _font("Poppins-Light.ttf", 34),
              (150, 160, 200))
    im.save(out, quality=94)


# ---------------------------------------------------------------- textos
TITULOS = {
    "blanco": ["Ruido Blanco para Dormir Profundo | {h} Horas Pantalla Negra 🌙",
               "Ruido Blanco {h} Horas · Pantalla Negra para Dormir y Concentrarte",
               "Ruido Blanco para Bebés y Adultos | {h} Horas Pantalla Negra 💤"],
    "lluvia": ["Lluvia Suave para Dormir | {h} Horas Pantalla Negra 🌧️",
               "Sonido de Lluvia para Dormir Profundo · {h} Horas Pantalla Negra",
               "Lluvia Relajante para Dormir y Calmar la Mente | {h} Horas 🌧️"],
    "ambiente": ["Música para Dormir Profundamente | {h} Horas Pantalla Negra 🌙",
                 "Música Relajante para Dormir y Calmar la Ansiedad · {h} Horas Pantalla Negra",
                 "Música Ambiente para Dormir Rápido | {h} Horas Pantalla Negra 💤"]}
DESC = {"blanco": "Ruido blanco suave y constante para dormir profundo, tapar ruidos de afuera, calmar al bebé o concentrarte.",
        "lluvia": "Sonido de lluvia suave y continua, sin truenos, para dormir, relajarte o meditar.",
        "ambiente": "Música ambiente lenta y suave, con acordes que flotan, para dormir profundamente y bajar la ansiedad."}


def textos(tipo, horas, n):
    title = TITULOS[tipo][n % len(TITULOS[tipo])].format(h=horas)
    desc = "\n".join([
        DESC[tipo], "",
        f"🌙 {horas} horas con pantalla negra para que la luz no te despierte.",
        f"🔊 Sonido original creado por {CANAL}. Usalo a volumen bajo.",
        "🔔 Suscribite: subimos un video nuevo para dormir todos los días.", "",
        "#PantallaNegra #" + NOMBRE[tipo].replace(" ", "").replace("ú", "u") + " #MusicaParaDormir #Dormir #Relajacion"])
    tags = [NOMBRE[tipo].lower(), "pantalla negra", "para dormir", "dormir profundo", f"{horas} horas",
            "música para dormir", "ruido blanco", "relajación", "sonidos para dormir", "dormir rápido"]
    return title, desc, tags


# ---------------------------------------------------------------- video
LOOP = 600.0          # 10 min de sonido que se repite sin corte (no se nota en ruido/lluvia/ambiente)
LUFS = -24.0          # volumen suave y parejo entre videos


def _leer_wav(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768


def _escribir_wav(p, x):
    with wave.open(p, "wb") as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def _lufs(p):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", p, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    try:
        return float(r.split("Integrated loudness:")[1].split("I:")[1].split("LUFS")[0])
    except Exception:
        return LUFS


def _loop_wav(tipo, seed, d):
    """WAV de LOOP segundos que empalma perfecto consigo mismo, ya con su volumen final."""
    p = os.path.join(d, "loop.wav")
    if tipo == "ambiente":
        raw = os.path.join(d, "raw.wav")
        T = _ambiente_loop(seed, raw)
        # eco suave: proceso dos vueltas y me quedo con la segunda (ya periódica)
        _ff("-stream_loop", "1", "-i", raw, "-af",
            f"aecho=0.8:0.6:90|170|310:0.28|0.2|0.12,lowpass=f=7000,atrim=start={T}:duration={T}", p)
    else:
        X = 10.0
        raw = os.path.join(d, "raw.wav")
        _ff("-filter_complex", _filtro_ruido(tipo, seed), "-map", "[a]", "-t", str(LOOP + X), "-ar", str(SR), raw)
        a = _leer_wav(raw)
        L, n = int(LOOP * SR), int(X * SR)
        y = a[:L].copy()
        w = np.linspace(0, np.pi / 2, n)[:, None]
        y[:n] = a[:n] * np.sin(w) + a[L:L + n] * np.cos(w)
        _escribir_wav(p, y)
    gain = 10 ** ((LUFS - _lufs(p)) / 20)
    _escribir_wav(p, _leer_wav(p) * gain)
    return p


def video(tipo, horas, seed, out, intro_png):
    """Pantalla negra (con la miniatura los primeros segundos, que se funde a negro) + sonido."""
    D = horas * 3600.0
    with tempfile.TemporaryDirectory() as d:
        loop = _loop_wav(tipo, seed, d)
        _ff("-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r=2:d={D}",
            "-loop", "1", "-framerate", "2", "-t", "12", "-i", intro_png,
            "-stream_loop", "-1", "-i", loop,
            "-filter_complex",
            "[1:v]scale=1920:1080,format=rgba,fade=t=out:st=5:d=6:alpha=1[i];[0:v][i]overlay=eof_action=pass,format=yuv420p[v];"
            f"[2:a]afade=t=in:d=8,afade=t=out:st={max(0, D - 15)}:d=15[a]",
            "-map", "[v]", "-map", "[a]", "-t", str(D),
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "30", "-g", "600",
            "-c:a", "aac", "-b:a", "128k", "-ar", str(SR), "-movflags", "+faststart", out)


def short(tipo, horas, seed, src, out, inicio=600.0, dur=30.0, titulo=None):
    """Short vertical de 30 s: cielo nocturno con el título + un tramo del sonido del video largo."""
    ac = ACENTO.get(tipo, ACENTO["ambiente"])
    im = _cielo(1080, 1920, seed, ac, luna=(0.70, 0.22), estrellas=260, rad=0.07)
    d = ImageDraw.Draw(im)
    if tipo == "lluvia":
        r = random.Random(seed + 1)
        for _ in range(420):
            x, y, L = r.uniform(0, 1080), r.uniform(0, 1920), r.uniform(24, 60)
            d.line((x, y, x - L * 0.25, y + L), fill=(110, 140, 200), width=2)
    big = (titulo or NOMBRE.get(tipo, "Para dormir")).upper()
    import textwrap
    y = 760
    for ln in textwrap.wrap(big, 16)[:4]:
        fs = 104
        while fs > 50 and d.textlength(ln, font=_font("Poppins-Medium.ttf", fs)) > 860:
            fs -= 4
        _centrado(d, 540, y, ln, _font("Poppins-Medium.ttf", fs), (245, 245, 250))
        y += fs + 26
    _centrado(d, 540, y + 30, "cerrá los ojos y respirá…", _font("Lora-Italic-Variable.ttf", 56), (200, 205, 225))
    lab = f"Video completo de {horas} h en el canal 🌙" if horas else "Video completo en el canal 🌙"
    _centrado(d, 540, 1640, lab.replace(" 🌙", ""), _font("Poppins-Medium.ttf", 44), ac)
    _centrado(d, 540, 1760, CANAL, _font("Lora-Variable.ttf", 50, "SemiBold"), ac)
    with tempfile.TemporaryDirectory() as td:
        png = os.path.join(td, "s.png")
        im.save(png)
        _ff("-loop", "1", "-framerate", "30", "-t", str(dur), "-i", png, "-ss", str(inicio), "-t", str(dur), "-i", src,
            "-filter_complex", f"[0:v]zoompan=z='1+0.00008*on':d=1:s=1080x1920:fps=30,format=yuv420p[v];"
            f"[1:a]afade=t=in:d=2,afade=t=out:st={dur - 3}:d=3[a]",
            "-map", "[v]", "-map", "[a]", "-t", str(dur), "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out)
    return out


def item_short(archivo, nombre):
    return {"archivo": archivo, "tipo": "short", "categoria": "10",
            "titulo": f"{nombre} para dormir en segundos 🌙 #shorts"[:100],
            "descripcion": f"{nombre} con pantalla oscura. 😴\n\n👉 El video completo está en el canal {CANAL}.\n"
                           "🔔 Suscribite: un video nuevo para dormir todos los días.\n\n#Shorts #Dormir #Relajacion #PantallaNegra",
            "tags": ["para dormir", "relajación", "pantalla negra", "shorts", nombre.lower()]}


def dir_relax():
    return os.path.join(ROOT, "canales", "relax")


def nuevo(tipo=None, horas=None, log=print):
    c = cfg()
    horas = float(horas or c.get("relax_horas", 8))
    horas = int(horas) if horas.is_integer() else horas
    sonidos = c.get("relax_sonidos", ["blanco", "lluvia", "ambiente"])
    hoy = dt.date.today()
    n = hoy.toordinal()
    tipo = tipo or sonidos[n % len(sonidos)]
    if tipo not in NOMBRE:
        raise SystemExit(f"Sonido desconocido: {tipo}. Opciones: {', '.join(NOMBRE)}")
    seed = n * 100 + list(NOMBRE).index(tipo)
    dest = os.path.join(dir_relax(), "listo")
    os.makedirs(dest, exist_ok=True)
    base = f"{hoy.isoformat()}_{tipo}_{horas}h"
    mini = os.path.join(dest, base + "_miniatura.jpg")
    out = os.path.join(dest, base + ".mp4")
    log(f"• {CANAL}: {NOMBRE[tipo]} {horas} h ({base})…")
    miniatura(tipo, horas, seed, mini)
    video(tipo, horas, seed, out, mini)
    title, desc, tags = textos(tipo, horas, n // len(sonidos))
    pj = os.path.join(dest, "publicar.json")
    items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
    items = [i for i in items if i["archivo"] != os.path.basename(out)]
    items.append({"archivo": os.path.basename(out), "tipo": "largo", "titulo": title, "descripcion": desc, "tags": tags,
                  "portada": os.path.basename(mini), "categoria": "10"})
    try:
        sh = os.path.join(dest, base + "_short.mp4")
        short(tipo, horas, seed, out, sh)
        items = [i for i in items if i["archivo"] != os.path.basename(sh)] + [item_short(os.path.basename(sh), NOMBRE[tipo])]
    except Exception as e:
        log(f"  (no pude armar el short: {str(e)[:100]})")
    json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(dest, "publicar.txt"), "w", encoding="utf-8") as f:
        for it in items:
            f.write("=" * 60 + f"\nARCHIVO: {it['archivo']}\nMINIATURA: {it['portada']}\n"
                    + (f"SUBIDO: {it['subido']}\n" if it.get("subido") else "")
                    + f"\nTÍTULO:\n{it['titulo']}\n\nDESCRIPCIÓN:\n{it['descripcion']}\n\n")
    log(f"✓ Listo: {out}")
    return out


def limpiar(dias=3):
    """Borra videos ya subidos de hace más de `dias` (son pesados)."""
    dest = os.path.join(dir_relax(), "listo")
    pj = os.path.join(dest, "publicar.json")
    if not os.path.exists(pj):
        return
    lim = dt.date.today() - dt.timedelta(days=dias)
    for it in json.load(open(pj, encoding="utf-8")):
        f = os.path.join(dest, it["archivo"])
        if it.get("subido") and os.path.exists(f) and it["archivo"][:10] < lim.isoformat():
            os.remove(f)
