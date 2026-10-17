"""Edición con ffmpeg: shorts 9:16, cierre animado, compresión, cuadros y hojas de revisión."""
import os, shutil, subprocess, tempfile
from PIL import Image, ImageDraw
from .paths import FONT, OUTRO, cfg
from . import mix as M

W, H = 1080, 1920
VID_ENC = ["-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-profile:v", "high", "-level", "4.0",
           "-pix_fmt", "yuv420p", "-video_track_timescale", "15360"]
AUD_ENC = ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]


def ff(*a):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *a], check=True)


def probe(f, entries, stream=None):
    a = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else []) + \
        ["-show_entries", entries, "-of", "csv=p=0", f]
    return subprocess.check_output(a).decode().strip()


def has_audio(f):
    return bool(probe(f, "stream=index", "a"))


def dur(f):
    return float(probe(f, "format=duration"))


def size(f):
    w, h = probe(f, "stream=width,height", "v:0").split(",")[:2]
    return int(w), int(h)


def mux(video, audio, out):
    """Une video y audio bajados por separado."""
    ff("-i", video, "-i", audio, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
       "-shortest", "-movflags", "+faststart", out)


def frame(video, sec, out):
    ff("-ss", str(max(0, sec)), "-i", video, "-frames:v", "1", "-q:v", "2", out)


def hoja(video, t0, d, out, every=2):
    """Hoja de revisión: un cuadro cada `every` s desde t0, con el tiempo del partido."""
    t0 = max(0, t0)
    n = max(1, int(d / every))
    cols = 5
    rows = (n + cols - 1) // cols
    ts = "drawtext=fontfile='%s':text='%%{pts\\:hms\\:%s}':fontsize=26:fontcolor=yellow:box=1:boxcolor=black@0.7:x=6:y=6" % (FONT, t0)
    ff("-ss", str(t0), "-t", str(d), "-i", video, "-vf", f"fps=1/{every},scale=384:-2,{ts},tile={cols}x{rows}",
       "-frames:v", "1", "-q:v", "3", out)


def overlay_png(path, l1, l2, tipo=None, fuente=None):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    M.pill(im, W / 2, 96, cfg().get("marca", "MI CANAL").upper(), M.NAVY, M.YEL + (240,), "Oswald.ttf", 34, "Bold")
    y = 230
    if tipo:
        M.pill(im, W / 2, y - 60, tipo, M.WHITE, M.RED + (235,), "Oswald.ttf", 36, "Bold", pad=(22, 6))
        y += 20
    if l1:
        y = M.big_text(im, l1, y, 78, M.WHITE, maxw=1000, stroke=7) + 30
    if l2:
        M.big_text(im, l2, y, 150, M.YEL, maxw=1000, stroke=9)
    if fuente:
        M.pill(im, W / 2, 1830, f"Imágenes: {fuente}", M.WHITE, (8, 16, 38, 200), "Oswald.ttf", 28, "Medium", pad=(20, 7))
    im.save(path)


