# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
import types

def before_validate_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_validate
    Umgeht die Adress-Validierung für Party-Rechnungen und fremde Lieferadressen
    Überträgt Party-Referenz von Sales Order zu Sales Invoice
    """
    if doc.doctype != "Sales Invoice":
        return
    
    # Prüfe, ob es sich um eine Party-Rechnung handelt und übertrage Party-Referenz
    is_party_invoice = False
    party_reference = None
    
    if doc.items:
        for item in doc.items:
            if item.sales_order:
                party_ref = frappe.db.get_value("Sales Order", item.sales_order, "custom_party_reference")
                if party_ref:
                    is_party_invoice = True
                    party_reference = party_ref
                    break
    
    # Setze Party-Referenz, falls noch nicht gesetzt
    if party_reference and not getattr(doc, "custom_party_reference", None):
        doc.custom_party_reference = party_reference
        frappe.log_error(f"Party-Referenz {party_reference} zu Sales Invoice {doc.name} übertragen", "INFO: party_reference_transferred")
    
    # Prüfe, ob fremde Lieferadresse verwendet wird
    is_foreign_shipping = False
    if doc.shipping_address_name and doc.customer:
        # Finde heraus, welcher Customer zur Lieferadresse gehört
        links = frappe.get_all("Dynamic Link", 
            filters={
                "parent": doc.shipping_address_name,
                "parenttype": "Address",
                "link_doctype": "Customer"
            },
            fields=["link_name"]
        )
        if links:
            shipping_customer = links[0].link_name
            if shipping_customer != doc.customer:
                is_foreign_shipping = True
    
    # Deaktiviere Adressvalidierung wenn nötig
    if is_party_invoice or is_foreign_shipping:
        def safe_validate_party_address(self, *args, **kwargs):
            pass
        
        def safe_validate_party_address_and_contact(self):
            pass
        
        doc.validate_party_address = types.MethodType(safe_validate_party_address, doc)
        doc.validate_party_address_and_contact = types.MethodType(safe_validate_party_address_and_contact, doc)

def after_save_sales_invoice(doc, method):
    """Hook für Sales Invoice after_save - cleanup nicht nötig"""
    pass

def get_shipping_account():
    """Gibt das Standard-Versandkonto zurück"""
    try:
        company = frappe.defaults.get_global_default('company')
        if not company:
            company = frappe.get_all("Company", limit=1)[0].name
        
        cash_account = frappe.get_cached_value("Company", company, "default_cash_account")
        if cash_account:
            return cash_account
            
        account = frappe.get_all("Account", 
            filters={
                "company": company,
                "is_group": 0, 
                "account_type": ["in", ["Cash", "Bank"]],
                "disabled": 0
            },
            fields=["name"],
            limit=1)
        
        if account:
            return account[0].name
            
        account = frappe.get_all("Account", 
            filters={
                "company": company,
                "is_group": 0, 
                "root_type": "Asset",
                "disabled": 0
            },
            fields=["name"],
            limit=1)
        
        if account:
            return account[0].name
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Ermitteln des Versandkontos: {str(e)}", "ERROR: get_shipping_account")
    
    return "Bargeld - BM"

def add_shipping_to_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_save
    Fügt automatisch Versandkosten hinzu, wenn sie im referenzierten Sales Order vorhanden sind
    """
    if getattr(doc, "docstatus", 0) != 0:
        return
    
    if doc.doctype != "Sales Invoice" or not doc.items:
        return
    
    # Hole Versandkosten aus Sales Orders
    total_shipping_cost = 0
    processed_orders = set()
    
    for item in doc.items:
        if item.sales_order and item.sales_order not in processed_orders:
            so_doc = frappe.get_doc("Sales Order", item.sales_order)
            shipping_cost = so_doc.get("custom_calculated_shipping_cost") or 0
            
            if shipping_cost > 0:
                total_shipping_cost += shipping_cost
                processed_orders.add(item.sales_order)
    
    if total_shipping_cost <= 0:
        return
    
    # Prüfe ob bereits Versandkosten vorhanden sind
    existing_shipping = False
    if doc.taxes:
        for tax in doc.taxes:
            if tax.description and "versand" in tax.description.lower():
                existing_shipping = True
                break
    
    if existing_shipping:
        return
    
    # Füge Versandkosten hinzu
    tax_row = doc.append("taxes", {})
    tax_row.description = "Versandkosten"
    tax_row.account_head = get_shipping_account()
    tax_row.charge_type = "Actual"
    tax_row.tax_amount = flt(total_shipping_cost)
    tax_row.add_deduct_tax = "Add"

