# -*- coding: utf-8 -*-
"""
detector.py — Motor de interferencias BIM de alto rendimiento con auditoría de Worksets.
"""
from __future__ import absolute_import

import clr
import math

clr.AddReference('System')
from System.Collections.Generic import List as CList

from Autodesk.Revit.DB import (
    BooleanOperationsType,
    BooleanOperationsUtils,
    BoundingBoxIntersectsFilter,
    ElementCategoryFilter,
    ElementFilter,
    FilteredElementCollector,
    GeometryInstance,
    ImportInstance,
    LogicalOrFilter,
    Options,
    Outline,
    RevitLinkInstance,
    Solid,
    SolidUtils,
    TemporaryViewMode,
    ViewDetailLevel,
    WorksetVisibility,
    XYZ,
)

from bim_clash.config import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_MIN_VOLUME_FT3,
    EXCLUDED_CATEGORY_IDS,
    EXCLUDED_CATEGORY_NAMES,
    default_categories,
)
from bim_clash.models import ClashRecord, ClashStatus, ClashType


# ─── Helpers de elemento y Visibilidad ────────────────────────────────────────

def _cat_name(element):
    try:
        return element.Category.Name if element.Category else u'Unknown'
    except Exception:
        return u'Unknown'


def _elem_name(element):
    try:
        n = element.Name
        if n:
            return n
    except Exception:
        pass
    return element.GetType().Name


def _is_excluded(element, view=None):
    """
    Filtro absoluto. Descarta elementos por ID, Categoría, y lo más importante:
    Visibilidad en la Vista Activa, Categorías apagadas en VG y Worksets cerrados/apagados.
    """
    try:
        if isinstance(element, ImportInstance):
            return True
    except Exception:
        pass

    cat = None
    try:
        cat = element.Category
    except Exception:
        pass
    
    if cat is None:
        return True

    # 1. Filtros duros por configuración interna
    try:
        cid = cat.Id.IntegerValue
        if cid in EXCLUDED_CATEGORY_IDS:
            return True
        if cat.Name in EXCLUDED_CATEGORY_NAMES:
            return True
    except Exception:
        pass

    # 🔥 2. FILTRO ESTRICTO DE VISIBILIDAD (Worksets, VG y Ocultos)
    if view is not None:
        # a) ¿La Categoría está apagada en VG? (Aplica a modelo activo y links)
        try:
            if view.GetCategoryHidden(cat.Id):
                return True
        except Exception:
            pass

        doc = element.Document
        
        # b) ¿El Workset del elemento está CERRADO globalmente? (No cargado)
        try:
            wt = doc.GetWorksetTable()
            if wt is not None:
                ws = wt.GetWorkset(element.WorksetId)
                if ws is not None and not ws.IsOpen:
                    return True
        except Exception:
            pass

        # c) ¿Oculto manualmente en la vista? — aplica a host Y a elementos de links
        #    IsHidden(view) funciona correctamente sobre el documento del elemento,
        #    independientemente de si ese documento es el host o un modelo vinculado.
        try:
            if element.IsHidden(view):
                return True
        except Exception:
            pass

        # d) ¿El Workset está apagado en VG para esta vista?
        #    Solo aplica al modelo activo (host); la vista host no tiene
        #    información de worksets de documentos linkeados.
        if not doc.IsLinked:
            try:
                if view.GetWorksetVisibility(element.WorksetId) == WorksetVisibility.Hidden:
                    return True
            except Exception:
                pass

    return False


# ─── Extracción de geometría con caché ────────────────────────────────────────

_GEOM_OPTIONS = None

def _geom_options():
    global _GEOM_OPTIONS
    if _GEOM_OPTIONS is None:
        opt = Options()
        opt.ComputeReferences        = False
        opt.IncludeNonVisibleObjects = False
        opt.DetailLevel              = ViewDetailLevel.Fine
        _GEOM_OPTIONS = opt
    return _GEOM_OPTIONS


def _collect_solids_recursive(geo_obj_iter, out_list):
    for obj in geo_obj_iter:
        if isinstance(obj, Solid):
            try:
                if obj.Volume > 1e-9:
                    out_list.append(obj)
            except Exception:
                pass
        elif isinstance(obj, GeometryInstance):
            try:
                _collect_solids_recursive(obj.GetInstanceGeometry(), out_list)
            except Exception:
                pass


def _solids_from_element(element, solid_cache):
    eid = element.Id.IntegerValue
    if eid in solid_cache:
        return solid_cache[eid]
    solids = []
    try:
        geo = element.get_Geometry(_geom_options())
        if geo is not None:
            _collect_solids_recursive(geo, solids)
    except Exception:
        pass
    solid_cache[eid] = solids
    return solids


