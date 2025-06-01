# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

def before_validate_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_validate
    Umgeht die Adress-Validierung für Party-Rechnungen
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
    
    # Wenn es eine Party-Rechnung ist, umgehe die Adress-Validierung
    if is_party_invoice:
        # Importiere die Elternklasse
        from erpnext.controllers.accounts_controller import AccountsController
        
        # Speichere die originale Methode
        if not hasattr(AccountsController, '_original_validate_party_address'):
            AccountsController._original_validate_party_address = AccountsController.validate_party_address
        
        # Überschreibe die Validierungsmethode temporär
        def dummy_validate_party_address(self, party, party_type, billing_address=None, shipping_address=None):
            pass
        
        # Monkey-patch die Validierung
        AccountsController.validate_party_address = dummy_validate_party_address

def after_save_sales_invoice(doc, method):
    """
    Hook für Sales Invoice after_save
    Stellt die ursprüngliche Adress-Validierung wieder her
    """
    # Stelle die originale Validierung wieder her
    from erpnext.controllers.accounts_controller import AccountsController
    if hasattr(AccountsController, '_original_validate_party_address'):
        AccountsController.validate_party_address = AccountsController._original_validate_party_address

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