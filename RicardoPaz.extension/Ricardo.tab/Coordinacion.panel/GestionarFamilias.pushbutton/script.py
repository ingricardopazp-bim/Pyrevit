#! python3
# -*- coding: utf-8 -*-
"""
Gestor de Familias y Tipos (todo el proyecto)
-----------------------------------------------
Permite revisar y editar, para TODAS las familias cargables del proyecto:
    - Nombre de Familia
    - Nombre de Tipo
    - Categoria a la que pertenece la familia

Entorno: pyRevit / IronPython 2.7 - Revit 2024/2025 (locale ES)
Autor: Ricardo (Ricardo.extension)

CAMBIOS EN ESTA VERSION
------------------------
- Se corrigio el cambio de categoria de familia. La asignacion directa
  "fam.FamilyCategory = nueva_categoria" sobre el elemento Family tal
  como esta cargado en el documento de PROYECTO no es un metodo
  soportado de forma fiable por la API: Revit puede "aceptarla" sin
  lanzar excepcion pero el cambio resulta inconsistente y no
  sobrevive a un recargo o uso real de la familia.

  El unico flujo soportado por la API es:
      1. doc.EditFamily(fam)                    -> documento de familia independiente
      2. familyDoc.OwnerFamily.FamilyCategory = nueva_categoria (Transaction en familyDoc)
      3. familyDoc.LoadFamily(doc, opciones)     -> recarga en el proyecto (Transaction en doc)
      4. familyDoc.Close(False)                  -> cierra sin guardar el .rfa temporal

  Ver la funcion recategorize_family() y la clase
  FamilyCategoryLoadOptions() mas abajo.
"""
__title__ = "Gestor de\nFamilias y Tipos"
__author__ = "Ricardo"
__doc__ = "Gestiona nombre de familia, nombre de tipo y categoria para todo el proyecto"

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')

from Autodesk.Revit.DB import (
    FilteredElementCollector, Family, FamilyInstance, Transaction,
    CategoryType, Element, IFamilyLoadOptions, FamilySource
)


def get_name(element):
    """Obtiene el nombre del elemento."""
    try:
        return element.Name
    except Exception:
        from Autodesk.Revit.DB import BuiltInParameter
        if hasattr(element, "get_Parameter"):
            param = element.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_NAME)
            if param:
                return param.AsString()
        return ""


def set_name(element, new_name):
    """Asigna el nombre del elemento."""
    try:
        element.Name = new_name
    except Exception as e:
        if logger:
            logger.error("Error al renombrar: " + str(e))

import System
from System.Windows.Forms import (
    Form, DataGridView, DataGridViewTextBoxColumn, DataGridViewComboBoxColumn, DataGridViewCheckBoxColumn,
    DataGridViewAutoSizeColumnsMode, DataGridViewSelectionMode, DockStyle,
    Button, TextBox, Label, MessageBox, MessageBoxButtons, MessageBoxIcon,
    FormStartPosition, DataGridViewContentAlignment, AnchorStyles,
    FlatStyle, DataGridViewCellStyle, ScrollBars, DataGridViewCellBorderStyle, Padding, BorderStyle, DataGridViewHeaderBorderStyle
)
from System.Drawing import Color, Font, FontStyle, Point, Size

from pyrevit import revit, script

doc = revit.doc
output = script.get_output()
logger = script.get_logger()

COLOR_BG = Color.FromArgb(246, 246, 248)
COLOR_HEADER = Color.FromArgb(33, 43, 54)
COLOR_ACCENT = Color.FromArgb(0, 120, 212)
COLOR_ERROR = Color.FromArgb(196, 43, 43)


# ------------------------------------------------------------------
# Recoleccion de datos
# ------------------------------------------------------------------
def get_valid_categories(doc):
    """Categorias de Modelo validas para recategorizar familias cargables."""
    cats = []
    for cat in doc.Settings.Categories:
        try:
            if cat.CategoryType == CategoryType.Model:
                cats.append(cat)
        except Exception:
            pass
    cats.sort(key=lambda c: c.Name)
    return cats


