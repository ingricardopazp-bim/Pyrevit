# -*- coding: utf-8 -*-
"""
rolling_offset_math.py
======================
Librería matemática pura para rolling offsets y clash resolution en piping MEP.
Sin dependencias de Revit API — usable en cualquier contexto Python.

FÓRMULAS IMPLEMENTADAS
─────────────────────────────────────────────────────────────────
  §1  Distancia espacial 3D        L = sqrt(X² + Y² + Z²)
  §2  Travel del offset            T = S / sin(α)
  §3  Avance / Spacing             A = S / tan(α)
  §4  Resultante horizontal        R = sqrt(X² + Y²)
  §5  Rolling offset combinado     S_roll = sqrt(lateral² + vertical²)
  §6  Ángulo del offset            θ = atan2(Y, X)
  §7  Vector dirección normalizado  d̂ = (P2-P1) / |P2-P1|
  §8  Producto cruz                 n = a × b
  §9  Producto punto / ángulo       cos θ = (a·b) / (|a||b|)
  §10 Punto desplazado              P_new = P + n̂ · d
  §11 Distancia punto-línea 3D
  §12 Offset mínimo requerido       S_min = R_pipe + R_obstacle + clearance
  §13 Longitud total rerouting      L_total = Σ Lᵢ
  §14 Bounding box collision AABB
  §15 Forma paramétrica de línea    P = P0 + t·d
  §16 Sistema de referencia local   (forward, right, up)
  §17 Proyección de punto sobre eje
  §18 Rolling offset 3D completo   (S, T, A desde X, Y, Z y α)

Autor: Ricardo Paz  |  v4  2025
"""

import math


# ═══════════════════════════════════════════════════════════════
# §1 — DISTANCIA ESPACIAL 3D
# ═══════════════════════════════════════════════════════════════

def distance_3d(dx, dy, dz):
    """
    L = sqrt(X² + Y² + Z²)

    Longitud real del tramo inclinado en el espacio.
    Base de todo rolling offset.

    Parámetros
    ----------
    dx : float  desplazamiento lateral   (X)
    dy : float  elevación vertical       (Y)
    dz : float  avance longitudinal      (Z)

    Retorna L en las mismas unidades que la entrada.

    Ejemplo
    -------
    >>> distance_3d(500, 300, 1200)
    1322.876...   # mm
    """
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def distance_between_points(p1, p2):
    """
    Distancia euclidiana entre dos puntos 3D (tuplas o listas [x, y, z]).

    >>> distance_between_points([0,0,0], [3,4,0])
    5.0
    """
    return distance_3d(p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2])


# ═══════════════════════════════════════════════════════════════
# §2 — TRAVEL DEL OFFSET
# ═══════════════════════════════════════════════════════════════

def travel(offset, angle_deg):
    """
    T = offset / sin(α)

    Longitud real del niple diagonal (eje a eje).
    Equivalente a L = S / sin(α) en la notación de caballitos.

    Factores rápidos de campo:
      22.5° → × 2.613
      30°   → × 2.000
      45°   → × 1.414
      60°   → × 1.155
      90°   → × 1.000

    >>> travel(400, 45)
    565.68...
    """
    if angle_deg <= 0 or angle_deg >= 180:
        raise ValueError("angle_deg debe estar en (0, 180)")
    return offset / math.sin(math.radians(angle_deg))


TRAVEL_FACTORS = {
    11.25: 1.0 / math.sin(math.radians(11.25)),
    22.5:  1.0 / math.sin(math.radians(22.5)),
    30.0:  2.0,
    45.0:  math.sqrt(2),   # 1.41421...
    60.0:  1.0 / math.sin(math.radians(60)),
    90.0:  1.0,
}


# ═══════════════════════════════════════════════════════════════
# §3 — AVANCE / SPACING
# ═══════════════════════════════════════════════════════════════

def spacing(offset, angle_deg):
    """
    A = offset / tan(α)

    Distancia longitudinal que consume cada diagonal.
    A 45°: spacing = offset (caso especial, tan 45° = 1).
    A 30°: spacing = offset × 1.732.

    >>> spacing(400, 45)
    400.0
    >>> spacing(400, 30)
    692.8...
    """
    if angle_deg <= 0 or angle_deg >= 90:
        raise ValueError("angle_deg debe estar en (0, 90) para un caballito")
    return offset / math.tan(math.radians(angle_deg))


