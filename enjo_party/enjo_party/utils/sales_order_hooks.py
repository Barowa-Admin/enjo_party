import frappe
from frappe import _
import types

# === AUTO SALES INVOICE TEMPORÄR DEAKTIVIERT ===
# Schalter für automatische Rechnungserstellung über Hooks (True = aktiv, False = deaktiviert)
ENABLE_AUTO_SALES_INVOICE_HOOKS = True  # Wieder aktiviert!
# Schalter für automatische Erstellung
# Lieferschein (Delivery Note) separat aktivierbar
ENABLE_AUTO_DELIVERY_NOTE = True
# Packliste (Pick List) separat aktivierbar
ENABLE_AUTO_PICKLIST = True


def auto_create_and_submit_sales_invoice(doc, method):
    """
    Hook für Sales Order on_submit
    Erstellt automatisch eine Sales Invoice und reicht sie ein
    """
    # TEMPORÄR DEAKTIVIERT: Automatische Rechnungserstellung über Hooks
    if not ENABLE_AUTO_SALES_INVOICE_HOOKS:
        frappe.log_error("AUTO SALES INVOICE HOOKS ist aktuell deaktiviert (ENABLE_AUTO_SALES_INVOICE_HOOKS = False)", "INFO: auto_invoice_hooks_deactivated")
        return
    
    try:
        frappe.log_error(f"Starting auto invoice creation for Sales Order: {doc.name}", "INFO: auto_invoice_start")
        
        # KORRIGIERT: Prüfe nur nach Sales Invoices die direkt zu diesem Sales Order gehören
        existing_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": ["!=", 2],
                "sales_order": doc.name  # Nur für diesen spezifischen Sales Order
            },
            fields=["name"],
            limit=1
        )
        
        if existing_invoices:
            frappe.log_error(f"Sales Invoice already exists for Sales Order {doc.name}: {existing_invoices[0]['name']}", "INFO: invoice_exists")
            return
        
        frappe.log_error(f"No existing invoice found - creating new one for Sales Order {doc.name}", "INFO: creating_new")
        
        # Hole Standard-Einstellungen
        company = doc.company or frappe.defaults.get_user_default("Company")
        
        # Erstelle Sales Invoice basierend auf Sales Order
        # === NEU: Mapper-Funktion verwenden, damit Steuern & weitere Felder korrekt übernommen werden ===
        try:
            from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
        except Exception as e:
            frappe.log_error(f"Import make_sales_invoice fehlgeschlagen: {str(e)}", "ERROR: mapper_import_failed")
            raise

        invoice = make_sales_invoice(doc.name)  # noch nicht gespeichert

        # Zusätzliche/benutzerdefinierte Felder anpassen
        invoice.remarks = f"Automatisch erstellt aus Sales Order: {doc.name}"
        invoice.sales_order = doc.name  # Custom-Feld für Duplikat-Prüfung

        # Custom Party/Sammelbestellung Referenz übernehmen
        if hasattr(doc, "custom_party_reference") and doc.custom_party_reference:
            try:
                # Prüfe ob es eine Party oder Sammelbestellung ist
                if frappe.db.exists("Party", doc.custom_party_reference):
                    party_doc = frappe.get_doc("Party", doc.custom_party_reference)
                    if party_doc.docstatus != 2:
                        invoice.custom_party_reference = doc.custom_party_reference
                    else:
                        frappe.log_error(f"Party {doc.custom_party_reference} ist cancelled – Referenz ignoriert", "WARNING: cancelled_party")
                elif frappe.db.exists("Sammelbestellung", doc.custom_party_reference):
                    sammelbestellung_doc = frappe.get_doc("Sammelbestellung", doc.custom_party_reference)
                    if sammelbestellung_doc.docstatus != 2:
                        invoice.custom_party_reference = doc.custom_party_reference
                    else:
                        frappe.log_error(f"Sammelbestellung {doc.custom_party_reference} ist cancelled – Referenz ignoriert", "WARNING: cancelled_sammelbestellung")
                else:
                    frappe.log_error(f"Weder Party noch Sammelbestellung {doc.custom_party_reference} gefunden", "WARNING: reference_not_found")
            except Exception as e:
                frappe.log_error(f"Fehler beim Laden der Referenz {doc.custom_party_reference}: {str(e)}", "WARNING: reference_load_error")

        if hasattr(doc, "custom_calculated_shipping_cost") and doc.custom_calculated_shipping_cost:
            invoice.custom_calculated_shipping_cost = doc.custom_calculated_shipping_cost

        # Preise exakt wie im Sales Order setzen und Preisregeln ignorieren
        invoice.flags.ignore_pricing_rule = True
        invoice.flags.ignore_item_price = True

        for i, invoice_item in enumerate(invoice.items):
            so_item = doc.items[i]
            invoice_item.rate = so_item.rate
            invoice_item.price_list_rate = so_item.rate
            invoice_item.base_rate = so_item.rate
            invoice_item.base_price_list_rate = so_item.rate
            invoice_item.amount = so_item.amount
            invoice_item.base_amount = so_item.amount
            invoice_item.flags.ignore_pricing_rule = True

        # Fehlende Felder füllen & Steuern/Totals neu berechnen
        invoice.run_method("set_missing_values")
        invoice.calculate_taxes_and_totals()

        # === ADRESS-VALIDIERUNG DEAKTIVIEREN FÜR PARTY/SAMMELBESTELLUNG-RECHNUNGEN ===
        # Prüfe, ob es sich um eine Party- oder Sammelbestellung-Rechnung handelt
        if hasattr(doc, "custom_party_reference") and doc.custom_party_reference:
            frappe.log_error(f"🎉 Party/Sammelbestellung-Invoice erkannt: {invoice.name if hasattr(invoice, 'name') else 'NEW'} - Validierung angepasst (DATEV-sicher)", "INFO: party_invoice_detected")
            
            # Überschreibe die Adress-Validierungsmethoden
            def safe_validate_party_address(self, party, party_type, billing_address, shipping_address=None):
                """Überspringe die Party-Adress-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_party_address für {party} (Type: {party_type}, Billing: {billing_address}, Shipping: {shipping_address})", "INFO: skip_party_address_validation")
                pass
            
            def safe_validate_party_address_and_contact(self):
                """Überspringe die komplette Party-Adress- und Kontakt-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_party_address_and_contact für {self.customer}", "INFO: skip_party_validation")
                pass
            
            def safe_validate_shipping_address(self):
                """Überspringe die Versandadress-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_shipping_address für {self.customer}", "INFO: skip_shipping_validation")
                pass
            
            def safe_validate_billing_address(self):
                """Überspringe die Rechnungsadress-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_billing_address für {self.customer}", "INFO: skip_billing_validation")
                pass
            
            # Überschreibe nur die Adress-Validierungsmethoden (wie bei Party)
            invoice.validate_party_address = types.MethodType(safe_validate_party_address, invoice)
            invoice.validate_party_address_and_contact = types.MethodType(safe_validate_party_address_and_contact, invoice)
            invoice.validate_shipping_address = types.MethodType(safe_validate_shipping_address, invoice)
            invoice.validate_billing_address = types.MethodType(safe_validate_billing_address, invoice)
            
            frappe.log_error(f"✅ Adressvalidierung für automatische Invoice deaktiviert", "SUCCESS: auto_invoice_address_validation_bypassed")

        # Jetzt speichern (nicht submitten)
        invoice.insert()
        frappe.log_error(f"Sales Invoice created: {invoice.name}", "INFO: invoice_created")

        # === NEU: Lieferschein und/oder Packliste erzeugen ===

        # 1) Lieferschein
        if ENABLE_AUTO_DELIVERY_NOTE:
            try:
                dn = create_delivery_note_for_sales_order(doc)
                if dn:
                    frappe.log_error(f"Delivery Note created: {dn.name}", "INFO: delivery_note_created")
            except Exception as e:
                frappe.log_error(f"Error creating Delivery Note for SO {doc.name}: {str(e)}", "ERROR: delivery_note_failed")

        # 2) Packliste
        if ENABLE_AUTO_PICKLIST:
            try:
                from enjo_party.enjo_party.utils.sales_invoice_hooks import auto_create_picklist_from_invoice
                auto_create_picklist_from_invoice(invoice, "auto")
            except Exception as e:
                frappe.log_error(f"Error creating Pick List for Invoice {invoice.name}: {str(e)}", "ERROR: picklist_create_failed")
        
        # Reiche die Sales Invoice ein
        # invoice.submit()  # <--- AUSKOMMENTIERT: Rechnung wird NICHT gebucht, nur erstellt
        # frappe.log_error(f"Sales Invoice submitted: {invoice.name}", "SUCCESS: invoice_submitted")
        
        frappe.log_error(f"✅ SUCCESS: Auto invoice complete for SO {doc.name} -> SI {invoice.name}", "SUCCESS: auto_invoice_complete")
        
    except Exception as e:
        frappe.log_error(f"Error in auto_create_and_submit_sales_invoice for {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: auto_invoice_failed")
        # Bei Fehlern nicht den gesamten Sales Order Submit blockieren
        frappe.msgprint(
            f"Sales Order wurde erstellt, aber die automatische Rechnungserstellung ist fehlgeschlagen: {str(e)}",
            title="Warnung",
            indicator="orange"
        ) 


