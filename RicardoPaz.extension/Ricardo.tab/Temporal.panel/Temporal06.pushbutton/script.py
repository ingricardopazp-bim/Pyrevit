# -*- coding: utf-8 -*-
"""Conecta dos ELECTRICAL FIXTURES YA COLOCADOS con una ruta de conduit
que pasa por una serie de caras del tunel, elegidas por el usuario en
orden.

IMPORTANTE: el punto donde se hace clic sobre cada cara NO decide si
hay quiebre entre caras ni la posicion final de ningun punto de paso;
eso se calcula SIEMPRE a partir de la geometria de las caras (ver
mas abajo). El clic se usa solo para dos cosas: (1) identificar cual
cara fue seleccionada, y (2) ubicar, DENTRO de esa cara, el punto
donde se evaluan su origen y su normal locales (ver get_face_plane),
porque el centro geometrico de una cara puede caer fuera de la region
que el usuario realmente selecciono (caras de solidos importados con
dominios UV grandes o descentrados):

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

  CASO ESPECIAL (planos casi paralelos, ej. muro plano contra el
  primer panel de una boveda curva): cuando las dos normales son muy
  parecidas pero no identicas, la interseccion EXACTA de los dos
  planos extendidos como infinitos puede caer larguisimo (cientos o
  miles de metros) del lugar real donde los paneles se tocan, aunque
  el calculo sea matematicamente correcto para los planos infinitos.
  Para evitar que eso arruine la ruta, se valida la distancia del
  punto resultante contra el punto medio simple entre las dos caras
  (ver MAX_CORNER_DEVIATION_MM): si se dispara mas alla de ese
  umbral, se descarta y se usa el punto medio en su lugar.

Flujo:
1. Selecciona el ELECTRICAL FIXTURE INICIAL.
2. Selecciona el ELECTRICAL FIXTURE FINAL.
3. Selecciona, en orden, las CARAS del tunel por las que debe pasar la
   tuberia (ESC para terminar de marcar caras). El lugar exacto del
   clic sobre cada cara es irrelevante, solo importa CUAL cara.
4. El script detecta TODOS los conectores de conduit SIN CONECTAR de
   cada fixture (puede haber varios, ej. 4: dos que miran hacia el
   otro fixture -el lado "cercano"- y dos que miran hacia el lado
   contrario -el lado "lejano"-). Se queda SOLO con los del lado
   cercano (los lejanos quedan quietos, sin tocar), los empareja entre
   si por posicion (primero por posicion LATERAL, para agrupar los
   conectores mas cercanos entre si -ej. la misma columna izquierda o
   derecha-, y dentro de cada grupo lateral por ALTURA, para que
   dentro de esa misma columna tampoco se crucen), y crea, para CADA
   par, una ruta independiente:
   - Un stub de 10 cm desde el conector abierto del fixture inicial.
   - Un tramo recto INDEPENDIENTE entre cada punto de paso consecutivo
     (uno por cada cambio de cara/esquina), calculado usando la
     posicion REAL de ESE conector (no un punto generico del fixture),
     para que cada tubo en paralelo siga su propia altura/posicion sin
     oscilar hacia la de otro tubo.
   - Un stub de 10 cm hacia el conector abierto del fixture final.

IMPORTANTE (sin conexion real): cada tramo se crea como un conduit
SUELTO. NO se llama a ConnectTo, NO se crean codos (elbow) ni acoples
(coupling), y el fixture tampoco queda conectado al primer/ultimo
tramo. Los extremos de tramos consecutivos se ubican exactamente en
el mismo punto XYZ (quedan pegados, simulando visualmente la
conexion), pero en el modelo de Revit son piezas de conduit
independientes, sin relacion de conectividad entre si. Esto es
intencional: se busca que cada tramo quede como una pieza paralela
separada, no una tuberia continua conectada.

NOTA: si el desplazamiento de 26 mm queda del lado equivocado (hacia
el muro en vez de hacia el tunel), cambia el signo en FACE_OFFSET_FT
(linea ~40) multiplicando por -1.

NOTA 2: se asume que los Electrical Fixtures tienen, dentro de su
MEPModel, al menos un conector de tipo conduit sin conectar (igual
que un conduit fitting). Si el fixture usa cable tray o solo tiene
conectores electricos (sin conduit), el script no encontrara un
conector valido y avisara con un mensaje de error.
"""

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import (
    XYZ, UV, Transaction, UnitUtils, UnitTypeId, Face, PlanarFace,
    FamilyInstance, BuiltInCategory, BuiltInParameter,
    ElementTypeGroup, Level, FilteredElementCollector, Domain
)
from Autodesk.Revit.DB.Electrical import Conduit, ConduitType
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms, script

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()

# Poner en False para desactivar todo el diagnostico y correr el
# script "limpio", sin imprimir nada en la ventana de output.
DEBUG = True

STUB_LEN_M = 0.10
FACE_OFFSET_MM = 66.0

# Diametro FIJO de conduit a usar en toda la ruta, independiente del
# diametro real del conector del fixture. Se usa para buscar el
# ConduitType mas cercano a este valor (ver find_matching_conduit_type).
#
# OJO: esto se compara contra RBS_CONDUIT_DIAMETER_PARAM, que en los
# ConduitType de Revit guarda el DIAMETRO EXTERIOR (Outside Diameter),
# NO el Trade Size / Size nominal. Para un conduit de 3" trade size,
# el Outside Diameter real es 3 1/2" (ver ficha de dimensiones del
# fabricante). Por eso aqui va 3.5, no 3.0: usar 3.0 hacia que el
# script emparejara con el tipo de 2 1/2" (cuyo diametro exterior si
# ronda las 3"), no con el de 3" que se buscaba.
CONDUIT_DIAMETER_IN = 3.5

