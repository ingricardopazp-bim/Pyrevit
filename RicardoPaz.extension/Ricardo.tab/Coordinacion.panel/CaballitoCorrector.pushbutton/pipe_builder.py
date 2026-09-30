# -*- coding: utf-8 -*-
"""
pipe_builder.py  —  Clash Resolver
Crea los segmentos de Pipe del caballito/desvío con codos en los 4 vértices.
Compatible con Revit 2024 y 2025 / IronPython / PyRevit.
"""

from Autodesk.Revit.DB import XYZ, Line, ElementId
from Autodesk.Revit.DB.Plumbing import Pipe


class PipeBuilder:

    def __init__(self, doc, bypass_data, original_pipe):
        self.doc      = doc
        self.bypass   = bypass_data
        self.original = original_pipe

        self.level_id       = original_pipe.ReferenceLevel.Id
        self.pipe_type_id   = original_pipe.GetTypeId()
        self.system_type_id = self._get_system_type_id()
        self.diameter       = self._get_diameter()

    # ─────────────────────────────────────────
    #  MÉTODO PRINCIPAL
    # ─────────────────────────────────────────
    def build(self):
        """
        Flujo:
          1. Recortar el original → queda: tramo_antes y tramo_despues
          2. Crear los 3 segmentos del caballito
          3. Insertar los 4 codos:
               - codo A: tramo_antes   ↔ seg_diagonal_entrada
               - codo B: seg_diagonal_entrada ↔ seg_paralelo
               - codo C: seg_paralelo  ↔ seg_diagonal_salida
               - codo D: seg_diagonal_salida  ↔ tramo_despues
        """
        # 1. Recortar el original y guardar referencia a los dos trozos
        tramo_antes, tramo_despues = self._trim_original_pipe()

        # 2. Crear los 3 segmentos del caballito
        seg_ids = []
        for start_pt, end_pt in self.bypass['segments']:
            if start_pt.DistanceTo(end_pt) < 0.02:
                continue
            pipe = self._create_pipe_segment(start_pt, end_pt)
            if pipe:
                seg_ids.append(pipe.Id)

        if len(seg_ids) != 3:
            print("[PipeBuilder] Advertencia: se esperaban 3 segmentos, se crearon {}".format(len(seg_ids)))

        # 3. Insertar los 4 codos
        self._insert_all_elbows(seg_ids, tramo_antes, tramo_despues)

        return seg_ids

    # ─────────────────────────────────────────
    #  RECORTAR PIPE ORIGINAL
    # ─────────────────────────────────────────
    def _trim_original_pipe(self):
        """
        Divide el pipe original en dos trozos: antes y después del caballito.
        Retorna (tramo_antes, tramo_despues).
        tramo_antes  termina en P0.
        tramo_despues empieza en P4.
        """
        loc   = self.original.Location
        curve = loc.Curve
        ep0   = curve.GetEndPoint(0)
        ep1   = curve.GetEndPoint(1)

        P0 = self.bypass['P0']
        P4 = self.bypass['P4']

        # Determinar qué extremo está cerca de P0 y cuál de P4
        if ep0.DistanceTo(P0) <= ep1.DistanceTo(P0):
            near_P0, near_P4 = ep0, ep1
        else:
            near_P0, near_P4 = ep1, ep0

        tramo_antes   = None
        tramo_despues = None

        try:
            # Acortar el original: near_P0 → P0
            if near_P0.DistanceTo(P0) > 0.02:
                loc.Curve  = Line.CreateBound(near_P0, P0)
                tramo_antes = self.original
            else:
                # El caballito empieza justo en el extremo del pipe.
                # El pipe original queda de longitud ~0 → eliminarlo para
                # evitar geometría duplicada en el modelo.
                self.doc.Delete(self.original.Id)
                tramo_antes = None

            # Crear segmento posterior: P4 → near_P4
            if P4.DistanceTo(near_P4) > 0.02:
                after = Pipe.Create(
                    self.doc,
                    self.system_type_id,
                    self.pipe_type_id,
                    self.level_id,
                    P4,
                    near_P4
                )
                dp = after.LookupParameter("Diameter")
                if dp and not dp.IsReadOnly:
                    dp.Set(self.diameter)
                tramo_despues = after
        except Exception as e:
            print("[PipeBuilder] Error en trim: {}".format(e))

        return tramo_antes, tramo_despues

    # ─────────────────────────────────────────
    #  CREAR SEGMENTO
    # ─────────────────────────────────────────
    def _create_pipe_segment(self, start_pt, end_pt):
        try:
            pipe = Pipe.Create(
                self.doc,
                self.system_type_id,
                self.pipe_type_id,
                self.level_id,
                start_pt,
                end_pt
            )
            dp = pipe.LookupParameter("Diameter") or pipe.LookupParameter("Outside Diameter")
            if dp and not dp.IsReadOnly:
                dp.Set(self.diameter)
            return pipe
        except Exception as e:
            print("[PipeBuilder] Error creando segmento: {}".format(e))
            return None

    # ─────────────────────────────────────────
    #  INSERTAR LOS 4 CODOS
    # ─────────────────────────────────────────
    def _insert_all_elbows(self, seg_ids, tramo_antes, tramo_despues):
        """
        Inserta los 4 codos del caballito:
          codo 1: tramo_antes      ↔ seg[0]  (diagonal entrada)
          codo 2: seg[0]           ↔ seg[1]  (diagonal → paralelo)
          codo 3: seg[1]           ↔ seg[2]  (paralelo → diagonal)
          codo 4: seg[2]           ↔ tramo_despues
        """
        if len(seg_ids) < 3:
            return

        s0 = self.doc.GetElement(seg_ids[0])
        s1 = self.doc.GetElement(seg_ids[1])
        s2 = self.doc.GetElement(seg_ids[2])

        # Codos internos del caballito (siempre presentes)
        self._elbow(s0, s1)   # codo en P1
        self._elbow(s1, s2)   # codo en P3

        # Codo de entrada: tramo_antes ↔ diagonal de entrada
        if tramo_antes:
            self._elbow(tramo_antes, s0)

        # Codo de salida: diagonal de salida ↔ tramo_despues
        if tramo_despues:
            self._elbow(s2, tramo_despues)

    def _elbow(self, elem_a, elem_b):
        """Inserta un codo entre dos elementos MEP usando NewElbowFitting."""
        try:
            c_a = self._nearest_open_connector(elem_a, elem_b)
            c_b = self._nearest_open_connector(elem_b, elem_a)
            if c_a and c_b:
                self.doc.Create.NewElbowFitting(c_a, c_b)
        except Exception as e:
            print("[PipeBuilder] Error insertando codo: {}".format(e))

    def _nearest_open_connector(self, element, toward_element):
        """
        Retorna el conector abierto de 'element' más cercano a 'toward_element'.
        """
        try:
            toward_mid = toward_element.Location.Curve.Evaluate(0.5, True)
            conns      = list(element.ConnectorManager.Connectors)
            open_c     = [c for c in conns if not c.IsConnected]
            pool       = open_c if open_c else conns
            return min(pool, key=lambda c: c.Origin.DistanceTo(toward_mid))
        except Exception as e:
            print("[PipeBuilder] Error buscando conector: {}".format(e))
            return None

    # ─────────────────────────────────────────
    #  UTILIDADES
    # ─────────────────────────────────────────
    def _get_system_type_id(self):
        try:
            sys = self.original.MEPSystem
            if sys:
                return sys.GetTypeId()
        except Exception:
            pass
        from Autodesk.Revit.DB import FilteredElementCollector
        from Autodesk.Revit.DB.Plumbing import PipingSystemType
        return FilteredElementCollector(self.doc).OfClass(PipingSystemType).FirstElementId()

    def _get_diameter(self):
        for n in ["Diameter", "Inside Diameter", "Nominal Diameter"]:
            p = self.original.LookupParameter(n)
            if p:
                return p.AsDouble()
        return 0.0833
