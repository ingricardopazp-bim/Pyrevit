# -*- coding: utf-8 -*-
from pyrevit import revit, forms, script
from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.DB import Transaction, LocationCurve
from Autodesk.Revit.Exceptions import OperationCanceledException
import math

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

PARAM_NAME = "Cross-Section Rotation"

contador = 0

while True:
    try:
        # --- 1. Selección de caras ---
        ref1 = uidoc.Selection.PickObject(ObjectType.Face, "Selecciona la primera cara (Esc para terminar)")
        ref2 = uidoc.Selection.PickObject(ObjectType.Face, "Selecciona la segunda cara")

    except OperationCanceledException:
        # El usuario presionó Esc -> se termina el ciclo
        break

    try:
        elem1 = doc.GetElement(ref1)
        elem2 = doc.GetElement(ref2)

        face1 = elem1.GetGeometryObjectFromReference(ref1)
        face2 = elem2.GetGeometryObjectFromReference(ref2)

        if face1 is None or face2 is None:
            forms.alert("No se pudo obtener la geometría de la cara (face es None).")
            continue

        bbox1 = face1.GetBoundingBox()
        bbox2 = face2.GetBoundingBox()

        normal1 = face1.ComputeNormal(bbox1.Min)
        normal2 = face2.ComputeNormal(bbox2.Min)

        dot_normals = normal1.DotProduct(normal2)
        dot_normals = max(-1.0, min(1.0, dot_normals))
        angle_rad = math.acos(dot_normals)
        angle_deg = math.degrees(angle_rad)

        valor_final = angle_deg - 180

        # --- 2. Sentido de dibujo del elemento 1 ---
        loc = elem1.Location
        sentido = "N/A (el elemento no tiene LocationCurve)"

        if isinstance(loc, LocationCurve):
            curve = loc.Curve
            start = curve.GetEndPoint(0)
            end = curve.GetEndPoint(1)
            direction = end - start
            right = view.RightDirection

            dot_dir = direction.DotProduct(right)

            if dot_dir > 0:
                sentido = "IZQUIERDA a DERECHA"
            elif dot_dir < 0:
                sentido = "DERECHA a IZQUIERDA"
            else:
                sentido = "Perpendicular a la vista (sin componente horizontal clara)"

        # --- 3. Invertir signo si el sentido es DERECHA a IZQUIERDA ---
        if sentido == "DERECHA a IZQUIERDA":
            valor_final = valor_final * -1

        valor_calculado = valor_final

        # --- 4. Localizar el parámetro y leer su valor actual ---
        param = elem1.LookupParameter(PARAM_NAME)

        if param is None:
            forms.alert("No se encontró el parámetro '{}' en el elemento {}.".format(
                PARAM_NAME, elem1.Id))
            continue

        if param.IsReadOnly:
            forms.alert("El parámetro '{}' es de solo lectura.".format(PARAM_NAME))
            continue

        valor_actual_rad = param.AsDouble()
        valor_actual_deg = math.degrees(valor_actual_rad)

        # Suma simple, respetando el signo del valor anterior
        valor_final = valor_calculado + valor_actual_deg

        # --- 5. Escribir el nuevo valor (una transacción POR CICLO) ---
        t = Transaction(doc, "Set Cross-Section Rotation - Elem {}".format(elem1.Id))
        t.Start()
        try:
            ok = param.SetValueString(str(valor_final))
            if not ok:
                param.Set(math.radians(valor_final))
            t.Commit()
        except Exception as e_param:
            t.RollBack()
            forms.alert("Error al escribir el parámetro: {}".format(e_param))
            continue

        contador += 1

        # --- 6. Resultado de este ciclo ---
        forms.alert(
            "Elemento: {}\n"
            "Ángulo entre normales: {:.2f}°\n"
            "Sentido de dibujo: {}\n"
            "Valor calculado (antes de sumar): {:.2f}\n"
            "Valor anterior del parámetro: {:.2f}\n"
            "Valor final escrito en '{}': {:.2f}".format(
                elem1.Id, angle_deg, sentido, valor_calculado, valor_actual_deg,
                PARAM_NAME, valor_final),
            title="Resultado (elemento #{})".format(contador)
        )

    except Exception as e:
        forms.alert("Error en este ciclo: {}".format(e))
        continue

if contador > 0:
    forms.alert("Proceso terminado. Elementos procesados: {}".format(contador))
else:
    forms.alert("Proceso cancelado. No se procesó ningún elemento.")