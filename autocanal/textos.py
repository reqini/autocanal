"""Textos por defecto, títulos y descripciones para YouTube (plantillas, sin IA)."""
import re

EMO = {"GOL": "⚽", "ROJA": "🟥", "PENAL": "😱", "POLÉMICA": "🔥", "VAR": "📺", "ATAJADA": "🧤", "LESIÓN": "🚑",
       "JUGADA": "😱", "PALO": "😱", "OFFSIDE": "🚩"}
GRANDE = {"GOL": "¡GOOOL!", "ROJA": "¡ROJA!", "PENAL": "¿ERA PENAL?", "POLÉMICA": "¿QUÉ COBRÓ?", "VAR": "¿Y EL VAR?",
          "ATAJADA": "¡LA SACÓ!", "PALO": "¡AL PALO!", "LESIÓN": "PREOCUPACIÓN", "OFFSIDE": "¿ERA OFFSIDE?",
          "JUGADA": "¡MIRÁ ESTO!"}
# cartel de intriga del arranque (adelanto de 1,8 s del momento clave)
GANCHO = {"GOL": "¿ENTRA O NO ENTRA? 👀|MIRALO HASTA EL FINAL", "JUGADA": "¿QUÉ PASÓ ACÁ? 😱|MIRALO HASTA EL FINAL",
          "ROJA": "SE PUDRIÓ TODO 🔥|MIRÁ CÓMO TERMINA", "POLÉMICA": "¿QUÉ COBRÓ? 🔥|VOS DECIDÍS",
          "PENAL": "¿ERA PENAL? 👀|VOS DECIDÍS", "ATAJADA": "NO LO VAS A CREER 😱|MIRALO HASTA EL FINAL",
          "VAR": "¿Y EL VAR? 👀|VOS DECIDÍS", "PALO": "¡CASI! 😱|MIRALO HASTA EL FINAL",
          "LESIÓN": "MOMENTO DE TENSIÓN 😟|MIRÁ LO QUE PASÓ", "OFFSIDE": "¿ERA OFFSIDE? 👀|VOS DECIDÍS"}
# títulos con intriga cuando no hay texto propio (rotan para no repetir)
INTRIGA = {"GOL": ["¡Mirá cómo terminó esta jugada!", "Nadie lo esperaba:", "¡Qué definición!", "¡Tremendo gol!", "Así se festejó:"],
           "JUGADA": ["¡Esperá al final!", "¿Viste lo que pasó acá?", "Mirá esta jugada:", "¡Qué momento!",
                      "¡Atención a esta jugada!"],
           "ROJA": ["Se pudrió todo:"], "ATAJADA": ["¿Cómo la sacó?"], "PENAL": ["¿Era penal?"],
           "POLÉMICA": ["¿Qué cobró el árbitro?"], "VAR": ["¿Y el VAR?"]}


def gancho(b):
    g = (b.get("gancho") or "").strip()
    if g.lower() in ("no", "n", "0"):
        return None
    return g or GANCHO.get(b.get("tipo", "JUGADA"), GANCHO["JUGADA"])


def vs(info, res=True):
    l, v = info.get("local", "Local"), info.get("visitante", "Visitante")
    r = info.get("resultado", "") if res else ""
    return f"{l} {r} {v}" if r else f"{l} vs {v}"


def defaults(b, info):
    """Completa texto/grande si vienen vacíos."""
    tipo = (b.get("tipo") or "JUGADA").upper()
    b["tipo"] = tipo
    if not b.get("texto"):
        b["texto"] = vs(info, False).upper()
    if not b.get("grande"):
        b["grande"] = GRANDE.get(tipo, "¡MIRÁ ESTO!")
    return b


STOP = {"la", "el", "los", "las", "un", "una", "cabeza", "penal", "tiro", "afuera", "nuevo", "vuelta", "media",
        "chilena", "volea", "zurda", "derecha", "palo", "lejos", "contra", "local", "visitante"}


def _nice(text, info):
    """MAYÚSCULAS -> 'Gol de Adson' respetando nombres propios conocidos."""
    keep = {w.lower(): w for k in ("local", "visitante", "torneo")
            for w in re.findall(r"[\wÁÉÍÓÚÑáéíóúñ]+", info.get(k, ""))}
    keep.update({"var": "VAR", "atr": "ATR"})
    words = text.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        core = re.sub(r"[^\wáéíóúñ]", "", lw)
        if core in keep:
            lw = lw.replace(core, keep[core])
        elif i > 0 and out[-1].lower().strip("¡¿") in ("de", "a", "del") and core not in STOP and core.isalpha():
            lw = lw.replace(core, core.capitalize())
        out.append(lw)
    s = " ".join(out)
    m = re.search(r"[^\W\d_]", s)
    return s[:m.start()] + s[m.start()].upper() + s[m.start() + 1:] if m else s


def _cut(t, n=60):
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "…"


def _tags(info, cfg, extra=()):
    tags = []
    for k in ("local", "visitante"):
        if info.get(k):
            tags.append("#" + re.sub(r"\W", "", info[k].title()))
    tags += ["#" + h.lstrip("#") for h in list(extra) + cfg.get("hashtags", [])]
    return " ".join(dict.fromkeys(tags))


def short_meta(b, info, cfg):
    tipo = b["tipo"]
    gran = b["grande"]
    main = _nice(b["texto"], info)
    if b["texto"].upper() == vs(info, False).upper():
        opts = INTRIGA.get(tipo, INTRIGA["JUGADA"])
        try:
            k = int(b.get("n", 1)) - 1
        except ValueError:
            k = 0
        title = f"{opts[k % len(opts)]} {vs(info, False)} {EMO.get(tipo, '')}"
    else:
        title = f"{main} | {vs(info)} {EMO.get(tipo, '')}"
    title = _cut(title.strip())
    desc = [f"{main} — {_nice(gran, info)}", f"{info.get('local', '')} vs {info.get('visitante', '')}"
            + (f" · {info['torneo']}" if info.get("torneo") else "") + (f" · Resultado: {info['resultado']}" if info.get("resultado") else ""),
            ""]
    if info.get("imagenes"):
        desc.append(f"Imágenes: {info['imagenes']}. Clip breve con fines informativos y de comentario.")
    desc += [f"👍 Dale me gusta y suscribite a {cfg['canal']} para más fútbol argentino todos los días.", "",
             _tags(info, cfg, ["Shorts"])]
    return title, "\n".join(desc)


def reac_meta(info, cfg, creadores, horizontal=False):
    h = info.get("hinchas")
    who = f"LOS HINCHAS DE {h.upper()}" if h else "LOS HINCHAS"
    de = f" de {h}" if h else ""
    title = _cut(f"Hinchas{de} reaccionan | {vs(info)} 😂")
    if horizontal:
        title = _cut(f"Así lo vivieron los hinchas{de} | {vs(info)}")
    desc = [f"Así vivieron {who.lower()} el {vs(info)}" + (f" ({info['torneo']})" if info.get("torneo") else "") + ".", "",
            "Reacciones originales de: " + ", ".join(creadores) + ". Todo el crédito a sus creadores — andá a ver sus canales.",
            ]
    if info.get("imagenes"):
        desc.append(f"Imágenes del partido: {info['imagenes']}.")
    desc += ["Video de comentario y reacción, con fines informativos.", "",
             f"👍 Dale me gusta y suscribite a {cfg['canal']}. ¿Y vos de qué lado estás? Dejalo en los comentarios.", "",
             _tags(info, cfg, [] if horizontal else ["Shorts"])]
    return title, "\n".join(desc)