# ═══════════════════════════════════════════════════════════════
# §4 — RESULTANTE HORIZONTAL / ROLLING OFFSET COMBINADO
# ═══════════════════════════════════════════════════════════════

def resultante_horizontal(dx, dy):
    """
    R = sqrt(X² + Y²)

    Offset combinado cuando hay desplazamiento lateral Y vertical.
    El resultado se usa como S en las fórmulas de travel y spacing.

    >>> resultante_horizontal(300, 400)
    500.0
    """
    return math.sqrt(dx * dx + dy * dy)


def rolling_offset_3d(lateral, vertical, longitudinal, angle_deg):
    """
    Rolling offset completo cuando el desplazamiento tiene componente
    lateral Y vertical simultáneamente.

    Pasos:
      1. S_roll = sqrt(lateral² + vertical²)   — offset combinado
      2. T      = S_roll / sin(α)              — travel (niple diagonal)
      3. A      = S_roll / tan(α)              — avance longitudinal

    Retorna dict con todos los valores.

    >>> rolling_offset_3d(300, 400, 0, 45)
    {'S_roll': 500.0, 'travel': 707.1..., 'spacing': 500.0, 'angle_roll': 53.13...}
    """
    S_roll = resultante_horizontal(lateral, vertical)
    T      = travel(S_roll, angle_deg)
    A      = spacing(S_roll, angle_deg)
    # Ángulo de inclinación del plano del rolling offset respecto a la horizontal
    angle_roll = math.degrees(math.atan2(vertical, lateral)) if lateral != 0 else 90.0

    return {
        "S_roll":     S_roll,
        "travel":     T,
        "spacing":    A,
        "angle_roll": angle_roll,
        # longitud espacial total si se incluye avance longitudinal dado
        "L_3d":       distance_3d(lateral, vertical, longitudinal),
    }


# ═══════════════════════════════════════════════════════════════
# §5 — ÁNGULO DEL OFFSET
# ═══════════════════════════════════════════════════════════════

def offset_angle_deg(y, x):
    """
    θ = atan2(Y, X)  en grados

    Ángulo de inclinación del offset respecto al eje horizontal.
    Útil para orientar fittings y calcular rotación de codos.

    >>> offset_angle_deg(400, 400)
    45.0
    >>> offset_angle_deg(300, 0)
    90.0
    """
    return math.degrees(math.atan2(y, x))


# ═══════════════════════════════════════════════════════════════
# §6 & §7 — VECTORES: DIRECCIÓN, NORMALIZACIÓN, MÓDULO
# ═══════════════════════════════════════════════════════════════

def vec_sub(p2, p1):
    """d = P2 - P1  (vector dirección crudo)"""
    return (p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2])


def vec_length(v):
    """
    |v| = sqrt(x² + y² + z²)

    Módulo del vector. Igual a distance_3d pero acepta tupla.
    """
    return math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])


def vec_normalize(v):
    """
    d̂ = v / |v|

    Vector unitario. Fundamental para desplazar puntos en una
    dirección dada independientemente de la escala.

    Retorna (0,0,0) si el vector es degenerado (|v| < 1e-9).

    >>> vec_normalize((3, 4, 0))
    (0.6, 0.8, 0.0)
    """
    length = vec_length(v)
    if length < 1e-9:
        return (0.0, 0.0, 0.0)
    return (v[0]/length, v[1]/length, v[2]/length)


def direction_vector(p1, p2):
    """
    Vector dirección normalizado de P1 a P2.
    Wrapper de conveniencia: vec_normalize(vec_sub(p2, p1)).
    """
    return vec_normalize(vec_sub(p2, p1))


# ═══════════════════════════════════════════════════════════════
# §8 — PRODUCTO CRUZ
# ═══════════════════════════════════════════════════════════════

