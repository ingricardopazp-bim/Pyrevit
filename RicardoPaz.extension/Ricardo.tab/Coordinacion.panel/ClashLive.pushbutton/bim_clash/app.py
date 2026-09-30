# -*- coding: utf-8 -*-
from __future__ import absolute_import

import clr

clr.AddReference('System.Windows.Forms')
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.UI import ExternalEvent

from bim_clash.detector import ClashDetector
from bim_clash.events import ClashExternalEventHandler
from bim_clash.state import ClashState
from bim_clash.ui import ClashManagerForm


_active_form    = None
_change_handler = None


def run(uidoc, doc, logger=None):
    global _active_form, _change_handler

    if _active_form is not None and not _active_form.IsDisposed:
        _active_form.Activate()
        return

    doc_path  = None
    doc_title = None
    try:
        doc_path  = doc.PathName
        doc_title = doc.Title
    except Exception:
        pass

    detector       = ClashDetector(doc)
    state          = ClashState(doc_title=doc_title, doc_path=doc_path)
    handler        = ClashExternalEventHandler()
    handler.detector = detector
    handler.state = state
    handler.logger = logger
    external_event = ExternalEvent.Create(handler)
    _active_form   = ClashManagerForm(uidoc, state, handler, external_event, logger)
    handler.form   = _active_form

    def _on_document_changed(sender, args):
        try:
            if _active_form is None or _active_form.IsDisposed:
                return
            if not _active_form.auto_scan:
                return
            if args.GetDocument().Title != doc.Title:
                return
            if handler.request_scan(_active_form.include_links):
                external_event.Raise()
        except Exception:
            pass

    _change_handler = _on_document_changed
    doc.Application.DocumentChanged += _on_document_changed

    def _on_form_closed(s, a):
        try:
            doc.Application.DocumentChanged -= _change_handler
        except Exception:
            pass

    from System.Windows.Forms import FormClosedEventHandler
    _active_form.FormClosed += FormClosedEventHandler(_on_form_closed)

    _active_form.Show()