STUB_LEN_FT = UnitUtils.ConvertToInternalUnits(STUB_LEN_M, UnitTypeId.Meters)
FACE_OFFSET_FT = UnitUtils.ConvertToInternalUnits(FACE_OFFSET_MM, UnitTypeId.Millimeters)
CONDUIT_DIAMETER_FT = UnitUtils.ConvertToInternalUnits(CONDUIT_DIAMETER_IN, UnitTypeId.Inches)

# Tolerancias para decidir si dos caras seguidas son "el mismo muro"
# (mismo plano) y por lo tanto NO deben generar un punto de quiebre.
PLANE_NORMAL_DOT_TOL = 0.0005                                        # 1 - dot(nA, nB)
PLANE_DIST_TOL_FT = UnitUtils.ConvertToInternalUnits(15.0, UnitTypeId.Millimeters)

# Tolerancia para considerar que una arista de una cara coincide con
# una arista de la otra (arista compartida real entre ambas caras).
SHARED_EDGE_TOL_FT = UnitUtils.ConvertToInternalUnits(5.0, UnitTypeId.Millimeters)

# El punto de esquina (interseccion de las dos caras) se calcula
# proyectando sobre la linea directa entre los dos fixtures, lo cual
# puede dar una altura fuera del rango real (visible) de las caras
# seleccionadas y terminar mas arriba de donde realmente van los
# tubos. Para evitarlo, el punto se recorta (clamp) para que quede
# dentro del rango vertical real de ambas caras, ampliado
# FACE_VERTICAL_PAD_MM hacia arriba y hacia abajo.
FACE_VERTICAL_PAD_MM = 500.0
FACE_VERTICAL_PAD_FT = UnitUtils.ConvertToInternalUnits(FACE_VERTICAL_PAD_MM, UnitTypeId.Millimeters)

# LIMITE DE SANIDAD para el ORIGEN de una cara individual (no ya para
# el punto de esquina calculado entre dos caras, ver
# MAX_CORNER_DEVIATION_MM mas abajo). Se ha observado que, para
# ciertas caras (aparentemente por un problema al resolver
# Reference.GlobalPoint sobre geometria de este host, posiblemente
# importada/anidada), el punto de clic que reporta Revit llega
# corrupto (cercano a (0,0,0) del proyecto) en vez del punto real
# donde se hizo clic, sin importar donde se clickee. Si el origen
# calculado para una cara recien clickeada queda a mas de esta
# distancia de AMBOS fixtures (inicial y final) Y de la linea que los
# une, se rechaza esa cara en el momento (no se agrega a la ruta) y
# se le pide al usuario volver a intentar el clic, en vez de dejar
# que ese punto corrupto contamine toda la ruta (que es lo que pasaba
# antes: el punto de esquina se disparaba a mas de 1 km).
MAX_FACE_ORIGIN_DEVIATION_MM = 100000.0
MAX_FACE_ORIGIN_DEVIATION_FT = UnitUtils.ConvertToInternalUnits(MAX_FACE_ORIGIN_DEVIATION_MM, UnitTypeId.Millimeters)

# LIMITE DE SANIDAD para el punto de esquina calculado por
# interseccion de planos. Cuando dos caras seguidas son casi
# paralelas (normales separadas por pocos grados) sin llegar a
# considerarse "el mismo plano" (ver PLANE_NORMAL_DOT_TOL), la
# interseccion EXACTA de esos dos planos extendidos como infinitos
# puede caer a cientos o miles de metros del lugar real donde las
# caras se tocan (el calculo es correcto para planos infinitos, pero
# no representa la geometria real, finita, de los paneles). Si el
# punto resultante se aleja mas de MAX_CORNER_DEVIATION_MM del punto
# medio simple entre los origenes de las dos caras, se descarta y se
# usa ese punto medio en su lugar.
MAX_CORNER_DEVIATION_MM = 3000.0
MAX_CORNER_DEVIATION_FT = UnitUtils.ConvertToInternalUnits(MAX_CORNER_DEVIATION_MM, UnitTypeId.Millimeters)

# Tolerancia para agrupar conectores que estan en la misma posicion
# LATERAL (misma "columna", ej. izquierda/derecha) aunque no tengan
# exactamente el mismo valor lateral. Es el PRIMER criterio de
# emparejamiento: agrupa los conectores mas cercanos entre si.
CONNECTOR_LATERAL_TOL_MM = 30.0
CONNECTOR_LATERAL_TOL_FT = UnitUtils.ConvertToInternalUnits(CONNECTOR_LATERAL_TOL_MM, UnitTypeId.Millimeters)


# ------------------------------------------------------------------
# Utilidades de diagnostico (solo imprimen si DEBUG = True)
# ------------------------------------------------------------------

def fmt_xyz(p):
    """Formatea un XYZ en milimetros, legible, para diagnostico."""
    if p is None:
        return "None"
    x = UnitUtils.ConvertFromInternalUnits(p.X, UnitTypeId.Millimeters)
    y = UnitUtils.ConvertFromInternalUnits(p.Y, UnitTypeId.Millimeters)
    z = UnitUtils.ConvertFromInternalUnits(p.Z, UnitTypeId.Millimeters)
    return "({:.1f}, {:.1f}, {:.1f}) mm".format(x, y, z)