def cross(a, b):
    """
    n = a × b

    Vector perpendicular al plano definido por a y b.
    Resultado sin normalizar — normalizar con vec_normalize si se necesita unitario.

    Usos clave en piping:
      • Obtener dirección lateral desde forward y up
      • Calcular plano de escape para el rerouting
      • Generar el sistema local (forward, right, up)

    >>> cross((1,0,0), (0,1,0))
    (0.0, 0.0, 1.0)
    """
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def perpendicular_direction(forward, world_up=(0.0, 0.0, 1.0)):
    """
    Calcula el vector 'right' perpendicular al eje de la tubería.

    Lógica estándar usada en Revit y motores 3D:
      right = normalize(forward × world_up)
      up    = normalize(right × forward)

    Si forward es casi paralelo a world_up (tubería vertical),
    usa world_up = (1,0,0) como alternativa.

    Retorna (right, up) — ambos normalizados.
    """
    fwd = vec_normalize(forward)
    dot = abs(fwd[0]*world_up[0] + fwd[1]*world_up[1] + fwd[2]*world_up[2])
    if dot > 0.95:
        world_up = (1.0, 0.0, 0.0)

    right = vec_normalize(cross(fwd, world_up))
    up    = vec_normalize(cross(right, fwd))
    return right, up


# ═══════════════════════════════════════════════════════════════
# §9 — PRODUCTO PUNTO / ÁNGULO ENTRE VECTORES
# ═══════════════════════════════════════════════════════════════

def dot(a, b):
    """a · b = ax*bx + ay*by + az*bz"""
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def angle_between_deg(a, b):
    """
    θ = acos( (a·b) / (|a||b|) )  en grados

    Ángulo real entre dos vectores.
    Retorna 0 si alguno es degenerado.

    Útil para:
      • Detectar si dos pipes son paralelos (θ ≈ 0° o 180°)
      • Clasificar dirección del obstáculo
      • Orientar accesorios

    >>> angle_between_deg((1,0,0), (0,1,0))
    90.0
    >>> angle_between_deg((1,0,0), (1,0,0))
    0.0
    """
    la = vec_length(a)
    lb = vec_length(b)
    if la < 1e-9 or lb < 1e-9:
        return 0.0
    cosine = max(-1.0, min(1.0, dot(a, b) / (la * lb)))
    return math.degrees(math.acos(cosine))


def are_parallel(a, b, tol_deg=1.0):
    """True si los vectores son paralelos (dentro de tol_deg grados)."""
    angle = angle_between_deg(a, b)
    return angle < tol_deg or angle > (180.0 - tol_deg)


def are_perpendicular(a, b, tol_deg=1.0):
    """True si los vectores son perpendiculares."""
    return abs(angle_between_deg(a, b) - 90.0) < tol_deg


# ═══════════════════════════════════════════════════════════════
# §10 — PUNTO DESPLAZADO
# ═══════════════════════════════════════════════════════════════

def move_point(p, normal, distance):
    """
    P_new = P + n̂ · d

    Mueve el punto P en la dirección normal (normalizada)
    una distancia d.

    La fórmula más usada en rerouting automático:
    desplaza la tubería perpendicular al eje para evitar el clash.

    >>> move_point((0,0,0), (0,1,0), 500)
    (0.0, 500.0, 0.0)
    """
    n = vec_normalize(normal)
    return (
        p[0] + n[0] * distance,
        p[1] + n[1] * distance,
        p[2] + n[2] * distance,
    )


def move_point_raw(p, direction_normalized, distance):
    """
    Igual que move_point pero asume que direction ya es unitario.
    Más rápido en loops donde la dirección no cambia.
    """
    return (
        p[0] + direction_normalized[0] * distance,
        p[1] + direction_normalized[1] * distance,
        p[2] + direction_normalized[2] * distance,
    )


# ═══════════════════════════════════════════════════════════════
# §11 — DISTANCIA PUNTO-LÍNEA 3D
# ═══════════════════════════════════════════════════════════════

