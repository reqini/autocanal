#!/usr/bin/env python3
"""Mix de reacciones: partido arriba (16:9) + reacción abajo, por bloques (uno por gol), sincronizados.

mix.py CONFIG.json OUT_DIR    -> OUT_DIR/block_N.mp4 y OUT_DIR/mix.mp4 (sin cierre)

CONFIG = {
 "match": "work/match.mp4", "react": "mix/reac.mp4", "strip": [x, y, w, h],   # recorte vertical de la reacción
 "credit": "...", "hook": "...",
 "blocks": [{"title": "GOL DE ALARCÓN", "score": "INSTITUTO 1-0 BOCA", "mood": "FESTEJAN 😂", "mood_color": "yel",
             "top": [[ss, dur], ...], "bottom": [[ss, dur], ...], "goal_t": 4.3,
             "subs": [[a, b, "TEXTO"], ...]}]
}
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .paths import FD, EMOJI, OUTRO
W, H = 1080, 1920
HEAD, TOP_H, DIV = 150, 608, 10
BOT_Y = HEAD + TOP_H + DIV           # 768
BOT_H = H - BOT_Y                    # 1152
YEL, CEL, NAVY, WHITE, RED = (255, 212, 0), (108, 172, 228), (8, 16, 38), (255, 255, 255), (230, 33, 23)
COL = {"yel": YEL, "red": RED, "cel": CEL}


def font(name, size, var=None):
    f = ImageFont.truetype(FD + name, size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


def fit(d, text, name, maxw, start, var=None):
    s = start
    while s > 16 and d.textlength(text, font=font(name, s, var)) > maxw:
        s -= 2
    return font(name, s, var)


def split_emoji(text):
    """separa un emoji final (si hay) del texto."""
    if text and ord(text[-1]) > 0x2000:
        return text[:-1].rstrip(), text[-1]
    return text, None


def emoji_img(ch, size):
    f = ImageFont.truetype(EMOJI, 109)
    im = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    r = size / max(im.size)
    return im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)


def pill(im, cx, y, text, fg, bg, fname, size, var=None, pad=(26, 10), maxw=1000):
    d = ImageDraw.Draw(im)
    txt, emo = split_emoji(text)
    f = fit(d, txt, fname, maxw - 2 * pad[0] - (size if emo else 0), size, var)
    bb = d.textbbox((0, 0), txt, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    ew = 0
    e = None
    if emo:
        e = emoji_img(emo, int(th * 1.25))
        ew = e.width + 12
    w = tw + ew + 2 * pad[0]
    x0 = cx - w / 2 if cx is not None else 40
    d.rounded_rectangle((x0, y, x0 + w, y + th + 2 * pad[1]), radius=(th + 2 * pad[1]) // 2, fill=bg)
    d.text((x0 + pad[0] - bb[0], y + pad[1] - bb[1]), txt, font=f, fill=fg)
    if e:
        im.alpha_composite(e, (int(x0 + pad[0] + tw + 12), int(y + pad[1] + th / 2 - e.height / 2)))
    return x0 + w, y + th + 2 * pad[1]


def big_text(im, text, y, size, fg, maxw=1000, stroke=9):
    d = ImageDraw.Draw(im)
    txt, emo = split_emoji(text)
    f = fit(d, txt, "Anton-Regular.ttf", maxw - (size if emo else 0), size)
    bb = d.textbbox((0, 0), txt, font=f, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    e = emoji_img(emo, int(th * 0.9)) if emo else None
    total = tw + (e.width + 16 if e else 0)
    x = (W - total) / 2
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x - bb[0] + 6, y - bb[1] + 10), txt, font=f, fill=(0, 0, 0, 170), stroke_width=stroke,
                            stroke_fill=(0, 0, 0, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    d.text((x - bb[0], y - bb[1]), txt, font=f, fill=fg, stroke_width=stroke, stroke_fill=(0, 0, 0))
    if e:
        im.alpha_composite(e, (int(x + tw + 16), int(y + th / 2 - e.height / 2)))
    return y + th


def header_png(path, b, idx, n):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, HEAD), fill=NAVY)
    d.rectangle((0, HEAD + TOP_H, W, BOT_Y), fill=YEL)
    # título del gol + marcador
    sc = b["score"]
    fs = fit(d, sc, "Oswald.ttf", 430, 40, "Bold")
    sw = d.textlength(sc, font=fs)
    ft = fit(d, b["title"], "Anton-Regular.ttf", W - 36 - sw - 44 - 72, 74)
    bb = d.textbbox((0, 0), b["title"], font=ft)
    d.text((36 - bb[0], (HEAD - (bb[3] - bb[1])) / 2 - bb[1] - 4), b["title"], font=ft, fill=WHITE)
    d.rounded_rectangle((W - 36 - sw - 44, 44, W - 36, 106), radius=12, fill=YEL)
    d.text((W - 36 - sw - 22, 48), sc, font=fs, fill=NAVY)
    # contador de gol
    fc = font("Oswald.ttf", 26, "SemiBold")
    d.text((W - 36 - sw - 44, 112), b.get("counter", f"GOL {idx}/{n}"), font=fc, fill=CEL)
    # etiqueta de reacción
    pill(im, None, BOT_Y + 26, b["mood"], NAVY if b.get("mood_color", "yel") != "red" else WHITE,
         COL[b.get("mood_color", "yel")] + (240,), "Oswald.ttf", 44, "Bold")
    im.save(path)


def credit_png(path, text):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pill(im, W / 2, 1846, text, WHITE, (8, 16, 38, 215), "Oswald.ttf", 30, "Medium", pad=(22, 8))
    im.save(path)


def sub_png(path, text):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    big_text(im, text, 1560, 104, YEL)
    im.save(path)


def hook_png(path, text):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, HEAD, W, HEAD + TOP_H), fill=(8, 16, 38, 150))
    lines = text.split("|")
    y = HEAD + 150 if len(lines) > 1 else HEAD + 230
    for i, ln in enumerate(lines):
        y = big_text(im, ln, y, 110 if i == 0 else 128, WHITE if i == 0 else YEL) + 30
    im.save(path)


def render_block(cfg, b, idx, n, out, tmp):
    hp = os.path.join(tmp, f"h{idx}.png"); header_png(hp, b, idx, n)
    cp = os.path.join(tmp, "credit.png"); credit_png(cp, cfg["credit"])
    dur = sum(it[1] for it in b["bottom"])
    ins, k = [], 0
    for ss, d in b["top"]:
        ins += ["-ss", str(ss), "-t", str(d), "-i", cfg["match"]]
    nt = len(b["top"])
    srcs = cfg.get("sources", {})
    bot_strips = []
    for item in b["bottom"]:
        ss, d = item[0], item[1]
        key = item[2] if len(item) > 2 else None
        src = srcs[key]["src"] if key else cfg["react"]
        bot_strips.append(srcs[key]["strip"] if key else cfg["strip"])
        ins += ["-ss", str(ss), "-t", str(d), "-i", src]
    nb = len(b["bottom"])
    ov = [hp, cp]
    subs = []
    for j, (a, e, t) in enumerate(b.get("subs", [])):
        p = os.path.join(tmp, f"s{idx}_{j}.png"); sub_png(p, t); subs.append((a, e, p))
    hook = None
    if idx == 1 and cfg.get("hook"):
        hook = os.path.join(tmp, "hook.png"); hook_png(hook, cfg["hook"])
    for p in ov + [s[2] for s in subs] + ([hook] if hook else []):
        ins += ["-loop", "1", "-t", str(dur), "-i", p]
    g = b["goal_t"]
    fc = []
    for i in range(nt):
        fc.append(f"[{i}:v]fps=30,scale=1080:608,setsar=1,setpts=PTS-STARTPTS[t{i}]")
    fc.append("".join(f"[t{i}]" for i in range(nt)) + f"concat=n={nt}:v=1:a=0[top]")
    for i in range(nb):
        j = nt + i
        x, y, w, h = bot_strips[i]
        fc.append(f"[{j}:v]fps=30,crop={w}:{h}:{x}:{y},scale=1080:{BOT_H}:force_original_aspect_ratio=increase,crop=1080:{BOT_H},"
                  f"unsharp=5:5:0.7,setsar=1,setpts=PTS-STARTPTS[b{i}];[{j}:a]aresample=44100,asetpts=PTS-STARTPTS[a{i}]")
    fc.append("".join(f"[b{i}][a{i}]" for i in range(nb)) + f"concat=n={nb}:v=1:a=1[bot0][aud]")
    zoom = f"1+0.18*between(t,{g},{g + 0.25})+0.10*between(t,{g + 0.25},{g + 1.8})"
    fc.append(f"[bot0]scale=w='1080*({zoom})':h='{BOT_H}*({zoom})':eval=frame,crop=1080:{BOT_H},"
              f"drawbox=c=white@0.6:t=fill:enable='between(t,{g},{g + 0.12})'[bot]")
    fc.append(f"color=c=0x081026:s={W}x{H}:r=30:d={dur}[bg];[bg][top]overlay=0:{HEAD}[c1];[c1][bot]overlay=0:{BOT_Y}[c2]")
    base = nt + nb
    fc.append(f"[c2][{base}:v]overlay[c3];[c3][{base + 1}:v]overlay[c4]")
    last = "c4"
    for j, (a, e, _) in enumerate(subs):
        fc.append(f"[{last}][{base + 2 + j}:v]overlay=enable='between(t,{a},{e})'[u{j}]")
        last = f"u{j}"
    if hook:
        fc.append(f"[{last}][{base + 2 + len(subs)}:v]overlay=enable='lt(t,{cfg.get('hook_dur', 2.4)})'[hk]")
        last = "hk"
    fc.append(f"[{last}]format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[aud]",
                    "-t", str(dur), "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-profile:v", "high",
                    "-level", "4.0", "-video_track_timescale", "15360", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-ac", "2", out], check=True)


def main(cfg_path, out_dir):
    cfg = json.load(open(cfg_path))
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "tmp"); os.makedirs(tmp, exist_ok=True)
    only = os.environ.get("ONLY")
    outs = []
    n = len(cfg["blocks"])
    for i, b in enumerate(cfg["blocks"], 1):
        o = os.path.join(out_dir, f"block_{i}.mp4")
        if not only or str(i) in only.split(","):
            render_block(cfg, b, i, n, o, tmp)
            print("ok block", i, flush=True)
        outs.append(o)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(o)}'\n" for o in outs)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    "-movflags", "+faststart", os.path.join(out_dir, "mix.mp4")], check=True)
    print("ok mix", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
