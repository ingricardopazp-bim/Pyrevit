# -*- coding: utf-8 -*-
# =========================================================
# LINKED ELEMENT ID INSPECTOR  v2.1
# pyRevit | Revit 2024 - 2026
# Ricardo.extension — BIM Coordination
# =========================================================

from pyrevit import revit, forms

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import ObjectType

from System.Windows.Forms import *
from System.Collections.Generic import List

import System
import System.Drawing as Drawing

# =========================================================
# DOCUMENTOS
# =========================================================

uidoc = revit.uidoc
doc   = revit.doc

# =========================================================
# PALETA  — Light Theme
# =========================================================

class T:
    BG          = Drawing.Color.FromArgb(244, 247, 252) # Main background
    SURFACE     = Drawing.Color.FromArgb(255, 255, 255) # Header background / Cards
    
    ACCENT      = Drawing.Color.FromArgb(37, 99, 235)   # Blue
    GREEN       = Drawing.Color.FromArgb(22, 163, 74)
    AMBER       = Drawing.Color.FromArgb(217, 119, 6)

    TEXT        = Drawing.Color.FromArgb(15, 23, 42)    # Dark text
    SUBTEXT     = Drawing.Color.FromArgb(71, 85, 105)   # Gray text
    MUTED       = Drawing.Color.FromArgb(148, 163, 184) # Light gray
    BORDER      = Drawing.Color.FromArgb(226, 232, 240) # Border


# =========================================================
# HELPERS UI
# =========================================================

def make_label(text, font_size=9, bold=False, color=None, italic=False):
    style = Drawing.FontStyle.Regular
    if bold and italic:
        style = Drawing.FontStyle.Bold | Drawing.FontStyle.Italic
    elif bold:
        style = Drawing.FontStyle.Bold
    elif italic:
        style = Drawing.FontStyle.Italic

    lbl = Label()
    lbl.Text      = text
    lbl.Font      = Drawing.Font("Segoe UI", font_size, style)
    lbl.ForeColor = color or T.TEXT
    lbl.AutoSize  = True
    lbl.BackColor = Drawing.Color.Transparent
    # Add small padding to prevent font clipping on edges (common WinForms issue)
    lbl.Padding   = Padding(2, 0, 2, 0)
    return lbl


class RoundedButton(Panel):
    def __init__(self, text, w, h, bg, fg, border_color, parent_bg, action):
        Panel.__init__(self)
        self.Width = w
        self.Height = h
        self.BackColor = parent_bg
        self.Cursor = Cursors.Hand
        
        self._text = text
        self._bg = bg
        self._fg = fg
        self._border_color = border_color
        self._action = action
        self._hover = False
        self._pressed = False
        
        self.Paint += self._on_paint
        self.MouseEnter += self._on_enter
        self.MouseLeave += self._on_leave
        self.MouseDown += self._on_down
        self.MouseUp += self._on_up
        self.Click += self._on_click
        
    def _on_enter(self, s, e):
        self._hover = True
        self.Invalidate()
    def _on_leave(self, s, e):
        self._hover = False
        self._pressed = False
        self.Invalidate()
    def _on_down(self, s, e):
        self._pressed = True
        self.Invalidate()
    def _on_up(self, s, e):
        self._pressed = False
        self.Invalidate()
    def _on_click(self, s, e):
        if self._action:
            self._action()
            
    def _on_paint(self, s, e):
        g = e.Graphics
        g.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias
        
        rect = Drawing.Rectangle(1, 1, self.Width - 3, self.Height - 3)
        radius = 8
        path = Drawing.Drawing2D.GraphicsPath()
        path.AddArc(rect.X, rect.Y, radius, radius, 180, 90)
        path.AddArc(rect.Right - radius, rect.Y, radius, radius, 270, 90)
        path.AddArc(rect.Right - radius, rect.Bottom - radius, radius, radius, 0, 90)
        path.AddArc(rect.X, rect.Bottom - radius, radius, radius, 90, 90)
        path.CloseFigure()
        
        bg_color = self._bg
        if self._pressed:
            bg_color = Drawing.Color.FromArgb(max(0, bg_color.R-15), max(0, bg_color.G-15), max(0, bg_color.B-15))
        elif self._hover:
            bg_color = Drawing.Color.FromArgb(max(0, bg_color.R-5), max(0, bg_color.G-5), max(0, bg_color.B-5))
            
        brush = Drawing.SolidBrush(bg_color)
        g.FillPath(brush, path)
        brush.Dispose()
        
        pen = Drawing.Pen(self._border_color, 1)
        g.DrawPath(pen, path)
        pen.Dispose()
        
        font = Drawing.Font("Segoe UI", 9, Drawing.FontStyle.Bold)
        sf = Drawing.StringFormat()
        sf.Alignment = Drawing.StringAlignment.Center
        sf.LineAlignment = Drawing.StringAlignment.Center
        text_brush = Drawing.SolidBrush(self._fg)
        g.DrawString(self._text, font, text_brush, rect, sf)
        text_brush.Dispose()
        font.Dispose()


