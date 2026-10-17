"""Recorte vertical 9:16 de cualquier video propio (para sacar shorts de un video largo)."""
import os, subprocess, tempfile, textwrap
from PIL import Image, ImageDraw, ImageFont
from .paths import FD


def duracion(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _rotulo(png, titulo, pie, color=(255, 214, 10)):
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FD + "Anton-Regular.ttf", 84)
    y = 150
    for ln in textwrap.wrap(titulo.upper(), 20)[:3]:
        w = d.textlength(ln, font=f)
        d.text(((1080 - w) / 2, y), ln, font=f, fill=(255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0))
        y += 104
    if pie:
        f2 = ImageFont.truetype(FD + "Poppins-Medium.ttf", 50)
        w = d.textlength(pie, font=f2)
        d.rounded_rectangle(((1080 - w) / 2 - 30, 1660, (1080 + w) / 2 + 30, 1750), radius=44, fill=(0, 0, 0, 170))
        d.text(((1080 - w) / 2, 1670), pie, font=f2, fill=color)
    im.save(png)


def short_vertical(src, out, titulo, inicio=None, dur=30.0, pie="Video completo en el canal"):
    """Toma `dur` segundos del video (desde `inicio`, o un tercio si no se indica), lo pasa a 9:16 con fondo
    desenfocado y le pone el título arriba y una llamada abajo."""
    total = duracion(src)
    dur = min(dur, total) if total else dur
    if inicio is None:
        inicio = max(0.0, min(total * 0.33, total - dur)) if total else 0.0
    with tempfile.TemporaryDirectory() as d:
        png = os.path.join(d, "r.png")
        _rotulo(png, titulo, pie)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(inicio), "-t", str(dur), "-i", src, "-i", png,
                        "-filter_complex",
                        "[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                        "boxblur=24:4,eq=brightness=-0.12[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                        "[bg][fg]overlay=(W-w)/2:(H-h)/2[m];[m][1:v]overlay=0:0,format=yuv420p,fps=30[v]",
                        "-map", "[v]", "-map", "0:a?", "-af", f"afade=t=in:d=1,afade=t=out:st={max(0, dur - 2)}:d=2",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", out], check=True)
    return out
