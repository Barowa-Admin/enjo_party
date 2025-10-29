import frappe
from frappe import _
from enjo_party.enjo_party.utils.stripe_checkout import create_stripe_checkout_session

def force_subscription_update(doc, method):
    """
    Wird nach dem Speichern eines Abonnements ausgeführt und erzwingt sofort ein Update
    """
    try:
        frappe.log_error(f"SUBSCRIPTION HOOK: Wurde aufgerufen für Subscription {doc.name}, Status: {doc.status}, Method: {method}", "DEBUG: subscription_hook")
        
        # Prüfe ob das Abo aktiv ist (Status "Active")
        if doc.status == "Active":
            frappe.log_error(f"SUBSCRIPTION HOOK: Subscription {doc.name} ist aktiv, starte process()", "DEBUG: subscription_hook")
            
            # Hole die process() Methode aus der Subscription
            subscription = frappe.get_doc("Subscription", doc.name)
            
            # Prüfe ob das Startdatum heute oder in der Vergangenheit ist
            if subscription.start_date <= frappe.utils.today():
                frappe.log_error(f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist erreicht, führe process() aus", "DEBUG: subscription_hook")
                
                subscription.process()
                frappe.db.commit()
                
                frappe.log_error(f"SUBSCRIPTION HOOK: process() abgeschlossen für {doc.name}", "DEBUG: subscription_hook")
                
                # Erstelle Payment Request für die generierte Rechnung
                invoices = frappe.get_all("Sales Invoice", 
                    filters={
                        "subscription": doc.name,
                        "docstatus": 1
                    },
                    order_by="creation desc",
                    limit=1
                )
                
                frappe.log_error(f"SUBSCRIPTION HOOK: Gefundene Invoices: {len(invoices)}", "DEBUG: subscription_hook")
                
                if invoices:
                    invoice = frappe.get_doc("Sales Invoice", invoices[0].name)
                    
                    frappe.log_error(f"SUBSCRIPTION HOOK: Erstelle Payment Request für Invoice {invoice.name}", "DEBUG: subscription_hook")
                    
                    # Payment Request erstellen
                    payment_request = frappe.get_doc({
                        "doctype": "Payment Request",
                        "payment_request_type": "Inward",
                        "transaction_date": invoice.posting_date,
                        "party_type": "Customer",
                        "party": invoice.customer,
                        "reference_doctype": "Sales Invoice",
                        "reference_name": invoice.name,
                        "payment_gateway_account": "Stripe-Stripe - EUR",  # Dein Payment Gateway
                        "grand_total": invoice.grand_total,
                        "currency": invoice.currency,
                        "email_to": invoice.contact_email,
                        "subject": f"Zahlungsaufforderung für Rechnung {invoice.name}"
                    })
                    payment_request.insert(ignore_permissions=True)
                    payment_request.submit()
                    
                    # Erstelle echten Stripe Checkout Link
                    stripe_url = create_stripe_checkout_session(payment_request)
                    if stripe_url:
                        payment_request.db_set('payment_url', stripe_url, update_modified=False)
                        frappe.log_error(f"SUBSCRIPTION HOOK: Stripe Checkout URL erstellt: {stripe_url}", "SUCCESS: subscription_hook")
                    
                    frappe.log_error(f"SUBSCRIPTION HOOK: Payment Request {payment_request.name} erstellt", "SUCCESS: subscription_hook")
                
                frappe.msgprint(_("Abonnement-Update und Payment Request wurden automatisch erstellt"))
            else:
                frappe.log_error(f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist noch nicht erreicht", "DEBUG: subscription_hook")
                frappe.msgprint(_("Abonnement-Update wird erst am Startdatum ausgeführt"))
        else:
            frappe.log_error(f"SUBSCRIPTION HOOK: Subscription {doc.name} ist nicht aktiv (Status: {doc.status})", "DEBUG: subscription_hook")
            
    except Exception as e:
        frappe.log_error(f"SUBSCRIPTION HOOK FEHLER für {doc.name}: {str(e)}", "ERROR: subscription_hook")


def create_payment_request_for_subscription_invoice(doc, method):
    """
    Erstellt automatisch Payment Request für alle Sales Invoices die zu einem Abonnement gehören
    Wird bei Sales Invoice on_submit ausgelöst
    """
    try:
        # Prüfe ob die Rechnung zu einem Abonnement gehört
        if doc.subscription and doc.docstatus == 1:
            # Prüfe ob bereits eine Payment Request existiert
            existing_requests = frappe.get_all("Payment Request",
                filters={
                    "reference_doctype": "Sales Invoice",
                    "reference_name": doc.name,
                    "docstatus": ["!=", 2]  # Nicht storniert
                }
            )
            
            if not existing_requests:
                # Payment Request erstellen
                payment_request = frappe.get_doc({
                    "doctype": "Payment Request",
                    "payment_request_type": "Inward",
                    "transaction_date": doc.posting_date,
                    "party_type": "Customer",
                    "party": doc.customer,
                    "reference_doctype": "Sales Invoice",
                    "reference_name": doc.name,
                    "payment_gateway_account": "Stripe-Stripe - EUR",  # Dein Payment Gateway
                    "grand_total": doc.grand_total,
                    "currency": doc.currency,
                    "email_to": doc.contact_email,
                    "subject": f"Zahlungsaufforderung für Rechnung {doc.name}"
                })
                payment_request.insert(ignore_permissions=True)
                payment_request.submit()
                
                # Erstelle echten Stripe Checkout Link
                stripe_url = create_stripe_checkout_session(payment_request)
                if stripe_url:
                    payment_request.db_set('payment_url', stripe_url, update_modified=False)
                    frappe.log_error(f"Stripe Checkout URL für {payment_request.name} erstellt: {stripe_url}", "SUCCESS: subscription_payment_request")
                
                frappe.log_error(f"Payment Request {payment_request.name} für Subscription Invoice {doc.name} erstellt", "SUCCESS: subscription_payment_request")
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Erstellen der Payment Request für Subscription Invoice {doc.name}: {str(e)}", "ERROR: subscription_payment_request")
