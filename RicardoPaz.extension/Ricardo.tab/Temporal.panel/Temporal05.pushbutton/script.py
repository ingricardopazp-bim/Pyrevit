# -*- coding: utf-8 -*-
__title__ = "Alargar 2\"\n+ subida a CAD"
__doc__ = "Alarga las tuberias de 2\" por el extremo alejado de la tuberia de 4\" y crea una subida hasta tocar una cara del CAD seleccionado (capas indicadas) + margen."

import traceback
import unicodedata
from pyrevit import forms, revit, script
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Plumbing import Pipe
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType

doc = revit.doc
uidoc = revit.uidoc
out = script.get_output()
TOL_D = 0.003   # pies, tolerancia de diametro
TOL_C = 0.01    # pies, tolerancia para ubicar conectores / empate de distancias

# Capas del CAD a analizar (comparacion sin tildes, espacios, guiones ni mayusculas)
CAPAS = ["andenizquierdo", "carcamoyandenderecho"]


# ---------------------------------------------------------------- utilidades
def norm(s):
    s = unicodedata.normalize("NFD", u"" + s)
    s = u"".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return u"".join(ch for ch in s.lower() if ch.isalnum())


def parse_pulgadas(txt):
    total = 0.0
    for parte in txt.strip().replace(",", ".").split():
        if "/" in parte:
            n, d = parte.split("/")
            total += float(n) / float(d)
        else:
            total += float(parte)
    return total


def m_a_pies(v):
    return UnitUtils.ConvertToInternalUnits(float(str(v).replace(",", ".")),
                                            UnitTypeId.Meters)


def diametro(p):
    prm = p.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
    return prm.AsDouble() if prm else 0.0


def conector_cercano(pipe, pt):
    mejor = None
    dmin = 1e9
    for c in pipe.ConnectorManager.Connectors:
        d = c.Origin.DistanceTo(pt)
        if d < dmin:
            dmin = d
            mejor = c
    return mejor, dmin


def extremo_libre(pipe, pt):
    c, d = conector_cercano(pipe, pt)
    return c is not None and d < TOL_C and not c.IsConnected


def dist_a_principales(pt, curvas_principales):
    dmin = 1e9
    for cv in curvas_principales:
        try:
            d = cv.Distance(pt)
        except Exception:
            d = min(cv.GetEndPoint(0).DistanceTo(pt),
                    cv.GetEndPoint(1).DistanceTo(pt))
        if d < dmin:
            dmin = d
    return dmin


# ---------------------------------------------------------------- CAD
class FiltroCAD(ISelectionFilter):
    def AllowElement(self, e):
        return isinstance(e, ImportInstance)

    def AllowReference(self, r, p):
        return False


def _tri(v0, v1, v2):
    """Triangulo como tupla con su caja XY para descartar rapido."""
    p0 = (v0.X, v0.Y, v0.Z)
    p1 = (v1.X, v1.Y, v1.Z)
    p2 = (v2.X, v2.Y, v2.Z)
    xs = (p0[0], p1[0], p2[0])
    ys = (p0[1], p1[1], p2[1])
    return (min(xs), max(xs), min(ys), max(ys), p0, p1, p2)


def _agregar_malla(mesh, tris):
    for i in range(mesh.NumTriangles):
        t = mesh.get_Triangle(i)
        tris.append(_tri(t.get_Vertex(0), t.get_Vertex(1), t.get_Vertex(2)))


