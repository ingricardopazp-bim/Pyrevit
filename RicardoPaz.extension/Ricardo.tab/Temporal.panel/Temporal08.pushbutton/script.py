# -*- coding: utf-8 -*-
import sys
import traceback
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from pyrevit import revit, forms

doc = revit.doc
uidoc = revit.uidoc

# Filtro para la selección de vínculos
class LinkSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        return isinstance(element, RevitLinkInstance)

    def AllowReference(self, reference, point):
        return True

def reubicar_elemento():
    # 1. Seleccionar el elemento a reubicar
    try:
        ref_elem = uidoc.Selection.PickObject(ObjectType.Element, "1. Selecciona el elemento a reubicar")
    except Exception:
        print("Selección cancelada por el usuario.")
        return

    elem = doc.GetElement(ref_elem)
    symbol = elem.Symbol
    symbol_name = Element.Name.GetValue(symbol)
    print("Elemento seleccionado: {} (ID: {})".format(symbol_name, elem.Id))

    # 2. Seleccionar la cara en el vínculo
    try:
        ref_face_linked = uidoc.Selection.PickObject(
            ObjectType.PointOnElement, 
            LinkSelectionFilter(), 
            "2. Haz clic directamente sobre la NUEVA cara del vínculo"
        )
    except Exception:
        print("Selección de cara cancelada por el usuario.")
        return

    link_instance = doc.GetElement(ref_face_linked.ElementId)
    if not isinstance(link_instance, RevitLinkInstance):
        forms.alert("El elemento seleccionado no pertenece a un vínculo.", exitscript=True)

    click_point = ref_face_linked.GlobalPoint

    # 3. Construcción segura de la referencia de vínculo para evitar SEHException
    host_face_ref = None
    try:
        # Intento de creación directa segura
        host_face_ref = ref_face_linked.CreateLinkReference(link_instance)
    except Exception:
        # Si falla el método nativo, parseamos la representación estable de la cara del vínculo
        stable_rep = ref_face_linked.ConvertToStableRepresentation(doc)
        host_face_ref = Reference.ParseFromStableRepresentation(doc, stable_rep)

    # 4. Transacción para recrear el elemento
    t = Transaction(doc, "Forzar nueva cara de link")
    t.Start()
    try:
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()

        old_id = elem.Id
        doc.Delete(old_id)

        # Crear la nueva instancia asociada a la referencia de cara
        new_elem = doc.Create.NewFamilyInstance(
            host_face_ref,
            click_point,
            XYZ.BasisX,
            symbol
        )

        doc.Regenerate()
        t.Commit()

        mensaje = "¡ÉXITO!\nElemento reubicado en la nueva cara.\n\nID Anterior: {}\nNuevo ID: {}".format(old_id, new_elem.Id)
        print(mensaje)
        forms.alert(mensaje, title="Reubicación Exitosa")

    except Exception as ex:
        t.RollBack()
        err_details = traceback.format_exc()
        print("Error durante la transacción:\n{}".format(err_details))
        forms.alert("Error de la API de Revit al crear la instancia:\n{}".format(str(ex)), title="Error")

if __name__ == "__main__":
    try:
        reubicar_elemento()
    except Exception as g_ex:
        print("Excepción global:\n{}".format(traceback.format_exc()))
        forms.alert("Error general en el script:\n{}".format(str(g_ex)))