# -*- coding: utf-8 -*-
"""
script.py  —  Entry point para pyRevit
Coloca este archivo junto con NavisworksClashManager.py
dentro de la carpeta:

  MiBIMTab.tab/
    ClashManager.panel/
      ClashManager.pushbutton/
          script.py
          NavisworksClashManager.py
          icon.png          (opcional, 32x32 px)
          bundle.yaml       (opcional)

pyRevit ejecuta script.py automáticamente al presionar el botón.
"""

import os
import sys

# Asegura que el directorio del script esté en el path
_dir = os.path.dirname(__file__)
if _dir not in sys.path:
    sys.path.insert(0, _dir)

# Importa y lanza la ventana modeless
from NavisworksClashManager import ClashManagerForm
from pyrevit import revit, HOST_APP

uidoc = revit.uidoc
doc   = revit.doc

form = ClashManagerForm(uidoc, doc)
form.Show()   # Modeless: no bloquea Revit