# =========================================================
# TARJETA
# =========================================================

class ElementCard(Panel):
    CARD_H = 126
    def __init__(self, data, index, status_bar):
        Panel.__init__(self)
        self._data = data
        self._status_bar = status_bar
        
        self.Width = 548
        self.Height = self.CARD_H
        self.BackColor = T.BG
        self.Margin = Padding(0, 0, 0, 12)
        
        self.inner_bg = T.SURFACE
        self.Paint += self._on_paint
        
        offsetX = 22
        
        lbl_num = make_label("#{0:02d}".format(index + 1), font_size=8, color=T.MUTED, italic=True)
        lbl_num.Location = Drawing.Point(offsetX, 12)
        self.Controls.Add(lbl_num)
        
        lbl_cat = make_label(data["category"], font_size=10, bold=True, color=T.ACCENT)
        lbl_cat.Location = Drawing.Point(offsetX, 26)
        self.Controls.Add(lbl_cat)
        
        lbl_id = Label()
        lbl_id.Text = data["id"]
        lbl_id.Font = Drawing.Font("Consolas", 14, Drawing.FontStyle.Bold)
        lbl_id.ForeColor = T.TEXT
        lbl_id.AutoSize = True
        lbl_id.Location = Drawing.Point(offsetX, 48)
        lbl_id.BackColor = Drawing.Color.Transparent
        self.Controls.Add(lbl_id)
        
        lbl_model = make_label(u"\u25CB  {}".format(data["model"]), font_size=9, color=T.SUBTEXT)
        lbl_model.Location = Drawing.Point(offsetX, 78)
        self.Controls.Add(lbl_model)
        
        uid_display = data["uid"][:45] + "..." if len(data["uid"]) > 45 else data["uid"]
        lbl_uid = make_label(uid_display, font_size=8, color=T.MUTED)
        lbl_uid.Location = Drawing.Point(offsetX, 98)
        self.Controls.Add(lbl_uid)
        
        # Botón 1: SOLO el número de ID
        btn_id = RoundedButton("Copiar ID", 110, 32, T.SURFACE, T.TEXT, T.BORDER, T.SURFACE, self._copy_id_only)
        btn_id.Location = Drawing.Point(415, 28)
        self.Controls.Add(btn_id)
        
        # Botón 2: ID + PROY (antes era el botón 1)
        btn_id_proy = RoundedButton(u"ID + Proyecto", 110, 32, T.SURFACE, T.TEXT, T.BORDER, T.SURFACE, self._copy_id_modelo)
        btn_id_proy.Location = Drawing.Point(415, 68)
        self.Controls.Add(btn_id_proy)
        
        # Para que el hover funcione en botones, el parent_bg del botón es inner_bg (que cambia a gris)
        self._btn_id = btn_id
        self._btn_id_proy = btn_id_proy

        self.MouseEnter += self._on_enter
        self.MouseLeave += self._on_leave
        for ctrl in self.Controls:
            if not isinstance(ctrl, RoundedButton):
                ctrl.MouseEnter += self._on_enter
                ctrl.MouseLeave += self._on_leave

    def _copy_id_only(self):
        Clipboard.SetText(self._data["id"])
        self._status_bar.set_ok(u"ID copiado: {}".format(self._data["id"]))

    def _copy_id_modelo(self):
        text = u"ID: {}\t\r\nPROY: {}".format(self._data["id"], self._data["model"])
        Clipboard.SetText(text)
        self._status_bar.set_ok(u"Copiado \u2014 ID {} | {}".format(self._data["id"], self._data["model"]))

    def _on_enter(self, s, e):
        self.inner_bg = Drawing.Color.FromArgb(248, 250, 252)
        self._btn_id.BackColor = self.inner_bg
        self._btn_id_proy.BackColor = self.inner_bg
        self.Invalidate()
    def _on_leave(self, s, e):
        self.inner_bg = T.SURFACE
        self._btn_id.BackColor = self.inner_bg
        self._btn_id_proy.BackColor = self.inner_bg
        self.Invalidate()
        
    def _on_paint(self, s, e):
        g = e.Graphics
        g.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias
        
        rect = Drawing.Rectangle(2, 2, self.Width - 5, self.Height - 5)
        radius = 8
        path = Drawing.Drawing2D.GraphicsPath()
        path.AddArc(rect.X, rect.Y, radius, radius, 180, 90)
        path.AddArc(rect.Right - radius, rect.Y, radius, radius, 270, 90)
        path.AddArc(rect.Right - radius, rect.Bottom - radius, radius, radius, 0, 90)
        path.AddArc(rect.X, rect.Bottom - radius, radius, radius, 90, 90)
        path.CloseFigure()
        
        brush = Drawing.SolidBrush(self.inner_bg)
        g.FillPath(brush, path)
        brush.Dispose()
        
        old_clip = g.Clip
        g.SetClip(path)
        accent_brush = Drawing.SolidBrush(T.ACCENT)
        g.FillRectangle(accent_brush, rect.X, rect.Y, 6, rect.Height)
        accent_brush.Dispose()
        g.Clip = old_clip
        
        pen = Drawing.Pen(T.BORDER, 1)
        g.DrawPath(pen, path)
        pen.Dispose()


