# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

"""
Subscription-Status-Manipulation

Dieses Modul manipuliert den ECHTEN ERPNext-Status (per_billed, per_delivered, 
billing_status, delivery_status) für Subscription-Sales Orders.

Problem:
- Subscription-Invoice wird zuerst erstellt und gebucht
- Sales Order wird danach erstellt und mit Invoice verknüpft
- ERPNext berechnet Status falsch weil die Verknüpfung nachträglich gesetzt wird
- Wenn Invoice bezahlt wird → per_billed bleibt bei 0% (sollte 100% sein)
- Wenn Delivery Note gebucht wird → per_delivered wird korrekt auf 100% gesetzt
- Status zeigt "abzurechnen" obwohl Invoice bezahlt ist

Lösung:
- Wenn ALLE Rechnungen der Subscription bezahlt sind → setze per_billed=100 
  für ALLE zugehörigen Sales Orders
- Wenn Delivery Note gebucht wird → setze per_delivered=100 
  für ALLE zugehörigen Sales Orders
"""

import frappe
from frappe.utils import flt


def update_subscription_status_on_payment(doc, method):
    """
    Hook für Payment Entry on_submit
    Prüft ob alle Rechnungen einer Subscription bezahlt sind
    """
    try:
        # Finde alle Sales Invoices die durch diesen Payment Entry bezahlt wurden
        for ref in doc.references:
            if ref.reference_doctype == "Sales Invoice":
                invoice = frappe.get_doc("Sales Invoice", ref.reference_name)
                
                # Prüfe ob die Invoice zu einer Subscription gehört
                subscription_name = getattr(invoice, "subscription", None)
                if subscription_name:
                    frappe.log_error(f"Payment für Subscription {subscription_name} erkannt", 
                                    "INFO: subscription_payment")
                    update_subscription_billing_status(subscription_name)
                    
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Billing-Status nach Zahlung: {str(e)}", 
                        "ERROR: subscription_status_payment")


def update_subscription_status_on_invoice_payment(doc, method):
    """
    Hook für Sales Invoice on_update_after_submit
    Wird aufgerufen wenn der outstanding_amount sich ändert
    Prüft ob Invoice zu einer Subscription gehört und aktualisiert den Status
    """
    try:
        # Prüfe ob die Invoice zu einer Subscription gehört
        subscription_name = getattr(doc, "subscription", None)
        if not subscription_name:
            return
        
        frappe.log_error(f"Invoice-Update für Subscription {subscription_name}", 
                        "INFO: subscription_invoice_update")
        update_subscription_billing_status(subscription_name)
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Update nach Invoice-Update: {str(e)}", 
                        "ERROR: subscription_status_invoice")


def update_subscription_status_on_delivery(doc, method):
    """
    Hook für Delivery Note on_submit
    Prüft ob Delivery Note zu einem Subscription-Sales Order gehört
    """
    try:
        # Finde den Sales Order für diesen Lieferschein
        sales_order_name = None
        for item in doc.items:
            # Prüfe sowohl against_sales_order als auch sales_order
            if hasattr(item, 'against_sales_order') and item.against_sales_order:
                sales_order_name = item.against_sales_order
                break
            elif hasattr(item, 'sales_order') and item.sales_order:
                sales_order_name = item.sales_order
                break
        
        if not sales_order_name:
            return
        
        # Hole den Sales Order
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        
        # Prüfe ob es ein Subscription-Sales Order ist
        subscription_name = getattr(sales_order, "custom_subscription", None)
        if not subscription_name:
            return
        
        frappe.log_error(f"Delivery Note für Subscription {subscription_name}", 
                       "INFO: subscription_delivery")
        update_subscription_delivery_status(subscription_name)
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Update nach Lieferschein: {str(e)}", 
                        "ERROR: subscription_status_delivery")


