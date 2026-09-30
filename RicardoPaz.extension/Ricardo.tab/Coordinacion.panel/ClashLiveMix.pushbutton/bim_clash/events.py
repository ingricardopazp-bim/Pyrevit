# -*- coding: utf-8 -*-
from __future__ import absolute_import

import clr


clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

import math
import traceback

from Autodesk.Revit.DB import (
    ElementId, RevitLinkInstance, FilteredElementCollector, XYZ,
    OverrideGraphicSettings, FillPatternElement, Transaction,
    BuiltInCategory, BuiltInParameter, DirectShape, GeometryObject,
    Line, Arc, CurveLoop, Frame, GeometryCreationUtilities, SolidOptions,
    View3D, BoundingBoxXYZ, TemporaryViewMode
)
from Autodesk.Revit.DB import Color as RevitColor
from Autodesk.Revit.UI import IExternalEventHandler
from System.Collections.Generic import List


# Colores de resaltado — mismos acentos que usan las tarjetas A/B del panel de detalle en ui.py
_COLOR_SOURCE = RevitColor(14, 165, 233)    # azul  — Elemento A
_COLOR_TARGET = RevitColor(249, 115, 22)    # naranja — Elemento B
_COLOR_BLACK  = RevitColor(0, 0, 0)         # líneas de proyección — siempre negras
_COLOR_MARKER = RevitColor(220, 38, 38)     # rojo — esfera temporal "Marcar punto"

_MARKER_RADIUS_FT = 0.5 * 3.280839895       # radio de la esfera: 0.5 m (diámetro 1 m)
_SECTION_PAD_FT = 0.5 * 3.280839895          # margen del Section Box alrededor de A+B: 0.5 m
_MARKER_MAX_DIST_FT = 5.0                   # tolerancia punto ↔ bbox de A+B para aceptar la conversión


