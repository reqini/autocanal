#!/usr/bin/env python3
"""Video horizontal 16:9 de reacciones: partido 1280x720 a la izquierda, hincha vertical a la derecha.

long.py CONFIG.json OUT_DIR   (env ONLY=intro,1A,1B,... para renderizar partes sueltas)
Partes: intro, por gol "A" (gol en vivo + hincha sincronizado) y "B" (repetición lenta + más hinchas), outro.
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .paths import FD, EMOJI, OUTRO
W, H = 1920, 1080
LW, HEAD, MH = 1280, 180, 720          # columna izquierda, banda superior, alto del partido
RX, RW = 1290, 630                     # columna de reacción
YEL, CEL, NAVY, WHITE, RED = (255, 212, 0), (108, 172, 228), (8, 16, 38), (255, 255, 255), (230, 33, 23)
COL = {"yel": YEL, "red": RED, "cel": CEL}
ENC = ["-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-profile:v", "high", "-level", "4.1",
       "-pix_fmt", "yuv420p", "-video_track_timescale", "15360", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]


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
    while s > 14 and d.textlength(text, font=font(name, s, var)) > maxw:
        s -= 2
    return font(name, s, var)


def emoji_img(ch, size):
    im = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=ImageFont.truetype(EMOJI, 109), embedded_color=True)
    im = im.crop(im.getbbox())
    r = size / max(im.size)
    return im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)


def split_emoji(t):
    return (t[:-1].rstrip(), t[-1]) if t and ord(t[-1]) > 0x2000 else (t, None)


def pill(im, x, y, text, fg, bg, size, var="Bold", pad=(22, 9), anchor="l"):
    d = ImageDraw.Draw(im)
    txt, emo = split_emoji(text)
    f = font("Oswald.ttf", size, var)
    bb = d.textbbox((0, 0), txt, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    e = emoji_img(emo, int(th * 1.25)) if emo else None
    w = tw + (e.width + 10 if e else 0) + 2 * pad[0]
    x0 = x - w / 2 if anchor == "c" else x
    d.rounded_rectangle((x0, y, x0 + w, y + th + 2 * pad[1]), radius=(th + 2 * pad[1]) // 2, fill=bg)
    d.text((x0 + pad[0] - bb[0], y + pad[1] - bb[1]), txt, font=f, fill=fg)
    if e:
        im.alpha_composite(e, (int(x0 + pad[0] + tw + 10), int(y + pad[1] + th / 2 - e.height / 2)))


def big(im, text, cx, y, size, fg, maxw, stroke=7):
    d = ImageDraw.Draw(im)
    txt, emo = split_emoji(text)
    f = fit(d, txt, "Anton-Regular.ttf", maxw - (size if emo else 0), size)
    bb = d.textbbox((0, 0), txt, font=f, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    e = emoji_img(emo, int(th * 0.9)) if emo else None
    x = cx - (tw + (e.width + 14 if e else 0)) / 2
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x - bb[0] + 5, y - bb[1] + 8), txt, font=f, fill=(0, 0, 0, 170), stroke_width=stroke,
                            stroke_fill=(0, 0, 0, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    d.text((x - bb[0], y - bb[1]), txt, font=f, fill=fg, stroke_width=stroke, stroke_fill=(0, 0, 0))
    if e:
        im.alpha_composite(e, (int(x + tw + 14), int(y + th / 2 - e.height / 2)))
    return y + th


def frame_png(path, cfg, g=None, idx=0, n=0):
    """bandas fijas: cabecera con gol/marcador, divisor, banda inferior con crédito."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, LW, HEAD), fill=NAVY)
    d.rectangle((0, HEAD + MH, LW, H), fill=NAVY)
    d.rectangle((LW, 0, RX, H), fill=YEL)
    fb = font("Oswald.ttf", 30, "SemiBold")
    from .paths import cfg as _cfg
    _b = _cfg().get("marca", "MI CANAL").upper().rsplit(" ", 1)
    _p = (_b[0] + " ") if len(_b) > 1 else ""
    d.text((40, 22), _p, font=fb, fill=WHITE)
    d.text((40 + d.textlength(_p, font=fb), 22), _b[-1], font=fb, fill=YEL)
    if g:
        ft = fit(d, g["title"], "Anton-Regular.ttf", 760, 84)
        bb = d.textbbox((0, 0), g["title"], font=ft)
        d.text((40 - bb[0], 70 - bb[1]), g["title"], font=ft, fill=WHITE)
        fs = font("Oswald.ttf", 44, "Bold")
        sw = d.textlength(g["score"], font=fs)
        d.rounded_rectangle((LW - 40 - sw - 48, 62, LW - 40, 134), radius=14, fill=YEL)
        d.text((LW - 40 - sw - 24, 66), g["score"], font=fs, fill=NAVY)
        d.text((LW - 40 - sw - 48, 140), g.get("counter", f"GOL {idx}/{n}"), font=font("Oswald.ttf", 26, "SemiBold"), fill=CEL)
    fc = font("Oswald.ttf", 24, "Regular")
    cw = d.textlength(cfg["credit"], font=fc)
    d.text(((LW - cw) / 2, H - 40), cfg["credit"], font=fc, fill=CEL)
    im.save(path)


