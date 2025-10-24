import frappe
from frappe import _

def force_subscription_update(doc, method):
    """
    Wird nach dem Submit eines Abonnements ausgeführt und erzwingt sofort ein Update
    """
    try:
        if doc.docstatus == 1:  # Nur bei Submit
            # Hole die process() Methode aus der Subscription
            subscription = frappe.get_doc("Subscription", doc.name)
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
            
    except Exception as e:
        frappe.log_error(f"Fehler beim automatischen Subscription Update: {str(e)}")
