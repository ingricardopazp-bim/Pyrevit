# -*- coding: utf-8 -*-
"""
NavisworksClashManager.py
=========================
Gestión de Clashes de Navisworks en Revit 2024 — pyRevit
---------------------------------------------------------
Autor  : Coordinación BIM
Versión: 2.0
Fecha  : 2026

Estructura XML esperada (Navisworks BCF/XML Export):
  <exchange>
    <batchtest>
      <clashtests>
        <clashtest name="..." status="...">
          <clashresults>
            <clashresult|clashgroup name="..." status="..." guid="...">
              <resultstatus>...</resultstatus>
              <clashobject>
                <objectattribute><name>Element ID</name><value>XXXXXXX</value>
                <pathlink><node>...archivo.rvt...</node></pathlink>
              </clashobject>
              <!-- clashgroup puede contener <clashresults> anidados -->
            </clashresult|clashgroup>
          </clashresults>
        </clashtest>
      </clashtests>
    </batchtest>
  </exchange>
"""

# ── Imports estándar ──────────────────────────────────────────────────────────
import os
import sys
import re
import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
clr.AddReference("System")

import System
from System import Array
from System.Collections.Generic import List
import System.Windows.Forms as WinForms
import System.Drawing as Drawing
import System.Drawing.Drawing2D as D2
import System.Drawing.Text as DrawingText
from System.Drawing import Color, Font, FontStyle, GraphicsUnit
from System.Windows.Forms import (
    Form, Panel, Label, Button, ComboBox, TreeView, TreeNode,
    TreeViewEventArgs, PictureBox, ToolTip, Splitter, RichTextBox,
    Application, DockStyle, AnchorStyles, BorderStyle, FlatStyle,
    MessageBox, MessageBoxButtons, MessageBoxIcon, OpenFileDialog,
    ControlStyles, MouseButtons, HScrollProperties, ScrollBars,
    FormBorderStyle, FormStartPosition, TextBox, CheckBox,
    StatusStrip, ToolStripStatusLabel, ProgressBar, ImageList,
    ContextMenuStrip, ToolStripMenuItem, DataGridView,
    DataGridViewTextBoxColumn, DataGridViewColumnHeadersHeightSizeMode,
    DataGridViewAutoSizeColumnMode, DataGridViewSelectionMode,
    FlowLayoutPanel, FlowDirection, GroupBox, TabControl, TabPage,
    TableLayoutPanel, SizeType, SplitContainer, Orientation, FixedPanel
)

from Autodesk.Revit.DB import (
    ElementId,
    FilteredElementCollector,
    RevitLinkInstance,
    Transaction,
    BuiltInParameter,
    Element,
    View,
    BoundingBoxXYZ,
    XYZ,
    View3D,
    ViewFamily,
    ViewFamilyType,
    ViewOrientation3D
)
from Autodesk.Revit.UI import (
    UIApplication, UIDocument, RevitCommandId, PostableCommand,IExternalEventHandler, ExternalEvent
)
from Autodesk.Revit.UI.Selection import ObjectType

try:
    import xml.etree.ElementTree as ET
except Exception:
    import System.Xml as ET

# ── Contexto Revit ────────────────────────────────────────────────────────────
try:
    from pyrevit import revit, HOST_APP
    uidoc = revit.uidoc
    doc   = revit.doc
    uiapp = HOST_APP.uiapp
except Exception:
    uidoc = __revit__.ActiveUIDocument  # noqa: F821
    doc   = uidoc.Document
    uiapp = uidoc.Application

# ═════════════════════════════════════════════════════════════════════════════
# PALETA DE COLORES & ESTILOS  — Light Premium v3
# ═════════════════════════════════════════════════════════════════════════════
class Theme:
    # ── Fondos ────────────────────────────────────────────────────────────────
    BG_DARK      = Color.FromArgb(255, 255, 255)  # #FFFFFF ventana principal
    BG_PANEL     = Color.FromArgb(248, 249, 250)  # #F8F9FA contenedores
    BG_CARD      = Color.FromArgb(255, 255, 255)  # #FFFFFF tarjetas/filas
    BG_HOVER     = Color.FromArgb(233, 236, 239)  # #E9ECEF hover suave
    BG_SELECTED  = Color.FromArgb(232, 245, 233)  # #E8F5E9 fila seleccionada verde menta

    # ── Acentos de acción ─────────────────────────────────────────────────────
    ACCENT       = Color.FromArgb( 0, 127,  207)  # #007BFF azul primario
    ACCENT2      = Color.FromArgb(  0,  86, 179)  # hover azul
    SUCCESS      = Color.FromArgb( 40, 167,  69)  # #28A745 verde
    WARNING      = Color.FromArgb(255, 193,   7)  # #FFC107 ámbar
    DANGER       = Color.FromArgb(220,  53,  69)  # #DC3545 rojo
    INFO         = Color.FromArgb(111,  66, 193)  # #6F42C1 morado
    ORANGE       = Color.FromArgb(253, 126,  20)  # #FD7E14 naranja aplicar
    TEAL         = Color.FromArgb( 15, 118, 110)  # #0F766E teal seleccionar

    # ── Texto ─────────────────────────────────────────────────────────────────
    TEXT_PRIMARY = Color.FromArgb( 33,  37,  41)  # #212529
    TEXT_MUTED   = Color.FromArgb(108, 117, 125)  # #6C757D
    TEXT_WHITE   = Color.FromArgb(255, 255, 255)

    # ── Bordes ────────────────────────────────────────────────────────────────
    BORDER       = Color.FromArgb(224, 224, 224)  # #E0E0E0
    TREE_SELECT  = Color.FromArgb(232, 245, 233)  # verde menta selección

    # ── Botones de toolbar ────────────────────────────────────────────────────
    SEL_GREEN    = Color.FromArgb( 15, 118, 110)  # teal seleccionar
    BOX_BLUE     = Color.FromArgb(0, 120, 212)  # púrpura section box

    # ── Tarjetas de estado (pastel) ───────────────────────────────────────────
    CARD_NEW_BG       = Color.FromArgb(249, 190, 190)  # #F9BEBE rojo pastel
    CARD_NEW_FG       = Color.FromArgb(123,  17,  16)  # #7B1110 rojo oscuro
    CARD_ACTIVE_BG    = Color.FromArgb(253, 228, 179)  # #FDE4B3 naranja pastel
    CARD_ACTIVE_FG    = Color.FromArgb(125,  70,   0)  # #7D4600 naranja oscuro
    CARD_APPROVED_BG  = Color.FromArgb(197, 230, 198)  # #C5E6C6 verde pastel
    CARD_APPROVED_FG  = Color.FromArgb( 27,  94,  32)  # #1B5E20 verde oscuro
    CARD_RESOLVED_BG  = Color.FromArgb(254, 243, 173)  # #FEF3AD amarillo pastel
    CARD_RESOLVED_FG  = Color.FromArgb(126, 108,   0)  # #7E6C00 amarillo oscuro
    CARD_TOTAL_BG     = Color.FromArgb(204, 229, 255)  # #CCE5FF azul pastel
    CARD_TOTAL_FG     = Color.FromArgb(  4,  53, 114)  # azul oscuro

    # ── Colores de estado para badges en lista ────────────────────────────────
    STATUS_COLORS = {
        "new":      Color.FromArgb(123,  17,  16),  # #7B1110 rojo oscuro
        "nuevo":    Color.FromArgb(123,  17,  16),
        "active":   Color.FromArgb(125,  70,   0),  # #7D4600 naranja oscuro
        "activo":   Color.FromArgb(125,  70,   0),
        "reviewed": Color.FromArgb(  1,  78, 115),  # #014E73 azul oscuro
        "revisado": Color.FromArgb(  1,  78, 115),
        "approved": Color.FromArgb( 27,  94,  32),  # #1B5E20 verde oscuro
        "aprobado": Color.FromArgb( 27,  94,  32),
        "resolved": Color.FromArgb(126, 108,   0),  # #7E6C00 amarillo oscuro
        "resuelto": Color.FromArgb(126, 108,   0),
    }
    STATUS_BG = {
        "new":      Color.FromArgb(249, 190, 190),  # #F9BEBE rojo pastel
        "nuevo":    Color.FromArgb(249, 190, 190),
        "active":   Color.FromArgb(253, 228, 179),  # #FDE4B3 naranja pastel
        "activo":   Color.FromArgb(253, 228, 179),
        "reviewed": Color.FromArgb(179, 228, 249),  # #B3E4F9 azul pastel
        "revisado": Color.FromArgb(179, 228, 249),
        "approved": Color.FromArgb(197, 230, 198),  # #C5E6C6 verde pastel
        "aprobado": Color.FromArgb(197, 230, 198),
        "resolved": Color.FromArgb(254, 243, 173),  # #FEF3AD amarillo pastel
        "resuelto": Color.FromArgb(254, 243, 173),
    }
    # Puntos de color en la lista (vibrantes — color base original)
    STATUS_DOT = {
        "new":      Color.FromArgb(229,  57,  53),  # #E53935
        "nuevo":    Color.FromArgb(229,  57,  53),
        "active":   Color.FromArgb(251, 140,   0),  # #FB8C00
        "activo":   Color.FromArgb(251, 140,   0),
        "reviewed": Color.FromArgb(  3, 155, 229),  # #039BE5
        "revisado": Color.FromArgb(  3, 155, 229),
        "approved": Color.FromArgb( 67, 160,  71),  # #43A047
        "aprobado": Color.FromArgb( 67, 160,  71),
        "resolved": Color.FromArgb(253, 216,  53),  # #FDD835
        "resuelto": Color.FromArgb(253, 216,  53),
    }

    # ── Tipografía ────────────────────────────────────────────────────────────
    FONT_TITLE  = Font("Segoe UI", 8,  FontStyle.Bold,    GraphicsUnit.Point)
    FONT_BODY   = Font("Segoe UI", 8,  FontStyle.Regular, GraphicsUnit.Point)
    FONT_SMALL  = Font("Segoe UI", 7,  FontStyle.Regular, GraphicsUnit.Point)
    FONT_MONO   = Font("Segoe UI", 8,  FontStyle.Regular, GraphicsUnit.Point)
    FONT_HEADER = Font("Segoe UI", 10, FontStyle.Bold,    GraphicsUnit.Point)
    FONT_NUM    = Font("Segoe UI", 22, FontStyle.Bold,    GraphicsUnit.Point)
    FONT_BADGE  = Font("Segoe UI", 7,  FontStyle.Bold,    GraphicsUnit.Point)
    FONT_ICON   = Font("Segoe UI Symbol", 18, FontStyle.Regular, GraphicsUnit.Point)

    @staticmethod
    def status_color(status_str):
        key = (status_str or "").lower().strip()
        return Theme.STATUS_COLORS.get(key, Theme.TEXT_MUTED)

    @staticmethod
    def status_bg(status_str):
        key = (status_str or "").lower().strip()
        return Theme.STATUS_BG.get(key, Theme.BG_PANEL)

    @staticmethod
    def status_dot(status_str):
        key = (status_str or "").lower().strip()
        return Theme.STATUS_DOT.get(key, Theme.TEXT_MUTED)

    @staticmethod
    def status_label(status_str):
        mapping = {
            "new": "Nuevo", "nuevo": "Nuevo",
            "active": "Activo", "activo": "Activo",
            "reviewed": "Revisado", "revisado": "Revisado",
            "approved": "Aprobado", "aprobado": "Aprobado",
            "resolved": "Resuelto", "resuelto": "Resuelto",
        }
        return mapping.get((status_str or "").lower().strip(), status_str or u"—")

# ═════════════════════════════════════════════════════════════════════════════
# PARSER XML DE NAVISWORKS
# ═════════════════════════════════════════════════════════════════════════════
class ClashObject:
    """Representa un objeto involucrado en un clash (element_id + modelo)."""
    def __init__(self):
        self.element_id  = None   # int
        self.model_name  = ""     # nombre .rvt extraído del pathlink
        self.layer       = ""
        self.family_name = ""
        self.element_type= ""

class ClashItem:
    """Clash individual (clashresult) o grupo (clashgroup)."""
    def __init__(self):
        self.name        = ""
        self.guid        = ""
        self.status      = ""      # atributo XML: active, resolved, new, approved
        self.result_status = ""    # texto de <resultstatus>
        self.distance    = ""
        self.grid_loc    = ""
        self.created_date= ""
        self.is_group    = False
        self.objects     = []      # List[ClashObject]
        self.children    = []      # List[ClashItem]  (solo si is_group)
        self.image_href  = ""

class ClashTest:
    """Un <clashtest> completo."""
    def __init__(self):
        self.name     = ""
        self.status   = ""
        self.summary  = {}         # {active, approved, new, resolved, total}
        self.items    = []         # List[ClashItem]  (mezcla de results y groups)

class NavisworksXMLParser:
    """Parser robusto para XML de Navisworks (agrupados e individuales)."""

    @staticmethod
    def _rvt_name_from_pathlink(pathlink_el):
        """Extrae el nombre del .rvt desde los nodos del pathlink."""
        if pathlink_el is None:
            return ""
        for node in pathlink_el.findall("node"):
            txt = (node.text or "").strip()
            if ".rvt" in txt.lower():
                # "IDU-...-ST1-NG-01.rvt : 68 : location <Not Shared>"
                return txt.split(":")[0].strip()
        return ""

    @staticmethod
    def _element_id_from_objectattribute(obj_el):
        """Extrae el Element ID de <objectattribute>."""
        for attr in obj_el.findall("objectattribute"):
            name_el  = attr.find("name")
            value_el = attr.find("value")
            if name_el is not None and "Element ID" in (name_el.text or ""):
                try:
                    return int((value_el.text or "").strip())
                except ValueError:
                    pass
        return None

    @staticmethod
    def _parse_clash_object(obj_el):
        co = ClashObject()
        co.element_id  = NavisworksXMLParser._element_id_from_objectattribute(obj_el)
        layer_el       = obj_el.find("layer")
        co.layer       = (layer_el.text or "").strip() if layer_el is not None else ""
        co.model_name  = NavisworksXMLParser._rvt_name_from_pathlink(obj_el.find("pathlink"))
        for st in obj_el.findall("smarttags/smarttag"):
            n = (st.findtext("name") or "").strip()
            v = (st.findtext("value") or "").strip()
            if n == "Elemento Nombre":
                co.family_name = v
            elif n == "Elemento Tipo":
                co.element_type = v
        return co

    @staticmethod
    def _parse_date(created_el):
        if created_el is None:
            return ""
        d = created_el.find("date")
        if d is None:
            return ""
        try:
            return "{day}/{month}/{year} {hour}:{minute}".format(
                day   = d.get("day",   "?"),
                month = d.get("month", "?"),
                year  = d.get("year",  "?"),
                hour  = d.get("hour",  "00"),
                minute= d.get("minute","00"),
            )
        except Exception:
            return ""

    @classmethod
    def _parse_clash_result(cls, result_el, is_group=False):
        item = ClashItem()
        item.name       = result_el.get("name", "")
        item.guid       = result_el.get("guid", "")
        item.status     = result_el.get("status", "")
        item.distance   = result_el.get("distance", "")
        item.image_href = result_el.get("href", "")
        item.is_group   = is_group

        rs = result_el.find("resultstatus")
        item.result_status = (rs.text or "").strip() if rs is not None else item.status

        gl = result_el.find("gridlocation")
        item.grid_loc = (gl.text or "").strip() if gl is not None else ""

        item.created_date = cls._parse_date(result_el.find("createddate"))

        # Objetos directos
        item.objects = []
        for obj_el in result_el.findall("clashobjects/clashobject"):
            item.objects.append(cls._parse_clash_object(obj_el))

        # Sub-resultados (dentro de un grupo)
        item.children = []
        sub_results = result_el.find("clashresults")
        if sub_results is not None:
            for child in sub_results:
                tag = child.tag
                if tag == "clashresult":
                    item.children.append(cls._parse_clash_result(child, is_group=False))
                elif tag == "clashgroup":
                    item.children.append(cls._parse_clash_result(child, is_group=True))

        return item

    @classmethod
    def parse(cls, xml_path):
        """Retorna List[ClashTest]."""
        tree = ET.parse(xml_path)
        root = tree.getroot()

        tests = []
        for ct_el in root.iter("clashtest"):
            ct = ClashTest()
            ct.name   = ct_el.get("name", "Sin nombre")
            ct.status = ct_el.get("status", "")

            # Summary
            summ = ct_el.find("summary")
            if summ is not None:
                ct.summary = {
                    "active":   summ.get("active",   "0"),
                    "approved": summ.get("approved", "0"),
                    "new":      summ.get("new",      "0"),
                    "resolved": summ.get("resolved", "0"),
                    "total":    summ.get("total",    "0"),
                }

            # Clashes directos
            results_el = ct_el.find("clashresults")
            if results_el is not None:
                for child in results_el:
                    if child.tag == "clashresult":
                        ct.items.append(cls._parse_clash_result(child, is_group=False))
                    elif child.tag == "clashgroup":
                        ct.items.append(cls._parse_clash_result(child, is_group=True))

            tests.append(ct)

        return tests