def tag_png(path, left_tag, mood=None, mood_color="yel"):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if left_tag:
        pill(im, 24, HEAD + 20, left_tag, WHITE, RED + (235,), 30)
    if mood:
        pill(im, RX + RW / 2, 24, mood, NAVY if mood_color != "red" else WHITE, COL[mood_color] + (240,), 34, anchor="c")
    im.save(path)


def sub_png(path, text):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    big(im, text, LW / 2, HEAD + MH + 22, 86, YEL, LW - 80)
    im.save(path)


def run(ins, fc, out, dur):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[aud]",
                    "-t", str(dur), *ENC, out], check=True)


def resolve(cfg, item):
    """[ss, d] o [ss, d, KEY] -> (ss, d, src, strip)."""
    ss, d = item[0], item[1]
    if len(item) > 2:
        sc = cfg["sources"][item[2]]
        return ss, d, sc["src"], sc["strip"]
    return ss, d, cfg["react"], cfg["strip"]


def right_chain(j, label, react_cfg):
    x, y, w, h = react_cfg
    return (f"[{j}:v]fps=30,crop={w}:{h}:{x}:{y},scale={RW}:{H}:force_original_aspect_ratio=increase,crop={RW}:{H},unsharp=5:5:0.6,"
            f"setsar=1,setpts=PTS-STARTPTS[{label}]")


