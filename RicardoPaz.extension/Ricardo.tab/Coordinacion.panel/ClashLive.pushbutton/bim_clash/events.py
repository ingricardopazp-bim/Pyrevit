# -*- coding: utf-8 -*-
from __future__ import absolute_import

import clr


clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import ElementId, RevitLinkInstance, FilteredElementCollector, XYZ
from Autodesk.Revit.UI import IExternalEventHandler
from System.Collections.Generic import List


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
        except Exception as err:
            if self.logger:
                self.logger.error(err)
            if self.form:
                self.form.show_error(str(err))
        finally:
            self.action = None

    def request_scan(self, include_links):
        if self.is_scanning:
            return False
        self.include_links = include_links
        self.action = 'scan'
        return True

    def abort_scan(self):
        """Cancela el scan en curso activando el flag en el detector."""
        self.detector.abort_flag = True

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

    # ── Select ────────────────────────────────────────────────────────────────
    def _execute_select(self, uiapp, zoom=True):
        record = self.selected_record
        if record is None:
            return

        uidoc = uiapp.ActiveUIDocument
        if uidoc is None:
            return
        doc = uidoc.Document

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