def update_subscription_billing_status(subscription_name):
    """
    Prüft ob alle Rechnungen bezahlt sind und setzt per_billed=100 
    für ALLE Sales Orders der Subscription
    
    WICHTIG: Prüft nur ob alle existierenden Rechnungen bezahlt sind.
    """
    try:
        # Finde alle GEBUCHTEN Sales Invoices der Subscription
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name", "outstanding_amount", "grand_total"]
        )
        
        if not invoices:
            frappe.log_error(f"Keine gebuchten Rechnungen für Subscription {subscription_name} gefunden", 
                           "DEBUG: no_invoices")
            return
        
        frappe.log_error(f"Gefunden: {len(invoices)} gebuchte Rechnungen für Subscription {subscription_name}", 
                        "DEBUG: invoice_count")
        
        # Prüfe ob ALLE Rechnungen bezahlt sind (outstanding_amount = 0)
        all_paid = True
        for inv in invoices:
            if flt(inv.outstanding_amount) > 0.01:
                all_paid = False
                frappe.log_error(f"Rechnung {inv.name} noch nicht bezahlt: {inv.outstanding_amount}", 
                               "DEBUG: invoice_not_paid")
                break
        
        if not all_paid:
            frappe.log_error(f"Nicht alle Rechnungen bezahlt für Subscription {subscription_name}", 
                           "DEBUG: not_all_paid")
            return
        
        frappe.log_error(f"ALLE {len(invoices)} Rechnungen bezahlt für Subscription {subscription_name} - setze Status!", 
                        "INFO: all_paid")
        
        # Finde ALLE Sales Orders der Subscription
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        if not sales_orders:
            frappe.log_error(f"Keine Sales Orders für Subscription {subscription_name} gefunden", 
                           "DEBUG: no_sales_orders")
            return
        
        # Setze per_billed=100 und billing_status="Fully Billed" für ALLE
        for so in sales_orders:
            # Lade das Dokument um den aktuellen per_delivered Status zu prüfen
            so_doc = frappe.get_doc("Sales Order", so.name)
            current_per_delivered = flt(so_doc.per_delivered) or 0
            
            # Setze Billing-Status
            frappe.db.set_value("Sales Order", so.name, {
                "per_billed": 100,
                "billing_status": "Fully Billed"
            }, update_modified=False)
            
            # Wenn bereits ausgeliefert (per_delivered=100), dann sollte Status "Completed" sein
            # Aktualisiere den Gesamtstatus
            so_doc.reload()
            so_doc.set_status(update=True)
            
            # WICHTIG: Setze Status auch direkt auf "Completed" wenn beide Bedingungen erfüllt sind
            if current_per_delivered >= 100:
                frappe.db.set_value("Sales Order", so.name, "status", "Completed", update_modified=False)
                so_doc.reload()
            
            frappe.log_error(f"Sales Order {so.name}: per_billed=100, billing_status=Fully Billed, per_delivered={current_per_delivered}, Status={so_doc.status}", 
                           "SUCCESS: billing_status_updated")
        
        frappe.db.commit()
        
        # Nach dem Billing-Update: Prüfe auch ob bereits Delivery vorhanden ist
        # Falls ja, sollten alle Orders bereits "Completed" sein
        # (nur wenn noch nicht alle Orders per_delivered=100 haben)
        all_orders_check = frappe.get_all(
            "Sales Order",
            filters={
                "custom_subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name", "per_delivered"]
        )
        if not all(flt(so.per_delivered) >= 100 for so in all_orders_check):
            update_subscription_delivery_status_if_exists(subscription_name)
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Billing-Status: {str(e)}", 
                        "ERROR: update_billing_status")


