import frappe
import stripe
from frappe import _

@frappe.whitelist(allow_guest=True)
def webhook_handler():
    """
    Stripe Webhook Handler für Payment Updates
    """
    try:
        # WICHTIG: Setze Administrator als User, damit Berechtigungen vorhanden sind
        frappe.set_user("Administrator")
        
        # Hole Request Body
        payload = frappe.request.get_data()
        
        # Parse JSON direkt (ohne Signatur-Verifizierung für Testing)
        import json
        event = json.loads(payload)
        
        # Handle checkout.session.completed Event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Hole Payment Request Name aus Metadata
            payment_request_name = session['metadata'].get('payment_request')
            
            if payment_request_name:
                # Hole Payment Request
                payment_request = frappe.get_doc("Payment Request", payment_request_name)
                
                # WICHTIG: Speichere Stripe Subscription ID falls vorhanden
                if session.get('subscription'):
                    stripe_subscription_id = session['subscription']
                    erpnext_subscription = session['metadata'].get('subscription')
                    if erpnext_subscription:
                        # Speichere Stripe Subscription ID in ERPNext Subscription als Custom Field oder Kommentar
                        frappe.log_error(f"WEBHOOK: Stripe Subscription ID {stripe_subscription_id} für ERPNext Subscription {erpnext_subscription}", "DEBUG: stripe_webhook")
                        # Speichere in Subscription DocType (wird später für Kündigung benötigt)
                        # Wir können es in einem Kommentar oder Custom Field speichern
                        # Für jetzt einfach loggen - die Funktion findet es über Payment Entries
                
                # Setze Status auf Paid
                payment_request.db_set('status', 'Paid', update_modified=False)
                
                # Erstelle Payment Entry direkt
                try:
                    # Prüfe ob bereits ein Payment Entry existiert
                    existing_entries = frappe.get_all("Payment Entry",
                        filters={
                            "reference_doctype": "Payment Request",
                            "reference_name": payment_request_name,
                            "docstatus": ["!=", 2]
                        }
                    )
                    
                    if not existing_entries:
                        # Lade Payment Request neu, um sicherzustellen, dass alle Daten aktuell sind
                        payment_request.reload()
                        
                        # Erstelle Payment Entry
                        payment_entry = payment_request.create_payment_entry()
                        payment_entry.reference_no = session['id']
                        payment_entry.reference_date = frappe.utils.nowdate()
                        
                        # Stelle sicher, dass der Payment Entry korrekt konfiguriert ist
                        frappe.log_error(f"WEBHOOK: Erstelle Payment Entry für Payment Request {payment_request_name}, Invoice: {payment_request.reference_name}", "DEBUG: stripe_webhook")
                        
                        payment_entry.insert(ignore_permissions=True)
                        frappe.log_error(f"WEBHOOK: Payment Entry {payment_entry.name} eingefügt", "DEBUG: stripe_webhook")
                        
                        payment_entry.submit()
                        frappe.db.commit()
                        
                        frappe.log_error(f"Payment Entry {payment_entry.name} erstellt und submitted für Payment Request {payment_request_name}", "SUCCESS: stripe_webhook")
                    else:
                        frappe.log_error(f"Payment Entry existiert bereits für Payment Request {payment_request_name}: {existing_entries[0].name}", "INFO: stripe_webhook")
                        
                except Exception as e:
                    frappe.log_error(f"Fehler beim Erstellen der Payment Entry für Payment Request {payment_request_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: stripe_webhook")
                
                frappe.log_error(f"Payment Request {payment_request_name} als bezahlt markiert", "SUCCESS: stripe_webhook")
        
        return {"status": "success"}
        
    except Exception as e:
        frappe.log_error(f"Fehler im Webhook Handler: {str(e)}", "ERROR: stripe_webhook")
        return {"status": "error", "message": str(e)}