def fmt_vec(v):
    """Formatea un vector (direccion) SIN unidades, solo componentes
    normalizadas, para diagnostico."""
    if v is None:
        return "None"
    return "[{:.4f}, {:.4f}, {:.4f}]".format(v.X, v.Y, v.Z)


def dbg(msg):
    if DEBUG:
        output.print_md(msg)


def dbg_face_info(label, face, origin, normal):
    z_min, z_max = get_face_z_range(face)
    z_min_mm = UnitUtils.ConvertFromInternalUnits(z_min, UnitTypeId.Millimeters)
    z_max_mm = UnitUtils.ConvertFromInternalUnits(z_max, UnitTypeId.Millimeters)
    dbg(
        "- **{0}** | tipo: `{1}` | origen(centro UV): {2} | normal: {3} "
        "| rango Z real: [{4:.1f}, {5:.1f}] mm".format(
            label,
            "PlanarFace" if isinstance(face, PlanarFace) else type(face).__name__,
            fmt_xyz(origin), fmt_vec(normal), z_min_mm, z_max_mm
        )
    )


def dbg_connector_info(label, conn, owner_elem):
    diam_mm = UnitUtils.ConvertFromInternalUnits(conn.Radius * 2.0, UnitTypeId.Millimeters)
    dbg(
        "- **{0}** | owner ElementId: `{1}` | origen: {2} | direccion (BasisZ): {3} "
        "| diametro real: {4:.1f} mm | Domain: `{5}`".format(
            label, owner_elem.Id, fmt_xyz(conn.Origin),
            fmt_vec(conn.CoordinateSystem.BasisZ), diam_mm, conn.Domain
        )
    )



