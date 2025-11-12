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
    
    # Prüfe, ob es sich um eine fremde Lieferadresse handelt
    is_foreign_shipping = False
    
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
    
    # Deaktiviere Validierungen für fremde Lieferadressen
    if is_foreign_shipping:
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