def update_subscription_billing_status_if_exists(subscription_name):
    """
    Prüft ob bereits alle Rechnungen bezahlt sind
    und aktualisiert dann den Billing-Status für alle Orders
    Wird nach dem Delivery-Update aufgerufen, um sicherzustellen dass beide Status gesetzt sind
    """
    try:
        # Prüfe zuerst ob Billing-Status bereits gesetzt ist (verhindert Endlosschleife)
        all_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name", "per_billed"]
        )
        
        # Wenn bereits alle Orders per_billed=100 haben, nichts tun
        if all_orders and all(flt(so.per_billed) >= 100 for so in all_orders):
            frappe.log_error(f"Billing-Status bereits gesetzt für Subscription {subscription_name}", 
                           "DEBUG: billing_already_set")
            return
        
        # Finde alle GEBUCHTEN Sales Invoices der Subscription
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name", "outstanding_amount"]
        )
        
        if not invoices:
            return
        
        # Prüfe ob ALLE Rechnungen bezahlt sind
        all_paid = all(flt(inv.outstanding_amount) <= 0.01 for inv in invoices)
        
        if all_paid:
            # Alle Rechnungen bezahlt → setze Billing-Status direkt (ohne erneute Delivery-Prüfung)
            frappe.log_error(f"Alle Rechnungen bereits bezahlt für Subscription {subscription_name} - setze Billing-Status direkt", 
                           "DEBUG: billing_already_paid")
            
            # Finde ALLE Sales Orders der Subscription
            all_orders = frappe.get_all(
                "Sales Order",
                filters={
                    "custom_subscription": subscription_name,
                    "docstatus": 1
                },
                fields=["name"]
            )
            
            # Setze per_billed=100 für ALLE
            for so in all_orders:
                so_doc = frappe.get_doc("Sales Order", so.name)
                current_per_delivered = flt(so_doc.per_delivered) or 0
                frappe.db.set_value("Sales Order", so.name, {
                    "per_billed": 100,
                    "billing_status": "Fully Billed"
                }, update_modified=False)
                so_doc.reload()
                so_doc.set_status(update=True)
                
                # WICHTIG: Setze Status auch direkt auf "Completed" wenn beide Bedingungen erfüllt sind
                if current_per_delivered >= 100:
                    frappe.db.set_value("Sales Order", so.name, "status", "Completed", update_modified=False)
                    so_doc.reload()
            
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Prüfen des Billing-Status: {str(e)}", 
                        "ERROR: check_billing_status")


def update_subscription_delivery_status_if_exists(subscription_name):
    """
    Prüft ob bereits ein Lieferschein existiert
    und aktualisiert dann den Delivery-Status für alle Orders
    Wird nach dem Billing-Update aufgerufen, um sicherzustellen dass beide Status gesetzt sind
    """
    try:
        # Prüfe zuerst ob Delivery-Status bereits gesetzt ist (verhindert Endlosschleife)
        all_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name", "per_delivered"]
        )
        
        # Wenn bereits alle Orders per_delivered=100 haben, nichts tun
        if all_orders and all(flt(so.per_delivered) >= 100 for so in all_orders):
            frappe.log_error(f"Delivery-Status bereits gesetzt für Subscription {subscription_name}", 
                           "DEBUG: delivery_already_set")
            return
        
        # Finde alle Sales Orders der Subscription
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        if not sales_orders:
            return
        
        # Prüfe ob für einen der Sales Orders ein gebuchter Lieferschein existiert
        delivery_notes = frappe.get_all(
            "Delivery Note Item",
            filters={
                "against_sales_order": ["in", [so.name for so in sales_orders]],
                "docstatus": 1
            },
            fields=["parent", "against_sales_order"],
            distinct=True
        )
        
        if delivery_notes:
            # Lieferschein existiert bereits → setze Delivery-Status direkt (ohne erneute Billing-Prüfung)
            frappe.log_error(f"Lieferschein bereits vorhanden für Subscription {subscription_name} - setze Delivery-Status direkt", 
                           "DEBUG: delivery_already_exists")
            
            # Setze per_delivered=100 für ALLE
            for so in sales_orders:
                so_doc = frappe.get_doc("Sales Order", so.name)
                current_per_billed = flt(so_doc.per_billed) or 0
                frappe.db.set_value("Sales Order", so.name, {
                    "per_delivered": 100,
                    "delivery_status": "Fully Delivered"
                }, update_modified=False)
                so_doc.reload()
                so_doc.set_status(update=True)
                
                # WICHTIG: Setze Status auch direkt auf "Completed" wenn beide Bedingungen erfüllt sind
                if current_per_billed >= 100:
                    frappe.db.set_value("Sales Order", so.name, "status", "Completed", update_modified=False)
                    so_doc.reload()
            
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Prüfen des Delivery-Status: {str(e)}", 
                        "ERROR: check_delivery_status")


