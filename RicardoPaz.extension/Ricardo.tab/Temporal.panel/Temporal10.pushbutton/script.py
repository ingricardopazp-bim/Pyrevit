# -*- coding: utf-8 -*-
"""Puntos de subelementos en un suelo sobre una cara, 5 cm por encima de ella.

Logica:
 1) Cruce en XY: se genera una malla densa sobre la extension en planta de la
    CARA y solo se conservan los puntos que caen dentro de la cara Y dentro de
    la cara superior del SUELO. Ademas se agregan puntos a lo largo de los
    bordes de la cara para que el contorno quede cubierto.
 2) En Z: ray vertical contra la cara -> cota de la cara; el punto se crea a
    esa cota + desfase (por defecto 5 cm).
 3) Los subelementos EXISTENTES del suelo que caigan dentro de la cara
    AMPLIADA (3 cm por cada lado) se suben/bajan a la cota de la cara + desfase.
    Solo cambia la cota, no se mueven en XY.
Cada punto se crea/ajusta en su propia SubTransaction; los que Revit rechace
se revierten solos. Soporta caras de vinculos (link).
IronPython 2.7 / pyRevit - Revit 2024/2025
"""
__title__ = "Puntos Suelo\na Cara"

import clr
import math
import traceback
from Autodesk.Revit.DB import (
    Floor, HostObjectUtils, Line, XYZ, Transaction, SubTransaction,
    TransactionStatus, IntersectionResultArray, SetComparisonResult, ElementId
)
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from pyrevit import forms, script

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
out = script.get_output()

FT_POR_M = 1.0 / 0.3048
RAY_LEN = 1000.0        # pies hacia arriba y hacia abajo
TOL_XY = 0.05           # pies: distancia minima a un punto existente
TOL_Z = 1e-4            # pies: tolerancia de verificacion de cota
MARGEN_BORDE = 0.1      # pies (~3 cm): no crear puntos pegados al borde del suelo
MAX_PUNTOS = 1500       # pide confirmacion si hay mas candidatos
DEDUP = 0.02            # pies: resolucion para descartar candidatos repetidos
AMPLIAR_CARA = 0.03 / 0.3048   # pies: la cara se "agranda" 3 cm por cada lado
PASO_SEG = 0.05 / 0.3048       # pies: muestreo del contorno para medir distancia


def log(msg):
    # Solo se usa para errores (traceback)
    out.print_md(msg)


class FloorFilter(ISelectionFilter):
    def AllowElement(self, e):
        return isinstance(e, Floor)

    def AllowReference(self, r, p):
        return False


def intersect_vertical(face, x, y, z_ref, transform=None):
    """Ray vertical en (x, y). Devuelve XYZ de interseccion con 'face' o None.
    Si 'transform' (link -> host) existe, el ray se lleva al espacio del link."""
    p1 = XYZ(x, y, z_ref - RAY_LEN)
    p2 = XYZ(x, y, z_ref + RAY_LEN)
    if transform is not None:
        inv = transform.Inverse
        p1, p2 = inv.OfPoint(p1), inv.OfPoint(p2)
    ray = Line.CreateBound(p1, p2)
    res = clr.Reference[IntersectionResultArray]()
    status = face.Intersect(ray, res)
    if status != SetComparisonResult.Overlap or res.Value is None or res.Value.Size == 0:
        return None
    pt = res.Value.get_Item(0).XYZPoint
    if transform is not None:
        pt = transform.OfPoint(pt)
    return pt


def bounds_xy(face, tr):
    """Extension en planta (XY) de la cara, en coordenadas del modelo activo."""
    xs, ys = [], []
    for p in face.Triangulate().Vertices:
        if tr is not None:
            p = tr.OfPoint(p)
        xs.append(p.X)
        ys.append(p.Y)
    return min(xs), max(xs), min(ys), max(ys)


def puntos_borde(face, tr, paso):
    """Puntos muestreados sobre los bordes de la cara (ya con su Z real)."""
    pts = []
    for loop in face.GetEdgesAsCurveLoops():
        for c in loop:
            if tr is not None:
                c = c.CreateTransformed(tr)
            n = max(1, int(math.ceil(c.Length / paso)))
            for i in range(n + 1):
                pts.append(c.Evaluate(i / float(n), True))
    return pts


def segmentos_borde(face, tr, paso):
    """Contorno de la cara como segmentos (x1,y1,z1,x2,y2,z2)."""
    segs = []
    for loop in face.GetEdgesAsCurveLoops():
        for c in loop:
            if tr is not None:
                c = c.CreateTransformed(tr)
            n = max(1, int(math.ceil(c.Length / paso)))
            prev = None
            for i in range(n + 1):
                p = c.Evaluate(i / float(n), True)
                if prev is not None:
                    segs.append((prev.X, prev.Y, prev.Z, p.X, p.Y, p.Z))
                prev = p
    return segs


