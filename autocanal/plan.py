"""Lectura/escritura de info.txt y plan.txt (texto simple, editable a mano)."""
import glob, os, re

VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm", ".m4v")
AUDIO_EXT = (".m4a", ".mp3", ".aac", ".wav", ".opus", ".ogg", ".weba")

INFO_TPL = """# Completá esto (lo demás es opcional). Guardá y listo.
local:
visitante:
torneo:
resultado:
# de quién son las imágenes del partido (sale en pantalla y en la descripción)
imagenes:
# opcional: de qué hinchada son las reacciones (ej: River)
hinchas:
"""


def tsec(s):
    """'2:53' / '1:02:03' / '173.5' -> segundos."""
    s = str(s).strip().rstrip("?")
    if not s:
        raise ValueError("tiempo vacío")
    parts = s.split(":")
    v = 0.0
    for p in parts:
        v = v * 60 + float(p)
    return v


def fmt(t):
    t = round(max(0.0, float(t)), 1)
    h, m, sec = int(t // 3600), int(t % 3600 // 60), t % 60
    ss = f"{sec:04.1f}" if abs(sec - round(sec)) > 0.05 else f"{int(round(sec)):02d}"
    return f"{h}:{m:02d}:{ss}" if h else f"{m}:{ss}"


def _kv(lines):
    d = {}
    for ln in lines:
        if ":" in ln and not ln.lstrip().startswith("#"):
            k, v = ln.split(":", 1)
            d[k.strip().lower()] = v.strip()
    return d


def leer_info(carpeta):
    p = os.path.join(carpeta, "info.txt")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return {k: v for k, v in _kv([l for l in f if not l.lstrip().startswith("#")]).items() if v}


def archivos(carpeta):
    """Encuentra el partido, el audio aparte (si hay) y las reacciones."""
    todos = sorted(glob.glob(os.path.join(carpeta, "*")))
    vids = [f for f in todos if f.lower().endswith(VIDEO_EXT) and os.path.isfile(f)]
    reac = [f for f in vids if os.path.basename(f).lower().startswith(("reaccion", "reacción", "reac_", "reac-"))]
    rest = [f for f in vids if f not in reac and not os.path.basename(f).startswith("_")]
    partido = next((f for f in rest if os.path.basename(f).lower().startswith("partido")), None)
    if not partido and rest:
        partido = max(rest, key=os.path.getsize)
    auds = [f for f in todos if f.lower().endswith(AUDIO_EXT)]
    return partido, (auds[0] if auds else None), reac


def creador(f):
    """'reaccion_FRANKO BONETTO.mp4' -> 'FRANKO BONETTO'."""
    b = os.path.splitext(os.path.basename(f))[0]
    b = re.sub(r"^(reacci[oó]n|reac)[ _\-]*", "", b, flags=re.I)
    return b.replace("_", " ").strip() or "hincha"


# ---------------------------------------------------------------- plan.txt
CAB = """# PLAN DE {titulo}
# Editá lo que quieras y guardá. Después corré: autocanal shorts  /  autocanal reacciones
#  momento : segundo clave (el gol). Sirve para sincronizar reacciones.
#  tramos  : inicio+duración (m:ss+seg). Varios separados por coma (jugada + repetición).
#  tipo    : GOL, POLÉMICA, ROJA, PENAL, ATAJADA, JUGADA, LESIÓN... (sale en el cartel rojo)
#  texto / grande : las dos líneas de arriba del short
#  gancho  : cartel de intriga del arranque (vacío = automático, 'no' = sin gancho). '|' separa renglones
#  frase   : (opcional) texto grande amarillo en el video de reacción
#  hinchas : (opcional) cartel de la reacción, ej: LOS DE RIVER SE RÍEN 😂
#  reacciones : FUENTE=m:ss (segundo de la reacción donde se ve el 'momento'). '?' = aproximado, revisalo.
#  hacer   : no  -> se saltea este bloque
"""


def escribir_plan(path, titulo, fuentes, bloques):
    out = [CAB.format(titulo=titulo.upper())]
    if fuentes:
        out.append("[fuentes]")
        for k, (f, nombre) in fuentes.items():
            out.append(f"{k} = {os.path.basename(f)} | {nombre}")
        out.append("")
    for i, b in enumerate(bloques, 1):
        out.append(f"[{i}]")
        out.append(f"momento: {fmt(b['t'])}")
        out.append("tramos: " + ", ".join(f"{fmt(s)}+{d:g}" for s, d in b["tramos"]))
        for k in ("tipo", "texto", "grande", "gancho", "frase", "hinchas"):
            out.append(f"{k}: {b.get(k, '')}")
        if fuentes:
            rr = " ".join(f"{k}={'no' if v is None else fmt(v[0]) + ('' if v[1] else '?')}" for k, v in b.get("reac", {}).items())
            out.append(f"reacciones: {rr}")
        if b.get("nota"):
            out.append(f"# {b['nota']}")
        out.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def leer_plan(path):
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    secs = re.split(r"^\[([^\]]+)\]\s*$", txt, flags=re.M)
    fuentes, bloques = {}, []
    for name, body in zip(secs[1::2], secs[2::2]):
        lines = [l for l in body.splitlines() if l.strip() and not l.lstrip().startswith("#")]
        if name.strip().lower() == "fuentes":
            for l in lines:
                if "=" in l:
                    k, v = l.split("=", 1)
                    f, _, nombre = v.partition("|")
                    fuentes[k.strip()] = (f.strip(), nombre.strip() or f.strip())
            continue
        d = _kv(lines)
        if d.get("hacer", "").lower() in ("no", "n", "0"):
            continue
        b = {"n": name.strip(), "t": tsec(d["momento"]) if d.get("momento") else None, "tramos": []}
        for tr in (d.get("tramos") or "").split(","):
            tr = tr.strip()
            if not tr:
                continue
            if "+" in tr:
                s, du = tr.split("+", 1)
            elif "-" in tr and ":" in tr.split("-")[1]:
                s, e = tr.split("-", 1)
                du = tsec(e) - tsec(s)
            else:
                raise ValueError(f"tramo inválido en [{name}]: '{tr}' (usá m:ss+segundos)")
            b["tramos"].append((tsec(s), float(du)))
        if b["t"] is None and b["tramos"]:
            b["t"] = b["tramos"][0][0] + 8
        for k in ("tipo", "texto", "grande", "gancho", "frase", "hinchas"):
            b[k] = d.get(k, "")
        b["reac"] = {}
        for tok in (d.get("reacciones") or "").split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                if v.lower() != "no":
                    b["reac"][k] = (tsec(v), not v.endswith("?"))
        bloques.append(b)
    return fuentes, bloques
