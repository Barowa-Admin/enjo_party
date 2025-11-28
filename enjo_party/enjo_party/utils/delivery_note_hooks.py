# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
import types

def before_validate_delivery_note(doc, method):
    """
    Hook für Delivery Note before_validate
    Umgeht die Adress-Validierung für fremde Lieferadressen
    Deaktiviert Lager-Validierung für alle Delivery Notes
    
    WICHTIG: Diese Funktion macht Lieferscheine IMMER buchbar, auch wenn:
    - Der Lagerbestand nicht ausreicht
    - Die Bewertungsrate fehlt
    - Keine Buchhaltungseinträge erstellt werden können
    
    ZUM KOMPLETTEN DEAKTIVIEREN:
    1. Kommentiere die Flag-Zuweisungen in diesem Block aus (Zeilen 38-41)
    2. Kommentiere den "Allow Zero Valuation" Block aus (Zeilen 44-49)
    3. Kommentiere die gesamte Funktion in hooks.py aus (Zeile 170)
    """
    if doc.doctype != "Delivery Note":
        return
    
    # WICHTIG: Stelle sicher, dass Trenner-Items (item_code == "---") NICHT entfernt werden
    # Speichere Trenner-Items vor Validierungen
    separator_items_backup = []
    if hasattr(doc, 'items') and doc.items:
        for idx, item in enumerate(doc.items):
            if item.item_code == "---":
                separator_items_backup.append({
                    'idx': idx,
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'qty': item.qty,
                    'rate': item.rate,
                    'amount': item.amount,
                    'uom': item.uom,
                    'stock_uom': item.stock_uom,
                    'conversion_factor': item.conversion_factor,
                    'stock_qty': item.stock_qty,
                    'base_amount': item.base_amount,
                    'base_rate': item.base_rate,
                    'warehouse': item.warehouse,
                    # HINWEIS: Delivery Note Item hat kein delivery_date Feld!
                    'sales_order': getattr(item, 'sales_order', None),
                    'sales_order_item': getattr(item, 'sales_order_item', None),
                    'allow_zero_valuation_rate': getattr(item, 'allow_zero_valuation_rate', 1)
                })
                frappe.log_error(f"🔍 Trenner-Item gesichert vor validate: item_code='{item.item_code}', item_name='{item.item_name}'", "DEBUG: separator_item_backed_up_validate")
    
    # ===================================================================================
    # ABSCHNITT 1: DEAKTIVIERUNG VON VALIDIERUNGEN
    # ===================================================================================
    # Diese Flags deaktivieren ERPNext-Validierungen, die das Buchen von Lieferscheinen
    # verhindern würden. Ohne diese Flags würde ERPNext Fehler werfen bei:
    # - Fehlender Bewertungsrate (z.B. "Bewertungsrate fehlt" Fehler)
    # - Unzureichendem Lagerbestand
    # - Fehlenden Buchhaltungseinträgen
    #
    # DEAKTIVIERUNG: Kommentiere die folgenden 4 Zeilen aus (Zeilen 38-41)
    # ===================================================================================
    doc.flags.ignore_warehouse_validation = True  # Ignoriert Lager-Validierung
    doc.flags.ignore_stock_validation = True      # Ignoriert Bestands-Validierung
    doc.flags.ignore_gl_entries = True            # KEINE Buchhaltungseinträge erstellen
    doc.flags.ignore_valuation_rate = True        # Ignoriere Bewertungsrate-Validierung
    
    # WICHTIG: Überschreibe auch die validate_item_valuation_rate Methode direkt
    # Dies verhindert, dass die Validierung in der validate() Methode ausgeführt wird
    # und der Lieferschein nicht gespeichert werden kann
    def safe_validate_item_valuation_rate(self, *args, **kwargs):
        """Überschreibt die Validierung für Bewertungsrate - verhindert Fehler beim Speichern"""
        pass
    
    if hasattr(doc, 'validate_item_valuation_rate'):
        doc.validate_item_valuation_rate = types.MethodType(safe_validate_item_valuation_rate, doc)
    
    # ===================================================================================
    # ABSCHNITT 2: "ALLOW ZERO VALUATION" FÜR ALLE ITEMS
    # ===================================================================================
    # Setzt automatisch "Allow Zero Valuation" für alle Artikel in der Delivery Note.
    # Dies ist notwendig, damit ERPNext Artikel ohne Bewertungsrate akzeptiert.
    # Ohne diese Einstellung würde ERPNext bei fehlender Bewertungsrate einen Fehler werfen.
    #
    # DEAKTIVIERUNG: Kommentiere den gesamten if-Block aus (Zeilen 44-49)
    # HINWEIS: Wenn dieser Block deaktiviert wird, müssen alle Artikel manuell
    #          "Allow Zero Valuation" in der Delivery Note gesetzt haben
    # ===================================================================================
    if hasattr(doc, 'items') and doc.items:
        for item in doc.items:
            if hasattr(item, 'allow_zero_valuation_rate'):
                item.allow_zero_valuation_rate = 1
            elif hasattr(item, 'allow_zero_valuation'):
                item.allow_zero_valuation = 1
    
    # WICHTIG: Stelle sicher, dass Trenner-Items nach Validierungen wieder vorhanden sind
    if separator_items_backup:
        # Prüfe, ob Trenner-Items noch vorhanden sind
        current_separator_count = sum(1 for item in doc.items if item.item_code == "---")
        if current_separator_count < len(separator_items_backup):
            frappe.log_error(f"⚠️ Trenner-Items wurden bei validate entfernt! Wiederherstelle {len(separator_items_backup)} Trenner-Items", "WARNING: separator_items_restored_validate")
            # Füge fehlende Trenner-Items wieder hinzu
            for backup_item in separator_items_backup:
                # Prüfe ob dieses Trenner-Item bereits vorhanden ist
                item_exists = any(
                    item.item_code == "---" and 
                    item.item_name == backup_item['item_name'] 
                    for item in doc.items
                )
                if not item_exists:
                    # Füge Trenner-Item wieder hinzu (OHNE delivery_date, da Delivery Note Item dieses Feld nicht hat)
                    new_item = doc.append('items', {
                        'item_code': backup_item['item_code'],
                        'item_name': backup_item['item_name'],
                        'qty': backup_item['qty'],
                        'rate': backup_item['rate'],
                        'amount': backup_item['amount'],
                        'uom': backup_item['uom'],
                        'stock_uom': backup_item['stock_uom'],
                        'conversion_factor': backup_item['conversion_factor'],
                        'stock_qty': backup_item['stock_qty'],
                        'base_amount': backup_item['base_amount'],
                        'base_rate': backup_item['base_rate'],
                        'warehouse': backup_item['warehouse'],
                        'sales_order': backup_item['sales_order'],
                        'sales_order_item': backup_item['sales_order_item'],
                        'allow_zero_valuation_rate': backup_item['allow_zero_valuation_rate']
                    })
                    frappe.log_error(f"✅ Trenner-Item bei validate wiederhergestellt: item_code='{backup_item['item_code']}', item_name='{backup_item['item_name']}'", "INFO: separator_item_restored_validate")
    
    # Prüfe, ob es sich um eine fremde Lieferadresse handelt ODER ob es ein Gruppenversand-Auftrag ist
    is_foreign_shipping = False
    is_gruppenversand = doc.customer == "Gruppenversand"
    
    if doc.shipping_address_name and doc.customer:
        # Prüfe, ob die Versandadresse zu einem anderen Kunden gehört
        try:
            # Suche alle Adressen die mit der shipping_address_name verknüpft sind
            address_links = frappe.get_all(
                "Dynamic Link",
                filters={"parent": doc.shipping_address_name, "parenttype": "Address"},
                fields=["link_doctype", "link_name"]
            )
            
            # Prüfe, ob die Adresse zu einem anderen Kunden gehört
            for link in address_links:
                if link.link_doctype == "Customer" and link.link_name != doc.customer:
                    is_foreign_shipping = True
                    frappe.log_error(f"Fremde Lieferadresse erkannt: {doc.shipping_address_name} gehört zu Kunde {link.link_name}, aber Delivery Note ist für Kunde {doc.customer}", "INFO: foreign_shipping_detected")
                    break
        except Exception as e:
            frappe.log_error(f"Fehler beim Prüfen der Versandadresse: {str(e)}", "WARNING: address_check_error")
    
    # Deaktiviere Validierungen für fremde Lieferadressen ODER für Gruppenversand
    if is_foreign_shipping or is_gruppenversand:
        if is_gruppenversand:
            frappe.log_error(f"✅ Gruppenversand erkannt für Delivery Note {doc.name} - Adressvalidierung deaktiviert", "INFO: delivery_note_pre_insert_validation_disabled")
        else:
            frappe.log_error(f"✅ Fremde Lieferadresse erkannt für Delivery Note {doc.name} - Validierung deaktiviert", "INFO: foreign_shipping_detected")
        
        # Deaktiviere ERPNext-Validierungen
        doc.flags.ignore_validate = True
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_links = True
        doc.flags.ignore_permissions = True
        doc.flags.ignore_address_validation = True
        doc.flags.ignore_shipping_validation = True
        doc.flags.ignore_billing_validation = True
        doc.flags.ignore_warehouse_validation = True  # Ignoriere Lager-Validierung
        doc.flags.ignore_stock_validation = True     # Ignoriere Bestand-Validierung
        
        # Überschreibe die Adress-Validierungsmethoden
        def safe_validate_party_address(self, *args, **kwargs):
            frappe.log_error(f"✅ Überspringe validate_party_address für {self.customer}", "INFO: skip_party_address_validation")
            pass
        
        def safe_validate_shipping_address(self):
            frappe.log_error(f"✅ Überspringe validate_shipping_address für {self.customer}", "INFO: skip_shipping_validation")
            pass
        
        def safe_validate_billing_address(self):
            frappe.log_error(f"✅ Überspringe validate_billing_address für {self.customer}", "INFO: skip_billing_validation")
            pass
        
        # Überschreibe nur die Adress-Validierungsmethoden
        doc.validate_party_address = types.MethodType(safe_validate_party_address, doc)
        doc.validate_shipping_address = types.MethodType(safe_validate_shipping_address, doc)
        doc.validate_billing_address = types.MethodType(safe_validate_billing_address, doc)
    
    # ===================================================================================
    # ABSCHNITT 3: "ALLOW ZERO VALUATION" FÜR ALLE ITEMS (NACH ADRESSVALIDIERUNG)
    # ===================================================================================
    # Diese Zeilen stellen sicher, dass auch nach der Adress-Validierungslogik
    # alle Items "Allow Zero Valuation" gesetzt haben. Dies ist eine Sicherheitsmaßnahme,
    # falls die vorherige Setzung überschrieben wurde.
    #
    # DEAKTIVIERUNG: Kommentiere den gesamten if-Block aus (Zeilen 104-109)
    # ===================================================================================
    if hasattr(doc, 'items') and doc.items:
        for item in doc.items:
            if hasattr(item, 'allow_zero_valuation_rate'):
                item.allow_zero_valuation_rate = 1
            elif hasattr(item, 'allow_zero_valuation'):
                item.allow_zero_valuation = 1


