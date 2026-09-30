# -*- coding: utf-8 -*-
"""Conecta dos conduit fittings YA COLOCADOS con una ruta de conduit
que pasa por una serie de caras del tunel, elegidas por el usuario en
orden.

IMPORTANTE: el punto donde se hace clic sobre cada cara NO se usa
para nada mas que identificar cual cara fue seleccionada. La
posicion real de cada punto de paso se calcula SIEMPRE a partir de la
geometria de las caras:

- Si dos caras SEGUIDAS son, en la practica, el mismo plano (mismo
  muro, aunque este subdividido en varios paneles), se tratan como
  una sola pared: no se genera ningun punto de quiebre entre ellas,
  y la ruta sigue derecho de una caja a la otra sin codos falsos por
  imprecision del clic.
- Si dos caras SEGUIDAS pertenecen a planos distintos (una esquina
  real del tunel, ej. muro -> boveda), el punto de paso se calcula
  como el punto de esa esquina desplazado FACE_OFFSET_MM milimetros
  hacia el interior del tunel (bisectriz de ambas normales). Para
  ubicar la esquina se busca primero la arista compartida entre las
  dos caras (si existe geometricamente); si no existe, se usa la
  interseccion de los dos planos. En ningun caso se usa el clic.

Flujo:
1. Selecciona el conduit fitting INICIAL.
2. Selecciona el conduit fitting FINAL.
3. Selecciona, en orden, las CARAS del tunel por las que debe pasar la
   tuberia (ESC para terminar de marcar caras). El lugar exacto del
   clic sobre cada cara es irrelevante, solo importa CUAL cara.
4. El script crea:
   - Un stub de 10 cm desde el conector abierto del fitting inicial.
   - Un tramo recto entre cada punto de paso consecutivo (o un solo
     tramo recto de caja a caja si no hay esquinas reales).
   - Un stub de 10 cm hacia el conector abierto del fitting final.
   - Codos (elbow) en los puntos donde cambia de direccion, o un
     acople (coupling) si el tramo sigue recto.

NOTA: si el desplazamiento de 26 mm queda del lado equivocado (hacia
el muro en vez de hacia el tunel), cambia el signo en FACE_OFFSET_FT
(linea ~40) multiplicando por -1.
"""

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import (
    XYZ, UV, Transaction, UnitUtils, UnitTypeId, Face, PlanarFace,
    FamilyInstance, BuiltInCategory, BuiltInParameter,
    ElementTypeGroup, Level, FilteredElementCollector
)
from Autodesk.Revit.DB.Electrical import Conduit, ConduitType
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms

doc = revit.doc
uidoc = revit.uidoc

STUB_LEN_M = 0.10
FACE_OFFSET_MM = 26.0

STUB_LEN_FT = UnitUtils.ConvertToInternalUnits(STUB_LEN_M, UnitTypeId.Meters)
FACE_OFFSET_FT = UnitUtils.ConvertToInternalUnits(FACE_OFFSET_MM, UnitTypeId.Millimeters)

# Tolerancias para decidir si dos caras seguidas son "el mismo muro"
# (mismo plano) y por lo tanto NO deben generar un punto de quiebre.
PLANE_NORMAL_DOT_TOL = 0.0005                                        # 1 - dot(nA, nB)
PLANE_DIST_TOL_FT = UnitUtils.ConvertToInternalUnits(15.0, UnitTypeId.Millimeters)

# Tolerancia para considerar que una arista de una cara coincide con
# una arista de la otra (arista compartida real entre ambas caras).
SHARED_EDGE_TOL_FT = UnitUtils.ConvertToInternalUnits(5.0, UnitTypeId.Millimeters)

PARALLEL_TOL = 0.001  # tolerancia (via dot product) para tratar un tramo como recto


class ConduitFittingFilter(ISelectionFilter):
    """Solo permite seleccionar Conduit Fittings."""
    def AllowElement(self, element):
        return (
            element.Category is not None
            and element.Category.Id.IntegerValue == int(BuiltInCategory.OST_ConduitFitting)
        )

    def AllowReference(self, reference, position):
        return False


def get_location_point(element):
    loc = element.Location
    return loc.Point


def get_face(doc, reference):
    element = doc.GetElement(reference)
    geom_obj = element.GetGeometryObjectFromReference(reference)
    if not isinstance(geom_obj, Face):
        return None
    return geom_obj


