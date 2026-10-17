"""Videos de reacción automáticos: short vertical (partido arriba, hincha abajo) y video horizontal largo."""
import json, os, tempfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from . import detect as D, media, mix, long as LG
from .textos import vs

MAX_BLOQUES = 4


def _align(t, r, pre, L, dm, dr):
    """Ventana del partido [sm, L] y de la reacción [sr, L] con el instante t<->r a `pre` s del inicio."""
    sm, sr = t - pre, r - pre
    if sr < 0:
        sm, sr, pre = sm - sr, 0.0, pre + sr
    if sm < 0:
        sr, sm, pre = sr - sm, 0.0, pre + sm
    L = max(3.0, min(L, dm - sm - 0.2, dr - sr - 0.2))
    return round(sm, 2), round(sr, 2), round(pre, 2), round(L, 2)


def _score(info):
    return vs(info).upper()


def plan_reacciones(bloques, fuentes):
    """[(bloque, [(K, r, exacto)...ordenados por confianza])] solo de bloques con reacción."""
    out = []
    for b in bloques:
        rs = [(k, v[0], v[1]) for k, v in b.get("reac", {}).items() if k in fuentes]
        rs.sort(key=lambda x: (not x[2]))
        if rs:
            out.append((b, rs))
    return out


def construir(carpeta, partido, fuentes, bloques, info, dest, log=print):
    """fuentes: {K: (archivo, nombre)}. Devuelve dict con rutas generadas."""
    src = {k: os.path.join(carpeta, f) for k, (f, _) in fuentes.items()}
    faltan = [f for f in src.values() if not os.path.exists(f)]
    if faltan:
        raise SystemExit(f"No encuentro: {', '.join(os.path.basename(f) for f in faltan)}")
    sel = plan_reacciones(bloques, fuentes)
    if not sel:
        raise SystemExit("Ningún bloque del plan tiene reacciones sincronizadas. Revisá la línea 'reacciones:' en plan.txt")
    dm = media.dur(partido)
    dr = {k: media.dur(f) for k, f in src.items()}
    log("  buscando caras para recortar…")
    st_short = {k: D.cara(f, 1080 / 1152) for k, f in src.items()}
    st_long = {k: D.cara(f, 630 / 1080) for k, f in src.items()}
    usados = []
    h = info.get("hinchas", "")
    quien = f"LOS DE {h.upper()}" if h else "LOS HINCHAS"
    credit_names = []

    # ------------------------------------------------ short vertical (primero goles/polémicas, en orden de partido)
    fuertes = ("GOL", "ROJA", "PENAL", "POLÉMICA", "VAR")
    orden = sorted(range(len(sel)), key=lambda i: (sel[i][0]["tipo"] not in fuertes and not sel[i][0].get("hinchas"), i))
    elegidos, n_bl = [], 0
    for i in orden:
        if n_bl >= MAX_BLOQUES:
            break
        elegidos.append(i)
        n_bl += len(sel[i][1])
    blocks = []
    for b, rs in [sel[i] for i in sorted(elegidos)]:
        for k, r, exacto in rs:
            if len(blocks) >= MAX_BLOQUES:
                break
            sm, sr, pre, L = _align(b["t"], r, 4.0, 12.0, dm, dr[k])
            nombre = fuentes[k][1]
            title = b["texto"] if b["texto"].upper() != vs(info, False).upper() else b["grande"]
            blocks.append({"title": title, "score": _score(info), "counter": b["tipo"],
                           "mood": b.get("hinchas") or f"ASÍ LO VIVIÓ {nombre.upper()}", "mood_color": "yel",
                           "top": [[sm, L]], "bottom": [[sr, L, k]], "goal_t": pre,
                           "subs": [[pre + 0.2, min(L, pre + 3.8), b["frase"]]] if b.get("frase") else []})
            usados.append(k)
            if nombre not in credit_names:
                credit_names.append(nombre)
    credit = "Reacciones: " + " · ".join(credit_names) + (f" · Imágenes: {info['imagenes']}" if info.get("imagenes") else "")
    tmp = os.path.join(dest, "_tmp_reaccion")
    os.makedirs(tmp, exist_ok=True)
    cfg_s = {"match": partido, "react": src[usados[0]], "strip": st_short[usados[0]],
             "sources": {k: {"src": src[k], "strip": st_short[k]} for k in src},
             "credit": credit, "hook": f"ASÍ REACCIONARON|{quien} 😱", "hook_dur": 2.2, "blocks": blocks}
    p = os.path.join(tmp, "short.json")
    json.dump(cfg_s, open(p, "w"), ensure_ascii=False, indent=1)
    log(f"  short de reacción ({len(blocks)} bloques)…")
    mix.main(p, os.path.join(tmp, "short"))
    out_short = os.path.join(dest, "reaccion_short.mp4")
    media.outro(os.path.join(tmp, "short", "mix.mp4"), out_short)

    # ------------------------------------------------ video horizontal
    goals = []
    for b, rs in sel:
        k, r, _ = rs[0]
        sm, sr, pre, L = _align(b["t"], r, 8.0, 20.0, dm, dr[k])
        title = b["texto"] if b["texto"].upper() != vs(info, False).upper() else b["grande"]
        g = {"title": title, "score": _score(info), "counter": b["tipo"], "tagA": "EN VIVO",
             "mood": b.get("hinchas") or f"ASÍ LO VIVIÓ {fuentes[k][1].upper()}", "mood_color": "yel",
             "A": {"left": [[sm, L]], "right": [[sr, L, k]], "goal_t": pre},
             "subs": [[pre + 0.2, min(L, pre + 3.8), b["frase"]]] if b.get("frase") else []}
        if len(rs) > 1:
            k2, r2, _ = rs[1]
            sm2, sr2, pre2, L2 = _align(b["t"], r2, 3.0, 14.0, dm, dr[k2])
            left_len = min(8.0, dm - sm2 - 0.2)
            g["B"] = {"left": [[sm2, left_len]], "right": [[sr2, L2, k2]]}
            g["moodB"] = f"Y {fuentes[k2][1].upper()}…"
        goals.append(g)
    b0, rs0 = sel[orden[0]]                 # el momento más fuerte abre el video y va en la miniatura
    k0, r0, _ = rs0[0]
    cfg_l = {"match": partido, "react": src[k0], "strip": st_long[k0],
             "sources": {k: {"src": src[k], "strip": st_long[k]} for k in src}, "credit": credit,
             "intro": {"bg": [max(0, b0["t"] - 2)], "right": [[max(0, r0 - 1.0), min(5.0, dr[k0] - max(0, r0 - 1.0) - 0.2), k0]],
                       "lines": [x for x in [f"ASÍ REACCIONARON {quien}", _score(info), (info.get("torneo") or "").upper()] if x]},
             "goals": goals}
    p2 = os.path.join(tmp, "long.json")
    json.dump(cfg_l, open(p2, "w"), ensure_ascii=False, indent=1)
    log(f"  video horizontal ({len(goals)} momentos)…")
    LG.main(p2, os.path.join(tmp, "long"))
    out_long = os.path.join(dest, "reaccion_horizontal.mp4")
    os.replace(os.path.join(tmp, "long", "long.mp4"), out_long)

    # ------------------------------------------------ portadas
    with tempfile.TemporaryDirectory() as d:
        mf = os.path.join(d, "m.jpg")
        media.frame(partido, b0["t"] + 1.0, mf)
        rfs = []
        for k in list(dict.fromkeys(usados))[:2]:
            rk = os.path.join(d, f"r{k}.jpg")
            rt = next(r for bb, rs in sel for kk, r, _ in rs if kk == k)
            media.frame(src[k], rt + 1.5, rk)
            rfs.append((rk, st_long[k]))
        mini = os.path.join(dest, "reaccion_horizontal_miniatura.jpg")
        miniatura(mf, rfs, mini, "ASÍ REACCIONARON", quien, _score(info))
    return {"short": out_short, "horizontal": out_long, "miniatura": mini, "creadores": credit_names}