def update_subscription_delivery_status(subscription_name):
    """
    Prüft ob ein Lieferschein existiert und setzt per_delivered=100 
    für ALLE Sales Orders der Subscription
    """
    try:
        # Finde alle Sales Orders der Subscription
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        if not sales_orders:
            frappe.log_error(f"Keine Sales Orders für Subscription {subscription_name} gefunden", 
                           "DEBUG: no_sales_orders")
            return
        
        # Prüfe ob für einen der Sales Orders ein gebuchter Lieferschein existiert
        delivery_notes = frappe.get_all(
            "Delivery Note Item",
            filters={
                "against_sales_order": ["in", [so.name for so in sales_orders]],
                "docstatus": 1
            },
            fields=["parent", "against_sales_order"],
            distinct=True
        )
        
        if not delivery_notes:
            frappe.log_error(f"Kein Lieferschein für Subscription {subscription_name}", 
                           "DEBUG: no_delivery_note")
            return
        
        frappe.log_error(f"Lieferschein für Subscription {subscription_name} gefunden - setze Status!", 
                        "INFO: delivery_found")
        
        # Setze per_delivered=100 und delivery_status="Fully Delivered" für ALLE
        for so in sales_orders:
            # Lade das Dokument um den aktuellen per_billed Status zu prüfen
            so_doc = frappe.get_doc("Sales Order", so.name)
            current_per_billed = flt(so_doc.per_billed) or 0
            
            # Setze Delivery-Status
            frappe.db.set_value("Sales Order", so.name, {
                "per_delivered": 100,
                "delivery_status": "Fully Delivered"
            }, update_modified=False)
            
            # Wenn bereits bezahlt (per_billed=100), dann sollte Status "Completed" sein
            # Aktualisiere den Gesamtstatus
            so_doc.reload()
            so_doc.set_status(update=True)
            
            # WICHTIG: Setze Status auch direkt auf "Completed" wenn beide Bedingungen erfüllt sind
            if current_per_billed >= 100:
                frappe.db.set_value("Sales Order", so.name, "status", "Completed", update_modified=False)
                so_doc.reload()
            
            frappe.log_error(f"Sales Order {so.name}: per_delivered=100, delivery_status=Fully Delivered, per_billed={current_per_billed}, Status={so_doc.status}", 
                           "SUCCESS: delivery_status_updated")
        
        frappe.db.commit()
        
        # Nach dem Delivery-Update: Prüfe auch ob bereits Billing vorhanden ist
        # Falls ja, sollten alle Orders bereits "Completed" sein
        # (nur wenn noch nicht alle Orders per_billed=100 haben)
        all_orders_check = frappe.get_all(
            "Sales Order",
            filters={
                "custom_subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name", "per_billed"]
        )
        if not all(flt(so.per_billed) >= 100 for so in all_orders_check):
            update_subscription_billing_status_if_exists(subscription_name)
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Delivery-Status: {str(e)}", 
                        "ERROR: update_delivery_status")


@frappe.whitelist()
def recalculate_subscription_status(subscription_name):
    """
    Manuelles Neuberechnen des Status für eine Subscription
    """
    try:
        frappe.log_error(f"Manuelles Status-Update für Subscription {subscription_name}", 
                        "INFO: manual_update")
        
        update_subscription_billing_status(subscription_name)
        update_subscription_delivery_status(subscription_name)
        
        return {
            "success": True,
            "message": f"Status wurde aktualisiert für Subscription {subscription_name}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
