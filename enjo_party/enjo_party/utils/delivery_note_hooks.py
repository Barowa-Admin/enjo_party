# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
import types

# PATCH: Verhindere mehrfache Webhook-Auslösung für dasselbe Dokument
_webhook_patch_applied = False

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
            
            # WICHTIG: Stelle sicher, dass Trenner-Items immer 0.001 haben (für ERPNext-Validierung)
            # ERPNext erlaubt keine Menge von 0, daher müssen Trenner-Items mindestens 0.001 haben
            if item.item_code == "---":
                if not item.qty or item.qty == 0:
                    item.qty = 0.001
                if not item.stock_qty or item.stock_qty == 0:
                    item.stock_qty = 0.001
    
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
    
    # WICHTIG: Stelle sicher, dass der Customer "Gruppenversand" existiert
    # Frappe's Webhook-System könnte den Webhook überspringen, wenn der Customer nicht existiert
    if is_gruppenversand:
        if not frappe.db.exists("Customer", "Gruppenversand"):
            frappe.log_error(
                "⚠️ Customer 'Gruppenversand' existiert nicht - erstelle ihn",
                "WARNING: gruppenversand_customer_missing"
            )
            try:
                # Erstelle den Customer "Gruppenversand" falls er nicht existiert
                gruppenversand_customer = frappe.get_doc({
                    "doctype": "Customer",
                    "customer_name": "Gruppenversand",
                    "customer_type": "Company",
                    "customer_group": frappe.defaults.get_global_default("customer_group") or "All Customer Groups",
                    "territory": frappe.defaults.get_global_default("territory") or "All Territories"
                })
                gruppenversand_customer.insert(ignore_permissions=True)
                frappe.log_error(
                    "✅ Customer 'Gruppenversand' erstellt",
                    "SUCCESS: gruppenversand_customer_created"
                )
            except Exception as e:
                frappe.log_error(
                    f"Fehler beim Erstellen des Customers 'Gruppenversand': {str(e)}",
                    "ERROR: gruppenversand_customer_creation_failed"
                )
    
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
        
        # WICHTIG: ignore_validate NICHT setzen, da dies die Webhook-Auslösung verhindern könnte!
        # Nur spezifische Validierungen deaktivieren, nicht die gesamte Validierung
        # doc.flags.ignore_validate = True  # DEAKTIVIERT - verhindert Webhook-Auslösung!
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
            
            # WICHTIG: Stelle sicher, dass Trenner-Items immer 0.001 haben (für ERPNext-Validierung)
            # ERPNext erlaubt keine Menge von 0, daher müssen Trenner-Items mindestens 0.001 haben
            if item.item_code == "---":
                if not item.qty or item.qty == 0:
                    item.qty = 0.001
                if not item.stock_qty or item.stock_qty == 0:
                    item.stock_qty = 0.001


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
    # WICHTIG: ignore_validate NICHT setzen, da dies die Webhook-Auslösung verhindern könnte!
    if is_gruppenversand:
        # doc.flags.ignore_validate = True  # DEAKTIVIERT - verhindert Webhook-Auslösung!
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
    
    # PATCH: Verhindere mehrfache Webhook-Auslösung für dasselbe Dokument
    # Wird VOR dem Submit angewendet, damit es vor Frappe's Webhook-Auslösung greift
    global _webhook_patch_applied
    
    if not _webhook_patch_applied:
        try:
            from frappe.integrations.doctype.webhook.webhook import enqueue_webhook as original_enqueue_webhook
            
            # Track bereits getriggerte Webhooks
            if not hasattr(frappe.local, '_webhook_triggered'):
                frappe.local._webhook_triggered = set()
            
            def patched_enqueue_webhook(doc=None, webhook=None, **kwargs):
                """Verhindert mehrfache Webhook-Auslösung für dasselbe Dokument"""
                # DEBUG: Logge ALLE Aufrufe, um zu sehen was passiert
                if doc and doc.doctype == "Delivery Note":
                    webhook_info = "unknown"
                    if isinstance(webhook, dict):
                        webhook_info = webhook.get("name", "dict")
                    elif hasattr(webhook, "name"):
                        webhook_info = webhook.name
                    elif isinstance(webhook, str):
                        webhook_info = webhook
                    
                    frappe.log_error(
                        f"🔍 PATCH: enqueue_webhook aufgerufen für {doc.name} (Customer: {doc.customer}, Webhook: {webhook_info})",
                        "DEBUG: webhook_patch_called"
                    )
                
                if doc and webhook and doc.doctype == "Delivery Note":
                    # Extrahiere Webhook-Name für Tracking
                    webhook_name = webhook
                    if isinstance(webhook, dict):
                        webhook_name = webhook.get("name", "unknown")
                    elif hasattr(webhook, "name"):
                        webhook_name = webhook.name
                    
                    doc_key = f"{doc.doctype}:{doc.name}:{webhook_name}"
                    
                    # Wenn dieser Webhook bereits für dieses Dokument getriggert wurde, überspringe
                    if doc_key in frappe.local._webhook_triggered:
                        frappe.log_error(
                            f"⏭️ Webhook {webhook_name} für {doc.name} wurde bereits getriggert - überspringe mehrfache Auslösung",
                            "INFO: webhook_already_triggered"
                        )
                        return
                    
                    # Markiere als getriggert
                    frappe.local._webhook_triggered.add(doc_key)
                    
                    frappe.log_error(
                        f"✅ Webhook {webhook_name} für {doc.name} wird getriggert (Customer: {doc.customer})",
                        "INFO: webhook_triggered_once"
                    )
                
                # Rufe die originale Funktion auf (ohne method Parameter)
                return original_enqueue_webhook(doc=doc, webhook=webhook, **kwargs)
            
            # PATCH: Überschreibe die Funktion
            import frappe.integrations.doctype.webhook.webhook as webhook_module
            webhook_module.enqueue_webhook = patched_enqueue_webhook
            _webhook_patch_applied = True
            
            frappe.log_error("✅ Webhook-System gepatcht in before_submit - mehrfache Auslösungen werden verhindert", "INFO: webhook_patch_applied")
            
        except Exception as e:
            frappe.log_error(
                f"Fehler beim Patchen des Webhook-Systems: {str(e)}\n{frappe.get_traceback()}",
                "WARNING: webhook_patch_failed"
            )
    
    
    # ===================================================================================
    # ABSCHNITT 1: DEAKTIVIERUNG VON VALIDIERUNGEN VOR DEM BUCHEN
    # ===================================================================================
    # Diese Flags werden VOR dem Submit gesetzt, um sicherzustellen, dass alle
    # Validierungen auch zu diesem Zeitpunkt noch deaktiviert sind.
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
            
            # WICHTIG: Überspringe Qty-Validierung für Trenner-Items
            # ERPNext prüft standardmäßig, ob qty > 0 ist, aber Trenner-Items haben 0.001
            if item.item_code == "---":
                # Überschreibe die validate_qty Methode für dieses Item
                def safe_validate_qty(self, *args, **kwargs):
                    """Überspringt Qty-Validierung für Trenner-Items"""
                    pass
                
                # Versuche die Methode zu überschreiben, falls sie existiert
                if hasattr(item, 'validate_qty'):
                    item.validate_qty = types.MethodType(safe_validate_qty, item)
                
                # Stelle sicher, dass die Menge mindestens 0.001 ist (für ERPNext-Validierung)
                if not item.qty or item.qty == 0:
                    item.qty = 0.001
                    item.stock_qty = 0.001
    
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
    
    # WICHTIG: Stelle sicher, dass Trenner-Items immer 0.001 haben (für ERPNext-Validierung)
    # ERPNext erlaubt keine Menge von 0, daher müssen Trenner-Items mindestens 0.001 haben
    if hasattr(doc, 'items') and doc.items:
        for item in doc.items:
            if item.item_code == "---":
                if not item.qty or item.qty == 0:
                    item.qty = 0.001
                if not item.stock_qty or item.stock_qty == 0:
                    item.stock_qty = 0.001
    
    # ===================================================================================
    # ABSCHNITT 4: KORREKTUR DER DATEN FÜR GRUPPENVERSAND-LIEFERSCHEINE
    # ===================================================================================
    # Korrigiert total_net_weight und shipping_address_name für Gruppenversand-Lieferscheine
    # WICHTIG: Muss VOR dem Submit passieren, damit der Webhook die korrekten Daten bekommt
    # ===================================================================================
    is_gruppenversand = doc.customer == "Gruppenversand"
    
    if is_gruppenversand:
        try:
            frappe.log_error(
                f"⚙️ Korrigiere Daten für Gruppenversand-Lieferschein {doc.name} vor Webhook-Trigger",
                "INFO: gruppenversand_data_correction"
            )
            
            # 1. total_net_weight berechnen (Summe aller Items, außer Trenner)
            # WICHTIG: Hole das Gewicht aus dem Sales Order, da es beim submit() verloren gehen kann
            total_weight = 0.0
            
            # Finde zuerst den Sales Order
            sales_order_name = None
            for item in doc.items:
                if hasattr(item, 'against_sales_order') and item.against_sales_order:
                    sales_order_name = item.against_sales_order
                    break
                elif hasattr(item, 'sales_order') and item.sales_order:
                    sales_order_name = item.sales_order
                    break
            
            sales_order = None
            if sales_order_name:
                try:
                    sales_order = frappe.get_cached_doc("Sales Order", sales_order_name)
                except:
                    pass
            
            for item in doc.items:
                if item.item_code == "---":
                    continue
                
                item_weight = 0.0
                qty = frappe.utils.flt(item.qty)
                
                # Versuche 1: Gewicht aus Delivery Note Item
                if hasattr(item, 'net_weight') and item.net_weight is not None:
                    item_weight = frappe.utils.flt(item.net_weight) * qty
                    frappe.log_error(
                        f"  Item {item.item_code}: Gewicht aus DN Item: {item.net_weight}g * {qty} = {item_weight}g",
                        "DEBUG: weight_from_dn_item"
                    )
                # Versuche 2: Gewicht aus Sales Order Item
                elif sales_order:
                    # Finde das entsprechende Sales Order Item
                    so_item = None
                    if hasattr(item, 'sales_order_item') and item.sales_order_item:
                        # Versuche über sales_order_item Referenz
                        for so_item_candidate in sales_order.items:
                            if so_item_candidate.name == item.sales_order_item:
                                so_item = so_item_candidate
                                break
                    else:
                        # Fallback: Suche nach item_code und qty
                        for so_item_candidate in sales_order.items:
                            if so_item_candidate.item_code == item.item_code:
                                so_item = so_item_candidate
                                break
                    
                    if so_item and hasattr(so_item, 'net_weight') and so_item.net_weight:
                        item_weight = frappe.utils.flt(so_item.net_weight) * qty
                        frappe.log_error(
                            f"  Item {item.item_code}: Gewicht aus SO Item: {so_item.net_weight}g * {qty} = {item_weight}g",
                            "DEBUG: weight_from_so_item"
                        )
                    elif sales_order and hasattr(sales_order, 'total_net_weight') and sales_order.total_net_weight:
                        # Fallback: Verwende total_net_weight vom Sales Order (proportional)
                        total_so_qty = sum(frappe.utils.flt(so_item.qty) for so_item in sales_order.items if so_item.item_code != "---")
                        if total_so_qty > 0:
                            item_weight = (frappe.utils.flt(sales_order.total_net_weight) / total_so_qty) * qty
                            frappe.log_error(
                                f"  Item {item.item_code}: Gewicht proportional aus SO total: {item_weight}g",
                                "DEBUG: weight_proportional_from_so"
                            )
                # Versuche 3: Gewicht direkt aus Item-Dokument
                if item_weight == 0.0:
                    try:
                        item_doc = frappe.get_cached_doc("Item", item.item_code)
                        if hasattr(item_doc, 'weight_per_unit') and item_doc.weight_per_unit:
                            weight_per_unit = frappe.utils.flt(item_doc.weight_per_unit)
                            item_weight = weight_per_unit * qty
                            
                            # Umrechnung auf Gramm, falls nötig
                            if hasattr(item_doc, 'weight_uom') and item_doc.weight_uom:
                                if item_doc.weight_uom.lower() in ['kg', 'kilogram']:
                                    item_weight = item_weight * 1000  # kg zu g
                            
                            frappe.log_error(
                                f"  Item {item.item_code}: Gewicht aus Item-Dokument: {weight_per_unit} {getattr(item_doc, 'weight_uom', 'g')} * {qty} = {item_weight}g",
                                "DEBUG: weight_from_item_doc"
                            )
                    except Exception as e:
                        frappe.log_error(
                            f"⚠️ Konnte Gewicht für Item {item.item_code} nicht berechnen: {str(e)}",
                            "WARNING: weight_calc_failed"
                        )
                
                total_weight += item_weight
            
            doc.total_net_weight = total_weight
            
            # WICHTIG: Speichere das Gewicht direkt in der DB, damit es beim submit() nicht verloren geht
            try:
                frappe.db.set_value("Delivery Note", doc.name, "total_net_weight", total_weight, update_modified=False)
                frappe.log_error(
                    f"✅ total_net_weight in DB gespeichert: {total_weight}g",
                    "INFO: weight_saved_to_db"
                )
            except Exception as e:
                frappe.log_error(
                    f"⚠️ Konnte Gewicht nicht in DB speichern: {str(e)}",
                    "WARNING: weight_db_save_failed"
                )
            
            frappe.log_error(
                f"✅ total_net_weight korrigiert zu: {doc.total_net_weight}g",
                "INFO: weight_corrected"
            )
            
            # 2. shipping_address_name und shipping_address korrigieren
            # sales_order_name wurde bereits oben ermittelt
            if sales_order_name and sales_order:
                sales_order = frappe.get_doc("Sales Order", sales_order_name)
                if sales_order.customer == "Gruppenversand":
                    # Dies ist der "Master"-Sales Order für den Gruppenversand
                    # Die shipping_address_name sollte die des tatsächlichen Empfängers sein
                    doc.shipping_address_name = sales_order.shipping_address_name
                    # Lade die formatierte Adresse
                    if doc.shipping_address_name:
                        try:
                            address_doc = frappe.get_doc("Address", doc.shipping_address_name)
                            doc.shipping_address = address_doc.get_display()
                        except Exception as e:
                            # Fallback: Verwende die Adresse vom Sales Order
                            doc.shipping_address = sales_order.shipping_address or ""
                            frappe.log_error(
                                f"⚠️ Konnte Adresse nicht formatieren: {str(e)}",
                                "WARNING: address_format_failed"
                            )
                    doc.customer_name = sales_order.customer_name  # Kundenname des Empfängers
                    frappe.log_error(
                        f"✅ Versandadresse korrigiert zu: {doc.shipping_address_name} (Customer: {doc.customer_name})",
                        "INFO: address_corrected"
                    )
            
            # WICHTIG: Speichere die Änderungen am Doc, damit sie für den Webhook verfügbar sind
            # Die Änderungen sind im Speicher und werden beim Submit gespeichert
            
        except Exception as e:
            frappe.log_error(
                f"❌ Fehler bei der Datenkorrektur für Gruppenversand-Lieferschein {doc.name}: {str(e)}\n{frappe.get_traceback()}",
                "ERROR: gruppenversand_data_correction_error"
            )

