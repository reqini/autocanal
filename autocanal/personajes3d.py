"""Librería de personajes 3D (se usa DENTRO de Blender).
Todos comparten el mismo "esqueleto" simple (rig): raíz, brazos/alas que se mueven, ojos que parpadean y miran,
cejas, cachetes y boca que habla. Así cualquier escena los anima igual con `animar()`.

Personajes: letra/número (cualquier carácter), Lolo (patito de hule), Rita (ranita), Tito (osito), Mishi (gatita).
Para sumar uno nuevo: una función que arme el cuerpo y llame a `_cara()` y `_brazo()`, y lo registrás en CATALOGO.
"""
import math
import bpy
import bmesh

NAVY = (28, 36, 84)
_MATS = {}


def srgb(c):
    return tuple(((v / 255) ** 2.2) for v in c)


def mat(nombre, color, rough=0.32, coat=0.7, emit=0.0, sss=0.0):
    k = (nombre, color, rough, coat, emit)
    if k in _MATS:
        return _MATS[k]
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    for n in ("Coat Weight", "Clearcoat"):
        if n in b.inputs:
            b.inputs[n].default_value = coat
    for n in ("Subsurface Weight", "Subsurface"):
        if n in b.inputs and sss:
            b.inputs[n].default_value = sss
    if emit and "Emission Strength" in b.inputs:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emit
    _MATS[k] = m
    return m


def _obj(o, m, parent):
    bpy.ops.object.shade_smooth()
    if m:
        o.data.materials.append(m)
    if parent:
        o.parent = parent
    return o


def esfera(loc, r, m, parent=None, escala=(1, 1, 1), seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    o = bpy.context.object
    o.scale = escala
    return _obj(o, m, parent)


def cilindro(loc, r, largo, m, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=largo, location=loc, rotation=rot, vertices=24)
    o = bpy.context.object
    return _obj(o, m, parent)


def cono(loc, r1, r2, largo, m, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=largo, location=loc, rotation=rot, vertices=24)
    return _obj(bpy.context.object, m, parent)


def arco(loc, r, grosor, m, parent=None, arriba=False, escala=(1, 0.55, 1)):
    """Media rosca: sonrisa (o ceja si arriba=True)."""
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=grosor, location=(0, 0, 0),
                                     major_segments=32, minor_segments=10)
    o = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co.y < -0.02 if arriba else v.co.y > 0.02)], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    o.rotation_euler = (math.radians(90), 0, 0)
    o.location = loc
    o.scale = escala
    return _obj(o, m, parent)


