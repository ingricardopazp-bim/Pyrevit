# -*- coding: utf-8 -*-
__title__ = 'Shaft Exacto\nEquipos/Plumbing'
__doc__ = 'Crea un shaft opening basándose en la silueta 3D exacta (figuras especiales) de un equipo eléctrico o aparato sanitario vinculado.'

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
from Autodesk.Revit.UI.Selection import *
import sys

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

class LinkedEquipmentFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, RevitLinkInstance)
        
    def AllowReference(self, ref, pos):
        link_instance = doc.GetElement(ref.ElementId)
        if isinstance(link_instance, RevitLinkInstance):
            link_doc = link_instance.GetLinkDocument()
            elem = link_doc.GetElement(ref.LinkedElementId)
            if elem and elem.Category:
                cat_id = elem.Category.Id.IntegerValue
                if cat_id == int(BuiltInCategory.OST_ElectricalEquipment) or cat_id == int(BuiltInCategory.OST_PlumbingFixtures):
                    return True
        return False

def get_exact_footprint(equip_elem, link_transform):
    """
    Extrae la geometría sólida del elemento, los une y proyecta la sombra
    exacta hacia el plano XY usando ExtrusionAnalyzer para obtener curvas de cualquier forma.
    """
    opt = Options()
    opt.DetailLevel = ViewDetailLevel.Fine
    geom_elem = equip_elem.get_Geometry(opt)
    
    if not geom_elem:
        return None
        
    solids = []
    
    # 1. Extraer recursivamente todos los sólidos reales
    def extract_solids(g_elem, current_transform):
        for geom_obj in g_elem:
            if isinstance(geom_obj, GeometryInstance):
                inst_transform = geom_obj.Transform
                final_transform = current_transform.Multiply(inst_transform)
                extract_solids(geom_obj.GetSymbolGeometry(), final_transform)
            elif isinstance(geom_obj, Solid) and geom_obj.Volume > 0:
                transformed_solid = SolidUtils.CreateTransformed(geom_obj, current_transform)
                solids.append(transformed_solid)

    extract_solids(geom_elem, link_transform)
    
    if not solids:
        return None
        
    # 2. Unir todos los sólidos en uno solo
    main_solid = solids[0]
    for i in range(1, len(solids)):
        try:
            main_solid = BooleanOperationsUtils.ExecuteBooleanOperation(
                main_solid, solids[i], BooleanOperationsType.Union)
        except:
            pass # Si la unión de algún componente falla, continuamos con lo que se pudo unir
            
    # 3. Proyectar el sólido al plano Z=0 para sacar el contorno 2D (Footprint)
    plane = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, XYZ.Zero)
    try:
        analyzer = ExtrusionAnalyzer.Create(main_solid, plane, XYZ.BasisZ)
        face = analyzer.GetExtrusionBase()
        curve_loops = face.GetEdgesAsCurveLoops()
        
        if curve_loops:
            # Por lo general puede haber agujeros interiores. 
            # Tomamos el CurveLoop exterior (el de mayor longitud perimetral).
            outer_loop = max(curve_loops, key=lambda loop: loop.GetExactLength())
            return outer_loop
    except:
        # Si la figura tiene errores geométricos graves, hacemos Fallback a Caja Rectangular (BoundingBox)
        pass
        
    # Fallback: Caja si el ExtrusionAnalyzer falla
    bbox = equip_elem.get_BoundingBox(None)
    if bbox:
        p1 = link_transform.OfPoint(XYZ(bbox.Min.X, bbox.Min.Y, 0))
        p2 = link_transform.OfPoint(XYZ(bbox.Max.X, bbox.Min.Y, 0))
        p3 = link_transform.OfPoint(XYZ(bbox.Max.X, bbox.Max.Y, 0))
        p4 = link_transform.OfPoint(XYZ(bbox.Min.X, bbox.Max.Y, 0))
        
        l1 = Line.CreateBound(p1, p2)
        l2 = Line.CreateBound(p2, p3)
        l3 = Line.CreateBound(p3, p4)
        l4 = Line.CreateBound(p4, p1)
        
        loop = CurveLoop()
        loop.Append(l1)
        loop.Append(l2)
        loop.Append(l3)
        loop.Append(l4)
        return loop
        
    return None

def main():
    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.LinkedElement, 
            LinkedEquipmentFilter(), 
            "Selecciona el equipo en el modelo vinculado (Permite formas especiales)"
        )
        
        link_instance = doc.GetElement(ref.ElementId)
        link_doc = link_instance.GetLinkDocument()
        link_transform = link_instance.GetTotalTransform()
        equip_elem = link_doc.GetElement(ref.LinkedElementId)
        
        # Obtenemos el Loop de curvas con la figura exacta
        outer_loop = get_exact_footprint(equip_elem, link_transform)
        if not outer_loop:
            TaskDialog.Show("Error", "No se pudo leer la geometría de este equipo.")
            return
            
        collector_levels = FilteredElementCollector(doc).OfClass(Level).ToElements()
        if not collector_levels:
            TaskDialog.Show("Error", "No hay niveles en el modelo anfitrión.")
            return
            
        levels_sorted = sorted(collector_levels, key=lambda lvl: lvl.Elevation)
        bottom_level = levels_sorted[0]
        top_level = levels_sorted[-1]
        
        z_elev = bottom_level.Elevation
        
        profile = CurveArray()
        
        # Mover las curvas exactamente a la altura del nivel inferior
        for curve in outer_loop:
            z_offset = z_elev - curve.GetEndPoint(0).Z
            if abs(z_offset) > 0.001:
                translation = Transform.CreateTranslation(XYZ(0, 0, z_offset))
                flat_curve = curve.CreateTransformed(translation)
                profile.Append(flat_curve)
            else:
                profile.Append(curve)
        
        t = Transaction(doc, "Crear Shaft con Perfil Exacto")
        t.Start()
        
        # Creamos el shaft con cualquier geometría (círculo, poligono, etc)
        shaft = doc.Create.NewOpening(bottom_level, top_level, profile)
        
        b_offset = shaft.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET)
        t_offset = shaft.get_Parameter(BuiltInParameter.WALL_TOP_OFFSET)
        
        # Ajustamos los offsets
        if b_offset and not b_offset.IsReadOnly:
            b_offset.Set(-3.0)
        if t_offset and not t_offset.IsReadOnly:
            t_offset.Set(3.0)

        t.Commit()
        
        TaskDialog.Show("Éxito", "Shaft creado copiando el corte exacto de la figura 3D del elemento.")
        
    except Autodesk.Revit.Exceptions.OperationCanceledException:
        pass
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        TaskDialog.Show("Excepción", "Ocurrió un error:\n\n" + str(error_msg))

if __name__ == '__main__':
    main()