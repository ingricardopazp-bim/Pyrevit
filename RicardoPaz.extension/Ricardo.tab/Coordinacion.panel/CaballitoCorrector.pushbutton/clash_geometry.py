# -*- coding: utf-8 -*-
"""
clash_geometry.py

Motor geométrico avanzado para resolución automática
de clashes MEP en Revit.

CARACTERÍSTICAS:
✔ Intersección REAL contra sólidos
✔ Compatibilidad con Revit Links
✔ Detección robusta de sólidos anidados
✔ Sistema de coordenadas local
✔ Protección contra tuberías verticales
✔ Caballitos 45°
✔ Caballitos 90°
✔ Ángulo variable
✔ Medición REAL de espacio libre (raycast sobre sólido real)
✔ Validación geométrica final
✔ Debug avanzado
✔ Librería rolling_offset_math integrada (§1-§18)

Autor: Ricardo Paz
CORRECCIONES GEOMETRICAS v4: 2025

FÓRMULAS IMPLEMENTADAS (norma de obra):
  Salto Neto:       S = D + H + R1           (rolling_offset_math.salto_neto)
  Longitud eje-eje: L = S / sin(α)           (rolling_offset_math.travel)
  Avance:           A = S / tan(α)           (rolling_offset_math.spacing)
  Longitud corte:   L_corte = L - (2 × C)   (rolling_offset_math.caballito_params)
  Offset mínimo:    S_min = R + R_obs + H    (rolling_offset_math.offset_minimo)
  Rolling 3D:       S_roll = sqrt(X²+Y²)    (rolling_offset_math.resultante_horizontal)
"""

# ============================================================
# IMPORTS
# ============================================================

import math
import Autodesk

from Autodesk.Revit.DB import (

    XYZ,
    Line,
    Solid,
    Options,
    Transform,
    GeometryInstance,
    RevitLinkInstance,

    SolidCurveIntersectionOptions,
    SolidUtils,

    ViewDetailLevel

)