def before_insert_delivery_note(doc, method):
    """
    Hook für Delivery Note before_insert
    Stellt sicher, dass alle Validierungen deaktiviert sind BEVOR das Dokument
    in die Datenbank eingefügt wird.
    
    WICHTIG: Diese Funktion wird beim ERSTELLEN (Insert) der Delivery Note aufgerufen
    und verhindert, dass die Validierung bereits beim Erstellen einen Fehler wirft.
    Dies gilt für ALLE Delivery Notes, auch wenn sie manuell über die UI erstellt werden.
    
    ZUM KOMPLETTEN DEAKTIVIEREN:
    1. Kommentiere alle Flag-Zuweisungen aus (Zeilen 158-161)
    2. Kommentiere den "Allow Zero Valuation" Block aus (Zeilen 171-176)
    3. Kommentiere diese Funktion in hooks.py aus (Zeile 185)
    """
    if doc.doctype != "Delivery Note":
        return
    
    # Prüfe ob es ein Gruppenversand-Auftrag ist
    is_gruppenversand = doc.customer == "Gruppenversand"
    
    # WICHTIG: Stelle sicher, dass Trenner-Items (item_code == "---") NICHT entfernt werden
    # Speichere Trenner-Items vor Validierungen
    separator_items_backup = []
    if hasattr(doc, 'items') and doc.items:
        for idx, item in enumerate(doc.items):
            if item.item_code == "---":
                separator_items_backup.append({
                    'idx': idx,
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'qty': item.qty,
                    'rate': item.rate,
                    'amount': item.amount,
                    'uom': item.uom,
                    'stock_uom': item.stock_uom,
                    'conversion_factor': item.conversion_factor,
                    'stock_qty': item.stock_qty,
                    'base_amount': item.base_amount,
                    'base_rate': item.base_rate,
                    'warehouse': item.warehouse,
                    # HINWEIS: Delivery Note Item hat kein delivery_date Feld!
                    'sales_order': getattr(item, 'sales_order', None),
                    'sales_order_item': getattr(item, 'sales_order_item', None),
                    'allow_zero_valuation_rate': getattr(item, 'allow_zero_valuation_rate', 1)
                })
                frappe.log_error(f"🔍 Trenner-Item gesichert vor insert: item_code='{item.item_code}', item_name='{item.item_name}'", "DEBUG: separator_item_backed_up")
    
    # ===================================================================================
    # ABSCHNITT 1: DEAKTIVIERUNG VON VALIDIERUNGEN BEIM ERSTELLEN
    # ===================================================================================
    # Diese Flags werden BEVOR das Dokument eingefügt wird gesetzt, um sicherzustellen,
    # dass alle Validierungen bereits beim Erstellen übersprungen werden.
    # Ohne diese Flags würde ERPNext beim insert() einen Fehler werfen.
    # Dies gilt auch für manuell erstellte Delivery Notes über die UI.
    #
    # DEAKTIVIERUNG: Kommentiere die folgenden 4 Zeilen aus (Zeilen 158-161)
    # ===================================================================================
    doc.flags.ignore_warehouse_validation = True  # Ignoriert Lager-Validierung
    doc.flags.ignore_stock_validation = True      # Ignoriert Bestands-Validierung
    doc.flags.ignore_gl_entries = True            # KEINE Buchhaltungseinträge erstellen
    doc.flags.ignore_valuation_rate = True        # Ignoriere Bewertungsrate-Validierung
    
    # Für Gruppenversand: Deaktiviere auch Adress-Validierungen
    if is_gruppenversand:
        doc.flags.ignore_validate = True
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_links = True
        doc.flags.ignore_permissions = True
        doc.flags.ignore_address_validation = True
        doc.flags.ignore_shipping_validation = True
        doc.flags.ignore_billing_validation = True
        
        # Überschreibe die Adress-Validierungsmethoden
        def safe_validate_party_address(self, *args, **kwargs):
            pass
        
        def safe_validate_shipping_address(self):
            pass
        
        def safe_validate_billing_address(self):
            pass
        
        doc.validate_party_address = types.MethodType(safe_validate_party_address, doc)
        doc.validate_shipping_address = types.MethodType(safe_validate_shipping_address, doc)
        doc.validate_billing_address = types.MethodType(safe_validate_billing_address, doc)
    
    # WICHTIG: Überschreibe auch die validate_item_valuation_rate Methode direkt
    # Dies verhindert, dass die Validierung in der validate() Methode ausgeführt wird
    def safe_validate_item_valuation_rate(self, *args, **kwargs):
        """Überschreibt die Validierung für Bewertungsrate - verhindert Fehler beim Speichern"""
        pass
    
    if hasattr(doc, 'validate_item_valuation_rate'):
        doc.validate_item_valuation_rate = types.MethodType(safe_validate_item_valuation_rate, doc)
    
    # ===================================================================================
    # ABSCHNITT 2: "ALLOW ZERO VALUATION" FÜR ALLE ITEMS BEIM ERSTELLEN
    # ===================================================================================
    # Setzt "Allow Zero Valuation" für alle Items, falls diese beim Erstellen
    # noch nicht gesetzt wurde. Dies ist KRITISCH für Delivery Notes, die manuell
    # über die UI erstellt werden, da diese sonst eine Fehlermeldung bei fehlender
    # Bewertungsrate werfen würden.
    #
    # DEAKTIVIERUNG: Kommentiere den gesamten if-Block aus (Zeilen 171-176)
    # ===================================================================================
    if hasattr(doc, 'items') and doc.items:
        for item in doc.items:
            if hasattr(item, 'allow_zero_valuation_rate'):
                item.allow_zero_valuation_rate = 1
            elif hasattr(item, 'allow_zero_valuation'):
                item.allow_zero_valuation = 1
    
    # WICHTIG: Stelle sicher, dass Trenner-Items nach Validierungen wieder vorhanden sind
    if separator_items_backup:
        # Prüfe, ob Trenner-Items noch vorhanden sind
        current_separator_count = sum(1 for item in doc.items if item.item_code == "---")
        if current_separator_count < len(separator_items_backup):
            frappe.log_error(f"⚠️ Trenner-Items wurden entfernt! Wiederherstelle {len(separator_items_backup)} Trenner-Items", "WARNING: separator_items_restored")
            # Füge fehlende Trenner-Items wieder hinzu
            for backup_item in separator_items_backup:
                # Prüfe ob dieses Trenner-Item bereits vorhanden ist
                item_exists = any(
                    item.item_code == "---" and 
                    item.item_name == backup_item['item_name'] 
                    for item in doc.items
                )
                if not item_exists:
                    # Füge Trenner-Item wieder hinzu (OHNE delivery_date, da Delivery Note Item dieses Feld nicht hat)
                    new_item = doc.append('items', {
                        'item_code': backup_item['item_code'],
                        'item_name': backup_item['item_name'],
                        'qty': backup_item['qty'],
                        'rate': backup_item['rate'],
                        'amount': backup_item['amount'],
                        'uom': backup_item['uom'],
                        'stock_uom': backup_item['stock_uom'],
                        'conversion_factor': backup_item['conversion_factor'],
                        'stock_qty': backup_item['stock_qty'],
                        'base_amount': backup_item['base_amount'],
                        'base_rate': backup_item['base_rate'],
                        'warehouse': backup_item['warehouse'],
                        'sales_order': backup_item['sales_order'],
                        'sales_order_item': backup_item['sales_order_item'],
                        'allow_zero_valuation_rate': backup_item['allow_zero_valuation_rate']
                    })
                    frappe.log_error(f"✅ Trenner-Item wiederhergestellt: item_code='{backup_item['item_code']}', item_name='{backup_item['item_name']}'", "INFO: separator_item_restored")
    
    if is_gruppenversand:
        frappe.log_error(f"✅ Gruppenversand erkannt - Adressvalidierung für Delivery Note {doc.name if hasattr(doc, 'name') else '(neu)'} beim Erstellen deaktiviert", "INFO: delivery_note_pre_insert_validation_disabled")
    else:
        frappe.log_error(f"✅ Validierungen für Delivery Note {doc.name if hasattr(doc, 'name') else '(neu)'} beim Erstellen deaktiviert", "INFO: delivery_note_pre_insert_validation_disabled")