def distance_point_to_line_3d(point, line_origin, line_direction):
    """
    Distancia mínima de un punto a una línea infinita en 3D.

    Fórmula vectorial:
      d = |(P - P0) × d̂| / |d̂|     (con d̂ ya normalizado → |d̂|=1)
      d = |(P - P0) × d̂|

    Muy útil para:
      • Clearance real entre eje de pipe y cara de obstáculo
      • Detección de proximidad sin intersección geométrica
      • Validación de separación entre sistemas MEP

    Parámetros
    ----------
    point          : (x,y,z) — punto a medir
    line_origin    : (x,y,z) — punto sobre la línea
    line_direction : (x,y,z) — dirección de la línea (no requiere normalizar)

    >>> distance_point_to_line_3d((0,5,0), (0,0,0), (1,0,0))
    5.0
    """
    d_hat  = vec_normalize(line_direction)
    w      = vec_sub(point, line_origin)
    cross_ = cross(w, d_hat)
    return vec_length(cross_)


def clearance_between_pipes(axis1_p0, axis1_p1, axis2_p0, axis2_p1,
                             r1, r2):
    """
    Clearance real entre dos tuberías paralelas o cruzadas.

    Calcula la distancia eje-a-eje y resta los radios exteriores.
    Un resultado negativo indica penetración (clash).

    Retorna:
      {'eje_a_eje': float, 'clearance': float, 'clash': bool}
    """
    d_hat1  = vec_normalize(vec_sub(axis1_p1, axis1_p0))
    dist_ee = distance_point_to_line_3d(axis2_p0, axis1_p0, d_hat1)
    clearance = dist_ee - r1 - r2
    return {
        "eje_a_eje": dist_ee,
        "clearance":  clearance,
        "clash":      clearance < 0.0,
    }


# ═══════════════════════════════════════════════════════════════
# §12 — OFFSET MÍNIMO REQUERIDO
# ═══════════════════════════════════════════════════════════════

def offset_minimo(r_pipe, r_obstacle, clearance):
    """
    S_min = R_pipe + R_obstacle + clearance

    Desplazamiento mínimo que necesita el eje de la tubería para
    que su superficie exterior quede a 'clearance' de distancia
    de la superficie del obstáculo.

    Equivale a: S = D + H + R1  donde:
      D ≈ distancia eje → cara obstáculo  (R_obstacle para cilindros)
      H = clearance
      R1 = r_pipe

    >>> offset_minimo(25, 100, 25)
    150.0
    """
    return r_pipe + r_obstacle + clearance


# ═══════════════════════════════════════════════════════════════
# §13 — LONGITUD TOTAL DEL REROUTING
# ═══════════════════════════════════════════════════════════════

def longitud_total(segments):
    """
    L_total = Σ |P_{i+1} - P_i|

    Suma de longitudes de todos los segmentos del rerouting.
    Útil para comparar rutas alternativas y minimizar material.

    Parámetros
    ----------
    segments : lista de tuplas [(p0, p1), (p1, p2), ...]
               donde cada punto es (x, y, z)

    >>> longitud_total([((0,0,0),(0,0,100)), ((0,0,100),(0,100,100))])
    200.0
    """
    return sum(distance_between_points(p0, p1) for p0, p1 in segments)


def mejor_ruta(rutas):
    """
    Dado un dict {nombre: lista_de_segmentos}, retorna el nombre
    de la ruta con menor longitud total.

    >>> mejor_ruta({'arriba': [((0,0,0),(0,200,0))],
    ...             'derecha': [((0,0,0),(100,0,0))]})
    'derecha'
    """
    return min(rutas, key=lambda name: longitud_total(rutas[name]))


# ═══════════════════════════════════════════════════════════════
# §14 — BOUNDING BOX COLLISION (AABB)
# ═══════════════════════════════════════════════════════════════

def aabb_overlap(min1, max1, min2, max2):
    """
    Detección rápida de colisión entre dos bounding boxes alineadas
    con los ejes (Axis-Aligned Bounding Boxes).

    Condición de colisión en cada eje:
      min1 ≤ max2  AND  max1 ≥ min2

    Parámetros
    ----------
    min1, max1 : (x,y,z) — esquinas del BB del elemento 1
    min2, max2 : (x,y,z) — esquinas del BB del elemento 2

    Retorna True si los BBs se solapan (posible clash).
    Primer filtro antes de intersección exacta con sólidos.

    >>> aabb_overlap((0,0,0),(2,2,2),(1,1,1),(3,3,3))
    True
    >>> aabb_overlap((0,0,0),(1,1,1),(2,2,2),(3,3,3))
    False
    """
    for i in range(3):
        if min1[i] > max2[i] or max1[i] < min2[i]:
            return False
    return True