def auto_create_picklist_from_invoice(doc, method):
    """
    Hook für Sales Invoice on_submit
    Erstellt automatisch eine Picklist für die eingereichte Sales Invoice
    """
    try:
        # Prüfe ob bereits eine Picklist existiert
        existing_picklists = frappe.get_all(
            "Pick List",
            filters={
                "docstatus": ["!=", 2],
                "custom_invoice_references": ["like", f"%{doc.name}%"]
            },
            fields=["name"],
            limit=1
        )
        
        if existing_picklists:
            return
        
        # Sammle Sales Order Informationen
        sales_orders = set()
        for item in doc.items:
            if item.sales_order:
                sales_orders.add(item.sales_order)
        
        if not sales_orders:
            return
        
        # Erstelle Picklist Items
        picklist_items = []
        
        for so_name in sales_orders:
            try:
                so_doc = frappe.get_doc("Sales Order", so_name)
                
                for so_item in so_doc.items:
                    if so_item.item_code and so_item.item_code.startswith("shipping-"):
                        continue
                    
                    warehouse = so_item.warehouse
                    if not warehouse:
                        warehouse = frappe.defaults.get_user_default("Warehouse")
                        if not warehouse:
                            warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, fields=["name"], limit=1)
                            warehouse = warehouses[0].name if warehouses else "Stores - Main"
                    
                    # Prüfe ob Item ein Product Bundle ist
                    bundle_items = frappe.get_all("Product Bundle Item", 
                                                 filters={"parent": so_item.item_code}, 
                                                 fields=["item_code", "qty", "uom", "description"])
                    
                    if bundle_items:
                        # Item ist ein Product Bundle - füge Bundle Items hinzu
                        frappe.log_error(f"Product Bundle erkannt: {so_item.item_code} mit {len(bundle_items)} Items", "INFO: bundle_detected")
                        for bundle_item in bundle_items:
                            bundle_qty = float(bundle_item.qty) * float(so_item.qty)
                            
                            picklist_item = {
                                "doctype": "Pick List Item",
                                "item_code": bundle_item.item_code,
                                "item_name": bundle_item.description or frappe.get_value("Item", bundle_item.item_code, "item_name"),
                                "qty": bundle_qty,
                                "stock_qty": bundle_qty,
                                "picked_qty": 0.0,
                                "stock_reserved_qty": 0.0,
                                "uom": bundle_item.uom or so_item.uom,
                                "stock_uom": bundle_item.uom or so_item.stock_uom or so_item.uom,
                                "conversion_factor": 1.0,
                                "warehouse": warehouse,
                                "sales_order": so_name,
                                "sales_order_item": so_item.name,
                                "batch_no": None,
                                "serial_no": None,
                                "use_serial_batch_fields": 0,
                                "serial_and_batch_bundle": None,
                                "product_bundle_item": so_item.item_code,  # Referenz zum Original Bundle
                                "material_request": None,
                                "material_request_item": None
                            }
                            
                            picklist_items.append(picklist_item)
                            frappe.log_error(f"Bundle Item hinzugefügt: {bundle_item.item_code} (Qty: {bundle_qty}) für Bundle {so_item.item_code}", "INFO: bundle_item_added")
                    else:
                        # Normaler Artikel - wie bisher
                        picklist_item = {
                            "doctype": "Pick List Item",
                            "item_code": so_item.item_code,
                            "item_name": so_item.item_name,
                            "qty": float(so_item.qty),
                            "stock_qty": float(so_item.stock_qty or so_item.qty),
                            "picked_qty": 0.0,
                            "stock_reserved_qty": 0.0,
                            "uom": so_item.uom,
                            "stock_uom": so_item.stock_uom or so_item.uom,
                            "conversion_factor": float(so_item.conversion_factor or 1.0),
                            "warehouse": warehouse,
                            "sales_order": so_name,
                            "sales_order_item": so_item.name,
                            "batch_no": None,
                            "serial_no": None,
                            "use_serial_batch_fields": 0,
                            "serial_and_batch_bundle": None,
                            "product_bundle_item": None,
                            "material_request": None,
                            "material_request_item": None
                        }
                        
                        picklist_items.append(picklist_item)
                    
            except Exception as e:
                continue
        
        if not picklist_items:
            return
        
        # Erstelle Invoice Reference
        try:
            customer_doc = frappe.get_doc("Customer", doc.customer)
            customer_display_name = customer_doc.customer_name or doc.customer
            if len(customer_display_name) > 15:
                customer_display_name = customer_display_name[:12] + "..."
        except:
            customer_display_name = doc.customer
        
        invoice_reference = f"{doc.name} ({customer_display_name})"
        
        # Erstelle Picklist
        picklist_data = {
            "doctype": "Pick List",
            "purpose": "Delivery",
            "company": doc.company,
            "customer": doc.customer,
            "custom_invoice_references": invoice_reference,
            "remarks": f"Automatisch erstellt für Rechnung: {doc.name}",
            "locations": picklist_items
        }
        
        picklist = frappe.get_doc(picklist_data)
        
        # Flags setzen um Lagerbestand-Validierung zu umgehen
        picklist.flags.ignore_permissions = True
        picklist.flags.ignore_mandatory = True
        
        # Überschreibe validate_for_qty um Lagerbestand-Prüfung zu umgehen
        def safe_validate_for_qty(self):
            pass
        
        import types
        picklist.validate_for_qty = types.MethodType(safe_validate_for_qty, picklist)
        
        picklist.insert()
        
        # NICHT automatisch einreichen - da Artikel möglicherweise nicht lagernd sind
        # Die Picklist kann manuell eingereicht werden, wenn alle Artikel verfügbar sind
        
        frappe.publish_realtime(
            "show_alert",
            {"message": f"Picklist {picklist.name} wurde automatisch erstellt!", "indicator": "green"},
            user=frappe.session.user
        )
        
    except Exception as e:
        pass