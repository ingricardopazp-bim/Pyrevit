# -*- coding: utf-8 -*-
__title__   = "Alinear CAD\npor Coordenadas"
__doc__     = "Mueve y rota un archivo CAD para que dos puntos específicos coincidan con coordenadas reales ingresadas manualmente."

from pyrevit import revit, DB, UI, forms, script

doc = revit.doc
uidoc = revit.uidoc

def to_float(val):
    if not val: return None
    # Cambia la coma por punto para evitar errores al tipear decimales (ej. 101159,20 -> 101159.20)
    val = val.replace(',', '.')
    try:
        return float(val.strip())
    except ValueError:
        return None

def meters_to_feet(m):
    # Compatibilidad con versiones de Revit
    try:
        return DB.UnitUtils.ConvertToInternalUnits(m, DB.UnitTypeId.Meters) # Revit 2021+
    except AttributeError:
        return DB.UnitUtils.ConvertToInternalUnits(m, DB.DisplayUnitType.DUT_METERS) # Revit 2020 e inferiores

def shared_to_internal(east_ft, north_ft, doc):
    """Convierte Coordenadas Compartidas a Coordenadas Internas de Revit de manera precisa."""
    pos0 = doc.ActiveProjectLocation.GetProjectPosition(DB.XYZ.Zero)
    posX = doc.ActiveProjectLocation.GetProjectPosition(DB.XYZ(100, 0, 0))
    posY = doc.ActiveProjectLocation.GetProjectPosition(DB.XYZ(0, 100, 0))
    
    vecX = DB.XYZ(posX.EastWest - pos0.EastWest, posX.NorthSouth - pos0.NorthSouth, 0).Normalize()
    vecY = DB.XYZ(posY.EastWest - pos0.EastWest, posY.NorthSouth - pos0.NorthSouth, 0).Normalize()
    
    v_shared = DB.XYZ(east_ft - pos0.EastWest, north_ft - pos0.NorthSouth, 0)
    
    int_x = v_shared.DotProduct(vecX)
    int_y = v_shared.DotProduct(vecY)
    
    return DB.XYZ(int_x, int_y, 0)

try:
    # 1. Seleccionar CAD
    class ImportInstanceSelectionFilter(UI.Selection.ISelectionFilter):
        def AllowElement(self, elem):
            return isinstance(elem, DB.ImportInstance)
        def AllowReference(self, ref, pos):
            return False

    ref_cad = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, ImportInstanceSelectionFilter(), "1/5: Selecciona el archivo CAD")
    cad_elem = doc.GetElement(ref_cad)

    # 2. Pick P1
    pt1_picked = uidoc.Selection.PickPoint("2/5: Haz clic en el PUNTO 1 en el CAD")

    # 3. Preguntar Coordenadas P1
    e1_str = forms.ask_for_string(prompt="PUNTO 1: Ingresa la coordenada ESTE (X) en metros:", title="Destino P1 - ESTE")
    if e1_str is None: script.exit()
    e1_m = to_float(e1_str)

    n1_str = forms.ask_for_string(prompt="PUNTO 1: Ingresa la coordenada NORTE (Y) en metros:", title="Destino P1 - NORTE")
    if n1_str is None: script.exit()
    n1_m = to_float(n1_str)

    if e1_m is None or n1_m is None:
        forms.alert("Coordenadas P1 inválidas.", exitscript=True)

    # 4. Pick P2
    pt2_picked = uidoc.Selection.PickPoint("4/5: Haz clic en el PUNTO 2 en el CAD (para definir la rotación)")

    # 5. Preguntar Coordenadas P2
    e2_str = forms.ask_for_string(prompt="PUNTO 2: Ingresa la coordenada ESTE (X) en metros:", title="Destino P2 - ESTE")
    if e2_str is None: script.exit()
    e2_m = to_float(e2_str)

    n2_str = forms.ask_for_string(prompt="PUNTO 2: Ingresa la coordenada NORTE (Y) en metros:", title="Destino P2 - NORTE")
    if n2_str is None: script.exit()
    n2_m = to_float(n2_str)

    if e2_m is None or n2_m is None:
        forms.alert("Coordenadas P2 inválidas.", exitscript=True)

    # --- CÁLCULOS MATEMÁTICOS ---
    
    # Convertir las coordenadas de entrada (MTS) a Pies Internos (FT)
    e1_ft = meters_to_feet(e1_m)
    n1_ft = meters_to_feet(n1_m)
    e2_ft = meters_to_feet(e2_m)
    n2_ft = meters_to_feet(n2_m)

    # Obtener el punto interno exacto en Revit para esas coordenadas geográficas
    target_p1 = shared_to_internal(e1_ft, n1_ft, doc)
    target_p2 = shared_to_internal(e2_ft, n2_ft, doc)

    # Aplanar las alturas (Z=0) para hacer una traslación y rotación estrictamente en planta 2D
    pt1 = DB.XYZ(pt1_picked.X, pt1_picked.Y, 0)
    pt2 = DB.XYZ(pt2_picked.X, pt2_picked.Y, 0)

    # Vector de Traslación
    translation_vec = DB.XYZ(target_p1.X - pt1.X, target_p1.Y - pt1.Y, 0)

    # Ángulo de Rotación
    vec_current_raw = pt2 - pt1
    vec_target_raw = target_p2 - target_p1

    angle = 0.0
    if vec_current_raw.GetLength() > 0.001 and vec_target_raw.GetLength() > 0.001:
        v_current = vec_current_raw.Normalize()
        v_target = vec_target_raw.Normalize()
        # Calcula el ángulo necesario para girar el vector actual hacia el objetivo
        angle = v_current.AngleOnPlaneTo(v_target, DB.XYZ.BasisZ)

    # --- EJECUTAR MOVIMIENTO ---
    t = DB.Transaction(doc, "Alinear CAD por Coordenadas")
    t.Start()

    try:
        # Desbloquear si está con pin
        was_pinned = cad_elem.Pinned
        if was_pinned:
            cad_elem.Pinned = False
            
        # 1. Mover
        DB.ElementTransformUtils.MoveElement(doc, cad_elem.Id, translation_vec)
        
        # 2. Rotar (Alrededor de la nueva posición del Punto 1)
        if abs(angle) > 0.0001:
            axis = DB.Line.CreateBound(target_p1, target_p1 + DB.XYZ.BasisZ)
            DB.ElementTransformUtils.RotateElement(doc, cad_elem.Id, axis, angle)
            
        # Ponerle Pin automáticamente para que no se mueva
        cad_elem.Pinned = True
        
        t.Commit()
        forms.alert("¡CAD alineado correctamente!\n\nSe movió al Punto 1 y se rotó para apuntar al Punto 2. El archivo ha quedado bloqueado (Pinned).", title="Éxito")
    except Exception as e:
        t.RollBack()
        forms.alert("Error al intentar alinear:\n{}".format(str(e)), title="Error")

except Exception as e:
    # Captura si el usuario presiona ESC para cancelar
    pass