def part(cfg, tmp, out, left, right, overlays, goal_t=None, subs=(), speed=1.0, dur=None):
    """left: [[ss, d], ...] del partido; right: [[ss, d], ...] de reacciones; overlays: PNGs siempre visibles."""
    dur = dur or sum(it[1] for it in right)
    rr = [resolve(cfg, it) for it in right]
    ins = []
    for ss, d in left:
        ins += ["-ss", str(ss), "-t", str(d), "-i", cfg["match"]]
    for ss, d, src, _ in rr:
        ins += ["-ss", str(ss), "-t", str(d), "-i", src]
    nl, nr = len(left), len(right)
    pngs = list(overlays) + [p for _, _, p in subs]
    for p in pngs:
        ins += ["-loop", "1", "-t", str(dur), "-i", p]
    fc = [f"[{i}:v]fps=30,scale={LW}:{MH},setsar=1,setpts=(PTS-STARTPTS)/{speed}[l{i}]" for i in range(nl)]
    fc.append("".join(f"[l{i}]" for i in range(nl)) + f"concat=n={nl}:v=1:a=0,fps=30[left]")
    for k in range(nr):
        j = nl + k
        fc.append(right_chain(j, f"r{k}", rr[k][3]) + f";[{j}:a]aresample=44100,asetpts=PTS-STARTPTS[a{k}]")
    fc.append("".join(f"[r{k}][a{k}]" for k in range(nr)) + f"concat=n={nr}:v=1:a=1[right0][aud]")
    if goal_t is not None:
        g = goal_t
        z = f"1+0.16*between(t,{g},{g + 0.25})+0.08*between(t,{g + 0.25},{g + 1.8})"
        fc.append(f"[right0]scale=w='{RW}*({z})':h='{H}*({z})':eval=frame,crop={RW}:{H},"
                  f"drawbox=c=white@0.6:t=fill:enable='between(t,{g},{g + 0.12})'[right]")
    else:
        fc.append("[right0]null[right]")
    fc.append(f"color=c=0x081026:s={W}x{H}:r=30:d={dur}[bg];[bg][left]overlay=0:{HEAD}:shortest=0[c1];"
              f"[c1][right]overlay={RX}:0[c2]")
    last, base = "c2", nl + nr
    for k in range(len(overlays)):
        fc.append(f"[{last}][{base + k}:v]overlay[o{k}]")
        last = f"o{k}"
    for k, (a, b, _) in enumerate(subs):
        fc.append(f"[{last}][{base + len(overlays) + k}:v]overlay=enable='between(t,{a},{b})'[s{k}]")
        last = f"s{k}"
    fc.append(f"[{last}]format=yuv420p[v]")
    run(ins, fc, out, dur)


def intro(cfg, tmp, out):
    it = cfg["intro"]
    dur = sum(x[1] for x in it["right"])
    rr = [resolve(cfg, x) for x in it["right"]]
    p = os.path.join(tmp, "intro.png")
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, LW, H), fill=(8, 16, 38, 175))
    d.rectangle((LW, 0, RX, H), fill=YEL)
    pill(im, LW / 2, 230, __import__("autocanal.paths", fromlist=["cfg"]).cfg().get("marca", "MI CANAL").upper(), NAVY, YEL + (255,), 34, anchor="c")
    y = 330
    for i, ln in enumerate(it["lines"]):
        y = big(im, ln, LW / 2, y, [96, 150, 78][min(i, 2)], [WHITE, YEL, WHITE][min(i, 2)], LW - 120) + 34
    fc_ = font("Oswald.ttf", 24, "Regular")
    cw = d.textlength(cfg["credit"], font=fc_)
    d.text(((LW - cw) / 2, H - 40), cfg["credit"], font=fc_, fill=CEL)
    im.save(p)
    ins = ["-ss", str(it["bg"][0]), "-t", str(dur), "-i", cfg["match"]]
    for ss, dd, src, _ in rr:
        ins += ["-ss", str(ss), "-t", str(dd), "-i", src]
    nr = len(it["right"])
    ins += ["-loop", "1", "-t", str(dur), "-i", p]
    fc = [f"[0:v]fps=30,scale={LW}:{MH},setpts=(PTS-STARTPTS)/0.5,boxblur=10:2,setsar=1[left0];"
          f"[left0]scale={int(LW * 1.5)}:{H},crop={LW}:{H}[left]"]
    for k in range(nr):
        fc.append(right_chain(1 + k, f"r{k}", rr[k][3]) + f";[{1 + k}:a]aresample=44100,asetpts=PTS-STARTPTS[a{k}]")
    fc.append("".join(f"[r{k}][a{k}]" for k in range(nr)) + f"concat=n={nr}:v=1:a=1[right][aud]")
    fc.append(f"color=c=0x081026:s={W}x{H}:r=30:d={dur}[bg];[bg][left]overlay=0:0[c1];[c1][right]overlay={RX}:0[c2];"
              f"[c2][{1 + nr}:v]overlay,format=yuv420p[v]")
    run(ins, fc, out, dur)


