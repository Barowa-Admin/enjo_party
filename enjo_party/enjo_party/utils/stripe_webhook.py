import frappe
import stripe
from frappe import _

@frappe.whitelist(allow_guest=True)
def webhook_handler():
    """
    Stripe Webhook Handler für Payment Updates
    """
    try:
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
                
                # Setze Status auf Paid
                payment_request.db_set('status', 'Paid', update_modified=False)
                
                # Erstelle Payment Entry
                try:
                    payment_entry = payment_request.create_payment_entry()
                    payment_entry.reference_no = session['id']
                    payment_entry.reference_date = frappe.utils.nowdate()
                    payment_entry.insert(ignore_permissions=True)
                    payment_entry.submit()
                    
                    frappe.log_error(f"Payment Entry {payment_entry.name} erstellt für Payment Request {payment_request_name}", "SUCCESS: stripe_webhook")
                except Exception as e:
                    frappe.log_error(f"Fehler beim Erstellen der Payment Entry: {str(e)}", "ERROR: stripe_webhook")
                
                frappe.log_error(f"Payment Request {payment_request_name} als bezahlt markiert", "SUCCESS: stripe_webhook")
        
        return {"status": "success"}
        
    except Exception as e:
        frappe.log_error(f"Fehler im Webhook Handler: {str(e)}", "ERROR: stripe_webhook")
        return {"status": "error", "message": str(e)}

