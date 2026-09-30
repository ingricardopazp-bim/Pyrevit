# -*- coding: utf-8 -*-
"""
models.py — Modelos de datos del motor de interferencias.
ClashRecord es inmutable en su identidad (key) pero mutable en status.
"""
from __future__ import absolute_import


class ClashStatus(object):
    NEW      = 'New'
    ACTIVE   = 'Active'
    REVIEWED = 'Reviewed'
    APPROVED = 'Approved'
    RESOLVED = 'Resolved'

    ALL = (NEW, ACTIVE, REVIEWED, APPROVED, RESOLVED)


class ClashType(object):
    """Clasificación geométrica de la interferencia."""
    HARD   = 'Hard'    # intersección volumétrica real (sólido-sólido)
    LINKED = 'Linked'  # igual que HARD pero el elemento B viene de modelo linkeado


class ClashRecord(object):
    __slots__ = (
        'key', 'source_doc', 'target_doc',
        'source_id', 'target_id',
        'source_name', 'target_name',
        'source_category', 'target_category',
        'volume', 'is_linked', 'status', 'clash_type',
    )

    def __init__(
        self,
        key,
        source_doc,
        target_doc,
        source_id,
        target_id,
        source_name,
        target_name,
        source_category,
        target_category,
        volume,
        is_linked=False,
        status=None,
        clash_type=None,
    ):
        self.key             = key
        self.source_doc      = source_doc
        self.target_doc      = target_doc
        self.source_id       = source_id
        self.target_id       = target_id
        self.source_name     = source_name
        self.target_name     = target_name
        self.source_category = source_category
        self.target_category = target_category
        self.volume          = volume
        self.is_linked       = is_linked
        self.status          = status if status is not None else ClashStatus.NEW
        self.clash_type      = clash_type if clash_type is not None else ClashType.HARD

    @property
    def pair_label(self):
        return u'%s #%s  \u00d7  %s #%s' % (
            self.source_name, self.source_id,
            self.target_name, self.target_id,
        )

    @property
    def context_label(self):
        if self.is_linked:
            return u'%s \u2192 %s' % (self.source_doc, self.target_doc)
        return self.source_doc

    def display_text(self):
        return u'%s | %s vs %s | %s | %.5f ft\u00b3' % (
            self.pair_label,
            self.source_category,
            self.target_category,
            self.status,
            self.volume,
        )

    def __str__(self):
        return self.display_text()

    def ToString(self):
        return self.display_text()
