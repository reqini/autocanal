"""AutoCanal — agente de YouTube open source: shorts, reacciones y videos para tus canales, todo local.

  autocanal nuevo NOMBRE        crea la carpeta del partido (partidos/NOMBRE) con info.txt para completar
  autocanal analizar [CARPETA]  busca los mejores momentos y sincroniza reacciones -> plan.txt + revisar/
  autocanal shorts [CARPETA]    hace los shorts del plan (con textos, cierre animado y portadas) -> listo/
  autocanal reacciones [CARP.]  hace el short de reacción y el video horizontal -> listo/
  autocanal todo [CARPETA]      analizar + shorts + reacciones (si hay archivos reaccion_*)
  autocanal vigilar             queda mirando partidos/: cuando aparece un partido nuevo, hace todo solo
  autocanal subir [CARPETA]     sube lo de listo/ a YouTube con la API oficial (opcional, ver GUIA)
  autocanal servicio instalar   deja 'vigilar' corriendo siempre (arranca con la Mac) | servicio quitar
  autocanal prueba              prueba rápida con un video sintético

  AUTÓNOMO
  autocanal archivo VIDEO.mp4 ["Título"]   sube un video/short propio al canal de deportes (+ short de 30 s si es largo)
  autocanal auto PARTIDO.mp4 ["Boca vs River"] [REACCION.mp4]   hace TODO solo (shorts + reacciones) y lo sube
  autocanal web                 abre la interfaz en el navegador (arrastrás el video y listo)

  DORMÍ PROFUNDO (canal de relajación, sonidos originales, pantalla negra)
  autocanal relax [blanco|lluvia|ambiente] [horas]   crea el video de hoy (sin nada: rota el sonido solo)
  autocanal relax subir         sube lo pendiente al canal para dormir (API oficial)
  autocanal relax diario        crear + subir + limpiar viejos (lo que corre solo cada día)
  autocanal relax servicio      lo deja programado todos los días (hora en config.json) | relax servicio quitar
  autocanal relax marca         regenera foto de perfil y banner del canal
  autocanal relax archivo VIDEO.mp4 ["Título"]   sube un video propio al canal para dormir (+ shorts)
  autocanal lolo nuevo          arma el short de Lolo de hoy (historia nueva cada día)
  autocanal lolo subir          sube lo pendiente al canal infantil
  autocanal lolo diario         arma + sube (lo que corre solo cada día)
  autocanal lolo servicio       lo deja programado todos los días (17:10) | lolo servicio quitar
  autocanal lolo shorts3d [letras numeros colores]   shorts 3D interactivos (≈1 min) listos para subir
  autocanal lolo aprende vocales|numeros|abecedario|letras|colores [3d]   canción educativa (3D con Blender: con juegos interactivos)
  autocanal lolo historia HISTORIA.md [N]   arma N shorts encadenados desde tu historia .md y los sube
  autocanal lolo archivo VIDEO.mp4 ["Título"]   sube un video infantil propio (+ short vertical si es largo)

CARPETA: nombre dentro de partidos/ o ruta. Si no la ponés, usa la última que tocaste.
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, time, traceback, unicodedata
from .paths import PARTIDOS, ROOT, cfg
from . import plan as P, textos as T, media, detect as D, relator

TIPO_COLOR = {"GOL": "yel", "ROJA": "red", "PENAL": "red", "POLÉMICA": "red", "VAR": "orange", "ATAJADA": "cel",
              "LESIÓN": "orange", "JUGADA": "cel", "OFFSIDE": "orange", "PALO": "cel"}


LOG_HOOK = None
SUBIR = None          # None = lo que diga config.json ("subir_auto"); True/False lo fuerza (interfaz web)


def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    if LOG_HOOK:
        LOG_HOOK(msg)


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "video"


def carpeta_de(arg):
    if arg:
        for c in (arg, os.path.join(PARTIDOS, arg)):
            if os.path.isdir(c):
                return os.path.abspath(c)
        raise SystemExit(f"No existe la carpeta '{arg}' (ni en {PARTIDOS})")
    cs = [c for c in glob.glob(os.path.join(PARTIDOS, "*")) if os.path.isdir(c) and not os.path.basename(c).startswith("_")]
    if not cs:
        raise SystemExit("No hay partidos. Creá uno con: autocanal nuevo NOMBRE")
    return max(cs, key=lambda c: max([os.path.getmtime(f) for f in glob.glob(os.path.join(c, "*"))] + [os.path.getmtime(c)]))


def preparar(carpeta):
    """Devuelve (ruta del partido con audio, reacciones, info). Une audio aparte si hace falta."""
    partido, audio, reac = P.archivos(carpeta)
    if not partido:
        raise SystemExit(f"No hay video del partido en {carpeta}. Poné el archivo (ej. partido.mp4) en esa carpeta.")
    if audio and not media.has_audio(partido):
        unido = os.path.join(carpeta, "_partido_con_audio.mp4")
        if not os.path.exists(unido) or os.path.getmtime(unido) < os.path.getmtime(partido):
            log(f"• Uniendo video + audio ({os.path.basename(audio)})…")
            media.mux(partido, audio, unido)
        partido = unido
    info = P.leer_info(carpeta)
    if not info.get("local"):
        nombre = os.path.basename(carpeta)
        partes = re.split(r"[-_ ]+vs?[-_ ]+|[-_]", nombre, maxsplit=1)
        info.setdefault("local", partes[0].title())
        if len(partes) > 1:
            info.setdefault("visitante", partes[1].replace("-", " ").title())
    return partido, reac, info


# ---------------------------------------------------------------- analizar
def analizar(carpeta, n=None):
    c = cfg()
    n = n or c["shorts_auto"]
    partido, reac, info = preparar(carpeta)
    log(f"• Analizando {os.path.basename(partido)} ({media.dur(partido) / 60:.0f} min)…")
    if media.has_audio(partido):
        moms = D.momentos(partido, n)
        nota = None
    else:
        moms = D.parejo(partido, n)
        nota = "SIN AUDIO: tiempos repartidos parejo, revisalos en revisar/"
        log("  ⚠ el video no tiene audio: no puedo detectar goles por el relato. Revisá los tiempos del plan.")
    usa_relator = relator.disponible()
    if usa_relator:
        log("  escuchando al relator (whisper local)…")
    fuentes = {}
    for i, f in enumerate(reac):
        fuentes[chr(65 + i)] = (os.path.basename(f), P.creador(f))
    cache = os.path.join(carpeta, ".cache")
    rev = os.path.join(carpeta, "revisar")
    shutil.rmtree(rev, ignore_errors=True)
    os.makedirs(rev)
    bloques = []
    for k, m in enumerate(moms, 1):
        b = {"t": m["t"], "tramos": [(m["inicio"], m["dur"])], "tipo": m["tipo"], "frase": "", "hinchas": ""}
        if usa_relator:
            tipo, txt = relator.interpretar(relator.escuchar(partido, m["t"] - 2))
            if tipo:
                b["tipo"] = tipo
            if txt:
                b["texto"] = txt
        T.defaults(b, info)
        if fuentes:
            b["reac"] = {}
            for K, (f, _) in fuentes.items():
                r, conf = D.sync(partido, os.path.join(carpeta, f), m["t"], cache)
                if r is None and media.dur(os.path.join(carpeta, f)) < 90 and b["tipo"] == "GOL" \
                        and not any(bb.get("reac", {}).get(K) for bb in bloques):
                    r, conf = 1.0, 0.0      # clip corto de redes: suelen arrancar justo antes del gol (aprox.)
                b["reac"][K] = None if r is None else (r, conf > 0)
        if nota:
            b["nota"] = nota
        bloques.append(b)
        media.hoja(partido, m["inicio"], m["dur"], os.path.join(rev, f"{k:02d}_{P.fmt(m['t']).replace(':', 'm')}.jpg"))
    P.escribir_plan(os.path.join(carpeta, "plan.txt"), f"{info.get('local', '')} vs {info.get('visitante', '')}",
                    fuentes, bloques)
    log(f"✓ plan.txt listo con {len(bloques)} momentos" + (f" y {len(fuentes)} reacciones" if fuentes else "")
        + f". Hojas para revisar en {rev}")
    for k, b in enumerate(bloques, 1):
        rr = ""
        if fuentes:
            rr = "  reac: " + ", ".join(f"{K}={'—' if v is None else P.fmt(v[0]) + ('' if v[1] else '?')}" for K, v in b["reac"].items())
        log(f"   [{k}] {P.fmt(b['t']):>7}  {b['tipo']:<8} {b['texto']} / {b['grande']}{rr}")
    return bloques


# ---------------------------------------------------------------- publicar
def _pub_load(dest):
    p = os.path.join(dest, "publicar.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def _pub_save(dest, items):
    items.sort(key=lambda x: x["archivo"])
    json.dump(items, open(os.path.join(dest, "publicar.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(dest, "publicar.txt"), "w", encoding="utf-8") as f:
        f.write("PARA PUBLICAR — copiá y pegá en YouTube Studio (Público · No es para niños)\n\n")
        for it in items:
            f.write("=" * 70 + f"\nARCHIVO: {it['archivo']}\n" + (f"PORTADA: {it['portada']}\n" if it.get("portada") else "")
                    + (f"SUBIDO: {it['subido']}\n" if it.get("subido") else "")
                    + f"\nTÍTULO:\n{it['titulo']}\n\nDESCRIPCIÓN:\n{it['descripcion']}\n\n")


def _pub_add(dest, new):
    items = [i for i in _pub_load(dest) if i["archivo"] not in {n["archivo"] for n in new}]
    _pub_save(dest, items + new)


def _chico(dest, f):
    if os.path.getsize(f) > 9.5 * 1048576:
        os.makedirs(os.path.join(dest, "10mb"), exist_ok=True)
        media.shrink(f, os.path.join(dest, "10mb", os.path.basename(f)))


# ---------------------------------------------------------------- shorts
def shorts(carpeta):
    from .cover import make as portada
    c = cfg()
    pp = os.path.join(carpeta, "plan.txt")
    if not os.path.exists(pp):
        analizar(carpeta)
    partido, _, info = preparar(carpeta)
    _, bloques = P.leer_plan(pp)
    dest = os.path.join(carpeta, "listo")
    os.makedirs(dest, exist_ok=True)
    nuevos = []
    for i, b in enumerate(bloques, 1):
        T.defaults(b, info)
        if not b["tramos"]:
            continue
        name = f"{i:02d}_{slug(b['texto'] if b['texto'].upper() != T.vs(info, False).upper() else b['grande'] + '-' + T.vs(info, False))}"
        log(f"• Short {i}/{len(bloques)}: {b['texto']} / {b['grande']}")
        with tempfile.TemporaryDirectory() as d:
            raw = os.path.join(d, "raw.mp4")
            media.short(partido, b["tramos"], raw, b["texto"], b["grande"], b["tipo"], info.get("imagenes"),
                        gancho=T.gancho(b) if c.get("gancho", True) else None, t_clave=b["t"])
            out = os.path.join(dest, name + ".mp4")
            media.outro(raw, out)
            fr = os.path.join(d, "f.jpg")
            media.frame(partido, (b["t"] or b["tramos"][0][0]) + 0.5, fr)
            cov = os.path.join(dest, name + "_portada.jpg")
            portada(fr, 960, cov, b["tipo"], b["texto"], b["grande"], (info.get("torneo") or "").upper(), c["handle"],
                    TIPO_COLOR.get(b["tipo"], "red"))
        _chico(dest, out)
        tit, desc = T.short_meta(b, info, c)
        nuevos.append({"archivo": os.path.basename(out), "tipo": "short", "titulo": tit, "descripcion": desc,
                       "portada": os.path.basename(cov)})
    _pub_add(dest, nuevos)
    log(f"✓ {len(nuevos)} shorts en {dest}  (títulos y descripciones en publicar.txt)")


# ---------------------------------------------------------------- reacciones
def reacciones(carpeta):
    from . import reac
    c = cfg()
    pp = os.path.join(carpeta, "plan.txt")
    if not os.path.exists(pp):
        analizar(carpeta)
    partido, _, info = preparar(carpeta)
    fuentes, bloques = P.leer_plan(pp)
    if not fuentes:
        log("• No hay reacciones (archivos que empiecen con 'reaccion_'). Salteo.")
        return
    for b in bloques:
        T.defaults(b, info)
    dest = os.path.join(carpeta, "listo")
    os.makedirs(dest, exist_ok=True)
    log("• Armando videos de reacción…")
    r = reac.construir(carpeta, partido, fuentes, bloques, info, dest, log)
    _chico(dest, r["short"])
    _chico(dest, r["horizontal"])
    ts, ds = T.reac_meta(info, c, r["creadores"])
    th, dh = T.reac_meta(info, c, r["creadores"], horizontal=True)
    _pub_add(dest, [{"archivo": "reaccion_short.mp4", "tipo": "short", "titulo": ts, "descripcion": ds},
                    {"archivo": "reaccion_horizontal.mp4", "tipo": "horizontal", "titulo": th, "descripcion": dh,
                     "portada": os.path.basename(r["miniatura"])}])
    shutil.rmtree(os.path.join(dest, "_tmp_reaccion"), ignore_errors=True)
    log(f"✓ Reacciones listas en {dest}")


def todo(carpeta, n=None):
    t0 = time.time()
    if n or not os.path.exists(os.path.join(carpeta, "plan.txt")):
        analizar(carpeta, n)
    shorts(carpeta)
    reacciones(carpeta)
    log(f"✓ Todo listo en {time.time() - t0:.0f} s → {os.path.join(carpeta, 'listo')}")
    if (cfg().get("subir_auto", True) if SUBIR is None else SUBIR) and os.path.exists(os.path.join(ROOT, "client_secret.json")):
        from .subir import subir
        subir(carpeta, log)


# ---------------------------------------------------------------- nuevo / vigilar / servicio
def nuevo(nombre):
    c = os.path.join(PARTIDOS, nombre)
    os.makedirs(c, exist_ok=True)
    ip = os.path.join(c, "info.txt")
    if not os.path.exists(ip):
        partes = re.split(r"\s+vs?\s+|-vs?-|_vs?_", nombre, maxsplit=1)
        txt = P.INFO_TPL
        if len(partes) == 2:
            txt = txt.replace("local: \n", f"local: {partes[0].strip().title()}\n").replace(
                "visitante: \n", f"visitante: {partes[1].strip().title()}\n")
        open(ip, "w", encoding="utf-8").write(txt)
    log(f"✓ Carpeta lista: {c}\n  1) Poné adentro el video del partido (partido.mp4) y, si tenés, reaccion_<creador>.mp4\n"
        f"  2) Completá info.txt\n  3) autocanal todo \"{nombre}\"")
    if sys.platform == "darwin":
        subprocess.run(["open", c])
        subprocess.run(["open", "-e", ip])


def avisar(msg):
    log(msg)
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "AutoCanal" sound name "Glass"'])


def vigilar(espera=None):
    espera = espera or cfg().get("espera_vigilar", 120)
    os.makedirs(PARTIDOS, exist_ok=True)
    log(f"👀 Vigilando {PARTIDOS} (arranco cuando una carpeta queda quieta {espera} s). Ctrl+C para cortar.")
    visto = {}
    while True:
        for c in sorted(glob.glob(os.path.join(PARTIDOS, "*"))):
            if not os.path.isdir(c) or os.path.basename(c).startswith("_"):
                continue
            if os.path.exists(os.path.join(c, "listo", ".hecho")) or os.path.exists(os.path.join(c, ".error")):
                continue
            partido, _, _ = P.archivos(c)
            if not partido:
                continue
            firma = tuple((f, os.path.getsize(f), os.path.getmtime(f)) for f in sorted(glob.glob(os.path.join(c, "*")))
                          if os.path.isfile(f))
            prev = visto.get(c)
            if not prev or prev[0] != firma:
                visto[c] = (firma, time.time())
                continue
            if time.time() - prev[1] < espera:
                continue
            nombre = os.path.basename(c)
            avisar(f"Arranco con {nombre}…")
            try:
                todo(c)
                open(os.path.join(c, "listo", ".hecho"), "w").write(time.ctime())
                avisar(f"✅ {nombre}: videos listos")
                if sys.platform == "darwin":
                    subprocess.run(["open", os.path.join(c, "listo")])
            except BaseException as e:
                if isinstance(e, KeyboardInterrupt):
                    raise
                open(os.path.join(c, ".error"), "w").write(traceback.format_exc())
                avisar(f"❌ {nombre}: falló (mirá .error en la carpeta)")
        time.sleep(20)


AGENTS = os.path.expanduser("~/Library/LaunchAgents")
SERV = {"atr": ("com.autocanal.deportes", ["vigilar"], "bot.log"),
        "relax": ("com.autocanal.dormir", ["relax", "diario"], "relax.log"),
        "lolo": ("com.autocanal.infantil", ["lolo", "diario"], "lolo.log")}


def servicio(accion, cual="atr"):
    if sys.platform != "darwin":
        raise SystemExit("El servicio es para macOS.")
    label, args, logf = SERV[cual]
    plist = os.path.join(AGENTS, label + ".plist")
    if accion == "instalar":
        os.makedirs(AGENTS, exist_ok=True)
        hora = cfg().get(f"{cual}_hora", {"relax": "03:10", "lolo": "17:10"}.get(cual))
        if cual in ("relax", "lolo"):
            hh, mm = hora.split(":")
            when = (f"<key>StartCalendarInterval</key><dict><key>Hour</key><integer>{int(hh)}</integer>"
                    f"<key>Minute</key><integer>{int(mm)}</integer></dict>")
        else:
            when = "<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>"
        prog = "".join(f"<string>{a}</string>" for a in [os.path.join(ROOT, "bin", "atr")] + args)
        open(plist, "w").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>Label</key><string>{label}</string>
 <key>ProgramArguments</key><array>{prog}</array>
 {when}
 <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
 <key>StandardOutPath</key><string>{os.path.join(ROOT, logf)}</string>
 <key>StandardErrorPath</key><string>{os.path.join(ROOT, logf)}</string>
</dict></plist>
""")
        subprocess.run(["launchctl", "unload", plist], capture_output=True)
        subprocess.run(["launchctl", "load", "-w", plist], check=True)
        if cual in ("relax", "lolo"):
            canal = cfg()["relax_canal"] if cual == "relax" else cfg()["infantil_canal"]
            log(f"✓ Listo: todos los días a las {hora} se crea y se sube un video nuevo "
                f"de {canal} (si la Mac está dormida, lo hace al despertarse). Log: {logf}")
        else:
            log("✓ Servicio instalado: el bot vigila partidos/ siempre (también al prender la Mac). Log: bot.log")
    else:
        subprocess.run(["launchctl", "unload", "-w", plist], capture_output=True)
        if os.path.exists(plist):
            os.remove(plist)
        log("✓ Servicio quitado.")


