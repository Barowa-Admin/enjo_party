# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

"""
Subscription-Status-Indikator

Berechnet den Zahlungsstatus für Subscriptions (ABOs) basierend auf:
- Zahlungsstatus der Rechnungen (outstanding_amount)
- Überfälligkeit (due_date + 5 Tage)
- Stornierte Rechnungen (Retourniert)
- Kündigungsstatus (cancel_at_period_end, status=Cancelled)

Status-Hierarchie:
1. Beendet - cancel_at_period_end=1 ODER status='Cancelled'
2. Retourniert - Mind. 1 stornierte Rechnung (docstatus=2)
3. Überfällig - Mind. 1 Rechnung mit outstanding_amount>0 UND due_date + 5 Tage < heute
4. Unbezahlt - Mind. 1 Rechnung mit outstanding_amount>0, aber noch nicht überfällig
5. Bezahlt - Alle Rechnungen bezahlt
"""

import frappe
from frappe.utils import flt, add_days, getdate, today


# Anzahl Tage nach Fälligkeit bis "Überfällig"
OVERDUE_DAYS = 5


def calculate_subscription_payment_status(subscription_name):
    """
    Berechnet den Zahlungsstatus für eine Subscription.
    
    Rückgabe: Der berechnete Status-String (Bezahlt, Unbezahlt, Überfällig, Retourniert, Beendet)
    """
    try:
        # Prüfe den Subscription-Status
        sub_data = frappe.db.get_value("Subscription", subscription_name, 
                                        ["status", "cancel_at_period_end"], as_dict=True)
        
        if not sub_data:
            return None
        
        # 1. Prüfe auf Beendet (Cancelled oder cancel_at_period_end)
        if sub_data.status == "Cancelled" or sub_data.cancel_at_period_end == 1:
            return "Beendet"
        
        # Hole alle Rechnungen dieser Subscription
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "subscription": subscription_name
            },
            fields=["name", "docstatus", "outstanding_amount", "due_date", "grand_total"]
        )
        
        if not invoices:
            # Keine Rechnungen - Subscription ist aktiv aber noch keine Abrechnung
            return "Bezahlt"  # Oder "Aktiv"?
        
        # 2. Prüfe auf stornierte Rechnungen (Retourniert)
        cancelled_invoices = [inv for inv in invoices if inv.docstatus == 2]
        if cancelled_invoices:
            return "Retourniert"
        
        # Filtere nur gebuchte Rechnungen für weitere Prüfungen
        submitted_invoices = [inv for inv in invoices if inv.docstatus == 1]
        
        if not submitted_invoices:
            # Keine gebuchten Rechnungen
            return "Bezahlt"
        
        # 3. Prüfe auf überfällige Rechnungen
        today_date = getdate(today())
        has_overdue = False
        has_unpaid = False
        
        for inv in submitted_invoices:
            if flt(inv.outstanding_amount) > 0.01:
                has_unpaid = True
                # Prüfe Fälligkeit
                if inv.due_date:
                    overdue_date = add_days(inv.due_date, OVERDUE_DAYS)
                    if getdate(overdue_date) < today_date:
                        has_overdue = True
                        break
        
        if has_overdue:
            return "Überfällig"
        
        if has_unpaid:
            return "Unbezahlt"
        
        # Alle Rechnungen bezahlt
        return "Bezahlt"
        
    except Exception as e:
        frappe.log_error(f"Fehler bei Status-Berechnung für Subscription {subscription_name}: {str(e)}", 
                        "ERROR: calculate_subscription_payment_status")
        return None


def update_subscription_payment_status(subscription_name):
    """
    Berechnet und speichert den Zahlungsstatus für eine Subscription im Custom Field.
    """
    try:
        new_status = calculate_subscription_payment_status(subscription_name)
        
        if new_status:
            # Prüfe ob Custom Field existiert
            if frappe.db.has_column("Subscription", "custom_payment_status"):
                current_status = frappe.db.get_value("Subscription", subscription_name, "custom_payment_status")
                
                if new_status != current_status:
                    frappe.db.set_value("Subscription", subscription_name, 
                                       "custom_payment_status", new_status, 
                                       update_modified=False)
                    frappe.db.commit()
                    
                    frappe.log_error(f"Subscription {subscription_name}: Status geändert von '{current_status}' auf '{new_status}'", 
                                   "INFO: subscription_status_updated")
            else:
                frappe.log_error("Custom Field 'custom_payment_status' existiert nicht in Subscription", 
                               "WARNING: subscription_status_indicator")
        
        return new_status
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Status-Update für Subscription {subscription_name}: {str(e)}", 
                        "ERROR: update_subscription_payment_status")
        return None


@frappe.whitelist()
def get_subscription_payment_status(subscription_name):
    """
    Whitelist-Funktion zum Abrufen des Zahlungsstatus einer Subscription.
    Kann vom Frontend aufgerufen werden.
    """
    return calculate_subscription_payment_status(subscription_name)


@frappe.whitelist()
def recalculate_subscription_payment_status(subscription_name):
    """
    Manuelles Neuberechnen des Zahlungsstatus für eine Subscription.
    """
    try:
        new_status = update_subscription_payment_status(subscription_name)
        
        return {
            "success": True,
            "status": new_status,
            "message": f"Zahlungsstatus wurde auf '{new_status}' aktualisiert"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def recalculate_all_subscription_payment_status():
    """
    Berechnet den Zahlungsstatus für ALLE aktiven Subscriptions neu.
    """
    try:
        subscriptions = frappe.get_all(
            "Subscription",
            filters={"status": ["in", ["Active", "Past Due Date", "Unpaid"]]},
            fields=["name"]
        )
        
        updated = 0
        for sub in subscriptions:
            try:
                update_subscription_payment_status(sub.name)
                updated += 1
            except Exception as e:
                frappe.log_error(f"Fehler bei Subscription {sub.name}: {str(e)}", 
                               "ERROR: batch_update")
        
        return {
            "success": True,
            "message": f"{updated} Subscriptions aktualisiert"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