def recolectar_cad(imp, capas_norm):
    """Devuelve (triangulos, vistas). La capa se lee A NIVEL DE CARA.
    vistas = {(tipo, capa): n} (diagnostico)."""
    tris = []
    vistas = {}
    cache = {}

    def nombre_de(g):
        try:
            sid = g.GraphicsStyleId
            if sid is None or sid == ElementId.InvalidElementId:
                return None
            k = sid.IntegerValue
            if k in cache:
                return cache[k]
            gs = doc.GetElement(sid)
            nom = None
            if gs is not None and gs.GraphicsStyleCategory is not None:
                nom = gs.GraphicsStyleCategory.Name
            cache[k] = nom
            return nom
        except Exception:
            return None

    def coincide(nombre):
        if nombre is None:
            return False
        n = norm(nombre)
        return any(c in n for c in capas_norm)

    def cuenta(tipo, nombre):
        k = (tipo, nombre)
        vistas[k] = vistas.get(k, 0) + 1

    def visita(geom):
        for g in geom:
            if isinstance(g, GeometryInstance):
                visita(g.GetInstanceGeometry())
            elif isinstance(g, Solid):
                if g.Faces.Size == 0:
                    continue
                nom_s = nombre_de(g)
                for f in g.Faces:
                    nom = nombre_de(f) or nom_s or u"(sin capa)"
                    cuenta("Face", nom)
                    if coincide(nom):
                        try:
                            _agregar_malla(f.Triangulate(), tris)
                        except Exception:
                            pass
            elif isinstance(g, Mesh):
                nom = nombre_de(g) or u"(sin capa)"
                cuenta("Mesh", nom)
                if coincide(nom):
                    try:
                        _agregar_malla(g, tris)
                    except Exception:
                        pass
            else:
                cuenta(g.GetType().Name, nombre_de(g) or u"(sin capa)")

    # Intento 1: sin filtro de vista / Intento 2: con la vista activa
    for usar_vista in (False, True):
        opt = Options()
        opt.ComputeReferences = False
        opt.IncludeNonVisibleObjects = True
        opt.DetailLevel = ViewDetailLevel.Fine
        if usar_vista:
            opt.View = doc.ActiveView
        vistas.clear()
        del tris[:]
        cache.clear()
        geom = imp.get_Geometry(opt)
        if geom is not None:
            visita(geom)
        out.print_md("**Intento {}** (vista={}): {} objetos".format(
            2 if usar_vista else 1, usar_vista, sum(vistas.values())))
        for k in sorted(vistas.keys()):
            out.print_md("- `{}` | `{}` : {}".format(k[0], k[1], vistas[k]))
        if tris:
            break
    return tris, vistas


def z_hit_arriba(pt, tris):
    """Z de la primera cara del CAD por encima de pt (rayo vertical). None si no hay."""
    px, py, pz = pt.X, pt.Y, pt.Z + 1e-4
    mejor = None
    for (minx, maxx, miny, maxy, v0, v1, v2) in tris:
        if px < minx or px > maxx or py < miny or py > maxy:
            continue
        d = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
        if abs(d) < 1e-12:
            continue  # triangulo vertical / degenerado
        a = ((v1[1] - v2[1]) * (px - v2[0]) + (v2[0] - v1[0]) * (py - v2[1])) / d
        b = ((v2[1] - v0[1]) * (px - v2[0]) + (v0[0] - v2[0]) * (py - v2[1])) / d
        c = 1.0 - a - b
        e = -1e-9
        if a < e or b < e or c < e:
            continue
        z = a * v0[2] + b * v1[2] + c * v2[2]
        if z > pz and (mejor is None or z < mejor):
            mejor = z
    return mejor