def relax_cmd(rest):
    from . import relax as R
    from .subir import subir_lista
    sub = rest[0] if rest else "nuevo"
    dest = os.path.join(R.dir_relax(), "listo")
    if sub in R.NOMBRE or sub == "nuevo":
        R.nuevo(None if sub == "nuevo" else sub, rest[1] if len(rest) > 1 else None, log)
    elif sub == "subir":
        subir_lista(dest, "relax", log, categoria="10")
    elif sub == "archivo":
        # autocanal relax archivo RUTA.mp4 ["Título"] -> sube un video propio al canal para dormir
        n, rest = _num(rest)
        if len(rest) < 2:
            raise SystemExit('Uso: autocanal relax archivo ~/Downloads/video.mp4 ["Título del video"] [cantidad de shorts]')
        src = os.path.abspath(os.path.expanduser(rest[1]))
        if not os.path.isfile(src):
            raise SystemExit(f"No encuentro el archivo: {src}")
        os.makedirs(dest, exist_ok=True)
        base = os.path.basename(src)
        dst = os.path.join(dest, base)
        if not os.path.exists(dst):
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
        nombre = re.sub(r"[-_]+", " ", os.path.splitext(base)[0]).strip()
        titulo = rest[2] if len(rest) > 2 else f"{nombre.capitalize()} | Pantalla Negra 🌙"
        desc = (f"{titulo}\n\n🌙 Pantalla oscura para que la luz no te despierte. Usalo a volumen bajo.\n"
                f"🔔 Suscribite a {cfg()['relax_canal']}: un video nuevo para dormir todos los días.\n\n"
                "#Dormir #PantallaNegra #MusicaParaDormir #Relajacion")
        pj = os.path.join(dest, "publicar.json")
        items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
        items = [i for i in items if i["archivo"] != base] + [
            {"archivo": base, "tipo": "largo", "titulo": titulo[:100], "descripcion": desc, "categoria": "10",
             "tags": ["música para dormir", "pantalla negra", "dormir", "relajación", nombre.lower()]}]
        try:
            from .recorte import duracion
            tot = duracion(dst)
            n = n if n is not None else (1 if tot > 90 else 0)
            corto = re.sub(r"[^\w\sáéíóúñÁÉÍÓÚÑ]", "", titulo).split("Pantalla")[0].strip()[:60] or nombre
            for k, ini in enumerate(_inicios(tot, n) if tot > 35 else []):
                sh = os.path.splitext(base)[0] + f"_short{k + 1}.mp4"
                log(f"• Armando short {k + 1}/{n} para promocionarlo…")
                R.short("ambiente", None, len(base) + k * 17, dst, os.path.join(dest, sh), inicio=ini, titulo=corto)
                it = R.item_short(sh, corto)
                if n > 1:
                    it["titulo"] = it["titulo"].replace(" #shorts", f" ({k + 1}) #shorts")
                items = [i for i in items if i["archivo"] != sh] + [it]
        except Exception as e:
            log(f"  (no pude armar el short: {str(e)[:100]})")
        json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"• Subiendo «{titulo}» a {cfg()['relax_canal']}…")
        subir_lista(dest, "relax", log, categoria="10")
    elif sub == "conectar":
        from .subir import cliente
        cliente("relax", log)
        log(f"✓ {cfg()['relax_canal']} conectado: el bot ya puede subir videos a ese canal.")
    elif sub == "diario":
        try:
            R.nuevo(log=log)
            subir_lista(dest, "relax", log, categoria="10")
            R.limpiar()
            avisar(f"🌙 {cfg()['relax_canal']}: video de hoy subido")
        except BaseException as e:
            if isinstance(e, KeyboardInterrupt):
                raise
            avisar(f"❌ {cfg()['relax_canal']} falló: {str(e)[:80]}")
            raise
    elif sub == "marca":
        m = os.path.join(R.dir_relax(), "marca")
        os.makedirs(m, exist_ok=True)
        R.perfil(os.path.join(m, "foto_perfil.jpg"))
        R.banner(os.path.join(m, "banner.jpg"))
        log(f"✓ Foto de perfil y banner en {m}")
    elif sub == "servicio":
        servicio(rest[1] if len(rest) > 1 else "instalar", "relax")
    else:
        raise SystemExit("Uso: autocanal relax [blanco|lluvia|ambiente] [horas] | subir | diario | marca | servicio [quitar]")