def collect_family_type_rows(doc):
    """Devuelve una fila por cada (familia, tipo) del proyecto completo."""
    families = FilteredElementCollector(doc).OfClass(Family).ToElements()

    # Conteo de instancias colocadas, por Id de tipo (una sola pasada)
    counts = {}
    instances = FilteredElementCollector(doc).OfClass(FamilyInstance).ToElements()
    for inst in instances:
        try:
            tid = inst.GetTypeId()
            counts[tid] = counts.get(tid, 0) + 1
        except Exception:
            pass

    # Conteo de tipos e instancias totales por familia
    type_counts = {}
    family_instances = {}
    for fam in families:
        try:
            sids = fam.GetFamilySymbolIds()
            type_counts[fam.Id] = len(sids)
            fam_inst = sum([counts.get(sid, 0) for sid in sids])
            family_instances[fam.Id] = fam_inst
        except Exception:
            type_counts[fam.Id] = 0
            family_instances[fam.Id] = 0

    rows = []
    for fam in families:
        cat = fam.FamilyCategory
        cat_name = cat.Name if cat else "Sin categoria"
        try:
            symbol_ids = fam.GetFamilySymbolIds()
        except Exception:
            symbol_ids = []
        for sid in symbol_ids:
            sym = doc.GetElement(sid)
            if sym is None:
                continue
            fam_name = get_name(fam)
            type_name = get_name(sym)
            try:
                is_inplace = fam.IsInPlace
            except Exception:
                is_inplace = False
            rows.append({
                'family_id': fam.Id,
                'family_name': fam_name,
                'type_id': sid,
                'type_name': type_name,
                'category': cat_name,
                'orig_family_name': fam_name,
                'orig_type_name': type_name,
                'orig_category': cat_name,
                'instances': counts.get(sid, 0),
                'is_inplace': is_inplace,
                'type_count': type_counts.get(fam.Id, 0),
                'family_instances': family_instances.get(fam.Id, 0)
            })

    rows.sort(key=lambda r: (-r['family_instances'], r['family_name'], r['type_name']))
    return rows


# ------------------------------------------------------------------
# Aplicacion de cambios (transacciones individuales -> fallas aisladas)
# ------------------------------------------------------------------
def rename_family(doc, family_id, new_name):
    t = Transaction(doc, "Renombrar familia")
    t.Start()
    try:
        fam = doc.GetElement(family_id)
        set_name(fam, new_name)
        t.Commit()
        return True, None
    except Exception as e:
        t.RollBack()
        return False, str(e)


# ------------------------------------------------------------------
# Opciones de carga para LoadFamily(): necesarias para que la familia
# recargada sobrescriba la version existente en el proyecto sin
# mostrar dialogos y conservando los valores de parametro actuales.
#
# IMPORTANTE (IronPython): los parametros "out" de C# llegan aqui como
# objetos con propiedad .Value. Asignar "= True" a secas (en vez de
# ".Value = True") es un error muy comun que hace que la opcion se
# ignore silenciosamente y Revit vuelva a preguntar o resetee valores.
# ------------------------------------------------------------------
class FamilyCategoryLoadOptions(IFamilyLoadOptions):
    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues.Value = True
        return True

    def OnSharedFamilyFound(self, sharedFamily, familyInUse, source, overwriteParameterValues):
        source.Value = FamilySource.Family
        overwriteParameterValues.Value = True
        return True


