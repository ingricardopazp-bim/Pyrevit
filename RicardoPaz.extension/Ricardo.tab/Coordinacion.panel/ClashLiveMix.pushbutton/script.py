# -*- coding: utf-8 -*-
# SCRIPT DE DIAGNOSTICO - renombrar a script.py para probar
from __future__ import absolute_import

import os
import sys
import traceback
import io

LOG = r'C:\ClashManager\debug_log.txt'


def log(msg):
    """Escribe en archivo Y en la consola de pyRevit."""
    try:
        folder = os.path.dirname(LOG)
        if not os.path.exists(folder):
            os.makedirs(folder)
        with io.open(LOG, 'a', encoding='utf-8') as f:
            f.write(u'%s\n' % msg)
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        pass


try:
    log(u'--- inicio ---')
    from pyrevit import forms, revit, script
    log(u'1. pyrevit importado')

    bundle_dir = os.path.dirname(__file__)
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
    log(u'2. bundle_dir = %s' % bundle_dir)
    log(u'   existe bim_clash? %s' % os.path.exists(os.path.join(bundle_dir, 'bim_clash')))

    from bim_clash.app import run
    log(u'3. bim_clash.app importado')

    logger = script.get_logger()

    if not revit.doc:
        forms.alert('Open a Revit model before running BIM Conflict Manager.', exitscript=True)
    log(u'4. doc = %s' % revit.doc.Title)

    run(revit.uidoc, revit.doc, logger)
    log(u'5. run() termino sin error')

except Exception as ex:
    log(u'ERROR %s: %s' % (type(ex).__name__, ex))
    log(traceback.format_exc())
