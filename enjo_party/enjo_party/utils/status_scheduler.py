# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

"""
Status-Scheduler

Täglicher Job zur Aktualisierung der Status für:
- Sammelbestellungen (Überfällig, Ausgeliefert)
- Parties/Präsentationen (Überfällig, Ausgeliefert)
- Subscriptions/ABOs (Überfällig, Unbezahlt, Bezahlt)

Wird einmal täglich ausgeführt um zeitbasierte Status zu aktualisieren.
"""

import frappe
from frappe.utils import flt


def update_overdue_status():
    """
    Hauptfunktion für den täglichen Scheduler-Job.
    Aktualisiert den Status für alle relevanten DocTypes.
    """
    frappe.log_error("Status-Scheduler gestartet", "INFO: status_scheduler")
    
    try:
        # 1. Sammelbestellungen aktualisieren
        update_sammelbestellung_overdue_status()
        
        # 2. Parties aktualisieren
        update_party_overdue_status()
        
        # 3. Subscriptions aktualisieren
        update_subscription_overdue_status()
        
        frappe.log_error("Status-Scheduler erfolgreich abgeschlossen", "INFO: status_scheduler")
        
    except Exception as e:
        frappe.log_error(f"Fehler im Status-Scheduler: {str(e)}", "ERROR: status_scheduler")


def update_sammelbestellung_overdue_status():
    """
    Aktualisiert den Überfälligkeits-Status für alle gebuchten Sammelbestellungen.
    """
    try:
        from enjo_party.enjo_party.utils.sammelbestellung_status import update_sammelbestellung_status
        
        # Hole alle gebuchten Sammelbestellungen die noch nicht "Ausgeliefert" sind
        sammelbestellungen = frappe.get_all(
            "Sammelbestellung",
            filters={
                "docstatus": 1,
                "status": ["in", ["Gebucht", "Überfällig"]]  # Nur diese Status prüfen
            },
            fields=["name"]
        )
        
        updated = 0
        for sb in sammelbestellungen:
            try:
                update_sammelbestellung_status(sb.name)
                updated += 1
            except Exception as e:
                frappe.log_error(f"Fehler bei Sammelbestellung {sb.name}: {str(e)}", 
                               "ERROR: status_scheduler_sammelbestellung")
        
        frappe.log_error(f"Sammelbestellungen aktualisiert: {updated}", "INFO: status_scheduler")
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Aktualisieren der Sammelbestellungen: {str(e)}", 
                        "ERROR: status_scheduler_sammelbestellung")


def update_party_overdue_status():
    """
    Aktualisiert den Überfälligkeits-Status für alle gebuchten Parties.
    """
    try:
        from enjo_party.enjo_party.utils.party_status import update_party_status
        
        # Hole alle gebuchten Parties die noch nicht "Ausgeliefert" sind
        parties = frappe.get_all(
            "Party",
            filters={
                "docstatus": 1,
                "status": ["in", ["Gebucht", "Überfällig"]]  # Nur diese Status prüfen
            },
            fields=["name"]
        )
        
        updated = 0
        for party in parties:
            try:
                update_party_status(party.name)
                updated += 1
            except Exception as e:
                frappe.log_error(f"Fehler bei Party {party.name}: {str(e)}", 
                               "ERROR: status_scheduler_party")
        
        frappe.log_error(f"Parties aktualisiert: {updated}", "INFO: status_scheduler")
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Aktualisieren der Parties: {str(e)}", 
                        "ERROR: status_scheduler_party")


def update_subscription_overdue_status():
    """
    Aktualisiert den Zahlungsstatus für alle aktiven Subscriptions.
    """
    try:
        from enjo_party.enjo_party.utils.subscription_status_indicator import update_subscription_payment_status
        
        # Hole alle aktiven Subscriptions
        subscriptions = frappe.get_all(
            "Subscription",
            filters={
                "status": ["in", ["Active", "Past Due Date", "Unpaid"]]
            },
            fields=["name"]
        )
        
        updated = 0
        overdue_count = 0
        
        for sub in subscriptions:
            try:
                new_status = update_subscription_payment_status(sub.name)
                updated += 1
                
                # Zähle überfällige Subscriptions für Reporting
                if new_status == "Überfällig":
                    overdue_count += 1
                    # Optional: Zahlungserinnerung senden
                    # send_payment_reminder(sub.name)
                    
            except Exception as e:
                frappe.log_error(f"Fehler bei Subscription {sub.name}: {str(e)}", 
                               "ERROR: status_scheduler_subscription")
        
        frappe.log_error(f"Subscriptions aktualisiert: {updated}, davon überfällig: {overdue_count}", 
                        "INFO: status_scheduler")
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Aktualisieren der Subscriptions: {str(e)}", 
                        "ERROR: status_scheduler_subscription")


def send_payment_reminder(subscription_name):
    """
    Sendet eine Zahlungserinnerung für eine überfällige Subscription.
    
    TODO: Implementieren wenn gewünscht
    """
    try:
        # Hole Subscription Details
        subscription = frappe.get_doc("Subscription", subscription_name)
        
        # Hole letzte unbezahlte Rechnung
        invoice = frappe.get_all(
            "Sales Invoice",
            filters={
                "subscription": subscription_name,
                "docstatus": 1,
                "outstanding_amount": [">", 0]
            },
            fields=["name", "outstanding_amount", "due_date"],
            order_by="due_date asc",
            limit=1
        )
        
        if not invoice:
            return
        
        # TODO: E-Mail-Versand implementieren
        # frappe.sendmail(...)
        
        frappe.log_error(f"Zahlungserinnerung für Subscription {subscription_name} (Invoice: {invoice[0].name})", 
                        "INFO: payment_reminder")
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Senden der Zahlungserinnerung für {subscription_name}: {str(e)}", 
                        "ERROR: payment_reminder")


@frappe.whitelist()
def run_status_update_manually():
    """
    Whitelist-Funktion zum manuellen Auslösen des Status-Updates.
    Kann über die Konsole oder API aufgerufen werden.
    """
    update_overdue_status()
    return {"success": True, "message": "Status-Update wurde ausgeführt"}
