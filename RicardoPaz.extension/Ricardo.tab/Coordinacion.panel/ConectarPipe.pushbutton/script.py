# -*- coding: utf-8 -*-
"""Conecta (o solo mueve) conectores de tuberia/ducto, de forma ciclica.

Al iniciar, pregunta UNA sola vez si se desea:
  - Conectar: mover el conector seleccionado hasta el fijo y unirlos (ConnectTo)
  - Solo mover: desplazar el conector seleccionado hasta el fijo, sin conectarlos

Luego repite en bucle:
  1) Selecciona el conector FIJO (ancla, no se mueve)
  2) Selecciona el conector que se MUEVE

El ciclo se detiene presionando ESC en cualquiera de las dos selecciones.
"""

__title__ = "Conectar\nConectores"
__author__ = "Ricardo"

import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import Line, LocationCurve
from Autodesk.Revit.UI import (
    TaskDialog,
    TaskDialogCommonButtons,
    TaskDialogResult,
    TaskDialogCommandLinkId,
)
from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms, script

doc = revit.doc
uidoc = revit.uidoc


def obtener_conector_mas_cercano(elemento, punto_click):
    """Devuelve el conector del elemento mas cercano al punto donde se hizo clic."""
    conectores = None

    if hasattr(elemento, "MEPModel") and elemento.MEPModel and elemento.MEPModel.ConnectorManager:
        conectores = elemento.MEPModel.ConnectorManager.Connectors
    elif hasattr(elemento, "ConnectorManager") and elemento.ConnectorManager:
        conectores = elemento.ConnectorManager.Connectors

    if conectores is None:
        return None

    mejor = None
    mejor_dist = None
    for c in conectores:
        dist = c.Origin.DistanceTo(punto_click)
        if mejor_dist is None or dist < mejor_dist:
            mejor = c
            mejor_dist = dist
    return mejor


def seleccionar_conector(mensaje):
    """Pide seleccionar un elemento. Devuelve (elemento, conector) o (None, None) si se cancela (ESC)."""
    try:
        ref = uidoc.Selection.PickObject(ObjectType.Element, mensaje)
    except OperationCanceledException:
        return None, None

    elemento = doc.GetElement(ref.ElementId)
    punto_click = ref.GlobalPoint
    conector = obtener_conector_mas_cercano(elemento, punto_click)

    if conector is None:
        return elemento, None

    return elemento, conector


def procesar_par(elemento_fijo, conector_fijo, elemento_mover, conector_mover, modo_conectar):
    """Mueve (y opcionalmente conecta) el conector_mover contra el conector_fijo."""
    if conector_mover.Origin.IsAlmostEqualTo(conector_fijo.Origin):
        return False

    destino = conector_fijo.Origin
    nombre_transaccion = "Conectar conector de tuberia" if modo_conectar else "Mover conector de tuberia"

    with revit.Transaction(nombre_transaccion):
        ubicacion = elemento_mover.Location

        if not isinstance(ubicacion, LocationCurve):
            return False

        curva = ubicacion.Curve
        p0 = curva.GetEndPoint(0)
        p1 = curva.GetEndPoint(1)

        # Determinar cual extremo de la curva corresponde al conector seleccionado
        # y mover solo ese extremo, dejando fijo el otro extremo del mismo elemento
        if p0.DistanceTo(conector_mover.Origin) <= p1.DistanceTo(conector_mover.Origin):
            nueva_curva = Line.CreateBound(destino, p1)
        else:
            nueva_curva = Line.CreateBound(p0, destino)

        ubicacion.Curve = nueva_curva

        if modo_conectar:
            conector_mover_actualizado = obtener_conector_mas_cercano(elemento_mover, destino)
            if conector_mover_actualizado and not conector_mover_actualizado.IsConnectedTo(conector_fijo):
                conector_mover_actualizado.ConnectTo(conector_fijo)

    return True


# 1. Preguntar el modo de operacion UNA sola vez, antes del ciclo
dialogo = TaskDialog("Conectar conectores")
dialogo.MainInstruction = "Que deseas hacer?"
dialogo.MainContent = (
    "Conectar: mueve el conector seleccionado hasta el conector fijo y los une (ConnectTo).\n\n"
    "Solo mover: desplaza el conector seleccionado hasta el conector fijo, sin conectarlos.\n\n"
    "Esta accion se repetira en ciclo. Presiona ESC durante la seleccion para detener."
)
dialogo.CommonButtons = TaskDialogCommonButtons.Cancel
dialogo.AddCommandLink(TaskDialogCommandLinkId.CommandLink1, "Conectar")
dialogo.AddCommandLink(TaskDialogCommandLinkId.CommandLink2, "Solo mover")

resultado = dialogo.Show()

if resultado == TaskDialogResult.CommandLink1:
    modo_conectar = True
elif resultado == TaskDialogResult.CommandLink2:
    modo_conectar = False
else:
    script.exit()

# 2. Ciclo: fijo -> mover -> fijo -> mover ... hasta ESC
contador = 0

while True:
    elemento_fijo, conector_fijo = seleccionar_conector(
        "Selecciona el conector FIJO (ancla) - ESC para terminar"
    )
    if conector_fijo is None:
        break

    elemento_mover, conector_mover = seleccionar_conector(
        "Selecciona el conector que se va a MOVER - ESC para terminar"
    )
    if conector_mover is None:
        break

    if procesar_par(elemento_fijo, conector_fijo, elemento_mover, conector_mover, modo_conectar):
        contador += 1

# 3. Resumen final
if contador > 0:
    accion = "conectados" if modo_conectar else "movidos"
    forms.alert(
        "Proceso terminado. {} par(es) de conectores {}.".format(contador, accion),
        title="Conectar conectores",
    )
else:
    forms.alert("Proceso terminado sin cambios.", title="Conectar conectores")