# -*- coding: utf-8 -*-
from __future__ import absolute_import

import clr

clr.AddReference('System')
clr.AddReference('System.Drawing')
clr.AddReference('System.Windows.Forms')

from System import EventHandler, Double
from System.ComponentModel import ListSortDirection
from System.Drawing import Color, Font, FontStyle, Point, Rectangle, Size, StringFormat, StringAlignment, ContentAlignment
from System.Drawing import SolidBrush, Pen, Region
from System.Drawing.Drawing2D import GraphicsPath, SmoothingMode, InterpolationMode, PixelOffsetMode
from System.Windows.Forms import (
    AnchorStyles,
    BorderStyle,
    Button,
    CheckBox,
    DockStyle,
    DrawItemEventHandler,
    DrawItemState,
    FlatStyle,
    Form,
    FormBorderStyle,
    Label,
    ListBox,
    MessageBox,
    MethodInvoker,
    NumericUpDown,
    PaintEventHandler,
    Panel,
    SelectionMode,
    SplitContainer,
    Orientation,
    FixedPanel,
    DataGridView,
    DataGridViewSelectionMode,
    DataGridViewTextBoxColumn,
    DataGridViewAutoSizeColumnMode,
    DataGridViewCellBorderStyle,
    DataGridViewAutoSizeRowsMode,
    DataGridViewHeaderBorderStyle,
    Padding,
    Cursors,
    FormStartPosition,
    PictureBox,
    PictureBoxSizeMode,
    DataGridViewCellPaintingEventHandler,
    DataGridViewPaintParts,
    FormClosedEventHandler,
    SortOrder,
    OpenFileDialog,
    DialogResult
)

from bim_clash.models import ClashStatus

# ─── Paleta de Colores ────────────────────────────────────────────────────────
C_BG_MAIN         = Color.FromArgb(243, 244, 246)
C_WHITE           = Color.FromArgb(255, 255, 255)
C_HEADER_BG       = Color.FromArgb(255, 255, 255)
C_TEXT_MAIN       = Color.FromArgb(55, 65, 81)
C_TEXT_MUTED      = Color.FromArgb(156, 163, 175)
C_DIVIDER         = Color.FromArgb(229, 231, 235)

C_NEW             = Color.FromArgb(249, 115, 22)
C_ACTIVE          = Color.FromArgb(239, 68, 68)
C_REVIEWED        = Color.FromArgb(34, 197, 94)
C_APPROVED        = Color.FromArgb(156, 163, 175)
C_RESOLVED        = Color.FromArgb(59, 130, 246)

C_LIST_BG         = Color.FromArgb(255, 255, 255)
C_LIST_ALT        = Color.FromArgb(249, 250, 251)
C_LIST_SEL        = Color.FromArgb(219, 234, 254)
C_LIST_SEL_TEXT   = Color.FromArgb(29, 78, 216)
C_CARD_BG         = Color.FromArgb(249, 250, 251)

C_BTN_SCAN        = Color.FromArgb(56, 189, 248)
C_BTN_ABORT       = Color.FromArgb(239, 68, 68)

C_FILTER_INACTIVE = Color.FromArgb(243, 244, 246)
C_FILTER_TEXT_OFF = Color.FromArgb(107, 114, 128)

STATUS_BAR_COLOR = {
    ClashStatus.NEW:      Color.FromArgb(249, 115, 22),
    ClashStatus.ACTIVE:   Color.FromArgb(220, 38, 38),
    ClashStatus.REVIEWED: Color.FromArgb(22, 163, 74),
    ClashStatus.APPROVED: Color.FromArgb(75, 85, 99),
    ClashStatus.RESOLVED: Color.FromArgb(37, 99, 235),
}
STATUS_COLOR = {
    ClashStatus.NEW:      C_NEW,
    ClashStatus.ACTIVE:   C_ACTIVE,
    ClashStatus.REVIEWED: C_REVIEWED,
    ClashStatus.APPROVED: C_APPROVED,
    ClashStatus.RESOLVED: C_RESOLVED,
}

FILTER_COLORS = {
    'New':      C_NEW,
    'Active':   C_ACTIVE,
    'Reviewed': C_REVIEWED,
    'Approved': C_APPROVED,
    'Resolved': C_RESOLVED,
    'Linked':   Color.FromArgb(253, 186, 116),
    'Model':    Color.FromArgb(196, 181, 253),
}

C_HIDDEN_WARN = Color.FromArgb(234, 88, 12)


def _clash_color(record):
    return STATUS_COLOR.get(record.status, C_TEXT_MUTED)


def _clash_bar_color(record):
    return STATUS_BAR_COLOR.get(record.status, Color.FromArgb(75, 85, 99))


def _make_rounded(control, radius=6, draw_border=True):
    def on_resize(s, e):
        try:
            path = GraphicsPath()
            r = s.ClientRectangle
            if r.Width <= 0 or r.Height <= 0: return
            d = radius * 2
            path.AddArc(r.X, r.Y, d, d, 180, 90)
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90)
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90)
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90)
            path.CloseFigure()
            s.Region = Region(path)
        except: pass
        
    def on_paint(s, e):
        if not draw_border: return
        try:
            g = e.Graphics
            g.SmoothingMode = SmoothingMode.AntiAlias
            path = GraphicsPath()
            r = Rectangle(0, 0, s.Width - 1, s.Height - 1)
            d = radius * 2
            path.AddArc(r.X, r.Y, d, d, 180, 90)
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90)
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90)
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90)
            path.CloseFigure()
            
            c = getattr(s.FlatAppearance, 'BorderColor', Color.Gray)
            pen = Pen(c, 1.5)
            g.DrawPath(pen, path)
            pen.Dispose()
            path.Dispose()
        except: pass

    control.Resize += EventHandler(on_resize)
    if draw_border:
        control.Paint += PaintEventHandler(on_paint)
        if hasattr(control, 'FlatAppearance'):
            control.FlatAppearance.BorderSize = 0
    on_resize(control, None)


def _flat_btn(text, loc, size, bg, parent, fg=None):
    b = Button()
    b.Text = text
    b.Location = Point(*loc)
    b.Size = Size(*size)
    b.FlatStyle = FlatStyle.Flat
    b.BackColor = bg
    b.FlatAppearance.BorderSize = 0
    if fg:
        b.ForeColor = fg
    b.Font = Font("Segoe UI", 8, FontStyle.Regular)
    b.Cursor = Cursors.Hand
    parent.Controls.Add(b)
    _make_rounded(b, radius=6, draw_border=True)
    return b


# ─── Botón de filtro toggle ───────────────────────────────────────────────────
class FilterButton(Button):
    def __init__(self, label, active_color):
        Button.__init__(self)
        self._label        = label
        self._active_color = active_color
        self._active       = False

        self.Text      = label
        self.FlatStyle = FlatStyle.Flat
        self.Font      = Font('Segoe UI', 8, FontStyle.Bold)
        self.FlatAppearance.BorderSize = 1
        self._update_style()

    @property
    def is_active(self):
        return self._active

    def toggle(self):
        self._active = not self._active
        self._update_style()

    def set_active(self, value):
        self._active = bool(value)
        self._update_style()

    def _update_style(self):
        if self._active:
            self.BackColor = self._active_color
            self.ForeColor = C_TEXT_MAIN if self._active_color not in (C_ACTIVE, C_RESOLVED) else Color.White
            self.FlatAppearance.BorderColor = self._active_color
        else:
            self.BackColor = C_FILTER_INACTIVE
            self.ForeColor = C_FILTER_TEXT_OFF
            self.FlatAppearance.BorderColor = C_DIVIDER


# ─── ListBox owner-draw ───────────────────────────────────────────────────────
_BAR_WIDTH = 8

