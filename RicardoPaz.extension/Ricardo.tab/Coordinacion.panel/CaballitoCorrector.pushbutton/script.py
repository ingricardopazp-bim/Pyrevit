# -*- coding: utf-8 -*-
"""
script.py  —  Caballito Corrector
Ricardo.extension · Coordinacion.panel · CaballitoCorrector.pushbutton
Revit 2024 / 2025 · PyRevit

Todos los módulos están en la misma carpeta que este script.

Flujo:
  1. Selección de tubería MEP (Conduit o Pipe)
  2. Selección del elemento obstáculo (modelo local o Revit Link)
  3. Análisis geométrico del clash
  4. Formulario WPF: tipo, ángulo, dirección
  5. Creación del caballito en Revit
"""

import sys
import os
import clr

# ── Revit API ────────────────────────────────────────────────────────
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import (
    Transaction, ElementId, RevitLinkInstance
)
from Autodesk.Revit.DB.Electrical import Conduit
from Autodesk.Revit.DB.Plumbing  import Pipe
from Autodesk.Revit.UI import Selection
import System.Collections.Generic

# ── PyRevit ──────────────────────────────────────────────────────────
from pyrevit import revit, forms, script as pyscript

# ── Módulos locales — misma carpeta que script.py ────────────────────
SCRIPT_DIR = os.path.dirname(__file__)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from clash_geometry  import ClashAnalyzer
from conduit_builder import ConduitBuilder
from pipe_builder    import PipeBuilder
from ui_forms        import show_caballito_form

# ── Variables globales Revit ──────────────────────────────────────────
doc    = revit.doc
uidoc  = revit.uidoc
logger = pyscript.get_logger()


# ════════════════════════════════════════════════════════════════════
#  FILTRO DE SELECCIÓN — solo Conduit y Pipe
# ════════════════════════════════════════════════════════════════════

class MepSelectionFilter(Selection.ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, (Conduit, Pipe))
    def AllowReference(self, reference, point):
        return True


# ════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════

def _tiene_links():
    """Verifica si hay Revit Links activos en el proyecto."""
    from Autodesk.Revit.DB import FilteredElementCollector
    links = FilteredElementCollector(doc)\
        .OfClass(RevitLinkInstance).ToElements()
    return len(links) > 0


def seleccionar_tuberia():
    """
    Paso 1: usuario selecciona el Conduit o Pipe con clash.
    Retorna el elemento o None si cancela.
    """
    try:
        ref = uidoc.Selection.PickObject(
            Selection.ObjectType.Element,
            MepSelectionFilter(),
            "Selecciona el Conduit o Pipe con clash"
        )
        return doc.GetElement(ref.ElementId)
    except Exception:
        return None


def seleccionar_obstaculo():
    """
    Paso 2: usuario selecciona el elemento obstáculo.
    Soporta modelo actual y Revit Links.
    Retorna (element, link_instance_or_None).
    """
    try:
        if _tiene_links():
            ref = uidoc.Selection.PickObject(
                Selection.ObjectType.LinkedElement,
                "Selecciona el elemento obstáculo"
            )
        else:
            ref = uidoc.Selection.PickObject(
                Selection.ObjectType.Element,
                "Selecciona el elemento obstáculo"
            )

        # Distinguir si es elemento de link o del modelo actual
        if ref.LinkedElementId != ElementId.InvalidElementId:
            link_inst = doc.GetElement(ref.ElementId)
            link_doc  = link_inst.GetLinkDocument()
            element   = link_doc.GetElement(ref.LinkedElementId)
            return element, link_inst
        else:
            element = doc.GetElement(ref.ElementId)
            return element, None

    except Exception:
        return None, None


def detectar_tipo(element):
    """Detecta si el elemento MEP es Conduit o Pipe."""
    if isinstance(element, Conduit):
        return 'conduit'
    elif isinstance(element, Pipe):
        return 'pipe'
    return 'unknown'


def obtener_angulo(form_result):
    """Extrae el ángulo numérico del FormResult."""
    if form_result.angle_type == 'variable':
        return form_result.custom_angle
    return float(form_result.angle_type)


