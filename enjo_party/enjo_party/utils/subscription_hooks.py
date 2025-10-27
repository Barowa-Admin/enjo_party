import frappe
from frappe import _

def force_subscription_update(doc, method):
    """
    Wird nach dem Speichern eines Abonnements ausgeführt und erzwingt sofort ein Update
    """
    try:
        # Prüfe ob das Abo aktiv ist (Status "Active")
        if doc.status == "Active":
            # Hole die process() Methode aus der Subscription
            subscription = frappe.get_doc("Subscription", doc.name)
            
            # Prüfe ob das Startdatum heute oder in der Vergangenheit ist
            if subscription.start_date <= frappe.utils.today():
                subscription.process()
                frappe.db.commit()
                
                # Erstelle Payment Request für die generierte Rechnung
                invoices = frappe.get_all("Sales Invoice", 
                    filters={
                        "subscription": doc.name,
                        "docstatus": 1
                    },
                    order_by="creation desc",
                    limit=1
                )
                
                if invoices:
                    invoice = frappe.get_doc("Sales Invoice", invoices[0].name)
                    
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
                        "email_to": invoice.contact_email
                    })
                    payment_request.insert(ignore_permissions=True)
                    payment_request.submit()
                
                frappe.msgprint(_("Abonnement-Update und Payment Request wurden automatisch erstellt"))
            else:
                frappe.msgprint(_("Abonnement-Update wird erst am Startdatum ausgeführt"))
            
    except Exception as e:
        frappe.log_error(f"Fehler beim automatischen Subscription Update: {str(e)}")


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
                    "email_to": doc.contact_email
                })
                payment_request.insert(ignore_permissions=True)
                payment_request.submit()
                
                frappe.log_error(f"Payment Request {payment_request.name} für Subscription Invoice {doc.name} erstellt", "SUCCESS: subscription_payment_request")
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Erstellen der Payment Request für Subscription Invoice {doc.name}: {str(e)}", "ERROR: subscription_payment_request")
