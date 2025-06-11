import frappe
from frappe import _


def auto_create_and_submit_sales_invoice(doc, method):
    """
    Hook für Sales Order on_submit
    Erstellt automatisch eine Sales Invoice und reicht sie ein
    """
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
        invoice_data = {
            "doctype": "Sales Invoice",
            "customer": doc.customer,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "customer_address": doc.customer_address,
            "shipping_address_name": doc.shipping_address_name,
            "po_no": doc.po_no,  # Party-Referenz übernehmen
            "po_date": doc.transaction_date,
            "company": company,
            "currency": doc.currency,
            "selling_price_list": doc.selling_price_list,
            "sales_partner": doc.sales_partner,
            "remarks": f"Automatisch erstellt aus Sales Order: {doc.name}",
            "items": []
        }
        
        # Sichere Behandlung von custom fields
        if hasattr(doc, 'custom_party_reference') and doc.custom_party_reference:
            # Prüfe ob die Party noch aktiv ist (nicht cancelled)
            try:
                party_doc = frappe.get_doc("Party", doc.custom_party_reference)
                if party_doc.docstatus != 2:  # Nicht cancelled
                    invoice_data["custom_party_reference"] = doc.custom_party_reference
                    frappe.log_error(f"Party Referenz hinzugefügt: {doc.custom_party_reference}", "DEBUG: party_ref_added")
                else:
                    frappe.log_error(f"Party {doc.custom_party_reference} ist cancelled - überspringe Referenz", "WARNING: cancelled_party")
            except Exception as e:
                frappe.log_error(f"Fehler beim Laden der Party {doc.custom_party_reference}: {str(e)}", "WARNING: party_load_error")
        else:
            frappe.log_error("Kein custom_party_reference gefunden - normaler Sales Order", "DEBUG: no_party_ref")
                
        if hasattr(doc, 'custom_calculated_shipping_cost') and doc.custom_calculated_shipping_cost:
            invoice_data["custom_calculated_shipping_cost"] = doc.custom_calculated_shipping_cost
        
        # Kopiere alle Items vom Sales Order
        for item in doc.items:
            invoice_item = {
                "doctype": "Sales Invoice Item",
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": getattr(item, 'description', item.item_name),
                "qty": item.qty,
                "rate": item.rate,
                "amount": item.amount,
                "uom": item.uom,
                "conversion_factor": getattr(item, 'conversion_factor', 1.0),
                "warehouse": getattr(item, 'warehouse', None),
                "sales_order": doc.name,  # Referenz zum Sales Order
                "so_detail": item.name     # Referenz zum Sales Order Item
            }
            
            # Optionale Felder nur hinzufügen wenn sie existieren
            if hasattr(item, 'cost_center') and item.cost_center:
                invoice_item["cost_center"] = item.cost_center
            if hasattr(item, 'income_account') and item.income_account:
                invoice_item["income_account"] = item.income_account
                
            invoice_data["items"].append(invoice_item)
        
        # Erstelle die Sales Invoice
        invoice = frappe.get_doc(invoice_data)
        
        # WICHTIG: Verhindere Preis-Validierung damit Gutschein-Preise erhalten bleiben
        invoice.flags.ignore_pricing_rule = True
        invoice.flags.ignore_item_price = True
        
        # Setze die exakten Preise aus dem Sales Order nochmal explizit
        for i, invoice_item in enumerate(invoice.items):
            so_item = doc.items[i]
            # Überschreibe mit den exakten Sales Order Preisen (inkl. Gutschein-Rabatte)
            invoice_item.rate = so_item.rate
            invoice_item.price_list_rate = so_item.rate  
            invoice_item.base_rate = so_item.rate
            invoice_item.base_price_list_rate = so_item.rate
            invoice_item.amount = so_item.amount
            invoice_item.base_amount = so_item.amount
            # Markiere als manuell gesetzt um weitere Validierung zu verhindern
            invoice_item.flags.ignore_pricing_rule = True
        
        invoice.insert()
        frappe.log_error(f"Sales Invoice created: {invoice.name}", "INFO: invoice_created")
        
        # Reiche die Sales Invoice ein
        invoice.submit()
        frappe.log_error(f"Sales Invoice submitted: {invoice.name}", "SUCCESS: invoice_submitted")
        
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