# ═════════════════════════════════════════════════════════════════════════════
# EXTERNAL EVENT — SECTIONBOX
# ═════════════════════════════════════════════════════════════════════════════

class SectionBoxHandler(IExternalEventHandler):
    """
    Flujo en Execute (hilo de Revit):
      1. Calcular bbox de los elementos
      2. TX-1: crear vista CLASHRP si no existe
      3. RequestViewChange
      4. TX-2: IsSectionBoxActive + SetSectionBox
    El resultado (ok, msg) queda en self.result para que
    el form lo lea con un Timer.
    """

    def __init__(self):
        self.uidoc         = None
        self.doc           = None
        self.clash_objects = None
        self.result        = None   # (bool, str)

    # ── helpers ──────────────────────────────────────────────────

    def _find_clash_view(self):
        for v in FilteredElementCollector(self.doc).OfClass(View3D):
            try:
                if not v.IsTemplate and v.Name.strip().upper() == "CLASHRP":
                    return v
            except:
                pass
        return None

    def _find_3d_vft(self):
        for vft in FilteredElementCollector(self.doc).OfClass(ViewFamilyType):
            try:
                if vft.ViewFamily == ViewFamily.ThreeDimensional:
                    return vft
            except:
                pass
        return None

    def _build_all_docs(self):
        docs = {}
        try:
            b = os.path.basename(self.doc.PathName)
            docs[b] = self.doc
            docs[os.path.splitext(b)[0]] = self.doc
        except:
            pass
        for li in FilteredElementCollector(self.doc).OfClass(RevitLinkInstance):
            try:
                ld = li.GetLinkDocument()
                if ld is None:
                    continue
                b = os.path.basename(ld.PathName)
                docs[b] = ld
                docs[os.path.splitext(b)[0]] = ld
            except:
                pass
        return docs

    def _resolve_doc(self, co, all_docs):
        if not co.model_name:
            return self.doc
        if co.model_name in all_docs:
            return all_docs[co.model_name]
        mn = co.model_name.lower()
        for k, v in all_docs.items():
            if mn in k.lower() or k.lower() in mn:
                return v
        return self.doc

    def _link_transform(self, target_doc):
        for li in FilteredElementCollector(self.doc).OfClass(RevitLinkInstance):
            try:
                ld = li.GetLinkDocument()
                if ld and ld.Equals(target_doc):
                    return li.GetTotalTransform()
            except:
                pass
        return None

    def _compute_bbox(self, all_docs):
        INF = float("inf")
        mn_x =  INF; mn_y =  INF; mn_z =  INF
        mx_x = -INF; mx_y = -INF; mx_z = -INF
        found = False
        for co in self.clash_objects:
            try:
                if co.element_id is None:
                    continue
                tdoc = self._resolve_doc(co, all_docs)
                el   = tdoc.GetElement(ElementId(co.element_id))
                if el is None:
                    continue
                bb = el.get_BoundingBox(None)
                if bb is None:
                    continue
                if tdoc.Equals(self.doc):
                    bmin, bmax = bb.Min, bb.Max
                else:
                    tf = self._link_transform(tdoc)
                    if tf is None:
                        continue
                    p1 = tf.OfPoint(bb.Min)
                    p2 = tf.OfPoint(bb.Max)
                    bmin = XYZ(min(p1.X,p2.X), min(p1.Y,p2.Y), min(p1.Z,p2.Z))
                    bmax = XYZ(max(p1.X,p2.X), max(p1.Y,p2.Y), max(p1.Z,p2.Z))
                mn_x = min(mn_x, bmin.X); mx_x = max(mx_x, bmax.X)
                mn_y = min(mn_y, bmin.Y); mx_y = max(mx_y, bmax.Y)
                mn_z = min(mn_z, bmin.Z); mx_z = max(mx_z, bmax.Z)
                found = True
            except:
                pass
        if not found:
            return None, None
        return XYZ(mn_x, mn_y, mn_z), XYZ(mx_x, mx_y, mx_z)

    # ── Execute ──────────────────────────────────────────────────

    def Execute(self, app):

        # ─── 1. Calcular bbox (fuera de toda transacción) ─────────
        try:
            all_docs = self._build_all_docs()
            min_pt, max_pt = self._compute_bbox(all_docs)
        except Exception as ex:
            self.result = (False, u"Error calculando bbox: " + str(ex))
            return

        if min_pt is None:
            self.result = (False,
                u"BoundingBox no encontrado.\n"
                u"Los Element IDs no están en el modelo activo ni en sus links.")
            return

        # ─── 2. TX-1: crear vista si no existe ────────────────────
        try:
            clash_view = self._find_clash_view()
            if clash_view is None:
                vft = self._find_3d_vft()
                if vft is None:
                    self.result = (False, u"No hay ViewFamilyType 3D.")
                    return
                t1 = Transaction(self.doc, u"Crear vista CLASHRP")
                t1.Start()
                try:
                    clash_view = View3D.CreateIsometric(self.doc, vft.Id)
                    clash_view.Name = u"CLASHRP"
                    t1.Commit()
                except Exception as ex:
                    t1.RollBack()
                    self.result = (False, u"Error creando CLASHRP: " + str(ex))
                    return
        except Exception as ex:
            self.result = (False, u"Error buscando/creando vista: " + str(ex))
            return

        # ─── 3. Activar la vista ──────────────────────────────────
        try:
            self.uidoc.RequestViewChange(clash_view)
        except:
            pass

        # ─── 4. TX-2: aplicar SectionBox ─────────────────────────
        try:
            OFF = 3.0
            sb     = BoundingBoxXYZ()
            sb.Min = XYZ(min_pt.X - OFF, min_pt.Y - OFF, min_pt.Z - OFF)
            sb.Max = XYZ(max_pt.X + OFF, max_pt.Y + OFF, max_pt.Z + OFF)

            t2 = Transaction(self.doc, u"SectionBox CLASHRP")
            t2.Start()
            try:
                clash_view.IsSectionBoxActive = True
                clash_view.SetSectionBox(sb)
                t2.Commit()
            except Exception as ex:
                t2.RollBack()
                self.result = (False, u"Error en SetSectionBox: " + str(ex))
                return
        except Exception as ex:
            self.result = (False, u"Error preparando SectionBox: " + str(ex))
            return

        # ─── 5. Zoom directo sobre UIView de CLASHRP ────────────
        # ZoomAndCenterRectangle actua directamente sobre el viewport
        # de la vista, sin necesidad de que sea la vista activa.
        try:
            ui_view = None
            for uv in self.uidoc.GetOpenUIViews():
                if uv.ViewId == clash_view.Id:
                    ui_view = uv
                    break

            if ui_view is not None:
                ui_view.ZoomAndCenterRectangle(sb.Min, sb.Max)
            else:
                # La vista no estaba abierta aun: fallback a PostCommand
                try:
                    cmd_id = RevitCommandId.LookupPostableCommandId(
                        PostableCommand.ZoomToFit
                    )
                    app.PostCommand(cmd_id)
                except:
                    pass
        except:
            pass

        self.result = (True, u"\u2713 SectionBox aplicado en CLASHRP.")

    def GetName(self):
        return "SectionBox External Event"


# ═════════════════════════════════════════════════════════════════════════════
# SELECTOR DE ELEMENTOS EN REVIT
# ═════════════════════════════════════════════════════════════════════════════
class RevitElementSelector:
    """Selecciona elementos y crea SectionBox."""

    def __init__(self, uidoc, doc):
        self.uidoc = uidoc
        self.doc   = doc

    def _get_all_docs(self):

        docs = {}

        title = os.path.splitext(
            os.path.basename(self.doc.PathName)
        )[0]

        docs[title] = self.doc
        docs[os.path.basename(self.doc.PathName)] = self.doc

        collector = FilteredElementCollector(
            self.doc
        ).OfClass(RevitLinkInstance)

        for link_inst in collector:

            link_doc = link_inst.GetLinkDocument()

            if link_doc is None:
                continue

            link_name = os.path.basename(link_doc.PathName)
            link_title = os.path.splitext(link_name)[0]

            docs[link_name] = link_doc
            docs[link_title] = link_doc

        return docs

    # ─────────────────────────────────────────────
    # SELECCIONAR ELEMENTOS
    # ─────────────────────────────────────────────

    def select_elements(self, clash_objects):

        if not clash_objects:
            return False, "No hay objetos."

        all_docs = self._get_all_docs()

        ids_to_select = List[ElementId]()
        missing = []

        for co in clash_objects:

            if co.element_id is None:
                continue

            eid = ElementId(co.element_id)

            target_doc = None

            if co.model_name:

                if co.model_name in all_docs:
                    target_doc = all_docs[co.model_name]

                else:

                    mname_lower = co.model_name.lower()

                    for k, v in all_docs.items():

                        if (
                            mname_lower in k.lower()
                            or k.lower() in mname_lower
                        ):
                            target_doc = v
                            break

            if target_doc is None:
                target_doc = self.doc

            el = target_doc.GetElement(eid)

            if el is None:
                missing.append(str(co.element_id))
                continue

            # LOCAL
            if target_doc.Equals(self.doc):

                ids_to_select.Add(eid)

            # LINKEADO
            else:

                collector = FilteredElementCollector(
                    self.doc
                ).OfClass(RevitLinkInstance)

                for li in collector:

                    ld = li.GetLinkDocument()

                    if ld and ld.Equals(target_doc):

                        ids_to_select.Add(li.Id)
                        break

        if ids_to_select.Count == 0:

            return (
                False,
                "No encontrados:\n{}".format(
                    ", ".join(missing)
                )
            )

        self.uidoc.Selection.SetElementIds(ids_to_select)

        return (
            True,
            "Seleccionados {} elemento(s).".format(
                ids_to_select.Count
            )
        )
        