# ─── Cálculo de intersección booleana ─────────────────────────────────────────

def _boolean_intersection_volume(solids_a, solids_b, transform_b=None):
    if not solids_a or not solids_b:
        return None

    total  = 0.0
    any_ok = False

    for sa in solids_a:
        for sb in solids_b:
            try:
                sb_work = sb
                if transform_b is not None:
                    sb_work = SolidUtils.CreateTransformed(sb, transform_b)
                result = BooleanOperationsUtils.ExecuteBooleanOperation(
                    sa, sb_work, BooleanOperationsType.Intersect)
                any_ok = True
                if result is not None:
                    v = result.Volume
                    if v and v > 0:
                        total += v
            except Exception:
                pass

    return total if any_ok else None


# ─── BoundingBox helpers ───────────────────────────────────────────────────────

def _bbox(element, transform=None):
    try:
        bb = element.get_BoundingBox(None)
        if bb is None:
            return None, None
        pts = [
            XYZ(bb.Min.X, bb.Min.Y, bb.Min.Z),
            XYZ(bb.Min.X, bb.Min.Y, bb.Max.Z),
            XYZ(bb.Min.X, bb.Max.Y, bb.Min.Z),
            XYZ(bb.Min.X, bb.Max.Y, bb.Max.Z),
            XYZ(bb.Max.X, bb.Min.Y, bb.Min.Z),
            XYZ(bb.Max.X, bb.Min.Y, bb.Max.Z),
            XYZ(bb.Max.X, bb.Max.Y, bb.Min.Z),
            XYZ(bb.Max.X, bb.Max.Y, bb.Max.Z),
        ]
        if transform is not None:
            pts = [transform.OfPoint(p) for p in pts]
        mn = XYZ(min(p.X for p in pts), min(p.Y for p in pts), min(p.Z for p in pts))
        mx = XYZ(max(p.X for p in pts), max(p.Y for p in pts), max(p.Z for p in pts))
        return mn, mx
    except Exception:
        return None, None


def _bbox_diagonal(mn, mx):
    dx = mx.X - mn.X
    dy = mx.Y - mn.Y
    dz = mx.Z - mn.Z
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def _outline(mn, mx, tol=0.0):
    try:
        return Outline(
            XYZ(mn.X - tol, mn.Y - tol, mn.Z - tol),
            XYZ(mx.X + tol, mx.Y + tol, mx.Z + tol),
        )
    except Exception:
        return None


def _bboxes_overlap(mn_a, mx_a, mn_b, mx_b):
    return (mn_a.X <= mx_b.X and mx_a.X >= mn_b.X and
            mn_a.Y <= mx_b.Y and mx_a.Y >= mn_b.Y and
            mn_a.Z <= mx_b.Z and mx_a.Z >= mn_b.Z)

def _get_overall_outline(elements):
    overall_mn, overall_mx = None, None
    for e in elements:
        mn, mx = _bbox(e)
        if mn is None:
            continue
        if overall_mn is None:
            overall_mn = XYZ(mn.X, mn.Y, mn.Z)
            overall_mx = XYZ(mx.X, mx.Y, mx.Z)
        else:
            overall_mn = XYZ(min(overall_mn.X, mn.X), min(overall_mn.Y, mn.Y), min(overall_mn.Z, mn.Z))
            overall_mx = XYZ(max(overall_mx.X, mx.X), max(overall_mx.Y, mx.Y), max(overall_mx.Z, mx.Z))
    return overall_mn, overall_mx


# ─── Spatial Hash Grid ────────────────────────────────────────────────────────

class SpatialHashGrid(object):
    def __init__(self, cell_size):
        self._cell  = float(cell_size)
        self._grid  = {}
        self._items = []

    def _cells_for_box(self, mn, mx):
        cs = self._cell
        x0 = int(math.floor(mn.X / cs))
        y0 = int(math.floor(mn.Y / cs))
        z0 = int(math.floor(mn.Z / cs))
        x1 = int(math.floor(mx.X / cs))
        y1 = int(math.floor(mx.Y / cs))
        z1 = int(math.floor(mx.Z / cs))
        cells = []
        for ix in range(x0, x1 + 1):
            for iy in range(y0, y1 + 1):
                for iz in range(z0, z1 + 1):
                    cells.append((ix, iy, iz))
        return cells

    def insert(self, element, mn, mx):
        idx = len(self._items)
        self._items.append((element, mn, mx))
        for cell in self._cells_for_box(mn, mx):
            if cell not in self._grid:
                self._grid[cell] = []
            self._grid[cell].append(idx)

    def query(self, mn, mx):
        seen_idx = set()
        result   = []
        for cell in self._cells_for_box(mn, mx):
            for idx in self._grid.get(cell, []):
                if idx not in seen_idx:
                    seen_idx.add(idx)
                    item = self._items[idx]
                    if _bboxes_overlap(mn, mx, item[1], item[2]):
                        result.append(item)
        return result


