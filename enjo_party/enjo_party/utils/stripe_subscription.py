import frappe
import stripe
from frappe import _

def cancel_stripe_subscription_at_period_end(erpnext_subscription_name):
    """
    Kündigt die Stripe Subscription zum Ende der Periode
    """
    try:
        # Hole Stripe Settings
        stripe_settings = frappe.get_doc("Stripe Settings", "Stripe")
        
        # Setze API Key (verschlüsselt gespeichert)
        api_key = frappe.utils.password.get_decrypted_password("Stripe Settings", "Stripe", "secret_key")
        if not api_key:
            frappe.log_error("Stripe Secret Key ist nicht konfiguriert", "ERROR: stripe_subscription_cancel")
            return False
        
        stripe.api_key = api_key
        
        # Finde alle Invoices zu dieser Subscription
        invoices = frappe.get_all("Sales Invoice",
            filters={
                "subscription": erpnext_subscription_name,
                "docstatus": 1
            },
            fields=["name"],
            order_by="creation desc",
            limit=5
        )
        
        stripe_subscription_id = None
        
        # Suche über Payment Requests und Checkout Sessions
        for invoice in invoices:
            payment_requests = frappe.get_all("Payment Request",
                filters={
                    "reference_doctype": "Sales Invoice",
                    "reference_name": invoice.name,
                    "docstatus": ["!=", 2]  # Auch Draft erlauben
                },
                fields=["name"],
                limit=1
            )
            
            if payment_requests:
                # Methode 1: Über Payment Entry → Session
                payment_entries = frappe.get_all("Payment Entry",
                    filters={
                        "reference_doctype": "Payment Request",
                        "reference_name": payment_requests[0].name,
                        "docstatus": 1
                    },
                    fields=["reference_no"],
                    limit=1
                )
                
                if payment_entries and payment_entries[0].reference_no:
                    session_id = payment_entries[0].reference_no
                    try:
                        session = stripe.checkout.Session.retrieve(session_id)
                        if session.get('subscription'):
                            stripe_subscription_id = session['subscription']
                            frappe.log_error(f"Stripe Subscription ID über Payment Entry Session gefunden: {stripe_subscription_id}", "DEBUG: stripe_subscription_cancel")
                            break
                    except Exception as e:
                        frappe.log_error(f"Fehler beim Abrufen der Stripe Session {session_id}: {str(e)}", "DEBUG: stripe_subscription_cancel")
                
                # Methode 2: Direkt alle Stripe Subscriptions durchsuchen (mit Metadata-Filter)
                if not stripe_subscription_id:
                    try:
                        # Suche alle Stripe Subscriptions und filtere nach unserer ERPNext Subscription ID in Metadata
                        subscriptions = stripe.Subscription.list(limit=100, status='active')
                        for sub in subscriptions:
                            # Prüfe ob diese Subscription zu unserer ERPNext Subscription gehört
                            if sub.metadata and sub.metadata.get('subscription') == erpnext_subscription_name:
                                stripe_subscription_id = sub.id
                                frappe.log_error(f"Stripe Subscription ID über Subscription-Liste gefunden: {stripe_subscription_id}", "DEBUG: stripe_subscription_cancel")
                                break
                    except Exception as e:
                        frappe.log_error(f"Fehler bei Stripe Subscription-Liste: {str(e)}", "DEBUG: stripe_subscription_cancel")
        
        if not stripe_subscription_id:
            frappe.log_error(f"Keine Stripe Subscription ID gefunden für ERPNext Subscription {erpnext_subscription_name}", "WARNING: stripe_subscription_cancel")
            return False
        
        # Kündige die Stripe Subscription zum Ende der Periode
        stripe.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        frappe.log_error(f"Stripe Subscription {stripe_subscription_id} wird zum Ende der Periode gekündigt", "SUCCESS: stripe_subscription_cancel")
        return True
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Kündigen der Stripe Subscription für {erpnext_subscription_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: stripe_subscription_cancel")
        return False