# ---------------------------------------------------------------- prueba
def prueba():
    c = os.path.join(PARTIDOS, "_prueba")
    shutil.rmtree(c, ignore_errors=True)
    os.makedirs(c)
    log("• Generando video de prueba (40 s)…")
    tone = "0.06*sin(2*PI*220*t)*between(t,24,30)+0.05*sin(2*PI*440*t)*between(t,24,30)"
    media.ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=40", "-f", "lavfi", "-i",
             f"aevalsrc='0.02*(random(0)-0.5)+{tone}':s=44100:d=40", "-shortest", "-c:v", "libx264", "-preset",
             "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", os.path.join(c, "partido.mp4"))
    open(os.path.join(c, "info.txt"), "w").write("local: Prueba\nvisitante: Test\nimagenes: \n")
    analizar(c, 1)
    shorts(c)
    outs = glob.glob(os.path.join(c, "listo", "*.mp4"))
    if not outs:
        raise SystemExit("✗ La prueba no generó videos.")
    log(f"✓ PRUEBA OK — el bot funciona. Mirá el resultado en {os.path.join(c, 'listo')}")
    if sys.platform == "darwin":
        subprocess.run(["open", os.path.join(c, "listo")])


YT = re.compile(r"(youtube\.com|youtu\.be|tiktok\.com|instagram\.com|twitch\.tv)", re.I)