def before_submit_delivery_note(doc, method):
    """
    Hook für Delivery Note before_submit
    Stellt sicher, dass alle Validierungen deaktiviert sind und alle Items 
    "Allow Zero Valuation" aktiviert haben.
    
    WICHTIG: Diese Funktion wird VOR dem Buchen (Submit) aufgerufen und stellt
    sicher, dass alle Validierungen auch zu diesem Zeitpunkt noch deaktiviert sind.
    Dies ist notwendig, da ERPNext zu verschiedenen Zeitpunkten validiert.
    
    ZUM KOMPLETTEN DEAKTIVIEREN:
    1. Kommentiere alle Flag-Zuweisungen aus (Zeilen 125-128)
    2. Kommentiere den "Allow Zero Valuation" Block aus (Zeilen 131-136)
    3. Kommentiere die Methoden-Überschreibung aus (Zeilen 139-147)
    4. Kommentiere diese Funktion in hooks.py aus (Zeile 171)
    """
    if doc.doctype != "Delivery Note":
        return
    
    # ===================================================================================
    # ABSCHNITT 1: DEAKTIVIERUNG VON VALIDIERUNGEN VOR DEM BUCHEN
    # ===================================================================================
    # Diese Flags werden VOR dem Submit gesetzt, um sicherzustellen, dass alle
    # Validierungen auch zu diesem späten Zeitpunkt noch deaktiviert sind.
    # ERPNext führt Validierungen zu verschiedenen Zeitpunkten durch, daher ist
    # diese doppelte Absicherung notwendig.
    #
    # DEAKTIVIERUNG: Kommentiere die folgenden 4 Zeilen aus (Zeilen 125-128)
    # ===================================================================================
    doc.flags.ignore_warehouse_validation = True  # Ignoriert Lager-Validierung
    doc.flags.ignore_stock_validation = True      # Ignoriert Bestands-Validierung
    doc.flags.ignore_gl_entries = True            # KEINE Buchhaltungseinträge erstellen
    doc.flags.ignore_valuation_rate = True        # Ignoriere Bewertungsrate-Validierung
    
    # ===================================================================================
    # ABSCHNITT 2: "ALLOW ZERO VALUATION" FÜR ALLE ITEMS VOR DEM BUCHEN
    # ===================================================================================
    # Setzt erneut "Allow Zero Valuation" für alle Items, falls diese Einstellung
    # zwischen validate und submit verloren gegangen ist.
    #
    # DEAKTIVIERUNG: Kommentiere den gesamten if-Block aus (Zeilen 131-136)
    # ===================================================================================
    if hasattr(doc, 'items') and doc.items:
        for item in doc.items:
            if hasattr(item, 'allow_zero_valuation_rate'):
                item.allow_zero_valuation_rate = 1
            elif hasattr(item, 'allow_zero_valuation'):
                item.allow_zero_valuation = 1
    
    # ===================================================================================
    # ABSCHNITT 3: ÜBERSCHREIBUNG VON VALIDIERUNGSMETHODEN
    # ===================================================================================
    # Versucht, die Validierungsmethoden für Bewertungsrate zu überschreiben.
    # Dies ist eine zusätzliche Sicherheitsmaßnahme, falls ERPNext die Validierung
    # trotz der Flags noch durchführt.
    #
    # DEAKTIVIERUNG: Kommentiere den gesamten Block aus (Zeilen 139-147)
    # HINWEIS: Diese Überschreibung ist optional, da die Flags normalerweise
    #          ausreichen sollten
    # ===================================================================================
    def safe_validate_valuation_rate(self, *args, **kwargs):
        frappe.log_error(f"✅ Überspringe Bewertungsrate-Validierung für Delivery Note {self.name}", "INFO: skip_valuation_rate_validation")
        pass
    
    # Versuche die Methode zu überschreiben, falls sie existiert
    if hasattr(doc, 'validate_valuation_rate'):
        doc.validate_valuation_rate = types.MethodType(safe_validate_valuation_rate, doc)
    if hasattr(doc, 'validate_item_valuation_rate'):
        doc.validate_item_valuation_rate = types.MethodType(safe_validate_valuation_rate, doc)