def aabb_expand(bb_min, bb_max, margin):
    """
    Expande un bounding box en todas las direcciones por 'margin'.
    Útil para detección de proximidad (clearance check).
    """
    return (
        (bb_min[0]-margin, bb_min[1]-margin, bb_min[2]-margin),
        (bb_max[0]+margin, bb_max[1]+margin, bb_max[2]+margin),
    )


# ═══════════════════════════════════════════════════════════════
# §15 — FORMA PARAMÉTRICA DE LÍNEA
# ═══════════════════════════════════════════════════════════════

def line_point(p0, direction, t):
    """
    P(t) = P0 + t · d̂

    Retorna el punto a distancia t sobre la línea.

    Usos:
      • Subdividir un segmento
      • Encontrar punto de intersección
      • Avanzar a lo largo de un pipe

    >>> line_point((0,0,0), (1,0,0), 5)
    (5.0, 0.0, 0.0)
    """
    d = vec_normalize(direction)
    return move_point_raw(p0, d, t)


def project_point_on_line(point, line_p0, line_p1):
    """
    Proyecta un punto sobre una línea finita (P0→P1).

    Retorna:
      {'projected': (x,y,z), 't': float (0=P0, 1=P1), 'distance': float}

    t < 0 → proyección antes de P0
    t > 1 → proyección después de P1
    0 ≤ t ≤ 1 → proyección dentro del segmento

    Muy útil para determinar en qué parte del pipe ocurre el clash
    y para calcular dónde cortar el tramo original.
    """
    d   = vec_sub(line_p1, line_p0)
    L   = vec_length(d)
    if L < 1e-9:
        return {"projected": line_p0, "t": 0.0, "distance": distance_between_points(point, line_p0)}

    d_hat = (d[0]/L, d[1]/L, d[2]/L)
    w     = vec_sub(point, line_p0)
    t_abs = dot(w, d_hat)             # distancia desde P0 en unidades reales
    t_norm = t_abs / L                # parámetrico [0,1]

    projected = move_point_raw(line_p0, d_hat, t_abs)
    dist      = distance_between_points(point, projected)
    return {"projected": projected, "t": t_norm, "distance": dist}


# ═══════════════════════════════════════════════════════════════
# §16 — SISTEMA DE REFERENCIA LOCAL (forward, right, up)
# ═══════════════════════════════════════════════════════════════

def local_frame(p1, p2, world_up=(0.0, 0.0, 1.0)):
    """
    Genera el sistema de referencia local de una tubería.

    forward = dirección normalizada P1 → P2
    right   = forward × world_up   (normalizado)
    up      = right × forward       (normalizado)

    Este sistema es exactamente lo que usa Revit internamente para
    posicionar accesorios y calcular offsets laterales/verticales.

    Retorna dict con los tres ejes unitarios.
    """
    fwd   = direction_vector(p1, p2)
    right, up = perpendicular_direction(fwd, world_up)
    return {"forward": fwd, "right": right, "up": up}


# ═══════════════════════════════════════════════════════════════
# §17 — PARÁMETROS COMPLETOS DEL CABALLITO (BYPASS)
# ═══════════════════════════════════════════════════════════════

