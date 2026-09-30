# -*- coding: utf-8 -*-
"""
xml_importer.py — Importa conflictos desde un reporte XML de clash detection
de Navisworks (batchtest > clashtests > clashtest > clashresults > clashgroup
[> clashresults > clashresult]*), resolviendo cada Element ID contra el
documento activo de Revit para obtener Categoria y Nombre reales.
"""
from __future__ import absolute_import

import os
import xml.etree.ElementTree as ET

from Autodesk.Revit.DB import ElementId, RevitLinkInstance, FilteredElementCollector

from bim_clash.models import ClashRecord, ClashStatus, ClashType


_STATUS_MAP = {
    'new':      ClashStatus.NEW,
    'active':   ClashStatus.ACTIVE,
    'reviewed': ClashStatus.REVIEWED,
    'approved': ClashStatus.APPROVED,
    'resolved': ClashStatus.RESOLVED,
}

# Mapa inverso — para escribir de vuelta al XML el status actual de la app.
_REVERSE_STATUS_MAP = {
    ClashStatus.NEW:      'new',
    ClashStatus.ACTIVE:   'active',
    ClashStatus.REVIEWED: 'reviewed',
    ClashStatus.APPROVED: 'approved',
    ClashStatus.RESOLVED: 'resolved',
}


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


def _element_id_from_clashobject(clashobject_node):
    """Extrae el Element ID entero desde un nodo <clashobject>."""
    for attr in clashobject_node.findall('objectattribute'):
        # El XML real de Navisworks usa <name>Element ID</name>, NO <n>.
        name_node = attr.find('name')
        value_node = attr.find('value')
        if name_node is not None and name_node.text == 'Element ID':
            if value_node is not None and value_node.text:
                try:
                    return int(value_node.text)
                except ValueError:
                    return None
    return None


def _all_docs(doc):
    """
    Devuelve [(titulo, documento, es_linkeado)] para el documento host
    y para cada modelo vinculado actualmente cargado y accesible.
    Un XML de Navisworks suele generarse contra un modelo federado
    (host + links); si solo se resuelve contra `doc`, cualquier Element ID
    que pertenezca a un link se pierde en silencio.
    """
    docs = [(doc.Title, doc, False)]
    try:
        links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
        for link in links:
            try:
                linked_doc = link.GetLinkDocument()
                if linked_doc is not None:
                    docs.append((linked_doc.Title, linked_doc, True))
            except Exception:
                pass
    except Exception:
        pass
    return docs


def _resolve_element(eid, docs):
    """
    Busca el ElementId `eid` primero en el host y luego en cada modelo
    vinculado (en el orden de `docs`). Devuelve (elemento, doc_title, is_linked)
    o (None, None, False) si no se encontro en ninguno.
    """
    for doc_title, d, is_linked in docs:
        try:
            el = d.GetElement(ElementId(eid))
        except Exception:
            el = None
        if el is not None:
            return el, doc_title, is_linked
    return None, None, False


_UNIT_TO_FEET = {
    'm': 3.280839895, 'cm': 0.03280839895, 'mm': 0.003280839895,
    'ft': 1.0, 'in': 1.0 / 12.0,
}


def _clash_point_ft(node, unit_factor):
    """Lee <clashpoint><pos3f x y z/> del nodo y lo devuelve en pies (x, y, z), o None."""
    try:
        pos = node.find('clashpoint/pos3f')
        if pos is None:
            return None
        return (float(pos.get('x')) * unit_factor,
                float(pos.get('y')) * unit_factor,
                float(pos.get('z')) * unit_factor)
    except Exception:
        return None


def _leaf_clash_nodes(clashgroup_node):
    """
    Un <clashgroup> puede contener resultados individuales anidados en su
    propio <clashresults><clashresult>...</clashresult></clashresults>.
    Si existen, esos son los conflictos reales (uno por par de elementos).
    Si NO existen, el propio clashgroup ya es el conflicto (grupo simple).
    """
    nested_results_container = clashgroup_node.find('clashresults')
    if nested_results_container is not None:
        nested = nested_results_container.findall('clashresult')
        if nested:
            return nested
    return [clashgroup_node]