def get_face_plane(face):
    """Devuelve (origen, normal) de la cara, SIN depender de donde se
    hizo clic. El origen SIEMPRE se evalua en el centro real del
    dominio UV de la cara (el centro visible del panel).

    OJO: para PlanarFace, 'face.Origin' NO es el centro visible del
    panel, es un punto arbitrario del plano infinito (suele quedar
    cerca de una referencia de construccion, en este caso cerca de la
    parte baja del muro). Usar ese punto como referencia de altura es
    lo que hacia que la interseccion entre dos caras se proyectara
    hacia esa referencia baja en vez de hacia la mitad real de la
    ruta. Por eso aqui NUNCA se usa face.Origin para la posicion."""
    bbox = face.GetBoundingBox()
    uv_center = UV(
        (bbox.Min.U + bbox.Max.U) / 2.0,
        (bbox.Min.V + bbox.Max.V) / 2.0
    )
    origin = face.Evaluate(uv_center)

    if isinstance(face, PlanarFace):
        normal = face.FaceNormal.Normalize()
    else:
        normal = face.ComputeNormal(uv_center).Normalize()

    return origin, normal


def is_same_plane(origin_a, normal_a, origin_b, normal_b):
    """True si ambas caras pertenecen, en la practica, al mismo plano
    (mismo muro), sin importar que sean paneles distintos."""
    if abs(normal_a.DotProduct(normal_b) - 1.0) > PLANE_NORMAL_DOT_TOL:
        return False
    dist = abs(normal_a.DotProduct(origin_b - origin_a))
    return dist <= PLANE_DIST_TOL_FT


def _face_edge_curves(face):
    curves = []
    for edge_array in face.EdgeLoops:
        for edge in edge_array:
            curves.append(edge.AsCurve())
    return curves


def find_shared_edge_point(face_a, face_b, ref_point):
    """Sin uso actualmente: en mallas de CAD vinculado el emparejamiento
    de aristas por tolerancia puede enganchar una arista incorrecta
    (una diagonal de la malla cerca de la esquina) y eso era lo que
    generaba el punto que se hundia antes del codo real. Se deja la
    funcion por si se necesita para geometria nativa de Revit con
    topologia limpia, pero compute_corner_point ya NO la llama: usa
    siempre la interseccion matematica de los dos planos, que es
    independiente de como este triangulada la malla importada."""
    for curve_a in _face_edge_curves(face_a):
        pa0 = curve_a.GetEndPoint(0)
        pa1 = curve_a.GetEndPoint(1)
        for curve_b in _face_edge_curves(face_b):
            pb0 = curve_b.GetEndPoint(0)
            pb1 = curve_b.GetEndPoint(1)
            same_dir = (pa0.DistanceTo(pb0) <= SHARED_EDGE_TOL_FT
                        and pa1.DistanceTo(pb1) <= SHARED_EDGE_TOL_FT)
            rev_dir = (pa0.DistanceTo(pb1) <= SHARED_EDGE_TOL_FT
                       and pa1.DistanceTo(pb0) <= SHARED_EDGE_TOL_FT)
            if same_dir or rev_dir:
                result = curve_a.Project(ref_point)
                if result is not None:
                    return result.XYZPoint
                return pa0 + (pa1 - pa0).Multiply(0.5)
    return None


def intersect_planes(origin_a, normal_a, origin_b, normal_b):
    """Interseccion de dos planos. Devuelve (punto_en_la_recta,
    direccion_unitaria) o None si son paralelos."""
    direction = normal_a.CrossProduct(normal_b)
    if direction.GetLength() < 1e-9:
        return None
    direction = direction.Normalize()

    d1 = normal_a.DotProduct(origin_a)
    d2 = normal_b.DotProduct(origin_b)
    dot_ab = normal_a.DotProduct(normal_b)
    denom = 1.0 - dot_ab * dot_ab
    ca = (d1 - d2 * dot_ab) / denom
    cb = (d2 - d1 * dot_ab) / denom
    point_on_line = normal_a.Multiply(ca) + normal_b.Multiply(cb)
    return point_on_line, direction


def closest_point_on_line(point_on_line, direction, ref_point):
    t = direction.DotProduct(ref_point - point_on_line)
    return point_on_line + direction.Multiply(t)