class ElectricalFixtureFilter(ISelectionFilter):
    """Solo permite seleccionar Electrical Fixtures."""
    def AllowElement(self, element):
        return (
            element.Category is not None
            and element.Category.Id.IntegerValue == int(BuiltInCategory.OST_ElectricalFixtures)
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


def get_face_plane(face, pick_point):
    """Devuelve (origen, normal) de la cara, evaluados en el punto
    real donde el usuario hizo clic (proyectado sobre la cara), NO en
    'face.Origin' ni en el centro de la bounding box UV.

    HISTORIAL DE ESTE CALCULO (por que no se usan las otras dos
    opciones obvias):

    1) face.Origin (descartado desde el principio): para una
       PlanarFace, 'face.Origin' NO es el centro visible del panel,
       es un punto arbitrario del plano infinito que representa esa
       cara (en este modelo caia cerca de una referencia de
       construccion, lejos del panel real). Usarlo como referencia de
       altura hacia que la interseccion entre dos caras se proyectara
       hacia esa referencia arbitraria en vez de hacia la mitad real
       de la ruta.

    2) Centro de la bounding box UV (usado antes, TAMBIEN descartado):
       en teoria evita el problema de (1) porque cae dentro del
       dominio parametrico de la cara. En la practica, para caras que
       vienen de solidos importados/vinculados (como este tunel), el
       dominio UV de una cara puede ser mucho mas grande o estar
       desplazado respecto a la region que realmente se ve/clickea
       (ej. una PlanarFace cuyo dominio UV se extiende muy por fuera
       del panel visible). Ahi el 'centro' de esa caja cae en un punto
       que no tiene nada que ver con donde clickeaste ni con el resto
       del tunel, y arrastra ese error a cualquier calculo que use ese
       origen (interseccion de planos, y hasta el punto medio de
       respaldo si tambien se calcula a partir de ese origen).

    3) Punto de clic proyectado sobre la cara (lo que se usa AHORA):
       'pick_point' es el punto 3D real donde el usuario hizo clic
       (Reference.GlobalPoint de la seleccion), que por definicion
       cae dentro de la region visible de la cara. Se proyecta sobre
       la cara con face.Project() para obtener su UV exacto, y ahi se
       evaluan el origen y la normal. Esto NO reintroduce el problema
       de (1): no se usa ninguna propiedad arbitraria de Revit, solo
       un punto garantizado dentro del panel que el usuario realmente
       senalo. El clic sigue sin influir en NADA mas (no decide si
       hay quiebre entre caras, ni la posicion final del punto de
       paso, que sigue calculandose por interseccion/fusion de
       planos): solo fija DONDE, dentro de esa cara, se evalua su
       plano local."""
    projection = face.Project(pick_point)
    if projection is not None:
        uv = projection.UVPoint
        origin = projection.XYZPoint
    else:
        # Respaldo (no deberia pasar: pick_point viene de un clic
        # sobre la propia cara): centro de la bounding box UV.
        bbox = face.GetBoundingBox()
        uv = UV(
            (bbox.Min.U + bbox.Max.U) / 2.0,
            (bbox.Min.V + bbox.Max.V) / 2.0
        )
        origin = face.Evaluate(uv)

    if isinstance(face, PlanarFace):
        normal = face.FaceNormal.Normalize()
    else:
        normal = face.ComputeNormal(uv).Normalize()

    return origin, normal


def get_face_z_range(face):
    """Devuelve (z_min, z_max): el rango real de alturas que cubre la
    cara, evaluado en las 4 esquinas de su bounding box UV (sirve
    tanto para caras planas de muro como para paneles curvos de
    boveda). Se usa para no dejar que el punto de esquina calculado
    termine por fuera de la zona donde realmente existe la cara."""
    bbox = face.GetBoundingBox()
    corners_uv = [
        UV(bbox.Min.U, bbox.Min.V),
        UV(bbox.Min.U, bbox.Max.V),
        UV(bbox.Max.U, bbox.Min.V),
        UV(bbox.Max.U, bbox.Max.V),
    ]
    zs = [face.Evaluate(uv).Z for uv in corners_uv]
    return min(zs), max(zs)


def clamp_point_to_z_range(line_point, direction, point, z_min, z_max):
    """Mueve 'point' a lo largo de la recta (line_point, direction) lo
    minimo necesario para que su Z quede dentro de [z_min, z_max].
    Si el punto ya esta dentro del rango, no lo toca. Si la recta es
    (casi) horizontal (direction.Z ~ 0) no se puede corregir la altura
    moviendose sobre ella, asi que se devuelve el punto sin cambios."""
    if point.Z >= z_min and point.Z <= z_max:
        return point
    if abs(direction.Z) < 1e-9:
        return point

    z_target = z_min if point.Z < z_min else z_max
    t = (z_target - line_point.Z) / direction.Z
    return line_point + direction.Multiply(t)


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


def distance_point_to_segment(point, seg_start, seg_end):
    """Distancia minima de 'point' al segmento (seg_start, seg_end),
    proyectando y recortando (clamp) al rango [0, longitud]. Se usa
    para validar que el origen de una cara recien clickeada sea
    geometricamente razonable (cercano a la ruta entre los dos
    fixtures), y asi detectar clics cuyo punto llego corrupto."""
    seg_vec = seg_end - seg_start
    seg_len = seg_vec.GetLength()
    if seg_len < 1e-9:
        return point.DistanceTo(seg_start)
    dir_ = seg_vec.Normalize()
    t = dir_.DotProduct(point - seg_start)
    t = max(0.0, min(seg_len, t))
    closest = seg_start + dir_.Multiply(t)
    return point.DistanceTo(closest)


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
    tienen por que coincidir con la altura real del recorrido).

    Luego, ese punto se recorta (clamp) en altura para que quede
    dentro del rango vertical real cubierto por 'face_a' y 'face_b',
    ampliado FACE_VERTICAL_PAD_FT hacia arriba y hacia abajo. Esto
    evita que el punto termine mas arriba (o mas abajo) de donde
    realmente van los tubos cuando la proyeccion sobre la linea
    directa cae fuera de la zona real de las caras.

    VALIDACION DE SANIDAD (nueva): cuando 'normal_a' y 'normal_b' son
    casi paralelas (pocos grados de diferencia) sin llegar a
    considerarse el mismo plano, la interseccion EXACTA de los dos
    planos extendidos como infinitos puede caer a cientos o miles de
    metros de donde las caras realmente se tocan (los planos
    infinitos si se cruzan ahi, pero los paneles finitos no). Por eso,
    antes de aplicar el offset y el clamp de Z, se compara el punto
    resultante contra el punto medio simple entre 'origin_a' y
    'origin_b'; si la distancia supera MAX_CORNER_DEVIATION_FT, se
    descarta el resultado de la interseccion y se usa ese punto medio
    en su lugar."""
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

        # --- Validacion de sanidad: planos casi paralelos que dan una
        # interseccion "de fuga" muy lejana. Se compara ANTES del
        # clamp de Z, porque el clamp solo corrige la altura, no un
        # descarrile lateral como el que produce este caso. ---
        deviation = base_point.DistanceTo(fallback_ref)
        if deviation > MAX_CORNER_DEVIATION_FT:
            dbg(
                "  (!) interseccion de planos descartada: el punto calculado "
                "quedo a {0:.1f} m del punto medio entre las caras (planos "
                "casi paralelos). Se usa el punto medio como respaldo.".format(
                    UnitUtils.ConvertFromInternalUnits(deviation, UnitTypeId.Meters)
                )
            )
            base_point = fallback_ref

        # Recortar la altura para que quede dentro de la zona real de
        # ambas caras, ampliada 50 cm arriba y abajo.
        z_min_a, z_max_a = get_face_z_range(face_a)
        z_min_b, z_max_b = get_face_z_range(face_b)
        allowed_min = max(z_min_a, z_min_b) - FACE_VERTICAL_PAD_FT
        allowed_max = min(z_max_a, z_max_b) + FACE_VERTICAL_PAD_FT
        if allowed_min > allowed_max:
            # las caras no se solapan ni ampliadas: usar la union en su
            # lugar, tambien ampliada, en vez de dejar el punto sin acotar
            allowed_min = min(z_min_a, z_min_b) - FACE_VERTICAL_PAD_FT
            allowed_max = max(z_max_a, z_max_b) + FACE_VERTICAL_PAD_FT
        base_point = clamp_point_to_z_range(line_point, direction, base_point,
                                             allowed_min, allowed_max)

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
    plano (esquina real), anclado a la linea directa p_start->p_end.

    Se deja como wrapper de conveniencia sobre merge_coplanar_faces +
    waypoints_for_path, que ahora se llaman por separado en main()
    para poder reutilizar la fusion de caras (calculada una sola vez)
    y recalcular solo la proyeccion (p_start/p_end) para cada tubo en
    paralelo."""
    return waypoints_for_path(merge_coplanar_faces(picked_faces), p_start, p_end)


