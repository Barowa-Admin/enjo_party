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

def add_shipping_to_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_save
    Fügt automatisch Versandkosten hinzu, wenn sie im referenzierten Sales Order vorhanden sind
    """
    if doc.doctype != "Sales Invoice" or not doc.items:
        return
    
    # Hole den ersten Sales Order aus den Items (alle Items sollten vom gleichen Sales Order stammen)
    sales_order_name = None
    for item in doc.items:
        if item.sales_order:
            sales_order_name = item.sales_order
            break
    
    if not sales_order_name:
        return
    
    try:
        # Hole Versandkosten vom Sales Order
        shipping_cost = frappe.db.get_value(
            "Sales Order", 
            sales_order_name, 
            "custom_calculated_shipping_cost"
        )
        
        if not shipping_cost or shipping_cost <= 0:
            return
        
        # Prüfe, ob bereits Versandkosten in der Rechnung vorhanden sind
        existing_shipping = False
        for tax in doc.taxes or []:
            if "versand" in tax.description.lower() or "shipping" in tax.description.lower():
                existing_shipping = True
                break
        
        if existing_shipping:
            return  # Versandkosten bereits vorhanden
        
        # Füge Versandkosten als Tax/Charge hinzu
        doc.append("taxes", {
            "charge_type": "Actual",
            "account_head": "Kasse - BM",  # Wie vom User angegeben
            "description": "Versandkosten",
            "tax_amount": flt(shipping_cost),
            "add_deduct_tax": "Add"
        })
        
        frappe.log_error(f"Versandkosten von {shipping_cost}€ zur Sales Invoice {doc.name} hinzugefügt", "INFO: Versandkosten")
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Hinzufügen von Versandkosten zur Sales Invoice {doc.name}: {str(e)}", "ERROR: Versandkosten") 