def _num(rest):
    """Separa un número suelto (cantidad de shorts) del resto de los argumentos."""
    n = next((int(x) for x in rest if re.fullmatch(r"\d{1,2}", x)), None)
    return n, [x for x in rest if not re.fullmatch(r"\d{1,2}", x)]


def _inicios(tot, n, dur=30.0):
    return [max(0.0, min(tot - dur - 1, tot * (k + 1) / (n + 1) - dur / 2)) for k in range(n)]


def archivo_atr(rest):
    """autocanal archivo VIDEO.mp4 ["Título"] -> sube un video propio ya editado al canal de deportes
    (si es largo, también recorta y sube un short vertical de 30 s)."""
    from .subir import subir_lista
    from .recorte import duracion, short_vertical
    n, rest = _num(rest)
    if not rest:
        raise SystemExit('Uso: autocanal archivo ~/Desktop/video.mp4 ["Título del video"] [cantidad de shorts]')
    src = os.path.abspath(os.path.expanduser(rest[0]))
    if not os.path.isfile(src):
        raise SystemExit(f"No encuentro el archivo: {src}")
    dest = os.path.join(PARTIDOS, "_propios", "listo")
    os.makedirs(dest, exist_ok=True)
    base = os.path.basename(src)
    dst = os.path.join(dest, base)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    nombre = re.sub(r"[-_]+", " ", os.path.splitext(base)[0]).strip()
    titulo = rest[1] if len(rest) > 1 else f"{nombre.capitalize()} ⚽🔥"
    desc = f"{titulo}\n\n⚽ Suscribite a {cfg()['canal']}.\n\n" + " ".join("#" + h for h in cfg()["hashtags"]) + " #Shorts"
    tags = ["futbol argentino", "futbol", "goles", nombre.lower()]
    tot = duracion(dst)
    pj = os.path.join(dest, "publicar.json")
    items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
    items = [i for i in items if i["archivo"] != base] + [
        {"archivo": base, "tipo": "largo" if tot > 180 else "short", "titulo": titulo[:100], "descripcion": desc,
         "tags": tags}]
    n = n if n is not None else (1 if tot > 70 else 0)
    corto = re.sub(r"\s*[|#].*", "", titulo)
    for k, ini in enumerate(_inicios(tot, n) if tot > 35 else []):
        sh = os.path.splitext(base)[0] + f"_short{k + 1}.mp4"
        log(f"• Recortando short vertical {k + 1}/{n}…")
        short_vertical(dst, os.path.join(dest, sh), corto, inicio=ini)
        items = [i for i in items if i["archivo"] != sh] + [
            {"archivo": sh, "tipo": "short", "titulo": (corto + (f" ({k + 1})" if n > 1 else "") + " #shorts")[:100],
             "descripcion": desc, "tags": tags}]
    json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    subir_lista(dest, "atr", log)