def merge_coplanar_faces(picked_faces):
    """Fusiona caras SEGUIDAS que son, en la practica, el mismo plano
    (mismo muro, aunque este subdividido en paneles), dejando solo los
    puntos donde realmente cambia de plano (esquinas reales). Se
    calcula UNA sola vez por cada corrida del script, independientemente
    de cuantos tubos en paralelo se vayan a crear (el resultado no
    depende de que conector se use)."""
    distinct = []
    for face, origin, normal in picked_faces:
        if distinct and is_same_plane(distinct[-1][1], distinct[-1][2], origin, normal):
            continue
        distinct.append((face, origin, normal))
    return distinct


def waypoints_for_path(distinct_faces, p_start, p_end):
    """A partir de las caras ya fusionadas (merge_coplanar_faces),
    calcula los puntos de esquina. Para tubos en paralelo, p_start/
    p_end deben ser el origen del CONECTOR real de ese tubo especifico
    (no el punto generico del fixture): asi cada tubo obtiene su
    propia proyeccion, consistente con su propia altura/posicion, en
    vez de que todos los tubos compartan una unica linea central que
    no coincide con ninguno de ellos.

    IMPORTANTE: cada esquina se ancla contra la linea que va desde el
    ULTIMO punto ya calculado (running_point, que arranca en p_start y
    avanza con cada esquina) hasta p_end -- NO siempre contra la linea
    original p_start->p_end fija. Si se ancla siempre contra la linea
    fija del inicio, en rutas con varias esquinas que no estan
    alineadas con esa unica linea recta (zigzag, subida/bajada, etc.)
    la proyeccion de una esquina puede caer "mas atras" que la
    esquina anterior, y el tubo terminaba devolviendose en vez de
    seguir avanzando. Al anclar contra el ultimo punto real ya
    resuelto, la referencia de proyeccion avanza junto con la ruta y
    no puede retroceder."""
    waypoints = []
    running_point = p_start
    for i in range(len(distinct_faces) - 1):
        face_a, origin_a, normal_a = distinct_faces[i]
        face_b, origin_b, normal_b = distinct_faces[i + 1]
        corner = compute_corner_point(face_a, origin_a, normal_a, face_b, origin_b, normal_b,
                                       running_point, p_end)
        waypoints.append(corner)
        running_point = corner
    return waypoints