def caballito_params(S, alpha_deg, C_mm=None, nps_in=None):
    """
    Calcula todos los parámetros de un caballito dado el Salto Neto S
    y el ángulo α de los codos.

    Fórmulas norma de obra:
      L (eje-a-eje)  = S / sin(α)
      A (avance)     = S / tan(α)
      L_corte        = L - 2C
      C (B16.9 LR)   = 1.5 × NPS × 25.4 × tan(α/2)   [mm]

    Parámetros
    ----------
    S         : float — Salto Neto en mm
    alpha_deg : float — ángulo del codo (45, 30, 60, 90, etc.)
    C_mm      : float — deducción centro-a-cara en mm. Si None se calcula
                        con la fórmula ASME B16.9 LR (requiere nps_in).
    nps_in    : float — diámetro nominal en pulgadas (solo si C_mm=None)

    Retorna dict con todos los valores en mm y el L_corte listo para cortar.
    """
    a_rad = math.radians(alpha_deg)

    L = S / math.sin(a_rad)     # longitud eje-a-eje de la diagonal
    A = S / math.tan(a_rad)     # avance longitudinal por diagonal

    # Deducción C
    if C_mm is None:
        if nps_in is None:
            raise ValueError("Se requiere nps_in cuando C_mm=None")
        C_90 = 1.5 * nps_in * 25.4                  # ASME B16.9 LR
        C_mm = C_90 * math.tan(math.radians(alpha_deg / 2.0))

    L_corte = max(L - 2.0 * C_mm, 0.0)

    return {
        "S_mm":      S,
        "alpha_deg": alpha_deg,
        "L_mm":      L,        # longitud eje-a-eje (niple diagonal)
        "A_mm":      A,        # avance por diagonal
        "C_mm":      C_mm,     # deducción centro-a-cara
        "L_corte_mm": L_corte, # longitud física de corte con segueta
        # factores rápidos de campo
        "factor_L":  1.0 / math.sin(a_rad),
        "factor_A":  1.0 / math.tan(a_rad) if alpha_deg < 90 else 0.0,
    }


def salto_neto(D, H, R1):
    """
    S = D + H + R1

    D  : distancia eje pipe → cara más lejana del obstáculo (en dirección del desvío)
    H  : holgura libre deseada entre superficies
    R1 : radio exterior de la tubería propia (incluyendo aislamiento)
    """
    return D + H + R1


# ═══════════════════════════════════════════════════════════════
# §18 — BUILDER DE PUNTOS DEL CABALLITO
# ═══════════════════════════════════════════════════════════════

def build_bypass_points(entry, exit_pt, forward, vec_offset, S, alpha_deg, min_parallel=None):
    """
    Calcula los 4 puntos del caballito (P0, P1, P3, P4) garantizando
    que el ángulo α es exacto aunque el tramo paralelo sea muy corto.

    Estrategia (corrección del bug del ajuste de mínimo):
      1. Calcular A = S / tan(α)
      2. Si la profundidad del obstáculo < min_parallel, expandir
         entry y exit_pt sobre el eje forward ANTES de calcular P0/P4.
      3. SIEMPRE:  P0 = entry_eff - forward*A
                   P1 = entry_eff + vec_offset*S
                   P3 = exit_eff  + vec_offset*S
                   P4 = exit_eff  + forward*A

    Parámetros
    ----------
    entry, exit_pt  : (x,y,z) — puntos de entrada/salida del clash sobre el eje
    forward         : (x,y,z) — dirección normalizada de la tubería
    vec_offset      : (x,y,z) — dirección normalizada del desvío
    S               : float   — Salto Neto (en las unidades de los puntos)
    alpha_deg       : float   — ángulo del codo
    min_parallel    : float   — longitud mínima del tramo central (None = sin mínimo)

    Retorna dict con P0, P1, P3, P4 y métricas de taller.
    """
    a_rad = math.radians(alpha_deg)
    L_diag = S / math.sin(a_rad)
    A      = S / math.tan(a_rad) if alpha_deg < 90.0 else 0.0

    fwd = vec_normalize(forward)
    vec = vec_normalize(vec_offset)

    depth = distance_between_points(entry, exit_pt)

    # Expandir entry/exit si el paralelo es insuficiente
    if min_parallel is not None and depth < min_parallel:
        extra = (min_parallel - depth) / 2.0
        entry_eff = move_point_raw(entry,   tuple(-x for x in fwd), extra)
        exit_eff  = move_point_raw(exit_pt, fwd, extra)
    else:
        entry_eff = entry
        exit_eff  = exit_pt

    # Calcular los 4 puntos — ángulo garantizado por construcción
    P0 = move_point_raw(entry_eff, tuple(-x for x in fwd), A)
    P1 = move_point_raw(entry_eff, vec, S)
    P3 = move_point_raw(exit_eff,  vec, S)
    P4 = move_point_raw(exit_eff,  fwd, A)

    L_central = distance_between_points(P1, P3)

    return {
        "P0": P0, "P1": P1, "P3": P3, "P4": P4,
        "segments": [(P0, P1), (P1, P3), (P3, P4)],
        "L_diagonal":  L_diag,
        "L_central":   L_central,
        "avance_A":    A,
        "depth_orig":  depth,
        "depth_efec":  distance_between_points(entry_eff, exit_eff),
    }