def cota_en_franja(x, y, segs, radio):
    """Si (x,y) esta a <= radio (en planta) del contorno, devuelve la Z del
    punto mas cercano del contorno; si no, None."""
    mejor_d2, mejor_z = None, None
    r2 = radio * radio
    for (x1, y1, z1, x2, y2, z2) in segs:
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / l2))
        qx, qy = x1 + t * dx, y1 + t * dy
        d2 = (x - qx) ** 2 + (y - qy) ** 2
        if d2 <= r2 and (mejor_d2 is None or d2 < mejor_d2):
            mejor_d2, mejor_z = d2, z1 + t * (z2 - z1)
    return mejor_z


def clave_xy(x, y):
    return (int(round(x / 0.001)), int(round(y / 0.001)))


# ------------------------------------------------------------ 1. seleccion
try:
    ref_floor = uidoc.Selection.PickObject(
        ObjectType.Element, FloorFilter(), "Selecciona el SUELO")
    floor = doc.GetElement(ref_floor.ElementId)
    ref_face = uidoc.Selection.PickObject(
        ObjectType.Face, "Selecciona la CARA de referencia (ray)")
except Exception:
    script.exit()

try:
    link_tr = None
    if ref_face.LinkedElementId != ElementId.InvalidElementId:
        link_inst = doc.GetElement(ref_face.ElementId)
        link_doc = link_inst.GetLinkDocument()
        link_elem = link_doc.GetElement(ref_face.LinkedElementId)
        target_face = link_elem.GetGeometryObjectFromReference(
            ref_face.CreateReferenceInLink())
        link_tr = link_inst.GetTotalTransform()
    else:
        target_face = doc.GetElement(ref_face.ElementId).GetGeometryObjectFromReference(ref_face)
except Exception:
    log("Error leyendo la cara:\n```\n{}\n```".format(traceback.format_exc()))
    script.exit()

if target_face is None or not hasattr(target_face, "Intersect"):
    forms.alert("La referencia seleccionada no es una cara valida.", exitscript=True)

s = forms.ask_for_string(default="1", prompt="Espaciado de la malla (m):",
                         title="Puntos de subelementos")
if not s:
    script.exit()
s2 = forms.ask_for_string(default="5", prompt="Desfase POR ENCIMA de la cara (cm):",
                          title="Puntos de subelementos")
if not s2:
    script.exit()
try:
    paso = float(s.replace(",", ".")) * FT_POR_M
    desfase = float(s2.replace(",", ".")) / 100.0 * FT_POR_M
    assert paso > 0
except Exception:
    forms.alert("Espaciado o desfase invalido.", exitscript=True)