def on_submit_delivery_note(doc, method):
    """
    Hook für Delivery Note on_submit
    Stellt sicher, dass Webhooks auch für Gruppenversand-Lieferscheine ausgelöst werden
    
    PROBLEM: Frappe's Webhook-System hat eine Bedingung, die Gruppenversand-Lieferscheine
    (customer == "Gruppenversand") ausschließt. Diese Funktion triggert den Webhook
    DIREKT über HTTP-Request und umgeht die Bedingungsprüfung komplett.
    """
    if doc.doctype != "Delivery Note":
        return
    
    # Prüfe ob es ein Gruppenversand-Lieferschein ist
    is_gruppenversand = doc.customer == "Gruppenversand"
    
    if is_gruppenversand:
        frappe.log_error(
            f"🔔 Gruppenversand-Lieferschein {doc.name} gebucht - triggere Webhook direkt",
            "INFO: group_shipping_webhook_trigger"
        )
        
        try:
            # Lade alle aktiven Webhooks für Delivery Note on_submit (nur Basisfelder)
            webhooks = frappe.get_all(
                "Webhook",
                filters={
                    "webhook_doctype": "Delivery Note",
                    "webhook_docevent": "on_submit",
                    "enabled": 1
                },
                fields=["name", "request_url"]
            )
            
            if not webhooks:
                frappe.log_error(
                    f"Keine Webhooks für Delivery Note on_submit gefunden",
                    "WARNING: no_webhooks_found"
                )
                return
            
            frappe.log_error(
                f"Gefunden: {len(webhooks)} Webhook(s) für Delivery Note on_submit - triggere direkt",
                "INFO: webhooks_found"
            )
            
            # Triggere jeden Webhook DIREKT über HTTP-Request (umgeht Bedingungsprüfung)
            for webhook in webhooks:
                try:
                    frappe.log_error(
                        f"Versuche Webhook {webhook.name} zu triggern...",
                        "INFO: webhook_attempt"
                    )
                    trigger_webhook_directly(doc, webhook)
                except Exception as e:
                    frappe.log_error(
                        f"Fehler beim Triggern des Webhooks {webhook.name}: {str(e)}\n{frappe.get_traceback()}",
                        "ERROR: webhook_trigger_failed"
                    )
                        
        except Exception as e:
            frappe.log_error(
                f"Fehler beim Prüfen von Webhooks: {str(e)}\n{frappe.get_traceback()}",
                "ERROR: webhook_check_failed"
            )


