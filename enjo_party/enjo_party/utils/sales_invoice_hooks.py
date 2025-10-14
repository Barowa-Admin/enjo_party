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
    Aktualisiert Adressen automatisch im Entwurfsmodus
    Setzt custom_auftrag Feld aus Sales Order
    """
    if doc.doctype != "Sales Invoice":
        return
    
    # Setze custom_auftrag Feld aus Sales Order
    if doc.items and not doc.custom_auftrag:
        for item in doc.items:
            if item.sales_order:
                doc.custom_auftrag = item.sales_order
                break
    
    # Für Party/Sammelbestellung-Rechnungen: Deaktiviere Validierungen und setze Steuern
    if hasattr(doc, "custom_party_reference") and doc.custom_party_reference:
        # Deaktiviere ERPNext-Validierungen
        doc.flags.ignore_validate_update_after_submit = True
        doc.flags.ignore_validate = True  # Temporär für die Validierung
        doc.flags.ignore_mandatory = True  # Temporär für die Validierung
        doc.flags.ignore_pricing_rule = True
        doc.flags.ignore_item_price = True
        
        # Setze Steuer-Template wenn nicht gesetzt
        if not doc.taxes_and_charges:
            tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
                {"company": doc.company, "is_default": 1}, "name")
            if tax_template:
                doc.taxes_and_charges = tax_template
                doc.taxes = []  # Leere bestehende Steuern
                doc.run_method("set_taxes")  # Setze Steuern neu
                
                # Setze alle Steuern auf "inklusive"
                if doc.taxes:
                    for tax in doc.taxes:
                        tax.included_in_print_rate = 1
                    # Neuberechnung mit inklusiven Steuern
                    doc.calculate_taxes_and_totals()
    
    # AUSKOMMENTIERT: Adress-Synchronisation im Entwurfsmodus deaktiviert
    # if doc.docstatus == 0:  # Nur im Entwurfsmodus
    #     sync_addresses_in_draft(doc)
    
    # AUSKOMMENTIERT: Adress-Synchronisation beim Buchen deaktiviert
    # if doc.docstatus == 1 and hasattr(doc, '_doc_before_save'):
    #     sync_addresses_before_submit(doc)
    
    # Prüfe, ob es sich um eine Party/Sammelbestellung-Rechnung handelt und übertrage Referenz
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
    
    # Setze Party/Sammelbestellung-Referenz, falls noch nicht gesetzt
    if party_reference and not getattr(doc, "custom_party_reference", None):
        doc.custom_party_reference = party_reference
        frappe.log_error(f"Party/Sammelbestellung-Referenz {party_reference} zu Sales Invoice {doc.name} übertragen", "INFO: party_reference_transferred")
    
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
    
    # Deaktiviere Validierungen für Party/Sammelbestellung-Rechnungen
    if is_party_invoice or is_foreign_shipping:
        # Deaktiviere ERPNext-Validierungen
        doc.flags.ignore_validate_update_after_submit = True
        doc.flags.ignore_validate = True  # Temporär für die Validierung
        doc.flags.ignore_mandatory = True  # Temporär für die Validierung
        doc.flags.ignore_links = True  # Ignoriere Link-Validierungen
        doc.flags.ignore_permissions = True  # Ignoriere Berechtigungen
        doc.flags.ignore_address_validation = True  # Ignoriere Adress-Validierung
        doc.flags.ignore_shipping_validation = True  # Ignoriere Versand-Validierung
        doc.flags.ignore_billing_validation = True  # Ignoriere Rechnungs-Validierung
        
        # Verhindere die Adress-Validierung komplett
        if hasattr(doc, '_validate_shipping_address'):
            delattr(doc, '_validate_shipping_address')
        if hasattr(doc, '_validate_billing_address'):
            delattr(doc, '_validate_billing_address')
        
        # Deaktiviere Adress-Validierungen
        def safe_validate_party_address(self, *args, **kwargs):
            frappe.log_error(f"✅ Überspringe validate_party_address für {self.customer}", "INFO: skip_party_address_validation")
            pass
        
        def safe_validate_party_address_and_contact(self):
            frappe.log_error(f"✅ Überspringe validate_party_address_and_contact für {self.customer}", "INFO: skip_party_validation")
            pass
        
        def safe_validate_shipping_address(self):
            frappe.log_error(f"✅ Überspringe validate_shipping_address für {self.customer}", "INFO: skip_shipping_validation")
            pass
        
        def safe_validate_billing_address(self):
            frappe.log_error(f"✅ Überspringe validate_billing_address für {self.customer}", "INFO: skip_billing_validation")
            pass
        
        def safe_validate_address(self):
            frappe.log_error(f"✅ Überspringe validate_address für {self.customer}", "INFO: skip_address_validation")
            pass
        
        # Überschreibe alle Validierungsmethoden
        doc.validate_party_address = types.MethodType(safe_validate_party_address, doc)
        doc.validate_party_address_and_contact = types.MethodType(safe_validate_party_address_and_contact, doc)
        doc.validate_shipping_address = types.MethodType(safe_validate_shipping_address, doc)
        doc.validate_billing_address = types.MethodType(safe_validate_billing_address, doc)
        doc.validate_address = types.MethodType(safe_validate_address, doc)
        
        # Setze Steuer-Template wenn nicht gesetzt
        if not doc.taxes_and_charges:
            tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
                {"company": doc.company, "is_default": 1}, "name")
            if tax_template:
                doc.taxes_and_charges = tax_template
                doc.taxes = []  # Leere bestehende Steuern
                doc.run_method("set_taxes")  # Setze Steuern neu
                
                # Setze alle Steuern auf "inklusive"
                if doc.taxes:
                    for tax in doc.taxes:
                        tax.included_in_print_rate = 1
                    # Neuberechnung mit inklusiven Steuern
                    doc.calculate_taxes_and_totals()

def sync_addresses_in_draft(doc):
    """
    Synchronisiert Adressen in Rechnungen im Entwurfsmodus mit den aktuellen Kundenadressen.
    Wird nur aufgerufen wenn docstatus == 0 (Entwurfsmodus).
    """
    if not doc.customer:
        return
    
    try:
        # Finde die aktuelle Standard-Billing-Adresse des Kunden
        current_billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": doc.customer,
                "parenttype": "Address"
            },
            fields=["parent"],
            limit=1
        )
        
        if current_billing_address:
            current_billing_address = current_billing_address[0].parent
            
            # Prüfe, ob die aktuelle Adresse in der Rechnung anders ist
            if doc.customer_address != current_billing_address:
                # Lade die neue Adresse
                new_address = frappe.get_doc("Address", current_billing_address)
                
                # Aktualisiere die Rechnungsadresse
                doc.customer_address = current_billing_address
                doc.address_display = new_address.get_display()
                
                frappe.log_error(
                    f"Adresse in Rechnung {doc.name} aktualisiert: {doc.customer_address} -> {current_billing_address}",
                    "INFO: address_sync_draft"
                )
        
        # AUSKOMMENTIERT: Automatische Versandadresse-Synchronisation deaktiviert
        # Das überschreibt manuell ausgewählte Versandadressen
        # Optional: Auch Versandadresse synchronisieren, falls sie zum gleichen Kunden gehört
        """
        if doc.shipping_address_name:
            # Prüfe, ob die Versandadresse zum Kunden gehört
            shipping_links = frappe.get_all("Dynamic Link",
                filters={
                    "parent": doc.shipping_address_name,
                    "parenttype": "Address",
                    "link_doctype": "Customer",
                    "link_name": doc.customer
                },
                fields=["parent"]
            )
            
            if shipping_links:
                # Versandadresse gehört zum Kunden - finde die aktuelle Standard-Versandadresse
                current_shipping_address = frappe.get_all("Dynamic Link",
                    filters={
                        "link_doctype": "Customer",
                        "link_name": doc.customer,
                        "parenttype": "Address"
                    },
                    fields=["parent"],
                    limit=1
                )
                
                if current_shipping_address:
                    current_shipping_address = current_shipping_address[0].parent
                    
                    if doc.shipping_address_name != current_shipping_address:
                        # Lade die neue Versandadresse
                        new_shipping_address = frappe.get_doc("Address", current_shipping_address)
                        
                        # Aktualisiere die Versandadresse
                        doc.shipping_address_name = current_shipping_address
                        doc.shipping_address = new_shipping_address.get_display()
                        
                        frappe.log_error(
                            f"Versandadresse in Rechnung {doc.name} aktualisiert: {doc.shipping_address_name} -> {current_shipping_address}",
                            "INFO: shipping_address_sync_draft"
                        )
        """
    
    except Exception as e:
        frappe.log_error(f"Fehler beim Synchronisieren der Adressen in Rechnung {doc.name}: {str(e)}", "ERROR: address_sync")

def sync_addresses_before_submit(doc):
    """
    Synchronisiert Adressen BEVOR die Rechnung gebucht wird.
    Zeigt eine Warnung an, wenn Adressen geändert wurden.
    """
    if not doc.customer:
        return
    
    try:
        # Finde die aktuelle Standard-Billing-Adresse des Kunden
        current_billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": doc.customer,
                "parenttype": "Address"
            },
            fields=["parent"],
            limit=1
        )
        
        if current_billing_address:
            current_billing_address = current_billing_address[0].parent
            
            # Prüfe, ob die aktuelle Adresse in der Rechnung anders ist
            if doc.customer_address != current_billing_address:
                # Lade die neue Adresse
                new_address = frappe.get_doc("Address", current_billing_address)
                
                # Aktualisiere die Rechnungsadresse
                old_address = doc.customer_address
                doc.customer_address = current_billing_address
                doc.address_display = new_address.get_display()
                
                # Zeige eine Warnung an
                frappe.msgprint(
                    f"Die Rechnungsadresse wurde automatisch von '{old_address}' auf '{current_billing_address}' aktualisiert.",
                    title="Adresse aktualisiert",
                    indicator="blue"
                )
                
                frappe.log_error(
                    f"Adresse in Rechnung {doc.name} beim Buchen aktualisiert: {old_address} -> {current_billing_address}",
                    "INFO: address_sync_before_submit"
                )
        
        # Optional: Auch Versandadresse synchronisieren
        if doc.shipping_address_name:
            # Prüfe, ob die Versandadresse zum Kunden gehört
            shipping_links = frappe.get_all("Dynamic Link",
                filters={
                    "parent": doc.shipping_address_name,
                    "parenttype": "Address",
                    "link_doctype": "Customer",
                    "link_name": doc.customer
                },
                fields=["parent"]
            )
            
            if shipping_links:
                # Versandadresse gehört zum Kunden - finde die aktuelle Standard-Versandadresse
                current_shipping_address = frappe.get_all("Dynamic Link",
                    filters={
                        "link_doctype": "Customer",
                        "link_name": doc.customer,
                        "parenttype": "Address"
                    },
                    fields=["parent"],
                    limit=1
                )
                
                if current_shipping_address:
                    current_shipping_address = current_shipping_address[0].parent
                    
                    if doc.shipping_address_name != current_shipping_address:
                        # Lade die neue Versandadresse
                        new_shipping_address = frappe.get_doc("Address", current_shipping_address)
                        
                        # Aktualisiere die Versandadresse
                        old_shipping_address = doc.shipping_address_name
                        doc.shipping_address_name = current_shipping_address
                        doc.shipping_address = new_shipping_address.get_display()
                        
                        # Zeige eine Warnung an
                        frappe.msgprint(
                            f"Die Versandadresse wurde automatisch von '{old_shipping_address}' auf '{current_shipping_address}' aktualisiert.",
                            title="Versandadresse aktualisiert",
                            indicator="blue"
                        )
                        
                        frappe.log_error(
                            f"Versandadresse in Rechnung {doc.name} beim Buchen aktualisiert: {old_shipping_address} -> {current_shipping_address}",
                            "INFO: shipping_address_sync_before_submit"
                        )
    
    except Exception as e:
        frappe.log_error(f"Fehler beim Synchronisieren der Adressen beim Buchen der Rechnung {doc.name}: {str(e)}", "ERROR: address_sync_before_submit")

@frappe.whitelist()
def get_current_customer_addresses(customer):
    """
    Gibt die aktuellen Standard-Adressen eines Kunden zurück.
    Wird von JavaScript aufgerufen für sofortige Adress-Synchronisation.
    """
    try:
        # Finde die aktuelle Standard-Billing-Adresse (bevorzugte Rechnungsadresse)
        billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": customer,
                "parenttype": "Address"
            },
            fields=["parent"]
        )
        
        billing_address_name = None
        billing_display = None
        
        if billing_address:
            # Suche zuerst nach bevorzugter Rechnungsadresse
            for addr_link in billing_address:
                addr_doc = frappe.get_doc("Address", addr_link.parent)
                if addr_doc.is_primary_address:
                    billing_address_name = addr_link.parent
                    billing_display = addr_doc.get_display()
                    break
            
            # Falls keine bevorzugte gefunden, nimm die erste verfügbare
            if not billing_address_name:
                billing_address_name = billing_address[0].parent
                billing_doc = frappe.get_doc("Address", billing_address_name)
                billing_display = billing_doc.get_display()
        
        # Finde die aktuelle Standard-Versandadresse (bevorzugte Lieferadresse)
        shipping_address_name = None
        shipping_display = None
        
        if billing_address:
            # Suche zuerst nach bevorzugter Lieferadresse
            for addr_link in billing_address:
                addr_doc = frappe.get_doc("Address", addr_link.parent)
                if addr_doc.is_shipping_address:
                    shipping_address_name = addr_link.parent
                    shipping_display = addr_doc.get_display()
                    break
            
            # Falls keine bevorzugte gefunden, nimm die Billing-Adresse
            if not shipping_address_name:
                shipping_address_name = billing_address_name
                shipping_display = billing_display
        
        return {
            "billing_address": billing_address_name,
            "billing_display": billing_display,
            "shipping_address": shipping_address_name,
            "shipping_display": shipping_display
        }
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Abrufen der Kundenadressen für {customer}: {str(e)}", "ERROR: get_customer_addresses")
        return {
            "billing_address": None,
            "billing_display": None,
            "shipping_address": None,
            "shipping_display": None
        }

def after_insert_sales_invoice(doc, method):
    """Hook für Sales Invoice after_insert - keine spezielle Logik mehr nötig"""
    pass

def onload_sales_invoice(doc, method):
    """
    Hook für Sales Invoice onload
    AUSKOMMENTIERT: Adress-Synchronisation beim Laden deaktiviert
    """
    # AUSKOMMENTIERT: Adress-Synchronisation beim Laden deaktiviert
    # Das überschreibt manuell ausgewählte Adressen
    return
    
    if doc.doctype != "Sales Invoice":
        return
    
    # Nur im Entwurfsmodus
    if doc.docstatus != 0:
        return
    
    if not doc.customer:
        return
    
    try:
        # Prüfe, ob Adressen synchronisiert werden müssen
        needs_sync = False
        
        # Finde die aktuelle Standard-Billing-Adresse des Kunden
        current_billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": doc.customer,
                "parenttype": "Address"
            },
            fields=["parent"],
            limit=1
        )
        
        if current_billing_address:
            current_billing_address = current_billing_address[0].parent
            
            # Prüfe, ob die aktuelle Adresse in der Rechnung anders ist
            if doc.customer_address != current_billing_address:
                needs_sync = True
                
                # Lade die neue Adresse
                new_address = frappe.get_doc("Address", current_billing_address)
                
                # Aktualisiere die Rechnungsadresse
                doc.customer_address = current_billing_address
                doc.address_display = new_address.get_display()
                
                frappe.log_error(
                    f"Adresse in Rechnung {doc.name} beim Laden aktualisiert: {doc.customer_address} -> {current_billing_address}",
                    "INFO: address_sync_onload"
                )
        
        # Optional: Auch Versandadresse synchronisieren
        if doc.shipping_address_name:
            # Prüfe, ob die Versandadresse zum Kunden gehört
            shipping_links = frappe.get_all("Dynamic Link",
                filters={
                    "parent": doc.shipping_address_name,
                    "parenttype": "Address",
                    "link_doctype": "Customer",
                    "link_name": doc.customer
                },
                fields=["parent"]
            )
            
            if shipping_links:
                # Versandadresse gehört zum Kunden - finde die aktuelle Standard-Versandadresse
                current_shipping_address = frappe.get_all("Dynamic Link",
                    filters={
                        "link_doctype": "Customer",
                        "link_name": doc.customer,
                        "parenttype": "Address"
                    },
                    fields=["parent"],
                    limit=1
                )
                
                if current_shipping_address:
                    current_shipping_address = current_shipping_address[0].parent
                    
                    if doc.shipping_address_name != current_shipping_address:
                        needs_sync = True
                        
                        # Lade die neue Versandadresse
                        new_shipping_address = frappe.get_doc("Address", current_shipping_address)
                        
                        # Aktualisiere die Versandadresse
                        doc.shipping_address_name = current_shipping_address
                        doc.shipping_address = new_shipping_address.get_display()
                        
                        frappe.log_error(
                            f"Versandadresse in Rechnung {doc.name} beim Laden aktualisiert: {doc.shipping_address_name} -> {current_shipping_address}",
                            "INFO: shipping_address_sync_onload"
                        )
        
        # Wenn Adressen aktualisiert wurden, zeige eine Nachricht
        if needs_sync:
            frappe.msgprint(
                "Die Adressen wurden automatisch mit den aktuellen Kundenadressen synchronisiert.",
                title="Adressen aktualisiert",
                indicator="blue"
            )
    
    except Exception as e:
        frappe.log_error(f"Fehler beim Synchronisieren der Adressen beim Laden der Rechnung {doc.name}: {str(e)}", "ERROR: address_sync_onload")

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
    WICHTIG: Die Picklist wird IMMER nur als Entwurf erstellt, nie automatisch gebucht!
    """
    # Sicherstellen, dass die Picklist nie automatisch gebucht wird
    if method == "auto":
        method = None
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
        picklist.flags.ignore_validate = True  # Ignoriere alle Validierungen
        picklist.docstatus = 0  # Explizit als Entwurf markieren
        
        # Überschreibe validate_for_qty um Lagerbestand-Prüfung zu umgehen
        def safe_validate_for_qty(self):
            pass
        
        import types
        picklist.validate_for_qty = types.MethodType(safe_validate_for_qty, picklist)
        
        # Stelle sicher, dass die Picklist als Entwurf erstellt wird
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