def lolo_cmd(rest):
    from .subir import subir_lista
    dest = os.path.join(ROOT, "canales", "lolo", "listo")
    sub = rest[0] if rest else "subir"
    if sub == "conectar":
        from .subir import cliente
        cliente("lolo", log)
    elif sub == "shorts3d":
        # autocanal lolo shorts3d [letras numeros colores] [rapida] -> shorts verticales 3D interactivos y los sube
        from . import educa as E
        temas = [x for x in rest[1:] if x in E.TEMAS] or ["letras", "numeros", "colores"]
        E.shorts3d(temas, dest, log, calidad="rapida" if "rapida" in rest else "normal")
        subir_lista(dest, "lolo", log, categoria="27")
    elif sub == "aprende":
        # autocanal lolo aprende vocales|numeros|abecedario [3d] [rapida] -> canción educativa interactiva y la sube
        from . import educa as E
        tema = next((x for x in rest[1:] if x in E.TEMAS), "vocales")
        E.nuevo(tema, dest, log, modo="3d" if "3d" in rest else "2d", calidad="rapida" if "rapida" in rest else "normal")
        subir_lista(dest, "lolo", log, categoria="27")
    elif sub == "nuevo":
        from . import lolo as L
        L.nuevo(dest, log)
    elif sub == "diario":
        try:
            from . import lolo as L
            L.nuevo(dest, log)
            subir_lista(dest, "lolo", log, categoria="1")
            avisar(f"🦆 {cfg()['infantil_canal']}: short de hoy subido")
        except BaseException as e:
            if isinstance(e, KeyboardInterrupt):
                raise
            avisar(f"❌ Lolo falló: {str(e)[:80]}")
            raise
    elif sub == "servicio":
        servicio("quitar" if len(rest) > 1 and rest[1] == "quitar" else "instalar", "lolo")
    elif sub == "historia":
        # autocanal lolo historia HISTORIA.md [cantidad] -> arma la secuencia de shorts y la sube
        if len(rest) < 2:
            raise SystemExit("Uso: autocanal lolo historia ~/Desktop/historia.md [cantidad de shorts]")
        from . import lolo as L
        L.desde_md(rest[1], dest, int(rest[2]) if len(rest) > 2 else None, log)
        subir_lista(dest, "lolo", log, categoria="1")
    elif sub == "archivo":
        # autocanal lolo archivo VIDEO.mp4 ["Título"] -> sube un video infantil propio (+ short vertical si es largo)
        n, rest = _num(rest)
        if len(rest) < 2:
            raise SystemExit('Uso: autocanal lolo archivo ~/Desktop/video.mp4 ["Título del video"] [cantidad de shorts]')
        src = os.path.abspath(os.path.expanduser(rest[1]))
        if not os.path.isfile(src):
            raise SystemExit(f"No encuentro el archivo: {src}")
        os.makedirs(dest, exist_ok=True)
        base = os.path.basename(src)
        dst = os.path.join(dest, base)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        nombre = re.sub(r"[-_]+", " ", os.path.splitext(base)[0]).strip()
        titulo = rest[2] if len(rest) > 2 else f"{nombre.capitalize()} 🦆 | {cfg()['infantil_canal']}"
        desc = (f"{titulo}\n\n🦆 Suscríbete a {cfg()['infantil_canal']}: ¡aventuras nuevas todos los días!\n\n"
                "#CuentosInfantiles #DibujosAnimados #VideosParaNiños")
        tags = ["lolo el patito", "cuentos infantiles", "dibujos animados", "videos para niños", nombre.lower()]
        from .recorte import duracion, short_vertical
        tot = duracion(dst)
        pj = os.path.join(dest, "publicar.json")
        items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
        items = [i for i in items if i["archivo"] != base] + [
            {"archivo": base, "tipo": "largo" if tot > 180 else "short", "titulo": titulo[:100], "descripcion": desc,
             "ninos": True, "categoria": "1", "tags": tags}]
        n = n if n is not None else (1 if tot > 70 else 0)
        corto = re.sub(r"\s*[|#].*", "", titulo)
        for k, ini in enumerate(_inicios(tot, n) if tot > 35 else []):
            sh = os.path.splitext(base)[0] + f"_short{k + 1}.mp4"
            log(f"• Recortando short vertical {k + 1}/{n}…")
            short_vertical(dst, os.path.join(dest, sh), corto, inicio=ini, pie="Mira el video completo en el canal")
            items = [i for i in items if i["archivo"] != sh] + [
                {"archivo": sh, "tipo": "short", "ninos": True, "categoria": "1", "tags": tags,
                 "titulo": (corto + (f" ({k + 1})" if n > 1 else "") + " 🦆 #shorts")[:100], "descripcion": desc}]
        json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        subir_lista(dest, "lolo", log, categoria="1")
    else:
        subir_lista(dest, "lolo", log, categoria="1")