# ═══════════════════════════════════════════════════════════════
# SELF-TEST  (ejecutar con: python rolling_offset_math.py)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    ok = True

    def check(name, got, expected, tol=0.01):
        global ok
        if abs(got - expected) > tol:
            print(u"FAIL  {}: got={:.6f}  expected={:.6f}".format(name, got, expected))
            ok = False
        else:
            print(u"OK    {}: {:.4f}".format(name, got))

    print("\n=== rolling_offset_math self-test ===\n")

    # §1 distancia — sqrt(500²+300²+1200²) = 1334.166
    check("distance_3d(500,300,1200)",
          distance_3d(500, 300, 1200), 1334.166, tol=0.1)

    # §2 travel
    check("travel(400, 45)",
          travel(400, 45), 565.685, tol=0.01)
    check("travel(400, 30)",
          travel(400, 30), 800.0, tol=0.01)

    # §3 spacing
    check("spacing(400, 45)", spacing(400, 45), 400.0, tol=0.01)
    check("spacing(400, 30)", spacing(400, 30), 692.82, tol=0.01)

    # §4 resultante
    check("resultante_horizontal(300,400)", resultante_horizontal(300, 400), 500.0)

    # §7 normalize
    n = vec_normalize((3, 4, 0))
    check("normalize(3,4,0).x", n[0], 0.6)
    check("normalize(3,4,0).y", n[1], 0.8)

    # §8 cross
    c = cross((1,0,0),(0,1,0))
    check("cross(X,Y).z", c[2], 1.0)

    # §9 angle
    check("angle(X,Y)", angle_between_deg((1,0,0),(0,1,0)), 90.0)
    check("angle(X,X)", angle_between_deg((1,0,0),(1,0,0)), 0.0)

    # §11 dist point-line
    check("dist_pt_line 5", distance_point_to_line_3d((0,5,0),(0,0,0),(1,0,0)), 5.0)

    # §14 aabb
    assert aabb_overlap((0,0,0),(2,2,2),(1,1,1),(3,3,3)) == True,  "aabb overlap fail"
    assert aabb_overlap((0,0,0),(1,1,1),(2,2,2),(3,3,3)) == False, "aabb no-overlap fail"
    print("OK    aabb_overlap")

    # §17 caballito_params con valores reales del log
    # S=218.3mm, α=45°, NPS=6" → C_90=228.6mm, C_45=94.7mm
    p = caballito_params(218.3, 45.0, nps_in=6.0)
    check("caballito L_mm(S=218.3,α=45)",
          p["L_mm"], 218.3 * math.sqrt(2), tol=0.1)
    check("caballito A_mm(S=218.3,α=45)",
          p["A_mm"], 218.3, tol=0.1)

    # §18 build_bypass_points — verificar ángulo exacto
    import math as _m
    fwd = (1.0, 0.0, 0.0)
    vec = (0.0, 0.0, 1.0)
    bp  = build_bypass_points(
        entry=(0.0, 0.0, 0.0),
        exit_pt=(0.5534, 0.0, 0.0),
        forward=fwd,
        vec_offset=vec,
        S=0.7161,
        alpha_deg=45.0,
        min_parallel=2.2083
    )
    P0, P1 = bp["P0"], bp["P1"]
    d01 = (P1[0]-P0[0], P1[1]-P0[1], P1[2]-P0[2])
    ang = angle_between_deg(d01, fwd)
    check("angle P0->P1 (should be 45°)", ang, 45.0, tol=0.01)
    check("L_diagonal P0->P1", bp["L_diagonal"], 0.7161/_m.sin(_m.radians(45)), tol=0.001)
    check("L_central >= min_parallel", bp["L_central"], 2.2083, tol=0.001)

    print("\n{}\n".format("TODOS LOS TESTS PASARON" if ok else "HAY FALLOS — revisar arriba"))
    sys.exit(0 if ok else 1)