# ------------------------------------------- 2. candidatos (solo lectura)
ajustes = {}
try:
    editor0 = floor.SlabShapeEditor
    if editor0 is None:
        forms.alert("Este suelo no admite edicion de subelementos "
                    "(SlabShapeEditor nulo; revisa que no tenga pendiente por flecha).",
                    exitscript=True)

    top_faces = []
    for r in HostObjectUtils.GetTopFaces(floor):
        f = floor.GetGeometryObjectFromReference(r)
        if f is not None:
            top_faces.append(f)
    if not top_faces:
        forms.alert("No se encontro la cara superior del suelo.", exitscript=True)

    bordes_suelo = []
    for tf in top_faces:
        for loop in tf.GetEdgesAsCurveLoops():
            for c in loop:
                bordes_suelo.append(c)

    bb = floor.get_BoundingBox(None)
    z_floor = (bb.Min.Z + bb.Max.Z) / 2.0
    existentes = [v.Position for v in editor0.SlabShapeVertices] if editor0.IsEnabled else []

    # extension XY de la cara recortada a la del suelo
    fx0, fx1, fy0, fy1 = bounds_xy(target_face, link_tr)
    x0, x1 = max(fx0, bb.Min.X), min(fx1, bb.Max.X)
    y0, y1 = max(fy0, bb.Min.Y), min(fy1, bb.Max.Y)
    if x0 > x1 or y0 > y1:
        forms.alert("La cara y el suelo no se cruzan en planta (XY).", exitscript=True)

    candidatos = []
    vistos = set()
    cnt = {"fuera_suelo": 0, "duplicado": 0, "borde": 0, "fuera_cara": 0}

    def agregar(x, y, z_cara):
        """Valida contra el suelo en XY y registra el candidato a z_cara + desfase."""
        key = (int(round(x / DEDUP)), int(round(y / DEDUP)))
        if key in vistos:
            return
        vistos.add(key)
        p_suelo = None
        for tf in top_faces:
            p_suelo = intersect_vertical(tf, x, y, z_floor)
            if p_suelo is not None:
                break
        if p_suelo is None:
            cnt["fuera_suelo"] += 1
            return
        if any((p.X - x) ** 2 + (p.Y - y) ** 2 < TOL_XY ** 2 for p in existentes):
            cnt["duplicado"] += 1
            return
        if any(c.Distance(p_suelo) < MARGEN_BORDE for c in bordes_suelo):
            cnt["borde"] += 1
            return
        candidatos.append((x, y, z_cara + desfase))

    # (a) malla densa sobre la extension de la cara
    x = x0
    while x <= x1 + 1e-9:
        y = y0
        while y <= y1 + 1e-9:
            hit = intersect_vertical(target_face, x, y, z_floor, link_tr)
            if hit is None:
                cnt["fuera_cara"] += 1
            else:
                agregar(x, y, hit.Z)
            y += paso
        x += paso

    # (b) puntos sobre los bordes de la cara (cota tomada del propio borde)
    for p in puntos_borde(target_face, link_tr, paso):
        agregar(p.X, p.Y, p.Z)

    # (c) subelementos EXISTENTES dentro de la cara ampliada -> se ajustaran
    if editor0.IsEnabled:
        segs = segmentos_borde(target_face, link_tr, PASO_SEG)
        for v in editor0.SlabShapeVertices:
            p = v.Position
            if not (fx0 - AMPLIAR_CARA <= p.X <= fx1 + AMPLIAR_CARA and
                    fy0 - AMPLIAR_CARA <= p.Y <= fy1 + AMPLIAR_CARA):
                continue
            hit = intersect_vertical(target_face, p.X, p.Y, z_floor, link_tr)
            z_cara = hit.Z if hit is not None else cota_en_franja(p.X, p.Y, segs, AMPLIAR_CARA)
            if z_cara is not None:
                ajustes[clave_xy(p.X, p.Y)] = z_cara + desfase
except Exception:
    log("Error calculando candidatos:\n```\n{}\n```".format(traceback.format_exc()))
    script.exit()

if not candidatos and not ajustes:
    forms.alert("No hay puntos para crear ni ajustar con esos parametros.", exitscript=True)
if len(candidatos) > MAX_PUNTOS:
    if not forms.alert("Se crearian {} puntos (mas de {}). Es lento y puede fallar. "
                       "Continuar?".format(len(candidatos), MAX_PUNTOS), yes=True, no=True):
        script.exit()

# ------------------------------------------------------- 3. crear / ajustar
regen_cada = 1 if len(candidatos) <= 300 else 25
creados = 0
ajustados = 0
fix_z = 0
max_err = 0.0
fallidos = []

t = Transaction(doc, "Puntos de subelementos sobre cara (+desfase)")
t.Start()
try:
    editor = floor.SlabShapeEditor
    if not editor.IsEnabled:
        editor.Enable()

    # 3a) ajustar subelementos existentes dentro de la cara ampliada
    if ajustes:
        for v in list(editor.SlabShapeVertices):
            z = ajustes.get(clave_xy(v.Position.X, v.Position.Y))
            if z is None:
                continue
            st = SubTransaction(doc)
            st.Start()
            try:
                for _ in range(2):   # 2do intento por si Revit no llega a la cota exacta
                    err = z - v.Position.Z
                    if abs(err) <= TOL_Z:
                        break
                    editor.ModifySubElement(v, err)
                st.Commit()
                ajustados += 1
            except Exception as ex:
                if st.GetStatus() == TransactionStatus.Started:
                    st.RollBack()
                fallidos.append((v.Position.X, v.Position.Y, z, str(ex)))
        doc.Regenerate()

    # 3b) crear puntos nuevos
    for i, (x, y, z) in enumerate(candidatos):
        st = SubTransaction(doc)
        st.Start()
        try:
            v = editor.DrawPoint(XYZ(x, y, z))
            if v is not None:
                err = z - v.Position.Z
                if abs(err) > TOL_Z:
                    editor.ModifySubElement(v, err)
                    fix_z += 1
                    err = z - v.Position.Z
                max_err = max(max_err, abs(err))
            if (i + 1) % regen_cada == 0:
                doc.Regenerate()
            st.Commit()
            creados += 1
        except Exception as ex:
            if st.GetStatus() == TransactionStatus.Started:
                st.RollBack()
            fallidos.append((x, y, z, str(ex)))

    doc.Regenerate()
    t.Commit()
except Exception:
    log("Error en la transaccion:\n```\n{}\n```".format(traceback.format_exc()))
    if t.GetStatus() == TransactionStatus.Started:
        t.RollBack()
    script.exit()