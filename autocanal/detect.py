"""Detección sin IA: momentos fuertes por audio, sincronía de reacciones y recorte automático de la cara."""
import os, subprocess
import numpy as np

SR = 16000


def audio(f, sr=SR, ss=None, t=None):
    a = ["ffmpeg", "-nostdin", "-v", "error"] + (["-ss", f"{ss:.2f}"] if ss is not None else []) + \
        (["-t", f"{t:.2f}"] if t else []) + ["-i", f, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    try:
        raw = subprocess.check_output(a)
    except subprocess.CalledProcessError:
        return np.zeros(0, np.float32)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def stream(f, sr, secs=60):
    """Lee el audio de a pedazos (sirve para partidos completos de 2 h sin llenar la memoria)."""
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", f, "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], stdout=subprocess.PIPE)
    n = int(sr * secs) * 2
    while True:
        raw = p.stdout.read(n)
        if not raw:
            break
        yield np.frombuffer(raw[:len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768
    p.wait()


def _sm(v, k):
    return np.convolve(v, np.ones(k) / k, "same")


# ---------------------------------------------------------------- momentos
def momentos(video, n=5, min_gap=25.0):
    """Devuelve [{t, inicio, dur, tipo, fuerza}] ordenados por tiempo.
    1) gritos de gol del relator (sonido sostenido y tonal: 'GOOOL') -> tipo GOL
    2) el resto, por subidas de volumen respecto del entorno -> tipo JUGADA
    """
    hop = SR // 10
    f = np.fft.rfftfreq(hop, 1 / SR)
    win = np.hanning(hop)
    fl_parts, lv_parts, rest = [], [], np.zeros(0, np.float32)
    for chunk in stream(video, SR):
        x = np.concatenate([rest, chunk])
        k = len(x) // hop
        rest = x[k * hop:]
        if not k:
            continue
        S = np.abs(np.fft.rfft(x[:k * hop].reshape(k, hop) * win, axis=1)) ** 2
        B = S[:, (f > 300) & (f < 4000)]
        fl_parts.append(np.exp(np.mean(np.log(B + 1e-12), 1)) / (np.mean(B, 1) + 1e-12))
        lv_parts.append(10 * np.log10(S[:, (f >= 50) & (f < 8000)].sum(1) + 1e-9))
    if not fl_parts or sum(map(len, fl_parts)) < 200:
        return []
    flat = _sm(np.concatenate(fl_parts), 5)
    lvl = _sm(np.concatenate(lv_parts), 10)
    m = len(flat)
    med = np.median(lvl)
    total = m / 10
    edge = min(20.0, total * 0.05)

    # 1) gritos de gol
    on = (flat < 0.05) & (lvl > med - 6)
    ev, i = [], 0
    while i < m:
        if on[i]:
            j = i
            while j < m and (on[j] or (j + 5 < m and on[j:j + 5].any())):
                j += 1
            d = (j - i) / 10
            t = i / 10
            if d >= 1.5 and edge < t < total - edge:
                if ev and t - (ev[-1]["t"] + ev[-1]["d"]) < 8:      # mismo festejo
                    ev[-1]["d"] = t + d - ev[-1]["t"]
                else:
                    ev.append({"t": t, "d": d, "f": float(1 - flat[i:j].mean())})
            i = j
        else:
            i += 1
    out = []
    for e in sorted(ev, key=lambda e: -e["d"]):
        if len(out) >= n:
            break
        if all(abs(e["t"] - o["t"]) >= min_gap for o in out):
            gol = e["d"] >= 3.0
            t = e["t"] - 1.5                                      # la pelota entra un toque antes del grito
            out.append({"t": round(t, 1), "inicio": round(max(0, t - 7.5), 1), "dur": 18.0,
                        "tipo": "GOL" if gol else "JUGADA", "fuerza": round(e["d"], 1)})

    # 2) completar con subidas de volumen (1 Hz, relativo a la mediana de 60 s)
    if len(out) < n:
        s = lvl[:m // 10 * 10].reshape(-1, 10).mean(1)
        pad = np.pad(s, 30, mode="edge")
        base = np.array([np.median(pad[k:k + 61]) for k in range(len(s))])
        exc = _sm(s - base, 3)
        for k in np.argsort(exc)[::-1]:
            if len(out) >= n or exc[k] <= 0:
                break
            t = float(k)
            if not (edge < t < total - edge):
                continue
            if all(abs(t - o["t"]) >= min_gap for o in out):
                out.append({"t": t, "inicio": max(0.0, t - 9), "dur": 16.0, "tipo": "JUGADA",
                            "fuerza": round(float(exc[k]), 1)})
    for o in out:
        o["dur"] = min(o["dur"], max(5.0, total - o["inicio"] - 0.5))
    return sorted(out, key=lambda o: o["t"])


def parejo(video, n=5):
    """Sin audio: reparte n momentos a lo largo del video (para revisar a mano)."""
    from .media import dur
    D = dur(video)
    return [{"t": round(D * (k + 0.5) / n, 1), "inicio": round(max(0, D * (k + 0.5) / n - 8), 1), "dur": 16.0,
             "tipo": "JUGADA", "fuerza": 0} for k in range(n)]


# ---------------------------------------------------------------- sincronía de reacciones
FPS = 50


def _feat_file(f, sr=8000):
    """Energía por 12 bandas (50 por segundo) -> 'golpes' de sonido. Se calcula de a pedazos."""
    hop, nfft = sr // FPS, 512
    win = np.hanning(nfft)
    edges = np.geomspace(4, 256, 13).astype(int)
    parts, rest = [], np.zeros(0, np.float32)
    for chunk in stream(f, sr, 30):
        x = np.concatenate([rest, chunk])
        if len(x) < nfft:
            rest = x
            continue
        nf = (len(x) - nfft) // hop + 1
        fr = np.lib.stride_tricks.sliding_window_view(x, nfft)[::hop][:nf] * win
        S = np.abs(np.fft.rfft(fr, axis=1)) ** 2
        parts.append(np.log(np.stack([S[:, edges[i]:edges[i + 1]].sum(1) for i in range(12)], 1) + 1e-8))
        rest = x[nf * hop:]
    if not parts:
        return np.zeros((0, 12), np.float32)
    return np.maximum(np.diff(np.concatenate(parts), axis=0), 0).astype(np.float32)


def feats_cache(f, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    st = os.stat(f)
    p = os.path.join(cache_dir, f"{os.path.basename(f)}.{int(st.st_size)}.npy")
    if os.path.exists(p):
        return np.load(p)
    F = _feat_file(f)
    np.save(p, F)
    return F


def _xcorr(q, r):
    """Correlación normalizada de q (m x 12) a lo largo de r (N x 12). Devuelve vector N-m+1."""
    m, N = len(q), len(r)
    if m < FPS or N <= m:
        return np.zeros(0)
    q = (q - q.mean(0)) / (q.std(0) + 1e-6)
    L = 1 << int(np.ceil(np.log2(N + m)))
    tot = np.zeros(N - m + 1)
    for b in range(q.shape[1]):
        rb, qb = r[:, b].astype(np.float64), q[:, b].astype(np.float64)
        c = np.fft.irfft(np.fft.rfft(rb, L) * np.conj(np.fft.rfft(qb, L)), L)[:N - m + 1]
        cs = np.concatenate([[0], np.cumsum(rb)])
        cs2 = np.concatenate([[0], np.cumsum(rb * rb)])
        mu = (cs[m:] - cs[:-m]) / m
        var = (cs2[m:] - cs2[:-m]) / m - mu ** 2
        tot += c / (m * np.sqrt(np.maximum(var, 1e-9)))
    return tot / q.shape[1]


def _best(c):
    if not len(c):
        return None, 0.0
    i = int(np.argmax(c))
    mask = np.ones(len(c), bool)
    mask[max(0, i - 5 * FPS):i + 5 * FPS] = False
    second = c[mask].max() if mask.any() else 1e-6
    return i, float(c[i] / max(second, 1e-6)) if c[i] > 0 else 0.0


def sync(match_f, react_f, t, cache_dir):
    """¿En qué segundo de la reacción se ve el instante t del partido?
    Devuelve (segundo_en_reaccion | None, confianza 0-1)."""
    Fm = feats_cache(match_f, cache_dir)
    Fr = feats_cache(react_f, cache_dir)
    if len(Fr) >= 90 * FPS:
        # reacción larga: busco varias ventanas del partido dentro de la reacción y voto
        cands = []
        for pre, L in [(4, 12), (6, 16), (8, 20), (10, 30)]:
            a = int((t - pre) * FPS)
            if a < 0 or a + L * FPS > len(Fm):
                continue
            c = _xcorr(Fm[a:a + L * FPS], Fr)
            i, r = _best(c)
            if i is not None:
                cands.append((i / FPS + (t - a / FPS), r))
        best = None
        for p, _ in cands:
            sc = sum(r - 1 for p2, r in cands if abs(p2 - p) <= 1.0)
            if best is None or sc > best[1]:
                best = (p, sc)
        if best and best[1] >= 0.8:
            return round(best[0], 2), round(min(1.0, best[1] / 2), 2)
        return None, 0.0
    # clip corto (redes): busco el clip dentro del partido
    c = _xcorr(Fr[:25 * FPS], Fm)
    j, r = _best(c)
    if j is not None and r >= 1.5 and c[j] >= 0.1:
        pos = t - j / FPS
        if 0 <= pos <= len(Fr) / FPS:
            return round(pos, 2), round(min(1.0, (r - 1) / 1.5), 2)
    return None, 0.0


# ---------------------------------------------------------------- recorte de la cara
def cara(video, aspect):
    """Recorte [x, y, w, h] con proporción `aspect` (ancho/alto) centrado en la cara más frecuente."""
    from .media import size
    W, H = size(video)
    if W / H > aspect:
        h, w = H, int(round(H * aspect))
    else:
        w, h = W, int(round(W / aspect))
    cx, cy = W / 2, H / 2
    try:
        import cv2
        cap = cv2.VideoCapture(video)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        pts = []
        for k in range(30):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (k + 0.5) / 30))
            ok, fr = cap.read()
            if not ok:
                continue
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            fs = casc.detectMultiScale(g, 1.1, 5, minSize=(max(24, H // 12),) * 2)
            if len(fs):
                x, y, fw, fh = max(fs, key=lambda b: b[2] * b[3])
                pts.append((x + fw / 2, y + fh / 2))
        cap.release()
        if pts:
            cx, cy = np.median(np.array(pts), 0)
            cy += h * 0.12                                      # deja aire arriba de la cabeza
    except Exception:
        pass
    x = int(max(0, min(W - w, cx - w / 2)))
    y = int(max(0, min(H - h, cy - h / 2)))
    return [x, y, w, h]
