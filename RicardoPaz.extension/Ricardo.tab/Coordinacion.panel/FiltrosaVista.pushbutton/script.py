# -*- coding: utf-8 -*-

from pyrevit import revit, DB, forms
from System.Collections.Generic import List
import traceback
import re

doc = revit.doc
active_view = doc.ActiveView

def hsv_to_rgb(h, s, v):
    if s == 0.0: return v, v, v
    i = int(h * 6.)
    f = (h * 6.) - i
    p, q, t = v * (1. - s), v * (1. - s * f), v * (1. - s * (1. - f))
    i %= 6
    if i == 0: return v, t, p
    if i == 1: return q, v, p
    if i == 2: return p, v, t
    if i == 3: return p, q, v
    if i == 4: return t, p, v
    if i == 5: return v, p, q
    return 0, 0, 0

def main():
    # 1. Analizar elementos en la vista activa
    collector = DB.FilteredElementCollector(doc, active_view.Id).WhereElementIsNotElementType()

    param_names = set()
    elements = []

    for el in collector:
        try:
            if el.Category and el.Category.CategoryType == DB.CategoryType.Model:
                if el.CanBeHidden(active_view): 
                    elements.append(el)
                    for param in el.Parameters:
                        if param.HasValue:
                            param_names.add(param.Definition.Name)
        except Exception:
            pass

    if not elements or not param_names:
        forms.alert("No se encontraron elementos de modelo o parámetros válidos en la vista.")
        return

    # 2. Mostrar lista
    selected_param_name = forms.SelectFromList.show(
        sorted(list(param_names)),
        title='Selecciona un parámetro (Crea y Colorea FILTROS)',
        button_name='Seleccionar'
    )

    if not selected_param_name:
        return

    # 3. Agrupar valores únicos
    value_elements_map = {}
    categories_set = set()

    for el in elements:
        try:
            param = el.LookupParameter(selected_param_name)
            if param and param.HasValue:
                val_str = param.AsValueString()
                if not val_str:
                    if param.StorageType == DB.StorageType.String:
                        val_str = param.AsString()
                    elif param.StorageType == DB.StorageType.Double:
                        val_str = str(param.AsDouble())
                    elif param.StorageType == DB.StorageType.Integer:
                        val_str = str(param.AsInteger())
                    elif param.StorageType == DB.StorageType.ElementId:
                        val_str = param.AsElementId().ToString()
                
                if val_str:
                    if val_str not in value_elements_map:
                        value_elements_map[val_str] = []
                    value_elements_map[val_str].append(el)
                    categories_set.add(el.Category.Id)
        except Exception:
            pass

    if not value_elements_map:
        forms.alert("Ningún elemento tiene un valor asignado para '{}'.".format(selected_param_name))
        return

    cat_list = List[DB.ElementId](list(categories_set))

    # Buscar patrón de relleno
    fill_pattern_element = None
    patterns = DB.FilteredElementCollector(doc).OfClass(DB.FillPatternElement).ToElements()
    for pattern in patterns:
        if pattern.GetFillPattern().IsSolidFill:
            fill_pattern_element = pattern
            break

    # 4. Procesar Filtros
    t = DB.Transaction(doc, "Crear/Colorear Filtros: " + selected_param_name)
    t.Start()
    
    unique_values = list(value_elements_map.keys())
    unique_values.sort()
    n_colors = len(unique_values)

    existing_filters = DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement).ToElements()
    existing_filter_dict = {f.Name: f for f in existing_filters}

    filtros_procesados = 0

    for i, val_str in enumerate(unique_values):
        safe_val = re.sub(r'[\\:\{\}\[\]\|;<>\?\'~]', '_', str(val_str))
        filter_name = "{} - {}".format(selected_param_name, safe_val)
        if len(filter_name) > 60:
            filter_name = filter_name[:60]

        filter_element = None
        
        # SI EL FILTRO YA EXISTE EN EL PROYECTO, LO REUTILIZAMOS. SI NO, LO CREAMOS.
        if filter_name in existing_filter_dict:
            filter_element = existing_filter_dict[filter_name]
        else:
            rep_el = value_elements_map[val_str][0]
            param = rep_el.LookupParameter(selected_param_name)
            param_id = param.Id

            rule = None
            if param.StorageType == DB.StorageType.String:
                v = param.AsString() or ""
                try:
                    rule = DB.ParameterFilterRuleFactory.CreateEqualsRule(param_id, v)
                except:
                    rule = DB.ParameterFilterRuleFactory.CreateEqualsRule(param_id, v, True)
            elif param.StorageType == DB.StorageType.Double:
                v = param.AsDouble()
                rule = DB.ParameterFilterRuleFactory.CreateEqualsRule(param_id, v, 0.0001)
            elif param.StorageType == DB.StorageType.Integer:
                v = param.AsInteger()
                rule = DB.ParameterFilterRuleFactory.CreateEqualsRule(param_id, v)
            elif param.StorageType == DB.StorageType.ElementId:
                v = param.AsElementId()
                rule = DB.ParameterFilterRuleFactory.CreateEqualsRule(param_id, v)

            if not rule:
                continue

            elem_filter = DB.ElementParameterFilter(rule)
            try:
                filter_element = DB.ParameterFilterElement.Create(doc, filter_name, cat_list, elem_filter)
            except Exception:
                continue

        if not filter_element:
            continue

        # Aplicar el filtro a la vista activa si no está aplicado
        try:
            active_view.AddFilter(filter_element.Id)
        except Exception:
            pass # Ya estaba aplicado a la vista

        # Generar color distinto para este filtro
        h = float(i) / max(1, n_colors) 
        r_f, g_f, b_f = hsv_to_rgb(h, 0.75, 0.95)
        r, g, b = int(r_f * 255), int(g_f * 255), int(b_f * 255)
        color = DB.Color(r, g, b)

        ogs = active_view.GetFilterOverrides(filter_element.Id)
        if not ogs:
            ogs = DB.OverrideGraphicSettings()
            
        ogs.SetSurfaceForegroundPatternColor(color)
        ogs.SetCutForegroundPatternColor(color)
        
        if fill_pattern_element:
            ogs.SetSurfaceForegroundPatternId(fill_pattern_element.Id)
            ogs.SetCutForegroundPatternId(fill_pattern_element.Id)

        # Actualizar el color del filtro en la vista
        active_view.SetFilterOverrides(filter_element.Id, ogs)
        filtros_procesados += 1

    t.Commit()
    
    forms.alert("¡Listo!\n\nSe procesaron {} filtros correspondientes al parámetro '{}'.\nSe crearon los que faltaban y se les asignó un color a todos en la vista activa.".format(filtros_procesados, selected_param_name))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import script
        output = script.get_output()
        output.print_md("### Error Detallado del Script:")
        output.print_html("<pre>{}</pre>".format(traceback.format_exc()))