def outro(cfg, tmp, out, dur=6.0):
    from .outro import asegurar
    asegurar()
    fr = os.path.join(OUTRO, "frames", "f%03d.png")
    last = os.path.join(OUTRO, "frames", "f077.png")
    p = os.path.join(tmp, "outro_bg.png")
    im = Image.new("RGBA", (W, H), NAVY + (255,))
    d = ImageDraw.Draw(im)
    for x0, w, col, a in [(150, 60, CEL, 120), (240, 22, YEL, 220), (1700, 60, CEL, 120), (1790, 22, YEL, 220)]:
        d.polygon([(x0, 0), (x0 + w, 0), (x0 + w - 600, H), (x0 - 600, H)], fill=col + (a,))
    big(im, "¿Y VOS DE QUÉ LADO ESTÁS?", W / 2, 70, 74, WHITE, 1500)
    big(im, "DEJALO EN LOS COMENTARIOS", W / 2, 175, 54, YEL, 1500, stroke=5)
    im.save(p)
    ins = ["-loop", "1", "-t", str(dur), "-i", p, "-framerate", "30", "-i", fr, "-loop", "1", "-t", str(dur), "-i", last,
           "-i", os.path.join(OUTRO, "pops.wav")]
    fc = ["[1:v]scale=-2:1344,setpts=PTS-STARTPTS[an];[2:v]scale=-2:1344[hold]",
          "[an][hold]concat=n=2:v=1:a=0,trim=duration=%s[ov]" % dur,
          f"[0:v][ov]overlay=(W-w)/2:-128,format=yuv420p[v]",
          f"[3:a]aresample=44100,aformat=channel_layouts=stereo,apad=whole_dur={dur}[aud]"]
    run(ins, fc, out, dur)


def main(cfg_path, out_dir):
    cfg = json.load(open(cfg_path))
    tmp = os.path.join(out_dir, "tmp")
    os.makedirs(tmp, exist_ok=True)
    only = os.environ.get("ONLY", "")
    want = lambda k: not only or k in only.split(",")
    parts = [("intro", os.path.join(out_dir, "p_intro.mp4"))]
    if want("intro"):
        intro(cfg, tmp, parts[0][1]); print("ok intro", flush=True)
    n = len(cfg["goals"])
    for i, g in enumerate(cfg["goals"], 1):
        fpng = os.path.join(tmp, f"frame{i}.png"); frame_png(fpng, cfg, g, i, n)
        ta = os.path.join(tmp, f"tagA{i}.png"); tag_png(ta, g.get("tagA", "EN VIVO"), g["mood"], g.get("mood_color", "yel"))
        tb = os.path.join(tmp, f"tagB{i}.png"); tag_png(tb, "REPETICIÓN · MÁS REACCIONES", g.get("moodB", g["mood"]), g.get("moodB_color", g.get("mood_color", "yel")))
        subs = []
        for k, (a, b, t) in enumerate(g.get("subs", [])):
            sp = os.path.join(tmp, f"sub{i}_{k}.png"); sub_png(sp, t); subs.append((a, b, sp))
        oa = os.path.join(out_dir, f"p_{i}A.mp4")
        if want(f"{i}A"):
            part(cfg, tmp, oa, g["A"]["left"], g["A"]["right"], [fpng, ta], g["A"]["goal_t"], subs)
            print(f"ok {i}A", flush=True)
        parts.append((f"{i}A", oa))
        if "B" in g:
            ob = os.path.join(out_dir, f"p_{i}B.mp4")
            if want(f"{i}B"):
                bl = g["B"]["left"]; br = g["B"]["right"]
                speed = sum(d for _, d in bl) / sum(x[1] for x in br)
                part(cfg, tmp, ob, bl, br, [fpng, tb], None, (), speed=round(speed, 4))
                print(f"ok {i}B", flush=True)
            parts.append((f"{i}B", ob))
    oo = os.path.join(out_dir, "p_outro.mp4")
    if want("outro"):
        outro(cfg, tmp, oo); print("ok outro", flush=True)
    parts.append(("outro", oo))
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for _, p in parts)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    "-movflags", "+faststart", os.path.join(out_dir, "long.mp4")], check=True)
    print("ok long", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