def recategorize_family(doc, family_id, new_category):
    """
    Cambia la categoria de una familia cargable mediante el UNICO flujo
    que la API soporta de forma fiable:

        1. doc.EditFamily(fam)                 -> documento de familia independiente
        2. familyDoc.OwnerFamily.FamilyCategory = new_category  (Transaction en familyDoc)
        3. familyDoc.LoadFamily(doc, opciones)  -> recarga en el proyecto (Transaction en doc)
        4. familyDoc.Close(False)               -> cierra sin guardar el .rfa temporal

    No todas las combinaciones origen/destino son validas: familias con
    comportamientos especiales (hosted, line-based, Structural Framing,
    etc.) pueden rechazar el cambio. En ese caso Revit lanza una
    excepcion con un mensaje descriptivo que se devuelve tal cual.
    """
    fam = doc.GetElement(family_id)

    if fam.IsInPlace:
        return False, "Familia in situ: la categoria no se puede cambiar por API."

    family_doc = None
    try:
        # 1. Abrir copia editable de la familia.
        #    doc.EditFamily() no puede llamarse con una transaccion
        #    abierta en doc, por eso NO debe invocarse esta funcion
        #    dentro de un Transaction(doc, ...) ya iniciado.
        family_doc = doc.EditFamily(fam)
        if family_doc is None or not family_doc.IsFamilyDocument:
            return False, "No se pudo abrir la familia para edicion (EditFamily devolvio None)."

        # 2. Cambiar la categoria DENTRO del documento de familia
        t1 = Transaction(family_doc, "Cambiar categoria de familia")
        t1.Start()
        try:
            family_doc.OwnerFamily.FamilyCategory = new_category
            t1.Commit()
        except Exception as e:
            t1.RollBack()
            family_doc.Close(False)
            return False, ("No se pudo asignar la categoria dentro del editor "
                            "de familias (posible incompatibilidad de "
                            "comportamiento, p.ej. hosted/line-based): {0}".format(e))

        # 3. Recargar la familia editada de vuelta al proyecto.
        #    IMPORTANTE: LoadFamily() maneja su propia transaccion interna
        #    sobre el documento destino. NO debe llamarse dentro de un
        #    Transaction(doc, ...) abierto por nosotros, o Revit lanza:
        #    "The document must not be modifiable before calling
        #    LoadFamily. Any open transaction must be closed prior
        #    the call."
        try:
            family_doc.LoadFamily(doc, FamilyCategoryLoadOptions())
        except Exception as e:
            family_doc.Close(False)
            return False, "Fallo al recargar la familia en el proyecto: {0}".format(e)

        # 4. Cerrar el documento temporal sin guardarlo en disco
        family_doc.Close(False)
        family_doc = None

        return True, None

    except Exception as e:
        if family_doc is not None:
            try:
                family_doc.Close(False)
            except Exception:
                pass
        return False, str(e)


def rename_type(doc, type_id, new_name):
    t = Transaction(doc, "Renombrar tipo")
    t.Start()
    try:
        sym = doc.GetElement(type_id)
        set_name(sym, new_name)
        t.Commit()
        return True, None
    except Exception as e:
        t.RollBack()
        return False, str(e)


# ------------------------------------------------------------------
# UI
# ------------------------------------------------------------------
class RoundedButton(Button):
    def __init__(self, text, back_color, fore_color=Color.White):
        Button.__init__(self)
        self.Text = text
        self.FlatStyle = FlatStyle.Flat
        self.FlatAppearance.BorderSize = 0
        self.BackColor = back_color
        self.ForeColor = fore_color
        self.Font = Font("Segoe UI", 9, FontStyle.Bold)
        self.Size = Size(150, 32)