# =========================================================
# BARRA DE ESTADO
# =========================================================

class StatusBar(Panel):
    def __init__(self, form_width):
        Panel.__init__(self)
        self.Height    = 36
        self.Width     = form_width
        self.Dock      = DockStyle.Bottom
        self.BackColor = T.BG
        
        self.Paint += self._on_paint
        
        self._lbl = make_label(u"Listo.", font_size=9, color=T.SUBTEXT)
        self._lbl.Location = Drawing.Point(24, 8)
        self.Controls.Add(self._lbl)
        
        self._dot = Panel()
        self._dot.Width = 8
        self._dot.Height = 8
        self._dot.Location = Drawing.Point(10, 13)
        self._dot.Paint += self._paint_dot
        self._dot_color = T.MUTED
        self.Controls.Add(self._dot)
        
        self._timer = Timer()
        self._timer.Interval = 3000
        self._timer.Tick += self._reset

    def set_ok(self, msg):
        self._lbl.Text = msg
        self._lbl.ForeColor = T.GREEN
        self._dot_color = T.GREEN
        self._dot.Invalidate()
        self._timer.Stop()
        self._timer.Start()

    def set_info(self, msg):
        self._lbl.Text = msg
        self._lbl.ForeColor = T.SUBTEXT
        self._dot_color = T.ACCENT
        self._dot.Invalidate()

    def _reset(self, s, e):
        self._timer.Stop()
        self._lbl.Text = u"Listo."
        self._lbl.ForeColor = T.SUBTEXT
        self._dot_color = T.MUTED
        self._dot.Invalidate()

    def _paint_dot(self, s, e):
        g = e.Graphics
        g.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias
        brush = Drawing.SolidBrush(self._dot_color)
        g.FillEllipse(brush, 0, 0, s.Width-1, s.Height-1)
        brush.Dispose()
        
    def _on_paint(self, s, e):
        g = e.Graphics
        pen = Drawing.Pen(T.BORDER, 1)
        g.DrawLine(pen, 0, 0, s.Width, 0)
        pen.Dispose()


# =========================================================
# FORMULARIO PRINCIPAL
# =========================================================

