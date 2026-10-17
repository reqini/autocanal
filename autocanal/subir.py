"""Subida a YouTube con la API oficial (gratis, cuota diaria de Google). Opcional.
Necesita client_secret.json en la carpeta del bot (ver GUIA.md, 'Subida automática').
Cada canal tiene su propio permiso: perfil 'atr' (deportes), 'relax' (dormir) y 'lolo' (infantil)."""
import json, os, subprocess, sys
from .paths import ROOT, cfg

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _libs():
    try:
        import googleapiclient, google_auth_oauthlib  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "google-api-python-client", "google-auth-oauthlib"],
                       check=True)


def cliente(perfil="atr", log=print):
    _libs()
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    cs = os.path.join(ROOT, "client_secret.json")
    tok = os.path.join(ROOT, ".token.json" if perfil == "atr" else f".token_{perfil}.json")
    if not os.path.exists(cs):
        raise SystemExit("Falta client_secret.json en la carpeta del bot. Seguí la GUIA (Subida automática).")
    creds = Credentials.from_authorized_user_file(tok, SCOPES) if os.path.exists(tok) else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds or not creds.valid:
            c = cfg()
            canal = {"atr": c["canal"], "relax": c["relax_canal"], "lolo": c["infantil_canal"]}.get(perfil, perfil)
            log(f"• Se abre el navegador: elegí el canal «{canal}» y aceptá.")
            creds = InstalledAppFlow.from_client_secrets_file(cs, SCOPES).run_local_server(port=0)
        open(tok, "w").write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def subir_lista(dest, perfil="atr", log=print, categoria="17"):
    """Sube lo pendiente de dest/publicar.json. Devuelve la lista actualizada."""
    pj = os.path.join(dest, "publicar.json")
    if not os.path.exists(pj):
        raise SystemExit(f"No hay nada para subir (falta {pj}).")
    items = json.load(open(pj, encoding="utf-8"))
    pend = [it for it in items if not it.get("subido") and os.path.exists(os.path.join(dest, it["archivo"]))]
    if not pend:
        log("• Nada pendiente para subir.")
        return items
    yt = cliente(perfil, log)
    from googleapiclient.http import MediaFileUpload
    priv = cfg().get("privacidad", "public")
    for it in pend:
        f = os.path.join(dest, it["archivo"])
        tags = it.get("tags") or [t.lstrip("#") for t in it["descripcion"].split() if t.startswith("#")][:15]
        body = {"snippet": {"title": it["titulo"][:100], "description": it["descripcion"], "tags": tags,
                            "categoryId": it.get("categoria", categoria), "defaultLanguage": "es",
                            "defaultAudioLanguage": "es"},
                "status": {"privacyStatus": priv, "selfDeclaredMadeForKids": bool(it.get("ninos"))}}
        log(f"• Subiendo {it['archivo']} ({os.path.getsize(f) / 1048576:.0f} MB)…")
        req = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=MediaFileUpload(f, mimetype="video/mp4", chunksize=16 * 1048576,
                                                            resumable=True))
        resp, last = None, -10
        while resp is None:
            try:
                st, resp = req.next_chunk()
            except Exception as e:
                if "uploadLimitExceeded" in str(e) or "exceeded the number of videos" in str(e):
                    log("⏸ YouTube no deja subir más videos hoy a este canal (límite diario). Quedan en la cola:"
                        f" {len(pend) - pend.index(it)} pendientes. Se suben solos mañana (o corré el mismo comando).")
                    return items
                raise
            if st and int(st.progress() * 100) >= last + 10:
                last = int(st.progress() * 100)
                log(f"  {last}%")
        vid = resp["id"]
        it["subido"] = f"https://youtu.be/{vid}"
        if it.get("portada") and it.get("tipo") in ("horizontal", "largo"):
            try:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(os.path.join(dest, it["portada"]))).execute()
            except Exception as e:
                log(f"  (no pude poner la miniatura: {str(e)[:120]} — verificá el teléfono en youtube.com/verify)")
        json.dump(items, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"  ✓ {it['subido']}")
    return items


def subir(carpeta, log=print):
    dest = os.path.join(carpeta, "listo")
    items = subir_lista(dest, "atr", log)
    from .cli import _pub_save
    _pub_save(dest, items)
    log("✓ Subida terminada. Revisá en YouTube Studio que estén Públicos.")