def on_submit_delivery_note(doc, method):
    """
    Hook für Delivery Note on_submit
    Triggert Webhooks explizit für Gruppenversand-Lieferscheine, da Frappe's Standard-System
    diese manchmal nicht automatisch auslöst.
    """
    if doc.doctype != "Delivery Note":
        return
    
    # Prüfe ob es ein Gruppenversand-Lieferschein ist
    is_gruppenversand = doc.customer == "Gruppenversand"
    
    if is_gruppenversand:
        try:
            frappe.log_error(
                f"🔔 Gruppenversand-Lieferschein {doc.name} gebucht - prüfe Webhook-Status",
                "INFO: gruppenversand_webhook_check"
            )
            
            # WICHTIG: Prüfe und korrigiere das Gewicht NACH dem Submit
            # Reload das Dokument, um sicherzustellen, dass wir die neuesten Daten haben
            doc.reload()
            
            if not doc.total_net_weight or doc.total_net_weight == 0.0:
                frappe.log_error(
                    f"⚠️ Gewicht fehlt nach submit() - korrigiere jetzt",
                    "WARNING: weight_missing_after_submit"
                )
                
                # Hole das Gewicht aus dem Sales Order
                sales_order_name = None
                for item in doc.items:
                    if hasattr(item, 'against_sales_order') and item.against_sales_order:
                        sales_order_name = item.against_sales_order
                        break
                    elif hasattr(item, 'sales_order') and item.sales_order:
                        sales_order_name = item.sales_order
                        break
                
                if sales_order_name:
                    try:
                        sales_order = frappe.get_cached_doc("Sales Order", sales_order_name)
                        if sales_order.total_net_weight:
                            doc.total_net_weight = sales_order.total_net_weight
                            frappe.db.set_value("Delivery Note", doc.name, "total_net_weight", sales_order.total_net_weight, update_modified=False)
                            frappe.log_error(
                                f"✅ Gewicht nach submit() korrigiert: {doc.total_net_weight}g (aus Sales Order)",
                                "INFO: weight_corrected_after_submit"
                            )
                    except Exception as e:
                        frappe.log_error(
                            f"⚠️ Konnte Gewicht nach submit() nicht korrigieren: {str(e)}",
                            "WARNING: weight_correction_failed_after_submit"
                        )
            
            # Warte kurz, damit Frappe's Standard-Webhook-System Zeit hat zu triggern
            import time
            time.sleep(0.5)
            
            # Prüfe, ob Webhooks bereits getriggert wurden
            # Wenn nicht, triggere sie explizit
            from frappe.integrations.doctype.webhook.webhook import enqueue_webhook
            
            # Hole alle aktiven Webhooks für Delivery Note on_submit
            webhooks = frappe.get_all(
                "Webhook",
                filters={
                    "webhook_doctype": "Delivery Note",
                    "webhook_docevent": "on_submit",
                    "enabled": 1
                },
                fields=["name", "condition", "request_url"]
            )
            
            if not webhooks:
                frappe.log_error(
                    f"⚠️ Keine Webhooks gefunden für Delivery Note on_submit",
                    "WARNING: no_webhooks_found"
                )
                return
            
            frappe.log_error(
                f"✅ {len(webhooks)} Webhook(s) gefunden - triggere jetzt explizit",
                "INFO: webhooks_found_explicit_trigger"
            )
            
            # Triggere jeden Webhook explizit
            for webhook_data in webhooks:
                webhook_name = webhook_data.name
                condition = webhook_data.get("condition", "")
                
                # Prüfe Bedingung, falls vorhanden
                should_trigger = True
                if condition:
                    try:
                        should_trigger = frappe.safe_eval(condition, {"doc": doc, "frappe": frappe})
                    except Exception as e:
                        frappe.log_error(
                            f"⚠️ Fehler beim Auswerten der Webhook-Bedingung für {webhook_name}: {str(e)}",
                            "WARNING: webhook_condition_error"
                        )
                        should_trigger = True  # Bei Fehler trotzdem triggern
                
                if should_trigger:
                    try:
                        # Triggere den Webhook explizit
                        enqueue_webhook(doc=doc, webhook={"name": webhook_name})
                        
                        frappe.log_error(
                            f"✅ Webhook {webhook_name} explizit getriggert für Gruppenversand-Lieferschein {doc.name}",
                            "SUCCESS: webhook_triggered_explicit"
                        )
                    except Exception as e:
                        frappe.log_error(
                            f"❌ Fehler beim Triggern des Webhooks {webhook_name} für {doc.name}: {str(e)}\n{frappe.get_traceback()}",
                            "ERROR: webhook_trigger_failed"
                        )
                else:
                    frappe.log_error(
                        f"⏭️ Webhook {webhook_name} nicht getriggert - Bedingung nicht erfüllt: {condition}",
                        "DEBUG: webhook_condition_not_met"
                    )
        
        except Exception as e:
            frappe.log_error(
                f"💥 Allgemeiner Fehler im on_submit_delivery_note Hook: {str(e)}\n{frappe.get_traceback()}",
                "ERROR: on_submit_hook_general_error"
            )



