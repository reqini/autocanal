"""Escena 3D para Blender (se ejecuta DENTRO de Blender, sin abrirlo):
    blender -b -P escena3d.py -- plan.json
Arma el prado, la cámara y las luces, y anima la lista de EVENTOS del plan con los personajes de personajes3d.py:
  titulo · anfitrion (Lolo y amigos hablan) · item (letra/número + dibujo + palabra) · pregunta (¿dónde está…?
  con cuenta regresiva y festejo) · contar (aparecen los objetos de a uno) · final (todos bailan)."""
import json, math, os, random, sys
import bpy

plan = json.load(open(sys.argv[sys.argv.index("--") + 1]))
sys.path.insert(0, plan["libdir"])
import personajes3d as P  # noqa: E402

W, H, FPS = plan["w"], plan["h"], plan["fps"]
NF = int(plan["dur"] * FPS)
V = H > W
F = lambda t: max(1, int(t * FPS))


def escenario():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    if plan.get("motor") == "CYCLES":
        sc.render.engine = "CYCLES"
        sc.cycles.samples = plan.get("muestras", 24)
        sc.cycles.use_denoising = True
    else:
        for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                sc.render.engine = e
                break
            except TypeError:
                continue
        for k, v in (("taa_render_samples", plan.get("muestras", 48)), ("use_gtao", True), ("use_soft_shadows", True),
                     ("use_raytracing", True), ("use_shadows", True)):
            try:
                setattr(sc.eevee, k, v)
            except AttributeError:
                pass
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, NF
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(plan["frames"], "f")
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("cielo")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    grad, coord, mp, ramp = (nt.nodes.new(n) for n in ("ShaderNodeTexGradient", "ShaderNodeTexCoord",
                                                       "ShaderNodeMapping", "ShaderNodeValToRGB"))
    mp.inputs["Rotation"].default_value = (0, math.pi / 2, 0)
    ramp.color_ramp.elements[0].color = (*P.srgb((70, 165, 255)), 1)
    ramp.color_ramp.elements[1].color = (*P.srgb((190, 232, 255)), 1)
    nt.links.new(coord.outputs["Window"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    verde = P.mat("pasto", P.srgb((96, 190, 80)), rough=0.9, coat=0)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.data.materials.append(verde)
    loma = P.mat("loma", P.srgb((120, 205, 100)), rough=0.9, coat=0)
    for x, y, s in [(-9, 22, 9), (7, 26, 11), (20, 30, 10), (-22, 28, 12)]:
        P.esfera((x, y, -s * 0.55), s, loma, escala=(1.6, 1, 0.6))
    tronco = P.mat("tronco", P.srgb((130, 84, 50)), rough=0.8, coat=0)
    copa = P.mat("copa", P.srgb((46, 160, 68)), rough=0.6, coat=0.2)
    for x, y in [(-8.5, 8), (9, 10), (-13, 14), (14, 16)]:
        P.cilindro((x, y, 1.0), 0.25, 2.0, tronco)
        P.esfera((x, y, 2.6), 1.3, copa)
        P.esfera((x + 0.7, y, 2.2), 0.9, copa)
    r = random.Random(4)
    for i in range(30):
        c = r.choice([(255, 255, 255), (255, 214, 10), (255, 120, 170), (160, 120, 255)])
        P.esfera((r.uniform(-12, 12), r.uniform(1, 9), 0.05), 0.12, P.mat(f"flor{c}", P.srgb(c), emit=0.25))
    P.esfera((14, 40, 16), 3, P.mat("sol", P.srgb((255, 214, 40)), emit=4))
    nube = P.mat("nube", (0.95, 0.97, 1.0), rough=0.9, coat=0)
    for x, z in [(-12, 11), (2, 13), (16, 10)]:
        for dx, rr in [(0, 1.6), (1.4, 1.2), (-1.3, 1.1)]:
            P.esfera((x + dx, 35, z), rr, nube)
    bpy.ops.object.light_add(type="SUN", location=(5, -5, 10))
    s = bpy.context.object
    s.data.energy = 3.4
    s.data.angle = math.radians(10)
    s.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
    for loc, en, rot in [((-5, -7, 5), 700, (65, 0, -35)), ((4, 6, 5), 400, (-60, 0, 150))]:  # relleno y contraluz
        bpy.ops.object.light_add(type="AREA", location=loc)
        a = bpy.context.object
        a.data.energy, a.data.size = en, 6
        a.rotation_euler = tuple(math.radians(v) for v in rot)
    loc = (0, -14, 2.3) if not V else (0, -8.5, 2.4)
    bpy.ops.object.camera_add(location=loc, rotation=(math.radians(88 if not V else 87), 0, 0))
    cam = bpy.context.object
    cam.data.lens = 40 if not V else 26
    sc.camera = cam
    for f in range(1, NF + 1, FPS):
        t = f / FPS
        cam.location = (math.sin(t * 0.18) * (0.6 if not V else 0.0), loc[1] + math.sin(t * 0.25) * 0.6, loc[2])
        cam.keyframe_insert("location", frame=f)
    return cam


def texto3d(txt, loc, size, color, nombre="txt"):
    bpy.ops.object.text_add(location=loc)
    t = bpy.context.object
    t.name = nombre
    t.data.body = txt
    t.data.font = FUENTE
    t.data.align_x, t.data.align_y = "CENTER", "CENTER"
    t.data.size = size
    t.data.extrude = size * 0.11
    t.data.bevel_depth = size * 0.03
    t.rotation_euler = (math.radians(90), 0, 0)
    t.data.materials.append(P.mat(f"t{color}", P.srgb(color), coat=1))
    return t


def imagen(path, loc, alto):
    bpy.ops.mesh.primitive_plane_add(size=alto, location=loc, rotation=(math.radians(90), 0, 0))
    pl = bpy.context.object
    m = bpy.data.materials.new("img")
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    b = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    if "Emission Color" in b.inputs:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = 0.35
    try:
        m.blend_method = "HASHED"
    except AttributeError:
        pass
    pl.data.materials.append(m)
    return pl


def mostrar(objs, t0, t1, pop=True):
    """Visible solo entre t0 y t1, con un 'pop' al aparecer."""
    a, b = F(t0), F(t1)
    for o in objs:
        base = tuple(o.scale)
        o.scale = (0.001,) * 3
        o.keyframe_insert("scale", frame=1)
        o.keyframe_insert("scale", frame=max(1, a - 1))
        if pop:
            o.scale = tuple(v * 1.18 for v in base)
            o.keyframe_insert("scale", frame=a + int(FPS * 0.2))
        o.scale = base
        o.keyframe_insert("scale", frame=a + int(FPS * 0.35))
        o.keyframe_insert("scale", frame=b)
        o.scale = (0.001,) * 3
        o.keyframe_insert("scale", frame=b + 1)


def confeti(t0, centro, n=60):
    r = random.Random(int(t0 * 100))
    cols = [(239, 59, 54), (255, 153, 0), (250, 204, 21), (34, 197, 94), (14, 165, 233), (124, 58, 237)]
    for i in range(n):
        bpy.ops.mesh.primitive_cube_add(size=0.12)
        c = bpy.context.object
        c.data.materials.append(P.mat(f"conf{i % 6}", P.srgb(cols[i % 6]), emit=0.4))
        x0, z0 = centro[0] + r.uniform(-4, 4), centro[2] + r.uniform(4, 7)
        vx = r.uniform(-1, 1)
        for dt in (0, 0.4, 0.9, 1.5, 2.2):
            f = F(t0 + dt)
            c.location = (x0 + vx * dt, centro[1] - 1, z0 - dt * dt * 1.6 - dt * 1.5)
            c.rotation_euler = (dt * 7 + i, dt * 5, dt * 3 + i)
            c.keyframe_insert("location", frame=f)
            c.keyframe_insert("rotation_euler", frame=f)
        c.scale = (1, 0.15, 0.6)
        mostrar([c], t0, t0 + 2.2, pop=False)


def crear(ch, color, fuente, nombre):
    """Una letra/número con cuerpo propio, o una bolita del color si es una palabra (ROJO, AZUL…)."""
    return P.bolita(color, nombre) if len(ch) > 2 else P.letra(ch, color, fuente, nombre)


# ------------------------------------------------------------------ eventos
escenario()
FUENTE = bpy.data.fonts.load(plan["fuente"]) if os.path.exists(plan["fuente"]) else None
EV = plan["eventos"]
HABLA = {k: [tuple(x) for x in v] for k, v in plan["habla"].items()}
fase = 0.0

for nombre in plan.get("anfitriones", ["lolo"]):
    fest = [(e["t_resp"], e["t1"]) for e in EV if e["tipo"] == "pregunta"]
    for lugar in ("centro", "lado"):
        vis = [(F(e["t0"]), F(e["t1"])) for e in EV if e["tipo"] == "anfitrion" and e.get("quien", "lolo") == nombre
               and e.get("lugar", "lado") == lugar]
        if not vis:
            continue
        rig = P.CATALOGO[nombre](f"{nombre}_{lugar}")
        if lugar == "centro":
            pos, esc = ((0, -1, 0), 1.25) if not V else ((0, -1, 0), 0.9)
        else:
            pos, esc = ((-3.9, -1.2, 0), 0.85) if not V else ((0, -4.6, -0.2), 0.32)
        P.animar(rig, vis, FPS, NF, pos=pos, escala=esc, entra=-6, habla=HABLA.get(nombre, []), festeja=fest,
                 baila=False)

for e in EV:
    fase += 0.37
    if e["tipo"] == "titulo":
        z = e.get("z", 4.2 if not V else 6.6)
        mostrar([texto3d(e["texto"], (0, 1, z), 1.0 if not V else 0.72, (255, 196, 0))], e["t0"], e["t1"])
    elif e["tipo"] == "item":
        rig = crear(e["ch"], tuple(e["color"]), FUENTE, f"pj_{e['ch']}_{e['t0']}")
        pos = (-1.2, 0, 0) if not V else (0, -1.0, 0)
        P.animar(rig, [(F(e["t0"]), F(e["t1"]))], FPS, NF, pos=pos, fase=fase, habla=HABLA.get(e["ch"], []))
        if e.get("img"):
            loc = (3.8, 0.5, 2.8) if not V else (0, 1.5, 6.0)
            alto = 2.6 if not V else 2.4
            mostrar([imagen(e["img"], loc, alto),
                     texto3d(e["palabra"].upper(), (loc[0], loc[1], loc[2] - alto * 0.66), alto * (0.36 if not V else 0.45),
                             tuple(e["color"]))],
                    e["t0"] + min(0.9, (e["t1"] - e["t0"]) * 0.25), e["t1"])
    elif e["tipo"] == "pregunta":
        n = len(e["opciones"])
        sep = 3.3 if not V else 1.75
        esc = 0.8 if not V else 0.5
        for i, (ch, c) in enumerate(zip(e["opciones"], e["colores"])):
            rig = crear(ch, tuple(c), FUENTE, f"op_{ch}_{e['t0']}")
            ok = ch == e["correcta"]
            x = (i - (n - 1) / 2) * sep + (1.2 if not V else 0)
            P.animar(rig, [(F(e["t0"]), F(e["t1"]))], FPS, NF, pos=(x, 0 if not V else -1.5, 0), escala=esc,
                     fase=fase + i * 0.5,
                     festeja=[(e["t_resp"], e["t1"])] if ok else [], triste=[(e["t_resp"], e["t1"])] if not ok else [],
                     habla=[(e["t_resp"], e["t_resp"] + 1.2)] if ok else [])
            if ok:
                confeti(e["t_resp"], (x, 0, 0))
                bpy.ops.mesh.primitive_torus_add(major_radius=2.1 * esc, minor_radius=0.08, location=(x, 0.3, 2.4 * esc),
                                                 rotation=(math.radians(90), 0, 0))
                aro = bpy.context.object
                aro.data.materials.append(P.mat("aro", P.srgb((255, 214, 10)), emit=2))
                mostrar([aro], e["t_resp"], e["t1"])
        for k, num in enumerate(("3", "2", "1")):
            t0 = e["t_cuenta"] + k * e.get("paso", 1.0)
            mostrar([texto3d(num, (0, 1, 4.5 if not V else 4.6), 2.4 if not V else 1.8, (255, 120, 40))],
                    t0, t0 + e.get("paso", 1.0) - 0.05)
        mostrar([texto3d(e["texto"], (0, 1, 4.8 if not V else 5.6), 0.9 if not V else 0.42, (255, 196, 0))],
                e["t0"], e["t_cuenta"])
    elif e["tipo"] == "contar":
        n = e["n"]
        cols_ = min(5, n)
        filas = math.ceil(n / cols_)
        tam = 1.5 if not V else 1.2
        for j in range(n):
            x = ((j % cols_) - (cols_ - 1) / 2) * tam * 1.1 + (1.2 if not V else 0)
            z = 3.4 - (j // cols_) * tam * 1.1 + (filas - 1) * tam * 0.5 + (0 if not V else 2.4)
            t_ap = e["t_objs"][j] if j < len(e["t_objs"]) else e["t0"]
            mostrar([imagen(e["img"], (x, 0.5, z), tam)], t_ap, e["t1"])
        mostrar([texto3d(str(n), (1.2 if not V else 0, 0.3, 0.9 if not V else 1.2), 1.6, tuple(e["color"]))],
                e["t_resp"], e["t1"])
        confeti(e["t_resp"], (0, 0, 0), 40)
    elif e["tipo"] == "final":
        m = len(e["chars"])
        fila = e["chars"] if m <= 10 else e["chars"][::max(1, m // 9)]
        k = len(fila)
        sep = min(2.6, 15 / k) if not V else min(1.3, 6.2 / k)
        esc = min(0.75, 4.2 / k) if not V else min(0.5, 2.4 / k)
        for j, (ch, c) in enumerate(fila):
            rig = crear(ch, tuple(c), FUENTE, f"fin_{ch}")
            P.animar(rig, [(F(e["t0"]), NF)], FPS, NF, pos=((j - (k - 1) / 2) * sep, 2, 0), escala=esc,
                     fase=j * 0.37, entra=0, festeja=[(e["t0"] + 0.5, e["t0"] + 1.5)])
        mostrar([texto3d(e.get("texto", "¡MUY BIEN!"), (0, 1, 4.4 if not V else 6.6), 1.0 if not V else 0.6,
                         (255, 196, 0))], e["t0"], plan["dur"])
        confeti(e["t0"] + 0.3, (0, 2, 0), 80)

if plan.get("solo"):
    for f in plan["solo"]:
        bpy.context.scene.frame_set(f)
        bpy.context.scene.render.filepath = os.path.join(plan["frames"], f"f{f:04d}")
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