class ClashListBox(ListBox):
    def __init__(self):
        ListBox.__init__(self)
        from System.Windows.Forms import DrawMode
        self.DrawMode            = DrawMode.OwnerDrawFixed
        self.ItemHeight          = 44
        self.BorderStyle         = getattr(BorderStyle, 'None')
        self.HorizontalScrollbar = True
        self.BackColor           = C_LIST_BG
        self.ForeColor           = C_TEXT_MAIN
        self.SelectionMode       = SelectionMode.MultiExtended

        self._font_title = Font('Segoe UI', 9, FontStyle.Bold)
        self._font_desc  = Font('Segoe UI', 8, FontStyle.Regular)
        self._pen_div    = Pen(C_DIVIDER)
        self._brush_sel  = SolidBrush(C_LIST_SEL)
        self._brush_alt  = SolidBrush(C_LIST_ALT)
        self._brush_bg   = SolidBrush(C_LIST_BG)
        self._brush_txt  = SolidBrush(C_TEXT_MAIN)
        self._brush_sel_t= SolidBrush(C_LIST_SEL_TEXT)
        self._brush_muted= SolidBrush(C_TEXT_MUTED)

        self.DrawItem += DrawItemEventHandler(self._on_draw_item)

    def _on_draw_item(self, sender, e):
        if e.Index < 0 or e.Index >= self.Items.Count:
            return

        record   = self.Items[e.Index]
        selected = (e.State & DrawItemState.Selected) == DrawItemState.Selected
        g, rc    = e.Graphics, e.Bounds

        bg_brush = self._brush_sel if selected else (self._brush_alt if e.Index % 2 else self._brush_bg)
        g.FillRectangle(bg_brush, rc)

        bar_color    = _clash_bar_color(record)
        status_brush = SolidBrush(bar_color)
        g.FillRectangle(status_brush, Rectangle(rc.X, rc.Y, _BAR_WIDTH, rc.Height))
        status_brush.Dispose()

        text_x = float(rc.X + _BAR_WIDTH + 8)

        title_brush = self._brush_sel_t if selected else self._brush_txt
        # NEW FORMAT: #ID1 vs #ID2
        title_text = u'#%s vs #%s' % (record.source_id, record.target_id)
        g.DrawString(title_text, self._font_title, title_brush, text_x, float(rc.Y + 5))

        # NEW FORMAT: Category1 • Category2 • Volume • Status
        detail = u'%s \u2022 %s \u2022 %.2fm\u00b3 \u2022 %s' % (
            record.source_category, record.target_category,
            record.volume * 0.0283168, record.status)

        desc_brush = self._brush_sel_t if selected else self._brush_muted
        g.DrawString(detail, self._font_desc, desc_brush, text_x, float(rc.Y + 24))

        g.DrawLine(self._pen_div, rc.X, rc.Bottom - 1, rc.Right, rc.Bottom - 1)

    def Dispose(self, disposing):
        if disposing:
            self._font_title.Dispose()
            self._font_desc.Dispose()
            self._pen_div.Dispose()
            self._brush_sel.Dispose()
            self._brush_alt.Dispose()
            self._brush_bg.Dispose()
            self._brush_txt.Dispose()
            self._brush_sel_t.Dispose()
            self._brush_muted.Dispose()
        ListBox.Dispose(self, disposing)


# ─── Panel de detalle Responsivo ─────────────────────────────────────────────
class ToolButton(Button):
    """Boton de herramienta (Section Box / Isolate) con estado on/off.
    Subclase de Python porque los controles .NET puros no admiten atributos nuevos."""

    def __init__(self, color_off, color_on):
        Button.__init__(self)
        self._is_active = False
        self._color_off = color_off
        self._color_on  = color_on

    def set_active(self, active):
        self._is_active = bool(active)
        self.BackColor = self._color_on if self._is_active else self._color_off


