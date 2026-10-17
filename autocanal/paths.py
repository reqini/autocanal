"""Rutas del bot: todo relativo a la carpeta donde está instalado."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
FD = os.path.join(ASSETS, "fonts") + os.sep
FONT = FD + "DejaVuSans-Bold.ttf"
EMOJI = FD + "NotoColorEmoji.ttf"
OUTRO = os.path.join(ASSETS, "outro")
ICON = os.path.join(ASSETS, "icono.png")
MODELOS = os.path.join(ASSETS, "modelos")
PARTIDOS = os.environ.get("AUTOCANAL_PARTIDOS", os.path.join(ROOT, "partidos"))
CONFIG = os.path.join(ROOT, "config.json")

DEFAULT_CFG = {
    "canal": "Mi Canal de Deportes",
    "marca": "MI CANAL",
    "handle": "@MiCanal",
    "hashtags": ["Deportes", "Highlights"],
    "relax_canal": "Mi Canal para Dormir",
    "infantil_canal": "Mi Canal Infantil",
    "shorts_auto": 5,
    "duracion_short": 18,
    "privacidad": "public",
    "modelo_whisper": "ggml-small.bin",
}


def cfg():
    c = dict(DEFAULT_CFG)
    try:
        with open(CONFIG, encoding="utf-8") as f:
            c.update(json.load(f))
    except FileNotFoundError:
        pass
    return c
