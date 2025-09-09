# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

def before_validate_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_validate
    Umgeht die Adress-Validierung NUR für Party-Rechnungen
    OHNE Monkey Patching (DATEV-sicher)
    """
    if doc.doctype != "Sales Invoice" or not doc.items:
        return
    
    # Hole den ersten Sales Order aus den Items
    sales_order_name = None
    for item in doc.items:
        if item.sales_order:
            sales_order_name = item.sales_order
            break
    
    if not sales_order_name:
        return
    
    # Prüfe, ob es sich um eine Party-Rechnung handelt
    is_party_invoice = frappe.db.get_value(
        "Sales Order", 
        sales_order_name, 
        "custom_party_reference"
    )
    
    # NUR bei Party-Rechnungen eingreifen - DATEV-Rechnungen nicht berühren!
    if is_party_invoice:
        frappe.log_error(f"🎉 Party-Invoice erkannt: {doc.name} - Validierung angepasst (DATEV-sicher)", "INFO: party_invoice_detected")
        
        # NEUER ANSATZ: Setze Dummy-Adressen statt Monkey Patching
        if not doc.customer_address:
            # Hole die erste verfügbare Adresse für den Customer
            addresses = frappe.get_all("Address", 
                filters={"link_doctype": "Customer", "link_name": doc.customer},
                fields=["name"], limit=1)
            if addresses:
                doc.customer_address = addresses[0].name
                frappe.log_error(f"✅ Dummy customer_address gesetzt: {doc.customer_address}", "INFO: party_invoice_address_fix")
        
        if not doc.shipping_address_name:
            doc.shipping_address_name = doc.customer_address
            frappe.log_error(f"✅ Dummy shipping_address_name gesetzt: {doc.shipping_address_name}", "INFO: party_invoice_address_fix")

def after_save_sales_invoice(doc, method):
    """
    Hook für Sales Invoice after_save
    Nichts mehr zu tun - kein Monkey Patching cleanup nötig
    """
    # Kein Monkey Patching cleanup mehr nötig - DATEV-sicher!
    pass

def get_shipping_account():
    """
    Gibt das Standard-Versandkonto zurück
    """
    try:
        # Hole die Standard-Company
        company = frappe.defaults.get_global_default('company')
        if not company:
            company = frappe.get_all("Company", limit=1)[0].name
        
        # Versuche Standard Cash Account der Company zu holen
        cash_account = frappe.get_cached_value("Company", company, "default_cash_account")
        if cash_account:
            return cash_account
            
        # Fallback: Suche nach einem Cash/Bank Account
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
            
        # Letzter Fallback: Irgendein Asset-Account
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
    
    # Absoluter Fallback
    return "Bargeld - BM"

def add_shipping_to_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_save
    Fügt automatisch Versandkosten hinzu, wenn sie im referenzierten Sales Order vorhanden sind
    """
    frappe.log_error(f"=== ADD_SHIPPING_TO_SALES_INVOICE START für {doc.name} ===", "DEBUG: shipping_hook_start")

    # Defensive: Nur im Entwurfsstatus (docstatus == 0) Änderungen zulassen
    # Verhindert Updates während/nach Submit, die externe Integrationen (z. B. DATEV) erneut triggern könnten
    try:
        if getattr(doc, "docstatus", 0) != 0:
            frappe.log_error(
                f"Überspringe Versandkosten-Hook: docstatus={getattr(doc, 'docstatus', None)}",
                "DEBUG: shipping_skip_non_draft"
            )
            return
    except Exception:
        # Falls etwas schiefgeht: lieber keinen Eingriff
        return
    
    if doc.doctype != "Sales Invoice" or not doc.items:
        frappe.log_error(f"Überspringe - doctype: {doc.doctype}, items: {len(doc.items) if doc.items else 0}", "DEBUG: shipping_hook_skip")
        return
    
    # NEUE LOGIK: Hole Versandkosten direkt aus den referenzierten Sales Orders
    total_shipping_cost = 0
    processed_orders = set()  # Verhindere Duplikate
    
    frappe.log_error(f"Prüfe {len(doc.items)} Items auf Sales Order Referenzen", "DEBUG: checking_items")
    
    # Gehe durch alle Items und sammle eindeutige Sales Orders
    for item in doc.items:
        if item.sales_order and item.sales_order not in processed_orders:
            frappe.log_error(f"Lade Sales Order: {item.sales_order}", "DEBUG: loading_so")
            
            # Lade den Sales Order
            so_doc = frappe.get_doc("Sales Order", item.sales_order)
            
            # Prüfe ob Versandkosten vorhanden sind
            shipping_cost = so_doc.get("custom_calculated_shipping_cost") or 0
            frappe.log_error(f"Sales Order {item.sales_order} hat Versandkosten: {shipping_cost}", "DEBUG: so_shipping_cost")
            
            if shipping_cost > 0:
                total_shipping_cost += shipping_cost
                processed_orders.add(item.sales_order)
                frappe.log_error(f"Addiere {shipping_cost}€ Versandkosten von SO {item.sales_order}", "DEBUG: adding_shipping")
    
    frappe.log_error(f"Gesamte Versandkosten aus {len(processed_orders)} Sales Orders: {total_shipping_cost}€", "DEBUG: total_shipping")
    
    # Wenn keine Versandkosten gefunden wurden, abbrechen
    if total_shipping_cost <= 0:
        frappe.log_error("Keine Versandkosten gefunden - Hook beendet", "DEBUG: no_shipping")
        return
    
    # Prüfe ob bereits Versandkosten in der Rechnung sind
    existing_shipping = False
    if doc.taxes:
        for tax in doc.taxes:
            if tax.description and "versand" in tax.description.lower():
                frappe.log_error(f"Versandkosten bereits vorhanden: {tax.description} - {tax.tax_amount}", "DEBUG: shipping_exists")
                existing_shipping = True
                break
    
    if existing_shipping:
        frappe.log_error("Versandkosten bereits vorhanden - Hook beendet", "DEBUG: shipping_already_exists")
        return
    
    # Versandkosten als neue Tax-Zeile hinzufügen - VEREINFACHT
    frappe.log_error(f"Füge Versandkosten-Zeile hinzu: {total_shipping_cost}€", "DEBUG: adding_tax_row")
    
    # Neue Tax-Zeile erstellen - genauso wie im manuellen Test
    tax_row = doc.append("taxes", {})
    tax_row.description = "Versandkosten"
    tax_row.account_head = get_shipping_account()
    tax_row.charge_type = "Actual"
    tax_row.tax_amount = flt(total_shipping_cost)
    tax_row.add_deduct_tax = "Add"
    
    frappe.log_error(f"Versandkosten erfolgreich hinzugefügt: {total_shipping_cost}€ - Konto: {tax_row.account_head}", "SUCCESS: shipping_added")

