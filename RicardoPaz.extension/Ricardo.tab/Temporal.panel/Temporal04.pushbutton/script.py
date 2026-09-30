# -*- coding: utf-8 -*-
__title__ = 'Familia en\nCaras de Cable'
__doc__ = ('Coloca una familia basada en cara en el centroide de la cara de inicio '
           'y de la cara final de cada cable (FreeFormElement creado con "CAD a Cables").')

import traceback
import sys

try:
    import System
    from Autodesk.Revit.DB import *
    from Autodesk.Revit.UI import *
    from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
    from pyrevit import forms

    uidoc = __revit__.ActiveUIDocument
    doc = uidoc.Document

    # Dos caras de distintos cables a menos de esta distancia se consideran una
    # junta interna (cables troceados por el script de CAD) y se ignoran.
    TOL_JUNTA = 2.0 / 304.8  # 2 mm en pies

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    class FiltroFreeForm(ISelectionFilter):
        def AllowElement(self, e):
            return isinstance(e, FreeFormElement)

        def AllowReference(self, r, p):
            return False

    def nombre_tipo(sym):
        p = sym.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
        return p.AsString() if p else "?"

    def simbolos_basados_en_cara():
        res = []
        for s in FilteredElementCollector(doc).OfClass(FamilySymbol):
            try:
                if s.Family.FamilyPlacementType == FamilyPlacementType.WorkPlaneBased:
                    res.append(s)
            except Exception:
                pass
        return res

    def obtener_cables():
        els = [doc.GetElement(i) for i in uidoc.Selection.GetElementIds()]
        els = [e for e in els if isinstance(e, FreeFormElement)]
        if els:
            return els
        op = forms.alert(
            "No hay cables preseleccionados.\n\n¿Qué cables quieres procesar?",
            options=["Todos los cables (FreeForm) del documento", "Seleccionar manualmente"])
        if op is None:
            return None
        if op.startswith("Todos"):
            return list(FilteredElementCollector(doc).OfClass(FreeFormElement))
        try:
            refs = uidoc.Selection.PickObjects(
                ObjectType.Element, FiltroFreeForm(),
                "Selecciona los cables y pulsa Finalizar")
        except Exception:
            return None
        return [doc.GetElement(r) for r in refs]

    def solidos_de(elem):
        opt = Options()
        opt.ComputeReferences = True          # necesario para hospedar en la cara
        opt.DetailLevel = ViewDetailLevel.Fine
        opt.IncludeNonVisibleObjects = False
        out = []

        def rec(geom):
            for o in geom:
                if isinstance(o, Solid):
                    if o.Volume > 0 and o.Faces.Size > 0:
                        out.append(o)
                elif isinstance(o, GeometryInstance):
                    rec(o.GetSymbolGeometry())

        ge = elem.get_Geometry(opt)
        if ge:
            rec(ge)
        return out

    def es_cara_tapa(face):
        """Cara plana limitada por un unico lazo formado solo por arcos (tapa circular)."""
        if not isinstance(face, PlanarFace):
            return False
        loops = face.GetEdgesAsCurveLoops()
        if loops.Count != 1:
            return False
        n = 0
        for c in loops[0]:
            n += 1
            if not isinstance(c, Arc):
                return False
        return n > 0

    def centroide(face):
        # Tapa circular: el centro del arco es el centroide exacto.
        for c in face.GetEdgesAsCurveLoops()[0]:
            if isinstance(c, Arc):
                return c.Center
        # Respaldo: centroide ponderado por area de la triangulacion.
        mesh = face.Triangulate()
        sx = sy = sz = a_tot = 0.0
        for i in range(mesh.NumTriangles):
            t = mesh.get_Triangle(i)
            p0, p1, p2 = t.get_Vertex(0), t.get_Vertex(1), t.get_Vertex(2)
            a = (p1 - p0).CrossProduct(p2 - p0).GetLength() / 2.0
            sx += a * (p0.X + p1.X + p2.X) / 3.0
            sy += a * (p0.Y + p1.Y + p2.Y) / 3.0
            sz += a * (p0.Z + p1.Z + p2.Z) / 3.0
            a_tot += a
        return XYZ(sx / a_tot, sy / a_tot, sz / a_tot)

    def direccion_referencia(normal):
        for eje in (XYZ.BasisZ, XYZ.BasisX):
            v = eje - normal.Multiply(eje.DotProduct(normal))
            if v.GetLength() > 1e-6:
                return v.Normalize()
        return XYZ.BasisY

    # ------------------------------------------------------------------
    # 1. Elegir la familia
    # ------------------------------------------------------------------
    simbolos = simbolos_basados_en_cara()
    if not simbolos:
        forms.alert("No hay familias basadas en cara cargadas en este documento.\n"
                    "Carga primero la familia y vuelve a ejecutar.", exitscript=True)

    mapa = {}
    for s in simbolos:
        mapa["{} : {}".format(s.FamilyName, nombre_tipo(s))] = s
    elegido = forms.SelectFromList.show(sorted(mapa.keys()),
                                        title="Familia basada en cara",
                                        button_name="Colocar",
                                        multiselect=False)
    if not elegido:
        sys.exit()
    simbolo = mapa[elegido]

    # ------------------------------------------------------------------
    # 2. Elegir los cables
    # ------------------------------------------------------------------
    cables = obtener_cables()
    if not cables:
        sys.exit()
    print("Cables a procesar: {}".format(len(cables)))

    # Activar el tipo (en su propia transaccion, antes de pedir referencias)
    if not simbolo.IsActive:
        ta = Transaction(doc, "Activar tipo de familia")
        ta.Start()
        simbolo.Activate()
        ta.Commit()
        doc.Regenerate()

    # ------------------------------------------------------------------
    # 3. Detectar caras de inicio/fin
    # ------------------------------------------------------------------
    tapas = []
    for cab in cables:
        for solido in solidos_de(cab):
            for face in solido.Faces:
                if es_cara_tapa(face):
                    tapas.append({"id": cab.Id, "face": face,
                                  "centro": centroide(face),
                                  "normal": face.FaceNormal})
    print("Caras de extremo detectadas: {}".format(len(tapas)))

    # Descartar juntas internas (extremos coincidentes de cables distintos)
    validas = []
    for i, a in enumerate(tapas):
        junta = False
        for j, b in enumerate(tapas):
            if i != j and a["id"] != b["id"] and a["centro"].DistanceTo(b["centro"]) < TOL_JUNTA:
                junta = True
                break
        if not junta:
            validas.append(a)
    descartadas = len(tapas) - len(validas)
    if descartadas:
        print("Juntas internas descartadas: {}".format(descartadas))

    # ------------------------------------------------------------------
    # 4. Colocar la familia en el centroide de cada cara
    # ------------------------------------------------------------------
    fabrica = doc.FamilyCreate if doc.IsFamilyDocument else doc.Create
    creadas = 0
    errores = []

    t = Transaction(doc, "Familia en caras de cables")
    t.Start()
    for cap in validas:
        try:
            ref_dir = direccion_referencia(cap["normal"])
            try:
                inst = fabrica.NewFamilyInstance(cap["face"].Reference, cap["centro"], ref_dir, simbolo)
            except Exception:
                inst = fabrica.NewFamilyInstance(cap["face"], cap["centro"], ref_dir, simbolo)
            if inst is not None:
                creadas += 1
        except Exception as ex:
            errores.append("Cable {}: {}".format(cap["id"].IntegerValue, ex))
    t.Commit()

    print("\n¡PROCESO TERMINADO!")
    print("Familias colocadas: {} de {}".format(creadas, len(validas)))
    if errores:
        print("Errores ({}):".format(len(errores)))
        for e in errores[:15]:
            print("  - " + e)

except System.Exception as e:
    print("\n--- ERROR DE REVIT ---")
    print(e)
except Exception as e:
    print("\n--- ERROR DE PYTHON ---")
    print(traceback.format_exc())