# Librería matemática pura — sin dependencias de Revit API
# Contiene todas las fórmulas de rolling offset, vectores y clash geometry
from rolling_offset_math import (
    salto_neto,
    travel,
    spacing,
    resultante_horizontal,
    offset_minimo,
    caballito_params,
    build_bypass_points,
    aabb_overlap,
    distance_point_to_line_3d,
    clearance_between_pipes,
    longitud_total,
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Holgura mínima libre entre cara de tubería y cara del obstáculo (ft)
# H en la fórmula S = D + H + R1
# 50 mm ≈ 0.164 ft  (ajustar según norma de proyecto)
HOLGURA_DEFAULT = 50.0 / 304.8

MIN_SEGMENT = 0.20
STEP = 0.10
MAX_SEARCH_DISTANCE = 10.0

# ============================================================
# DEDUCCIÓN CENTRO-A-CARA  (C)  —  NORMAS ASME / ASTM
# ============================================================
#
# ESTRATEGIA:
#   • ASME B16.9 LR  (acero carbono/inox soldado a tope)
#       C_90 = 1.5 × d_n  [pulgadas]          ← FÓRMULA EXACTA
#       C_45 = 0.414 × 1.5 × d_n              ← FÓRMULA EXACTA
#       C_α  = C_90 × tan(α/2)                ← FÓRMULA GENERAL
#
#   • Materiales sin fórmula cerrada (PVC, CPVC, Cobre, Roscado)
#       Se usan tablas tabuladas de los estándares ASTM / ASME B16.
#       Para ángulos intermedios: C_α = C_90 × tan(α/2)
#
# Todas las tablas en MILÍMETROS, clave = NPS en pulgadas.
# ============================================================

# ── PVC cédula 40 — ASTM D2466 ──────────────────────────────────────
_C_PVC_SCH40 = {
    0.50:  19.1,
    0.75:  22.2,
    1.00:  26.7,
    1.25:  31.8,
    1.50:  36.6,
    2.00:  45.7,
    2.50:  55.9,
    3.00:  66.0,
    4.00:  84.1,
    6.00: 123.8,
    8.00: 163.6,
}

# ── CPVC cédula 80 — ASTM D2467 ─────────────────────────────────────
_C_CPVC_SCH80 = {
    0.25:   9.7,
    0.50:  19.1,
    0.75:  22.4,
    1.00:  27.0,
    1.25:  32.0,
    1.50:  36.8,
    2.00:  46.0,
    3.00:  66.7,
    4.00:  85.1,
}

# ── Fierro maleable roscado — ASME B16.3 Clase 150 ──────────────────
_C_ROSCADO_150 = {
    0.25:   9.5,
    0.375: 11.1,
    0.50:  14.3,
    0.75:  17.5,
    1.00:  22.2,
    1.25:  26.2,
    1.50:  29.4,
    2.00:  36.5,
    2.50:  44.4,
    3.00:  52.4,
    4.00:  66.7,
}

# ── Cobre tipo L/M soldable — ASME B16.22 ───────────────────────────
_C_COBRE_LM = {
    0.375: 11.1,
    0.50:  15.9,
    0.75:  19.1,
    1.00:  25.4,
    1.25:  31.8,
    1.50:  38.1,
    2.00:  50.8,
    2.50:  63.5,
    3.00:  76.2,
    4.00: 101.6,
}

# ── Mapa de nombre de sistema Revit → método/tabla ──────────────────
# Tuplas: (subcadena_en_nombre_sistema, tipo_calculo, tabla_o_None)
# tipo_calculo:
#   'b169_lr'  → fórmula ASME B16.9 LR  (C_90 = 1.5 × d_n)
#   'table'    → tabla tabulada
_SYSTEM_CALC_MAP = [
    ("copper",    "table",    _C_COBRE_LM),
    ("cobre",     "table",    _C_COBRE_LM),
    ("cpvc",      "table",    _C_CPVC_SCH80),
    ("pvc",       "table",    _C_PVC_SCH40),
    ("galv",      "table",    _C_ROSCADO_150),
    ("rosca",     "table",    _C_ROSCADO_150),
    ("threaded",  "table",    _C_ROSCADO_150),
    ("screwed",   "table",    _C_ROSCADO_150),
    ("socket",    "table",    _C_ROSCADO_150),  # B16.11: misma lógica tabla
    ("acero",     "b169_lr",  None),
    ("steel",     "b169_lr",  None),
    ("carbon",    "b169_lr",  None),
    ("negro",     "b169_lr",  None),
    ("black",     "b169_lr",  None),
    ("stainless", "b169_lr",  None),
    ("inox",      "b169_lr",  None),
    ("ss",        "b169_lr",  None),
]

# Fallback: acero soldable ASME B16.9 LR (el más común en obra)
_FALLBACK_CALC = "b169_lr"


# ── Utilidad: interpolación lineal en tabla ──────────────────────────

def _lookup_table(table, nps_in):
    """Busca C en tabla; interpola linealmente si NPS no está exacto."""
    keys = sorted(table.keys())
    if nps_in in table:
        return table[nps_in]
    lower = [k for k in keys if k <= nps_in]
    upper = [k for k in keys if k >= nps_in]
    if not lower:
        return table[keys[0]]
    if not upper:
        return table[keys[-1]]
    k_lo, k_hi = lower[-1], upper[0]
    if k_lo == k_hi:
        return table[k_lo]
    t = (nps_in - k_lo) / float(k_hi - k_lo)
    return table[k_lo] + t * (table[k_hi] - table[k_lo])


# ── Cálculo principal de C ───────────────────────────────────────────

def get_elbow_deduction_mm(mep_element, angle_deg=90):
    """
    Calcula C (deducción centro-a-cara del codo) en mm.

    Normas implementadas
    --------------------
    ASME B16.9 LR  (acero carbono/inox soldado a tope):
        C_90 = 1.5 × d_n [pulg] × 25.4
        C_45 = 0.414 × 1.5 × d_n [pulg] × 25.4
        C_α  = C_90 × tan(α / 2)          ← fórmula general LR

    PVC/CPVC/Cobre/Roscado:
        C_90  ← tabla tabulada del estándar
        C_α   = C_90 × tan(α / 2)

    Parámetros
    ----------
    mep_element : Revit Element  (Pipe o Conduit)
    angle_deg   : float  — ángulo real del codo utilizado (45, 90, etc.)

    Retorna C en milímetros.
    """

    # ── 1. Diámetro nominal en pulgadas ─────────────────────────
    nps_in = 1.0

    try:
        for pname in ["Outside Diameter", "Diameter",
                      "Nominal Diameter", "Inside Diameter"]:
            p = mep_element.LookupParameter(pname)
            if p and p.AsDouble() > 0:
                nps_in = p.AsDouble() * 12.0   # pies → pulgadas
                break
    except Exception:
        pass

    # Redondear al NPS comercial más cercano
    NPS_COMERCIALES = [
        0.25, 0.375, 0.50, 0.75, 1.00, 1.25, 1.50,
        2.00, 2.50, 3.00, 3.50, 4.00, 5.00, 6.00,
        8.00, 10.00, 12.00
    ]
    nps_in = min(NPS_COMERCIALES, key=lambda x: abs(x - nps_in))

    # ── 2. Identificar material desde el nombre del sistema ──────
    system_name = ""
    try:
        sys_elem = mep_element.MEPSystem
        if sys_elem:
            stype = sys_elem.Document.GetElement(sys_elem.GetTypeId())
            system_name = (stype.Name if stype else sys_elem.Name) or ""
    except Exception:
        pass

    calc_type  = _FALLBACK_CALC
    table_data = None
    name_lower = system_name.lower()

    for keyword, ctype, tbl in _SYSTEM_CALC_MAP:
        if keyword in name_lower:
            calc_type  = ctype
            table_data = tbl
            break

    # ── 3. C_90 según norma ──────────────────────────────────────
    if calc_type == "b169_lr":
        # ASME B16.9 Long Radius — fórmula exacta
        # C_90 [mm] = 1.5 × NPS [pulg] × 25.4 mm/pulg
        C_90_mm = 1.5 * nps_in * 25.4
        norma   = "ASME B16.9 LR"
    else:
        # Tabla tabulada
        C_90_mm = _lookup_table(table_data, nps_in)
        norma   = "tabla"

    # ── 4. Ajustar a ángulo real: C_α = C_90 × tan(α/2) ────────
    # Fórmula válida para codos Long Radius y como aproximación
    # razonable para tablas tabuladas a ángulos intermedios.
    if angle_deg == 90:
        C_mm = C_90_mm
    else:
        # Fórmula exacta ASME B16.9: C_α = C_90 × tan(α/2)
        # Aplica tanto a LR como a tablas tabuladas para ángulos intermedios.
        # No se usa la constante 0.414 (es solo una aproximación de tan(22.5°)=0.41421...)
        C_mm = C_90_mm * math.tan(math.radians(angle_deg / 2.0))

    print(
        u"DEDUCCIÓN C — NPS={:.3f}\"  sistema='{}'  norma={}  "
        u"C_90={:.2f}mm  α={}°  C={:.2f}mm".format(
            nps_in, system_name, norma, C_90_mm, angle_deg, C_mm
        )
    )

    return C_mm

# ============================================================
# UTILIDADES
# ============================================================

def ft(mm):
    return mm / 304.8


def safe_normalize(vec):

    try:

        if vec.GetLength() < 1e-9:
            return XYZ(0, 0, 0)

        return vec.Normalize()

    except:
        return XYZ(0, 0, 0)

# ============================================================
# CLASE PRINCIPAL
# ============================================================

class ClashAnalyzer(object):

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        doc,
        mep_element,
        obstacle_element,
        link_instance=None
    ):

        self.doc = doc

        self.mep_element = mep_element

        self.obstacle = obstacle_element

        self.link_instance = link_instance

        self.link_transform = (

            link_instance.GetTotalTransform()

            if link_instance

            else Transform.Identity

        )

        self.mep_curve = None

        self.mep_direction = None

        self.mep_diameter = None

        self.forward = None
        self.right = None
        self.up = None

        self.obstacle_solids = []

        self.clash_zone = None

        self.available_directions = {}

        self.recommended = None

    # ========================================================
    # ANALYZE
    # ========================================================

    def analyze(self):

        print("\n==============================")
        print("INICIANDO ANÁLISIS")
        print("==============================")

        self._extract_mep_geometry()

        self._extract_obstacle_solids()

        if not self.obstacle_solids:

            print("NO SE ENCONTRARON SÓLIDOS")

            return False

        self.clash_zone = self._compute_real_clash()

        if not self.clash_zone:

            print("NO SE DETECTÓ INTERSECCIÓN GEOMÉTRICA")

            return False

        self._evaluate_directions()

        self.recommended = self._recommend_direction()

        print("DIRECCIÓN RECOMENDADA:", self.recommended)

        return True

    # ========================================================
    # GEOMETRÍA MEP
    # ========================================================

    def _extract_mep_geometry(self):

        print("\nEXTRAYENDO GEOMETRÍA MEP")

        loc = self.mep_element.Location

        self.mep_curve = loc.Curve

        p0 = self.mep_curve.GetEndPoint(0)

        p1 = self.mep_curve.GetEndPoint(1)

        self.mep_direction = safe_normalize(
            p1.Subtract(p0)
        )

        try:

            param = (

                self.mep_element.LookupParameter(
                    "Outside Diameter"
                )

                or

                self.mep_element.LookupParameter(
                    "Diameter"
                )

            )

            self.mep_diameter = param.AsDouble()

        except:

            self.mep_diameter = ft(25)

        print("DIÁMETRO:", self.mep_diameter)

        self._build_local_system()

    # ========================================================
    # SISTEMA LOCAL
    # ========================================================

    def _build_local_system(self):

        self.forward = self.mep_direction

        world_up = XYZ.BasisZ

        dot = abs(
            self.forward.DotProduct(world_up)
        )

        # Protección tubería vertical
        if dot > 0.95:

            world_up = XYZ.BasisX

        self.right = safe_normalize(

            self.forward.CrossProduct(
                world_up
            )

        )

        self.up = safe_normalize(

            self.right.CrossProduct(
                self.forward
            )

        )

        print("SISTEMA LOCAL GENERADO")

    # ========================================================
    # EXTRAER SÓLIDOS
    # ========================================================

    def _extract_obstacle_solids(self):

        print("\nEXTRAYENDO SÓLIDOS")

        opt = Options()

        opt.ComputeReferences = False

        opt.IncludeNonVisibleObjects = True

        opt.DetailLevel = ViewDetailLevel.Fine

        geom = self.obstacle.get_Geometry(opt)

        solids = []

        # ====================================================
        # FUNCIÓN RECURSIVA
        # ====================================================

        def collect_geometry(
            geometry_element,
            current_transform
        ):

            for geo_obj in geometry_element:

                # --------------------------------------------
                # SOLID
                # --------------------------------------------

                if isinstance(geo_obj, Solid):

                    try:

                        if geo_obj.Volume > 1e-6:

                            transformed_solid = (
                                SolidUtils.CreateTransformed(
                                    geo_obj,
                                    current_transform
                                )
                            )

                            solids.append(
                                transformed_solid
                            )

                    except Exception as ex:

                        print(
                            "ERROR SOLID:",
                            ex
                        )

                # --------------------------------------------
                # GEOMETRY INSTANCE
                # --------------------------------------------

                elif isinstance(
                    geo_obj,
                    GeometryInstance
                ):

                    try:

                        instance_geometry = (
                            geo_obj.GetInstanceGeometry()
                        )

                        instance_transform = (
                            current_transform.Multiply(
                                geo_obj.Transform
                            )
                        )

                        collect_geometry(
                            instance_geometry,
                            instance_transform
                        )

                    except Exception as ex:

                        print(
                            "ERROR INSTANCE:",
                            ex
                        )

        # ====================================================
        # EJECUTAR
        # ====================================================

        collect_geometry(
            geom,
            self.link_transform
        )

        self.obstacle_solids = solids

        print(
            "SÓLIDOS DETECTADOS:",
            len(solids)
        )

    # ========================================================
    # INTERSECCIÓN REAL
    # ========================================================

    def _compute_real_clash(self):

        print("\nBUSCANDO INTERSECCIÓN REAL")

        p0 = self.mep_curve.GetEndPoint(0)

        p1 = self.mep_curve.GetEndPoint(1)

        direction = safe_normalize(
            p1.Subtract(p0)
        )

        # ====================================================
        # EXTENDER LÍNEA
        # ====================================================

        extension = 100.0

        new_start = p0.Subtract(
            direction.Multiply(extension)
        )

        new_end = p1.Add(
            direction.Multiply(extension)
        )

        test_line = Line.CreateBound(
            new_start,
            new_end
        )

        intersections = []

        # ====================================================
        # TEST SOLIDS
        # ====================================================

        for idx, solid in enumerate(
            self.obstacle_solids
        ):

            try:

                print(
                    "TEST SOLID:",
                    idx
                )

                options = (
                    SolidCurveIntersectionOptions()
                )

                result = solid.IntersectWithCurve(
                    test_line,
                    options
                )

                print(
                    "SEGMENTOS:",
                    result.SegmentCount
                )

                if result.SegmentCount > 0:

                    for i in range(
                        result.SegmentCount
                    ):

                        segment = (
                            result.GetCurveSegment(i)
                        )

                        seg_start = (
                            segment.GetEndPoint(0)
                        )

                        seg_end = (
                            segment.GetEndPoint(1)
                        )

                        intersections.append(
                            (seg_start, seg_end)
                        )

                        print(
                            "INTERSECCIÓN ENCONTRADA"
                        )

            except Exception as ex:

                print(
                    "ERROR INTERSECTION:",
                    ex
                )

        # ====================================================
        # VALIDAR
        # ====================================================

        if not intersections:

            return None

        intersections.sort(
            key=lambda x: p0.DistanceTo(x[0])
        )

        entry = intersections[0][0]

        exit_pt = intersections[-1][1]

        center = entry.Add(
            exit_pt.Subtract(entry).Multiply(0.5)
        )

        depth = entry.DistanceTo(exit_pt)

        print("ENTRY:", entry)

        print("EXIT:", exit_pt)

        print("DEPTH:", depth)

        return {

            "entry": entry,
            "exit": exit_pt,
            "center": center,
            "depth": depth

        }

    # ========================================================
    # EVALUAR DIRECCIONES
    # ========================================================

    def _evaluate_directions(self):

        print("\nEVALUANDO DIRECCIONES")

        directions = {

            "arriba": self.up,

            "abajo": self.up.Negate(),

            "derecha": self.right,

            "izquierda": self.right.Negate()

        }

        # Radio exterior de la tubería propia (R1 = diámetro / 2)
        radio_propio = self.mep_diameter / 2.0

        # Espacio mínimo requerido = R1 + H (holgura)
        # Es el offset mínimo medido desde el EJE de la tubería
        # hasta el punto libre más allá del obstáculo
        required = radio_propio + HOLGURA_DEFAULT

        for name, vec in directions.items():

            free_space = self._measure_free_space(
                self.clash_zone["center"],
                vec
            )

            feasible = free_space > required

            self.available_directions[name] = {

                "vector": vec,

                "free_space": free_space,

                "required": required,

                "feasible": feasible

            }

            print(
                name,
                "FREE:",
                free_space,
                "REQUIRED:",
                required,
                "OK:",
                feasible
            )

    # ========================================================
    # ESPACIO LIBRE REAL
    #
    # CORRECCIÓN 3+4: La versión anterior avanzaba punto a punto
    # y devolvía la distancia al PRIMER punto dentro del sólido
    # (cara de entrada). La fórmula S = D + H + R1 necesita D
    # como la distancia desde el eje de la tubería hasta la cara
    # MÁS LEJANA del obstáculo en la dirección del desvío.
    #
    # Solución: lanzar un rayo desde 'start' en 'direction',
    # intersectarlo contra todos los sólidos con IntersectWithCurve
    # y quedarse con el punto de SALIDA más lejano.
    # ========================================================

    def _measure_free_space(
        self,
        start,
        direction
    ):
        """
        Retorna D: distancia desde 'start' hasta la cara MÁS LEJANA
        del obstáculo en la dirección indicada.
        Si no hay intersección devuelve MAX_SEARCH_DISTANCE.
        """
        ray_end  = start.Add(direction.Multiply(MAX_SEARCH_DISTANCE))
        try:
            ray_line = Line.CreateBound(start, ray_end)
        except Exception:
            return MAX_SEARCH_DISTANCE

        farthest_exit = None

        for solid in self.obstacle_solids:
            try:
                opts   = SolidCurveIntersectionOptions()
                result = solid.IntersectWithCurve(ray_line, opts)
                for i in range(result.SegmentCount):
                    seg      = result.GetCurveSegment(i)
                    exit_pt  = seg.GetEndPoint(1)   # cara de SALIDA
                    dist_exit = start.DistanceTo(exit_pt)
                    if farthest_exit is None or dist_exit > farthest_exit:
                        farthest_exit = dist_exit
            except Exception:
                continue

        if farthest_exit is None:
            return MAX_SEARCH_DISTANCE

        return farthest_exit

    # ========================================================
    # RECOMENDACIÓN
    # ========================================================

    def _recommend_direction(self):

        feasible = {

            k: v

            for k, v

            in self.available_directions.items()

            if v["feasible"]

        }

        if not feasible:

            return None

        priority = [

            "arriba",

            "derecha",

            "izquierda",

            "abajo"

        ]

        best = sorted(

            feasible.items(),

            key=lambda x: (

                -x[1]["free_space"],

                priority.index(x[0])

            )

        )

        return best[0][0]

    # ========================================================
    # GENERAR BYPASS
    # ========================================================

    def get_bypass_points(

        self,

        direction_name,

        angle_deg=45,

        offset_distance=None,

        holgura=None,

        deduccion_codo=None

    ):
        """
        Calcula la geometría completa del caballito.

        Parámetros
        ----------
        direction_name  : str   – 'arriba', 'abajo', 'derecha', 'izquierda'
        angle_deg       : float – ángulo α de los codos (11.25, 22.5, 30, 45, 60, 90)
        offset_distance : float – Salto Neto manual en ft. Si es None se
                                  calcula con S = D + H + R1.
        holgura         : float – H en ft. Si es None usa HOLGURA_DEFAULT.
        deduccion_codo  : float – C en ft (centro-a-cara del codo). Se usa
                                  para calcular L_corte = L - 2C.
                                  Si es None usa DEDUCCION_CODO_DEFAULT.
        """

        if direction_name not in self.available_directions:

            raise Exception(
                "Dirección inválida: {}".format(direction_name)
            )

        # Advertencia si el usuario eligió manualmente una dirección
        # que el analizador marcó como infeasible (espacio insuficiente).
        dir_info = self.available_directions[direction_name]
        if not dir_info["feasible"]:
            print(
                u"ADVERTENCIA: dirección '{}' tiene espacio libre insuficiente "
                u"({:.1f} mm disponible, {:.1f} mm requerido). "
                u"El caballito puede colisionar con otros elementos.".format(
                    direction_name,
                    dir_info["free_space"] * 304.8,
                    dir_info["required"]   * 304.8,
                )
            )

        vec = self.available_directions[
            direction_name
        ]["vector"]

        entry   = self.clash_zone["entry"]
        exit_pt = self.clash_zone["exit"]

        # ── Valores por defecto ────────────────────────────────────
        if holgura is None:
            holgura = HOLGURA_DEFAULT

        # ── Deducción C automática ─────────────────────────────────
        # Si el usuario no pasa un valor manual, se calcula desde
        # las tablas ANSI/ASTM según el diámetro y tipo de sistema.
        if deduccion_codo is None:
            C_mm = get_elbow_deduction_mm(self.mep_element, angle_deg)
            deduccion_codo = C_mm / 304.8   # convertir mm → ft
            print(
                "C automático: {:.2f} mm ({:.5f} ft)".format(
                    C_mm, deduccion_codo
                )
            )

        # ── Salto Neto: S = D + H + R1 ────────────────────────────
        # D: distancia desde el eje de la tubería hasta la cara
        #    más lejana del obstáculo, medida en la dirección del desvío.
        #    Aquí D = free_space de la dirección seleccionada.
        if offset_distance is None:

            D  = self.available_directions[direction_name]["free_space"]
            H  = holgura
            R1 = self.mep_diameter / 2.0

            # Fórmula correcta: S = D + H + R1
            offset_distance = D + H + R1

            print(
                "SALTO NETO calculado:"
                "  D={:.4f}ft  H={:.4f}ft  R1={:.4f}ft  S={:.4f}ft".format(
                    D, H, R1, offset_distance
                )
            )

        # ====================================================
        # 90°
        # ====================================================

        if angle_deg == 90:

            return self._build_90(
                entry,
                exit_pt,
                vec,
                offset_distance,
                deduccion_codo
            )

        # ====================================================
        # VARIABLE / 45°
        # ====================================================

        return self._build_angle(

            entry,
            exit_pt,
            vec,
            offset_distance,
            angle_deg,
            deduccion_codo

        )

    # ========================================================
    # BUILD 90°
    #
    # CORRECCIÓN 1: La geometría del caballito 90° estaba mal.
    # P0 y P4 son los puntos donde comienzan las diagonales
    # perpendiculares al eje, no desplazados hacia atrás.
    # El segmento central P1→P3 debe ser PARALELO al eje original
    # y desplazado en la dirección del offset.
    # ========================================================

    def _build_90(
        self,
        entry,
        exit_pt,
        vec,
        offset,
        deduccion_codo=0.0
    ):

        print("\nGENERANDO 90°")

        # ── Longitud mínima del tramo perpendicular ────────────────
        # Cada tramo vertical necesita alojar 2 codos de 90° (2×C_90)
        # más un niple mínimo de ensamble.
        # Si el Salto Neto S < ese mínimo, el tramo físico sería
        # demasiado corto para insertar los accesorios → L_corte negativo.
        # Se usa C del codo a 90° porque estos tramos siempre llevan codos 90°.
        MIN_NIPLE_PERP = 50.0 / 304.8           # 50 mm mínimo de niple entre codos
        L_perp_min     = 2.0 * deduccion_codo + MIN_NIPLE_PERP

        # El offset real del eje puede ser mayor que S si los codos lo requieren.
        # Revit sigue desplazando la tubería la distancia correcta para el
        # clearance; el tramo extra sólo alarga la subida/bajada sin cambiar
        # la posición del tramo central (que está definido por entry/exit).
        L_perp = max(offset, L_perp_min)

        if L_perp > offset:
            print(
                u"  AJUSTE perp: S={:.1f}mm insuficiente para 2×C_90, "
                u"L_perp aumentado a {:.1f}mm".format(
                    offset * 304.8, L_perp * 304.8
                )
            )

        # back: distancia mínima de retiro antes/después del obstáculo
        back = max(
            self.mep_diameter * 3,
            MIN_SEGMENT
        )

        # P0: punto en el eje original, antes de la zona de clash
        P0 = entry.Subtract(
            self.forward.Multiply(back)
        )

        # P1: perpendicular desde P0 subiendo L_perp en dirección vec
        P1 = P0.Add(
            vec.Multiply(L_perp)
        )

        # P4: punto en el eje original, después de la zona de clash
        P4 = exit_pt.Add(
            self.forward.Multiply(back)
        )

        # P3: perpendicular desde P4 al mismo nivel que P1
        P3 = P4.Add(
            vec.Multiply(L_perp)
        )

        # ── Métricas de taller ────────────────────────────────────
        L_niple      = P1.DistanceTo(P3)
        L_corte      = max(L_niple - 2.0 * deduccion_codo, 0.0)
        L_corte_perp = max(L_perp  - 2.0 * deduccion_codo, 0.0)
        avance_total = P0.DistanceTo(P4)

        print(
            "  L_perp={:.1f}mm  L_niple={:.1f}mm  C_90={:.1f}mm  "
            "L_corte_perp={:.1f}mm  L_corte_central={:.1f}mm".format(
                L_perp       * 304.8,
                L_niple      * 304.8,
                deduccion_codo * 304.8,
                L_corte_perp * 304.8,
                L_corte      * 304.8,
            )
        )

        segments = [

            (P0, P1),   # perpendicular de subida

            (P1, P3),   # tramo central paralelo al eje original

            (P3, P4)    # perpendicular de bajada

        ]

        return {

            "points": [P0, P1, P3, P4],

            "segments": segments,

            "offset_distance": L_perp,

            "P0": P0,
            "P4": P4,

            # ── Datos de taller ──────────────────────────────────
            "angulo_deg":      90,
            "salto_neto_ft":   offset,          # S original (clearance real)
            "L_perp_ft":       L_perp,           # longitud real del tramo que sube/baja
            "L_niple_ft":      L_niple,
            "L_corte_ft":      L_corte,
            "L_corte_perp_ft": L_corte_perp,
            "avance_ft":       avance_total,
            "deduccion_codo":  deduccion_codo,
            # conversión a mm para reporte
            "salto_neto_mm":   offset       * 304.8,
            "L_perp_mm":       L_perp       * 304.8,
            "L_niple_mm":      L_niple      * 304.8,
            "L_corte_mm":      L_corte      * 304.8,
            "L_corte_perp_mm": L_corte_perp * 304.8,
            "avance_mm":       avance_total * 304.8,

        }

    # ========================================================
    # BUILD ÁNGULO
    #
    # CORRECCIÓN 2: La fórmula del avance horizontal era incorrecta.
    # Para un caballito con ángulo α respecto al eje original:
    #   L (niple diagonal) = offset / sin(α)
    #   avance horizontal  = offset / tan(α)   ← CORRECTO
    #
    # El código anterior calculaba horizontal = offset / tan(angle)
    # pero luego colocaba P0 = entry - forward * horizontal
    # y P4 = exit + forward * horizontal, lo que duplicaba el avance
    # total en lugar de medir desde el punto de clash.
    #
    # CORRECCIÓN 3: P1 y P3 deben tener la misma componente en `vec`
    # (mismo offset lateral) para que el tramo central sea paralelo
    # al eje original. En el código anterior P1 usaba entry y
    # P3 usaba exit como base, lo que era correcto, pero la
    # validación de longitud mínima del paralelo modificaba P1 y P3
    # en la dirección forward SIN actualizar P0 y P4, generando
    # segmentos diagonales de longitud incorrecta.
    # ========================================================

    def _build_angle(
        self,
        entry,
        exit_pt,
        vec,
        offset,
        angle_deg,
        deduccion_codo=0.0
    ):

        print(
            "\nGENERANDO ÁNGULO:",
            angle_deg
        )

        # Convertir XYZ de Revit a tuplas para rolling_offset_math
        def to_tuple(xyz_obj):
            return (xyz_obj.X, xyz_obj.Y, xyz_obj.Z)

        def to_xyz(t):
            return XYZ(t[0], t[1], t[2])

        fwd_t  = to_tuple(self.forward)
        vec_t  = to_tuple(vec)
        ent_t  = to_tuple(entry)
        exit_t = to_tuple(exit_pt)

        min_parallel = max(self.mep_diameter * 4, MIN_SEGMENT)

        # Delegar cálculo completo a rolling_offset_math
        # — garantiza ángulo α exacto aunque el paralelo sea pequeño
        bp = build_bypass_points(
            entry       = ent_t,
            exit_pt     = exit_t,
            forward     = fwd_t,
            vec_offset  = vec_t,
            S           = offset,
            alpha_deg   = angle_deg,
            min_parallel= min_parallel,
        )

        P0 = to_xyz(bp["P0"])
        P1 = to_xyz(bp["P1"])
        P3 = to_xyz(bp["P3"])
        P4 = to_xyz(bp["P4"])

        L_diagonal      = bp["L_diagonal"]
        L_niple_central = bp["L_central"]
        horizontal      = bp["avance_A"]

        # Longitudes de corte: L_corte = L - 2C
        L_corte_diag    = max(L_diagonal      - 2.0 * deduccion_codo, 0.0)
        L_corte_central = max(L_niple_central - 2.0 * deduccion_codo, 0.0)

        avance_total = P0.DistanceTo(P4)

        print(
            "  S={:.4f}ft  α={}°  L_diag={:.4f}ft  A={:.4f}ft  "
            "paralelo_orig={:.4f}ft  paralelo_efec={:.4f}ft".format(
                offset, angle_deg, L_diagonal, horizontal,
                bp["depth_orig"], bp["depth_efec"]
            )
        )
        print(
            "  L_diag={:.4f}ft  C={:.4f}ft  L_corte_diag={:.4f}ft  "
            "L_central={:.4f}ft  L_corte_central={:.4f}ft".format(
                L_diagonal, deduccion_codo, L_corte_diag,
                L_niple_central, L_corte_central
            )
        )

        segments = [
            (P0, P1),   # diagonal de entrada
            (P1, P3),   # tramo central paralelo
            (P3, P4)    # diagonal de salida
        ]

        return {

            "points": [P0, P1, P3, P4],

            "segments": segments,

            "offset_distance": offset,

            "P0": P0,
            "P4": P4,

            # ── Datos de taller ──────────────────────────────────
            "angulo_deg":          angle_deg,
            "salto_neto_ft":       offset,
            "L_diagonal_ft":       L_diagonal,
            "L_niple_central_ft":  L_niple_central,
            "avance_ft":           horizontal,
            "avance_total_ft":     avance_total,
            "L_corte_diag_ft":     L_corte_diag,
            "L_corte_central_ft":  L_corte_central,
            "deduccion_codo":      deduccion_codo,
            # conversión a mm para reporte
            "salto_neto_mm":       offset          * 304.8,
            "L_diagonal_mm":       L_diagonal      * 304.8,
            "L_niple_central_mm":  L_niple_central * 304.8,
            "avance_mm":           horizontal      * 304.8,
            "avance_total_mm":     avance_total    * 304.8,
            "L_corte_diag_mm":     L_corte_diag    * 304.8,
            "L_corte_central_mm":  L_corte_central * 304.8,

        }

    # ========================================================
    # VALIDACIÓN FINAL
    #
    # CORRECCIÓN 4: la validación debe verificar TAMBIÉN que
    # la longitud mínima de cada segmento sea > 0 para evitar
    # que Revit falle al crear pipes/conduits de longitud cero.
    # ========================================================

    def validate_bypass(
        self,
        bypass_data
    ):

        print("\nVALIDANDO BYPASS")

        for seg in bypass_data["segments"]:

            # Verificar longitud mínima del segmento
            seg_length = seg[0].DistanceTo(seg[1])
            if seg_length < 0.01:
                print("SEGMENTO DEGENERADO (longitud < 0.01 ft):", seg_length)
                return False

            try:
                line = Line.CreateBound(
                    seg[0],
                    seg[1]
                )
            except Exception as ex:
                print("SEGMENTO INVÁLIDO:", ex)
                return False

            for solid in self.obstacle_solids:

                try:

                    options = (
                        SolidCurveIntersectionOptions()
                    )

                    result = solid.IntersectWithCurve(
                        line,
                        options
                    )

                    if result.SegmentCount > 0:

                        print(
                            "BYPASS INVÁLIDO"
                        )

                        return False

                except:
                    continue

        print("BYPASS VÁLIDO")

        return True
