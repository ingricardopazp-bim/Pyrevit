# -*- coding: utf-8 -*-
__title__ = "Cotas\nBatea"
__doc__ = "Define cota batea de inicio y final de la tubería seleccionada"

from pyrevit import revit, DB, forms, script

doc = revit.doc
uidoc = revit.uidoc
out = script.get_output()
BIP = DB.BuiltInParameter
M = DB.UnitTypeId.Meters


def m2i(v):
    return DB.UnitUtils.ConvertToInternalUnits(v, M)


def i2m(v):
    return DB.UnitUtils.ConvertFromInternalUnits(v, M)


def pedir(msg, default):
    v = forms.ask_for_string(default="{:.3f}".format(default), prompt=msg,
                             title="Cotas batea")
    if v is None:
        script.exit()
    return float(v.replace(",", "."))


# 1. Tubería seleccionada
ids = list(uidoc.Selection.GetElementIds())
pipe = doc.GetElement(ids[0]) if len(ids) == 1 else None
if not isinstance(pipe, DB.Plumbing.Pipe):
    forms.alert("Selecciona UNA tubería rígida.", exitscript=True)

# 2. Sistema de cotas
modo = forms.CommandSwitchWindow.show(
    ["Coordenadas compartidas", "Internas del proyecto"],
    message="¿En qué sistema están las cotas?")
if not modo:
    script.exit()

if modo == "Coordenadas compartidas":
    z_off = doc.ActiveProjectLocation.GetTotalTransform().Origin.Z
else:
    z_off = 0.0

# 3. Diámetro interior (si no está definido, usa el exterior y avisa)
d_int = pipe.get_Parameter(BIP.RBS_PIPE_INNER_DIAM_PARAM).AsDouble()
if d_int <= 0:
    d_int = pipe.get_Parameter(BIP.RBS_PIPE_OUTER_DIAMETER).AsDouble()
    forms.alert("El tipo no tiene diámetro interior definido.\n"
                "Se usará el diámetro exterior para calcular la batea.")

crv = pipe.Location.Curve
p0 = crv.GetEndPoint(0)
p1 = crv.GetEndPoint(1)

if abs(p0.X - p1.X) < 1e-6 and abs(p0.Y - p1.Y) < 1e-6:
    forms.alert("La tubería es vertical; este script no aplica.", exitscript=True)

batea_ini0 = i2m(p0.Z + z_off - d_int / 2.0)
batea_fin0 = i2m(p1.Z + z_off - d_int / 2.0)

batea_ini = pedir("Cota batea INICIO (m):", batea_ini0)
batea_fin = pedir("Cota batea FINAL (m):", batea_fin0)


# 4. Batea -> cota del eje del tubo (coordenadas internas)
def z_eje(batea_m):
    return m2i(batea_m) + d_int / 2.0 - z_off


n0 = DB.XYZ(p0.X, p0.Y, z_eje(batea_ini))
n1 = DB.XYZ(p1.X, p1.Y, z_eje(batea_fin))

# 5. Aplicar moviendo los extremos de la curva
with revit.Transaction("Cotas batea"):
    try:
        pipe.Location.Curve = DB.Line.CreateBound(n0, n1)
    except Exception as ex:
        forms.alert("No se pudo modificar la tubería:\n{}".format(ex),
                    exitscript=True)

# 6. Verificación
crv = pipe.Location.Curve
r_ini = i2m(crv.GetEndPoint(0).Z + z_off - d_int / 2.0)
r_fin = i2m(crv.GetEndPoint(1).Z + z_off - d_int / 2.0)
largo = i2m(crv.Length)
pend = (batea_ini - batea_fin) / largo * 100 if largo else 0

out.print_md("### Resultado")
out.print_md("- Batea inicio: **{:.3f}** m (pedido {:.3f})".format(r_ini, batea_ini))
out.print_md("- Batea final: **{:.3f}** m (pedido {:.3f})".format(r_fin, batea_fin))
out.print_md("- Longitud: {:.3f} m, pendiente: {:.2f} %".format(largo, pend))