def parse_navisworks_xml(xml_path, doc):
    """
    Parsea el XML de Navisworks y devuelve una lista de ClashRecord,
    resolviendo cada Element ID contra `doc` (el documento activo de Revit)
    para obtener categoria y nombre reales.

    Args:
        xml_path (str): ruta al archivo .xml exportado de Navisworks.
        doc (Document): documento activo de Revit (self.doc en el handler).

    Returns:
        list[ClashRecord]
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    unit_factor = _UNIT_TO_FEET.get((root.get('units') or 'm').lower(), 3.280839895)
    doc_title  = doc.Title
    docs       = _all_docs(doc)          # host + links cargados
    records    = []
    total_pairs   = 0
    skipped_ids   = []   # [(eid_a, eid_b)] descartados por Element ID no resuelto

    for clashtest in root.iter('clashtest'):
        for clashresults_top in clashtest.findall('clashresults'):
            for clashgroup in clashresults_top.findall('clashgroup'):

                for node in _leaf_clash_nodes(clashgroup):
                    clashobjects = node.find('clashobjects')
                    if clashobjects is None:
                        continue

                    objs = clashobjects.findall('clashobject')
                    if len(objs) < 2:
                        continue

                    eid_a = _element_id_from_clashobject(objs[0])
                    eid_b = _element_id_from_clashobject(objs[1])
                    if eid_a is None or eid_b is None:
                        continue

                    total_pairs += 1

                    element_a, doc_a_title, linked_a = _resolve_element(eid_a, docs)
                    element_b, doc_b_title, linked_b = _resolve_element(eid_b, docs)
                    if element_a is None or element_b is None:
                        # El elemento no existe en el host NI en ningun link cargado
                        # (borrado desde que se genero el XML, o el link no esta
                        # cargado/visible en este momento).
                        skipped_ids.append((eid_a, eid_b))
                        continue

                    # Distancia de interferencia como aproximacion de "volumen"
                    # ya que el XML de Navisworks no reporta volumen real.
                    distance_attr = node.get('distance', '0')
                    try:
                        pseudo_volume = abs(float(distance_attr))
                    except ValueError:
                        pseudo_volume = 0.0

                    status_attr = node.get('status', 'new').lower()
                    status = _STATUS_MAP.get(status_attr, ClashStatus.NEW)

                    is_linked = linked_a or linked_b
                    # La key usa siempre el titulo del doc host activo, para no
                    # romper la continuidad del status guardado entre imports.
                    key = u'xml:%s:%s:%s' % (doc_title, eid_a, eid_b)

                    record = ClashRecord(
                        key=key,
                        source_doc=doc_a_title,
                        target_doc=doc_b_title,
                        source_id=eid_a,
                        target_id=eid_b,
                        source_name=_elem_name(element_a),
                        target_name=_elem_name(element_b),
                        source_category=_cat_name(element_a),
                        target_category=_cat_name(element_b),
                        volume=pseudo_volume,
                        is_linked=is_linked,
                        status=status,
                        clash_type=ClashType.LINKED if is_linked else ClashType.HARD,
                        point=_clash_point_ft(node, unit_factor),
                    )
                    records.append(record)

    if not records and total_pairs > 0:
        raise Exception(
            u'El XML trae %d pares de conflicto, pero ninguno de sus Element ID '
            u'existe en el documento activo (%s) ni en sus %d modelo(s) linkeado(s). '
            u'Verifica que sea el mismo modelo federado con el que se genero el '
            u'reporte de Navisworks.' % (total_pairs, doc_title, len(docs) - 1))

    # No abortamos por un import parcial, pero dejamos el conteo expuesto en la
    # propia funcion para que quien la llame (events.py) pueda avisar al usuario
    # cuantos pares se descartaron y por que.
    parse_navisworks_xml.last_skipped_count = len(skipped_ids)
    parse_navisworks_xml.last_total_pairs   = total_pairs

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Guardar statuses de vuelta al XML original (solo aplica cuando el origen es XML)
# ─────────────────────────────────────────────────────────────────────────────

def save_statuses_to_xml(xml_path, records):
    """
    Escribe en el XML de Navisworks original el status actual (New/Active/
    Reviewed/Approved/Resolved) de cada `record` de origen XML, haciendo match
    por el par de Element ID (source_id, target_id).

    Crea un respaldo `<xml_path>.bak` la primera vez (si no existe ya) antes
    de sobrescribir, ya que el archivo original suele ser un entregable de
    Navisworks compartido con el equipo.

    Args:
        xml_path (str): ruta al .xml original usado en el import.
        records (list[ClashRecord]): registros cuyo status se quiere persistir.

    Returns:
        int: numero de nodos <clashresult>/<clashgroup> actualizados.
    """
    status_by_pair = {}
    for r in records:
        status_by_pair[(r.source_id, r.target_id)] = r.status

    tree = ET.parse(xml_path)
    root = tree.getroot()

    updated = 0
    for clashtest in root.iter('clashtest'):
        for clashresults_top in clashtest.findall('clashresults'):
            for clashgroup in clashresults_top.findall('clashgroup'):
                for node in _leaf_clash_nodes(clashgroup):
                    clashobjects = node.find('clashobjects')
                    if clashobjects is None:
                        continue
                    objs = clashobjects.findall('clashobject')
                    if len(objs) < 2:
                        continue
                    eid_a = _element_id_from_clashobject(objs[0])
                    eid_b = _element_id_from_clashobject(objs[1])
                    if eid_a is None or eid_b is None:
                        continue

                    pair = (eid_a, eid_b)
                    if pair in status_by_pair:
                        navis_status = _REVERSE_STATUS_MAP.get(status_by_pair[pair], 'new')
                        node.set('status', navis_status)
                        updated += 1

    if updated:
        backup_path = xml_path + '.bak'
        if not os.path.exists(backup_path):
            try:
                import shutil
                shutil.copy2(xml_path, backup_path)
            except Exception:
                pass
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)

    return updated
