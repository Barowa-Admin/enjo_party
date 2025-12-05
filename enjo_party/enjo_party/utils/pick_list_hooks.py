# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
import types
from frappe.utils import flt

def before_validate_pick_list(doc, method):
    """
    Hook für Pick List before_validate
    Deaktiviert Lager-Validierung für alle Pick Lists
    WICHTIG: Setzt auch item_name für Trenn-Items BEVOR Frappe es überschreibt
    
    WICHTIG: Diese Funktion macht Packlisten IMMER buchbar, auch wenn:
    - Der Lagerbestand nicht ausreicht
    - Die Bewertungsrate fehlt
    - Keine Buchhaltungseinträge erstellt werden können
    
    ZUM KOMPLETTEN DEAKTIVIEREN:
    1. Kommentiere alle Flag-Zuweisungen aus (Zeilen 26-29)
    2. Kommentiere diese Funktion in hooks.py aus (Zeile 174)
    """
    if doc.doctype != "Pick List":
        return
    
    # WICHTIG: Stelle sicher, dass item_name für Trenn-Items BEVOR der Validierung gesetzt wird
    # Frappe könnte das item_name in set_missing_values() überschreiben
    # WICHTIG: Verwende Position in der Pick List, um das richtige Trenn-Item aus der Sales Order zu finden
    separator_index_in_picklist = 0
    for picklist_item_idx, picklist_item in enumerate(doc.locations):
        if picklist_item.item_code == "---":
            # Trenn-Item: Suche in Sales Order nach dem Trenn-Item an der entsprechenden Position
            if picklist_item.sales_order:
                try:
                    so_doc = frappe.get_doc("Sales Order", picklist_item.sales_order)
                    # Zähle Trenn-Items in der Sales Order und finde das an der Position separator_index_in_picklist
                    separator_index_in_so = 0
                    for so_item in so_doc.items:
                        if so_item.item_code == "---" and abs(flt(so_item.qty) - flt(picklist_item.qty)) < 0.0001:
                            # Prüfe ob dies das richtige Trenn-Item ist (basierend auf Position)
                            if separator_index_in_so == separator_index_in_picklist:
                                # Gefunden! Übernehme item_name aus Sales Order Item
                                if so_item.item_name and "Bestellung für:" in so_item.item_name:
                                    picklist_item.item_name = so_item.item_name
                                    frappe.log_error(f"📋 Trenn-Item #{separator_index_in_picklist} (Position {picklist_item_idx}) item_name in before_validate gesetzt: {so_item.item_name}", "DEBUG: separator_item_name_before_validate")
                                    separator_index_in_picklist += 1
                                    break
                            separator_index_in_so += 1
                except Exception as e:
                    frappe.log_error(f"⚠️ Fehler beim Setzen von item_name für Trenn-Item in before_validate: {str(e)}", "WARNING: separator_item_name_error_validate")
    
    # ===================================================================================
    # ABSCHNITT 1: DEAKTIVIERUNG VON VALIDIERUNGEN FÜR PACKLISTEN
    # ===================================================================================
    # Diese Flags deaktivieren ERPNext-Validierungen, die das Buchen von Packlisten
    # verhindern würden. Ohne diese Flags würde ERPNext Fehler werfen bei:
    # - Fehlender Bewertungsrate
    # - Unzureichendem Lagerbestand
    # - Fehlenden Buchhaltungseinträgen
    #
    # DEAKTIVIERUNG: Kommentiere die folgenden 4 Zeilen aus (Zeilen 26-29)
    # ===================================================================================
    doc.flags.ignore_warehouse_validation = True  # Ignoriert Lager-Validierung
    doc.flags.ignore_stock_validation = True      # Ignoriert Bestands-Validierung
    doc.flags.ignore_gl_entries = True            # KEINE Buchhaltungseinträge erstellen
    doc.flags.ignore_valuation_rate = True        # Ignoriere Bewertungsrate-Validierung
    
    frappe.log_error(f"✅ Lager-Validierung für Pick List {doc.name} deaktiviert", "INFO: picklist_validation_disabled")