# ---------------------------------------------------------------- principal
def main():
    vista = doc.ActiveView

    diam_txt = forms.ask_for_string(default="2",
                                    prompt="Diametro de las tuberias a modificar (pulgadas):",
                                    title="Diametro")
    diam_ref_txt = forms.ask_for_string(default="4",
                                        prompt="Diametro de la tuberia de referencia (pulgadas):",
                                        title="Tuberia de referencia")
    alarga_txt = forms.ask_for_string(default="0.085",
                                      prompt="Alargar (metros):",
                                      title="Alargue")
    margen_txt = forms.ask_for_string(default="0.095",
                                      prompt="Margen sobre la cara del CAD (metros):",
                                      title="Margen")
    if not diam_txt or not diam_ref_txt or not alarga_txt or not margen_txt:
        return

    d_obj = parse_pulgadas(diam_txt) / 12.0
    d_ref = parse_pulgadas(diam_ref_txt) / 12.0
    alarga = m_a_pies(alarga_txt)
    margen = m_a_pies(margen_txt)

    # --- Seleccionar CAD
    try:
        ref = uidoc.Selection.PickObject(ObjectType.Element, FiltroCAD(),
                                         "Selecciona el CAD")
    except Exception:
        return  # cancelado
    imp = doc.GetElement(ref.ElementId)

    tris, vistas = recolectar_cad(imp, CAPAS)
    out.print_md("**Triangulos en las capas indicadas:** {}".format(len(tris)))
    if not tris:
        forms.alert("No se encontraron caras en las capas indicadas.\n"
                    "Revisa la lista de tipos/capas en la ventana de salida.",
                    exitscript=True)

    todas = list(FilteredElementCollector(doc, vista.Id).OfClass(Pipe))
    tubos = [p for p in todas if abs(diametro(p) - d_obj) <= TOL_D]
    principales = [p for p in todas if abs(diametro(p) - d_ref) <= TOL_D]

    out.print_md("**Tuberias de {}\" en vista:** {}  |  **Tuberias de {}\" (referencia):** {}".format(
        diam_txt, len(tubos), diam_ref_txt, len(principales)))

    if not tubos:
        forms.alert("No hay tuberias de {}\" en la vista.".format(diam_txt),
                    exitscript=True)
    if not principales:
        forms.alert("No hay tuberias de {}\" en la vista para usar como referencia.".format(diam_ref_txt),
                    exitscript=True)

    curvas_ref = [q.Location.Curve for q in principales]

    alargadas = 0
    subidas = 0
    codos = 0
    omitidas = []
    fallos = []

    with revit.Transaction("Alargar tuberias y crear subida a CAD"):
        for p in tubos:
            try:
                c = p.Location.Curve
                a = c.GetEndPoint(0)
                b = c.GetEndPoint(1)
                largo = a.DistanceTo(b)
                if largo < 1e-6:
                    continue
                u = (b - a).Normalize()

                # Extremo alejado de la tuberia de referencia: 1 = final, 0 = inicial
                da = dist_a_principales(a, curvas_ref)
                db = dist_a_principales(b, curvas_ref)
                if abs(da - db) < TOL_C:
                    omitidas.append(p.Id.IntegerValue)
                    fallos.append((p.Id.IntegerValue,
                                   "no se pudo definir el extremo alejado (distancias iguales)"))
                    continue
                e = 1 if db > da else 0

                # Solo si el extremo alejado esta libre
                pt = b if e == 1 else a
                if not extremo_libre(p, pt):
                    omitidas.append(p.Id.IntegerValue)
                    continue

                # Nuevo extremo
                na, nb = a, b
                if e == 1:
                    nb = b + u * alarga
                else:
                    na = a - u * alarga
                base = nb if e == 1 else na

                # Altura hasta la cara del CAD (antes de modificar nada)
                zh = z_hit_arriba(base, tris)
                if zh is None:
                    omitidas.append(p.Id.IntegerValue)
                    fallos.append((p.Id.IntegerValue,
                                   "no hay cara del CAD encima del extremo; no se modifico"))
                    continue
                sube = (zh - base.Z) + margen

                p.Location.Curve = Line.CreateBound(na, nb)
                alargadas += 1
                doc.Regenerate()

                sys_id = p.get_Parameter(
                    BuiltInParameter.RBS_PIPING_SYSTEM_TYPE_PARAM).AsElementId()
                tipo_id = p.GetTypeId()
                niv_id = p.ReferenceLevel.Id

                tope = XYZ(base.X, base.Y, base.Z + sube)
                riser = Pipe.Create(doc, sys_id, tipo_id, niv_id, base, tope)
                riser.get_Parameter(
                    BuiltInParameter.RBS_PIPE_DIAMETER_PARAM).Set(diametro(p))
                subidas += 1
                doc.Regenerate()

                # Codo entre horizontal y subida
                c1, d1 = conector_cercano(p, base)
                c2, d2 = conector_cercano(riser, base)
                try:
                    doc.Create.NewElbowFitting(c1, c2)
                    codos += 1
                except Exception as ex:
                    fallos.append((p.Id.IntegerValue, "codo: " + str(ex)))
            except Exception as ex:
                fallos.append((p.Id.IntegerValue, str(ex)))

    out.print_md("**Alargadas:** {}  |  **Subidas:** {}  |  **Codos:** {}  |  **Omitidas:** {}  |  **Fallos:** {}".format(
        alargadas, subidas, codos, len(omitidas), len(fallos)))
    for i, e in fallos:
        out.print_md("Fallo en {}: {}".format(i, e))

    forms.alert("Alargadas: {}\nSubidas: {}\nCodos: {}\nOmitidas: {}\nFallos: {}".format(
        alargadas, subidas, codos, len(omitidas), len(fallos)), title="Listo")


try:
    main()
except Exception:
    out.print_md("```\n{}\n```".format(traceback.format_exc()))