class InspectorForm(Form):
    W = 606
    H = 720

    def __init__(self, elements):
        self._elements = elements

        self.Text              = "Linked Element ID Inspector"
        self.Width             = self.W
        self.Height            = self.H
        self.BackColor         = T.BG
        self.StartPosition     = FormStartPosition.CenterScreen
        self.FormBorderStyle   = FormBorderStyle.FixedSingle
        self.MaximizeBox       = False

        self.status = StatusBar(self.W)
        self.Controls.Add(self.status)

        hdr = Panel()
        hdr.Dock      = DockStyle.Top
        hdr.Height    = 130
        hdr.BackColor = T.SURFACE
        self.Controls.Add(hdr)

        sep = Panel()
        sep.Width     = self.W
        sep.Height    = 2
        sep.Location  = Drawing.Point(0, 128)
        sep.BackColor = T.ACCENT
        hdr.Controls.Add(sep)

        lbl_title = make_label("LINKED ELEMENT ID INSPECTOR", font_size=13, bold=True, color=T.ACCENT)
        lbl_title.Location = Drawing.Point(20, 20)
        hdr.Controls.Add(lbl_title)

        lbl_sub = make_label(u"{} elemento(s) seleccionado(s)".format(len(elements)), font_size=10, color=T.SUBTEXT)
        lbl_sub.Location = Drawing.Point(22, 48)
        hdr.Controls.Add(lbl_sub)

        btn_all = RoundedButton("Copiar todo", 110, 32, T.SURFACE, T.TEXT, T.BORDER, T.SURFACE, self._copy_all_rich)
        btn_all.Location = Drawing.Point(22, 80)
        hdr.Controls.Add(btn_all)

        btn_tsv = RoundedButton("Copiar tabla", 110, 32, T.SURFACE, T.TEXT, T.BORDER, T.SURFACE, self._copy_as_tsv)
        btn_tsv.Location = Drawing.Point(142, 80)
        hdr.Controls.Add(btn_tsv)

        self.flow = FlowLayoutPanel()
        self.flow.Location    = Drawing.Point(20, 150)
        self.flow.Width       = 562
        self.flow.Height      = self.H - 150 - 36 - 24
        self.flow.AutoScroll  = True
        self.flow.WrapContents = False
        self.flow.FlowDirection = FlowDirection.TopDown
        self.flow.Padding     = Padding(0, 8, 0, 8)
        self.Controls.Add(self.flow)

        for i, data in enumerate(elements):
            card = ElementCard(data, i, self.status)
            self.flow.Controls.Add(card)

        self.status.set_info(
            u"{} elemento(s). 'Copiar ID' copia solo el n\u00famero; 'ID + Proyecto' incluye el modelo.".format(len(elements))
        )

    def _copy_all_rich(self):
        lines = []
        for e in self._elements:
            lines.append(u"{}  |  {}  |  {}".format(e["id"], e["model"], e["category"]))
        Clipboard.SetText(u"\r\n".join(lines))
        self.status.set_ok(u"{} IDs copiados con modelo y categoría.".format(len(lines)))

    def _copy_as_tsv(self):
        rows = [u"ID\tModelo\tCategoría\tUniqueID"]
        for e in self._elements:
            rows.append(u"{}\t{}\t{}\t{}".format(e["id"], e["model"], e["category"], e["uid"]))
        Clipboard.SetText(u"\r\n".join(rows))
        self.status.set_ok(u"Tabla copiada ({} filas) \u2014 lista para pegar en Excel.".format(len(rows) - 1))


# =========================================================
# MAIN
# =========================================================

def get_selected_linked_elements():
    refs = uidoc.Selection.PickObjects(
        ObjectType.LinkedElement,
        "Seleccione elementos en modelos vinculados"
    )
    data = []
    for ref in refs:
        try:
            link_instance = doc.GetElement(ref.ElementId)
            link_doc      = link_instance.GetLinkDocument()
            if not link_doc:
                continue
            linked_elem = link_doc.GetElement(ref.LinkedElementId)
            if not linked_elem:
                continue
            try:
                category = linked_elem.Category.Name
            except:
                category = "Sin categoria"
            try:
                uid = linked_elem.UniqueId
            except:
                uid = "-"
            data.append({
                "id":       str(linked_elem.Id.IntegerValue),
                "uid":      uid,
                "category": category,
                "model":    link_doc.Title,
            })
        except:
            pass
    return data

try:
    elements = get_selected_linked_elements()
    if not elements:
        forms.alert(
            "No se seleccionaron elementos vinculados.",
            title="Linked Element Inspector"
        )
    else:
        form = InspectorForm(elements)
        form.ShowDialog()

except System.OperationCanceledException:
    pass
except Exception as ex:
    forms.alert(str(ex), title="Error — Linked Element Inspector")