def compute_corner_point(face_a, origin_a, normal_a, face_b, origin_b, normal_b,
                          p_start, p_end):
    """Punto de paso en la esquina real entre 'face_a' y 'face_b',
    desplazado FACE_OFFSET_FT hacia el interior del tunel (bisectriz
    de ambas normales).

    La posicion sobre la recta de interseccion de los dos planos se
    elige como el punto MAS CERCANO a la linea recta directa entre
    las dos cajas (p_start -> p_end): esa linea es la ruta "ideal"
    si no hubiera muros de por medio, asi que anclar la esquina a
    ella evita que el punto se vaya hacia una altura arbitraria
    (como pasaba al promediar los centros de los paneles, que no
    tienen por que coincidir con la altura real del recorrido)."""
    result = intersect_planes(origin_a, normal_a, origin_b, normal_b)
    fallback_ref = origin_a + (origin_b - origin_a).Multiply(0.5)

    if result is None:
        base_point = fallback_ref
    else:
        line_point, direction = result

        seg_vec = p_end - p_start
        seg_len = seg_vec.GetLength()
        if seg_len < 1e-9:
            base_point = closest_point_on_line(line_point, direction, fallback_ref)
        else:
            dir2 = seg_vec.Normalize()
            r = line_point - p_start
            b = direction.DotProduct(dir2)
            d = direction.DotProduct(r)
            e = dir2.DotProduct(r)
            denom = 1.0 - b * b
            if abs(denom) < 1e-9:
                # la interseccion es (casi) paralela a la linea caja-caja
                base_point = closest_point_on_line(line_point, direction, fallback_ref)
            else:
                t2 = (e - b * d) / denom
                t2 = max(0.0, min(seg_len, t2))
                ref_on_segment = p_start + dir2.Multiply(t2)
                base_point = closest_point_on_line(line_point, direction, ref_on_segment)

    bisector = normal_a + normal_b
    if bisector.GetLength() < 1e-6:
        bisector = normal_a  # normales opuestas (caso raro): usar solo una
    bisector = bisector.Normalize()

    return base_point + bisector.Multiply(FACE_OFFSET_FT)


def build_waypoints_from_faces(picked_faces, p_start, p_end):
    """'picked_faces' es una lista de (face, origin, normal) en el
    orden en que el usuario las selecciono. Devuelve la lista de
    puntos de paso: fusiona caras seguidas que son el mismo plano
    (mismo muro) y solo genera un punto donde realmente cambia de
    plano (esquina real), anclado a la linea directa p_start->p_end."""
    distinct = []
    for face, origin, normal in picked_faces:
        if distinct and is_same_plane(distinct[-1][1], distinct[-1][2], origin, normal):
            continue
        distinct.append((face, origin, normal))

    waypoints = []
    for i in range(len(distinct) - 1):
        face_a, origin_a, normal_a = distinct[i]
        face_b, origin_b, normal_b = distinct[i + 1]
        waypoints.append(
            compute_corner_point(face_a, origin_a, normal_a, face_b, origin_b, normal_b,
                                  p_start, p_end)
        )
    return waypoints


def get_connectors(element):
    if isinstance(element, FamilyInstance):
        mep_model = element.MEPModel
        if mep_model is None or mep_model.ConnectorManager is None:
            return []
        return list(mep_model.ConnectorManager.Connectors)
    cm = getattr(element, "ConnectorManager", None)
    if cm is None:
        return []
    return list(cm.Connectors)


def pick_open_connector_towards(element, direction):
    open_conns = [c for c in get_connectors(element) if not c.IsConnected]
    if not open_conns:
        return None
    best, best_dot = None, -2.0
    for c in open_conns:
        outward = c.CoordinateSystem.BasisZ.Normalize()
        dot = outward.DotProduct(direction)
        if dot > best_dot:
            best_dot, best = dot, c
    return best


def get_connector_at(element, point, tol=1e-5):
    for c in get_connectors(element):
        if c.Origin.DistanceTo(point) <= tol:
            return c
    return None


def find_matching_conduit_type(doc, diameter_ft):
    best_type, best_diff = None, None
    for ct in FilteredElementCollector(doc).OfClass(ConduitType):
        p = ct.get_Parameter(BuiltInParameter.RBS_CONDUIT_DIAMETER_PARAM)
        if p is None:
            continue
        diff = abs(p.AsDouble() - diameter_ft)
        if best_diff is None or diff < best_diff:
            best_diff, best_type = diff, ct
    if best_type is None:
        return doc.GetDefaultElementTypeId(ElementTypeGroup.ConduitType)
    return best_type.Id


def get_level_id(element, doc):
    level_id = element.LevelId
    if level_id is not None and level_id.IntegerValue > 0:
        return level_id
    return FilteredElementCollector(doc).OfClass(Level).FirstElementId()


def connect_two_conduits(doc, conn_a, conn_b):
    """Une dos conectores de conduit: si los tramos quedan alineados
    usa ConnectTo (Revit resuelve con un acople si aplica); si cambian
    de direccion, crea un codo (elbow)."""
    dir_a = conn_a.CoordinateSystem.BasisZ.Normalize()
    dir_b = conn_b.CoordinateSystem.BasisZ.Normalize()
    if abs(abs(dir_a.DotProduct(dir_b)) - 1.0) <= PARALLEL_TOL:
        conn_a.ConnectTo(conn_b)
    else:
        doc.Create.NewElbowFitting(conn_a, conn_b)


