# -*- coding: utf-8 -*-
"""
conduit_builder.py  —  Clash Resolver
Crea los segmentos de Conduit del caballito con codos en los 4 vértices.
Compatible con Revit 2024 y 2025 / IronPython / PyRevit.
"""

from Autodesk.Revit.DB import XYZ, Line, ElementId
from Autodesk.Revit.DB.Electrical import Conduit


class ConduitBuilder:

    def __init__(self, doc, bypass_data, original_conduit):
        self.doc      = doc
        self.bypass   = bypass_data
        self.original = original_conduit

        self.level_id        = original_conduit.ReferenceLevel.Id
        self.conduit_type_id = original_conduit.GetTypeId()
        self.diameter        = original_conduit.LookupParameter("Diameter").AsDouble()

    # ─────────────────────────────────────────
    #  MÉTODO PRINCIPAL
    # ─────────────────────────────────────────
    def build(self):
        # 1. Recortar el original
        tramo_antes, tramo_despues = self._trim_original_conduit()

        # 2. Crear los 3 segmentos del caballito
        seg_ids = []
        for start_pt, end_pt in self.bypass['segments']:
            if start_pt.DistanceTo(end_pt) < 0.02:
                continue
            c = self._create_conduit_segment(start_pt, end_pt)
            if c:
                seg_ids.append(c.Id)

        # 3. Insertar los 4 codos
        self._insert_all_elbows(seg_ids, tramo_antes, tramo_despues)

        return seg_ids

    # ─────────────────────────────────────────
    #  RECORTAR CONDUIT ORIGINAL
    # ─────────────────────────────────────────
    def _trim_original_conduit(self):
        loc   = self.original.Location
        curve = loc.Curve
        ep0   = curve.GetEndPoint(0)
        ep1   = curve.GetEndPoint(1)

        P0 = self.bypass['P0']
        P4 = self.bypass['P4']

        if ep0.DistanceTo(P0) <= ep1.DistanceTo(P0):
            near_P0, near_P4 = ep0, ep1
        else:
            near_P0, near_P4 = ep1, ep0

        tramo_antes   = None
        tramo_despues = None

        try:
            if near_P0.DistanceTo(P0) > 0.02:
                loc.Curve   = Line.CreateBound(near_P0, P0)
                tramo_antes = self.original
            else:
                # El caballito empieza justo en el extremo del conduit.
                # Eliminar el original para evitar geometría duplicada.
                self.doc.Delete(self.original.Id)
                tramo_antes = None

            if P4.DistanceTo(near_P4) > 0.02:
                after = Conduit.Create(
                    self.doc,
                    self.conduit_type_id,
                    P4,
                    near_P4,
                    self.level_id
                )
                dp = after.LookupParameter("Diameter")
                if dp and not dp.IsReadOnly:
                    dp.Set(self.diameter)
                tramo_despues = after
        except Exception as e:
            print("[ConduitBuilder] Error en trim: {}".format(e))

        return tramo_antes, tramo_despues

    # ─────────────────────────────────────────
    #  CREAR SEGMENTO
    # ─────────────────────────────────────────
    def _create_conduit_segment(self, start_pt, end_pt):
        try:
            c = Conduit.Create(
                self.doc,
                self.conduit_type_id,
                start_pt,
                end_pt,
                self.level_id
            )
            dp = c.LookupParameter("Diameter")
            if dp and not dp.IsReadOnly:
                dp.Set(self.diameter)
            return c
        except Exception as e:
            print("[ConduitBuilder] Error creando segmento: {}".format(e))
            return None

    # ─────────────────────────────────────────
    #  INSERTAR LOS 4 CODOS
    # ─────────────────────────────────────────
    def _insert_all_elbows(self, seg_ids, tramo_antes, tramo_despues):
        if len(seg_ids) < 3:
            return

        s0 = self.doc.GetElement(seg_ids[0])
        s1 = self.doc.GetElement(seg_ids[1])
        s2 = self.doc.GetElement(seg_ids[2])

        self._elbow(s0, s1)
        self._elbow(s1, s2)

        if tramo_antes:
            self._elbow(tramo_antes, s0)
        if tramo_despues:
            self._elbow(s2, tramo_despues)

    def _elbow(self, elem_a, elem_b):
        try:
            c_a = self._nearest_open_connector(elem_a, elem_b)
            c_b = self._nearest_open_connector(elem_b, elem_a)
            if c_a and c_b:
                self.doc.Create.NewElbowFitting(c_a, c_b)
        except Exception as e:
            print("[ConduitBuilder] Error insertando codo: {}".format(e))

    def _nearest_open_connector(self, element, toward_element):
        try:
            toward_mid = toward_element.Location.Curve.Evaluate(0.5, True)
            conns      = list(element.ConnectorManager.Connectors)
            open_c     = [c for c in conns if not c.IsConnected]
            pool       = open_c if open_c else conns
            return min(pool, key=lambda c: c.Origin.DistanceTo(toward_mid))
        except Exception as e:
            print("[ConduitBuilder] Error buscando conector: {}".format(e))
            return None
