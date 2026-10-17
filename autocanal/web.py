"""Interfaz local: http://127.0.0.1:8765 — arrastrás el video, completás 4 datos y el bot hace todo (y sube)."""
import glob, json, mimetypes, os, re, threading, time, traceback, urllib.parse, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from .paths import ROOT, PARTIDOS
from . import cli

PORT = 8765
ENTRADA = os.path.join(ROOT, "entrada")
LOG, JOB = [], {"nombre": None}
LOCK = threading.Lock()


def _log(msg):
    with LOCK:
        LOG.append(time.strftime("%H:%M:%S ") + msg)
        del LOG[:-400]


cli.LOG_HOOK = _log


def correr(nombre, fn, *a):
    if JOB["nombre"]:
        return False

    def run():
        JOB["nombre"] = nombre
        _log(f"▶ {nombre}")
        try:
            fn(*a)
            _log(f"✅ Terminado: {nombre}")
        except BaseException as e:
            _log(f"❌ {e if isinstance(e, SystemExit) else traceback.format_exc(limit=2)}")
        finally:
            JOB["nombre"] = None
            cli.SUBIR = None
    threading.Thread(target=run, daemon=True).start()
    return True


def futbol(d):
    cli.SUBIR = bool(d.get("subir"))
    info = {k: d.get(k, "") for k in ("local", "visitante", "torneo", "resultado", "imagenes", "hinchas")}
    nombre = f"{info['local']} vs {info['visitante']}" if info["local"] and info["visitante"] else None
    c = cli.preparar_entrada(d["archivo"], nombre, info if info["local"] else None, d.get("reacciones") or [])
    _log(f"Carpeta del partido: {c}")
    if d.get("rehacer") and os.path.exists(os.path.join(c, "plan.txt")):
        os.remove(os.path.join(c, "plan.txt"))
    cli.todo(c)


def relax(d):
    acc = d.get("accion")
    args = {"nuevo": [d.get("tipo") or "nuevo"] + ([str(d["horas"])] if d.get("horas") else []),
            "subir": ["subir"], "conectar": ["conectar"], "servicio": ["servicio"], "diario": ["diario"]}[acc]
    cli.relax_cmd(args)