def aplicar_caballito(mep_element, bypass_data, mep_type):
    """
    Crea los segmentos del caballito dentro de una Transaction.
    Retorna lista de ElementId creados.
    """
    with Transaction(doc, "Caballito Corrector — Desvío MEP") as t:
        t.Start()
        try:
            if mep_type == 'conduit':
                builder = ConduitBuilder(doc, bypass_data, mep_element)
            else:
                builder = PipeBuilder(doc, bypass_data, mep_element)

            created_ids = builder.build()
            t.Commit()
            return created_ids

        except Exception as e:
            t.RollBack()
            logger.error("Error en Transaction: {}".format(e))
            raise


# ════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════

def main():

    # ── 1. Seleccionar tubería MEP ───────────────────────────────────
    mep_element = seleccionar_tuberia()
    if mep_element is None:
        forms.alert("Operación cancelada.", title="Caballito Corrector")
        return

    # ── 2. Seleccionar obstáculo ─────────────────────────────────────
    obstacle, link_instance = seleccionar_obstaculo()
    if obstacle is None:
        forms.alert("Operación cancelada.", title="Caballito Corrector")
        return

    # ── 3. Análisis geométrico ───────────────────────────────────────
    try:
        analyzer = ClashAnalyzer(doc, mep_element, obstacle, link_instance)
        clash_found = analyzer.analyze()
    except Exception as e:
        forms.alert(
            "Error analizando el clash:\n\n{}".format(e),
            title="Error de análisis", warn_icon=True
        )
        logger.error("ClashAnalyzer error: {}".format(e))
        return

    if not clash_found:
        forms.alert(
            "No se detectó intersección geométrica entre los elementos.\n\n"
            "Verifica que los elementos realmente se superpongan en el modelo.",
            title="Sin clash detectado", warn_icon=True
        )
        return

    # ── 4. Formulario WPF ────────────────────────────────────────────
    result = show_caballito_form(analyzer=analyzer)

    if not result.accepted:
        forms.alert("Operación cancelada.", title="Caballito Corrector")
        return

    # ── 5. Resolver tipo de elemento ─────────────────────────────────
    mep_type = result.element_type
    if mep_type == 'auto':
        mep_type = detectar_tipo(mep_element)
        if mep_type == 'unknown':
            forms.alert(
                "No se pudo detectar si el elemento es Conduit o Pipe.\n"
                "Selecciona el tipo manualmente en el formulario.",
                title="Tipo desconocido", warn_icon=True
            )
            return

    # ── 6. Resolver dirección ────────────────────────────────────────
    direction = result.direction
    if direction == 'auto':
        direction = analyzer.recommended
        if direction is None:
            forms.alert(
                "El addin no pudo calcular una dirección recomendada.\n"
                "Ejecuta de nuevo y selecciona la dirección manualmente.",
                title="Sin recomendación", warn_icon=True
            )
            return

    # ── 7. Calcular geometría del caballito ──────────────────────────
    angulo = obtener_angulo(result)
    try:
        # deduccion_codo: si el formulario lo expone (mm), se usa ese valor.
        # Si no existe, se pasa None y clash_geometry lo calcula
        # automáticamente desde las tablas ANSI/ASTM.
        deduccion_codo_ft = None
        if hasattr(result, 'deduccion_codo') and result.deduccion_codo:
            deduccion_codo_ft = float(result.deduccion_codo) / 304.8

        bypass_data = analyzer.get_bypass_points(
            direction_name  = direction,
            angle_deg       = angulo,
            offset_distance = result.custom_offset,
            deduccion_codo  = deduccion_codo_ft   # None → automático
        )
    except Exception as e:
        forms.alert(
            "Error calculando la geometría del desvío:\n\n{}".format(e),
            title="Error geométrico", warn_icon=True
        )
        logger.error("get_bypass_points error: {}".format(e))
        return

    # ── 8. Crear en Revit ────────────────────────────────────────────
    try:
        created_ids = aplicar_caballito(mep_element, bypass_data, mep_type)

        # Seleccionar elementos creados en el modelo
        id_list = System.Collections.Generic.List[ElementId]()
        for eid in created_ids:
            id_list.Add(eid)
        uidoc.Selection.SetElementIds(id_list)



    except Exception as e:
        forms.alert(
            "Error al crear los segmentos en Revit:\n\n{}".format(e),
            title="Error Revit", warn_icon=True
        )
        logger.error("aplicar_caballito error: {}".format(e))


# ════════════════════════════════════════════════════════════════════
main()
