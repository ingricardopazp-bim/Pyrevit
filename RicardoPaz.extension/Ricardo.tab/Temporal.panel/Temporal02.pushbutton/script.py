# -*- coding: utf-8 -*-
__title__ = 'CAD a Cables\nVisibles'

import traceback
import sys

try:
    import math
    from Autodesk.Revit.DB import *
    from Autodesk.Revit.UI import *
    from Autodesk.Revit.UI.Selection import ObjectType
    from System.Collections.Generic import List
    import System

    uidoc = __revit__.ActiveUIDocument
    doc = uidoc.Document

    if not doc.IsFamilyDocument:
        print("-> ALERTA: Este script debe ejecutarse dentro de un archivo de familia (ej. Modelo Genérico Adaptativo).")
        sys.exit()

    try:
        ref = uidoc.Selection.PickObject(ObjectType.Element, "Selecciona el archivo CAD")
        cad_element = doc.GetElement(ref)
    except Exception:
        sys.exit()

    print("Analizando geometría del CAD (Filtrando capas ocultas)...")
    
    # Configurar opciones para que Revit tenga en cuenta la vista actual
    opt = Options()
    opt.View = doc.ActiveView 
    
    geom_elem = cad_element.get_Geometry(opt)
    path_loops = []
    SHORT_TOLERANCE = 0.003 

    if geom_elem:
        for geom_obj in geom_elem:
            if isinstance(geom_obj, GeometryInstance):
                inst_geom = geom_obj.GetInstanceGeometry()
                for inst_obj in inst_geom:
                    
                    # --- FILTRO DE CAPAS OCULTAS ---
                    is_visible = True
                    if inst_obj.GraphicsStyleId != ElementId.InvalidElementId:
                        g_style = doc.GetElement(inst_obj.GraphicsStyleId)
                        if g_style and g_style.GraphicsStyleCategory:
                            cat = g_style.GraphicsStyleCategory
                            try:
                                # Comprobamos si la capa (subcategoría) está apagada en la vista activa
                                if doc.ActiveView.GetCategoryHidden(cat.Id):
                                    is_visible = False
                            except:
                                pass
                    
                    # Si la capa está oculta, la ignoramos y no creamos el cable
                    if not is_visible:
                        continue
                    # -------------------------------

                    if isinstance(inst_obj, Curve):
                        if inst_obj.Length > SHORT_TOLERANCE:
                            loop = CurveLoop()
                            loop.Append(inst_obj)
                            path_loops.append(loop)
                    elif isinstance(inst_obj, PolyLine):
                        pts = inst_obj.GetCoordinates()
                        if len(pts) > 1:
                            loop = CurveLoop()
                            last_pt = pts[0]
                            for i in range(1, len(pts)):
                                if last_pt.DistanceTo(pts[i]) > SHORT_TOLERANCE:
                                    line = Line.CreateBound(last_pt, pts[i])
                                    loop.Append(line)
                                    last_pt = pts[i]
                            
                            count = 0
                            for _ in loop: count += 1
                            if count > 0:
                                path_loops.append(loop)

    print("Trazados (polilíneas/curvas) VISIBLES encontrados: {}".format(len(path_loops)))
    
    if len(path_loops) > 0:
        radius_feet = 45.0 / 304.8
        created_count = 0
        
        t = Transaction(doc, "Convertir CAD a Cables (Capas Visibles)")
        t.Start()
        
        print("Generando cables continuos de 50mm... por favor espera.")
        for i, path_loop in enumerate(path_loops):
            first_curve = None
            for c in path_loop:
                first_curve = c
                break
                
            if not first_curve:
                continue

            try:
                start_param = first_curve.GetEndParameter(0)
                transform = first_curve.ComputeDerivatives(start_param, True)
                origin = transform.Origin
                normal = transform.BasisX
                
                plane = Plane.CreateByNormalAndOrigin(normal, origin)
                arc1 = Arc.Create(plane, radius_feet, 0.0, math.pi)
                arc2 = Arc.Create(plane, radius_feet, math.pi, 2 * math.pi)
                
                profile_loop = CurveLoop()
                profile_loop.Append(arc1)
                profile_loop.Append(arc2)
                
                profile_loops = List[CurveLoop]()
                profile_loops.Add(profile_loop)
                
                solid = GeometryCreationUtilities.CreateSweptGeometry(path_loop, 0, 0.0, profile_loops)
                if solid and solid.Volume > 0:
                    FreeFormElement.Create(doc, solid)
                    created_count += 1
                    
            except Exception as ex:
                for c in path_loop:
                    try:
                        c_start = c.GetEndParameter(0)
                        c_trans = c.ComputeDerivatives(c_start, True)
                        c_origin = c_trans.Origin
                        c_normal = c_trans.BasisX
                        
                        c_plane = Plane.CreateByNormalAndOrigin(c_normal, c_origin)
                        c_arc1 = Arc.Create(c_plane, radius_feet, 0.0, math.pi)
                        c_arc2 = Arc.Create(c_plane, radius_feet, math.pi, 2 * math.pi)
                        
                        c_prof = CurveLoop()
                        c_prof.Append(c_arc1)
                        c_prof.Append(c_arc2)
                        
                        c_profs = List[CurveLoop]()
                        c_profs.Add(c_prof)
                        
                        c_path = CurveLoop()
                        c_path.Append(c)
                        
                        c_solid = GeometryCreationUtilities.CreateSweptGeometry(c_path, 0, 0.0, c_profs)
                        if c_solid and c_solid.Volume > 0:
                            FreeFormElement.Create(doc, c_solid)
                            created_count += 1
                    except Exception:
                        pass
                
        t.Commit()
        
        print("\n¡PROCESO TERMINADO!")
        print("Elementos sólidos creados exitosamente: {}".format(created_count))
        
    else:
        print("No se encontraron curvas visibles procesables en el CAD.")

except System.Exception as e:
    print("\n--- ERROR DE REVIT ---")
    print(e)
except Exception as e:
    print("\n--- ERROR DE PYTHON ---")
    print(traceback.format_exc())