def vacio(nombre, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(nombre, None)
    bpy.context.collection.objects.link(e)
    e.parent = parent
    e.location = loc
    return e


class Rig:
    def __init__(self, nombre):
        self.raiz = vacio(nombre)
        self.nombre = nombre
        self.brazos = []   # (pivote, lado)
        self.ojos = []     # (blanco, pupila, brillo)
        self.cejas = []
        self.boca = None
        self.boca_abierta = None
        self.alto = 2.0
        self.mira = []     # pupilas que se mueven


def _cara(rig, cx, cz, frente_y, ojo_r=0.38, sep=0.42, iris=(70, 40, 20), mejillas=True, boca_z=None, boca_r=0.3,
          cachete_col=(255, 120, 150)):
    p = rig.raiz
    blanco = mat("ojo", (1, 1, 1), rough=0.15, coat=1)
    negro = mat("pupila", (0.005, 0.005, 0.01), rough=0.05, coat=1)
    col_iris = mat(f"iris{iris}", srgb(iris), rough=0.1, coat=1)
    oscuro = mat("linea", srgb(NAVY), rough=0.4, coat=0.3)
    for s in (-1, 1):
        x = cx + s * sep
        o = esfera((x, frente_y + ojo_r * 0.35, cz), ojo_r, blanco, p, escala=(1, 0.75, 1.15))
        ir = esfera((x, frente_y - ojo_r * 0.35, cz - ojo_r * 0.05), ojo_r * 0.52, col_iris, p, escala=(1, 0.5, 1.1))
        pu = esfera((x, frente_y - ojo_r * 0.55, cz - ojo_r * 0.05), ojo_r * 0.3, negro, p, escala=(1, 0.5, 1.1))
        br = esfera((x - ojo_r * 0.18, frente_y - ojo_r * 0.72, cz + ojo_r * 0.22), ojo_r * 0.12, blanco, p)
        br2 = esfera((x + ojo_r * 0.15, frente_y - ojo_r * 0.72, cz - ojo_r * 0.2), ojo_r * 0.06, blanco, p)
        rig.ojos.append((o, (ir, pu, br, br2)))
        c = arco((x, frente_y - ojo_r * 0.1, cz + ojo_r * 1.35), ojo_r * 0.55, ojo_r * 0.09, oscuro, p, arriba=True,
                 escala=(1, 0.5, 1))
        rig.cejas.append(c)
        if mejillas:
            esfera((x + s * ojo_r * 0.55, frente_y + 0.02, cz - ojo_r * 1.55), ojo_r * 0.38,
                   mat("cachete", srgb(cachete_col), rough=0.6, coat=0, emit=0.15), p, escala=(1, 0.3, 0.7))
    bz = boca_z if boca_z is not None else cz - ojo_r * 1.9
    rig.boca = arco((cx, frente_y - 0.02, bz), boca_r, boca_r * 0.22, oscuro, p)
    bo = esfera((cx, frente_y + 0.02, bz - boca_r * 0.15), boca_r * 0.7, mat("bocaint", srgb((120, 20, 40)), coat=0.2),
                p, escala=(1, 0.4, 0.75))
    lengua = esfera((cx, frente_y - 0.0, bz - boca_r * 0.4), boca_r * 0.4, mat("lengua", srgb((240, 90, 110))), p,
                    escala=(1, 0.4, 0.5))
    rig.boca_abierta = (bo, lengua)


def _brazo(rig, hombro, lado, largo=1.1, grosor=0.09, color=NAVY, guante=True):
    piv = vacio(f"hombro_{rig.nombre}", rig.raiz, hombro)
    m = mat(f"brazo{color}", srgb(color), rough=0.4, coat=0.3)
    cilindro((lado * largo / 2, 0, 0), grosor, largo, m, piv, rot=(0, math.radians(90), 0))
    if guante:
        g = mat("guante", (0.95, 0.95, 0.97), rough=0.5, coat=0.2)
        esfera((lado * largo, 0, 0), grosor * 2.6, g, piv, escala=(1, 0.8, 1))
        esfera((lado * (largo + grosor * 1.6), -grosor, grosor * 1.8), grosor * 1.1, g, piv)  # pulgar
    rig.brazos.append((piv, lado))
    return piv


def _piernas(rig, sep=0.35, alto=0.62, grosor=0.09, color=NAVY, zapato=(230, 50, 60)):
    m = mat(f"pierna{color}", srgb(color), rough=0.4, coat=0.3)
    zs = mat(f"zapato{zapato}", srgb(zapato), rough=0.3, coat=0.8)
    suela = mat("suela", (0.95, 0.95, 0.95), rough=0.6, coat=0)
    for s in (-1, 1):
        cilindro((s * sep, 0, alto / 2 + 0.08), grosor, alto, m, rig.raiz)
        esfera((s * (sep + 0.05), -0.14, 0.1), 0.22, zs, rig.raiz, escala=(1, 1.5, 0.62))
        esfera((s * (sep + 0.05), -0.14, 0.03), 0.22, suela, rig.raiz, escala=(1.02, 1.52, 0.25))


# ------------------------------------------------------------------ personajes
def letra(ch, color, fuente, nombre=None):
    rig = Rig(nombre or f"pj_{ch}")
    bpy.ops.object.text_add(location=(0, 0, 0))
    t = bpy.context.object
    t.data.body = ch
    if fuente:
        t.data.font = fuente
    t.data.align_x, t.data.align_y = "CENTER", "BOTTOM"
    t.data.size = 4.2
    t.data.extrude = 0.34
    t.data.bevel_depth = 0.09
    t.data.bevel_resolution = 5
    t.rotation_euler = (math.radians(90), 0, 0)
    t.location = (0, 0, 0.7)
    t.data.materials.append(mat(f"letra{color}", srgb(color), rough=0.22, coat=1))
    t.parent = rig.raiz
    bpy.context.view_layer.update()
    xs = [v[0] for v in t.bound_box]
    ys = [v[1] for v in t.bound_box]
    ancho, alto = max(xs) - min(xs), max(ys) - min(ys)
    rig.alto = alto + 0.7
    frente = -0.34 - 0.09
    _cara(rig, 0, 0.7 + alto * 0.74, frente - 0.05, ojo_r=0.3, sep=0.34, boca_z=0.7 + alto * 0.45, boca_r=0.26)
    for s in (-1, 1):
        _brazo(rig, (s * max(0.5, ancho * 0.5), 0, 0.7 + alto * 0.48), s)
    _piernas(rig)
    return rig


def bolita(color, nombre="bolita"):
    """Bolita de pintura de un color (para aprender colores): cuerpo redondo brillante, cara, guantes y zapatillas."""
    rig = Rig(nombre)
    m = mat(f"bolita{color}", srgb(color), rough=0.18, coat=1)
    esfera((0, 0, 1.85), 1.25, m, rig.raiz, escala=(1, 0.9, 1.05))
    esfera((-0.45, -0.75, 2.5), 0.22, mat("brillo_b", (1, 1, 1), rough=0.05, coat=1, emit=0.6), rig.raiz,
           escala=(1, 0.3, 0.7))
    rig.alto = 3.2
    _cara(rig, 0, 2.25, -1.08, ojo_r=0.32, sep=0.4, boca_z=1.5, boca_r=0.3)
    for s in (-1, 1):
        _brazo(rig, (s * 1.15, 0, 1.85), s, largo=0.9)
    _piernas(rig, sep=0.45)
    return rig


def lolo(nombre="lolo"):
    """Lolo, el patito de hule (amarillo brillante, pico naranja, alitas)."""
    rig = Rig(nombre)
    p = rig.raiz
    am = mat("lolo", srgb((255, 205, 20)), rough=0.18, coat=1, sss=0.1)
    na = mat("pico", srgb((255, 130, 20)), rough=0.25, coat=1)
    cuerpo = esfera((0, 0, 1.0), 1.0, am, p, escala=(1.15, 1.0, 0.85))
    esfera((0, 0.9, 1.25), 0.45, am, p, escala=(0.8, 1, 1.1))  # colita
    esfera((0, -0.25, 2.15), 0.78, am, p)  # cabeza
    esfera((0, -1.0, 2.0), 0.36, na, p, escala=(1.2, 1.0, 0.45))  # pico arriba
    esfera((0, -0.95, 1.86), 0.3, na, p, escala=(1.1, 0.9, 0.35))  # pico abajo
    rig.alto = 3.0
    _cara(rig, 0, 2.4, -0.82, ojo_r=0.24, sep=0.3, boca_z=1.86, boca_r=0.0001, iris=(40, 90, 200))
    for s in (-1, 1):  # alitas
        piv = vacio("ala", p, (s * 1.05, -0.1, 1.15))
        esfera((s * 0.25, 0, 0.1), 0.42, am, piv, escala=(0.45, 0.9, 0.7))
        rig.brazos.append((piv, s))
    return rig


def rita(nombre="rita"):
    """Rita, la ranita (verde, ojos arriba, moñito rosa)."""
    rig = Rig(nombre)
    p = rig.raiz
    vd = mat("rita", srgb((90, 200, 90)), rough=0.3, coat=0.8, sss=0.1)
    pz = mat("panza", srgb((200, 240, 160)), rough=0.4, coat=0.4)
    esfera((0, 0, 1.2), 1.1, vd, p, escala=(1.2, 0.9, 1.0))
    esfera((0, -0.55, 1.05), 0.75, pz, p, escala=(1.1, 0.5, 0.9))
    for s in (-1, 1):
        esfera((s * 0.5, -0.1, 2.15), 0.45, vd, p)
    rig.alto = 2.6
    _cara(rig, 0, 2.25, -0.42, ojo_r=0.34, sep=0.5, boca_z=1.6, boca_r=0.45, iris=(30, 120, 40))
    moño = mat("moño", srgb((255, 90, 160)), coat=1)
    for s in (-1, 1):
        esfera((0.6 + s * 0.22, 0.1, 2.68), 0.2, moño, p, escala=(1.3, 0.6, 0.9))
    for s in (-1, 1):
        _brazo(rig, (s * 1.15, -0.1, 1.35), s, largo=0.8, grosor=0.12, color=(70, 170, 70), guante=False)
        esfera((s * 0.7, -0.3, 0.12), 0.35, vd, p, escala=(1.2, 1.6, 0.4))  # patas
    return rig


def tito(nombre="tito"):
    """Tito, el osito (marrón, hocico claro, orejas redondas)."""
    rig = Rig(nombre)
    p = rig.raiz
    ma = mat("tito", srgb((170, 110, 60)), rough=0.7, coat=0.1)
    cl = mat("hocico", srgb((235, 200, 150)), rough=0.7, coat=0.1)
    esfera((0, 0, 1.15), 1.0, ma, p, escala=(1.0, 0.85, 1.05))
    esfera((0, -0.6, 1.05), 0.6, cl, p, escala=(1, 0.5, 1.0))
    esfera((0, -0.1, 2.4), 0.85, ma, p)
    for s in (-1, 1):
        esfera((s * 0.65, 0, 3.1), 0.32, ma, p, escala=(1, 0.6, 1))
        esfera((s * 0.65, -0.12, 3.1), 0.18, cl, p, escala=(1, 0.5, 1))
    esfera((0, -0.85, 2.2), 0.36, cl, p, escala=(1.1, 0.7, 0.8))
    esfera((0, -1.1, 2.32), 0.13, mat("nariz", (0.02, 0.02, 0.02), rough=0.1, coat=1), p)
    rig.alto = 3.4
    _cara(rig, 0, 2.62, -0.78, ojo_r=0.22, sep=0.32, boca_z=2.05, boca_r=0.18, iris=(60, 30, 10))
    for s in (-1, 1):
        _brazo(rig, (s * 0.95, 0, 1.5), s, largo=0.7, grosor=0.2, color=(170, 110, 60), guante=False)
        esfera((s * 0.5, -0.2, 0.2), 0.36, ma, p, escala=(1, 1.4, 0.6))
    return rig


def mishi(nombre="mishi"):
    """Mishi, la gatita (gris clara, orejas puntiagudas, bigotes)."""
    rig = Rig(nombre)
    p = rig.raiz
    gr = mat("mishi", srgb((200, 200, 215)), rough=0.6, coat=0.2)
    rs = mat("orejaint", srgb((255, 160, 190)), rough=0.6, coat=0.1)
    esfera((0, 0, 1.1), 0.95, gr, p, escala=(1, 0.85, 1.05))
    esfera((0, -0.1, 2.35), 0.85, gr, p, escala=(1.1, 1, 0.95))
    for s in (-1, 1):
        cono((s * 0.55, 0, 3.1), 0.32, 0.0, 0.6, gr, p, rot=(0, s * 0.3, 0))
        cono((s * 0.55, -0.1, 3.05), 0.18, 0.0, 0.4, rs, p, rot=(0, s * 0.3, 0))
        for k in (-1, 1):
            cilindro((s * 0.65, -0.85, 2.1 + k * 0.08), 0.015, 0.7, mat("bigote", (0.1, 0.1, 0.1)), p,
                     rot=(0, math.radians(90) + s * k * 0.15, 0))
    esfera((0, -0.95, 2.22), 0.1, rs, p)
    rig.alto = 3.3
    _cara(rig, 0, 2.55, -0.82, ojo_r=0.26, sep=0.36, boca_z=2.0, boca_r=0.16, iris=(60, 170, 90))
    for s in (-1, 1):
        _brazo(rig, (s * 0.9, 0, 1.4), s, largo=0.7, grosor=0.17, color=(200, 200, 215), guante=False)
        esfera((s * 0.45, -0.2, 0.18), 0.32, gr, p, escala=(1, 1.4, 0.6))
    cola = cilindro((0.7, 0.8, 1.3), 0.12, 1.4, gr, p, rot=(0.6, 0.6, 0))
    return rig


CATALOGO = {"lolo": lolo, "rita": rita, "tito": tito, "mishi": mishi, "bolita": bolita}


# ------------------------------------------------------------------ animación común
def animar(rig, tramos, fps, nf, pos=(0, 0, 0), escala=1.0, fase=0.0, entra=8.0, habla=(), festeja=(), triste=(),
           baila=True, paso=2):
    """tramos: [(f_ini, f_fin)] en que se ve. habla/festeja/triste: [(t0, t1)] en segundos."""
    en = lambda t, ls: any(a <= t <= b for a, b in ls)
    for f in range(1, nf + 1, paso):
        t = f / fps
        a0 = next((a for a, b in tramos if a <= f <= b), None)
        r = rig.raiz
        if a0 is None:
            r.location = (pos[0], pos[1], -30)
            r.scale = (escala,) * 3
            r.rotation_euler = (0, 0, 0)
        else:
            u = (f - a0) / fps
            ent = 1 - (1 - min(1, u / 0.5)) ** 3
            fest = en(t, festeja)
            amp = 0.35 if baila else 0.08
            salto = abs(math.sin((t + fase) * math.pi * (3.0 if fest else 2.2))) * (1.4 if fest else amp) * escala
            if en(t, triste):
                salto = 0
            r.location = (pos[0] + (1 - ent) * entra, pos[1], pos[2] + salto)
            sq = 1 + 0.07 * math.sin((t + fase) * math.pi * 4.4)
            r.scale = (escala / math.sqrt(sq), escala / math.sqrt(sq), escala * sq)
            giro = math.tau * min(1, max(0, (t - next(a for a, b in festeja if a <= t <= b)) / 0.6)) if fest else 0
            r.rotation_euler = (0, math.sin((t + fase) * 2.2) * 0.07, math.sin((t + fase) * 1.1) * 0.16 + giro)
        r.keyframe_insert("location", frame=f)
        r.keyframe_insert("scale", frame=f)
        r.keyframe_insert("rotation_euler", frame=f)
        fest = en(t, festeja)
        for piv, s in rig.brazos:
            if fest:
                ang = s * (1.6 + 0.4 * math.sin(t * 12))
            elif en(t, triste):
                ang = -s * 0.9
            else:
                ang = s * (0.5 + 0.8 * math.sin((t + fase) * 5 + (0 if s < 0 else math.pi)))
            piv.rotation_euler = (0, -ang if piv.name.startswith("ala") else ang, 0)
            piv.keyframe_insert("rotation_euler", frame=f)
        parp = ((t + fase * 3) % 3.4) < 0.12
        mx = math.sin((t + fase) * 0.9) * 0.06
        for o, partes in rig.ojos:
            o.scale = (1, 0.75, 0.1 if parp else 1.15)
            o.keyframe_insert("scale", frame=f)
            for x in partes:
                x.hide_render = parp
                x.keyframe_insert("hide_render", frame=f)
        hab = en(t, habla)
        for c in rig.cejas:
            c.location.z = c.location.z if not hasattr(c, "_z0") else c["_z0"]
        if rig.boca_abierta:
            bo, le = rig.boca_abierta
            ab = (hab and math.sin(t * 22) > -0.3) or fest
            for x in (bo, le):
                x.hide_render = not ab
                x.keyframe_insert("hide_render", frame=f)
            if ab:
                k = 0.6 + 0.5 * abs(math.sin(t * 17)) if hab else 1.1
                bo.scale = (1, 0.4, 0.75 * k)
                bo.keyframe_insert("scale", frame=f)
            if rig.boca:
                rig.boca.hide_render = ab
                rig.boca.keyframe_insert("hide_render", frame=f)