# ═════════════════════════════════════════════════════════════════════════════
# GUARDADO XML — Actualiza atributo status sin romper el documento
# ═════════════════════════════════════════════════════════════════════════════
class XMLStatusUpdater:
    """Actualiza el status de clashes en el XML original."""

    STATUS_MAP = {
        "Nuevo":    "new",
        "Activo":   "active",
        "Aprobado": "approved",
        "Resuelto": "resolved",
    }
    STATUS_RESULT_MAP = {
        "new":      "Nuevo",
        "active":   "Activo",
        "approved": "Aprobado",
        "resolved": "Resuelto",
    }

    @classmethod
    def update_and_save(cls, xml_path, changes_dict):
        """
        changes_dict = {guid: (new_status_attr, new_resultstatus_text)}
        Modifica el XML en disco y devuelve (ok, mensaje).
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            updated = 0
            for el in root.iter():
                if el.tag not in ("clashresult", "clashgroup"):
                    continue
                guid = el.get("guid", "")
                if guid in changes_dict:
                    new_attr, new_rs_text = changes_dict[guid]
                    el.set("status", new_attr)
                    rs_el = el.find("resultstatus")
                    if rs_el is not None:
                        rs_el.text = new_rs_text
                    updated += 1

            # Guardar sobre el mismo archivo
            tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            return True, "Guardado: {} registro(s) actualizados en\n{}".format(updated, xml_path)

        except Exception as ex:
            return False, "Error al guardar:\n{}".format(str(ex))

# ═════════════════════════════════════════════════════════════════════════════
# CONTROLES PERSONALIZADOS
# ═════════════════════════════════════════════════════════════════════════════
class DarkButton(Button):
    """
    Botón plano con esquinas redondeadas (radio=6px).
    Reutiliza el nombre DarkButton para no romper referencias existentes,
    pero aplica colores del tema claro.
    """
    RADIUS = 6

    def __init__(self, text="", accent=False, danger=False, success=False,
                 sel_green=False, box_blue=False, orange=False, ghost=False,
                 bold=False):
        super(DarkButton, self).__init__()
        self.Text      = text
        self.FlatStyle = FlatStyle.Flat
        self.Cursor    = WinForms.Cursors.Hand
        self.Font      = Theme.FONT_TITLE if (bold or accent) else Theme.FONT_BODY
        self.Height    = 30

        if sel_green:                          # Seleccionar → teal
            self._bg  = Theme.TEAL
            self._fg  = Theme.TEXT_WHITE
            self._brd = Theme.BG_PANEL
        elif box_blue:                         # SectionBox → púrpura
            self._bg  = Theme.BOX_BLUE
            self._fg  = Theme.TEXT_WHITE
            self._brd = Theme.BG_PANEL
        elif accent:                           # Guardar XML → azul
            self._bg  = Theme.ACCENT
            self._fg  = Theme.TEXT_WHITE
            self._brd = Theme.BG_PANEL
        elif success:                          # Cargar XML → verde
            self._bg  = Theme.SUCCESS
            self._fg  = Theme.TEXT_WHITE
            self._brd = Theme.BG_PANEL
        elif danger:
            self._bg  = Theme.DANGER
            self._fg  = Theme.TEXT_WHITE
            self._brd = Theme.BG_PANEL
        elif orange:                           # Aplicar cambios
            self._bg  = Theme.ORANGE
            self._fg  = Theme.TEXT_WHITE
            self._brd = Color.FromArgb(210, 100, 10)
        else:                                  # ghost / toolbar
            self._bg  = Theme.BG_HOVER
            self._fg  = Theme.TEXT_PRIMARY
            self._brd = Theme.BORDER

        self.BackColor = self._bg
        self.ForeColor = self._fg
        self.FlatAppearance.BorderSize = 0
        self.FlatAppearance.MouseOverBackColor = Color.FromArgb(
            max(self._bg.R - 18, 0),
            max(self._bg.G - 18, 0),
            max(self._bg.B - 18, 0)
        )
        self.SetStyle(ControlStyles.UserPaint |
                      ControlStyles.AllPaintingInWmPaint |
                      ControlStyles.OptimizedDoubleBuffer, True)
        self._hover = False
        self.MouseEnter += self._on_enter
        self.MouseLeave += self._on_leave

    def _on_enter(self, s, e):
        self._hover = True; self.Invalidate()
    def _on_leave(self, s, e):
        self._hover = False; self.Invalidate()

    def OnPaint(self, e):
        g  = e.Graphics
        g.SmoothingMode = D2.SmoothingMode.AntiAlias
        rc = self.ClientRectangle
        r  = self.RADIUS
        bg = (Color.FromArgb(max(self._bg.R-18,0),
                             max(self._bg.G-18,0),
                             max(self._bg.B-18,0))
              if self._hover else self._bg)

        # Ruta redondeada
        path = D2.GraphicsPath()
        path.AddArc(rc.X,             rc.Y,              r*2, r*2, 180, 90)
        path.AddArc(rc.Right - r*2,   rc.Y,              r*2, r*2, 270, 90)
        path.AddArc(rc.Right - r*2,   rc.Bottom - r*2,   r*2, r*2,   0, 90)
        path.AddArc(rc.X,             rc.Bottom - r*2,   r*2, r*2,  90, 90)
        path.CloseFigure()

        g.FillPath(Drawing.SolidBrush(bg), path)
        # Borde fino
        pen = Drawing.Pen(self._brd, 1.0)
        g.DrawPath(pen, path)
        pen.Dispose()
        path.Dispose()

        # Texto centrado
        fg = self._fg if self.Enabled else Theme.TEXT_MUTED
        sf = Drawing.StringFormat()
        sf.Alignment     = Drawing.StringAlignment.Center
        sf.LineAlignment = Drawing.StringAlignment.Center
        g.DrawString(self.Text, self.Font, Drawing.SolidBrush(fg),
                     Drawing.RectangleF(rc.X, rc.Y, rc.Width, rc.Height), sf)
        sf.Dispose()


class StatusBadge(Label):
    """Badge de estado con fondo pastel y texto oscuro."""
    def __init__(self, status_str=""):
        super(StatusBadge, self).__init__()
        self.AutoSize  = False
        self.Width     = 72
        self.Height    = 18
        self.TextAlign = Drawing.ContentAlignment.MiddleCenter
        self.Font      = Theme.FONT_BADGE
        self.set_status(status_str)

    def set_status(self, status_str):
        self.Text      = Theme.status_label(status_str)
        self.BackColor = Theme.status_bg(status_str)
        self.ForeColor = Theme.status_color(status_str)

# ═════════════════════════════════════════════════════════════════════════════
# TARJETA REDONDEADA DE ELEMENTO DIRECTO — owner-draw
# ═════════════════════════════════════════════════════════════════════════════
class _RoundedElementCard(Panel):
    """
    Tarjeta de elemento directo con esquinas redondeadas y borde de acento.
    Renderiza todo via OnPaint para evitar artefactos en los bordes.
    Al hacer clic llama a on_click(element_id) si se provee.
    """
    RADIUS = 8

    def __init__(self, accent_color, index, co, w, h, on_click=None):
        super(_RoundedElementCard, self).__init__()
        self._accent   = accent_color
        self._index    = index
        self._co       = co
        self._on_click = on_click   # callable(element_id) o None
        self._hover    = False
        self.Width     = w
        self.Height    = h
        self.BackColor = Theme.BG_PANEL   # fondo del contenedor (transparente visual)
        self.Cursor    = WinForms.Cursors.Hand
        self.SetStyle(
            ControlStyles.UserPaint |
            ControlStyles.AllPaintingInWmPaint |
            ControlStyles.OptimizedDoubleBuffer,
            True
        )
        self.MouseEnter += self._on_enter
        self.MouseLeave += self._on_leave
        if on_click is not None:
            self.Click += self._handle_click

    def _on_enter(self, s, e):
        self._hover = True
        self.Invalidate()

    def _on_leave(self, s, e):
        self._hover = False
        self.Invalidate()

    def _handle_click(self, s, e):
        if self._on_click is not None:
            self._on_click(self._co.element_id)

    def OnPaint(self, e):
        g  = e.Graphics
        g.SmoothingMode     = D2.SmoothingMode.AntiAlias
        g.TextRenderingHint = DrawingText.TextRenderingHint.ClearTypeGridFit
        rc = self.ClientRectangle
        r  = self.RADIUS

        # ── Fondo blanco redondeado (con hover suave) ──
        card_rect = Drawing.Rectangle(rc.X, rc.Y, rc.Width - 2, rc.Height - 3)
        path = D2.GraphicsPath()
        path.AddArc(card_rect.X,             card_rect.Y,              r*2, r*2, 180, 90)
        path.AddArc(card_rect.Right - r*2,   card_rect.Y,              r*2, r*2, 270, 90)
        path.AddArc(card_rect.Right - r*2,   card_rect.Bottom - r*2,   r*2, r*2,   0, 90)
        path.AddArc(card_rect.X,             card_rect.Bottom - r*2,   r*2, r*2,  90, 90)
        path.CloseFigure()

        # Fondo hover sutil
        bg_color = Theme.BG_HOVER if self._hover else Theme.BG_CARD
        g.FillPath(Drawing.SolidBrush(bg_color), path)

        # Borde externo del color acento (más intenso en hover)
        border_alpha = 120 if self._hover else 60
        pen_border = Drawing.Pen(Color.FromArgb(border_alpha, self._accent.R, self._accent.G, self._accent.B), 1.5)
        g.DrawPath(pen_border, path)
        pen_border.Dispose()
        path.Dispose()

        # ── Borde izquierdo de acento (4px redondeado solo en esquinas izq) ──
        acc_path = D2.GraphicsPath()
        acc_path.AddArc(card_rect.X, card_rect.Y, r*2, r*2, 180, 90)
        acc_path.AddLine(card_rect.X + r, card_rect.Y, card_rect.X + 4, card_rect.Y)
        acc_path.AddLine(card_rect.X + 4, card_rect.Y, card_rect.X + 4, card_rect.Bottom)
        acc_path.AddLine(card_rect.X + 4, card_rect.Bottom, card_rect.X + r, card_rect.Bottom)
        acc_path.AddArc(card_rect.X, card_rect.Bottom - r*2, r*2, r*2, 90, 90)
        acc_path.CloseFigure()
        g.FillPath(Drawing.SolidBrush(self._accent), acc_path)
        acc_path.Dispose()

        # ── Header: "⊞ ELEMENTO 1" (con ícono de búsqueda si tiene callback) ──
        click_hint = u" 🔍" if self._on_click is not None else u""
        hdr_txt  = u"\u229e  ELEMENTO {}{}".format(self._index, click_hint)
        hdr_font = Theme.FONT_TITLE
        hdr_rect = Drawing.RectangleF(float(14), float(5), float(card_rect.Width - 18), float(16))
        sf_l = Drawing.StringFormat()
        sf_l.LineAlignment = Drawing.StringAlignment.Center
        g.DrawString(hdr_txt, hdr_font, Drawing.SolidBrush(self._accent), hdr_rect, sf_l)

        # ── Separador bajo el header ──
        sep_y = 23
        g.DrawLine(Drawing.Pen(Theme.BORDER, 1), 14, sep_y, card_rect.Width - 4, sep_y)

        # ── Filas de datos ──
        rows = [
            (u"ID:",      str(self._co.element_id) if self._co.element_id else u"N/A"),
            (u"Modelo:",  self._co.model_name  or u"\u2014"),
            (u"Familia:", self._co.family_name or u"\u2014"),
            (u"Capa:",    self._co.layer       or u"\u2014"),
        ]
        lbl_font = Font("Segoe UI", 7, FontStyle.Regular, GraphicsUnit.Point)
        val_font = Font("Segoe UI", 7, FontStyle.Bold,    GraphicsUnit.Point)
        ry = 27
        for lbl_t, val_t in rows:
            lbl_rect = Drawing.RectangleF(float(14), float(ry), float(54), float(13))
            val_rect = Drawing.RectangleF(float(70), float(ry), float(card_rect.Width - 76), float(13))
            sf_l2 = Drawing.StringFormat(); sf_l2.LineAlignment = Drawing.StringAlignment.Center
            g.DrawString(lbl_t, lbl_font, Drawing.SolidBrush(Theme.TEXT_MUTED),  lbl_rect, sf_l2)
            g.DrawString(val_t, val_font, Drawing.SolidBrush(Theme.TEXT_PRIMARY), val_rect, sf_l2)
            ry += 15
        lbl_font.Dispose()
        val_font.Dispose()


# ═════════════════════════════════════════════════════════════════════════════
# PANEL DE DETALLE DE CLASH
# ═════════════════════════════════════════════════════════════════════════════
class ClashDetailPanel(Panel):
    """Panel derecho que muestra info del clash seleccionado. Tema claro."""

    def __init__(self):
        super(ClashDetailPanel, self).__init__()
        self.BackColor = Theme.BG_PANEL
        self.Padding   = WinForms.Padding(10)
        self._build_ui()
        self.current_item = None
        self._loading = False   # flag para suprimir eventos durante carga
        self.on_element_click = None   # callable(element_id) inyectado por ClashManagerForm
        
    def _build_ui(self):

        # HEADER
        lbl_title = Label()
        lbl_title.Text      = u"\u2261  DETALLE DE INCIDENCIA"
        lbl_title.Font      = Theme.FONT_TITLE
        lbl_title.ForeColor = Color.FromArgb(30,  90, 160)
        lbl_title.BackColor = Color.FromArgb(220, 235, 250)
        lbl_title.Dock      = DockStyle.Top
        lbl_title.Height    = 26
        lbl_title.Padding   = WinForms.Padding(6, 0, 0, 0)
        lbl_title.TextAlign = Drawing.ContentAlignment.MiddleLeft

        # INFO — Panel scrollable con tarjetas estructuradas
        self._scroll_panel = Panel()
        self._scroll_panel.Dock       = DockStyle.Fill
        self._scroll_panel.AutoScroll = True
        self._scroll_panel.BackColor  = Theme.BG_PANEL
        self._scroll_panel.Padding    = WinForms.Padding(8, 6, 8, 6)

        # Placeholder cuando no hay item
        self._lbl_placeholder = Label()
        self._lbl_placeholder.Text      = u"Seleccione un clash en el árbol para ver el detalle."
        self._lbl_placeholder.ForeColor = Theme.TEXT_MUTED
        self._lbl_placeholder.Font      = Theme.FONT_BODY
        self._lbl_placeholder.AutoSize  = False
        self._lbl_placeholder.Dock      = DockStyle.Fill
        self._lbl_placeholder.TextAlign = Drawing.ContentAlignment.MiddleCenter
        self._scroll_panel.Controls.Add(self._lbl_placeholder)

        # ── PANEL DE ACCIONES INFERIOR ────────────────────────────────────────
        # Orden: SECCIÓN BOX → SELECCIONAR → ESTADO
        # Ancho de ventana ~500px → botones de ~130px cada uno
        pnl_bottom = Panel()
        pnl_bottom.BackColor = Theme.BG_PANEL
        pnl_bottom.Dock      = DockStyle.Bottom
        pnl_bottom.Height    = 132

        # Línea separadora superior del panel
        sep = Panel()
        sep.BackColor = Theme.BORDER
        sep.Height    = 1
        sep.Dock      = DockStyle.Top

        W1 = 151   # ancho botón elemento 1 y 2
        W2 = 82    # ancho botón "Ambos" / "Box Ambos"
        X1 = 10    # label inicio
        X2 = 96    # botón 1
        X3 = X2 + W1 + 4
        X4 = X3 + W1 + 4

        # ── FILA 1: SECCIÓN BOX (púrpura) ─────────────────────────────────────
        lbl_box = Label()
        lbl_box.Text      = u"Secc. Box:"
        lbl_box.ForeColor = Theme.TEXT_MUTED
        lbl_box.Font      = Theme.FONT_BODY
        lbl_box.AutoSize  = True
        lbl_box.Location  = Drawing.Point(X1, 8)

        self.btn_box1 = DarkButton(u"Elem. 1", box_blue=True)
        self.btn_box1.Width    = W1
        self.btn_box1.Height   = 26
        self.btn_box1.Location = Drawing.Point(X2, 4)
        self.btn_box1.Enabled  = False

        self.btn_box2 = DarkButton(u"Elem. 2", box_blue=True)
        self.btn_box2.Width    = W1
        self.btn_box2.Height   = 26
        self.btn_box2.Location = Drawing.Point(X3, 4)
        self.btn_box2.Enabled  = False

        self.btn_box_ambos = DarkButton(u"Ambos", box_blue=True)
        self.btn_box_ambos.Width    = W2
        self.btn_box_ambos.Height   = 26
        self.btn_box_ambos.Location = Drawing.Point(X4, 4)
        self.btn_box_ambos.Enabled  = False

        # ── FILA 2: SELECCIONAR (teal) ────────────────────────────────────────
        lbl_sel = Label()
        lbl_sel.Text      = u"Seleccionar:"
        lbl_sel.ForeColor = Theme.TEXT_MUTED
        lbl_sel.Font      = Theme.FONT_BODY
        lbl_sel.AutoSize  = True
        lbl_sel.Location  = Drawing.Point(X1, 40)

        self.btn_sel1 = DarkButton(u"Elemento 1", sel_green=True)
        self.btn_sel1.Width    = W1
        self.btn_sel1.Height   = 26
        self.btn_sel1.Location = Drawing.Point(X2, 36)
        self.btn_sel1.Enabled  = False

        self.btn_sel2 = DarkButton(u"Elemento 2", sel_green=True)
        self.btn_sel2.Width    = W1
        self.btn_sel2.Height   = 26
        self.btn_sel2.Location = Drawing.Point(X3, 36)
        self.btn_sel2.Enabled  = False

        self.btn_sel_ambos = DarkButton(u"Ambos", sel_green=True)
        self.btn_sel_ambos.Width    = W2
        self.btn_sel_ambos.Height   = 26
        self.btn_sel_ambos.Location = Drawing.Point(X4, 36)
        self.btn_sel_ambos.Enabled  = False

        # ── FILA 3: BOTONES DE ESTADO RÁPIDO ─────────────────────────────────
        lbl_st = Label()
        lbl_st.Text      = u"Estado:"
        lbl_st.ForeColor = Theme.TEXT_MUTED
        lbl_st.Font      = Theme.FONT_BODY
        lbl_st.AutoSize  = True
        lbl_st.Location  = Drawing.Point(X1, 72)

        STATUS_BTNS = [
            (u"● Nuevo",    "Nuevo",    Theme.CARD_NEW_BG,      Theme.CARD_NEW_FG),
            (u"● Activo",   "Activo",   Theme.CARD_ACTIVE_BG,   Theme.CARD_ACTIVE_FG),
            (u"● Aprobado", "Aprobado", Theme.CARD_APPROVED_BG, Theme.CARD_APPROVED_FG),
            (u"● Resuelto", "Resuelto", Theme.CARD_RESOLVED_BG, Theme.CARD_RESOLVED_FG),
        ]
        self._status_btns = {}
        sbtn_x = X2
        sbtn_w = 96
        for text, key, bg, fg in STATUS_BTNS:
            btn = DarkButton(text)
            btn.Width    = sbtn_w
            btn.Height   = 26
            btn.Location = Drawing.Point(sbtn_x, 68)
            btn.Enabled  = False
            btn._bg  = bg
            btn._fg  = fg
            btn._brd = Theme.BORDER
            btn.BackColor = bg
            btn.ForeColor = fg
            btn.FlatAppearance.MouseOverBackColor = Color.FromArgb(
                max(bg.R - 20, 0), max(bg.G - 20, 0), max(bg.B - 20, 0)
            )
            pnl_bottom.Controls.Add(btn)
            self._status_btns[key] = btn
            sbtn_x += sbtn_w + 4

        # ComboBox oculto — mantiene la lógica de _on_status_changed_inline
        self.cmb_status = ComboBox()
        self.cmb_status.Items.AddRange(Array[object](
            [u"Nuevo", u"Activo", u"Aprobado", u"Resuelto"]
        ))
        self.cmb_status.Visible       = False
        self.cmb_status.DropDownStyle = WinForms.ComboBoxStyle.DropDownList
        # ── MENSAJES / ESTADO ─────────────────────────────────────
        self.lbl_message = Label()
        self.lbl_message.Text      = u""
        self.lbl_message.ForeColor = Color.FromArgb(30, 90, 160)
        self.lbl_message.BackColor = Color.FromArgb(220, 235, 250)
        self.lbl_message.Font      = Theme.FONT_SMALL
        self.lbl_message.AutoSize  = False
        self.lbl_message.Width     = 490
        self.lbl_message.Height    = 22
        self.lbl_message.Location  = Drawing.Point(6, 108)
        self.lbl_message.TextAlign = Drawing.ContentAlignment.MiddleLeft
        self.lbl_message.Padding   = WinForms.Padding(4, 0, 0, 0)
        # ── SEPARADOR INFERIOR ─────────────────────────────
        self.bottom_separator = Panel()
        self.bottom_separator.BackColor = Theme.BORDER
        self.bottom_separator.Width  = 470
        self.bottom_separator.Height = 1
        self.bottom_separator.Location = Drawing.Point(10, 128)

        # ADD CONTROLS
        pnl_bottom.Controls.Add(sep)
        pnl_bottom.Controls.Add(lbl_box)
        pnl_bottom.Controls.Add(self.btn_box1)
        pnl_bottom.Controls.Add(self.btn_box2)
        pnl_bottom.Controls.Add(self.btn_box_ambos)
        pnl_bottom.Controls.Add(lbl_sel)
        pnl_bottom.Controls.Add(self.btn_sel1)
        pnl_bottom.Controls.Add(self.btn_sel2)
        pnl_bottom.Controls.Add(self.btn_sel_ambos)
        pnl_bottom.Controls.Add(lbl_st)
        pnl_bottom.Controls.Add(self.cmb_status)
        pnl_bottom.Controls.Add(self.lbl_message)
        pnl_bottom.Controls.Add(self.bottom_separator)

        self.Controls.Add(self._scroll_panel)
        self.Controls.Add(pnl_bottom)
        self.Controls.Add(lbl_title)

    def _make_info_row(self, label, value, y):
        """Crea una fila de label+valor para el panel de info."""
        lbl = Label()
        lbl.Text      = label
        lbl.ForeColor = Theme.TEXT_MUTED
        lbl.Font      = Theme.FONT_SMALL
        lbl.AutoSize  = False
        lbl.Width     = 72
        lbl.Height    = 16
        lbl.Location  = Drawing.Point(0, y)
        lbl.TextAlign = Drawing.ContentAlignment.MiddleLeft

        val = Label()
        val.Text      = value
        val.ForeColor = Theme.TEXT_PRIMARY
        val.Font      = Theme.FONT_BODY
        val.AutoSize  = False
        val.Width     = 340
        val.Height    = 16
        val.Location  = Drawing.Point(76, y)
        val.TextAlign = Drawing.ContentAlignment.MiddleLeft
        return lbl, val

    def _make_element_card(self, co, index, panel_w):
        """Crea una tarjeta de elemento directo (ClashObject) estilo imagen."""
        accent_color = Color.FromArgb(30, 90, 160) if index == 1 else Color.FromArgb(15, 118, 110)

        # Callback para seleccionar en árbol todos los clashes con el mismo elemento
        on_click = self.on_element_click if (co.element_id is not None and self.on_element_click is not None) else None

        # Panel owner-draw con esquinas redondeadas
        card = _RoundedElementCard(
            accent_color = accent_color,
            index        = index,
            co           = co,
            w            = panel_w - 4,
            h            = 94,
            on_click     = on_click
        )
        return card

    def show_item(self, item):
        self.current_item = item

        # Limpiar panel scrollable
        self._scroll_panel.Controls.Clear()

        if item is None:
            self._scroll_panel.Controls.Add(self._lbl_placeholder)
            self.btn_sel1.Enabled      = False
            self.btn_sel2.Enabled      = False
            self.btn_sel_ambos.Enabled = False
            self.btn_box1.Enabled      = False
            self.btn_box2.Enabled      = False
            self.btn_box_ambos.Enabled = False
            return

        direct_objs = item.objects
        panel_w = self._scroll_panel.ClientSize.Width - 20
        if panel_w < 200:
            panel_w = 460

        y = 4

        # ── SECCIÓN INFO DEL CLASH ────────────────────────────────────────────
        lbl_sec = Label()
        lbl_sec.Text      = u"INFORMACIÓN DEL CLASH"
        lbl_sec.Font      = Theme.FONT_BADGE
        lbl_sec.ForeColor = Theme.TEXT_MUTED
        lbl_sec.AutoSize  = False
        lbl_sec.Width     = panel_w
        lbl_sec.Height    = 14
        lbl_sec.Location  = Drawing.Point(0, y)
        self._scroll_panel.Controls.Add(lbl_sec)
        y += 16

        # Tarjeta de info general — 2 columnas, bordes redondeados
        info_card = Panel()
        info_card.BackColor  = Theme.BG_CARD
        info_card.Width      = panel_w
        info_card.Height     = 76
        info_card.Location   = Drawing.Point(0, y)
        info_card.Padding    = WinForms.Padding(8, 4, 8, 4)

        def _paint_rounded_border(sender, pe):
            rc2 = sender.ClientRectangle
            rad = 8
            pe.Graphics.SmoothingMode = D2.SmoothingMode.AntiAlias
            # Fondo
            bp2 = D2.GraphicsPath()
            bp2.AddArc(rc2.X,             rc2.Y,              rad*2, rad*2, 180, 90)
            bp2.AddArc(rc2.Right - rad*2, rc2.Y,              rad*2, rad*2, 270, 90)
            bp2.AddArc(rc2.Right - rad*2, rc2.Bottom - rad*2, rad*2, rad*2,   0, 90)
            bp2.AddArc(rc2.X,             rc2.Bottom - rad*2, rad*2, rad*2,  90, 90)
            bp2.CloseFigure()
            pe.Graphics.FillPath(Drawing.SolidBrush(Theme.BG_CARD), bp2)
            pe.Graphics.DrawPath(Drawing.Pen(Theme.BORDER, 1), bp2)
            bp2.Dispose()
            sender.CreateGraphics().Dispose()

        info_card.Paint += _paint_rounded_border

        col_w   = (panel_w - 20) // 2
        left_rows = [
            (u"Nombre",  item.name),
            (u"GUID",    (item.guid[:20] + u"…") if len(item.guid) > 20 else item.guid),
            (u"Estado",  Theme.status_label(item.status)),
            (u"Dist.",   (u"{} m".format(item.distance)) if item.distance else u"—"),
        ]
        right_rows = [
            (u"Grid",    item.grid_loc or u"—"),
            (u"Fecha",   item.created_date or u"—"),
            (u"Tipo",    u"GRUPO" if item.is_group else u"Clash"),
        ]
        for i, (lbl_t, val_t) in enumerate(left_rows):
            iry = 4 + i * 17
            l = Label(); l.Text = lbl_t + u":"; l.ForeColor = Theme.TEXT_MUTED
            l.Font = Theme.FONT_SMALL; l.AutoSize = False; l.Width = 48; l.Height = 14
            l.Location = Drawing.Point(8, iry); l.TextAlign = Drawing.ContentAlignment.MiddleLeft
            info_card.Controls.Add(l)
            v = Label(); v.Text = val_t; v.ForeColor = Theme.TEXT_PRIMARY
            v.Font = Theme.FONT_SMALL; v.AutoSize = False; v.Width = col_w - 52; v.Height = 14
            v.Location = Drawing.Point(58, iry); v.TextAlign = Drawing.ContentAlignment.MiddleLeft
            info_card.Controls.Add(v)
        for i, (lbl_t, val_t) in enumerate(right_rows):
            iry = 4 + i * 17
            l2 = Label(); l2.Text = lbl_t + u":"; l2.ForeColor = Theme.TEXT_MUTED
            l2.Font = Theme.FONT_SMALL; l2.AutoSize = False; l2.Width = 36; l2.Height = 14
            l2.Location = Drawing.Point(col_w + 12, iry); l2.TextAlign = Drawing.ContentAlignment.MiddleLeft
            info_card.Controls.Add(l2)
            v2 = Label(); v2.Text = val_t; v2.ForeColor = Theme.TEXT_PRIMARY
            v2.Font = Theme.FONT_SMALL; v2.AutoSize = False; v2.Width = col_w - 40; v2.Height = 14
            v2.Location = Drawing.Point(col_w + 52, iry); v2.TextAlign = Drawing.ContentAlignment.MiddleLeft
            info_card.Controls.Add(v2)

        self._scroll_panel.Controls.Add(info_card)
        y += info_card.Height + 10

        # ── SECCIÓN ELEMENTOS DIRECTOS ────────────────────────────────────────
        if direct_objs:
            lbl_elem = Label()
            lbl_elem.Text      = u"\u26AF  ELEMENTOS DIRECTOS"
            lbl_elem.Font      = Theme.FONT_BADGE
            lbl_elem.ForeColor = Theme.TEXT_MUTED
            lbl_elem.AutoSize  = False
            lbl_elem.Width     = panel_w
            lbl_elem.Height    = 14
            lbl_elem.Location  = Drawing.Point(0, y)
            self._scroll_panel.Controls.Add(lbl_elem)
            y += 16

            # Dos tarjetas side-by-side si caben, o apiladas
            card_w = (panel_w - 6) // 2 if len(direct_objs) >= 2 else panel_w
            for i, co in enumerate(direct_objs[:2]):
                ec = self._make_element_card(co, i + 1, card_w)
                ec.Location = Drawing.Point(i * (card_w + 6), y)
                self._scroll_panel.Controls.Add(ec)
            y += 98

        # ── CONTENIDO DEL GRUPO ───────────────────────────────────────────────
        if item.is_group and item.children:
            lbl_grp = Label()
            lbl_grp.Text      = u"CONTENIDO DEL GRUPO ({} clashes)".format(len(item.children))
            lbl_grp.Font      = Theme.FONT_BADGE
            lbl_grp.ForeColor = Theme.TEXT_MUTED
            lbl_grp.AutoSize  = False
            lbl_grp.Width     = panel_w
            lbl_grp.Height    = 14
            lbl_grp.Location  = Drawing.Point(0, y)
            self._scroll_panel.Controls.Add(lbl_grp)
            y += 18
            for child in item.children:
                cl = Label()
                cl.Text      = u"  \u2022  {}  [{}]".format(child.name, Theme.status_label(child.status))
                cl.ForeColor = Theme.status_color(child.status)
                cl.Font      = Theme.FONT_SMALL
                cl.AutoSize  = False
                cl.Width     = panel_w
                cl.Height    = 14
                cl.Location  = Drawing.Point(0, y)
                self._scroll_panel.Controls.Add(cl)
                y += 15

        # ── Habilitar botones ─────────────────────────────────────────────────
        has_obj1 = len(direct_objs) >= 1 and direct_objs[0].element_id is not None
        has_obj2 = len(direct_objs) >= 2 and direct_objs[1].element_id is not None

        self.btn_sel1.Enabled      = has_obj1
        self.btn_sel2.Enabled      = has_obj2
        self.btn_sel_ambos.Enabled = has_obj1 or has_obj2
        self.btn_box1.Enabled      = has_obj1
        self.btn_box2.Enabled      = has_obj2
        self.btn_box_ambos.Enabled = has_obj1 or has_obj2

        lbl1 = direct_objs[0].family_name if has_obj1 and direct_objs[0].family_name else u"Elemento 1"
        lbl2 = direct_objs[1].family_name if has_obj2 and direct_objs[1].family_name else u"Elemento 2"
        lbl1 = lbl1[:18] + u"\u2026" if len(lbl1) > 18 else lbl1
        lbl2 = lbl2[:18] + u"\u2026" if len(lbl2) > 18 else lbl2
        self.btn_sel1.Text = u"  {}".format(lbl1)
        self.btn_sel2.Text = u"  {}".format(lbl2)
        self.btn_box1.Text = u"  {}".format(lbl1)
        self.btn_box2.Text = u"  {}".format(lbl2)

        # ── Estado en combobox — sin disparar el evento ───────────────────────
        self._loading = True
        label = Theme.status_label(item.status)
        if label in [u"Nuevo", u"Activo", u"Aprobado", u"Resuelto"]:
            self.cmb_status.SelectedItem = label
        else:
            self.cmb_status.SelectedIndex = 0
        self._loading = False

    def get_direct_object(self, index):
        """Retorna el ClashObject en posición index (0 o 1) del item actual, o None."""
        item = self.current_item
        if item is None or index >= len(item.objects):
            return None
        return item.objects[index]

    def get_all_direct_objects(self):
        """Retorna los objetos directos del item actual (no recorre hijos)."""
        if self.current_item is None:
            return []
        return list(self.current_item.objects)

    def _collect_all_objects(self, item):
        """Recorre recursivamente (para grupos)."""
        objs = list(item.objects)
        for child in item.children:
            objs.extend(self._collect_all_objects(child))
        return objs

    def get_current_status(self):
        sel = self.cmb_status.SelectedItem
        return str(sel) if sel else "Activo"

# ═════════════════════════════════════════════════════════════════════════════
# TARJETA REDONDEADA — owner-draw Panel para las métricas
# ═════════════════════════════════════════════════════════════════════════════
class _RoundedCard(Panel):
    """
    Tarjeta con esquinas redondeadas, número grande y etiqueta.
    Soporta estado activo (toggle de filtro) dibujando un borde de acento.
    """
    SHADOW_COLOR = Color.FromArgb(18, 0, 0, 0)

    def __init__(self, val="0", label=u"", bg=None, fg=None, radius=8, w=108, h=64, icon=u""):
        super(_RoundedCard, self).__init__()
        self._val    = val
        self._label  = label
        self._bg     = bg or Color.White
        self._fg     = fg or Theme.TEXT_PRIMARY
        self._radius = radius
        self._active = False
        self._icon   = icon
        self.Width   = w
        self.Height  = h
        self.BackColor = Theme.BG_PANEL
        self.Cursor    = WinForms.Cursors.Hand
        self.SetStyle(
            ControlStyles.UserPaint |
            ControlStyles.AllPaintingInWmPaint |
            ControlStyles.OptimizedDoubleBuffer,
            True
        )

    def set_active(self, active):
        self._active = active
        self.Invalidate()

    def set_value(self, val):
        """Actualiza solo el número sin destruir ni recrear el control (evita parpadeo)."""
        self._val = str(val)
        self.Invalidate()

    def OnPaint(self, e):
        g  = e.Graphics
        g.SmoothingMode      = D2.SmoothingMode.AntiAlias
        g.TextRenderingHint  = DrawingText.TextRenderingHint.ClearTypeGridFit
        rc = self.ClientRectangle
        r  = self._radius

        # ── Sombra ──
        shadow_rect = Drawing.Rectangle(rc.X + 1, rc.Y + 2, rc.Width - 2, rc.Height - 2)
        shadow_path = D2.GraphicsPath()
        shadow_path.AddArc(shadow_rect.X,               shadow_rect.Y,              r*2, r*2, 180, 90)
        shadow_path.AddArc(shadow_rect.Right - r*2,     shadow_rect.Y,              r*2, r*2, 270, 90)
        shadow_path.AddArc(shadow_rect.Right - r*2,     shadow_rect.Bottom - r*2,   r*2, r*2,   0, 90)
        shadow_path.AddArc(shadow_rect.X,               shadow_rect.Bottom - r*2,   r*2, r*2,  90, 90)
        shadow_path.CloseFigure()
        g.FillPath(Drawing.SolidBrush(self.SHADOW_COLOR), shadow_path)
        shadow_path.Dispose()

        # ── Fondo redondeado ──
        card_rect = Drawing.Rectangle(rc.X, rc.Y, rc.Width - 2, rc.Height - 3)
        card_path = D2.GraphicsPath()
        card_path.AddArc(card_rect.X,             card_rect.Y,              r*2, r*2, 180, 90)
        card_path.AddArc(card_rect.Right - r*2,   card_rect.Y,              r*2, r*2, 270, 90)
        card_path.AddArc(card_rect.Right - r*2,   card_rect.Bottom - r*2,   r*2, r*2,   0, 90)
        card_path.AddArc(card_rect.X,             card_rect.Bottom - r*2,   r*2, r*2,  90, 90)
        card_path.CloseFigure()
        g.FillPath(Drawing.SolidBrush(self._bg), card_path)

        # ── Borde: acento grueso si activo, fino si no ──
        if self._active:
            pen = Drawing.Pen(self._fg, 2.5)
        else:
            pen = Drawing.Pen(Theme.BORDER, 1.0)
        g.DrawPath(pen, card_path)
        pen.Dispose()
        card_path.Dispose()

        sf = Drawing.StringFormat()
        sf.Alignment     = Drawing.StringAlignment.Center
        sf.LineAlignment = Drawing.StringAlignment.Center

        # ── Icono izquierdo ──
        icon_w = 36
        if self._icon:
            icon_rect = Drawing.RectangleF(
                float(card_rect.X + 4), float(card_rect.Y + 4),
                float(icon_w), float(card_rect.Height - 8)
            )
            icon_font = Font("Segoe UI Emoji", 15, FontStyle.Regular, GraphicsUnit.Point)
            g.DrawString(self._icon, icon_font, Drawing.SolidBrush(self._fg), icon_rect, sf)
            icon_font.Dispose()

        # ── Número grande (zona derecha) ──
        right_x = card_rect.X + (icon_w + 6 if self._icon else 4)
        right_w = card_rect.Right - right_x - 4
        num_font = Font("Segoe UI", 18, FontStyle.Bold, GraphicsUnit.Point)
        num_rect = Drawing.RectangleF(
            float(right_x), float(card_rect.Y + 2),
            float(right_w), float(card_rect.Height - 22)
        )
        g.DrawString(self._val, num_font, Drawing.SolidBrush(self._fg), num_rect, sf)
        num_font.Dispose()

        # ── Etiqueta inferior ──
        lbl_font = Font("Segoe UI", 7, FontStyle.Regular, GraphicsUnit.Point)
        lbl_rect = Drawing.RectangleF(
            float(right_x), float(card_rect.Bottom - 18),
            float(right_w), 16.0
        )
        lbl_col = self._fg if self._active else Theme.TEXT_MUTED
        g.DrawString(self._label, lbl_font, Drawing.SolidBrush(lbl_col), lbl_rect, sf)
        lbl_font.Dispose()
        sf.Dispose()


# ═════════════════════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL (MODELESS)
# ═════════════════════════════════════════════════════════════════════════════
class ClashManagerForm(Form):
    def __init__(self, uidoc, doc):
        super(ClashManagerForm, self).__init__()
        self.uidoc     = uidoc
        self.doc       = doc
        self.selector  = RevitElementSelector(uidoc, doc)
        self.sectionbox_handler = SectionBoxHandler()
        self.sectionbox_event = ExternalEvent.Create(
            self.sectionbox_handler
        )
        self.xml_path  = None
        self.clash_tests = []
        self._pending_changes = {}   # {guid: (status_attr, resultstatus_text)}
        self._node_item_map   = {}   # {TreeNode: ClashItem}  — nodos VISIBLES en árbol
        self._item_node_map   = {}   # {id(ClashItem): TreeNode}  — TODOS, O(1) lookup
        self._item_in_tree    = set()  # id(ClashItem) físicamente en el árbol
        self._ct_node_map     = {}   # {id(ClashTest): TreeNode header}
        self._filter_active   = set()  # labels activos como filtro
        self._stat_cards      = {}     # label → _RoundedCard

        # ── Multi-selección manual (Ctrl/Shift) ───────────────────────────────
        self._multi_selected_nodes = set()   # set de TreeNode seleccionados
        self._last_clicked_node    = None    # anchor para Shift-rango

        # Timer para leer el resultado del ExternalEvent (es asíncrono)
        self._result_timer = WinForms.Timer()
        self._result_timer.Interval = 300   # ms
        self._result_timer.Tick += self._on_result_timer

        self._setup_form()
        self._build_ui()
        self.Load += self._on_form_loaded
        self._update_status_bar("Cargue un archivo XML de Navisworks para comenzar.")

    def _on_result_timer(self, sender, e):
        """Lee el resultado del SectionBoxHandler cuando ya terminó."""
        res = self.sectionbox_handler.result
        if res is None:
            return
        self._result_timer.Stop()
        self.sectionbox_handler.result = None   # reset para siguiente uso
        ok, msg = res
        if ok:
            self._update_status_bar("OK: " + msg)
        else:
            self._update_status_bar("ERROR: " + msg)
            MessageBox.Show(msg, u"Error SectionBox",
                            MessageBoxButtons.OK, MessageBoxIcon.Error)

    def _on_form_loaded(self, sender, e):

        self.split_main.Panel1MinSize = 280
        self.split_main.Panel2MinSize = 200

        total_h = self.split_main.Height

        desired = 260

        max_allowed = total_h - self.split_main.Panel2MinSize

        if max_allowed < self.split_main.Panel1MinSize:
            max_allowed = self.split_main.Panel1MinSize

        self.split_main.SplitterDistance = min(desired, max_allowed)
    
    
    # ── Configuración de la ventana ──────────────────────────────────────────
    def _setup_form(self):
        self.Text            = u"Clash Manager — BIM"
        self.Width           = 560
        self.Height          = 820
        self.MinimumSize     = Drawing.Size(560, 600)
        self.BackColor       = Theme.BG_DARK
        self.ForeColor       = Theme.TEXT_PRIMARY
        self.Font            = Theme.FONT_BODY
        self.FormBorderStyle = FormBorderStyle.Sizable
        self.StartPosition   = FormStartPosition.Manual
        self.TopMost         = False
        self.ShowInTaskbar   = True
        self.Location        = Drawing.Point(80, 80)

    # ── Construcción UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        # ════════════════════════════════════════════════════════════════════
        # TOOLBAR — dos filas compactas
        # ════════════════════════════════════════════════════════════════════
        toolbar = Panel()
        toolbar.BackColor = Theme.BG_CARD
        toolbar.Dock      = DockStyle.Top
        toolbar.Height    = 80

        sep_toolbar = Panel()
        sep_toolbar.BackColor = Theme.BORDER
        sep_toolbar.Height    = 1
        sep_toolbar.Dock      = DockStyle.Bottom

        # Fila 1 — título
        lbl_logo = Label()
        lbl_logo.Text      = u"CLASH MANAGER  |  BIM Coordination"
        lbl_logo.Font      = Theme.FONT_TITLE
        lbl_logo.ForeColor = Theme.TEXT_PRIMARY
        lbl_logo.AutoSize  = False
        lbl_logo.Width     = 460
        lbl_logo.Height    = 18
        lbl_logo.Location  = Drawing.Point(10, 8)

        # Fila 2 — botones de acción
        self.btn_load = DarkButton(u"⬆ Cargar XML", success=True)
        self.btn_load.Width    = 115
        self.btn_load.Height   = 26
        self.btn_load.Location = Drawing.Point(10, 32)
        self.btn_load.Click   += self._on_load_xml

        self.btn_save = DarkButton(u"✔ Guardar XML", accent=True)
        self.btn_save.Width    = 115
        self.btn_save.Height   = 26
        self.btn_save.Location = Drawing.Point(135, 32)
        self.btn_save.Enabled  = False
        self.btn_save.Click   += self._on_save_xml

        self.btn_expand = DarkButton(u"+ Expandir")
        self.btn_expand.Width    = 115
        self.btn_expand.Height   = 26
        self.btn_expand.Location = Drawing.Point(260, 32)
        self.btn_expand.Enabled  = False
        self.btn_expand._bg  = Color.FromArgb(255, 255, 255)
        self.btn_expand._fg  = Color.FromArgb(30, 90, 160)
        self.btn_expand._brd = Color.FromArgb(150, 195, 235)
        self.btn_expand.Click   += self._on_expand_all

        self.btn_collapse = DarkButton(u"− Colapsar")
        self.btn_collapse.Width    = 115
        self.btn_collapse.Height   = 26
        self.btn_collapse.Location = Drawing.Point(385, 32)
        self.btn_collapse.Enabled  = False
        self.btn_collapse._bg  = Color.FromArgb(255, 255, 255)
        self.btn_collapse._fg  = Color.FromArgb(30, 90, 160)
        self.btn_collapse._brd = Color.FromArgb(150, 195, 235)
        self.btn_collapse.Click   += self._on_collapse_all

        toolbar.Controls.Add(sep_toolbar)
        toolbar.Controls.Add(lbl_logo)
        toolbar.Controls.Add(self.btn_load)
        toolbar.Controls.Add(self.btn_save)
        toolbar.Controls.Add(self.btn_expand)
        toolbar.Controls.Add(self.btn_collapse)

        # ════════════════════════════════════════════════════════════════════
        # STATS — fila horizontal de badges compactos (visible tras cargar)
        # ════════════════════════════════════════════════════════════════════
        self.stats_panel = Panel()
        self.stats_panel.BackColor = Theme.BG_PANEL
        self.stats_panel.Dock      = DockStyle.Top
        self.stats_panel.Height    = 90
        self.stats_panel.Visible   = False
        self._enable_double_buffer(self.stats_panel)

        sep_stats = Panel()
        sep_stats.BackColor = Theme.BORDER
        sep_stats.Height    = 1
        sep_stats.Dock      = DockStyle.Bottom
        self.stats_panel.Controls.Add(sep_stats)

        # ================================================================
        # PANEL ARBOL - arriba
        # ================================================================
        self.tree_panel = Panel()
        self.tree_panel.BackColor = Theme.BG_CARD
        self.tree_panel.Dock      = DockStyle.Fill

        self.tree = TreeView()
        self._enable_double_buffer(self.tree)
        self.tree.Dock          = DockStyle.Fill
        self.tree.BackColor     = Theme.BG_CARD
        self.tree.ForeColor     = Theme.TEXT_PRIMARY
        self.tree.Font          = Theme.FONT_BODY
        self.tree.BorderStyle   = getattr(BorderStyle, "None", 0)
        self.tree.ShowLines     = True
        self.tree.ShowPlusMinus = False
        self.tree.ItemHeight    = 26
        self.tree.HideSelection = False
        self.tree.AfterSelect    += self._on_tree_select
        self.tree.AfterExpand    += self._on_tree_expand_collapse
        self.tree.AfterCollapse  += self._on_tree_expand_collapse
        self.tree.DrawMode        = WinForms.TreeViewDrawMode.OwnerDrawText
        self.tree.DrawNode       += self._on_draw_node
        self.tree.MouseDown += self._on_tree_mouse_down

        self.tree_panel.Controls.Add(self.tree)

        # ================================================================
        # PANEL DETALLE - abajo
        # ================================================================
        self.detail_panel = ClashDetailPanel()
        self.detail_panel.Dock = DockStyle.Fill
        self.detail_panel.cmb_status.SelectedIndexChanged += self._on_status_changed_inline
        self.detail_panel.btn_sel1.Click      += self._on_select_obj1
        self.detail_panel.btn_sel2.Click      += self._on_select_obj2
        self.detail_panel.btn_sel_ambos.Click += self._on_select_ambos
        self.detail_panel.btn_box1.Click      += self._on_box_obj1
        self.detail_panel.btn_box2.Click      += self._on_box_obj2
        self.detail_panel.btn_box_ambos.Click += self._on_box_ambos

        # Inyectar callback para "clic en tarjeta de elemento → selección en árbol"
        self.detail_panel.on_element_click = self._select_clashes_by_element_id

        # Conectar botones de estado del panel al handler del form
        for key, btn in self.detail_panel._status_btns.items():
            def _make_handler(k):
                def _handler(s, e):
                    self._on_quick_status(k)
                return _handler
            btn.Click += _make_handler(key)

        # Registrar referencia para habilitar/deshabilitar desde el form
        self._status_quick_btns = self.detail_panel._status_btns

        # ================================================================
        # SPLITCONTAINER — separa árbol (Panel1) y detalle (Panel2)
        # El splitter es arrastrable verticalmente
        # ================================================================
        self.split_main = SplitContainer()
        self.split_main.Dock            = DockStyle.Fill
        self.split_main.Orientation     = Orientation.Horizontal
        self.split_main.SplitterWidth   = 5
        self.split_main.FixedPanel      = FixedPanel.Panel2
        self.split_main.BackColor       = Theme.BORDER
        self.split_main.Panel1.BackColor = Theme.BG_CARD
        self.split_main.Panel2.BackColor = Theme.BG_PANEL

        self.split_main.Panel1.Controls.Add(self.tree_panel)
        self.split_main.Panel2.Controls.Add(self.detail_panel)

        # ════════════════════════════════════════════════════════════════════
        # ENSAMBLADO — orden inverso (Fill va primero en Controls.Add)
        # ════════════════════════════════════════════════════════════════════
        self.Controls.Add(self.split_main)         # Fill
        self.Controls.Add(self.stats_panel)        # Top — visible tras carga
        self.Controls.Add(toolbar)                 # Top — siempre visible

    # ── Font según estado expandido/colapsado ────────────────────────────────
    def _node_font_for(self, node, item):
        """
        Grupos colapsados  → negrita  (indica que hay contenido dentro)
        Grupos expandidos  → normal   (el contenido ya es visible)
        Hojas (no grupos)  → normal
        """
        if item is not None and item.is_group and not node.IsExpanded:
            return Theme.FONT_TITLE   # Bold
        return Theme.FONT_BODY        # Regular

    def _on_tree_expand_collapse(self, sender, e):
        """Actualiza el font del nodo al expandir o colapsar."""
        node = e.Node
        item = self._node_item_map.get(node)
        node.NodeFont = self._node_font_for(node, item)
        self.tree.Invalidate()

    # ── Owner-draw del TreeView — tema claro ────────────────────────────────
    def _on_draw_node(self, sender, e):
        node   = e.Node
        item   = self._node_item_map.get(node)
        bounds = e.Bounds

        # ── Fondo de fila ──
        if node in self._multi_selected_nodes or node.IsSelected:
            bg = Theme.BG_SELECTED
        elif e.State & WinForms.TreeNodeStates.Hot:
            bg = Theme.BG_HOVER
        else:
            bg = Theme.BG_CARD

        e.Graphics.FillRectangle(Drawing.SolidBrush(bg), bounds)

        # Línea separadora inferior (1px gris claro)
        sep_y = bounds.Bottom - 1
        e.Graphics.DrawLine(Drawing.Pen(Theme.BORDER, 1),
                            bounds.X, sep_y, bounds.Right, sep_y)

        x = bounds.X + 4
        y = bounds.Y

        if item is not None:
            # ── Expansor custom para grupos ─────────────────
            if node.Nodes.Count > 0:

                exp_size = 10

                exp_x = x
                exp_y = y + (bounds.Height - exp_size) // 2

                exp_rect = Drawing.Rectangle(
                    exp_x,
                    exp_y,
                    exp_size,
                    exp_size
                )

                e.Graphics.SmoothingMode = D2.SmoothingMode.AntiAlias

                # Fondo
                e.Graphics.FillRectangle(
                    Drawing.SolidBrush(Color.FromArgb(250,250,250)),
                    exp_rect
                )

                # Borde
                e.Graphics.DrawRectangle(
                    Drawing.Pen(Theme.BORDER, 1),
                    exp_rect
                )

                # Línea horizontal
                my = exp_y + exp_size // 2

                e.Graphics.DrawLine(
                    Drawing.Pen(Theme.TEXT_MUTED, 1),
                    exp_x + 2,
                    my,
                    exp_x + exp_size - 2,
                    my
                )

                # Línea vertical si está cerrado
                if not node.IsExpanded:

                    mx = exp_x + exp_size // 2

                    e.Graphics.DrawLine(
                        Drawing.Pen(Theme.TEXT_MUTED, 1),
                        mx,
                        exp_y + 2,
                        mx,
                        exp_y + exp_size - 2
                    )

                x += 16
            
            # ── Punto de color del estado (círculo 9px) ──
            dot_col  = Theme.status_dot(item.status)
            dot_x    = x
            dot_y    = y + (bounds.Height - 9) // 2
            dot_rect = Drawing.Rectangle(dot_x, dot_y, 9, 9)
            e.Graphics.SmoothingMode = D2.SmoothingMode.AntiAlias
            e.Graphics.FillEllipse(Drawing.SolidBrush(dot_col), dot_rect)
            x += 16

            # ── Nombre del clash ──
            name_part = item.name
            txt_col   = Theme.TEXT_PRIMARY
            name_font = self._node_font_for(node, item)
            e.Graphics.DrawString(
                name_part, name_font,
                Drawing.SolidBrush(txt_col),
                float(x), float(y + (bounds.Height - 14) // 2)
            )

            # ── Badge de estado redondeado (tarjeta pastel) ──
            status_lbl = Theme.status_label(item.status)
            badge_fg   = Theme.status_color(item.status)
            badge_bg   = Theme.status_bg(item.status)

            badge_font  = Theme.FONT_BADGE
            badge_tw    = 65   # ancho fijo de la tarjeta badge
            badge_th    = 16   # altura un poco mayor
            # Badge posicionado con más espacio: 72px antes del margen derecho
            badge_rx    = int(bounds.Right) - badge_tw - 40
            badge_ry    = y + (bounds.Height - badge_th) // 2

            # Fondo redondeado del badge
            brad = 5
            bp   = D2.GraphicsPath()
            bp.AddArc(badge_rx,                     badge_ry,                     brad*2, brad*2, 180, 90)
            bp.AddArc(badge_rx + badge_tw - brad*2, badge_ry,                     brad*2, brad*2, 270, 90)
            bp.AddArc(badge_rx + badge_tw - brad*2, badge_ry + badge_th - brad*2, brad*2, brad*2,   0, 90)
            bp.AddArc(badge_rx,                     badge_ry + badge_th - brad*2, brad*2, brad*2,  90, 90)
            bp.CloseFigure()
            e.Graphics.SmoothingMode = D2.SmoothingMode.AntiAlias
            e.Graphics.FillPath(Drawing.SolidBrush(badge_bg), bp)
            # Borde suave del badge
            pen_badge = Drawing.Pen(Color.FromArgb(60, badge_fg.R, badge_fg.G, badge_fg.B), 0.8)
            e.Graphics.DrawPath(pen_badge, bp)
            pen_badge.Dispose()
            bp.Dispose()

            # Texto centrado en el badge
            sf_badge = Drawing.StringFormat()
            sf_badge.Alignment     = Drawing.StringAlignment.Center
            sf_badge.LineAlignment = Drawing.StringAlignment.Center
            badge_rect = Drawing.RectangleF(float(badge_rx), float(badge_ry), float(badge_tw), float(badge_th))
            e.Graphics.DrawString(status_lbl, badge_font, Drawing.SolidBrush(badge_fg), badge_rect, sf_badge)

            # ── Distancia alineada a la derecha ──
            if not item.is_group and item.distance:
                try:
                    dist_txt = u"{:.3f}m".format(float(item.distance))
                except Exception:
                    dist_txt = item.distance
                sf_right = Drawing.StringFormat()
                sf_right.Alignment = Drawing.StringAlignment.Far
                dist_rect = Drawing.RectangleF(
                    bounds.X+25, float(y + (bounds.Height - 14) // 2),
                    bounds.Width +25, 14
                )
                e.Graphics.DrawString(dist_txt, Theme.FONT_SMALL,
                                      Drawing.SolidBrush(Theme.TEXT_MUTED),
                                      dist_rect, sf_right)
        else:
            # Nodo raíz (ClashTest header) — fondo azul muy pastel y claro
            card_bg  = Color.FromArgb(220, 235, 250)  # azul aún más claro pastel
            card_fg  = Color.FromArgb( 30,  90, 160)  # azul medio — legible sin ser oscuro
            sep_col  = Color.FromArgb(180, 210, 245)  # borde inferior suave

            # Fondo pastel extendido hasta el borde derecho del TreeView
            full_rect = Drawing.Rectangle(0, bounds.Y, self.tree.ClientSize.Width, bounds.Height)
            e.Graphics.FillRectangle(Drawing.SolidBrush(card_bg), full_rect)

            # Borde inferior suave (sin barra izquierda oscura)
            e.Graphics.DrawLine(Drawing.Pen(sep_col, 1),
                                0, bounds.Bottom - 1,
                                self.tree.ClientSize.Width, bounds.Bottom - 1)

            # ── Expansor +/- dibujado manualmente ──
            exp_size = 12
            exp_x    = x + 2
            exp_y    = y + (bounds.Height - exp_size) // 2
            exp_rect = Drawing.Rectangle(exp_x, exp_y, exp_size, exp_size)
            # Caja del expansor
            e.Graphics.SmoothingMode = D2.SmoothingMode.AntiAlias
            e.Graphics.FillRectangle(Drawing.SolidBrush(Color.FromArgb(255,255,255)), exp_rect)
            e.Graphics.DrawRectangle(Drawing.Pen(card_fg, 1), exp_rect)
            # Línea horizontal (siempre)
            mx = exp_x + 2; my = exp_y + exp_size // 2
            e.Graphics.DrawLine(Drawing.Pen(card_fg, 1), mx, my, exp_x + exp_size - 2, my)
            # Línea vertical solo si está colapsado (=no expandido)
            if not node.IsExpanded:
                vx = exp_x + exp_size // 2; vy = exp_y + 2
                e.Graphics.DrawLine(Drawing.Pen(card_fg, 1), vx, vy, vx, exp_y + exp_size - 2)

            # Texto desplazado a la derecha del expansor
            e.Graphics.DrawString(
                node.Text, Theme.FONT_TITLE,
                Drawing.SolidBrush(card_fg),
                float(x + exp_size + 8), float(y + (bounds.Height - 14) // 2)
            )

    def _on_tree_mouse_down(self, sender, e):

        node = self.tree.GetNodeAt(e.X, e.Y)

        if node is None:
            return

        item = self._node_item_map.get(node)

        # ── Nodo raíz (ClashTest): siempre expande/colapsa con un clic ──
        if item is None:
            if node.IsExpanded:
                node.Collapse()
            else:
                node.Expand()
            return

        # ── Nodo de grupo: expande/colapsa con un clic en cualquier zona ──
        if item.is_group:
            if node.IsExpanded:
                node.Collapse()
            else:
                node.Expand()
            # También selecciona para mostrar detalle
            self._multi_selected_nodes.clear()
            self._multi_selected_nodes.add(node)
            self._last_clicked_node = node
            self.tree.SelectedNode = node
            self.tree.Invalidate()
            return

        # ── Nodo hoja: gestionar multi-selección ──────────────────────────
        ctrl_down  = int(WinForms.Control.ModifierKeys & WinForms.Keys.Control)  != 0
        shift_down = int(WinForms.Control.ModifierKeys & WinForms.Keys.Shift)    != 0

        if ctrl_down:
            # Toggle: si ya está en la selección lo quita; si no lo añade
            if node in self._multi_selected_nodes:
                self._multi_selected_nodes.discard(node)
            else:
                self._multi_selected_nodes.add(node)
            self._last_clicked_node = node
            self.tree.SelectedNode  = node   # mueve el foco visual
            self.tree.Invalidate()
            # Mostrar detalle del nodo en foco (el último clickeado)
            self._show_multi_or_single_detail()

        elif shift_down and self._last_clicked_node is not None:
            # Rango: seleccionar todos los nodos hoja entre anchor y actual
            all_leaves = self._get_all_leaf_nodes_in_order()
            try:
                i1 = all_leaves.index(self._last_clicked_node)
                i2 = all_leaves.index(node)
            except ValueError:
                # Si no están en la lista (nodos de grupo etc.) → selección simple
                self._multi_selected_nodes = set([node])
                self._last_clicked_node = node
                self.tree.SelectedNode = node
                self.tree.Invalidate()
                self._show_multi_or_single_detail()
                return

            start, end = min(i1, i2), max(i1, i2)
            self._multi_selected_nodes = set(all_leaves[start:end + 1])
            self.tree.SelectedNode = node
            self.tree.Invalidate()
            self._show_multi_or_single_detail()

        else:
            # Clic normal: selección única
            self._multi_selected_nodes = set([node])
            self._last_clicked_node = node
            self.tree.SelectedNode  = node
            self.tree.Invalidate()
            # _on_tree_select se encarga del detalle

    def _get_all_leaf_nodes_in_order(self):
        """Retorna lista ordenada de nodos hoja (no grupos, no raíces) tal como
        aparecen en el árbol de arriba a abajo."""
        result = []

        def _walk(nodes):
            for node in nodes:
                item = self._node_item_map.get(node)
                if item is None:
                    # nodo raíz — sólo sus hijos
                    _walk(node.Nodes)
                elif item.is_group:
                    _walk(node.Nodes)
                else:
                    result.append(node)
                    _walk(node.Nodes)   # por si hay hojas anidadas

        _walk(self.tree.Nodes)
        return result

    def _show_multi_or_single_detail(self):
        """Muestra el detalle del clash en foco (SelectedNode).
        Si hay varios seleccionados también habilita los botones de estado."""
        node = self.tree.SelectedNode
        item = self._node_item_map.get(node) if node else None
        self.detail_panel.show_item(item)
        multi_count = len(self._multi_selected_nodes)
        enabled = item is not None or multi_count > 1
        self._set_quick_btns_enabled(enabled)
        if multi_count > 1:
            self._update_status_bar(
                u"ⓘ  {} elementos seleccionados — usa los botones de estado para cambio múltiple.".format(multi_count)
            )

    def _enable_double_buffer(self, control):

        try:
            import System

            prop = control.GetType().GetProperty(
                "DoubleBuffered",
                System.Reflection.BindingFlags.Instance |
                System.Reflection.BindingFlags.NonPublic
            )

            if prop:
                prop.SetValue(control, True, None)

        except:
            pass

    # ── Carga de XML ──────────────────────────────────────────────────────────
    def _on_load_xml(self, sender, e):
        dlg = OpenFileDialog()
        dlg.Title  = "Seleccionar XML de Navisworks"
        dlg.Filter = "Navisworks XML (*.xml)|*.xml|Todos los archivos|*.*"
        if dlg.ShowDialog() != WinForms.DialogResult.OK:
            return

        self.xml_path = dlg.FileName
        self._pending_changes = {}

        try:
            self.clash_tests = NavisworksXMLParser.parse(self.xml_path)
        except Exception as ex:
            MessageBox.Show(
                "Error al parsear el XML:\n{}".format(str(ex)),
                "Error", MessageBoxButtons.OK, MessageBoxIcon.Error
            )
            return

        self._populate_tree(self.clash_tests)
        self._show_stats(self.clash_tests)

        total = sum(len(ct.items) for ct in self.clash_tests)
        self._update_status_bar(
            u"Cargado: {}  |  {} prueba(s)  |  {} clash(es) en raíz".format(
                os.path.basename(self.xml_path),
                len(self.clash_tests), total
            )
        )
        self.btn_save.Enabled     = True
        self.btn_expand.Enabled   = True
        self.btn_collapse.Enabled = True

    # ══════════════════════════════════════════════════════════════════════════
    # ARQUITECTURA QUIRÚRGICA DATOS ↔ VISTA
    # ══════════════════════════════════════════════════════════════════════════
    # _node_item_map  : {TreeNode  → ClashItem}  — solo nodos VISIBLES en el árbol
    # _item_node_map  : {id(item)  → TreeNode}   — TODOS los nodos, estén o no en árbol
    # _item_in_tree   : set de id(ClashItem) que están físicamente en el árbol
    # _ct_node_map    : {id(ClashTest) → TreeNode header}
    #
    # Al filtrar  → _apply_filter_to_tree()  solo hace node.Remove() / Nodes.Insert()
    #              sobre los nodos que CAMBIAN de visibilidad. Sin Nodes.Clear().
    # Al cambiar estado → _refresh_node_in_place()  solo retoca texto + Invalidate()
    # ══════════════════════════════════════════════════════════════════════════

    def _populate_tree(self, tests, filter_status=None):
        """Construye el árbol completo. Se llama UNA SOLA VEZ al cargar el XML.
        Crea todos los nodos y los registra; los filtros posteriores usan
        cirugía quirúrgica (add/remove individual) sin reconstruir nada."""

        self._multi_selected_nodes.clear()
        self._item_node_map = {}    # id(ClashItem) → TreeNode  (TODOS, siempre)
        self._item_in_tree  = set() # id(ClashItem) que están físicamente en el árbol
        self._ct_node_map   = {}    # id(ClashTest) → header TreeNode

        self.tree.BeginUpdate()
        self.tree.Nodes.Clear()
        self._node_item_map.clear()

        for ct in tests:
            ct_node = TreeNode(
                u"{}  [{} total]".format(
                    ct.name,
                    ct.summary.get("total", "?")
                )
            )
            ct_node.ForeColor = Theme.TEXT_PRIMARY
            ct_node.BackColor = Theme.BG_PANEL
            ct_node.NodeFont  = Theme.FONT_TITLE

            self._ct_node_map[id(ct)] = ct_node

            for item in ct.items:
                self._add_item_node(ct_node, item)

            self.tree.Nodes.Add(ct_node)
            ct_node.Expand()

        self.tree.EndUpdate()

        # Aplicar filtro inicial si hay uno activo
        if filter_status:
            self._apply_filter_to_tree(filter_status)

    def _add_item_node(self, parent_node, item):
        """Crea el TreeNode y lo agrega. Registra en todos los maps.
        Siempre crea (sin filtro); el filtro actúa quirúrgicamente después."""
        label = self._build_node_label(item)
        node  = TreeNode(label)

        self._node_item_map[node]     = item
        self._item_node_map[id(item)] = node
        self._item_in_tree.add(id(item))

        for child in item.children:
            self._add_item_node(node, child)

        parent_node.Nodes.Add(node)

        if item.is_group:
            node.Collapse()

        node.NodeFont = self._node_font_for(node, item)

    # ──────────────────────────────────────────────────────────────────────────
    # FILTRO QUIRÚRGICO — solo add/remove sobre nodos que cambian visibilidad
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_filter_to_tree(self, filter_status):
        """Aplica el filtro quirúrgicamente: solo toca los nodos que cambian
        de estado visible↔oculto. No llama a Nodes.Clear() nunca."""

        # Guardar estado expandido de grupos (se preserva durante cirugía)
        expanded_state = {}
        for node, item in list(self._node_item_map.items()):
            if item is not None and item.is_group:
                expanded_state[id(item)] = node.IsExpanded

        # Guardar selección actual
        selected_item = self._node_item_map.get(self.tree.SelectedNode)

        self.tree.BeginUpdate()

        for ct in self.clash_tests:
            ct_node = self._ct_node_map.get(id(ct))
            if ct_node is None:
                continue
            self._sync_items(ct_node, ct.items, filter_status, expanded_state)

        self.tree.EndUpdate()

        # Restaurar selección si el nodo sigue visible
        try:
            if selected_item is not None:
                if id(selected_item) in self._item_in_tree:
                    node = self._item_node_map.get(id(selected_item))
                    if node:
                        self.tree.SelectedNode = node
                else:
                    # El item seleccionado ya no está en el árbol
                    self.tree.SelectedNode = None
                    self.detail_panel.show_item(None)
                    self._set_quick_btns_enabled(False)
        except:
            pass

        # Sincronizar multi-selección
        self._multi_selected_nodes = {
            n for n in self._multi_selected_nodes
            if self._node_item_map.get(n) is not None
               and id(self._node_item_map[n]) in self._item_in_tree
        }
        
    def _clear_nodes_recursive(self, node):
        """Desacopla TODOS los descendientes de 'node', en cualquier
        profundidad, para que cada TreeNode quede libre y pueda
        reinsertarse de forma independiente más adelante."""
        for child_node in list(node.Nodes):
            self._clear_nodes_recursive(child_node)
        if node.Nodes.Count > 0:
            node.Nodes.Clear()

    def _sync_items(self, parent_node, items, filter_status, expanded_state):
        """Recorre 'items' en orden y hace add/remove quirúrgico en parent_node.
        'insert_index' rastrea en qué posición insertar el próximo nodo visible."""
        insert_index = 0

        for item in items:
            node = self._item_node_map.get(id(item))
            if node is None:
                continue

            should_show = (not filter_status) or self._item_matches_filter(item, filter_status)
            in_tree     = id(item) in self._item_in_tree

            if should_show and not in_tree:
                # ── Aparecer: insertar en la posición correcta ────────────────
                parent_node.Nodes.Insert(insert_index, node)
                self._node_item_map[node] = item
                self._item_in_tree.add(id(item))

                # Para grupos: sincronizar sus hijos recursivamente.
                # Sus hijos fueron desacoplados (node.Nodes.Clear) al removerse,
                # así que _sync_items los reinsertará limpiamente.
                if item.is_group:
                    self._sync_items(node, item.children, filter_status, expanded_state)
                    was_expanded = expanded_state.get(id(item), False)
                    if was_expanded:
                        node.Expand()
                    else:
                        node.Collapse()

                insert_index += 1

            elif should_show and in_tree:
                # ── Ya visible: actualizar texto y sincronizar hijos ──────────
                node.Text     = self._build_node_label(item)
                node.NodeFont = self._node_font_for(node, item)
                if item.is_group:
                    self._sync_items(node, item.children, filter_status, expanded_state)
                insert_index += 1

            elif not should_show and in_tree:
                # ── Desaparecer: quitar nodo físicamente ──────────────────────
                # IMPORTANTE: para grupos, vaciar sus hijos ANTES de remover el nodo.
                # Si no, los hijos quedan físicamente en node.Nodes y cuando el grupo
                # vuelva _sync_items intentará insertarlos de nuevo → error WinForms.
                if item.is_group:
                    self._clear_nodes_recursive(node)   # ← todos los niles
                node.Remove()
                self._node_item_map.pop(node, None)
                self._item_in_tree.discard(id(item))
                self._mark_subtree_removed(item)

            # else: no visible y no estaba → nada que hacer

    def _mark_subtree_removed(self, item):
        """Marca item y todos sus descendientes como fuera del árbol."""
        # El item principal ya fue marcado por el caller; procesamos hijos
        for child in item.children:
            self._item_in_tree.discard(id(child))
            child_node = self._item_node_map.get(id(child))
            if child_node is not None:
                self._node_item_map.pop(child_node, None)
            self._mark_subtree_removed(child)

    # ──────────────────────────────────────────────────────────────────────────
    # REFRESCO IN-PLACE DE UN NODO (sin tocar el árbol)
    # ──────────────────────────────────────────────────────────────────────────

    def _refresh_node_in_place(self, item):
        """Actualiza texto y font del nodo en O(1) via lookup inverso.
        Solo actúa si el nodo está actualmente en el árbol."""
        node = self._item_node_map.get(id(item))
        if node is not None and id(item) in self._item_in_tree:
            node.Text     = self._build_node_label(item)
            node.NodeFont = self._node_font_for(node, item)
            self.tree.Invalidate()

    def _build_node_label(self, item):
        status_lbl = Theme.status_label(item.status)
        if item.is_group:
            n_children = self._count_leaves(item)
            return u"{}  ({} incidencias)  [{}]".format(
                item.name, n_children, status_lbl
            )
        else:
            dist = " | {:.3f}m".format(float(item.distance)) if item.distance else ""
            return u"{}  [{}]{}".format(item.name, status_lbl, dist)

    def _count_leaves(self, item):
        if not item.is_group:
            return 1
        return sum(self._count_leaves(c) for c in item.children)

    def _item_matches_filter(self, item, filter_status):
        label = Theme.status_label(item.status)
        if isinstance(filter_status, set):
            matched = label in filter_status
        else:
            matched = label == filter_status
        if matched:
            return True
        for child in item.children:
            if self._item_matches_filter(child, filter_status):
                return True
        return False

    # ── Stats panel — tarjetas redondeadas blancas ────────────────────────────
    def _show_stats(self, tests):
        self.stats_panel.Height  = 90
        self.stats_panel.Visible = True
        if not tests:
            return
        # Usar conteo real en memoria (no el summary del XML que puede estar desactualizado)
        live_summ = self._compute_live_summary()
        self._show_stats_from_summary(live_summ)

    # ── Selección en árbol ────────────────────────────────────────────────────
    def _on_tree_select(self, sender, e):
        node = e.Node
        item = self._node_item_map.get(node)
        self.detail_panel.show_item(item)
        # Habilitar botones de estado rápido solo si hay un clash seleccionado
        self._set_quick_btns_enabled(item is not None)

    # ── Seleccionar Elemento 1 ────────────────────────────────────────────────
    def _on_select_obj1(self, sender, e):
        co = self.detail_panel.get_direct_object(0)
        if co is None:
            self._update_status_bar(u"Elemento 1 no disponible.")
            return
        ok, msg = self.selector.select_elements([co])
        self._update_status_bar((u"✓ " if ok else u"⚠ ") + msg)
        if not ok:
            MessageBox.Show(msg, u"Información", MessageBoxButtons.OK, MessageBoxIcon.Information)

    # ── Seleccionar Elemento 2 ────────────────────────────────────────────────
    def _on_select_obj2(self, sender, e):
        co = self.detail_panel.get_direct_object(1)
        if co is None:
            self._update_status_bar(u"Elemento 2 no disponible.")
            return
        ok, msg = self.selector.select_elements([co])
        self._update_status_bar((u"✓ " if ok else u"⚠ ") + msg)
        if not ok:
            MessageBox.Show(msg, u"Información", MessageBoxButtons.OK, MessageBoxIcon.Information)

    # ── Seleccionar Ambos ────────────────────────────────────────────────────
    def _on_select_ambos(self, sender, e):
        objs = self.detail_panel.get_all_direct_objects()
        if not objs:
            self._update_status_bar(u"Sin elementos directos para seleccionar.")
            return
        ok, msg = self.selector.select_elements(objs)
        self._update_status_bar((u"✓ " if ok else u"⚠ ") + msg)
        if not ok:
            MessageBox.Show(msg, u"Información", MessageBoxButtons.OK, MessageBoxIcon.Information)
    
    # ─────────────────────────────────────────────
    # SECTIONBOX OBJETO 1
    # ─────────────────────────────────────────────

    def _on_box_obj1(self, sender, e):
        co = self.detail_panel.get_direct_object(0)
        if co is None:
            self._update_status_bar(u"Elemento 1 no disponible en este clash.")
            return
        self.sectionbox_handler.result        = None
        self.sectionbox_handler.uidoc         = self.uidoc
        self.sectionbox_handler.doc           = self.doc
        self.sectionbox_handler.clash_objects = [co]
        self.sectionbox_event.Raise()
        self._result_timer.Start()
        self._update_status_bar(u"⏳ Aplicando SectionBox — Elemento 1...")

    # ─────────────────────────────────────────────
    # SECTIONBOX OBJETO 2
    # ─────────────────────────────────────────────

    def _on_box_obj2(self, sender, e):
        co = self.detail_panel.get_direct_object(1)
        if co is None:
            self._update_status_bar(u"Elemento 2 no disponible en este clash.")
            return
        self.sectionbox_handler.result        = None
        self.sectionbox_handler.uidoc         = self.uidoc
        self.sectionbox_handler.doc           = self.doc
        self.sectionbox_handler.clash_objects = [co]
        self.sectionbox_event.Raise()
        self._result_timer.Start()
        self._update_status_bar(u"⏳ Aplicando SectionBox — Elemento 2...")

    # ─────────────────────────────────────────────
    # SECTIONBOX AMBOS
    # ─────────────────────────────────────────────

    def _on_box_ambos(self, sender, e):
        objs = self.detail_panel.get_all_direct_objects()
        if not objs:
            self._update_status_bar(u"Sin elementos directos para SectionBox.")
            return
        self.sectionbox_handler.result        = None
        self.sectionbox_handler.uidoc         = self.uidoc
        self.sectionbox_handler.doc           = self.doc
        self.sectionbox_handler.clash_objects = objs
        self.sectionbox_event.Raise()
        self._result_timer.Start()
        self._update_status_bar(u"⏳ Aplicando SectionBox — Ambos elementos...")
            
    # ── Recuento de estados en memoria (para actualizar cards) ───────────────
    def _compute_live_summary(self):
        """Recorre todos los ClashItems en memoria y retorna dict de conteos."""
        counts = {"new": 0, "active": 0, "approved": 0, "resolved": 0, "total": 0}

        def _count_item(it):
            key = (it.status or "").lower().strip()
            if key in counts:
                counts[key] += 1
            counts["total"] += 1
            for child in it.children:
                _count_item(child)

        for ct in self.clash_tests:
            for it in ct.items:
                _count_item(it)

        return {k: str(v) for k, v in counts.items()}

    def _show_stats_from_summary(self, summ):
        """Reconstruye las tarjetas de estadísticas con un summary dado."""
        self.stats_panel.Controls.Clear()
        sep_stats = Panel()
        sep_stats.BackColor = Theme.BORDER
        sep_stats.Height    = 1
        sep_stats.Dock      = DockStyle.Bottom
        self.stats_panel.Controls.Add(sep_stats)

        BADGES = [
            ("new",      u"Nuevo",    Theme.CARD_NEW_BG,      Theme.CARD_NEW_FG,      u"\U0001f4c4"),
            ("active",   u"Activo",   Theme.CARD_ACTIVE_BG,   Theme.CARD_ACTIVE_FG,   u"\U0001f4da"),
            ("approved", u"Aprobado", Theme.CARD_APPROVED_BG, Theme.CARD_APPROVED_FG, u"\u2705"),
            ("resolved", u"Resuelto", Theme.CARD_RESOLVED_BG, Theme.CARD_RESOLVED_FG, u"\U0001f6a9"),
            ("total",    u"Total",    Theme.CARD_TOTAL_BG,    Theme.CARD_TOTAL_FG,    u"\U0001f4ca"),
        ]
        x      = 6
        card_w = 100
        card_h = 72
        y_off  = 8
        RADIUS = 8

        self._stat_cards = {}   # label_es → _RoundedCard

        for key, label, bg, fg, icon in BADGES:
            val  = str(summ.get(key, "0"))
            card = _RoundedCard(
                val=val, label=label, bg=bg, fg=fg,
                radius=RADIUS, w=card_w, h=card_h, icon=icon
            )
            card.Location = Drawing.Point(x, y_off)

            # Tarjeta Total limpia filtros; el resto filtra
            if key == "total":
                def _clear_handler(s, e):
                    self._on_card_filter_click(None)
                card.Click += _clear_handler
            else:
                card.set_active(label in self._filter_active)
                def _make_card_handler(lbl):
                    def _handler(s, e):
                        self._on_card_filter_click(lbl)
                    return _handler
                card.Click += _make_card_handler(label)

            self._stat_cards[label] = card
            self.stats_panel.Controls.Add(card)
            x += card_w + 5

        self.stats_panel.Refresh()

    def _update_stats_in_place(self, summ):
        """
        Actualiza los valores numéricos de las tarjetas de estadísticas
        sin destruirlas ni recrearlas. Elimina el parpadeo al cambiar estados.
        Si las tarjetas aún no existen, las crea normalmente.
        """
        KEY_MAP = {
            u"Nuevo":    "new",
            u"Activo":   "active",
            u"Aprobado": "approved",
            u"Resuelto": "resolved",
            u"Total":    "total",
        }
        if not self._stat_cards:
            # Primera vez o tras un Clear: crear normalmente
            self._show_stats_from_summary(summ)
            return

        self.stats_panel.SuspendLayout()
        for label, card in self._stat_cards.items():
            key = KEY_MAP.get(label, label.lower())
            card.set_value(summ.get(key, "0"))
        self.stats_panel.ResumeLayout(False)

    # ── Cambio de estado inline ───────────────────────────────────────────────
    def _on_status_changed_inline(self, sender, e):
        # Ignorar si el cambio viene de show_item cargando un clash
        if self.detail_panel._loading:
            return
        item = self.detail_panel.current_item
        if item is None:
            return
        selected_label = str(self.detail_panel.cmb_status.SelectedItem or "Activo")
        attr = XMLStatusUpdater.STATUS_MAP.get(selected_label, "active")
        rs   = selected_label

        # Registrar cambio pendiente
        self._pending_changes[item.guid] = (attr, rs)

        # Actualizar item en memoria
        item.status        = attr
        item.result_status = rs

        # ── Si hay filtro activo: re-aplicarlo para que el nodo entre/salga ──
        # El nodo puede ya no cumplir el filtro → debe desaparecer de la vista.
        if self._filter_active:
            self._apply_filter_to_tree(self._filter_active)
            # Si el item ya no aparece en el árbol filtrado, limpiar el detalle
            item_node = self._item_node_map.get(id(item))
            if item_node not in self._node_item_map:
                self.detail_panel.show_item(None)
                self._set_quick_btns_enabled(False)
        else:
            # Sin filtro: solo retoca texto + font del nodo y redibuja
            self._refresh_node_in_place(item)

        # ── Auto-actualizar grupo padre si corresponde ───────────────────────
        self._auto_update_parent_group(item)

        # ── Actualizar tarjetas de estadísticas en tiempo real SIN recrearlas ─
        live_summ = self._compute_live_summary()
        self._update_stats_in_place(live_summ)

        self._update_status_bar(
            u"ⓘ  Cambio pendiente: {} → {}  (no guardado)".format(item.name, selected_label)
        )

    def _find_parent_group(self, target_item):
        """Busca el ClashItem grupo que contiene directamente a target_item."""
        for ct in self.clash_tests:
            result = self._search_parent_in(ct.items, target_item)
            if result is not None:
                return result
        return None

    def _search_parent_in(self, items, target_item):
        """Recorre recursivamente buscando el padre directo de target_item."""
        for it in items:
            if it.is_group:
                for child in it.children:
                    if child is target_item:
                        return it
                result = self._search_parent_in(it.children, target_item)
                if result is not None:
                    return result
        return None

    def _auto_update_parent_group(self, changed_item):
        """
        Recalcula el estado del grupo padre según esta prioridad:

        PRIORIDAD 1 — Si hay al menos 1 Nuevo o Activo:
            → Mayoría entre Nuevo y Activo. Empate → Activo.
               Si no hay ninguno de los dos pero sí Revisado → Revisado.

        PRIORIDAD 2 — Si el 100% son Aprobado o Resuelto:
            → Mayoría entre los dos. Empate → Resuelto.

        Sube recursivamente hasta la raíz.
        """
        _NORMALIZE = {
            "new":      "new",      "nuevo":    "new",
            "active":   "active",   "activo":   "active",
            "reviewed": "reviewed", "revisado": "reviewed",
            "approved": "approved", "aprobado": "approved",
            "resolved": "resolved", "resuelto": "resolved",
        }

        parent = self._find_parent_group(changed_item)
        if parent is None:
            return

        # Recopilar estados de todas las hojas normalizados
        def _collect_leaf_statuses(group):
            statuses = []
            for child in group.children:
                if child.is_group:
                    statuses.extend(_collect_leaf_statuses(child))
                else:
                    raw = (child.status or "").lower().strip()
                    statuses.append(_NORMALIZE.get(raw, raw))
            return statuses

        leaf_statuses = _collect_leaf_statuses(parent)
        if not leaf_statuses:
            return

        count_new      = leaf_statuses.count("new")
        count_active   = leaf_statuses.count("active")
        count_reviewed = leaf_statuses.count("reviewed")
        count_approved = leaf_statuses.count("approved")
        count_resolved = leaf_statuses.count("resolved")

        # ── PRIORIDAD 1: hay Nuevo o Activo ──────────────────────────────────
        if count_new > 0 or count_active > 0:
            if count_new > count_active:
                new_attr = "new"
            elif count_active > count_new:
                new_attr = "active"
            else:
                new_attr = "active"   # empate → Activo (más urgente)

        # ── hay Revisado pero ningún Nuevo ni Activo ──────────────────────────
        elif count_reviewed > 0:
            new_attr = "reviewed"

        # ── PRIORIDAD 2: 100% Aprobado o Resuelto ────────────────────────────
        elif count_approved + count_resolved == len(leaf_statuses):
            new_attr = "resolved" if count_resolved >= count_approved else "approved"

        else:
            return  # estado desconocido, no tocar

        new_label = XMLStatusUpdater.STATUS_RESULT_MAP.get(new_attr, new_attr)

        # Aplicar y refrescar
        parent.status        = new_attr
        parent.result_status = new_label
        self._pending_changes[parent.guid] = (new_attr, new_label)

        for node, it in self._node_item_map.items():
            if it is parent:
                self._refresh_node_in_place(parent)
                break

        # Subir al abuelo recursivamente
        self._auto_update_parent_group(parent)

    # ── Filtro ────────────────────────────────────────────────────────────────
    def _on_card_filter_click(self, label):
        """Toggle de filtro al hacer clic en una tarjeta. None = limpiar todo."""
        if label is None:
            self._filter_active.clear()
        elif label in self._filter_active:
            self._filter_active.discard(label)
        else:
            self._filter_active.add(label)

        # Actualizar borde activo en todas las tarjetas
        for lbl, card in self._stat_cards.items():
            card.set_active(lbl in self._filter_active)

        # Aplicar filtro SIN reconstruir el mapa de datos
        active = self._filter_active if self._filter_active else None
        self._apply_filter_to_tree(active)

    def _on_filter_btn_click(self, sender, e):
        label, bg_on, fg_on = sender.Tag

        if label == u"Todos":
            # Todos limpia cualquier selección individual
            self._filter_active.clear()
        else:
            # Desactivar "Todos" visualmente
            btn_todos = self._filter_btns[u"Todos"]
            btn_todos.BackColor = Theme.BG_CARD
            btn_todos.ForeColor = Theme.TEXT_MUTED
            btn_todos.FlatAppearance.BorderColor = Theme.BORDER

            # Toggle del estado clickeado
            if label in self._filter_active:
                self._filter_active.discard(label)
            else:
                self._filter_active.add(label)

            # Si queda vacío volvemos a "Todos"
            if not self._filter_active:
                label = u"Todos"

        # Actualizar apariencia de todos los botones
        for lbl, btn in self._filter_btns.items():
            _, bg, fg = btn.Tag
            if lbl == u"Todos":
                active = not self._filter_active
            else:
                active = lbl in self._filter_active

            if active:
                btn.BackColor = bg if bg else Color.FromArgb(204, 229, 255)
                btn.ForeColor = fg if fg else Color.FromArgb(  4,  53, 114)
                btn.FlatAppearance.BorderColor = Color.FromArgb( 23, 105, 209)
            else:
                btn.BackColor = Theme.BG_CARD
                btn.ForeColor = Theme.TEXT_MUTED
                btn.FlatAppearance.BorderColor = Theme.BORDER

        active = self._filter_active if self._filter_active else None
        self._apply_filter_to_tree(active)
    # ── Expandir / Colapsar ───────────────────────────────────────────────────
    def _on_expand_all(self, sender, e):
        self.tree.BeginUpdate()
        self.tree.ExpandAll()
        self.tree.EndUpdate()

    def _on_collapse_all(self, sender, e):
        self.tree.BeginUpdate()
        for node in self.tree.Nodes:
            node.Collapse(False)  # colapsa hijos también
        self.tree.EndUpdate()

    # ── Guardar XML ───────────────────────────────────────────────────────────
    def _on_save_xml(self, sender, e):
        if not self.xml_path:
            self._update_status_bar("⚠ No hay archivo XML cargado.")
            return

        if not self._pending_changes:
            MessageBox.Show(
                "No hay cambios de estado pendientes por guardar.",
                "Sin cambios", MessageBoxButtons.OK, MessageBoxIcon.Information
            )
            return

        res = MessageBox.Show(
            u"Se guardarán {} cambio(s) en:\n{}\n\n¿Continuar?".format(
                len(self._pending_changes), self.xml_path
            ),
            "Confirmar guardado",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Question
        )
        if res != WinForms.DialogResult.Yes:
            return

        ok, msg = XMLStatusUpdater.update_and_save(self.xml_path, self._pending_changes)
        if ok:
            self._pending_changes.clear()
            self._update_status_bar("OK: " + msg.replace("\n", " | "))
            MessageBox.Show(msg, "Guardado exitoso", MessageBoxButtons.OK, MessageBoxIcon.Information)
        else:
            self._update_status_bar(u"✗ Error al guardar.")
            MessageBox.Show(msg, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error)

    # ── Botones de estado rápido (barra inferior) ─────────────────────────────
    def _on_quick_status(self, key):
        """Aplica el estado 'key' (Nuevo/Activo/Aprobado/Resuelto) al clash actual.
        Si hay múltiples nodos seleccionados, aplica a todos ellos en un solo batch."""
        # ── Cambio múltiple ────────────────────────────────────────────────────
        if len(self._multi_selected_nodes) > 1:
            attr = XMLStatusUpdater.STATUS_MAP.get(key, "active")
            rs   = key
            changed = 0

            # Paso 1: actualizar datos y texto de nodos en batch (sin Invalidate aún)
            self.tree.BeginUpdate()
            items_changed = []
            for node in list(self._multi_selected_nodes):
                item = self._node_item_map.get(node)
                if item is None:
                    continue
                item.status        = attr
                item.result_status = rs
                self._pending_changes[item.guid] = (attr, rs)
                node.Text     = self._build_node_label(item)
                node.NodeFont = self._node_font_for(node, item)
                items_changed.append(item)
                changed += 1

            # Paso 2: actualizar grupos padre (una sola pasada, sin duplicados)
            parents_done = set()
            for item in items_changed:
                parent = self._find_parent_group(item)
                if parent is not None and id(parent) not in parents_done:
                    self._auto_update_parent_group(item)
                    parents_done.add(id(parent))

            self.tree.EndUpdate()

            # Paso 3: si hay filtro activo re-aplicarlo (mantiene consistencia)
            # _apply_filter_to_tree preserva el estado expandido
            if self._filter_active:
                self._apply_filter_to_tree(self._filter_active)
            else:
                self.tree.Invalidate()   # un solo redibujado al final

            # Paso 4: actualizar tarjetas de estadísticas
            live_summ = self._compute_live_summary()
            self._update_stats_in_place(live_summ)
            self._update_status_bar(
                u"ⓘ  {} clash(es) → {}  (no guardado)".format(changed, key)
            )
            return

        # ── Cambio individual (comportamiento original) ────────────────────────
        item = self.detail_panel.current_item
        if item is None:
            return
        # Sincronizar el ComboBox del panel detalle — dispara _on_status_changed_inline
        cmb = self.detail_panel.cmb_status
        if str(cmb.SelectedItem or "") != key:
            cmb.SelectedItem = key
        else:
            # Ya estaba seleccionado → forzar actualización manual
            self._on_status_changed_inline(None, None)


    def _select_clashes_by_element_id(self, element_id):
        """Selecciona en el árbol todos los clashes visibles (nodos hoja) que contienen
        el element_id dado en cualquiera de sus ClashObjects directos.
        Actualiza _multi_selected_nodes y refresca el árbol."""
        if element_id is None:
            return

        matching_nodes = []
        for node, item in self._node_item_map.items():
            if item is None or item.is_group:
                continue
            for co in item.objects:
                if co.element_id == element_id:
                    matching_nodes.append(node)
                    break

        if not matching_nodes:
            self._update_status_bar(
                u"⚠  No se encontraron más clashes con Elemento ID {}.".format(element_id)
            )
            return

        # Actualizar selección múltiple
        self._multi_selected_nodes = set(matching_nodes)

        # Mover el foco al primer nodo encontrado
        first_node = matching_nodes[0]
        self.tree.SelectedNode = first_node
        first_node.EnsureVisible()
        self.tree.Invalidate()

        # Habilitar botones de estado para cambio múltiple
        self._set_quick_btns_enabled(True)
        self._update_status_bar(
            u"ⓘ  {} clash(es) con Elemento ID {} seleccionados — usa los botones de estado para cambio múltiple.".format(
                len(matching_nodes), element_id
            )
        )

    def _set_quick_btns_enabled(self, enabled):
        """Habilita o deshabilita los botones de la barra de estado."""
        for btn in self._status_quick_btns.values():
            btn.Enabled = enabled

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _update_status_bar(self, text):

        try:
            self.detail_panel.lbl_message.Text = text
            self.detail_panel.lbl_message.Refresh()
        except:
            pass

# ═════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA pyRevit
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    form = ClashManagerForm(uidoc, doc)
    # Modeless: Show() sin ShowDialog() para no bloquear Revit
    form.Show()