def _build_grid(elements, bbox_cache):
    diagonals = []
    for elem in elements:
        mn, mx = _bbox(elem)
        eid = elem.Id.IntegerValue
        bbox_cache[eid] = (mn, mx)
        if mn is not None:
            d = _bbox_diagonal(mn, mx)
            if d > 0:
                diagonals.append(d)

    if not diagonals:
        return None, bbox_cache

    diagonals.sort()
    cell_size = max(diagonals[len(diagonals) // 2], 0.1)

    grid = SpatialHashGrid(cell_size)
    for elem in elements:
        eid = elem.Id.IntegerValue
        mn, mx = bbox_cache[eid]
        if mn is not None:
            grid.insert(elem, mn, mx)

    return grid, bbox_cache


# ─── Clave de par (sin duplicados) ────────────────────────────────────────────

def _pair_key(doc_a, id_a, doc_b, id_b):
    left  = '%s:%d' % (doc_a, id_a)
    right = '%s:%d' % (doc_b, id_b)
    if left > right:
        left, right = right, left
    return '%s|%s' % (left, right)


# ─── Filtro de categorías ──────────────────────────────────────────────────────

def _make_category_filter(categories):
    filters = []
    for bic in categories:
        try:
            filters.append(ElementCategoryFilter(bic))
        except Exception:
            pass

    if not filters:
        from Autodesk.Revit.DB import BuiltInCategory
        try:
            filters.append(ElementCategoryFilter(BuiltInCategory.OST_GenericModel))
        except Exception:
            pass

    if len(filters) == 1:
        return filters[0]

    col = CList[ElementFilter]()
    for f in filters:
        col.Add(f)
    return LogicalOrFilter(col)


# ─── Colector de candidatos ────────────────────────────────────────────────────

def _collect_elements(doc, categories, view=None, outline=None):
    cat_filter = _make_category_filter(categories)
    try:
        # 🔥 CORRECCIÓN CLAVE: Usamos 'not doc.IsLinked' en lugar de 'doc.Equals()'
        if view is not None and not doc.IsLinked:
            collector = FilteredElementCollector(doc, view.Id)
        else:
            collector = FilteredElementCollector(doc)
            
        collector.WherePasses(cat_filter).WhereElementIsNotElementType()
        
        # Filtro opcional por Outline
        if outline is not None:
            collector.WherePasses(BoundingBoxIntersectsFilter(outline))
            
        elements = list(collector.ToElements())
    except Exception:
        elements = []

    # Se pasa la vista a _is_excluded para forzar la exclusión por Worksets y VG
    return [e for e in elements if not _is_excluded(e, view)]


# ─── Motor principal ───────────────────────────────────────────────────────────

class ClashDetector(object):

    def __init__(self, doc, categories=None,
                 min_volume=DEFAULT_MIN_VOLUME_FT3,
                 max_results=DEFAULT_MAX_RESULTS):
        self.doc          = doc
        self.categories   = categories or default_categories()
        self.min_volume   = min_volume
        self.max_results  = max_results
        self._cat_filter  = _make_category_filter(self.categories)
        self._active_view = None
        self.abort_flag   = False   # poner a True para cancelar el scan en curso

    # ── API pública ──────────────────────────────────────────────────────────

    def scan(self, include_links=True, selected_ids=None, view=None,
             max_results=None, prev_statuses=None):
        self.abort_flag   = False
        if max_results is not None:
            self.max_results = max_results
        self.prev_statuses = prev_statuses if prev_statuses is not None else {}
        self.active_count  = 0
        records           = []
        seen              = set()
        solid_cache       = {}
        self._active_view = view

        sel_list = []
        if selected_ids is not None:
            try:
                sel_list = [eid for eid in selected_ids]
            except Exception:
                sel_list = []

        # 1. Definir los elementos anfitriones
        if sel_list:
            host_elements = self._selected_elements(sel_list)
        else:
            host_elements = _collect_elements(self.doc, self.categories, view)

        if not host_elements:
            return records

        # 2. Definir el entorno objetivo 
        target_elements = _collect_elements(self.doc, self.categories, view)

        # 3. Escaneo interno
        records = self._scan_host(host_elements, target_elements, seen, solid_cache)

        # 4. Escaneo de vínculos
        if include_links and self.active_count < self.max_results:
            link_records = self._scan_links(host_elements, target_elements, seen, solid_cache)
            records.extend(link_records)

        records.sort(key=lambda r: r.volume, reverse=True)
        return records

    # ── Scan host ────────────────────────────────────────────────────────────

    def _scan_host(self, host_elements, target_elements, seen, solid_cache):
        records    = []
        bbox_cache = {}

        grid, bbox_cache = _build_grid(target_elements, bbox_cache)
        if grid is None:
            return records

        doc_title = self.doc.Title

        for element in host_elements:
            if self.abort_flag:
                break

            eid_a = element.Id.IntegerValue
            mn_a, mx_a = bbox_cache.get(eid_a, (None, None))
            
            if mn_a is None:
                mn_a, mx_a = _bbox(element)
                if mn_a is None: continue

            candidates_tuples = grid.query(mn_a, mx_a)

            for cand_tuple in candidates_tuples:
                other = cand_tuple[0]
                eid_b = other.Id.IntegerValue
                
                if eid_a == eid_b:
                    continue

                key = _pair_key(doc_title, eid_a, doc_title, eid_b)
                if key in seen:
                    continue
                seen.add(key)

                prev_status = self.prev_statuses.get(key, None)
                
                if prev_status in (ClashStatus.APPROVED, ClashStatus.REVIEWED):
                    # Omitir cálculo de geometría pesada
                    new_status = prev_status
                    volume = 0.01 # Valor nominal mínimo
                else:
                    if self.active_count >= self.max_results:
                        continue  # Ya llegamos al límite, ignoramos nuevos/activos

                    solids_a = _solids_from_element(element, solid_cache)
                    solids_b = _solids_from_element(other,   solid_cache)
                    volume   = _boolean_intersection_volume(solids_a, solids_b)

                    if volume is None or volume < self.min_volume:
                        continue

                    # Máquina de estados: si sigue chocando, calcular nuevo status
                    if prev_status is None:
                        new_status = ClashStatus.NEW          # primera vez
                    elif prev_status == ClashStatus.NEW:
                        new_status = ClashStatus.ACTIVE       # visto antes, sigue chocando
                    elif prev_status == ClashStatus.ACTIVE:
                        new_status = ClashStatus.ACTIVE       # sigue activo
                    else:
                        # Resolved pero AÚN choca → vuelve a Active
                        new_status = ClashStatus.ACTIVE

                is_active = new_status in (ClashStatus.NEW, ClashStatus.ACTIVE)

                r = ClashRecord(key, doc_title, doc_title, eid_a, eid_b,
                                _elem_name(element), _elem_name(other),
                                _cat_name(element), _cat_name(other),
                                volume, False, new_status, ClashType.HARD)
                records.append(r)

                if is_active:
                    self.active_count += 1

        return records

    # ── Scan links ───────────────────────────────────────────────────────────

    def _scan_links(self, host_elements, target_elements, seen, solid_cache):
        records   = []
        doc_title = self.doc.Title

        if self._active_view is not None:
            links = list(
                FilteredElementCollector(self.doc, self._active_view.Id)
                .OfClass(RevitLinkInstance)
                .ToElements()
            )
        else:
            links = list(
                FilteredElementCollector(self.doc)
                .OfClass(RevitLinkInstance)
                .ToElements()
            )
        
        overall_mn, overall_mx = _get_overall_outline(host_elements)

        for link in links:
            if self.abort_flag:
                break
            if self.active_count >= self.max_results:
                break

            # Verificación blindada del Workset del propio vínculo en la vista anfitriona
            if self._active_view is not None:
                try:
                    if link.IsHidden(self._active_view):
                        continue
                    if not self._active_view.IsElementVisibleInTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate, link.Id):
                        continue
                    if self._active_view.GetWorksetVisibility(link.WorksetId) == WorksetVisibility.Hidden:
                        continue
                except Exception:
                    pass

            linked_doc = link.GetLinkDocument()
            if linked_doc is None:
                continue

            transform         = link.GetTotalTransform()
            inverse_transform = transform.Inverse
            link_title        = linked_doc.Title

            if overall_mn is not None and overall_mx is not None:
                pts = [
                    XYZ(overall_mn.X, overall_mn.Y, overall_mn.Z),
                    XYZ(overall_mn.X, overall_mn.Y, overall_mx.Z),
                    XYZ(overall_mn.X, overall_mx.Y, overall_mn.Z),
                    XYZ(overall_mn.X, overall_mx.Y, overall_mx.Z),
                    XYZ(overall_mx.X, overall_mn.Y, overall_mn.Z),
                    XYZ(overall_mx.X, overall_mn.Y, overall_mx.Z),
                    XYZ(overall_mx.X, overall_mx.Y, overall_mn.Z),
                    XYZ(overall_mx.X, overall_mx.Y, overall_mx.Z)
                ]
                pts_link = [inverse_transform.OfPoint(p) for p in pts]
                l_mn = XYZ(min(p.X for p in pts_link), min(p.Y for p in pts_link), min(p.Z for p in pts_link))
                l_mx = XYZ(max(p.X for p in pts_link), max(p.Y for p in pts_link), max(p.Z for p in pts_link))
                link_outline = _outline(l_mn, l_mx)
            else:
                link_outline = None

            # IMPORTANTE: Se envía self._active_view para que audite Visibilidad y Worksets dentro del link
            link_elements = _collect_elements(linked_doc, self.categories, view=self._active_view, outline=link_outline)
            
            if not link_elements:
                continue

            link_bbox_cache = {}
            for le in link_elements:
                mn_l, mx_l = _bbox(le, transform)
                link_bbox_cache[le.Id.IntegerValue] = (mn_l, mx_l)

            valid_diags = []
            for mn, mx in link_bbox_cache.values():
                if mn is not None:
                    d = _bbox_diagonal(mn, mx)
                    if d > 0:
                        valid_diags.append(d)

            if not valid_diags:
                continue

            valid_diags.sort()
            link_cell = max(valid_diags[len(valid_diags) // 2], 0.1)

            grid_l = SpatialHashGrid(link_cell)
            for le in link_elements:
                mn_l, mx_l = link_bbox_cache[le.Id.IntegerValue]
                if mn_l is not None:
                    grid_l.insert(le, mn_l, mx_l)

            link_solid_cache = {}

            for host_elem in host_elements:
                if self.abort_flag:
                    break

                eid_a      = host_elem.Id.IntegerValue
                mn_a, mx_a = _bbox(host_elem)
                if mn_a is None:
                    continue

                candidates_tuples = grid_l.query(mn_a, mx_a)

                for cand_tuple in candidates_tuples:
                    link_elem = cand_tuple[0]
                    eid_b = link_elem.Id.IntegerValue
                    
                    key = _pair_key(doc_title, eid_a, link_title, eid_b)
                    if key in seen:
                        continue
                    seen.add(key)

                    prev_status = self.prev_statuses.get(key, None)
                    
                    if prev_status in (ClashStatus.APPROVED, ClashStatus.REVIEWED):
                        # Omitir cálculo de geometría pesada
                        new_status = prev_status
                        volume = 0.01 # Valor nominal mínimo
                    else:
                        if self.active_count >= self.max_results:
                            continue

                        solids_a = _solids_from_element(host_elem, solid_cache)
                        solids_b = _solids_from_element(link_elem, link_solid_cache)
                        volume   = _boolean_intersection_volume(solids_a, solids_b, transform)

                        if volume is None or volume < self.min_volume:
                            continue

                        # Máquina de estados
                        if prev_status is None:
                            new_status = ClashStatus.NEW
                        elif prev_status == ClashStatus.NEW:
                            new_status = ClashStatus.ACTIVE
                        elif prev_status == ClashStatus.ACTIVE:
                            new_status = ClashStatus.ACTIVE
                        else:
                            # Resolved pero AÚN choca → vuelve a Active
                            new_status = ClashStatus.ACTIVE

                    is_active = new_status in (ClashStatus.NEW, ClashStatus.ACTIVE)

                    r = ClashRecord(key, doc_title, link_title, eid_a, eid_b,
                                    _elem_name(host_elem), _elem_name(link_elem),
                                    _cat_name(host_elem), _cat_name(link_elem),
                                    volume, True, new_status, ClashType.LINKED)
                    records.append(r)

                    if is_active:
                        self.active_count += 1

        return records

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _selected_elements(self, selected_ids):
        elements = []
        for eid in selected_ids:
            try:
                elem = self.doc.GetElement(eid)
                # No forzamos la exclusión por vista si el usuario lo seleccionó a mano
                if elem is not None and not _is_excluded(elem, None):
                    elements.append(elem)
            except Exception:
                pass
        return elements