def trigger_webhook_directly(doc, webhook):
    """
    Triggert einen Webhook DIREKT über HTTP-Request.
    Umgeht Frappe's Webhook-Bedingungsprüfung komplett.
    """
    import json
    import hashlib
    import hmac
    
    try:
        frappe.log_error(
            f"🔧 Lade Webhook-Dokument {webhook.name}",
            "DEBUG: webhook_load_doc"
        )
        
        # Lade vollständiges Webhook-Dokument
        webhook_doc = frappe.get_doc("Webhook", webhook.name)
        
        frappe.log_error(
            f"🔧 Webhook-URL: {webhook_doc.request_url}",
            "DEBUG: webhook_url"
        )
        
        # Erstelle Webhook-Daten basierend auf der Webhook-Konfiguration
        webhook_data = {}
        
        # Füge Standard-Felder hinzu
        webhook_data["doctype"] = doc.doctype
        webhook_data["name"] = doc.name
        webhook_data["event"] = "on_submit"
        
        # Füge alle Felder des Dokuments hinzu
        doc_dict = doc.as_dict()
        webhook_data["doc"] = doc_dict
        
        # Füge spezifische Webhook-Daten hinzu, falls konfiguriert
        if hasattr(webhook_doc, 'webhook_data') and webhook_doc.webhook_data:
            for field in webhook_doc.webhook_data:
                if hasattr(field, 'fieldname') and field.fieldname and hasattr(doc, field.fieldname):
                    key = getattr(field, 'key', None) or field.fieldname
                    webhook_data[key] = doc.get(field.fieldname)
        
        # Erstelle Headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Füge konfigurierte Headers hinzu
        if hasattr(webhook_doc, 'webhook_headers') and webhook_doc.webhook_headers:
            for header in webhook_doc.webhook_headers:
                if hasattr(header, 'key') and header.key:
                    headers[header.key] = getattr(header, 'value', '') or ""
        
        # Füge Webhook-Secret als Header hinzu, falls konfiguriert
        if hasattr(webhook_doc, 'webhook_secret') and webhook_doc.webhook_secret:
            # Erstelle HMAC-Signatur
            payload_str = json.dumps(webhook_data, sort_keys=True, default=str)
            signature = hmac.new(
                webhook_doc.webhook_secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Frappe-Webhook-Signature"] = signature
        
        frappe.log_error(
            f"📤 Sende Webhook-Request an {webhook_doc.request_url} für {doc.name}",
            "INFO: webhook_request_sending"
        )
        
        # Verwende Frappe's eingebaute HTTP-Funktionen
        try:
            from frappe.integrations.utils import make_post_request
            
            response = make_post_request(
                webhook_doc.request_url,
                data=json.dumps(webhook_data, default=str),
                headers=headers
            )
            
            frappe.log_error(
                f"✅ Webhook {webhook.name} erfolgreich ausgelöst für {doc.name} (Response: {str(response)[:200]})",
                "SUCCESS: webhook_triggered"
            )
            
            # Erstelle Webhook Request Log für Nachverfolgung
            try:
                log = frappe.new_doc("Webhook Request Log")
                log.webhook = webhook.name
                log.reference_doctype = doc.doctype
                log.reference_document = doc.name
                log.response_code = "200"
                log.response = str(response)[:1000] if response else ""
                log.flags.ignore_permissions = True
                log.insert()
                frappe.db.commit()
                frappe.log_error(
                    f"📝 Webhook-Log erstellt für {doc.name}",
                    "INFO: webhook_log_created"
                )
            except Exception as log_error:
                frappe.log_error(
                    f"Webhook-Log konnte nicht erstellt werden: {str(log_error)}\n{frappe.get_traceback()}",
                    "WARNING: webhook_log_failed"
                )
                
        except ImportError:
            # Fallback: Verwende requests direkt
            import requests
            
            response = requests.post(
                webhook_doc.request_url,
                json=webhook_data,
                headers=headers,
                timeout=30
            )
            
            # Logge Ergebnis
            if response.status_code >= 200 and response.status_code < 300:
                frappe.log_error(
                    f"✅ Webhook {webhook.name} erfolgreich ausgelöst für {doc.name} (Status: {response.status_code})",
                    "SUCCESS: webhook_triggered"
                )
            else:
                frappe.log_error(
                    f"⚠️ Webhook {webhook.name} für {doc.name} - Status: {response.status_code}",
                    "WARNING: webhook_unexpected_status"
                )
            
    except Exception as e:
        frappe.log_error(
            f"❌ Webhook {webhook.name} Fehler für {doc.name}: {str(e)}\n{frappe.get_traceback()}",
            "ERROR: webhook_general_error"
        )
