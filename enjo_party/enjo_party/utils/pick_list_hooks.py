# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe

def before_validate_pick_list(doc, method):
    """
    Hook für Pick List before_validate
    Deaktiviert Lager-Validierung für alle Pick Lists
    """
    if doc.doctype != "Pick List":
        return
    
    # ALLGEMEIN: Lager-Validierung für alle Pick Lists deaktivieren
    # Das ermöglicht das Buchen auch wenn Artikel nicht im Lager verfügbar sind
    doc.flags.ignore_warehouse_validation = True
    doc.flags.ignore_stock_validation = True
    
    frappe.log_error(f"✅ Lager-Validierung für Pick List {doc.name} deaktiviert", "INFO: picklist_validation_disabled")