def before_submit_pick_list(doc, method):
    """
    Hook für Pick List before_submit
    Stellt sicher, dass alle Validierungen deaktiviert sind.
    
    WICHTIG: Diese Funktion wird VOR dem Buchen (Submit) aufgerufen und stellt
    sicher, dass alle Validierungen auch zu diesem Zeitpunkt noch deaktiviert sind.
    Dies ist notwendig, da ERPNext zu verschiedenen Zeitpunkten validiert.
    
    ZUM KOMPLETTEN DEAKTIVIEREN:
    1. Kommentiere alle Flag-Zuweisungen aus (Zeilen 52-55)
    2. Kommentiere diese Funktion in hooks.py aus (Zeile 175)
    """
    if doc.doctype != "Pick List":
        return
    
    # ===================================================================================
    # ABSCHNITT 1: DEAKTIVIERUNG VON VALIDIERUNGEN VOR DEM BUCHEN
    # ===================================================================================
    # Diese Flags werden VOR dem Submit gesetzt, um sicherzustellen, dass alle
    # Validierungen auch zu diesem späten Zeitpunkt noch deaktiviert sind.
    # ERPNext führt Validierungen zu verschiedenen Zeitpunkten durch, daher ist
    # diese doppelte Absicherung notwendig.
    #
    # DEAKTIVIERUNG: Kommentiere die folgenden 4 Zeilen aus (Zeilen 52-55)
    # ===================================================================================
    doc.flags.ignore_warehouse_validation = True  # Ignoriert Lager-Validierung
    doc.flags.ignore_stock_validation = True      # Ignoriert Bestands-Validierung
    doc.flags.ignore_gl_entries = True            # KEINE Buchhaltungseinträge erstellen
    doc.flags.ignore_valuation_rate = True        # Ignoriere Bewertungsrate-Validierung
    
    frappe.log_error(f"✅ Validierungen für Pick List {doc.name} vor Submit deaktiviert", "INFO: picklist_pre_submit_validation_disabled")


def before_save_pick_list(doc, method):
    """
    Hook für Pick List before_save
    Stellt sicher, dass item_name aus Sales Order Item übernommen wird (für Gruppenversand mit Präfix)
    WICHTIG: Setzt auch item_name für Trenner-Items (item_code == "---") aus Sales Order Item
    """
    if doc.doctype != "Pick List":
        return
    
    # Stelle sicher, dass item_name aus Sales Order Item übernommen wird
    # WICHTIG: Verwende Position in der Pick List, um das richtige Trenn-Item aus der Sales Order zu finden
    separator_index_in_picklist = 0
    for picklist_item_idx, picklist_item in enumerate(doc.locations):
        # WICHTIG: Trenn-Items haben KEIN sales_order_item, daher müssen wir sie anders behandeln
        if picklist_item.item_code == "---":
            # Trenn-Item: Suche in Sales Order nach dem Trenn-Item an der entsprechenden Position
            if picklist_item.sales_order:
                try:
                    so_doc = frappe.get_doc("Sales Order", picklist_item.sales_order)
                    # Zähle Trenn-Items in der Sales Order und finde das an der Position separator_index_in_picklist
                    separator_index_in_so = 0
                    for so_item in so_doc.items:
                        if so_item.item_code == "---" and abs(flt(so_item.qty) - flt(picklist_item.qty)) < 0.0001:
                            # Prüfe ob dies das richtige Trenn-Item ist (basierend auf Position)
                            if separator_index_in_so == separator_index_in_picklist:
                                # Gefunden! Übernehme item_name aus Sales Order Item
                                if so_item.item_name and "Bestellung für:" in so_item.item_name:
                                    picklist_item.item_name = so_item.item_name
                                    frappe.log_error(f"📋 Trenn-Item #{separator_index_in_picklist} (Position {picklist_item_idx}) item_name aus SO übernommen in before_save: {so_item.item_name}", "DEBUG: separator_item_name_from_so_before_save")
                                    separator_index_in_picklist += 1
                                    break
                            separator_index_in_so += 1
                except Exception as e:
                    frappe.log_error(f"⚠️ Fehler beim Übernehmen von item_name für Trenn-Item: {str(e)}", "WARNING: separator_item_name_error")
        elif picklist_item.sales_order_item:
            # Normale Items: Übernehme item_name aus Sales Order Item
            try:
                so_item = frappe.get_doc("Sales Order Item", picklist_item.sales_order_item)
                if so_item.item_name:
                    picklist_item.item_name = so_item.item_name
                    frappe.log_error(f"📦 Picklist Item {picklist_item.item_code} item_name aus SO übernommen: {so_item.item_name}", "DEBUG: picklist_item_name_from_so")
            except Exception as e:
                frappe.log_error(f"⚠️ Fehler beim Übernehmen von item_name für Picklist Item: {str(e)}", "WARNING: picklist_item_name_error")