class ClashExternalEventHandler(IExternalEventHandler):
    __namespace__ = "BimClash"

    def __init__(self):
        self.detector        = None
        self.state           = None
        self.logger          = None
        self.form            = None
        self.action          = None
        self.include_links   = True
        self.selected_record = None
        self.select_target   = 'source'
        self.is_scanning     = False
        self.max_results     = None   # None = usar DEFAULT_MAX_RESULTS del detector
        self.xml_path         = None
        self.last_xml_path    = None   # ultimo XML importado con exito — usado por "Guardar XML"
        self._solid_fill_id      = None   # cache del FillPattern solido
        self._highlighted_view_id = None
        self._highlighted_ids     = []
        self._marker_ids          = []   # esferas temporales creadas por "Marcar punto"
        self._section_state       = None  # {'view_id','key','was_active','box'} del Section Box aplicado
        self._isolate_state       = None  # {'view_id','key'} del aislamiento temporal aplicado

    def GetName(self):
        return 'BIM Conflict Manager External Event'

    def Execute(self, uiapp):
        try:
            if self.action == 'scan':
                self._execute_scan()
            elif self.action == 'select':
                self._execute_select(uiapp)
            elif self.action == 'select_only':
                self._execute_select(uiapp, zoom=False)
            elif self.action == 'import_xml':
                self._execute_import_xml()
            elif self.action == 'save_xml':
                self._execute_save_xml()
            elif self.action == 'mark_point':
                self._execute_mark_point(uiapp)
            elif self.action == 'section_box':
                self._execute_section_box(uiapp)
            elif self.action == 'isolate':
                self._execute_isolate(uiapp)
        except Exception as err:
            tb = traceback.format_exc()
            if self.logger:
                self.logger.error(u'%s: %s\n%s' % (type(err).__name__, err, tb))
            if self.form:
                self.form.show_error(u'%s: %s' % (type(err).__name__, err))
        finally:
            self.action = None

    def request_scan(self, include_links):
        if self.is_scanning:
            return False
        self.include_links = include_links
        self.action = 'scan'
        return True

    def request_xml_import(self, xml_path):
        if self.is_scanning:
            return False
        self.xml_path = xml_path
        self.action = 'import_xml'
        return True

    def request_save_xml(self):
        """Escribe los statuses actuales de vuelta al ultimo XML importado.
        Solo tiene sentido cuando el origen de los conflictos es un XML
        (ver ui.py: solo se habilita el boton en source_mode == 'xml')."""
        if self.is_scanning:
            return False
        if not self.last_xml_path:
            return False
        self.action = 'save_xml'
        return True

    def abort_scan(self):
        """Cancela el scan en curso activando el flag en el detector."""
        self.detector.abort_flag = True

    # ── Limpieza de overrides huérfanos de una sesión anterior ──────────────────
    def cleanup_stale_highlights(self):
        """
        Se ejecuta una vez, al abrir el Manager, ANTES de mostrar el formulario.
        Si una sesión previa dejó un conflicto pintado (Elemento A azul / B naranja)
        sin limpiar — por cierre abrupto de Revit, crash, o cerrar el Manager con
        un elemento aún resaltado — el color queda guardado en la vista dentro del
        propio modelo. Esta rutina lee lo último persistido en el JSON de estado y
        lo limpia antes de que el usuario vea nada raro.
        """
        # Esferas temporales de "Marcar punto" que hayan quedado de otra sesión.
        try:
            self._delete_markers(self.detector.doc, self.state.get_markers())
            self.state.clear_markers()
        except Exception:
            pass

        try:
            view_id, element_ids = self.state.get_highlight()
        except Exception:
            return
        if not view_id or not element_ids:
            return

        doc = self.detector.doc
        try:
            view = doc.GetElement(ElementId(view_id))
        except Exception:
            view = None

        if view is not None:
            empty = OverrideGraphicSettings()
            t = Transaction(doc, 'ClashLiveMix - Limpiar resaltado (sesion anterior)')
            t.Start()
            try:
                for eid_int in element_ids:
                    try:
                        view.SetElementOverrides(ElementId(eid_int), empty)
                    except Exception:
                        pass
                t.Commit()
            except Exception:
                t.RollBack()

        # Se limpia la marca persistida exista o no la vista (p.ej. vista borrada).
        self.state.clear_highlight()

    def request_section_box(self, record):
        self.selected_record = record
        self.action          = 'section_box'

    def request_isolate(self, record):
        self.selected_record = record
        self.action          = 'isolate'

    def request_mark_point(self, record):
        self.selected_record = record
        self.action          = 'mark_point'

    def request_select(self, record, target='source'):
        self.selected_record = record
        self.select_target   = target
        self.action          = 'select'

    def request_select_only(self, record, target='source'):
        self.selected_record = record
        self.select_target   = target
        self.action          = 'select_only'

    # ── Scan ─────────────────────────────────────────────────────────────────
    def _execute_scan(self):
        self.is_scanning = True
        try:
            uidoc        = self._active_uidoc()
            selected_ids = []
            active_view  = None
            if uidoc is not None:
                try:
                    selected_ids = list(uidoc.Selection.GetElementIds())
                except Exception:
                    selected_ids = []
                try:
                    active_view = uidoc.ActiveView
                except Exception:
                    active_view = None
            records = self.detector.scan(self.include_links, selected_ids, active_view,
                                         max_results=self.max_results, prev_statuses=self.state._statuses)
            merged  = self.state.merge(records)
            if self.form:
                self.form.apply_records(merged)
        finally:
            self.is_scanning = False
            if self.form:
                try:
                    from System.Windows.Forms import MethodInvoker
                    self.form.BeginInvoke(MethodInvoker(self.form._on_scan_finished))
                except Exception:
                    pass

    def _active_uidoc(self):
        try:
            return self.form.uidoc
        except Exception:
            return None

    # ── Import XML (Navisworks) ─────────────────────────────────────────────────
    def _execute_import_xml(self):
        self.is_scanning = True
        try:
            uidoc = self._active_uidoc()
            doc = uidoc.Document if uidoc is not None else None
            if doc is None:
                raise Exception('No se encontro un documento activo de Revit.')
            from bim_clash.xml_importer import parse_navisworks_xml
            records = parse_navisworks_xml(self.xml_path, doc)
            self.last_xml_path = self.xml_path   # exito → queda disponible para "Guardar XML"
            merged  = self.state.merge(records)
            if self.form:
                self.form.apply_records(merged)

            skipped = getattr(parse_navisworks_xml, 'last_skipped_count', 0)
            total   = getattr(parse_navisworks_xml, 'last_total_pairs', len(records))
            if skipped and self.form:
                msg = (u'Se importaron %d de %d pares de conflicto.\n'
                       u'%d fueron descartados porque su Element ID no existe '
                       u'ni en el documento activo ni en sus modelos linkeados '
                       u'cargados actualmente.\n\n'
                       u'Revisa que el modelo federado (host + links) coincida '
                       u'con el usado al generar el reporte de Navisworks.'
                       % (total - skipped, total, skipped))
                try:
                    from System.Windows.Forms import MethodInvoker
                    self.form.BeginInvoke(MethodInvoker(lambda: self.form.show_error(msg)))
                except Exception:
                    pass
        finally:
            self.is_scanning = False
            self.xml_path = None
            if self.form:
                try:
                    from System.Windows.Forms import MethodInvoker
                    self.form.BeginInvoke(MethodInvoker(self.form._on_scan_finished))
                except Exception:
                    pass

    # ── Guardar XML (escribe statuses de vuelta al Navisworks XML) ─────────────
    def _execute_save_xml(self):
        self.is_scanning = True
        try:
            from bim_clash.xml_importer import save_statuses_to_xml
            records = [r for r in self.state.records() if r.key.startswith('xml:')]
            updated = save_statuses_to_xml(self.last_xml_path, records)
            if self.form:
                msg = (u'Se actualizaron %d conflictos en:\n%s\n\n'
                       u'(Se guardo un respaldo .bak del archivo original la '
                       u'primera vez que se escribio.)' % (updated, self.last_xml_path))
                try:
                    from System.Windows.Forms import MethodInvoker
                    self.form.BeginInvoke(MethodInvoker(lambda: self.form.show_error(msg)))
                except Exception:
                    pass
        finally:
            self.is_scanning = False
            if self.form:
                try:
                    from System.Windows.Forms import MethodInvoker
                    self.form.BeginInvoke(MethodInvoker(self.form._on_scan_finished))
                except Exception:
                    pass

    # ── Select ────────────────────────────────────────────────────────────────
    def _execute_select(self, uiapp, zoom=True):
        record = self.selected_record
        if record is None:
            return

        uidoc = uiapp.ActiveUIDocument
        if uidoc is None:
            return
        doc = uidoc.Document

        # ── Auto-reset isolate al cambiar de conflicto ──────────────────────
        # Si el isolate estaba activo para un conflicto distinto al que ahora
        # se selecciona, se desactiva automáticamente (en una sola transacción)
        # para que el usuario pueda ver el nuevo conflicto sin tener que
        # apagarlo a mano.
        st_iso = self._isolate_state
        if st_iso is not None and st_iso.get('key') != record.key:
            try:
                iso_view = doc.GetElement(ElementId(st_iso['view_id']))
                if iso_view is not None and iso_view.IsTemporaryHideIsolateActive():
                    t_reset = Transaction(doc, 'ClashLiveMix - Quitar aislamiento al cambiar conflicto')
                    t_reset.Start()
                    try:
                        iso_view.DisableTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate)
                        t_reset.Commit()
                    except Exception:
                        t_reset.RollBack()
            except Exception:
                pass
            self._isolate_state = None
            # Notificar a la UI para que el botón ISOLATE se apague
            if self.form:
                try:
                    from System.Windows.Forms import MethodInvoker
                    self.form.BeginInvoke(MethodInvoker(self.form._update_tool_button_states))
                except Exception:
                    pass

        try:
            view = uidoc.ActiveView
            if view is not None:
                self._highlight_record(doc, view, record)
        except Exception:
            pass

        if self.select_target == 'source':
            # Elemento A — siempre host model, selección directa
            if record.source_doc != doc.Title:
                if self.form:
                    self.form.show_error(
                        'Element A belongs to "%s".\nOpen that document first.' % record.source_doc)
                return
            eid = ElementId(record.source_id)
            ids = List[ElementId]()
            ids.Add(eid)
            uidoc.Selection.SetElementIds(ids)
            if zoom:
                uidoc.ShowElements(eid)

        else:
            # Elemento B
            if not record.is_linked:
                # Mismo modelo — selección directa normal
                eid = ElementId(record.target_id)
                ids = List[ElementId]()
                ids.Add(eid)
                uidoc.Selection.SetElementIds(ids)
                if zoom:
                    uidoc.ShowElements(eid)
            else:
                # Modelo linkeado.
                # Usamos Reference.CreateReferenceToLinkedInstance para construir
                # una referencia al elemento exacto dentro del link — igual que
                # lo que devuelve PickObject(ObjectType.LinkedElement).
                # Esto permite SelectionSetReferences (selección visual exacta)
                # + ShowElements al elemento, no al link completo.
                link_instance = self._find_link_instance(doc, record.target_doc)
                if link_instance is None:
                    if self.form:
                        self.form.show_error(
                            'Could not find linked model %s.' % record.target_doc)
                    return

                linked_doc = link_instance.GetLinkDocument()
                if linked_doc is None:
                    return

                target_eid = ElementId(record.target_id)
                link_element = linked_doc.GetElement(target_eid)
                if link_element is None:
                    return

                # Selección exacta del elemento dentro del link.
                # Método 1: CreateLinkReference — equivalente a PickObject(LinkedElement).
                # Método 2: ParseFromStableRepresentation — fallback si el primero falla.
                selected = False
                try:
                    from Autodesk.Revit.DB import Reference
                    from System.Collections.Generic import List as CsList

                    linked_ref = Reference(link_element).CreateLinkReference(link_instance)
                    refs = CsList[Reference]()
                    refs.Add(linked_ref)
                    uidoc.Selection.SetReferences(refs)
                    selected = True
                except Exception:
                    pass

                if not selected:
                    try:
                        from Autodesk.Revit.DB import Reference
                        from System.Collections.Generic import List as CsList

                        link_unique_id    = link_instance.UniqueId
                        element_unique_id = link_element.UniqueId
                        stable = '%s:0:RVTLINK:%s:0:' % (link_unique_id, element_unique_id)
                        ref  = Reference.ParseFromStableRepresentation(doc, stable)
                        refs = CsList[Reference]()
                        refs.Add(ref)
                        uidoc.Selection.SetReferences(refs)
                        selected = True
                    except Exception:
                        pass

                if not selected:
                    if self.form:
                        self.form.show_error(
                            'No se pudo seleccionar el elemento linked ID %d.\n'
                            'El elemento existe en el link pero la referencia no pudo construirse.'
                            % record.target_id)

                # Zoom al bbox del elemento en coordenadas del host
                if zoom:
                    world_min, world_max = self._element_world_bbox(
                        link_element, link_instance.GetTotalTransform())
                    if world_min is not None:
                        self._zoom_to_points(uidoc, world_min, world_max)

    # ── Resaltado por color (Elemento A / Elemento B) ───────────────────────────
    def _get_solid_fill_pattern_id(self, doc):
        if self._solid_fill_id is not None:
            return self._solid_fill_id
        try:
            patterns = FilteredElementCollector(doc).OfClass(FillPatternElement)
            for fp in patterns:
                try:
                    if fp.GetFillPattern().IsSolidFill:
                        self._solid_fill_id = fp.Id
                        break
                except Exception:
                    continue
        except Exception:
            pass
        return self._solid_fill_id

    def _build_override(self, doc, color):
        ogs = OverrideGraphicSettings()
        solid = self._get_solid_fill_pattern_id(doc)
        if solid is not None:
            ogs.SetSurfaceForegroundPatternVisible(True)
            ogs.SetSurfaceForegroundPatternId(solid)
            ogs.SetSurfaceForegroundPatternColor(color)
            ogs.SetCutForegroundPatternVisible(True)
            ogs.SetCutForegroundPatternId(solid)
            ogs.SetCutForegroundPatternColor(color)
        # Líneas de proyección siempre en negro — solo el relleno de superficie/
        # corte y la línea de corte usan el color de acento (azul/naranja).
        ogs.SetProjectionLineColor(_COLOR_BLACK)
        ogs.SetCutLineColor(color)
        return ogs

    def _clear_highlight(self, doc):
        """Quita el override de color de lo que haya quedado pintado del conflicto anterior."""
        if not self._highlighted_ids:
            return
        view = None
        if self._highlighted_view_id is not None:
            try:
                view = doc.GetElement(self._highlighted_view_id)
            except Exception:
                view = None
        if view is not None:
            empty = OverrideGraphicSettings()
            t = Transaction(doc, 'ClashLiveMix - Limpiar resaltado')
            t.Start()
            try:
                for eid in self._highlighted_ids:
                    try:
                        view.SetElementOverrides(eid, empty)
                    except Exception:
                        pass
                t.Commit()
            except Exception:
                t.RollBack()
        self._highlighted_ids = []
        if self.state is not None:
            self.state.clear_highlight()

    def _highlight_record(self, doc, view, record):
        """
        Colorea el Elemento A (azul) y el Elemento B (naranja) del conflicto
        seleccionado en la tabla, y limpia el resaltado del conflicto anterior.
        Si el Elemento B viene de un modelo vinculado, no se colorea (su
        ElementId pertenece al documento del link, no a `doc`).
        """
        self._clear_highlight(doc)

        targets = [(record.source_id, _COLOR_SOURCE)]
        if not record.is_linked:
            targets.append((record.target_id, _COLOR_TARGET))

        new_ids = []
        t = Transaction(doc, 'ClashLiveMix - Resaltar conflicto')
        t.Start()
        try:
            for eid_int, color in targets:
                eid = ElementId(eid_int)
                if doc.GetElement(eid) is None:
                    continue
                try:
                    view.SetElementOverrides(eid, self._build_override(doc, color))
                    new_ids.append(eid)
                except Exception:
                    pass
            t.Commit()
        except Exception:
            t.RollBack()
            return

        self._highlighted_view_id = view.Id
        self._highlighted_ids     = new_ids
        if self.state is not None:
            self.state.set_highlight(view.Id.IntegerValue, [e.IntegerValue for e in new_ids])

    # ── Marcar punto exacto del conflicto (esfera temporal) ─────────────────────
    def _delete_markers(self, doc, int_ids):
        """Borra (si existen) los elementos con esos ElementId enteros."""
        if not int_ids:
            return
        t = Transaction(doc, 'ClashLiveMix - Quitar punto temporal')
        t.Start()
        try:
            for i in int_ids:
                try:
                    eid = ElementId(int(i))
                    if doc.GetElement(eid) is not None:
                        doc.Delete(eid)
                except Exception:
                    pass
            t.Commit()
        except Exception:
            t.RollBack()

    def _clear_markers(self, doc):
        """Quita la esfera temporal actual (si hay) y olvida el registro persistido."""
        ids = [e.IntegerValue for e in self._marker_ids]
        self._marker_ids = []
        try:
            self._delete_markers(doc, ids)
        finally:
            if self.state is not None:
                self.state.clear_markers()

    def _record_ref_bboxes(self, doc, record):
        """bbox (min, max) en coordenadas del host de los elementos A y B del conflicto."""
        boxes = []
        for eid_int, doc_title in ((record.source_id, record.source_doc),
                                   (record.target_id, record.target_doc)):
            try:
                if doc_title == doc.Title:
                    el = doc.GetElement(ElementId(eid_int))
                    tr = None
                else:
                    link = self._find_link_instance(doc, doc_title)
                    if link is None:
                        continue
                    ldoc = link.GetLinkDocument()
                    el = ldoc.GetElement(ElementId(eid_int)) if ldoc is not None else None
                    tr = link.GetTotalTransform()
                if el is None:
                    continue
                if tr is None:
                    bb = el.get_BoundingBox(None)
                    if bb is not None:
                        boxes.append((bb.Min, bb.Max))
                else:
                    mn, mx = self._element_world_bbox(el, tr)
                    if mn is not None:
                        boxes.append((mn, mx))
            except Exception:
                pass
        return boxes

    @staticmethod
    def _dist_to_bbox(p, mn, mx):
        dx = max(mn.X - p.X, 0.0, p.X - mx.X)
        dy = max(mn.Y - p.Y, 0.0, p.Y - mx.Y)
        dz = max(mn.Z - p.Z, 0.0, p.Z - mx.Z)
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def _report_point_to_internal(self, doc, record):
        """
        El clashpoint del XML viene en coordenadas del reporte (aquí MAGNA-SIRGAS,
        p.ej. X≈4.7e6 m), no en coordenadas internas de Revit. Se prueban las
        posibles conversiones (sin transformar / con la transformación de
        coordenadas compartidas del proyecto en ambos sentidos) y se elige la que
        deja el punto pegado a los elementos A y B. Devuelve (XYZ, distancia_ft).
        """
        raw = XYZ(record.point[0], record.point[1], record.point[2])
        candidates = [raw]
        try:
            total = doc.ActiveProjectLocation.GetTotalTransform()
            candidates.append(total.Inverse.OfPoint(raw))
            candidates.append(total.OfPoint(raw))
        except Exception:
            pass

        boxes = self._record_ref_bboxes(doc, record)
        if not boxes:
            raise Exception(u'No se pudo verificar la ubicacion: los elementos del conflicto '
                            u'no se encontraron en el documento activo ni en sus links.')

        best, best_score = None, None
        for c in candidates:
            score = sum(self._dist_to_bbox(c, mn, mx) for mn, mx in boxes)
            if best_score is None or score < best_score:
                best, best_score = c, score
        return best, best_score

    def _make_sphere_solid(self, center, radius):
        """Esfera sólida: semicírculo en el plano XZ girado 360° alrededor del eje Z."""
        top    = XYZ(center.X, center.Y, center.Z + radius)
        bottom = XYZ(center.X, center.Y, center.Z - radius)
        mid    = XYZ(center.X + radius, center.Y, center.Z)
        loop = CurveLoop()
        loop.Append(Line.CreateBound(top, bottom))
        loop.Append(Arc.Create(bottom, top, mid))
        frame = Frame(center, XYZ.BasisX, XYZ.BasisY, XYZ.BasisZ)
        options = SolidOptions(ElementId.InvalidElementId, ElementId.InvalidElementId)
        loops = List[CurveLoop]()
        loops.Add(loop)
        return GeometryCreationUtilities.CreateRevolvedGeometry(
            frame, loops, 0.0, 2.0 * math.pi, options)

    def _pick_marker_category(self, doc, view):
        """Masas si es posible y visible en la vista; si no, Modelos genéricos."""
        for bic in (BuiltInCategory.OST_Mass, BuiltInCategory.OST_GenericModel):
            cid = ElementId(bic)
            try:
                if not DirectShape.IsValidCategoryId(cid, doc):
                    continue
                if view is not None and view.GetCategoryHidden(cid):
                    continue
            except Exception:
                pass
            return cid
        return ElementId(BuiltInCategory.OST_GenericModel)

    def _execute_mark_point(self, uiapp):
        record = self.selected_record
        uidoc = uiapp.ActiveUIDocument
        if record is None or uidoc is None:
            return
        if not getattr(record, 'point', None):
            raise Exception(u'Este conflicto no trae coordenada de punto (solo disponible '
                            u'en conflictos importados desde XML).')
        doc  = uidoc.Document
        view = uidoc.ActiveView

        center, dist = self._report_point_to_internal(doc, record)
        if dist > _MARKER_MAX_DIST_FT:
            raise Exception(
                u'El punto del XML no cae cerca de los elementos del conflicto '
                u'(mejor conversion probada a %.1f ft). Puede que el reporte de '
                u'Navisworks use otro origen/coordenadas que este modelo, y por eso '
                u'no se creo la esfera.' % dist)

        # Una sola esfera temporal a la vez: quita la anterior.
        self._clear_markers(doc)

        t = Transaction(doc, 'ClashLiveMix - Punto del conflicto')
        t.Start()
        try:
            sphere = self._make_sphere_solid(center, _MARKER_RADIUS_FT)
            cat_id = self._pick_marker_category(doc, view)
            ds = DirectShape.CreateElement(doc, cat_id)
            ds.ApplicationId     = 'BimClash'
            ds.ApplicationDataId = 'ClashPointMarker'
            shapes = List[GeometryObject]()
            shapes.Add(sphere)
            ds.SetShape(shapes)
            try:
                p = ds.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
                if p is not None and not p.IsReadOnly:
                    p.Set(u'TEMP Clash %s x %s' % (record.source_id, record.target_id))
            except Exception:
                pass
            if view is not None:
                try:
                    view.SetElementOverrides(ds.Id, self._build_override(doc, _COLOR_MARKER))
                except Exception:
                    pass
            t.Commit()
        except Exception:
            t.RollBack()
            raise

        self._marker_ids = [ds.Id]
        if self.state is not None:
            self.state.set_markers([ds.Id.IntegerValue])

        try:
            ids = List[ElementId]()
            ids.Add(ds.Id)
            uidoc.Selection.SetElementIds(ids)
            uidoc.ShowElements(ds.Id)
        except Exception:
            pass

    # ── Section Box / Isolate sobre los dos elementos del conflicto ─────────────
    def _find_3d_view(self, doc):
        """Vista 3D no plantilla y no perspectiva; prefiere la {3D} por defecto."""
        best = None
        for v in FilteredElementCollector(doc).OfClass(View3D).ToElements():
            try:
                if v.IsTemplate or v.IsPerspective:
                    continue
                if v.Name == '{3D}':
                    return v
                if best is None:
                    best = v
            except Exception:
                pass
        return best

    def _restore_section_box(self, doc):
        """Devuelve el Section Box de la vista a como estaba antes de aplicarlo."""
        st = self._section_state
        self._section_state = None
        if not st:
            return
        try:
            view = doc.GetElement(ElementId(st['view_id']))
        except Exception:
            view = None
        if view is None:
            return
        t = Transaction(doc, 'ClashLiveMix - Restaurar Section Box')
        t.Start()
        try:
            if st['box'] is not None:
                view.SetSectionBox(st['box'])
            view.IsSectionBoxActive = st['was_active']
            t.Commit()
        except Exception:
            t.RollBack()

    def _execute_section_box(self, uiapp):
        """
        Section Box en la vista 3D ajustado a la caja de A + B (con margen).
        Segundo clic sobre el mismo conflicto = lo quita y restaura el estado previo.
        Funciona igual si A o B están en un link (usa el bbox ya transformado al host).
        """
        record = self.selected_record
        uidoc = uiapp.ActiveUIDocument
        if record is None or uidoc is None:
            return
        doc  = uidoc.Document
        view = uidoc.ActiveView

        if not (isinstance(view, View3D) and not view.IsPerspective):
            view = self._find_3d_view(doc)
            if view is None:
                raise Exception(u'No hay una vista 3D (no perspectiva) para aplicar el Section Box.')
            uidoc.ActiveView = view

        vid = view.Id.IntegerValue
        st  = self._section_state
        if st and st['view_id'] == vid and st['key'] == record.key:
            self._restore_section_box(doc)     # toggle: quitar
            return
        if st and st['view_id'] != vid:
            self._restore_section_box(doc)     # había uno en otra vista: se deja como estaba
            st = None

        boxes = self._record_ref_bboxes(doc, record)
        if not boxes:
            raise Exception(u'No se encontraron los elementos del conflicto para calcular el Section Box.')
        pad = _SECTION_PAD_FT
        bb = BoundingBoxXYZ()
        bb.Min = XYZ(min(b[0].X for b in boxes) - pad,
                     min(b[0].Y for b in boxes) - pad,
                     min(b[0].Z for b in boxes) - pad)
        bb.Max = XYZ(max(b[1].X for b in boxes) + pad,
                     max(b[1].Y for b in boxes) + pad,
                     max(b[1].Z for b in boxes) + pad)

        if st:   # mismo view, otro conflicto: se conserva el estado ORIGINAL previo
            was_active, old_box = st['was_active'], st['box']
        else:
            was_active = view.IsSectionBoxActive
            try:
                old_box = view.GetSectionBox()
            except Exception:
                old_box = None

        t = Transaction(doc, 'ClashLiveMix - Section Box del conflicto')
        t.Start()
        try:
            view.SetSectionBox(bb)
            view.IsSectionBoxActive = True
            t.Commit()
        except Exception:
            t.RollBack()
            raise

        self._section_state = {'view_id': vid, 'key': record.key,
                               'was_active': was_active, 'box': old_box}
        try:
            for uiv in uidoc.GetOpenUIViews():
                if uiv.ViewId == view.Id:
                    uiv.ZoomAndCenterRectangle(bb.Min, bb.Max)
                    break
        except Exception:
            pass

    def _execute_isolate(self, uiapp):
        """
        Aislamiento temporal (Isolate Elements) de A y B en la vista activa.
        Segundo clic sobre el mismo conflicto = lo quita.
        Un elemento dentro de un link no se puede aislar solo: se aísla su
        RevitLinkInstance (el link completo). La esfera de "Marcar punto" se
        mantiene visible si existe.
        """
        record = self.selected_record
        uidoc = uiapp.ActiveUIDocument
        if record is None or uidoc is None:
            return
        doc  = uidoc.Document
        view = uidoc.ActiveView

        try:
            can_isolate = view.CanUseTemporaryVisibilityModes()
        except Exception:
            can_isolate = False
        if not can_isolate:
            raise Exception(u'La vista activa no admite aislamiento temporal '
                            u'(usa una vista de modelo: 3D, planta, corte, etc.).')

        vid    = view.Id.IntegerValue
        active = view.IsTemporaryHideIsolateActive()
        st     = self._isolate_state

        if active and st and st['view_id'] == vid and st['key'] == record.key:
            t = Transaction(doc, 'ClashLiveMix - Quitar aislamiento')
            t.Start()
            try:
                view.DisableTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate)
                t.Commit()
            except Exception:
                t.RollBack()
                raise
            self._isolate_state = None
            return

        ids  = List[ElementId]()
        seen = set()
        for eid_int, doc_title in ((record.source_id, record.source_doc),
                                   (record.target_id, record.target_doc)):
            if doc_title == doc.Title:
                target = ElementId(eid_int)
            else:
                link = self._find_link_instance(doc, doc_title)
                if link is None:
                    continue
                target = link.Id
            if target.IntegerValue not in seen:
                seen.add(target.IntegerValue)
                ids.Add(target)
        for m in self._marker_ids:
            try:
                if doc.GetElement(m) is not None and m.IntegerValue not in seen:
                    seen.add(m.IntegerValue)
                    ids.Add(m)
            except Exception:
                pass
        if ids.Count == 0:
            raise Exception(u'No se encontraron los elementos del conflicto en este documento ni en sus links.')

        t = Transaction(doc, 'ClashLiveMix - Aislar conflicto')
        t.Start()
        try:
            if active:
                view.DisableTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate)
            view.IsolateElementsTemporary(ids)
            t.Commit()
        except Exception:
            t.RollBack()
            raise
        self._isolate_state = {'view_id': vid, 'key': record.key}

    def _reset_view_tools(self, doc):
        """Al cerrar el Manager: quita el Section Box y el aislamiento que él aplicó."""
        try:
            self._restore_section_box(doc)
        except Exception:
            pass
        st = self._isolate_state
        self._isolate_state = None
        if not st:
            return
        try:
            view = doc.GetElement(ElementId(st['view_id']))
            if view is not None and view.IsTemporaryHideIsolateActive():
                t = Transaction(doc, 'ClashLiveMix - Quitar aislamiento')
                t.Start()
                try:
                    view.DisableTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate)
                    t.Commit()
                except Exception:
                    t.RollBack()
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _find_link_instance(self, doc, target_doc_title):
        links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
        for link in links:
            try:
                linked_doc = link.GetLinkDocument()
                if linked_doc is not None and linked_doc.Title == target_doc_title:
                    return link
            except Exception:
                pass
        return None

    def _element_world_bbox(self, element, transform):
        """
        Devuelve (min_xyz, max_xyz) del elemento en coordenadas del host,
        aplicando el transform del link. Retorna (None, None) si falla.
        """
        try:
            bbox = element.get_BoundingBox(None)
            if bbox is None:
                return None, None

            # Las 8 esquinas del bbox en espacio local del link
            mn, mx = bbox.Min, bbox.Max
            corners = [
                XYZ(mn.X, mn.Y, mn.Z), XYZ(mn.X, mn.Y, mx.Z),
                XYZ(mn.X, mx.Y, mn.Z), XYZ(mn.X, mx.Y, mx.Z),
                XYZ(mx.X, mn.Y, mn.Z), XYZ(mx.X, mn.Y, mx.Z),
                XYZ(mx.X, mx.Y, mn.Z), XYZ(mx.X, mx.Y, mx.Z),
            ]

            # Transformar a coordenadas del host
            world = [transform.OfPoint(c) for c in corners]

            world_min = XYZ(
                min(p.X for p in world),
                min(p.Y for p in world),
                min(p.Z for p in world),
            )
            world_max = XYZ(
                max(p.X for p in world),
                max(p.Y for p in world),
                max(p.Z for p in world),
            )
            return world_min, world_max
        except Exception:
            return None, None

    def _zoom_to_points(self, uidoc, world_min, world_max):
        """
        Hace zoom a la región definida por world_min / world_max
        usando ZoomAndCenterRectangle en todas las vistas abiertas activas.
        Si falla (vista no es plana o no soporta el método), no hace nada.
        """
        try:
            # Agregar un padding del 20 % alrededor del elemento
            pad_x = max((world_max.X - world_min.X) * 0.20, 0.5)
            pad_y = max((world_max.Y - world_min.Y) * 0.20, 0.5)

            corner1 = XYZ(world_min.X - pad_x, world_min.Y - pad_y, world_min.Z)
            corner2 = XYZ(world_max.X + pad_x, world_max.Y + pad_y, world_max.Z)

            ui_views = uidoc.GetOpenUIViews()
            for uiv in ui_views:
                try:
                    uiv.ZoomAndCenterRectangle(corner1, corner2)
                    break   # zoom a la primera vista activa es suficiente
                except Exception:
                    pass
        except Exception:
            pass