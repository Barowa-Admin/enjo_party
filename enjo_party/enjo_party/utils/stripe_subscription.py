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
        
        # Hole Subscription Details
        subscription_doc = frappe.get_doc("Subscription", erpnext_subscription_name)
        customer = subscription_doc.party
        
        # Hole Customer Email
        customer_email = frappe.db.get_value("Customer", customer, "email_id")
        
        frappe.log_error(f"Suche Stripe Subscription für ERPNext Subscription {erpnext_subscription_name}, Customer: {customer}, Email: {customer_email}", "DEBUG: stripe_subscription_cancel")
        
        stripe_subscription_id = None
        
        # Methode 1: Prüfe Custom Field (zuverlässigste Methode - wird vom Webhook gespeichert)
        if frappe.db.has_column("Subscription", "custom_stripe_subscription_id"):
            stripe_subscription_id = frappe.db.get_value("Subscription", erpnext_subscription_name, "custom_stripe_subscription_id")
            if stripe_subscription_id:
                frappe.log_error(f"Stripe Subscription ID gefunden in Custom Field: {stripe_subscription_id} für {erpnext_subscription_name}", "DEBUG: stripe_subscription_cancel")
        
        # Methode 1b: Falls Custom Field leer, suche in Kommentaren (Fallback wenn Custom Field nicht existiert)
        if not stripe_subscription_id:
            try:
                comments = frappe.get_all("Comment",
                    filters={
                        "reference_doctype": "Subscription",
                        "reference_name": erpnext_subscription_name,
                        "comment_type": "Comment"
                    },
                    fields=["content"],
                    order_by="creation desc",
                    limit=10
                )
                
                for comment in comments:
                    content = comment.get("content", "")
                    # Suche nach "Stripe Subscription ID: sub_..."
                    if "Stripe Subscription ID:" in content:
                        import re
                        match = re.search(r'Stripe Subscription ID:\s*(sub_[a-zA-Z0-9]+)', content)
                        if match:
                            stripe_subscription_id = match.group(1)
                            frappe.log_error(f"Stripe Subscription ID gefunden in Kommentar: {stripe_subscription_id} für {erpnext_subscription_name}", "DEBUG: stripe_subscription_cancel")
                            break
            except Exception as e:
                frappe.log_error(f"Fehler beim Lesen der Kommentare: {str(e)}", "DEBUG: stripe_subscription_cancel")
        
        # Methode 2: Suche direkt ALLE aktiven Stripe Subscriptions und finde die passende (nur wenn Custom Field leer ist)
        if not stripe_subscription_id:
            try:
                frappe.log_error(f"Starte Suche in Stripe Subscriptions...", "DEBUG: stripe_subscription_cancel")
                subscriptions = stripe.Subscription.list(limit=100, status='active')
                frappe.log_error(f"Gefundene Stripe Subscriptions: {len(subscriptions.data)}", "DEBUG: stripe_subscription_cancel")
                
                for sub in subscriptions.data:
                    # Prüfe Metadata - sollte die ERPNext Subscription ID enthalten
                    sub_metadata = sub.metadata or {}
                    if sub_metadata.get('subscription') == erpnext_subscription_name:
                        stripe_subscription_id = sub.id
                        frappe.log_error(f"Stripe Subscription ID über Metadata Match gefunden: {stripe_subscription_id} (Metadata: {sub_metadata})", "DEBUG: stripe_subscription_cancel")
                        break
                    else:
                        frappe.log_error(f"Prüfe Subscription {sub.id}, Metadata: {sub_metadata}, suche nach: {erpnext_subscription_name}", "DEBUG: stripe_subscription_cancel")
                
                # Falls nicht gefunden, suche über Checkout Sessions
                if not stripe_subscription_id and customer_email:
                    frappe.log_error(f"Suche in Checkout Sessions für Email: {customer_email}", "DEBUG: stripe_subscription_cancel")
                    sessions = stripe.checkout.Session.list(limit=50)
                    for sess in sessions.data:
                        sess_metadata = sess.metadata or {}
                        if sess.get('customer_email') == customer_email and sess.get('subscription'):
                            if sess_metadata.get('subscription') == erpnext_subscription_name:
                                stripe_subscription_id = sess['subscription']
                                frappe.log_error(f"Stripe Subscription ID über Checkout Session gefunden: {stripe_subscription_id}", "DEBUG: stripe_subscription_cancel")
                                break
            except Exception as e:
                frappe.log_error(f"Fehler bei Stripe-Suche: {str(e)}\n{frappe.get_traceback()}", "ERROR: stripe_subscription_cancel")
        
        # Methode 3: Fallback - über Payment Entry → Session (nur wenn noch nicht gefunden)
        if not stripe_subscription_id:
            invoices = frappe.get_all("Sales Invoice",
                filters={
                    "subscription": erpnext_subscription_name,
                    "docstatus": 1
                },
                fields=["name"],
                order_by="creation desc",
                limit=3
            )
            
            for invoice in invoices:
                payment_requests = frappe.get_all("Payment Request",
                    filters={
                        "reference_doctype": "Sales Invoice",
                        "reference_name": invoice.name,
                        "docstatus": ["!=", 2]
                    },
                    fields=["name"],
                    limit=1
                )
                
                if payment_requests:
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
                                frappe.log_error(f"Stripe Subscription ID über Payment Entry gefunden: {stripe_subscription_id}", "DEBUG: stripe_subscription_cancel")
                                break
                        except Exception as e:
                            frappe.log_error(f"Fehler beim Abrufen der Session {session_id}: {str(e)}", "DEBUG: stripe_subscription_cancel")
        
        if not stripe_subscription_id:
            frappe.log_error(f"Keine Stripe Subscription ID gefunden für ERPNext Subscription {erpnext_subscription_name}", "WARNING: stripe_subscription_cancel")
            return False
        
        # Prüfe zuerst den aktuellen Status der Stripe Subscription
        try:
            current_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            current_status = current_subscription.get('status')
            current_cancel_at_period_end = current_subscription.get('cancel_at_period_end')
            
            frappe.log_error(f"Stripe Subscription Status: {current_status}, cancel_at_period_end: {current_cancel_at_period_end}", "DEBUG: stripe_subscription_cancel")
            
            # Wenn bereits gekündigt oder cancel_at_period_end bereits True ist, ist alles gut
            if current_status == 'canceled' or current_cancel_at_period_end:
                frappe.log_error(f"Stripe Subscription {stripe_subscription_id} ist bereits gekündigt oder wird bereits gekündigt", "INFO: stripe_subscription_cancel")
                return True
            
            # Kündige die Stripe Subscription zum Ende der Periode
            # Das bedeutet: Aktuelle Periode läuft noch, aber keine neue Periode wird mehr gestartet
            frappe.log_error(f"Rufe Stripe API auf: stripe.Subscription.modify({stripe_subscription_id}, cancel_at_period_end=True)", "DEBUG: stripe_subscription_cancel")
            
            modified_subscription = stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            frappe.log_error(f"Stripe API Antwort: cancel_at_period_end={modified_subscription.get('cancel_at_period_end')}, status={modified_subscription.get('status')}", "DEBUG: stripe_subscription_cancel")
            frappe.log_error(f"Stripe Subscription {stripe_subscription_id} wird zum Ende der Periode gekündigt (keine weiteren Abbuchungen)", "SUCCESS: stripe_subscription_cancel")
            return True
            
        except stripe.error.InvalidRequestError as e:
            # Wenn die Subscription bereits gekündigt ist, ist das OK
            error_message = str(e)
            if "canceled subscription" in error_message.lower() or "can only update" in error_message.lower():
                frappe.log_error(f"Stripe Subscription {stripe_subscription_id} ist bereits gekündigt - das ist OK", "INFO: stripe_subscription_cancel")
                return True
            else:
                frappe.log_error(f"Stripe API Fehler: {str(e)} (Type: {type(e).__name__})", "ERROR: stripe_subscription_cancel")
                raise
        except stripe.error.StripeError as e:
            frappe.log_error(f"Stripe API Fehler: {str(e)} (Type: {type(e).__name__})", "ERROR: stripe_subscription_cancel")
            raise
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Kündigen der Stripe Subscription für {erpnext_subscription_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: stripe_subscription_cancel")
        return False


@frappe.whitelist()
def cancel_subscription_in_stripe(subscription_name):
    """
    Server-Funktion um Stripe Subscription direkt zu kündigen
    Wird vom Client-Script aufgerufen
    """
    try:
        frappe.log_error(f"Server-Funktion aufgerufen: cancel_subscription_in_stripe für {subscription_name}", "DEBUG: stripe_subscription_cancel")
        result = cancel_stripe_subscription_at_period_end(subscription_name)
        if result:
            return {"success": True, "message": "Stripe Subscription wurde erfolgreich gekündigt"}
        else:
            return {"success": False, "message": "Stripe Subscription ID nicht gefunden"}
    except Exception as e:
        frappe.log_error(f"Fehler in cancel_subscription_in_stripe für {subscription_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: stripe_subscription_cancel")
        return {"success": False, "message": str(e)}