def estado():
    parts = []
    for c in sorted(glob.glob(os.path.join(PARTIDOS, "*")), key=os.path.getmtime, reverse=True)[:12]:
        if not os.path.isdir(c) or os.path.basename(c).startswith("_"):
            continue
        pj = os.path.join(c, "listo", "publicar.json")
        items = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
        parts.append({"nombre": os.path.basename(c), "items": items,
                      "base": "p/" + os.path.basename(c) + "/listo"})
    rp = os.path.join(ROOT, "canales", "relax", "listo", "publicar.json")
    rel = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else []
    with LOCK:
        lg = LOG[-200:]
    return {"job": JOB["nombre"], "log": lg, "partidos": parts, "relax": rel[-10:],
            "conectado": os.path.exists(os.path.join(ROOT, "client_secret.json")),
            "relax_ok": os.path.exists(os.path.join(ROOT, ".token_relax.json")),
            "atr_ok": os.path.exists(os.path.join(ROOT, ".token.json"))}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            b = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/estado":
            self._json(estado())
        elif u.path.startswith("/media/"):
            rel = urllib.parse.unquote(u.path[len("/media/"):])
            base = PARTIDOS if rel.startswith("p/") else ROOT
            f = os.path.realpath(os.path.join(base, rel[2:]))
            okdir = any(f.startswith(os.path.realpath(r) + os.sep) for r in (ROOT, PARTIDOS))
            if not okdir or not os.path.isfile(f):
                return self._json({"error": "no existe"}, 404)
            size = os.path.getsize(f)
            rng = self.headers.get("Range")
            start, end = 0, size - 1
            if rng and (m := re.match(r"bytes=(\d*)-(\d*)", rng)):
                start = int(m.group(1) or 0)
                end = int(m.group(2)) if m.group(2) else min(size - 1, start + 4 * 1048576)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(f)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with open(f, "rb") as fh:
                fh.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = fh.read(min(1048576, left))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    left -= len(chunk)
        else:
            self._json({"error": "no existe"}, 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        if u.path == "/api/archivo":                      # subida del archivo arrastrado (queda en entrada/)
            name = os.path.basename(urllib.parse.parse_qs(u.query).get("nombre", ["video.mp4"])[0])
            os.makedirs(ENTRADA, exist_ok=True)
            dst = os.path.join(ENTRADA, name)
            with open(dst, "wb") as f:
                while n > 0:
                    chunk = self.rfile.read(min(4 * 1048576, n))
                    if not chunk:
                        break
                    f.write(chunk)
                    n -= len(chunk)
            return self._json({"ruta": dst})
        d = json.loads(self.rfile.read(n) or b"{}")
        if u.path == "/api/futbol":
            ok = correr(f"Fútbol: {d.get('local') or os.path.basename(d.get('archivo', ''))}", futbol, d)
        elif u.path == "/api/relax":
            ok = correr(f"Dormir: {d.get('accion')}", relax, d)
        elif u.path == "/api/subir":
            ok = correr("Subir partido", lambda: __import__("atr.subir", fromlist=["subir"]).subir(
                os.path.join(PARTIDOS, d["partido"]), cli.log))
        else:
            return self._json({"error": "no existe"}, 404)
        self._json({"ok": ok, "msg": None if ok else "Ya hay una tarea corriendo, esperá que termine."})


def servir():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print(f"AutoCanal web en {url}  (dejá esta ventana abierta; Ctrl+C para cerrar)", flush=True)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoCanal</title>
<style>
:root{--bg:#0b1020;--card:#131a30;--line:#24304f;--tx:#e9ecf5;--mut:#93a0c0;--yel:#ffd400;--cel:#6cace4;--vio:#b9a2ff;--ok:#4ade80;--bad:#f87171}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:20px 24px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{margin:0;font-size:20px}header .pill{font-size:12px;padding:3px 10px;border-radius:99px;border:1px solid var(--line);color:var(--mut)}
.pill.ok{color:var(--ok);border-color:#1f5135}.pill.bad{color:var(--bad);border-color:#5b2626}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px;padding:18px 24px;max-width:1300px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.card h2{margin:0 0 12px;font-size:17px}.atr h2 span{color:var(--yel)}.dp h2 span{color:var(--vio)}
.drop{border:2px dashed var(--line);border-radius:12px;padding:22px;text-align:center;color:var(--mut);cursor:pointer;transition:.15s}
.drop.on{border-color:var(--yel);color:var(--tx)}.drop b{color:var(--tx)}
label{display:block;font-size:12px;color:var(--mut);margin:10px 0 4px}
input,select{width:100%;padding:9px 11px;border-radius:9px;border:1px solid var(--line);background:#0e1427;color:var(--tx);font:inherit}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
button{margin-top:14px;padding:11px 16px;border-radius:10px;border:0;font:600 15px inherit;cursor:pointer;background:var(--yel);color:#0b1020}
button.sec{background:#1d2745;color:var(--tx);margin-right:6px}.dp button{background:var(--vio)}
button:disabled{opacity:.45;cursor:default}.chk{display:flex;gap:8px;align-items:center;margin-top:10px;color:var(--mut)}.chk input{width:auto}
#log{grid-column:1/-1;font:12.5px ui-monospace,Menlo,monospace;white-space:pre-wrap;max-height:260px;overflow:auto;color:#c6cee6}
.res{grid-column:1/-1}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}
.it{background:#0e1427;border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:12.5px}
.it video,.it img{width:100%;aspect-ratio:9/16;object-fit:cover;background:#000;display:block}.it.h video,.it.h img{aspect-ratio:16/9}
.it div{padding:8px}.it a{color:var(--cel)}.mut{color:var(--mut)}h3{margin:18px 0 8px;font-size:15px}
</style></head><body>
<header><h1>🤖 AutoCanal</h1><span id="job" class="pill">listo</span><span id="cx" class="pill"></span></header>
<main>
<section class="card atr"><h2>Deportes <span>⚽</span></h2>
<div class="drop" id="drop">Arrastrá acá el <b>video del partido</b><br><small>o hacé clic para elegirlo</small></div>
<input type="file" id="file" accept="video/*" hidden>
<label>…o pegá la ruta del archivo en tu Mac</label><input id="ruta" placeholder="~/Downloads/partido.mp4">
<label>Reacciones (opcional, podés elegir varias; el nombre del archivo = crédito)</label><input type="file" id="reac" accept="video/*" multiple>
<div class="row"><div><label>Local</label><input id="local" placeholder="Boca"></div><div><label>Visitante</label><input id="visitante" placeholder="River"></div></div>
<div class="row"><div><label>Torneo</label><input id="torneo" placeholder="Liga Profesional"></div><div><label>Resultado</label><input id="resultado" placeholder="2-1"></div></div>
<div class="row"><div><label>Imágenes de</label><input id="imagenes" placeholder="ESPN / TNT Sports"></div><div><label>Reacciones de hinchas de</label><input id="hinchas" placeholder="River"></div></div>
<label class="chk"><input type="checkbox" id="subir" checked> Subir a YouTube cuando termine</label>
<button id="go">Hacer todo</button>
</section>
<section class="card dp"><h2>🌙 Canal para <span>dormir</span></h2>
<div class="row"><div><label>Sonido</label><select id="tipo"><option value="">Automático (rota)</option><option value="blanco">Ruido blanco</option><option value="lluvia">Lluvia suave</option><option value="ambiente">Música ambiente</option></select></div>
<div><label>Horas</label><select id="horas"><option>8</option><option>10</option><option>3</option><option>1</option></select></div></div>
<button data-r="nuevo">Crear video</button> <button class="sec" data-r="subir">Subir pendientes</button>
<div><button class="sec" data-r="conectar">Conectar canal</button><button class="sec" data-r="servicio">Automático todos los días</button></div>
<h3>Últimos videos</h3><div id="rel" class="mut">—</div>
</section>
<section class="card" id="log">Esperando…</section>
<section class="card res"><h2>Resultados</h2><div id="parts" class="mut">Todavía no hay partidos.</div></section>
</main>
<script>
const $=s=>document.querySelector(s);let picked=null;
const drop=$('#drop'),file=$('#file');
drop.onclick=()=>file.click();file.onchange=()=>pick(file.files[0]);
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('on')}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('on')}));
drop.addEventListener('drop',ev=>pick(ev.dataTransfer.files[0]));
function pick(f){if(!f)return;picked=f;drop.innerHTML='🎬 <b>'+f.name+'</b><br><small>'+(f.size/1048576).toFixed(0)+' MB</small>';
 const m=f.name.replace(/\.[^.]+$/,'').split(/\s+vs?\.?\s+|\s+-\s+/i);if(m.length>1&&!$('#local').value){$('#local').value=cap(m[0]);$('#visitante').value=cap(m[1])}}
const cap=s=>s.trim().replace(/[_-]+/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
async function up(f){const r=await fetch('/api/archivo?nombre='+encodeURIComponent(f.name),{method:'POST',body:f});return (await r.json()).ruta}
$('#go').onclick=async()=>{let archivo=$('#ruta').value.trim();const b=$('#go');b.disabled=true;
 try{if(!archivo){if(!picked){alert('Elegí o arrastrá el video del partido');return}b.textContent='Copiando video…';archivo=await up(picked)}
 const reacciones=[];for(const f of $('#reac').files){b.textContent='Copiando '+f.name+'…';reacciones.push(await up(f))}
 const d={archivo,reacciones,subir:$('#subir').checked};['local','visitante','torneo','resultado','imagenes','hinchas'].forEach(k=>d[k]=$('#'+k).value.trim());
 const r=await (await fetch('/api/futbol',{method:'POST',body:JSON.stringify(d)})).json();if(!r.ok)alert(r.msg)}
 finally{b.disabled=false;b.textContent='Hacer todo'}};
document.querySelectorAll('[data-r]').forEach(b=>b.onclick=async()=>{const r=await (await fetch('/api/relax',{method:'POST',body:JSON.stringify({accion:b.dataset.r,tipo:$('#tipo').value,horas:$('#horas').value})})).json();if(!r.ok)alert(r.msg)});
const med=(base,f)=>'/media/'+encodeURI(base+'/'+f);
function card(base,it){const h=it.tipo!=='short';const v=it.portada&&h?'<img src="'+med(base,it.portada)+'">':'<video src="'+med(base,it.archivo)+'#t=2" preload="metadata" controls></video>';
 return '<div class="it'+(h?' h':'')+'">'+v+'<div>'+it.titulo+'<br>'+(it.subido?'<a href="'+it.subido+'" target="_blank">✓ en YouTube</a>':'<span class="mut">sin subir</span>')+'</div></div>'}
let last='';async function tick(){try{const s=await (await fetch('/api/estado')).json();
 $('#job').textContent=s.job?'⏳ '+s.job:'listo';$('#job').className='pill'+(s.job?'':' ok');
 $('#cx').textContent=s.conectado?('YouTube: deportes '+(s.atr_ok?'✓':'—')+' · dormir '+(s.relax_ok?'✓':'—')):'YouTube sin permiso (client_secret.json)';$('#cx').className='pill '+(s.conectado?'ok':'bad');
 const lg=s.log.join('\n')||'Esperando…';if(lg!==last){$('#log').textContent=lg;$('#log').scrollTop=1e9;last=lg}
 const pk=JSON.stringify([s.partidos,s.relax]);if(pk!==lastParts){lastParts=pk;
 $('#parts').innerHTML=s.partidos.length?s.partidos.map(p=>'<h3>'+p.nombre+'</h3><div class="grid">'+p.items.map(i=>card(p.base,i)).join('')+'</div>').join(''):'Todavía no hay partidos.';
 $('#rel').innerHTML=s.relax.length?'<div class="grid">'+s.relax.slice().reverse().map(i=>card('r/canales/relax/listo',i)).join('')+'</div>':'—';}
 document.querySelectorAll('button').forEach(b=>b.disabled=!!s.job);}catch(e){$('#job').textContent='bot apagado';$('#job').className='pill bad'}}
let lastParts='';tick();setInterval(tick,3000);
</script></body></html>"""