def auto_create_picklist_from_invoice(doc, method):
	"""
	Hook für Sales Invoice on_submit
	Erstellt automatisch eine Picklist für die eingereichte Sales Invoice
	"""
	try:
		frappe.log_error(f"🎯 AUTO PICKLIST: Starting for Sales Invoice: {doc.name}", "INFO: auto_picklist_start")
		
		# Prüfe ob bereits eine Picklist für diese Sales Invoice existiert
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
			frappe.log_error(f"❌ Picklist existiert bereits für Invoice {doc.name}: {existing_picklists[0]['name']}", "INFO: picklist_exists")
			return
		
		# Sammle Sales Order Informationen
		sales_orders = set()
		for item in doc.items:
			if item.sales_order:
				sales_orders.add(item.sales_order)
		
		if not sales_orders:
			frappe.log_error(f"❌ Keine Sales Orders gefunden für Invoice {doc.name}", "WARNING: no_sales_orders")
			return
		
		frappe.log_error(f"📋 Gefundene Sales Orders: {list(sales_orders)}", "DEBUG: found_sales_orders")
		
		# Erstelle Picklist Items
		picklist_items = []
		
		# Für jeden Sales Order die Items sammeln
		for so_name in sales_orders:
			try:
				so_doc = frappe.get_doc("Sales Order", so_name)
				
				for so_item in so_doc.items:
					# Überspringe Versandartikel (nur echte Produkte)
					if so_item.item_code and so_item.item_code.startswith("shipping-"):
						frappe.log_error(f"📦 Versandartikel übersprungen: {so_item.item_code}", "DEBUG: shipping_item_skipped")
						continue
					
					# Hole Standard-Warehouse
					warehouse = so_item.warehouse
					if not warehouse:
						warehouse = frappe.defaults.get_user_default("Warehouse")
						if not warehouse:
							# Fallback: Erstes verfügbares Warehouse
							warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, fields=["name"], limit=1)
							warehouse = warehouses[0].name if warehouses else "Stores - Main"
					
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
					frappe.log_error(f"✅ Picklist Item hinzugefügt: {so_item.item_code} (SO: {so_name})", "DEBUG: picklist_item_added")
					
			except Exception as e:
				frappe.log_error(f"❌ Fehler beim Verarbeiten von SO {so_name}: {str(e)}", "ERROR: so_processing_error")
				continue
		
		if not picklist_items:
			frappe.log_error(f"❌ Keine Picklist Items gefunden für Invoice {doc.name}", "WARNING: no_picklist_items")
			return
		
		# Erstelle Invoice Reference mit Kundenname
		try:
			customer_doc = frappe.get_doc("Customer", doc.customer)
			customer_display_name = customer_doc.customer_name or doc.customer
			# Kürze den Namen für bessere Lesbarkeit
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
		
		frappe.log_error(f"🎯 Erstelle Picklist für Invoice {doc.name} mit {len(picklist_items)} Items", "INFO: creating_picklist")
		
		# Erstelle und reiche Picklist ein
		picklist = frappe.get_doc(picklist_data)
		picklist.insert()
		frappe.log_error(f"✅ Picklist erstellt: {picklist.name}", "SUCCESS: picklist_created")
		
		try:
			picklist.submit()
			frappe.log_error(f"🎉 Picklist eingereicht: {picklist.name}", "SUCCESS: picklist_submitted")
		except Exception as e:
			frappe.log_error(f"⚠️ Picklist konnte nicht eingereicht werden: {str(e)}", "WARNING: picklist_submit_failed")
		
		# Zeige Erfolgsnotifikation
		frappe.publish_realtime(
			"show_alert",
			{"message": f"Picklist {picklist.name} wurde automatisch erstellt!", "indicator": "green"},
			user=frappe.session.user
		)
		
	except Exception as e:
		frappe.log_error(f"💥 Fehler in auto_create_picklist_from_invoice für {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: auto_picklist_error") 