class GestorFamiliasForm(Form):
    def __init__(self, doc):
        Form.__init__(self)
        self.doc = doc
        self.categories = get_valid_categories(doc)
        self.category_names = [c.Name for c in self.categories]
        self.category_by_name = dict((c.Name, c) for c in self.categories)
        self.all_rows = collect_family_type_rows(doc)
        self.visible_rows = list(self.all_rows)

        self.init_ui()
        self.load_grid()

    # -- construccion de controles ---------------------------------
    def init_ui(self):
        self.Text = "Gestor de Familias y Tipos - Todo el Proyecto"
        self.Size = Size(1180, 720)
        self.StartPosition = FormStartPosition.CenterScreen
        self.BackColor = COLOR_BG
        self.Font = Font("Segoe UI", 9)

        lbl_search = Label()
        lbl_search.Text = "Buscar (familia / tipo / categoria):"
        lbl_search.Location = Point(15, 15)
        lbl_search.Size = Size(230, 20)
        self.Controls.Add(lbl_search)

        self.txt_search = TextBox()
        self.txt_search.Location = Point(250, 12)
        self.txt_search.Size = Size(350, 24)
        self.txt_search.TextChanged += self.on_search
        self.Controls.Add(self.txt_search)

        self.lbl_count = Label()
        self.lbl_count.Location = Point(620, 15)
        self.lbl_count.Size = Size(200, 20)
        self.lbl_count.ForeColor = Color.FromArgb(90, 90, 90)
        self.Controls.Add(self.lbl_count)

        self.btn_delete = RoundedButton("Eliminar marcados", COLOR_ERROR)
        self.btn_delete.Location = Point(780, 10)
        self.btn_delete.Size = Size(140, 28)
        self.btn_delete.Click += self.on_delete_selected
        self.Controls.Add(self.btn_delete)

        self.btn_refresh = RoundedButton("Actualizar lista", Color.FromArgb(120, 120, 120))
        self.btn_refresh.Location = Point(930, 10)
        self.btn_refresh.Size = Size(110, 28)
        self.btn_refresh.Click += self.on_refresh
        self.Controls.Add(self.btn_refresh)

        self.btn_apply = RoundedButton("Aplicar Cambios", COLOR_ACCENT)
        self.btn_apply.Location = Point(1055, 10)
        self.btn_apply.Size = Size(110, 28)
        self.btn_apply.Click += self.on_apply
        self.Controls.Add(self.btn_apply)

        self.grid = DataGridView()
        self.grid.Location = Point(15, 45)
        self.grid.Size = Size(1150, 540)
        self.grid.Anchor = (AnchorStyles.Top | AnchorStyles.Bottom |
                             AnchorStyles.Left | AnchorStyles.Right)
        self.grid.AllowUserToAddRows = False
        self.grid.AllowUserToDeleteRows = False
        self.grid.RowHeadersVisible = False
        self.grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
        self.grid.SelectionMode = DataGridViewSelectionMode.CellSelect
        self.grid.BackgroundColor = Color.White
        self.grid.BorderStyle = getattr(BorderStyle, 'None')
        self.grid.EnableHeadersVisualStyles = False
        self.grid.ColumnHeadersDefaultCellStyle.BackColor = COLOR_HEADER
        self.grid.ColumnHeadersDefaultCellStyle.ForeColor = Color.White
        self.grid.ColumnHeadersDefaultCellStyle.Font = Font("Segoe UI", 9, FontStyle.Bold)
        self.grid.ColumnHeadersDefaultCellStyle.Padding = Padding(4)
        self.grid.ColumnHeadersBorderStyle = DataGridViewHeaderBorderStyle.Single
        self.grid.AlternatingRowsDefaultCellStyle.BackColor = Color.FromArgb(245, 245, 245)
        self.grid.CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal
        self.grid.GridColor = Color.FromArgb(230, 230, 230)
        self.grid.RowTemplate.Height = 28
        self.grid.DataError += self.on_grid_data_error
        self.grid.CellValueChanged += self.on_cell_value_changed
        self.grid.CellClick += self.on_cell_click

        col_cat = DataGridViewComboBoxColumn()
        col_cat.Name = "categoria"
        col_cat.HeaderText = "Categoria"
        combo_items = list(self.category_names)
        if "Sin categoria" not in combo_items:
            combo_items.append("Sin categoria")
        combo_items.sort()
        for val in combo_items:
            col_cat.Items.Add(val)
        col_cat.FillWeight = 22
        self.grid.Columns.Add(col_cat)

        col_fam = DataGridViewTextBoxColumn()
        col_fam.Name = "familia"
        col_fam.HeaderText = "Nombre de Familia"
        col_fam.FillWeight = 30
        self.grid.Columns.Add(col_fam)

        col_eq = DataGridViewTextBoxColumn()
        col_eq.Name = "separador"
        col_eq.HeaderText = ""
        col_eq.ReadOnly = True
        col_eq.FillWeight = 3
        col_eq.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter
        col_eq.DefaultCellStyle.ForeColor = COLOR_ACCENT
        col_eq.DefaultCellStyle.Font = Font("Segoe UI", 10, FontStyle.Bold)
        self.grid.Columns.Add(col_eq)

        col_tipo = DataGridViewTextBoxColumn()
        col_tipo.Name = "tipo"
        col_tipo.HeaderText = "Nombre de Tipo"
        col_tipo.FillWeight = 30
        self.grid.Columns.Add(col_tipo)

        col_inst = DataGridViewTextBoxColumn()
        col_inst.Name = "instancias"
        col_inst.HeaderText = "Instancias"
        col_inst.ReadOnly = True
        col_inst.FillWeight = 12
        self.grid.Columns.Add(col_inst)

        col_del = DataGridViewCheckBoxColumn()
        col_del.Name = "eliminar"
        col_del.HeaderText = "Eliminar"
        col_del.FillWeight = 12
        self.grid.Columns.Add(col_del)

        self.Controls.Add(self.grid)

        lbl_log = Label()
        lbl_log.Text = "Resultado:"
        lbl_log.Location = Point(15, 595)
        lbl_log.Size = Size(100, 20)
        lbl_log.Anchor = AnchorStyles.Bottom | AnchorStyles.Left
        self.Controls.Add(lbl_log)

        self.txt_log = TextBox()
        self.txt_log.Location = Point(15, 618)
        self.txt_log.Size = Size(1150, 60)
        self.txt_log.Anchor = (AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right)
        self.txt_log.Multiline = True
        self.txt_log.ReadOnly = True
        self.txt_log.ScrollBars = ScrollBars.Vertical
        self.txt_log.BackColor = Color.FromArgb(250, 250, 250)
        self.Controls.Add(self.txt_log)

    # -- datos <-> grilla ---------------------------------------------
    def load_grid(self):
        self.grid.Rows.Clear()
        for row in self.visible_rows:
            idx = self.grid.Rows.Add()
            r = self.grid.Rows[idx]
            r.Cells["categoria"].Value = row['category']
            r.Cells["familia"].Value = row['family_name']
            if row['type_count'] == 1:
                r.Cells["separador"].Value = " ="
                r.Cells["separador"].ToolTipText = "Clic para igualar el nombre del tipo al de la familia"
            else:
                r.Cells["separador"].Value = ""
            r.Cells["tipo"].Value = row['type_name']
            r.Cells["instancias"].Value = row['instances']
            r.Tag = row
            if row.get('is_inplace'):
                r.Cells["categoria"].ReadOnly = True
                r.Cells["categoria"].Style.BackColor = Color.FromArgb(238, 238, 238)
                r.Cells["categoria"].ToolTipText = (
                    "Familia in situ (in-place): la categoria no se puede "
                    "cambiar por API."
                )
        self.lbl_count.Text = "{0} tipos / {1} familias".format(
            len(self.visible_rows),
            len(set(r['family_id'].IntegerValue for r in self.visible_rows))
        )

    def on_grid_data_error(self, sender, args):
        # Evita el dialogo predeterminado de error del DataGridView.
        # Si ocurre (valor de combo fuera de lista, etc.) lo dejamos pasar
        # sin interrumpir al usuario; el valor simplemente no se pinta.
        args.ThrowException = False
        try:
            logger.debug(
                "DataGridView DataError en fila {0}, columna {1}: {2}".format(
                    args.RowIndex, args.ColumnIndex, args.Exception
                )
            )
        except Exception:
            pass

    def on_cell_value_changed(self, sender, args):
        if args.RowIndex < 0:
            return
        col_name = self.grid.Columns[args.ColumnIndex].Name
        
        # Si se editó el nombre de una familia, sincronizamos en las demás filas 
        # que corresponden a la misma familia para no confundir al usuario.
        if col_name == "familia":
            new_val = self.grid.Rows[args.RowIndex].Cells[args.ColumnIndex].Value
            row_data = self.grid.Rows[args.RowIndex].Tag
            if row_data:
                fam_id = row_data['family_id']
                # Deshabilitamos el evento temporalmente para no entrar en loop
                self.grid.CellValueChanged -= self.on_cell_value_changed
                for i in range(self.grid.Rows.Count):
                    if i != args.RowIndex:
                        other_data = self.grid.Rows[i].Tag
                        if other_data and other_data['family_id'] == fam_id:
                            self.grid.Rows[i].Cells["familia"].Value = new_val
                            # Opcional: indicarle al usuario que se auto-cambió coloreando
                            self.grid.Rows[i].Cells["familia"].Style.ForeColor = COLOR_ACCENT
                self.grid.Rows[args.RowIndex].Cells["familia"].Style.ForeColor = COLOR_ACCENT
                self.grid.CellValueChanged += self.on_cell_value_changed

    def on_cell_click(self, sender, args):
        if args.RowIndex < 0 or args.ColumnIndex < 0:
            return
        col_name = self.grid.Columns[args.ColumnIndex].Name
        if col_name == "separador":
            val = self.grid.Rows[args.RowIndex].Cells[args.ColumnIndex].Value
            if val and "=" in val:
                fam_name = self.grid.Rows[args.RowIndex].Cells["familia"].Value
                self.grid.Rows[args.RowIndex].Cells["tipo"].Value = fam_name
                self.grid.Rows[args.RowIndex].Cells["tipo"].Style.ForeColor = COLOR_ACCENT
    def on_delete_selected(self, sender, args):
        self.grid.EndEdit()
        
        to_delete = set()
        fam_names = []
        for r in self.grid.Rows:
            if r.Cells["eliminar"].Value:
                row_data = r.Tag
                if row_data and row_data['family_id'] not in to_delete:
                    to_delete.add(row_data['family_id'])
                    fam_names.append(row_data['family_name'])
                    
        if not to_delete:
            MessageBox.Show("No has marcado ninguna familia para eliminar.", "Aviso", MessageBoxButtons.OK, MessageBoxIcon.Information)
            return
            
        msg = "¿Estás seguro de que deseas eliminar del proyecto las siguientes {} familias (y todos sus tipos)?\n\n- ".format(len(to_delete))
        msg += "\n- ".join(fam_names[:10])
        if len(fam_names) > 10:
            msg += "\n... y {} más.".format(len(fam_names) - 10)
            
        res = MessageBox.Show(msg, "Confirmar Eliminación Múltiple", MessageBoxButtons.YesNo, MessageBoxIcon.Warning)
        
        if res == System.Windows.Forms.DialogResult.Yes:
            t = Transaction(self.doc, "Eliminar Familias Múltiples")
            t.Start()
            err_count = 0
            for fam_id in to_delete:
                try:
                    self.doc.Delete(fam_id)
                except Exception:
                    err_count += 1
            t.Commit()
            
            if err_count > 0:
                MessageBox.Show("Se eliminaron algunas familias, pero {} fallaron.".format(err_count), "Advertencia", MessageBoxButtons.OK, MessageBoxIcon.Warning)
            
            self.on_refresh(None, None)

    def on_search(self, sender, args):
        text = self.txt_search.Text.strip().lower()
        if not text:
            self.visible_rows = list(self.all_rows)
        else:
            self.visible_rows = [
                r for r in self.all_rows
                if text in r['family_name'].lower()
                or text in r['type_name'].lower()
                or text in r['category'].lower()
            ]
        self.load_grid()

    def on_refresh(self, sender, args):
        self.all_rows = collect_family_type_rows(self.doc)
        self.on_search(None, None)
        self.txt_log.Text = "Lista actualizada."

    # -- aplicar cambios ------------------------------------------------
    def on_apply(self, sender, args):
        # Confirmar celdas en edicion
        self.grid.EndEdit()

        family_new_name = {}     # family_id -> nuevo nombre
        family_new_cat = {}      # family_id -> Category
        type_new_name = {}       # type_id -> nuevo nombre
        log_lines = []
        ok_count = 0
        err_count = 0

        for r in self.grid.Rows:
            data = r.Tag
            if data is None:
                continue
            cur_cat = r.Cells["categoria"].Value
            cur_fam = (r.Cells["familia"].Value or "").strip()
            cur_tipo = (r.Cells["tipo"].Value or "").strip()

            if cur_fam and cur_fam != data['orig_family_name']:
                family_new_name[data['family_id']] = cur_fam

            if cur_cat and cur_cat != data['orig_category'] and cur_cat in self.category_by_name:
                if data.get('is_inplace'):
                    log_lines.append(
                        "[OMITIDO] '{0}' es una familia in situ (in-place); "
                        "su categoria no se puede cambiar por API.".format(
                            data['orig_family_name'])
                    )
                else:
                    family_new_cat[data['family_id']] = self.category_by_name[cur_cat]

            if cur_tipo and cur_tipo != data['orig_type_name']:
                type_new_name[data['type_id']] = cur_tipo

        if not (family_new_name or family_new_cat or type_new_name or log_lines):
            self.txt_log.Text = "No hay cambios para aplicar."
            return

        for fam_id, new_name in family_new_name.items():
            ok, err = rename_family(self.doc, fam_id, new_name)
            if ok:
                ok_count += 1
            else:
                err_count += 1
                log_lines.append("[ERROR] Renombrar familia -> '{0}': {1}".format(new_name, err))

        for fam_id, new_cat in family_new_cat.items():
            ok, err = recategorize_family(self.doc, fam_id, new_cat)
            if ok:
                ok_count += 1
            else:
                err_count += 1
                log_lines.append("[ERROR] Cambiar categoria (familia id {0}): {1}".format(
                    fam_id.IntegerValue, err))

        for type_id, new_name in type_new_name.items():
            ok, err = rename_type(self.doc, type_id, new_name)
            if ok:
                ok_count += 1
            else:
                err_count += 1
                log_lines.append("[ERROR] Renombrar tipo -> '{0}': {1}".format(new_name, err))

        self.all_rows = collect_family_type_rows(self.doc)
        self.on_search(None, None)

        summary = "Cambios aplicados: {0} correctos, {1} con error.".format(ok_count, err_count)
        if log_lines:
            summary += "\r\n" + "\r\n".join(log_lines)
        self.txt_log.Text = summary


# ------------------------------------------------------------------
# Punto de entrada
# ------------------------------------------------------------------
def main():
    try:
        if doc is None:
            MessageBox.Show("No hay documento activo.", "Aviso",
                             MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return
        if doc.IsFamilyDocument:
            MessageBox.Show("Esta herramienta debe ejecutarse en un documento de PROYECTO, "
                             "no en el editor de familias.", "Aviso",
                             MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return

        form = GestorFamiliasForm(doc)
        form.ShowDialog()
    except Exception as e:
        import traceback
        MessageBox.Show("Error fatal:\n" + traceback.format_exc(), "Error", MessageBoxButtons.OK, MessageBoxIcon.Error)
        if logger:
            logger.error(traceback.format_exc())


if __name__ == '__main__':
    main()