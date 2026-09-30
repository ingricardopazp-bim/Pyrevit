# -*- coding: utf-8 -*-
"""
config.py — Parámetros globales del motor de interferencias.
Centraliza TODAS las constantes, categorías y exclusiones.

IMPORTANTE: Todos los accesos a BuiltInCategory usan getattr defensivo
para evitar AttributeError en versiones de Revit donde un BIC fue
renombrado o eliminado (p.ej. OST_ReferencePlanes → OST_CLines en Revit 2024+).
"""
from __future__ import absolute_import

try:
    from Autodesk.Revit.DB import BuiltInCategory
except Exception:
    BuiltInCategory = None


# ── Tolerancias geométricas ────────────────────────────────────────────────────
DEFAULT_MIN_VOLUME_FT3 = 0.00005   # ≈ 0.014 cm³ — evita artefactos numéricos
DEFAULT_MAX_RESULTS    = 100


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORÍAS EXCLUIDAS — nunca aparecen como participante en un choque
# ─────────────────────────────────────────────────────────────────────────────
EXCLUDED_CATEGORY_NAMES = {
    '<Imported in Families>',
    'Imports in Families',
    'Model Groups',
    'Coordination Model',
    'Point Clouds',
}

EXCLUDED_CATEGORIES = set()

# Nombres de BIC a excluir — se resuelven con getattr defensivo para evitar
# AttributeError en versiones de Revit donde el nombre cambió o no existe.
# OST_ReferencePlanes fue renombrado a OST_CLines en Revit 2024+.
_EXCLUDED_BIC_NAMES = [
    # Vistas y cámaras
    'OST_Cameras',
    'OST_Views',
    'OST_Viewports',
    # Anotaciones 2D
    'OST_TextNotes',
    'OST_Dimensions',
    'OST_Tags',
    'OST_KeynoteTags',
    'OST_SpotSlopes',
    'OST_SpotElevations',
    'OST_SpotCoordinates',
    'OST_RasterImages',
    'OST_Lines',
    'OST_SketchLines',
    'OST_WeakDims',
    # Grids, ejes, niveles
    'OST_Grids',
    'OST_Levels',
    'OST_ReferencePlanes',   # Revit < 2024
    'OST_CLines',            # Revit 2024+ (renombrado de OST_ReferencePlanes)
    'OST_ReferenceLines',
    # Masa, habitaciones y espacios (no tienen sólido real)
    'OST_Rooms',
    'OST_Areas',
    'OST_MEPSpaces',
    'OST_Mass',
    # Importaciones DWG / DXF
    'OST_ImportObjectStyles',
    'OST_RvtLinks',
    # Detalles
    'OST_DetailComponents',
    'OST_FilledRegion',
    'OST_InsulationLines',
]

if BuiltInCategory is not None:
    for _bic_name in _EXCLUDED_BIC_NAMES:
        try:
            EXCLUDED_CATEGORIES.add(getattr(BuiltInCategory, _bic_name))
        except AttributeError:
            pass  # BIC no disponible en esta versión de Revit — se ignora

# Conjunto de IntegerValues para lookup O(1) en el filtrado
EXCLUDED_CATEGORY_IDS = (
    {int(bic) for bic in EXCLUDED_CATEGORIES}
    if EXCLUDED_CATEGORIES else set()
)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORÍAS ACTIVAS (participantes en el choque)
# ─────────────────────────────────────────────────────────────────────────────
_ACTIVE_BIC_NAMES = [
    # MEP — Mecánica
    'OST_DuctCurves', 'OST_DuctFitting', 'OST_DuctAccessory',
    'OST_FlexDuctCurves', 'OST_MechanicalEquipment',
    # MEP — Hidráulica
    'OST_PipeCurves', 'OST_PipeFitting', 'OST_PipeAccessory',
    'OST_FlexPipeCurves', 'OST_PlumbingFixtures',
    # MEP — Eléctrica
    'OST_CableTray', 'OST_CableTrayFitting',
    'OST_Conduit', 'OST_ConduitFitting',
    'OST_ElectricalEquipment', 'OST_ElectricalFixtures',
    # Estructura
    'OST_StructuralFraming', 'OST_StructuralColumns',
    'OST_StructuralFoundation', 'OST_StructuralStiffener',
    # Arquitectura
    'OST_Walls', 'OST_Floors', 'OST_Ceilings', 'OST_Roofs',
    'OST_Stairs', 'OST_Ramps', 'OST_Doors', 'OST_Windows',
    # Genéricos
    'OST_GenericModel',
]


def default_categories():
    """
    Devuelve la lista de BuiltInCategory para el escaneo.
    Usa getattr defensivo para evitar AttributeError en cualquier versión de Revit.
    """
    if BuiltInCategory is None:
        return []
    result = []
    for name in _ACTIVE_BIC_NAMES:
        try:
            result.append(getattr(BuiltInCategory, name))
        except AttributeError:
            pass
    return result
