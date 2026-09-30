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

    # Limpia cualquier resaltado (Elemento A/B) que haya quedado pintado en el
    # modelo desde una sesión anterior que no se cerró limpiamente, ANTES de
    # mostrar el formulario — así el usuario no ve colores "fantasma".
    try:
        handler.cleanup_stale_highlights()
    except Exception:
        pass

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
        # Cierre limpio: si quedó algo pintado, lo quitamos ya mismo en vez de
        # dejarlo para que la próxima sesión lo encuentre "de sorpresa".
        try:
            handler._clear_highlight(doc)
        except Exception:
            pass
        try:
            handler._clear_markers(doc)   # esfera temporal de "Marcar punto"
        except Exception:
            pass
        try:
            handler._reset_view_tools(doc)   # Section Box / Isolate aplicados desde el Manager
        except Exception:
            pass

    from System.Windows.Forms import FormClosedEventHandler
    _active_form.FormClosed += FormClosedEventHandler(_on_form_closed)

    _active_form.Show()