def compute_cumulative_fractions(ref_start, base_waypoints, ref_end):
    """Para cada punto de 'base_waypoints' calcula que fraccion (0..1)
    de la longitud TOTAL de la ruta de referencia (ref_start -> ...
    -> ref_end) representa llegar hasta ese punto. Se usa para
    interpolar, de forma suave y proporcional a la distancia real
    recorrida, el desplazamiento lateral propio de cada tubo en
    paralelo (ver interpolate_offset), en vez de repartir ese
    desplazamiento por indice de punto (lo cual no es preciso si los
    tramos tienen longitudes muy distintas entre si)."""
    pts = [ref_start] + list(base_waypoints) + [ref_end]
    dists = [pts[i].DistanceTo(pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(dists)
    n = len(base_waypoints)
    if total < 1e-9:
        return [(i + 1) / float(n + 1) for i in range(n)]
    fractions = []
    cum = 0.0
    for i in range(n):
        cum += dists[i]
        fractions.append(cum / total)
    return fractions


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


def get_open_connectors(element):
    """Conectores FISICOS de conduit sin conectar (puede haber mas de
    uno, ej. dos conductos de 3\" en paralelo).

    Se filtran por Domain.DomainCableTrayConduit: un Electrical
    Fixture normalmente tambien trae un conector ELECTRICO logico
    (para el circuito, Domain.DomainElectrical) que no representa un
    tubo fisico y no tiene un diametro real de conduit. Si no se
    filtra, ese conector logico se mezcla con los conectores de
    conduit reales, lo que genera conteos y diametros incorrectos (ej.
    detectar 1\" en vez de 3\", o emparejar solo una ruta en vez de las
    dos)."""
    return [
        c for c in get_connectors(element)
        if not c.IsConnected and c.Domain == Domain.DomainCableTrayConduit
    ]


def sort_connectors_by_lateral_then_height(connectors, reference_point, route_direction):
    """Ordena los conectores abiertos de un mismo fixture con DOS
    criterios, en este orden de prioridad:

    1) Posicion LATERAL (PRIMER criterio): se agrupan los conectores
       cuya posicion lateral difiere menos de CONNECTOR_LATERAL_TOL_MM
       (misma "columna", ej. izquierda/derecha), y esos grupos se
       ordenan de un lado al otro. Esto asegura que los conectores mas
       cercanos entre si lateralmente (ej. los 4 que estan pegados)
       queden agrupados y se conecten entre si.
    2) ALTURA (SEGUNDO criterio): dentro de cada grupo lateral, se
       ordena de arriba hacia abajo, para que dentro de la misma
       columna tampoco se crucen los tubos en paralelo.

    Al aplicar el mismo criterio (con la misma direccion lateral
    global) tanto al fixture inicial como al final, el zip() posterior
    empareja columna-con-columna y, dentro de cada columna,
    arriba-con-arriba / abajo-con-abajo."""
    lateral = route_direction.CrossProduct(XYZ.BasisZ)
    if lateral.GetLength() < 1e-6:
        lateral = route_direction.CrossProduct(XYZ.BasisX)
    lateral = lateral.Normalize()

    vertical = lateral.CrossProduct(route_direction)
    if vertical.GetLength() < 1e-6:
        vertical = XYZ.BasisZ
    else:
        vertical = vertical.Normalize()

    def lateral_val(c):
        return lateral.DotProduct(c.Origin - reference_point)

    def vertical_val(c):
        return vertical.DotProduct(c.Origin - reference_point)

    # --- Primer criterio: agrupar por posicion lateral con tolerancia
    # (comparando contra el promedio incremental del grupo, para no
    # depender de comparar solo contra un elemento fijo). ---
    ordered_by_lateral = sorted(connectors, key=lateral_val)
    groups = []
    for c in ordered_by_lateral:
        placed = False
        for group in groups:
            group_avg = sum(lateral_val(x) for x in group) / len(group)
            if abs(lateral_val(c) - group_avg) <= CONNECTOR_LATERAL_TOL_FT:
                group.append(c)
                placed = True
                break
        if not placed:
            groups.append([c])

    groups.sort(key=lambda grp: sum(lateral_val(x) for x in grp) / len(grp))

    # --- Segundo criterio: dentro de cada grupo lateral, ordenar por
    # altura (de arriba hacia abajo). ---
    ordered = []
    for group in groups:
        group.sort(key=vertical_val, reverse=True)
        ordered.extend(group)
    return ordered


def keep_connectors_facing(connectors, direction):
    """De todos los conectores de conduit abiertos de UN fixture, deja
    solo los que miran hacia el OTRO fixture (los 'cercanos', el lado
    por donde debe salir esta ruta), descartando los que miran hacia
    el lado contrario (los 'lejanos', que deben quedar quietos sin
    tocar). Se decide por el signo del producto punto entre la
    direccion de salida de cada conector (BasisZ de su sistema de
    coordenadas) y 'direction' (la direccion hacia el otro fixture)."""
    return [c for c in connectors if c.CoordinateSystem.BasisZ.DotProduct(direction) > 0]


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


def create_routed_conduit_between_connectors(doc, conn_start, conn_end, waypoints,
                                              conduit_type_id, level_id):
    """Igual que antes, pero recibe directamente el CONECTOR inicial y
    final ya elegidos (uno de los N conectores abiertos del fixture),
    en vez de escogerlos internamente. Asi se puede llamar una vez por
    cada tubo en paralelo. Crea la ruta como tramos INDEPENDIENTES (ver
    notas del encabezado del archivo): sin ConnectTo ni codos, solo
    piezas de conduit sueltas cuyos extremos coinciden geometricamente.

    Devuelve (path_points, created_ids) para diagnostico: la
    polilinea completa realmente usada y los ElementId de cada tramo
    de Conduit creado, en el mismo orden."""
    p1 = conn_start.Origin
    stub1_dir = conn_start.CoordinateSystem.BasisZ.Normalize()
    stub1_end = p1 + stub1_dir.Multiply(STUB_LEN_FT)

    p2 = conn_end.Origin
    stub2_dir = conn_end.CoordinateSystem.BasisZ.Normalize()
    stub2_end = p2 + stub2_dir.Multiply(STUB_LEN_FT)

    # Polilinea completa: origen del conector inicial -> stub -> waypoints
    # -> stub -> origen del conector final. Cada par consecutivo se crea
    # como un tramo de conduit suelto.
    path_points = [p1, stub1_end] + list(waypoints) + [stub2_end, p2]

    created_ids = []
    for i in range(len(path_points) - 1):
        new_conduit = Conduit.Create(doc, conduit_type_id, path_points[i], path_points[i + 1], level_id)
        created_ids.append(new_conduit.Id)

    return path_points, created_ids


def main():
    fixture_filter = ElectricalFixtureFilter()

    try:
        pick_start = uidoc.Selection.PickObject(
            ObjectType.Element, fixture_filter,
            "Selecciona el ELECTRICAL FIXTURE INICIAL"
        )
        pick_end = uidoc.Selection.PickObject(
            ObjectType.Element, fixture_filter,
            "Selecciona el ELECTRICAL FIXTURE FINAL"
        )
    except OperationCanceledException:
        return

    elem_start = doc.GetElement(pick_start.ElementId)
    elem_end = doc.GetElement(pick_end.ElementId)

    dbg("## DIAGNOSTICO: Fixtures")
    dbg("- **Fixture INICIAL** | ElementId: `{0}` | Location: {1}".format(
        elem_start.Id, fmt_xyz(get_location_point(elem_start))
    ))
    dbg("- **Fixture FINAL** | ElementId: `{0}` | Location: {1}".format(
        elem_end.Id, fmt_xyz(get_location_point(elem_end))
    ))

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

        pick_point = face_ref.GlobalPoint
        dbg("- Cara #{0} clickeada | host ElementId: `{1}` | punto de clic (crudo, GlobalPoint): {2}".format(
            len(picked_faces) + 1, doc.GetElement(face_ref).Id, fmt_xyz(pick_point)
        ))

        origin, normal = get_face_plane(face, pick_point)

        deviation = distance_point_to_segment(
            origin, get_location_point(elem_start), get_location_point(elem_end)
        )
        if deviation > MAX_FACE_ORIGIN_DEVIATION_FT:
            forms.alert(
                "El punto obtenido para esta cara quedo a {0:.1f} m de la "
                "ruta entre los dos fixtures (posible problema al leer el "
                "punto de clic sobre esta geometria). Se descarta este "
                "clic: intenta seleccionar la cara de nuevo.".format(
                    UnitUtils.ConvertFromInternalUnits(deviation, UnitTypeId.Meters)
                )
            )
            continue

        picked_faces.append((face, origin, normal))
        dbg_face_info("cara #{0} (cruda, antes de fusionar)".format(len(picked_faces)), face, origin, normal)

    if not picked_faces:
        proceed = forms.alert(
            "No marcaste ninguna cara: se creara un tramo directo entre "
            "los dos electrical fixtures. Continuar?",
            yes=True, no=True
        )
        if not proceed:
            return
        distinct_faces = []
    else:
        # --- Deteccion y correccion automatica de orden invertido ---
        # El resto del codigo arma la ruta como
        # p_start -> cara#1 -> cara#2 -> ... -> cara#N -> p_end, en el
        # orden EXACTO en que se clickearon las caras. Si el usuario
        # clickeo empezando por el lado del fixture FINAL y terminando
        # cerca del fixture INICIAL (orden "al reves"), la ruta salta
        # de p_start hasta el otro extremo del tunel, retrocede cara
        # por cara, y al final vuelve a saltar hasta p_end: un zigzag
        # grande ("avanza y se devuelve"), no un error de calculo de
        # esquinas. Se detecta comparando, a lo largo de la direccion
        # fixture inicial -> fixture final, si la PRIMERA cara
        # clickeada quedo mas cerca del fixture final que la ULTIMA;
        # en ese caso se invierte la lista antes de seguir.
        route_dir_check = get_location_point(elem_end) - get_location_point(elem_start)
        if route_dir_check.GetLength() > 1e-9:
            route_dir_check = route_dir_check.Normalize()
            proj_first = route_dir_check.DotProduct(picked_faces[0][1] - get_location_point(elem_start))
            proj_last = route_dir_check.DotProduct(picked_faces[-1][1] - get_location_point(elem_start))
            if proj_first > proj_last:
                dbg(
                    "## (!) Orden de caras invertido detectado: la primera "
                    "cara clickeada quedaba mas cerca del fixture FINAL que "
                    "la ultima. Se invierte el orden de la lista antes de "
                    "construir la ruta."
                )
                forms.alert(
                    "Las caras parecen haber sido clickeadas en orden "
                    "inverso (de fixture FINAL hacia fixture INICIAL). Se "
                    "invierte automaticamente el orden para construir la "
                    "ruta correctamente."
                )
                picked_faces = list(reversed(picked_faces))
        distinct_faces = merge_coplanar_faces(picked_faces)

    dbg("## DIAGNOSTICO: Caras FUSIONADAS (despues de merge_coplanar_faces)")
    dbg("Total caras clickeadas: {0} -> total caras distintas (planos) despues de fusionar: {1}".format(
        len(picked_faces), len(distinct_faces)
    ))
    for i, (face, origin, normal) in enumerate(distinct_faces):
        dbg_face_info("plano distinto #{0}".format(i), face, origin, normal)

    # Todos los conectores FISICOS de conduit sin conectar de cada
    # fixture (puede haber 4: 2 en el lado cercano al otro fixture, 2
    # en el lado lejano/contrario).
    open_start = get_open_connectors(elem_start)
    open_end = get_open_connectors(elem_end)

    dbg("## DIAGNOSTICO: Conectores abiertos de conduit (SIN filtrar por lado)")
    dbg("**Fixture INICIAL** ({0} conector(es) abiertos de conduit):".format(len(open_start)))
    for i, c in enumerate(open_start):
        dbg_connector_info("conector inicial #{0}".format(i), c, elem_start)
    dbg("**Fixture FINAL** ({0} conector(es) abiertos de conduit):".format(len(open_end)))
    for i, c in enumerate(open_end):
        dbg_connector_info("conector final #{0}".format(i), c, elem_end)

    if not open_start or not open_end:
        forms.alert(
            "Alguno de los dos electrical fixtures no tiene conectores "
            "de conduit abiertos.",
            exitscript=True
        )

    # Direccion general de la ruta (de fixture a fixture). Se usa para
    # dos cosas: (1) quedarnos solo con los conectores de CADA fixture
    # que miran hacia el OTRO fixture (el lado 'cercano'; el lado
    # 'lejano' queda quieto sin tocar), y (2) ordenar (lateral y luego
    # altura) los que sobreviven para emparejarlos consistentemente y
    # que los tubos en paralelo no se crucen.
    route_direction = get_location_point(elem_end) - get_location_point(elem_start)
    if route_direction.GetLength() < 1e-9:
        route_direction = XYZ.BasisX
    else:
        route_direction = route_direction.Normalize()

    # En el fixture inicial, "cercano" = mira hacia elem_end (misma
    # direccion que route_direction). En el fixture final, "cercano" =
    # mira hacia elem_start (direccion opuesta a route_direction).
    open_start = keep_connectors_facing(open_start, route_direction)
    open_end = keep_connectors_facing(open_end, route_direction.Negate())

    dbg("## DIAGNOSTICO: Conectores despues de filtrar por lado 'cercano'")
    dbg("route_direction (fixture inicial -> fixture final): {0}".format(fmt_vec(route_direction)))
    dbg("**Fixture INICIAL**, lado cercano ({0} conector(es)):".format(len(open_start)))
    for i, c in enumerate(open_start):
        dbg_connector_info("cercano inicial #{0}".format(i), c, elem_start)
    dbg("**Fixture FINAL**, lado cercano ({0} conector(es)):".format(len(open_end)))
    for i, c in enumerate(open_end):
        dbg_connector_info("cercano final #{0}".format(i), c, elem_end)

    if not open_start or not open_end:
        forms.alert(
            "No se encontraron conectores de conduit orientados hacia "
            "el otro electrical fixture (todos miran hacia el lado "
            "contrario).",
            exitscript=True
        )

    if len(open_start) != len(open_end):
        forms.alert(
            "Del lado cercano, el fixture inicial tiene {0} conector(es) "
            "y el final tiene {1}. Se emparejaran solo los primeros {2} "
            "(los sobrantes se ignoran).".format(
                len(open_start), len(open_end), min(len(open_start), len(open_end))
            )
        )

    open_start = sort_connectors_by_lateral_then_height(open_start, get_location_point(elem_start), route_direction)
    open_end = sort_connectors_by_lateral_then_height(open_end, get_location_point(elem_end), route_direction)

    pairs = list(zip(open_start, open_end))

    dbg("## DIAGNOSTICO: Conectores ORDENADOS (lateral, luego altura) y EMPAREJADOS")
    for i, (cs, ce) in enumerate(pairs):
        dbg("**Par #{0}**:".format(i))
        dbg_connector_info("  -> conector INICIAL del par #{0}".format(i), cs, elem_start)
        dbg_connector_info("  -> conector FINAL del par #{0}".format(i), ce, elem_end)

    # --- Ruta de referencia (UNA sola, comun a todos los tubos) ---
    # Se calcula usando el punto del FIXTURE (no de un conector en
    # particular) como ancla. Si se calculara una esquina distinta
    # por cada tubo (proyectando cada uno por su lado), los 4 puntos
    # de esquina terminan cayendo casi todos sobre la MISMA recta de
    # interseccion de los dos planos (esa recta depende solo de las
    # caras, no del conector), lo que hace que los tubos en paralelo
    # converjan y se crucen justo en la esquina, aunque en sus
    # extremos (conectores) si esten separados lateralmente.
    ref_p_start = get_location_point(elem_start)
    ref_p_end = get_location_point(elem_end)
    base_waypoints = (
        waypoints_for_path(distinct_faces, ref_p_start, ref_p_end)
        if distinct_faces else []
    )
    fractions = (
        compute_cumulative_fractions(ref_p_start, base_waypoints, ref_p_end)
        if base_waypoints else []
    )

    dbg("## DIAGNOSTICO: Ruta BASE de referencia (comun a todos los tubos)")
    dbg("ref_p_start (fixture inicial): {0}".format(fmt_xyz(ref_p_start)))
    for i, wp in enumerate(base_waypoints):
        dbg("- waypoint base #{0}: {1} | fraccion acumulada: {2:.4f}".format(
            i, fmt_xyz(wp), fractions[i]
        ))
    dbg("ref_p_end (fixture final): {0}".format(fmt_xyz(ref_p_end)))

    level_id = get_level_id(elem_start, doc)

    dbg("## DIAGNOSTICO: Trazado final por cada tubo (lo que realmente se crea)")

    t = Transaction(doc, "Crear tramos de conduit (sin conexion) entre electrical fixtures")
    t.Start()
    try:
        for pipe_idx, (conn_start, conn_end) in enumerate(pairs):
            # Desplazamiento lateral REAL de este tubo respecto a la
            # ruta de referencia: la diferencia entre su conector y el
            # punto del fixture, en cada extremo.
            offset_start = conn_start.Origin - ref_p_start
            offset_end = conn_end.Origin - ref_p_end

            # Cada waypoint de la ruta base se desplaza por una mezcla
            # de offset_start/offset_end, ponderada segun que tan
            # avanzado esta ese punto en la ruta (fractions). Asi el
            # tubo se separa suavemente desde su conector inicial y
            # converge suavemente hacia su conector final, MANTENIENDO
            # siempre la misma separacion relativa que en los stubs:
            # nunca se cruza con los demas tubos en paralelo.
            waypoints_i = [
                base_waypoints[j]
                + offset_start.Multiply(1.0 - fractions[j])
                + offset_end.Multiply(fractions[j])
                for j in range(len(base_waypoints))
            ]

            # Diametro FIJO (trade size 3", buscado por su Outside
            # Diameter real de 3.5" via CONDUIT_DIAMETER_FT), no el
            # diametro real del conector del fixture.
            conduit_type_id = find_matching_conduit_type(doc, CONDUIT_DIAMETER_FT)

            path_points, created_ids = create_routed_conduit_between_connectors(
                doc, conn_start, conn_end, waypoints_i, conduit_type_id, level_id
            )

            dbg("### Tubo #{0}".format(pipe_idx))
            dbg("offset_start (conector inicial - fixture inicial): {0}".format(fmt_xyz(offset_start)))
            dbg("offset_end (conector final - fixture final): {0}".format(fmt_xyz(offset_end)))
            dbg("Conduit type usado: `{0}`".format(conduit_type_id))
            dbg("Nivel usado: `{0}`".format(level_id))
            dbg("Polilinea COMPLETA (en orden, incluye stubs):")
            for i, p in enumerate(path_points):
                tag = ""
                if i == 0:
                    tag = " <- origen conector INICIAL"
                elif i == 1:
                    tag = " <- fin del stub inicial (10cm)"
                elif i == len(path_points) - 2:
                    tag = " <- inicio del stub final (10cm)"
                elif i == len(path_points) - 1:
                    tag = " <- origen conector FINAL"
                else:
                    tag = " <- waypoint de esquina"
                dbg("  {0}. {1}{2}".format(i, fmt_xyz(p), tag))
            dbg("Tramos de Conduit creados (ElementIds, en el mismo orden de la polilinea): {0}".format(
                ", ".join(str(cid) for cid in created_ids)
            ))
        t.Commit()
    except Exception as ex:
        t.RollBack()
        forms.alert("No se pudo crear la ruta de conduit:\n{}".format(ex))


if __name__ == '__main__':
    main()