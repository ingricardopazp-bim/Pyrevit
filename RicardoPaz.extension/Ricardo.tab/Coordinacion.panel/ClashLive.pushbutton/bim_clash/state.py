# -*- coding: utf-8 -*-
"""
state.py — Gestión de estado e historial de interferencias.
Persiste statuses en DOS ubicaciones:
  1. ConflictManager/<doc_title>.json junto al modelo (si disponible)
  2. C:\ClashManager\<doc_title>.json  (siempre, para retomar sin modelo cargado)
"""
from __future__ import absolute_import

import os
import json

from bim_clash.models import ClashRecord, ClashStatus, ClashType

# Carpeta fija de persistencia en disco C
_FIXED_FOLDER = r'C:\ClashManager'


class ClashState(object):
    def __init__(self, doc_title=None, doc_path=None):
        self._statuses   = {}
        self._records    = []
        self._json_path  = None   # junto al modelo
        self._fixed_path = None   # C:\ClashManager\...

        safe_title = (doc_title or 'model').replace('/', '_').replace('\\', '_')

        # ── Ruta fija C:\ClashManager ─────────────────────────────────────────
        try:
            if not os.path.exists(_FIXED_FOLDER):
                os.makedirs(_FIXED_FOLDER)
            self._fixed_path = os.path.join(_FIXED_FOLDER, safe_title + '.json')
        except Exception:
            self._fixed_path = None

        # ── Ruta junto al modelo ──────────────────────────────────────────────
        if doc_path:
            try:
                folder = os.path.join(os.path.dirname(doc_path), 'ConflictManager')
                if not os.path.exists(folder):
                    os.makedirs(folder)
                self._json_path = os.path.join(folder, safe_title + '.json')
            except Exception:
                self._json_path = None

        self._load()

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load(self):
        """Carga desde la ruta que tenga datos más recientes (por mtime)."""
        loaded = False

        candidates = []
        for path in (self._json_path, self._fixed_path):
            if path and os.path.exists(path):
                try:
                    candidates.append((os.path.getmtime(path), path))
                except Exception:
                    pass

        # Ordenar del más reciente al más antiguo
        candidates.sort(reverse=True)

        for _, path in candidates:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self._statuses = data.get('statuses', {})
                loaded = True
                break
            except Exception:
                pass

        if not loaded:
            self._statuses = {}

    def _save(self):
        """Guarda en AMBAS rutas si están disponibles."""
        data = {'statuses': self._statuses}
        for path in (self._json_path, self._fixed_path):
            if path:
                try:
                    with open(path, 'w') as f:
                        json.dump(data, f, indent=2)
                except Exception:
                    pass

    # ── Merge ─────────────────────────────────────────────────────────────────

    def merge(self, records):
        """
        Recibe registros con status ya calculado por el detector (máquina de estados).
        Solo persiste los nuevos statuses y marca como Resolved los que desaparecieron.
        """
        incoming_keys = set()
        for record in records:
            incoming_keys.add(record.key)
            self._statuses[record.key] = record.status

        # Los que no aparecen en este scan se marcan como Resolved,
        # excepto los que el usuario marcó explícitamente como Approved.
        for key, status in list(self._statuses.items()):
            if key not in incoming_keys and status not in (ClashStatus.APPROVED, ClashStatus.REVIEWED, ClashStatus.RESOLVED):
                self._statuses[key] = ClashStatus.RESOLVED

        old_protected = [r for r in self._records if r.key not in incoming_keys and r.status in (ClashStatus.APPROVED, ClashStatus.REVIEWED)]
        self._records = list(records) + old_protected
        self._save()
        return self._records

    # ── Mutación de estado ────────────────────────────────────────────────────

    def set_status(self, key, status):
        self._statuses[key] = status
        for record in self._records:
            if record.key == key:
                record.status = status
                break
        self._save()

    def set_status_bulk(self, keys, status):
        key_set = set(keys)
        self._statuses.update({k: status for k in key_set})
        for record in self._records:
            if record.key in key_set:
                record.status = status
        self._save()

    # ── Consulta ──────────────────────────────────────────────────────────────

    def records(self):
        return list(self._records)

    def filtered_records(self, active_filters=None):
        if not active_filters:
            result = list(self._records)
        else:
            status_filters = {f for f in active_filters
                              if f in (ClashStatus.NEW, ClashStatus.ACTIVE, ClashStatus.REVIEWED,
                                       ClashStatus.APPROVED, ClashStatus.RESOLVED)}
            link_filter  = 'Linked' in active_filters
            model_filter = 'Model'  in active_filters

            result = []
            for r in self._records:
                if status_filters and r.status not in status_filters:
                    continue
                if link_filter and not model_filter and not r.is_linked:
                    continue
                if model_filter and not link_filter and r.is_linked:
                    continue
                result.append(r)

        # Ordenar por source_id (ID del elemento A)
        result.sort(key=lambda r: r.source_id)
        return result

    def summary(self, records=None):
        lst = records if records is not None else self._records
        counts = {s: 0 for s in ClashStatus.ALL}
        linked = 0
        for r in lst:
            counts[r.status] = counts.get(r.status, 0) + 1
            if r.is_linked:
                linked += 1
        counts['Linked'] = linked
        counts['Total']  = len(lst)
        return counts