def gancho_png(path, text):
    """Cartel de intriga para el arranque: banda oscura y texto grande sobre el video."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, H), fill=(8, 16, 38, 110))
    M.pill(im, W / 2, 96, cfg().get("marca", "MI CANAL").upper(), M.NAVY, M.YEL + (240,), "Oswald.ttf", 34, "Bold")
    lines = text.split("|")
    y = 330 if len(lines) > 1 else 400
    for i, ln in enumerate(lines):
        y = M.big_text(im, ln, y, 112 if i == 0 else 84, M.WHITE if i == 0 else M.YEL, maxw=1000, stroke=9 if i == 0 else 7) + 34
    im.save(path)


def short(video, tramos, out, l1="", l2="", tipo=None, fuente=None, gancho=None, t_clave=None, gdur=1.8):
    """Corta uno o más tramos [(inicio, dur)], arma el 9:16 con fondo desenfocado y textos.
    gancho: texto de intriga; abre con un adelanto de {gdur} s del momento clave (t_clave) y ese cartel."""
    au = has_audio(video)
    with tempfile.TemporaryDirectory() as d:
        png = os.path.join(d, "ov.png")
        overlay_png(png, l1, l2, tipo, fuente)
        G = 0.0
        if gancho and t_clave is not None:
            G = gdur
            tramos = [(max(0.0, t_clave - 1.0), G)] + list(tramos)
            gp = os.path.join(d, "g.png")
            gancho_png(gp, gancho)
        ins = []
        for s, t in tramos:
            ins += ["-ss", f"{max(0, s):.2f}", "-t", f"{t:.2f}", "-i", video]
        n = len(tramos)
        total = sum(t for _, t in tramos)
        ins += ["-loop", "1", "-t", f"{total:.2f}", "-i", png]
        if G:
            ins += ["-loop", "1", "-t", f"{total:.2f}", "-i", gp]
        na = n + (2 if G else 1)                     # índice de la entrada de silencio (si no hay audio)
        if not au:
            ins += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        fc = []
        for i in range(n):
            fc.append(f"[{i}:v]fps=30,setsar=1,setpts=PTS-STARTPTS[v{i}]")
            if au:
                fc.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
        if au:
            fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
        else:
            fc.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[cv]")
        fc.append("[cv]split=2[bg][fg];"
                  "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,scale=216:384,boxblur=6:2,"
                  "scale=1080:1920,drawbox=c=0x08101F@0.35:t=fill[b];"
                  "[fg]scale=1080:-2[f];[b][f]overlay=(W-w)/2:(H-h)/2[c];"
                  + (f"[c][{n}:v]overlay=enable='gte(t,{G})'[c2];[c2][{n + 1}:v]overlay=enable='lt(t,{G})',"
                     f"drawbox=c=white@0.7:t=fill:enable='between(t,{G},{G + 0.08})',format=yuv420p[v]"
                     if G else f"[c][{n}:v]overlay,format=yuv420p[v]"))
        amap = ["-map", "[ca]"] if au else ["-map", f"{na}:a"]
        ff(*ins, "-filter_complex", ";".join(fc), "-map", "[v]", *amap, "-t", f"{total:.2f}", *VID_ENC, *AUD_ENC,
           "-movflags", "+faststart", out)


def outro(src, out):
    """Agrega al final la animación de 'me gusta + suscribite'."""
    from .outro import asegurar
    asegurar()
    with tempfile.TemporaryDirectory() as d:
        last = os.path.join(d, "last.png")
        ff("-sseof", "-0.3", "-i", src, "-update", "1", "-frames:v", "1", last)
        seg = os.path.join(d, "outro.mp4")
        ins = ["-loop", "1", "-framerate", "30", "-t", "2.6", "-i", last,
               "-framerate", "30", "-i", os.path.join(OUTRO, "frames", "f%03d.png"),
               "-i", os.path.join(OUTRO, "pops.wav")]
        fc = ("[0:v]scale=1080:1920,setsar=1,split[s][b];[b]scale=216:384,boxblur=8:2,scale=1080:1920,"
              "drawbox=c=0x08101F@0.6:t=fill[bb];[s][bb]xfade=transition=fade:duration=0.3:offset=0[bg];"
              "[bg][1:v]overlay=0:0:shortest=1,format=yuv420p[v];"
              "[2:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]")
        ff(*ins, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", "2.6", *VID_ENC, *AUD_ENC, seg)
        lst = os.path.join(d, "list.txt")
        with open(lst, "w") as f:
            f.write(f"file '{os.path.abspath(src)}'\nfile '{seg}'\n")
        ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out)


def shrink(src, out, mb=8.3):
    """Deja el archivo por debajo de ~10 MB (límite de subida por Chrome). Si ya es chico, lo copia."""
    if os.path.getsize(src) <= mb * 1048576:
        if os.path.abspath(src) != os.path.abspath(out):
            shutil.copyfile(src, out)
        return
    br = int(mb * 8388608 / dur(src) / 1000) - 96
    ff("-i", src, "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{br}k", "-maxrate", f"{br}k",
       "-bufsize", f"{br * 2}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out)


def to720(src, out):
    """Versión 720p liviana de un video horizontal."""
    ff("-i", src, "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out)
