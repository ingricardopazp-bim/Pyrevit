# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import (
    Line, FilteredElementCollector, BuiltInCategory,
    Transaction, FamilySymbol, Level,
)
from Autodesk.Revit.DB.Structure import StructuralType
from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import revit, script

doc = revit.doc
uidoc = revit.uidoc

# --- 1. Buscar el FamilySymbol una sola vez, fuera del bucle ---
print("Buscando FamilySymbol NEW_JERSEY...")
todos = FilteredElementCollector(doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_StructuralFraming).ToElements()
candidatos = [s for s in todos if "NEW_JERSEY" in s.Family.Name.upper()]

if not candidatos:
    print("ERROR: No se encontro ninguna familia NEW_JERSEY.")
    script.exit()

simbolo = candidatos[0]
print("OK - simbolo: {} / activo: {}".format(simbolo.Id, simbolo.IsActive))

nivel = getattr(doc.ActiveView, "GenLevel", None)
if nivel is None:
    nivel = FilteredElementCollector(doc).OfClass(Level).FirstElement()
print("Nivel: {}".format(nivel.Id if nivel else "NINGUNO"))

# Activar el simbolo antes del bucle (evita reactivarlo en cada vuelta)
if not simbolo.IsActive:
    t_act = Transaction(doc, "Activar simbolo NEW_JERSEY")
    t_act.Start()
    simbolo.Activate()
    doc.Regenerate()
    t_act.Commit()
    print("Simbolo activado.")

# --- 2. Bucle ciclico: una linea -> una transaccion ---
total_creadas = 0
contador = 0

while True:
    try:
        ref = uidoc.Selection.PickObject(ObjectType.Edge, "Selecciona una linea (Esc para terminar)")
    except OperationCanceledException:
        print("Seleccion cancelada por el usuario. Fin del script.")
        break

    contador += 1
    print("{}. Linea seleccionada.".format(contador))

    elemento = doc.GetElement(ref.ElementId)
    geo = elemento.GetGeometryObjectFromReference(ref)
    curva = geo.AsCurve()
    p0 = curva.GetEndPoint(0)
    p1 = curva.GetEndPoint(1)
    linea_recta = Line.CreateBound(p0, p1)

    t = Transaction(doc, "Crear New Jersey #{}".format(contador))
    t.Start()
    try:
        nueva = doc.Create.NewFamilyInstance(linea_recta, simbolo, nivel, StructuralType.Beam)
        t.Commit()
        total_creadas += 1
        print("   OK - creada Id: {} (long: {:.2f}). Total: {}".format(nueva.Id, linea_recta.Length, total_creadas))
    except Exception as e:
        print("   ERROR: {}".format(e))
        t.RollBack()
        print("   Transaccion revertida para esta linea.")

print("Proceso terminado. Total de elementos New Jersey creados: {}".format(total_creadas))