def preparar_entrada(fuente, nombre=None, info=None, reacciones=()):
    """Archivo (o link directo a un .mp4) -> carpeta de partido lista. Devuelve la carpeta."""
    import urllib.request
    if re.match(r"https?://", fuente):
        if YT.search(fuente):
            raise SystemExit("No bajo videos de YouTube/TikTok/Instagram (derechos y reglas de esas plataformas). "
                             "Bajalo vos y pasame el archivo.")
        base = os.path.basename(fuente.split("?")[0]) or "partido.mp4"
    else:
        fuente = os.path.abspath(os.path.expanduser(fuente))
        if not os.path.isfile(fuente):
            raise SystemExit(f"No encuentro el archivo: {fuente}")
        base = os.path.basename(fuente)
    nombre = nombre or re.sub(r"[_\-]+", " ", os.path.splitext(base)[0]).strip()
    c = os.path.join(PARTIDOS, slug(nombre).replace("-vs-", " vs ").replace("-", " "))
    os.makedirs(c, exist_ok=True)
    dst = os.path.join(c, "partido" + (os.path.splitext(base)[1] or ".mp4"))
    if not os.path.exists(dst):
        if re.match(r"https?://", fuente):
            log(f"• Bajando {fuente}…")
            urllib.request.urlretrieve(fuente, dst)
        else:
            try:
                os.link(fuente, dst)
            except OSError:
                shutil.copy2(fuente, dst)
    for r in reacciones:
        rb = os.path.basename(r)
        rd = os.path.join(c, rb if rb.lower().startswith("reac") else "reaccion_" + rb)
        if not os.path.exists(rd):
            shutil.copy2(r, rd)
    ip = os.path.join(c, "info.txt")
    datos = dict(info or {})
    if not datos.get("local"):
        partes = re.split(r"\s+vs?\.?\s+|\s+-\s+", nombre, maxsplit=1, flags=re.I)
        datos.setdefault("local", partes[0].strip().title())
        if len(partes) > 1:
            datos.setdefault("visitante", partes[1].strip().title())
    if not os.path.exists(ip) or info:
        with open(ip, "w", encoding="utf-8") as f:
            for k in ("local", "visitante", "torneo", "resultado", "imagenes", "hinchas"):
                f.write(f"{k}: {datos.get(k, '')}\n")
    return c