def miniatura(match_frame, reacts, out, l1, l2, pill_txt):
    W, H = 1280, 720
    c = Image.new("RGBA", (W, H), LG.NAVY + (255,))
    m = Image.open(match_frame).convert("RGB").resize((W, H), Image.LANCZOS)
    c.paste(ImageEnhance.Brightness(m.filter(ImageFilter.GaussianBlur(2))).enhance(0.55), (0, 0))
    d = ImageDraw.Draw(c)
    slots = [W - 405, 0] if len(reacts) > 1 else [W - 405]
    for (img, (x, y, w, h)), sx in zip(reacts, slots):
        im = Image.open(img).convert("RGB").crop((x, y, x + w, y + h)).resize((405, 720), Image.LANCZOS)
        c.paste(ImageEnhance.Contrast(im.filter(ImageFilter.UnsharpMask(3, 90, 2))).enhance(1.1), (sx, 0))
        d.rectangle((sx - 8, 0, sx, H) if sx else (405, 0, 413, H), fill=LG.YEL)
    cx = (W - 405) / 2 if len(reacts) == 1 else W / 2
    mw = W - 405 - 80 if len(reacts) == 1 else 440
    LG.pill(c, cx, 70, "REACCIÓN", LG.WHITE, LG.RED + (255,), 40, anchor="c")
    y = LG.big(c, l1, cx, 170, 120, LG.WHITE, mw, stroke=8) + 30
    LG.big(c, l2, cx, y, 150, LG.YEL, mw, stroke=9)
    LG.pill(c, cx, 600, pill_txt, LG.NAVY, LG.YEL + (255,), 34, anchor="c")
    c.convert("RGB").save(out, quality=92)
