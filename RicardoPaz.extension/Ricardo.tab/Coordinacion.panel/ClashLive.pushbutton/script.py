# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import sys

from pyrevit import forms, revit, script


bundle_dir = os.path.dirname(__file__)
if bundle_dir not in sys.path:
    sys.path.insert(0, bundle_dir)

from bim_clash.app import run


logger = script.get_logger()


if not revit.doc:
    forms.alert('Open a Revit model before running BIM Conflict Manager.', exitscript=True)

run(revit.uidoc, revit.doc, logger)