class ConflictDetailPanel(Panel):
    def __init__(self):
        Panel.__init__(self)
        self.BackColor       = C_BG_MAIN
        self._record         = None
        self._on_select      = None
        self._on_select_only = None
        self._on_section_box = None
        self._on_isolate     = None
        self._uidoc          = None
        self._is_horizontal  = False
        self._build()
        self.Resize += EventHandler(self._on_resize)

    def _build(self):
        from System.Drawing import ContentAlignment
        self.BackColor = C_WHITE

        self._title = self._lbl('Conflict Detail', Font('Segoe UI', 10, FontStyle.Bold), C_TEXT_MAIN, (10, 8), (300, 20))
        self._badge = self._lbl('', Font('Segoe UI', 8, FontStyle.Bold), C_TEXT_MAIN, (10, 30), (100, 18))
        self._badge.BackColor = C_FILTER_INACTIVE
        self._vol = self._lbl('', Font('Segoe UI', 8, FontStyle.Regular), C_TEXT_MUTED, (116, 32), (200, 16))
        sep = Panel()
        sep.BackColor = C_DIVIDER
        self.Controls.Add(sep)
        self._sep = sep

        # Herramientas de vista sobre los DOS elementos: Section Box + Isolate
        _COLOR_BTN_OFF = Color.FromArgb(51, 65, 85)
        _COLOR_BTN_ON  = Color.FromArgb(14, 165, 233)   # azul activo

        def _tool_btn(text, cb_name):
            btn = ToolButton(_COLOR_BTN_OFF, _COLOR_BTN_ON)
            btn.Text = text
            btn.BackColor = _COLOR_BTN_OFF
            btn.ForeColor = Color.White
            btn.FlatStyle = FlatStyle.Flat
            btn.Font = Font('Segoe UI', 8, FontStyle.Bold)
            btn.FlatAppearance.BorderSize = 0

            self.Controls.Add(btn)
            _make_rounded(btn, radius=8, draw_border=False)
            def _click(s, a, n=cb_name):
                cb = getattr(self, n)
                if cb and self._record:
                    cb(self._record)
            btn.Click += EventHandler(_click)
            return btn
        self._btn_section = _tool_btn(u'\u25A2 SECTION BOX', '_on_section_box')
        self._btn_isolate = _tool_btn(u'\u25D0 ISOLATE', '_on_isolate')

        # Cards
        self._card_a = self._build_card('A', Color.FromArgb(14, 165, 233), 'source')
        self._card_b = self._build_card('B', Color.FromArgb(249, 115, 22), 'target')

        self._ph = self._lbl(u'Select a conflict\nto see details', Font('Segoe UI', 10, FontStyle.Regular), C_TEXT_MUTED, (0, 0), (10, 10))
        self._ph.TextAlign = ContentAlignment.MiddleCenter
        self._show_placeholder(True)

    def _lbl(self, text, font, color, loc, sz):
        l = Label()
        l.Text      = text
        l.Font      = font
        l.ForeColor = color
        l.BackColor = Color.Transparent
        l.Location  = Point(loc[0], loc[1])
        l.Size      = Size(sz[0], sz[1])
        l.AutoSize  = False
        self.Controls.Add(l)
        return l

    def _build_card(self, letter, accent, target):
        bg = Panel()
        bg.BackColor = C_CARD_BG
        self.Controls.Add(bg)

        bar = Panel()
        bar.BackColor = accent
        bg.Controls.Add(bar)

        def _cl(text, font, color):
            l = Label()
            l.Text = text
            l.Font = font
            l.ForeColor = color
            l.BackColor = Color.Transparent
            l.AutoSize = False
            bg.Controls.Add(l)
            return l

        lbl_letter = _cl('ELEMENT ' + letter, Font('Segoe UI', 7, FontStyle.Bold), accent)
        lbl_name = _cl('', Font('Segoe UI', 9, FontStyle.Bold), C_TEXT_MAIN)
        lbl_id = _cl('', Font('Segoe UI', 8, FontStyle.Regular), C_TEXT_MUTED)
        lbl_cat = _cl('', Font('Segoe UI', 8, FontStyle.Regular), C_TEXT_MAIN)
        lbl_doc = _cl('', Font('Segoe UI', 8, FontStyle.Italic), C_TEXT_MUTED)

        btn = Button()
        btn.Text = u'\u25ce Select in View'
        btn.BackColor = accent
        btn.ForeColor = Color.White
        btn.FlatStyle = FlatStyle.Flat
        btn.Font = Font('Segoe UI', 8, FontStyle.Bold)
        btn.FlatAppearance.BorderSize = 0
        bg.Controls.Add(btn)
        _make_rounded(btn, radius=8, draw_border=False)

        btn2 = Button()
        btn2.Text = u'\u25cb Select Only'
        btn2.BackColor = C_FILTER_INACTIVE
        btn2.ForeColor = C_TEXT_MAIN
        btn2.FlatStyle = FlatStyle.Flat
        btn2.Font = Font('Segoe UI', 8, FontStyle.Bold)
        btn2.FlatAppearance.BorderSize = 0
        bg.Controls.Add(btn2)
        _make_rounded(btn2, radius=8, draw_border=False)

        _t = target
        def _on_click(s, a, t=_t):
            if self._on_select and self._record:
                self._on_select(self._record, t)
        def _on_click2(s, a, t=_t):
            if self._on_select_only and self._record:
                self._on_select_only(self._record, t)
        btn.Click += EventHandler(_on_click)
        btn2.Click += EventHandler(_on_click2)

        return {
            'bg': bg, 'bar': bar, 'letter': lbl_letter, 'name': lbl_name, 'id': lbl_id,
            'cat': lbl_cat, 'doc': lbl_doc, 'btn': btn, 'btn2': btn2, 'accent': accent
        }

    def _on_resize(self, sender, args):
        w = self.Width
        h = self.Height
        self._ph.Size = Size(w, h)
        
        is_horiz = w >= 800
        self._is_horizontal = is_horiz

        if is_horiz:
            self._sep.Location = Point(0, 40)
            self._sep.Size = Size(w, 1)
            tbw = 130
            self._btn_isolate.Size = Size(tbw, 26)
            self._btn_isolate.Location = Point(w - 10 - tbw, 8)
            self._btn_section.Size = Size(tbw, 26)
            self._btn_section.Location = Point(w - 10 - 2 * tbw - 6, 8)
            self._title.Size = Size(max(50, w - 20 - 2 * tbw - 16), 24)
            self._title.Font = Font('Segoe UI', 12, FontStyle.Bold)
            self._badge.Visible = False
            self._vol.Visible = False
            
            card_h = max(80, (h - 60) // 2 - 5)
            # Layout Horizontal Mode for Cards
            self._layout_card(self._card_a, 10, 50, w - 20, card_h, is_horiz)
            self._layout_card(self._card_b, 10, 50 + card_h + 10, w - 20, card_h, is_horiz)
        else:
            self._sep.Location = Point(0, 56)
            self._sep.Size = Size(w, 1)
            self._title.Size = Size(w - 20, 20)
            self._title.Font = Font('Segoe UI', 10, FontStyle.Bold)
            self._badge.Visible = self._record is not None
            self._vol.Visible = self._record is not None
            
            # Fila de herramientas (Section Box / Isolate) antes de las tarjetas
            tbw = (w - 16 - 6) // 2
            self._btn_section.Size = Size(tbw, 28)
            self._btn_section.Location = Point(8, 62)
            self._btn_isolate.Size = Size(tbw, 28)
            self._btn_isolate.Location = Point(8 + tbw + 6, 62)

            top = 98
            card_h = max(118, min(132, (h - top - 18) // 2))
            self._layout_card(self._card_a, 8, top, w - 16, card_h, is_horiz)
            self._layout_card(self._card_b, 8, top + card_h + 10, w - 16, card_h, is_horiz)

    def _layout_card(self, card, x, y, w, h, is_horiz):
        bg = card['bg']
        bg.Location = Point(x, y)
        bg.Size = Size(w, h)
        card['bar'].Size = Size(4, h)
        
        if is_horiz:
            text_x = 14

            # Botones a la derecha
            btn_w = 120
            btn_h = (h - 20) // 2
            card['btn'].Location = Point(w - btn_w - 10, 10)
            card['btn'].Size = Size(btn_w, btn_h)
            card['btn'].Text = u'\u25ce VIEW'
            card['btn2'].Location = Point(w - btn_w - 10, 10 + btn_h + 5)
            card['btn2'].Size = Size(btn_w, btn_h)
            card['btn2'].Text = u'\u25cb ONLY'

            text_w = w - btn_w - text_x - 20
            card['letter'].Location = Point(text_x, 6)
            card['letter'].Size = Size(text_w, 14)
            card['name'].Location = Point(text_x, 22)
            card['name'].Size = Size(text_w, 20)
            card['id'].Location = Point(text_x, 42)
            card['id'].Size = Size(text_w, 16)
            card['cat'].Location = Point(text_x, 58)
            card['cat'].Size = Size(text_w, 16)
            card['doc'].Location = Point(text_x, 74)
            card['doc'].Size = Size(text_w, 16)
        else:
            # Buttons at bottom
            btn_w = (w - 30) // 2
            card['btn'].Location = Point(10, h - 34)
            card['btn'].Size = Size(btn_w, 26)
            card['btn'].Text = u'\u25ce Select in View'
            
            card['btn2'].Location = Point(10 + btn_w + 10, h - 34)
            card['btn2'].Size = Size(btn_w, 26)
            card['btn2'].Text = u'\u25cb Select Only'
            
            text_w = w - 20
            card['letter'].Location = Point(10, 6)
            card['letter'].Size = Size(text_w, 14)
            card['name'].Location = Point(10, 22)
            card['name'].Size = Size(text_w, 20)
            card['id'].Location = Point(10, 42)
            card['id'].Size = Size(text_w, 16)
            card['cat'].Location = Point(10, 58)
            card['cat'].Size = Size(text_w, 16)
            card['doc'].Location = Point(10, 74)
            card['doc'].Size = Size(text_w, 16)




    def _show_placeholder(self, show):
        self._ph.Visible = show
        self._title.Visible = not show
        if not self._is_horizontal:
            self._badge.Visible = not show
            self._vol.Visible = not show
        self._sep.Visible = not show
        self._btn_section.Visible = not show
        self._btn_isolate.Visible = not show
        self._card_a['bg'].Visible = not show
        self._card_b['bg'].Visible = not show

    def update_tool_buttons(self, isolate_active=False, section_active=False):
        """Actualiza el color ON/OFF de los botones Isolate y Section Box."""
        try:
            self._btn_isolate.set_active(isolate_active)
        except Exception:
            pass
        try:
            self._btn_section.set_active(section_active)
        except Exception:
            pass

    def load_record(self, record):
        self._record = record
        if record is None:
            self._show_placeholder(True)
            return
            
        self._show_placeholder(False)
        self._on_resize(None, None) # force layout refresh

        if self._is_horizontal:
            self._title.Text = u'Conflict Detail: #%s vs #%s' % (record.source_id, record.target_id)
        else:
            self._title.Text = u'Conflict Detail'
            
        self._badge.Text = '  ' + record.status.upper() + '  '
        self._badge.BackColor = _clash_color(record)
        self._vol.Text = u'Vol: %.5f ft\u00b3' % record.volume

        self._card_a['name'].Text = record.source_name
        self._card_a['id'].Text   = 'ID: %s' % record.source_id
        self._card_a['cat'].Text  = 'Category: %s' % record.source_category
        self._card_a['doc'].Text  = 'Doc: %s' % record.source_doc

        self._card_b['name'].Text = record.target_name
        self._card_b['id'].Text   = 'ID: %s' % record.target_id
        self._card_b['cat'].Text  = 'Category: %s' % record.target_category
        self._card_b['doc'].Text  = '%s%s' % (u'\U0001f517 ' if record.is_linked else '', record.target_doc)

        link_color = Color.FromArgb(249, 115, 22) if record.is_linked else Color.FromArgb(249, 115, 22)
        self._card_b['bar'].BackColor = link_color
        self._card_b['btn'].BackColor = link_color



# ─── Diálogo inicial: motor interno vs XML de Navisworks ─────────────────────
class SourceModeDialog(Form):
    def __init__(self):
        Form.__init__(self)
        self.mode = None  # 'engine' | 'xml'

        self.Text            = 'Fuente de datos'
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition   = FormStartPosition.CenterParent
        self.MinimizeBox     = False
        self.MaximizeBox     = False
        self.ClientSize      = Size(360, 170)
        self.BackColor       = C_WHITE

        lbl = Label()
        lbl.Text      = u'\u00bfCon qu\u00e9 fuente vas a trabajar los conflictos?'
        lbl.Font      = Font('Segoe UI', 9, FontStyle.Regular)
        lbl.ForeColor = C_TEXT_MAIN
        lbl.TextAlign = ContentAlignment.MiddleCenter
        lbl.AutoSize  = False
        lbl.Location  = Point(10, 15)
        lbl.Size      = Size(340, 40)
        self.Controls.Add(lbl)

        btn_engine = _flat_btn(u'\u25A3 MOTOR INTERNO', (30, 70), (150, 50), C_BTN_SCAN, self, fg=Color.White)
        btn_engine.Font = Font('Segoe UI', 9, FontStyle.Bold)
        btn_engine.Click += EventHandler(self._pick_engine)

        btn_xml = _flat_btn(u'\u2913 CARGAR XML', (190, 70), (150, 50), Color.FromArgb(99, 102, 241), self, fg=Color.White)
        btn_xml.Font = Font('Segoe UI', 9, FontStyle.Bold)
        btn_xml.Click += EventHandler(self._pick_xml)

        hint = Label()
        hint.Text      = u'Motor interno = escaneo geom\u00e9trico en Revit.\nCargar XML = reporte de clash detection de Navisworks.'
        hint.Font      = Font('Segoe UI', 7, FontStyle.Italic)
        hint.ForeColor = C_TEXT_MUTED
        hint.TextAlign = ContentAlignment.MiddleCenter
        hint.AutoSize  = False
        hint.Location  = Point(10, 130)
        hint.Size      = Size(340, 30)
        self.Controls.Add(hint)

    def _pick_engine(self, sender, args):
        self.mode = 'engine'
        self.Close()

    def _pick_xml(self, sender, args):
        self.mode = 'xml'
        self.Close()


# ─── Form principal Responsive ───────────────────────────────────────────────
class ClashManagerForm(Form):
    def __init__(self, uidoc, state, handler, external_event, logger):
        Form.__init__(self)
        self.uidoc            = uidoc
        self.state            = state
        self.handler          = handler
        self.external_event   = external_event
        self.logger           = logger
        self.include_links    = True
        self.auto_scan        = False
        self._xml_mode_ui     = False   # True => se muestran GUARDAR XML / MARCAR PUNTO
        self._active_filters  = set()
        self._is_horizontal   = False
        self.source_mode      = None   # 'engine' | 'xml' — se define en _prompt_source_mode
        self._source_asked    = False

        self.Text            = 'BIM Conflict Manager'
        self.Width           = 440
        self.Height          = 900
        self.MinimumSize     = Size(400, 600)
        self.BackColor       = C_BG_MAIN

        self._build_ui()
        self.Resize      += EventHandler(self._on_resize)
        self.Load        += EventHandler(self._on_load)
        self.FormClosed  += FormClosedEventHandler(self._on_form_closed)

    def _build_ui(self):
        # Top Container
        self.pnl_top = Panel()
        self.pnl_top.Dock = DockStyle.Top
        self.pnl_top.BackColor = C_WHITE
        self.Controls.Add(self.pnl_top)

        self.lbl_title = Label()
        self.lbl_title.Text = 'Conflict Manager'
        self.lbl_title.Font = Font('Segoe UI', 14, FontStyle.Bold)
        self.lbl_title.ForeColor = Color.FromArgb(13, 71, 161)
        self.lbl_title.AutoSize = True
        self.pnl_top.Controls.Add(self.lbl_title)

        self.chk_linked = CheckBox()
        self.chk_linked.Text = 'Linked Models'
        self.chk_linked.Checked = True
        self.chk_linked.AutoSize = True
        self.chk_linked.CheckedChanged += EventHandler(self._toggle_links)
        self.pnl_top.Controls.Add(self.chk_linked)

        self.chk_live = CheckBox()
        self.chk_live.Text = 'Live Updates'
        self.chk_live.AutoSize = True
        self.chk_live.CheckedChanged += EventHandler(self._toggle_auto)
        self.pnl_top.Controls.Add(self.chk_live)

        self.lbl_max = Label()
        self.lbl_max.Text = 'Max Incidents:'
        self.lbl_max.AutoSize = True
        self.pnl_top.Controls.Add(self.lbl_max)

        self.spin_max = NumericUpDown()
        self.spin_max.Minimum = 10
        self.spin_max.Maximum = 10000
        self.spin_max.Value = 100
        self.spin_max.Size = Size(60, 20)
        self.pnl_top.Controls.Add(self.spin_max)

        self.pnl_top_sep = Panel()
        self.pnl_top_sep.BackColor = C_DIVIDER
        self.pnl_top_sep.Height = 1
        self.pnl_top.Controls.Add(self.pnl_top_sep)

        # Filters
        self.filters = {}
        self.badges = {}
        filter_defs = [('All', 'All', C_TEXT_MAIN), ('New', 'New', C_NEW), ('Active', 'Active', C_ACTIVE), 
                       ('Reviewed', 'Reviewed', C_REVIEWED), ('Approved', 'Approved', C_APPROVED), ('Resolved', 'Resolved', C_RESOLVED)]
        
        for k, text, color in filter_defs:
            b = _flat_btn(text, (0, 0), (60, 24), C_WHITE, self.pnl_top, fg=C_TEXT_MAIN)
            b.Click += EventHandler(self._toggle_filter)
            self.filters[k] = b
            _make_rounded(b, radius=12, draw_border=True)
            
            badge = Label()
            badge.AutoSize = False
            badge.TextAlign = ContentAlignment.MiddleCenter
            badge.Font = Font("Segoe UI", 7, FontStyle.Bold)
            badge.BackColor = Color.FromArgb(230, 230, 230)
            badge.ForeColor = Color.Gray
            badge.Click += EventHandler(self._toggle_filter)
            b.Controls.Add(badge)
            _make_rounded(badge, radius=3, draw_border=False)
            self.badges[k] = badge

        # Bottom Actions
        self.pnl_bottom = Panel()
        self.pnl_bottom.Dock = DockStyle.Bottom
        self.pnl_bottom.Height = 50
        self.pnl_bottom.BackColor = C_WHITE
        self.Controls.Add(self.pnl_bottom)

        self.btn_scan = _flat_btn('SCAN CONFLICT', (10, 10), (120, 30), C_WHITE, self.pnl_bottom, fg=C_TEXT_MAIN)
        self.btn_scan.FlatAppearance.BorderColor = Color.FromArgb(200, 200, 200)
        self.btn_scan.FlatAppearance.BorderSize = 1
        self.btn_scan.Click += EventHandler(self._scan_click)

        # Botón para importar reporte XML de Navisworks (alternativa al motor)
        self.btn_xml = _flat_btn('CARGAR XML', (0, 10), (120, 30), C_WHITE, self.pnl_bottom, fg=C_TEXT_MAIN)
        self.btn_xml.FlatAppearance.BorderColor = Color.FromArgb(200, 200, 200)
        self.btn_xml.FlatAppearance.BorderSize = 1
        self.btn_xml.Click += EventHandler(self._import_xml_click)

        # Botón Verde de Approved
        self.btn_approve = _flat_btn('MARK AS APPROVED', (140, 10), (140, 30), Color.FromArgb(22, 163, 74), self.pnl_bottom, fg=Color.White)
        self.btn_approve.Click += EventHandler(self._approve_click)
        
        # Botón de Reviewed
        self.btn_review = _flat_btn('MARK AS REVIEWED', (290, 10), (140, 30), C_REVIEWED, self.pnl_bottom, fg=Color.White)
        self.btn_review.Click += EventHandler(self._review_click)

        # Botón "Guardar XML" — escribe los statuses actuales de vuelta al
        # Navisworks XML original. Solo aplica y solo es visible cuando el
        # origen de los conflictos es un XML (source_mode == 'xml').
        self.btn_save_xml = _flat_btn('GUARDAR XML', (440, 10), (140, 30), Color.FromArgb(99, 102, 241), self.pnl_bottom, fg=Color.White)
        self.btn_save_xml.Click += EventHandler(self._save_xml_click)
        self.btn_save_xml.Visible = False
        self.btn_save_xml.Enabled = False

        # Botón "Marcar punto" — crea una esfera temporal en la coordenada exacta
        # del conflicto (clashpoint del XML). Solo visible en modo XML.
        self.btn_point = _flat_btn('MARCAR PUNTO', (590, 10), (140, 30), Color.FromArgb(220, 38, 38), self.pnl_bottom, fg=Color.White)
        self.btn_point.Click += EventHandler(self._mark_point_click)
        self.btn_point.Visible = False
        
        self.lbl_multisel = Label()
        self.lbl_multisel.Text = "Ctrl+Click / Shift+Click para multi-sel"
        self.lbl_multisel.Font = Font("Segoe UI", 8, FontStyle.Italic)
        self.lbl_multisel.ForeColor = Color.Gray
        self.lbl_multisel.AutoSize = True
        self.pnl_bottom.Controls.Add(self.lbl_multisel)

        # Splitter
        self.split = SplitContainer()
        self.split.Dock = DockStyle.Fill
        self.split.Orientation = Orientation.Horizontal
        self.split.BackColor = C_DIVIDER
        self.split.Panel1MinSize = 100
        self.split.Panel2MinSize = 100
        self.Controls.Add(self.split)

        # DataGridView for Horizontal
        self.grid = DataGridView()
        self.grid.Dock = DockStyle.Fill
        self.grid.AutoGenerateColumns = False
        self.grid.AllowUserToAddRows = False
        self.grid.ReadOnly = True
        self.grid.SelectionMode = DataGridViewSelectionMode.FullRowSelect
        self.grid.MultiSelect = True
        self.grid.RowHeadersVisible = False
        self.grid.BackgroundColor = C_LIST_BG
        self.grid.BorderStyle = getattr(BorderStyle, 'None')
        self.grid.CellBorderStyle = getattr(DataGridViewCellBorderStyle, 'SingleHorizontal')
        self.grid.GridColor = Color.FromArgb(235, 235, 235)
        self.grid.RowTemplate.Height = 36
        self.grid.EnableHeadersVisualStyles = False
        self.grid.ColumnHeadersBorderStyle = getattr(DataGridViewHeaderBorderStyle, 'Single')
        self.grid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(248, 250, 252)
        self.grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = Color.FromArgb(248, 250, 252)
        self.grid.ColumnHeadersDefaultCellStyle.SelectionForeColor = C_TEXT_MAIN

        self.grid.DefaultCellStyle.Font = Font('Segoe UI', 8, FontStyle.Regular)
        self.grid.ColumnHeadersDefaultCellStyle.Font = Font('Segoe UI', 8, FontStyle.Bold)
        self.grid.DefaultCellStyle.ForeColor = C_TEXT_MAIN
        self.grid.DefaultCellStyle.SelectionBackColor = Color.FromArgb(240, 247, 255)
        self.grid.DefaultCellStyle.SelectionForeColor = C_TEXT_MAIN
        
        self.grid.CellPainting += DataGridViewCellPaintingEventHandler(self._grid_cell_painting)

        
        col_id = DataGridViewTextBoxColumn()
        col_id.HeaderText = "CONFLICT ID"
        col_id.Width = 180
        
        col_desc = DataGridViewTextBoxColumn()
        col_desc.HeaderText = "DESCRIPTION"
        col_desc.AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill
        
        col_status = DataGridViewTextBoxColumn()
        col_status.HeaderText = "STATUS"
        col_status.Width = 100
        
        col_vol = DataGridViewTextBoxColumn()
        col_vol.HeaderText = "VOLUME (ft3)"
        col_vol.Width = 100
        col_vol.ValueType = Double
        
        self.grid.Columns.Add(col_id)
        self.grid.Columns.Add(col_desc)
        self.grid.Columns.Add(col_vol)
        self.grid.Columns.Add(col_status)
        self.grid.SelectionChanged += EventHandler(self._on_grid_selection_changed)

        # ListBox for Vertical
        self.listbox = ClashListBox()
        self.listbox.Dock = DockStyle.Fill
        self.listbox.SelectedIndexChanged += EventHandler(self._on_selection_changed)

        self.split.Panel1.Controls.Add(self.grid)
        self.split.Panel1.Controls.Add(self.listbox)

        # Detail Panel
        self.detail_panel = ConflictDetailPanel()
        self.detail_panel.Dock = DockStyle.Fill
        self.detail_panel._on_select = self._select_element
        self.detail_panel._on_select_only = self._select_element_only
        self.detail_panel._on_section_box = self._section_box_element
        self.detail_panel._on_isolate = self._isolate_element
        self.detail_panel._uidoc = self.uidoc
        self.split.Panel2.Controls.Add(self.detail_panel)

        self.Controls.SetChildIndex(self.split, 0)
        self.Controls.SetChildIndex(self.pnl_top, 1)
        self.Controls.SetChildIndex(self.pnl_bottom, 2)

    def _update_filter_texts(self):
        counts = self.state.summary()
        for k in ['All', 'New', 'Active', 'Reviewed', 'Approved', 'Resolved']:
            btn = self.filters[k]
            badge = self.badges.get(k)
            val = counts.get('Total', 0) if k == 'All' else counts.get(k, 0)
            if getattr(self, '_is_horizontal', False):
                btn.Text = "  " + k
                btn.TextAlign = ContentAlignment.MiddleLeft
                if badge:
                    badge.Visible = True
                    val_str = str(val)
                    badge.Text = val_str
                    # Ancho dinámico basado en la cantidad de caracteres
                    bw = max(24, 12 + len(val_str) * 6)
                    bh = 16
                    badge.Size = Size(bw, bh)
                    badge.Location = Point(btn.Width - bw - 6, (btn.Height - bh) // 2)
            else:
                btn.Text = "%s\n(%d)" % (k, val)
                btn.TextAlign = ContentAlignment.MiddleCenter
                if badge:
                    badge.Visible = False

    def _toggle_filter(self, sender, args):
        k = None
        for key, b in self.filters.items():
            if b == sender or self.badges.get(key) == sender:
                k = key
                break
        if k:
            if k == 'All':
                self._active_filters.clear()
            else:
                if k in self._active_filters:
                    self._active_filters.remove(k)
                else:
                    self._active_filters.add(k)
            self._update_filter_buttons()
            self._refresh_list()

    def _update_filter_buttons(self):
        for k, btn in self.filters.items():
            badge = self.badges.get(k)
            is_horiz = getattr(self, '_is_horizontal', False)
            
            if k == 'All' and not self._active_filters:
                if is_horiz:
                    btn.BackColor = Color.FromArgb(219, 234, 254)
                    btn.FlatAppearance.BorderColor = Color.FromArgb(59, 130, 246)
                    btn.ForeColor = C_TEXT_MAIN
                else:
                    btn.BackColor = C_WHITE
                    btn.FlatAppearance.BorderColor = Color.FromArgb(156, 163, 175)
                    btn.ForeColor = C_TEXT_MAIN
                if badge:
                    badge.BackColor = Color.FromArgb(191, 219, 254)
                    badge.ForeColor = Color.FromArgb(30, 64, 175)
            elif k in self._active_filters:
                c = FILTER_COLORS.get(k, C_DIVIDER)
                if is_horiz:
                    btn.BackColor = c
                    btn.ForeColor = Color.White if c in (C_ACTIVE, C_RESOLVED) else C_TEXT_MAIN
                else:
                    # En modo vertical, bg es suave y el texto es el color base
                    # ACTIVE rojo, etc. Usamos un bg muy suave
                    btn.BackColor = Color.FromArgb(min(255, c.R + 45), min(255, c.G + 45), min(255, c.B + 45))
                    btn.ForeColor = Color.FromArgb(max(0, c.R - 40), max(0, c.G - 40), max(0, c.B - 40))
                
                btn.FlatAppearance.BorderColor = c
                if badge:
                    if c in (C_ACTIVE, C_RESOLVED):
                        badge.BackColor = Color.FromArgb(max(0, c.R - 40), max(0, c.G - 40), max(0, c.B - 40))
                        badge.ForeColor = Color.White
                    else:
                        badge.BackColor = Color.FromArgb(min(255, c.R + 40), min(255, c.G + 40), min(255, c.B + 40))
                        badge.ForeColor = C_TEXT_MAIN
            else:
                btn.BackColor = C_WHITE
                btn.ForeColor = Color.FromArgb(107, 114, 128)
                btn.FlatAppearance.BorderColor = Color.FromArgb(209, 213, 219) # gris claro
                if badge:
                    badge.BackColor = Color.FromArgb(230, 230, 230)
                    badge.ForeColor = Color.Gray

    def _on_resize(self, sender, args):
        w = self.Width
        self._is_horizontal = w >= 800

        self.grid.Visible = self._is_horizontal
        self.listbox.Visible = not self._is_horizontal
        
        if self._is_horizontal:
            self.grid.BringToFront()
        else:
            self.listbox.BringToFront()

        if self._is_horizontal:
            self.pnl_top.Height = 80
            self.lbl_title.AutoSize = True
            self.lbl_title.TextAlign = getattr(ContentAlignment, 'MiddleLeft', ContentAlignment.TopLeft)
            self.lbl_title.Location = Point(10, 10)
            
            self.chk_linked.Text = 'Linked Models'
            self.chk_live.Text = 'Live Updates'
            self.lbl_max.Text = 'Max Incidents:'
            
            self.btn_scan.Text = u'\u25A3 SCAN CONFLICT'
            self.btn_approve.Text = u'\u2714 MARK AS APPROVED'
            self.btn_review.Text = u'\u270E MARK AS REVIEWED'
            
            y2 = 45
            self.chk_linked.Location = Point(10, y2)
            self.chk_live.Location = Point(self.chk_linked.Right + 10, y2)
            self.lbl_max.Location = Point(self.chk_live.Right + 10, y2+2)
            self.spin_max.Location = Point(self.lbl_max.Right + 5, y2)
            
            self.pnl_top_sep.Visible = False
            
            fx = self.spin_max.Right + 20
            for k in ['All', 'New', 'Active', 'Reviewed', 'Approved', 'Resolved']:
                b = self.filters[k]
                b.Size = Size(105, 26)
                b.Location = Point(fx, y2 - 2)
                b.Font = Font('Segoe UI', 8, FontStyle.Regular)
                fx += b.Width + 5
            
            # Ahora que los botones tienen tamaño, actualizar badges
            self._update_filter_texts()
                
            self.btn_xml.Text = u'\u2913 CARGAR XML'
            self.btn_save_xml.Text = u'\u2913 GUARDAR XML'
            self.btn_point.Text = u'\u25CF MARCAR PUNTO'
            self._layout_bottom_buttons(horizontal=True)
        else:
            self.pnl_top.Height = 150
            
            self.lbl_title.AutoSize = False
            self.lbl_title.Size = Size(w, 30)
            self.lbl_title.Location = Point(0, 8)
            self.lbl_title.TextAlign = ContentAlignment.MiddleCenter
            
            self.chk_linked.Text = 'Linked'
            self.chk_live.Text = 'Live'
            self.lbl_max.Text = u'M\xe1x:'
            
            y_chk = 38
            self.chk_linked.Location = Point(10, y_chk)
            self.chk_live.Location = Point(self.chk_linked.Right + 10, y_chk)
            
            self.spin_max.Location = Point(w - self.spin_max.Width - 15, y_chk)
            self.lbl_max.Location = Point(self.spin_max.Left - self.lbl_max.Width - 5, y_chk+2)
            
            self.pnl_top_sep.Visible = True
            self.pnl_top_sep.Location = Point(10, 65)
            self.pnl_top_sep.Width = w - 20
            
            y_btn = 73
            btn_w = (w - 20 - 10) // 3
            
            fx = 10
            keys = ['All', 'New', 'Active', 'Reviewed', 'Approved', 'Resolved']
            for i, k in enumerate(keys):
                b = self.filters[k]
                b.Size = Size(btn_w, 32)
                row = i // 3
                col = i % 3
                b.Location = Point(10 + col * (btn_w + 5), y_btn + row * 37)
                b.Font = Font('Segoe UI', 7, FontStyle.Regular)
            
            self._update_filter_texts()
            
            self.btn_scan.Text = u'\u25A3 SCAN'
            self.btn_approve.Text = u'\u2714 APPROVE'
            self.btn_review.Text = u'\u270E REVIEWED'
            self.btn_xml.Text = u'\u2913 XML'
            self.btn_save_xml.Text = u'\u2913 GUARDAR'
            self.btn_point.Text = u'\u25CF PUNTO'
            self._layout_bottom_buttons(horizontal=False)

    def _layout_bottom_buttons(self, horizontal):
        """
        Acomoda los botones del panel inferior sin que se salgan del ancho:
          - Fila de "origen": SCAN, CARGAR XML y (solo modo XML) GUARDAR XML, MARCAR PUNTO.
          - Fila de "estado": REVIEWED, APPROVED.
        Horizontal ancho: todo en una sola fila alineada a la derecha (si cabe junto
        al texto de multi-selección). Si no cabe, o en vista vertical, se parte en
        filas y el panel crece en alto.
        """
        pad, gap, h = 10, 6, 30
        cw = self.ClientSize.Width
        avail = cw - 2 * pad
        xml_ui = getattr(self, '_xml_mode_ui', False)

        src = [self.btn_scan, self.btn_xml]
        if xml_ui:
            src += [self.btn_save_xml, self.btn_point]
        status = [self.btn_review, self.btn_approve]

        # ── Una sola fila (solo horizontal, si cabe) ───────────────────────────
        if horizontal:
            widths = {}
            for b in src + status:
                widths[b] = 160 if b in status else 140
            row_order = src + status
            total = sum(widths[b] for b in row_order) + gap * (len(row_order) - 1)
            label_w = 270   # espacio para "Ctrl+Click / Shift+Click para multi-sel"
            if pad + label_w + total <= cw - pad:
                x = cw - pad - total
                for b in row_order:
                    b.Size = Size(widths[b], h)
                    b.Location = Point(x, 10)
                    x += widths[b] + gap
                self.lbl_multisel.Visible = True
                self.lbl_multisel.Location = Point(10, 18)
                self.pnl_bottom.Height = 50
                return

        # ── Filas que se ajustan al ancho ──────────────────────────────────────
        self.lbl_multisel.Visible = False
        min_w = 100
        max_w = 170 if horizontal else None
        max_cols = max(1, (avail + gap) // (min_w + gap))
        y = 10
        for group in (src, status):
            n = len(group)
            rows = (n + max_cols - 1) // max_cols
            per_row = (n + rows - 1) // rows
            for r in range(rows):
                chunk = group[r * per_row:(r + 1) * per_row]
                bw = (avail - (len(chunk) - 1) * gap) // len(chunk)
                if max_w is not None:
                    bw = min(bw, max_w)
                for i, b in enumerate(chunk):
                    b.Size = Size(bw, h)
                    b.Location = Point(pad + i * (bw + gap), y)
                y += h + 6
        self.pnl_bottom.Height = max(50, y + 4)

    def _selected_record(self):
        if self._is_horizontal:
            if self.grid.SelectedRows.Count > 0:
                return self.grid.SelectedRows[0].Tag
        else:
            if self.listbox.SelectedIndex >= 0:
                return self.listbox.Items[self.listbox.SelectedIndex]
        return None

    def _selected_records(self):
        if self._is_horizontal:
            return [row.Tag for row in self.grid.SelectedRows]
        else:
            return [item for item in self.listbox.SelectedItems]

    def _get_filtered_records(self):
        return self.state.filtered_records(self._active_filters)

    def _refresh_list(self, records=None, preserve_scroll=False):
        if records is None:
            records = self._get_filtered_records()

        selected_keys = {r.key for r in self._selected_records()}

        # Guardar posición de scroll antes de reconstruir
        saved_top_listbox = self.listbox.TopIndex if preserve_scroll else 0
        saved_top_grid    = self.grid.FirstDisplayedScrollingRowIndex if (preserve_scroll and self.grid.RowCount > 0) else 0

        # Guardar ordenamiento actual
        sort_col = self.grid.SortedColumn
        sort_order = self.grid.SortOrder

        self.grid.SuspendLayout()
        self.grid.Rows.Clear()
        for r in records:
            idx = self.grid.Rows.Add()
            row = self.grid.Rows[idx]
            row.Cells[0].Value = "#%s vs #%s" % (r.source_id, r.target_id)
            row.Cells[1].Value = "%s x %s" % (r.source_name, r.target_name)
            row.Cells[2].Value = float(round(r.volume, 4))
            row.Cells[3].Value = r.status.upper()
            row.Tag = r
            if r.key in selected_keys:
                row.Selected = True
                
        # Restaurar ordenamiento
        if sort_col is not None and sort_order != getattr(SortOrder, 'None'):
            direction = ListSortDirection.Ascending if sort_order == SortOrder.Ascending else ListSortDirection.Descending
            try:
                self.grid.Sort(sort_col, direction)
            except Exception:
                pass
                
        self.grid.ResumeLayout()

        self.listbox.BeginUpdate()
        self.listbox.Items.Clear()
        if records:
            from System import Array
            arr = Array[object](records)
            self.listbox.Items.AddRange(arr)
        for i in range(self.listbox.Items.Count):
            if self.listbox.Items[i].key in selected_keys:
                    self.listbox.SetSelected(i, True)
        self.listbox.EndUpdate()

        # Restaurar posición de scroll
        if preserve_scroll:
            try:
                if saved_top_listbox > 0 and self.listbox.Items.Count > saved_top_listbox:
                    self.listbox.TopIndex = saved_top_listbox
            except Exception:
                pass
            try:
                if saved_top_grid > 0 and self.grid.RowCount > saved_top_grid:
                    self.grid.FirstDisplayedScrollingRowIndex = saved_top_grid
            except Exception:
                pass

        self._update_filter_texts()

    def _grid_cell_painting(self, sender, e):
        if e.RowIndex < 0:
            return

        is_selected = self.grid.Rows[e.RowIndex].Selected

        if e.ColumnIndex == 0:
            e.PaintBackground(e.ClipBounds, True)
            if is_selected:
                blue_brush = SolidBrush(Color.FromArgb(14, 165, 233))
                e.Graphics.FillRectangle(blue_brush, e.CellBounds.X, e.CellBounds.Y, 4, e.CellBounds.Height)
                blue_brush.Dispose()
            
            text = str(e.Value) if e.Value else ""
            if text:
                sf = StringFormat()
                sf.Alignment = StringAlignment.Near
                sf.LineAlignment = StringAlignment.Center
                
                rect = Rectangle(e.CellBounds.X + 10, e.CellBounds.Y, e.CellBounds.Width - 10, e.CellBounds.Height)
                
                if is_selected:
                    font = Font("Segoe UI", 9, FontStyle.Bold)
                    fg_brush = SolidBrush(Color.FromArgb(14, 165, 233))
                else:
                    font = Font("Segoe UI", 8, FontStyle.Bold)
                    fg_brush = SolidBrush(Color.FromArgb(100, 116, 139))
                    
                e.Graphics.DrawString(text, font, fg_brush, rect, sf)
                font.Dispose()
                fg_brush.Dispose()
            e.Handled = True

        elif e.ColumnIndex == 3:
            e.PaintBackground(e.ClipBounds, True)
            status = str(e.Value) if e.Value else ""
            if status:
                if status == 'ACTIVE':
                    bg_color = Color.FromArgb(254, 226, 226)
                    fg_color = Color.FromArgb(185, 28, 28)
                elif status == 'RESOLVED':
                    bg_color = Color.FromArgb(220, 252, 231)
                    fg_color = Color.FromArgb(21, 128, 61)
                elif status == 'REVIEWED':
                    bg_color = Color.FromArgb(226, 232, 240)
                    fg_color = Color.FromArgb(71, 85, 105)
                elif status == 'NEW':
                    bg_color = Color.FromArgb(241, 245, 249)
                    fg_color = Color.FromArgb(51, 65, 85)
                else:
                    bg_color = Color.FromArgb(243, 244, 246)
                    fg_color = Color.FromArgb(75, 85, 99)
                
                rect = Rectangle(e.CellBounds.X + 8, e.CellBounds.Y + 6, e.CellBounds.Width - 16, e.CellBounds.Height - 12)
                radius = 3
                path = GraphicsPath()
                path.AddArc(rect.X, rect.Y, radius, radius, 180, 90)
                path.AddArc(rect.Right - radius, rect.Y, radius, radius, 270, 90)
                path.AddArc(rect.Right - radius, rect.Bottom - radius, radius, radius, 0, 90)
                path.AddArc(rect.X, rect.Bottom - radius, radius, radius, 90, 90)
                path.CloseFigure()
                
                e.Graphics.SmoothingMode = SmoothingMode.AntiAlias
                bg_brush = SolidBrush(bg_color)
                e.Graphics.FillPath(bg_brush, path)
                
                sf = StringFormat()
                sf.Alignment = StringAlignment.Center
                sf.LineAlignment = StringAlignment.Center
                font = Font("Segoe UI", 7, FontStyle.Bold)
                fg_brush = SolidBrush(fg_color)
                e.Graphics.DrawString(status, font, fg_brush, rect, sf)
                
                bg_brush.Dispose()
                fg_brush.Dispose()
                path.Dispose()
                font.Dispose()
            e.Handled = True

    def request_scan(self):
        try:
            self.handler.max_results = int(self.spin_max.Value)
            if self.handler.request_scan(self.include_links):
                self.btn_scan.Enabled = False
                self.external_event.Raise()
        except Exception as err:
            MessageBox.Show(str(err))

    def _on_scan_finished(self):
        self.btn_scan.Enabled = True
        self.btn_xml.Enabled = True
        # "Guardar XML" solo se habilita si estamos en modo XML y ya hay
        # un import exitoso del que tomar la ruta de origen.
        if self.source_mode == 'xml' and self.handler.last_xml_path:
            self.btn_save_xml.Enabled = True
        else:
            self.btn_save_xml.Enabled = False

    def apply_records(self, records):
        if self.InvokeRequired:
            self.BeginInvoke(MethodInvoker(lambda: self._apply_pending_records(records)))
        else:
            self._apply_pending_records(records)

    def _apply_pending_records(self, records):
        self._update_filter_buttons()
        self._refresh_list()

    def _update_tool_button_states(self):
        """Refleja en los botones del panel de detalle el estado real de isolate y section box."""
        try:
            st_iso  = self.handler._isolate_state
            st_sec  = self.handler._section_state
            record  = self._selected_record()

            iso_on = (
                st_iso is not None
                and record is not None
                and st_iso.get('key') == record.key
            )
            sec_on = (
                st_sec is not None
                and record is not None
                and st_sec.get('key') == record.key
            )
            self.detail_panel.update_tool_buttons(
                isolate_active=iso_on,
                section_active=sec_on,
            )
        except Exception:
            pass

    def _on_selection_changed(self, sender, args):
        record = self._selected_record()
        if record:
            self._select_element(record, 'source')
            if hasattr(self, 'detail_panel') and not self._is_horizontal:
                self.detail_panel.load_record(record)
            self._update_tool_button_states()

    def _on_grid_selection_changed(self, sender, args):
        record = self._selected_record()
        if record:
            self._select_element(record, 'source')
            if hasattr(self, 'detail_panel') and self._is_horizontal:
                self.detail_panel.load_record(record)
            self._update_tool_button_states()

    def _scan_click(self, sender, args):
        self.request_scan()

    def _import_xml_click(self, sender, args):
        dlg = OpenFileDialog()
        dlg.Filter = 'Navisworks Clash XML (*.xml)|*.xml|All files (*.*)|*.*'
        dlg.Title = 'Seleccionar reporte XML de clash detection'
        if dlg.ShowDialog() == DialogResult.OK:
            try:
                if self.handler.request_xml_import(dlg.FileName):
                    self.btn_xml.Enabled = False
                    self.btn_scan.Enabled = False
                    self.external_event.Raise()
            except Exception as err:
                MessageBox.Show(str(err))

    def _save_xml_click(self, sender, args):
        try:
            if self.handler.request_save_xml():
                self.btn_save_xml.Enabled = False
                self.btn_xml.Enabled = False
                self.external_event.Raise()
        except Exception as err:
            MessageBox.Show(str(err))

    def _mark_point_click(self, sender, args):
        record = self._selected_record()
        if record is None:
            MessageBox.Show(u'Selecciona un conflicto en la tabla.')
            return
        self.handler.request_mark_point(record)
        self.external_event.Raise()

    def show_error(self, message):
        def _show():
            MessageBox.Show(message)
        if self.InvokeRequired:
            self.BeginInvoke(MethodInvoker(_show))
        else:
            _show()

    def _toggle_links(self, sender, args):
        self.include_links = self.chk_linked.Checked
        self.request_scan()

    def _toggle_auto(self, sender, args):
        self.auto_scan = self.chk_live.Checked

    def _select_element(self, record, target):
        self.handler.request_select(record, target)
        self.external_event.Raise()

    def _section_box_element(self, record):
        self.handler.request_section_box(record)
        self.external_event.Raise()
        # Refrescar el estado visual del botón después de que la acción se ejecute
        self.BeginInvoke(MethodInvoker(self._update_tool_button_states))

    def _isolate_element(self, record):
        self.handler.request_isolate(record)
        self.external_event.Raise()
        # Refrescar el estado visual del botón después de que la acción se ejecute
        self.BeginInvoke(MethodInvoker(self._update_tool_button_states))

    def _select_element_only(self, record, target):
        self.handler.request_select_only(record, target)
        self.external_event.Raise()

    def _review_click(self, sender, args):
        recs = self._selected_records()
        if recs:
            self.state.set_status_bulk([r.key for r in recs], ClashStatus.REVIEWED)
            self._refresh_and_advance()

    def _approve_click(self, sender, args):
        recs = self._selected_records()
        if recs:
            self.state.set_status_bulk([r.key for r in recs], ClashStatus.APPROVED)
            self._refresh_and_advance()

    def _resolve_click(self, sender, args):
        recs = self._selected_records()
        if recs:
            self.state.set_status_bulk([r.key for r in recs], ClashStatus.RESOLVED)
            self._refresh_and_advance()

    def _refresh_and_advance(self):
        """Refresca la lista y selecciona automaticamente el siguiente elemento
        en la posicion donde estaba la seleccion anterior."""
        # Capturar indice actual antes de refrescar
        next_idx = -1
        if self._is_horizontal:
            if self.grid.SelectedRows.Count > 0:
                indices = sorted([row.Index for row in self.grid.SelectedRows])
                next_idx = indices[0]  # primer indice seleccionado
        else:
            selected_indices = list(self.listbox.SelectedIndices)
            if selected_indices:
                next_idx = min(selected_indices)  # primer indice seleccionado

        # Refrescar (sin restaurar scroll automaticamente, lo hacemos aqui)
        saved_top_listbox = self.listbox.TopIndex
        saved_top_grid    = self.grid.FirstDisplayedScrollingRowIndex if self.grid.RowCount > 0 else 0

        self._refresh_list(preserve_scroll=False)

        # Seleccionar el siguiente elemento en la misma posicion de la lista
        if next_idx >= 0:
            if self._is_horizontal:
                count = self.grid.RowCount
                if count > 0:
                    target = min(next_idx, count - 1)
                    try:
                        self.grid.ClearSelection()
                        self.grid.Rows[target].Selected = True
                        self.grid.FirstDisplayedScrollingRowIndex = max(0, target - 2)
                    except Exception:
                        pass
            else:
                count = self.listbox.Items.Count
                if count > 0:
                    target = min(next_idx, count - 1)
                    try:
                        self.listbox.ClearSelected()
                        self.listbox.SetSelected(target, True)
                        # Mantener el scroll para que el item seleccionado sea visible
                        top = max(0, target - 2)
                        self.listbox.TopIndex = top
                    except Exception:
                        pass
        else:
            # Sin seleccion previa, restaurar scroll como antes
            try:
                if self.listbox.Items.Count > saved_top_listbox:
                    self.listbox.TopIndex = saved_top_listbox
            except Exception:
                pass
            try:
                if self.grid.RowCount > saved_top_grid:
                    self.grid.FirstDisplayedScrollingRowIndex = saved_top_grid
            except Exception:
                pass

    def _on_load(self, sender, args):
        self._update_filter_buttons()
        self._on_resize(None, None)
        try:
            available = self.split.Height
            dist = max(self.split.Panel1MinSize, min(available - self.split.Panel2MinSize - self.split.SplitterWidth, int(available * 0.4)))
            self.split.SplitterDistance = dist
        except Exception:
            pass
        if not self._source_asked:
            self._source_asked = True
            self._prompt_source_mode()

    def _prompt_source_mode(self):
        dlg = SourceModeDialog()
        dlg.ShowDialog(self)
        self.source_mode = dlg.mode or 'engine'

        if self.source_mode == 'xml':
            # Bloqueamos lo que solo aplica al motor geometrico interno.
            self.btn_scan.Enabled  = False
            self.chk_linked.Enabled = False
            self.chk_live.Checked   = False
            self.chk_live.Enabled   = False
            self._xml_mode_ui = True
            self.btn_save_xml.Visible = True   # solo existe cuando el origen es XML
            self.btn_point.Visible    = True   # idem: el punto viene del XML
            self._on_resize(None, None)        # reacomoda los botones con los nuevos visibles
            self._import_xml_click(None, None)
        else:
            self.btn_xml.Enabled = False
            self._xml_mode_ui = False
            self.btn_save_xml.Visible = False
            self.btn_point.Visible = False
            self._on_resize(None, None)
            self.request_scan()

    def _on_form_closed(self, sender, args):
        pass

    def OnClosed(self, args):
        Form.OnClosed(self, args)