def create_routed_conduit(doc, elem_start, elem_end, waypoints, conduit_type_id, level_id):
    """Crea la ruta completa: stub inicial -> tramos por 'waypoints' -> stub final.
    Si 'waypoints' esta vacia, el tramo entre stubs es un unico segmento
    recto de caja a caja."""
    p_start = get_location_point(elem_start)
    p_end = get_location_point(elem_end)

    first_target = waypoints[0] if waypoints else p_end
    last_target = waypoints[-1] if waypoints else p_start

    dir_start = (first_target - p_start).Normalize()
    dir_end = (last_target - p_end).Normalize()

    conn_start = pick_open_connector_towards(elem_start, dir_start)
    conn_end = pick_open_connector_towards(elem_end, dir_end)
    if conn_start is None or conn_end is None:
        raise Exception(
            "Alguno de los dos fittings no tiene un conector abierto "
            "orientado hacia la ruta."
        )

    p1 = conn_start.Origin
    stub1_dir = conn_start.CoordinateSystem.BasisZ.Normalize()
    stub1_end = p1 + stub1_dir.Multiply(STUB_LEN_FT)

    p2 = conn_end.Origin
    stub2_dir = conn_end.CoordinateSystem.BasisZ.Normalize()
    stub2_end = p2 + stub2_dir.Multiply(STUB_LEN_FT)

    # Puntos completos de la polilinea: stub inicial -> waypoints -> stub final
    path_points = [stub1_end] + list(waypoints) + [stub2_end]

    # Crear stub inicial y stub final
    stub_start = Conduit.Create(doc, conduit_type_id, p1, stub1_end, level_id)
    stub_end = Conduit.Create(doc, conduit_type_id, p2, stub2_end, level_id)

    # Crear tramos rectos entre cada par consecutivo de la polilinea
    segments = []
    for i in range(len(path_points) - 1):
        seg = Conduit.Create(doc, conduit_type_id, path_points[i], path_points[i + 1], level_id)
        segments.append(seg)

    doc.Regenerate()

    # Conectar: fitting inicial -> stub inicial
    conn_start.ConnectTo(get_connector_at(stub_start, p1))

    # stub inicial -> primer tramo
    connect_two_conduits(
        doc,
        get_connector_at(stub_start, stub1_end),
        get_connector_at(segments[0], stub1_end)
    )

    # tramos intermedios entre si
    for i in range(len(segments) - 1):
        shared_point = path_points[i + 1]
        connect_two_conduits(
            doc,
            get_connector_at(segments[i], shared_point),
            get_connector_at(segments[i + 1], shared_point)
        )

    # ultimo tramo -> stub final
    connect_two_conduits(
        doc,
        get_connector_at(segments[-1], stub2_end),
        get_connector_at(stub_end, stub2_end)
    )

    # stub final -> fitting final
    get_connector_at(stub_end, p2).ConnectTo(conn_end)


def main():
    conduit_filter = ConduitFittingFilter()

    try:
        pick_start = uidoc.Selection.PickObject(
            ObjectType.Element, conduit_filter,
            "Selecciona el conduit fitting INICIAL"
        )
        pick_end = uidoc.Selection.PickObject(
            ObjectType.Element, conduit_filter,
            "Selecciona el conduit fitting FINAL"
        )
    except OperationCanceledException:
        return

    elem_start = doc.GetElement(pick_start.ElementId)
    elem_end = doc.GetElement(pick_end.ElementId)

    picked_faces = []
    while True:
        try:
            face_ref = uidoc.Selection.PickObject(
                ObjectType.Face,
                "Selecciona la SIGUIENTE cara del tunel a seguir (ESC para terminar la ruta)"
            )
        except OperationCanceledException:
            break

        face = get_face(doc, face_ref)
        if face is None:
            forms.alert("La referencia seleccionada no corresponde a una cara, se omite.")
            continue

        origin, normal = get_face_plane(face)
        picked_faces.append((face, origin, normal))

    if not picked_faces:
        proceed = forms.alert(
            "No marcaste ninguna cara: se creara un tramo directo entre "
            "los dos fittings. Continuar?",
            yes=True, no=True
        )
        if not proceed:
            return
        waypoints = []
    else:
        p_start = get_location_point(elem_start)
        p_end = get_location_point(elem_end)
        waypoints = build_waypoints_from_faces(picked_faces, p_start, p_end)

    diameter_ft = None
    for c in get_connectors(elem_start):
        if not c.IsConnected:
            diameter_ft = c.Radius * 2.0
            break
    if diameter_ft is None:
        forms.alert("El fitting inicial no tiene conectores abiertos.", exitscript=True)

    conduit_type_id = find_matching_conduit_type(doc, diameter_ft)
    level_id = get_level_id(elem_start, doc)

    t = Transaction(doc, "Crear ruta de conduit entre fittings")
    t.Start()
    try:
        create_routed_conduit(doc, elem_start, elem_end, waypoints, conduit_type_id, level_id)
        t.Commit()
    except Exception as ex:
        t.RollBack()
        forms.alert("No se pudo crear la ruta de conduit:\n{}".format(ex))


if __name__ == '__main__':
    main()