@frappe.whitelist()
def create_invoice_from_sales_order(sales_order_name):
    """
    Erstellt eine Sales Invoice für einen Sales Order (für Client Scripts)
    """
    # TEMPORÄR DEAKTIVIERT: Auch die manuelle Client-Script Funktion deaktivieren
    if not ENABLE_AUTO_SALES_INVOICE_HOOKS:
        return {
            "success": False,
            "message": "Automatische Rechnungserstellung ist derzeit deaktiviert (ENABLE_AUTO_SALES_INVOICE_HOOKS = False)",
            "invoice_name": None
        }
    
    try:
        frappe.log_error(f"Client Script: Starting invoice creation for Sales Order: {sales_order_name}", "INFO: client_auto_invoice_start")
        
        # Lade den Sales Order
        doc = frappe.get_doc("Sales Order", sales_order_name)
        
        # Prüfe ob bereits eine Sales Invoice für diesen Sales Order existiert
        existing_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": ["!=", 2],
                "sales_order": doc.name
            },
            fields=["name"],
            limit=1
        )
        
        if existing_invoices:
            return {
                "success": False,
                "message": f"Sales Invoice existiert bereits: {existing_invoices[0]['name']}",
                "invoice_name": existing_invoices[0]['name']
            }
        
        # Erstelle Sales Invoice (verwende die gleiche Logik wie der Hook)
        auto_create_and_submit_sales_invoice(doc, "manual")
        
        # Finde die erstellte Sales Invoice
        created_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": ["!=", 2],
                "sales_order": doc.name
            },
            fields=["name"],
            limit=1
        )
        
        if created_invoices:
            return {
                "success": True,
                "message": f"Sales Invoice {created_invoices[0]['name']} wurde automatisch erstellt",
                "invoice_name": created_invoices[0]['name']
            }
        else:
            return {
                "success": False,
                "message": "Sales Invoice konnte nicht erstellt werden",
                "invoice_name": None
            }
        
    except Exception as e:
        frappe.log_error(f"Client Script Error for {sales_order_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: client_auto_invoice_failed")
        return {
            "success": False,
            "message": f"Fehler: {str(e)}",
            "invoice_name": None
        } 


# =====================
# HILFSFUNKTIONEN
# =====================

def create_delivery_note_for_sales_order(sales_order_doc):
    """Erstellt einen Lieferschein (Delivery Note) für den gegebenen Sales Order und gibt das DN-Dokument zurück.
    Nutzt die Standard-Mapper-Funktion von ERPNext. Bei Fehlern wird None zurückgegeben."""

    try:
        # Import erst hier, um Abhängigkeiten nur bei Bedarf zu laden
        from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
    except Exception as e:
        frappe.log_error(f"Import make_delivery_note fehlgeschlagen: {str(e)}", "ERROR: dn_import_failed")
        return None

    try:
        dn = make_delivery_note(sales_order_doc.name)
        dn.insert()
        return dn
    except Exception as e:
        frappe.log_error(f"Delivery Note konnte nicht erstellt werden: {str(e)}", "ERROR: dn_creation_failed")
        return None 