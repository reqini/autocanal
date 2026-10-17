"""Opcional: escucha al relator con whisper.cpp (local, gratis) para poner nombres y tipo de jugada.
Si whisper no está instalado, no hace nada y el bot usa textos genéricos."""
import os, re, shutil, subprocess, tempfile
from .paths import MODELOS, cfg

KEYS = [(r"\bgo{2,}l|\bgolazo|\bgol de\b", "GOL"), (r"\bpenal", "PENAL"), (r"\broja\b|\bexpuls", "ROJA"),
        (r"\bvar\b", "VAR"), (r"\boffside|fuera de juego|posici[oó]n adelantada", "OFFSIDE"),
        (r"\bpalo\b|travesa[ñn]o", "PALO"), (r"\batajad|\bla sac[oó]\b|\btap[oó]\b", "ATAJADA"),
        (r"\blesi[oó]n|lesionad|camilla", "LESIÓN")]
NOMBRE = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?"


def disponible():
    exe = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
    model = os.path.join(MODELOS, cfg().get("modelo_whisper", "ggml-small.bin"))
    return (exe, model) if exe and os.path.exists(model) else None


def escuchar(video, t0, d=14.0):
    w = disponible()
    if not w:
        return ""
    exe, model = w
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "a.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{max(0, t0):.2f}", "-t", str(d), "-i", video,
                        "-ac", "1", "-ar", "16000", wav], check=True)
        try:
            r = subprocess.run([exe, "-m", model, "-l", "es", "-nt", "-np", "-f", wav], capture_output=True,
                               text=True, timeout=180)
            return " ".join(r.stdout.split())
        except Exception:
            return ""


def interpretar(texto):
    """-> (tipo | None, texto_corto | None)"""
    if not texto:
        return None, None
    low = texto.lower()
    tipo = next((t for rx, t in KEYS if re.search(rx, low)), None)
    m = re.search(r"\b[Gg]o+l(?:azo)?,?\s+(?:de|del)\s+(" + NOMBRE + ")", texto)
    if m:
        return "GOL", f"GOL DE {m.group(1).upper()}"
    return tipo, None