def auto(rest):
    """autocanal auto ARCHIVO|LINK ["Local vs Visitante"] -> analiza, hace todo y sube solo."""
    if not rest:
        raise SystemExit('Uso: autocanal auto PARTIDO.mp4 ["Boca vs River"] [REACCION.mp4 ...]')
    n, rest = _num(rest)
    archivos = [os.path.expanduser(x) for x in rest[1:] if os.path.isfile(os.path.expanduser(x))]
    nombres = [x for x in rest[1:] if not os.path.isfile(os.path.expanduser(x))]
    c = preparar_entrada(rest[0], nombres[0] if nombres else None, reacciones=archivos)
    log(f"• Carpeta: {c}" + (f" — {n} shorts" if n else ""))
    todo(c, n)
    open(os.path.join(c, "listo", ".hecho"), "w").write(time.ctime())


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help", "ayuda"):
        print(__doc__)
        return
    cmd, rest = a[0], a[1:]
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"Falta {tool}. Corré de nuevo el instalador (instalar.command).")
    if cmd == "nuevo":
        nuevo(" ".join(rest) or time.strftime("partido-%Y-%m-%d"))
    elif cmd == "analizar":
        analizar(carpeta_de(rest[0] if rest else None), int(rest[1]) if len(rest) > 1 else None)
    elif cmd == "todo":
        n, rest = _num(rest)
        todo(carpeta_de(rest[0] if rest else None), n)
    elif cmd in ("shorts", "reacciones"):
        {"shorts": shorts, "reacciones": reacciones}[cmd](carpeta_de(rest[0] if rest else None))
    elif cmd == "vigilar":
        vigilar()
    elif cmd == "servicio":
        servicio(rest[0] if rest else "instalar")
    elif cmd == "subir":
        from .subir import subir
        subir(carpeta_de(rest[0] if rest else None), log)
    elif cmd == "prueba":
        prueba()
    elif cmd in ("relax", "dormir"):
        relax_cmd(rest)
    elif cmd in ("lolo", "infantil"):
        lolo_cmd(rest)
    elif cmd == "auto":
        auto(rest)
    elif cmd == "archivo":
        archivo_atr(rest)
    elif cmd == "web":
        from .web import servir
        servir()
    else:
        print(__doc__)
        raise SystemExit(f"Comando desconocido: {cmd}")


if __name__ == "__main__":
    main()
