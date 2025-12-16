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
        
        # Handle checkout.session.completed Event (erstes Payment)
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
                        # Speichere Stripe Subscription ID in ERPNext Subscription
                        # Versuche Custom Field, falls nicht vorhanden, speichere in Kommentar
                        try:
                            # Prüfe ob Custom Field existiert
                            if frappe.db.has_column("Subscription", "custom_stripe_subscription_id"):
                                frappe.db.set_value("Subscription", erpnext_subscription, "custom_stripe_subscription_id", stripe_subscription_id, update_modified=False)
                                frappe.log_error(f"WEBHOOK: Stripe Subscription ID {stripe_subscription_id} in Custom Field gespeichert für {erpnext_subscription}", "DEBUG: stripe_webhook")
                            else:
                                # Fallback: Speichere in Kommentar
                                subscription_doc = frappe.get_doc("Subscription", erpnext_subscription)
                                subscription_doc.add_comment("Comment", f"Stripe Subscription ID: {stripe_subscription_id}")
                                frappe.log_error(f"WEBHOOK: Stripe Subscription ID {stripe_subscription_id} in Kommentar gespeichert für {erpnext_subscription}", "DEBUG: stripe_webhook")
                        except Exception as e:
                            frappe.log_error(f"WEBHOOK: Fehler beim Speichern der Stripe Subscription ID: {str(e)}", "ERROR: stripe_webhook")
                
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
        
        # Handle invoice.payment_succeeded Event (wiederkehrende Zahlungen - erfolgreich)
        elif event['type'] == 'invoice.payment_succeeded':
            invoice_obj = event['data']['object']
            stripe_subscription_id = invoice_obj.get('subscription')
            
            if stripe_subscription_id:
                # Finde ERPNext Subscription über Stripe Subscription ID
                erpnext_subscription = None
                
                # Methode 1: Prüfe Custom Field
                if frappe.db.has_column("Subscription", "custom_stripe_subscription_id"):
                    subscriptions = frappe.get_all("Subscription",
                        filters={"custom_stripe_subscription_id": stripe_subscription_id},
                        fields=["name"],
                        limit=1
                    )
                    if subscriptions:
                        erpnext_subscription = subscriptions[0].name
                
                # Methode 2: Fallback - suche über Payment Entries
                if not erpnext_subscription:
                    frappe.log_error(f"WEBHOOK: invoice.payment_succeeded für Stripe Subscription {stripe_subscription_id}, aber ERPNext Subscription nicht gefunden", "WARNING: stripe_webhook")
                    return {"status": "success"}
                
                # Finde die neueste unbezahlte Invoice für diese Subscription
                invoices = frappe.get_all("Sales Invoice",
                    filters={
                        "subscription": erpnext_subscription,
                        "docstatus": 1,
                        "status": ["!=", "Paid"]
                    },
                    fields=["name", "grand_total", "posting_date"],
                    order_by="posting_date desc",
                    limit=1
                )
                
                if invoices:
                    invoice_name = invoices[0].name
                    invoice = frappe.get_doc("Sales Invoice", invoice_name)
                    
                    # Erstelle Payment Entry für die Invoice
                    try:
                        # Prüfe ob bereits ein Payment Entry existiert
                        existing_entries = frappe.get_all("Payment Entry",
                            filters={
                                "reference_doctype": "Sales Invoice",
                                "reference_name": invoice_name,
                                "docstatus": ["!=", 2]
                            }
                        )
                        
                        if not existing_entries:
                            # Hole Account-Informationen
                            company = invoice.company
                            receivable_account = frappe.db.get_value("Company", company, "default_receivable_account")
                            if not receivable_account:
                                # Fallback: Suche nach Receivable Account
                                receivable_account = frappe.db.get_value("Account", 
                                    {"account_type": "Receivable", "company": company, "is_group": 0}, 
                                    "name")
                            
                            # Erstelle Payment Entry direkt für die Invoice
                            payment_entry = frappe.get_doc({
                                "doctype": "Payment Entry",
                                "payment_type": "Receive",
                                "party_type": "Customer",
                                "party": invoice.customer,
                                "posting_date": frappe.utils.nowdate(),
                                "company": company,
                                "paid_from": receivable_account,
                                "paid_to": receivable_account,
                                "paid_amount": invoice.grand_total,
                                "received_amount": invoice.grand_total,
                                "source_exchange_rate": 1,
                                "target_exchange_rate": 1,
                                "reference_no": invoice_obj.get('id', ''),
                                "reference_date": frappe.utils.nowdate(),
                                "references": [{
                                    "reference_doctype": "Sales Invoice",
                                    "reference_name": invoice_name,
                                    "allocated_amount": invoice.grand_total
                                }]
                            })
                            
                            payment_entry.insert(ignore_permissions=True)
                            payment_entry.submit()
                            frappe.db.commit()
                            
                            frappe.log_error(f"WEBHOOK: Payment Entry {payment_entry.name} erstellt für wiederkehrende Zahlung (Invoice {invoice_name})", "SUCCESS: stripe_webhook")
                        else:
                            frappe.log_error(f"WEBHOOK: Payment Entry existiert bereits für Invoice {invoice_name}: {existing_entries[0].name}", "INFO: stripe_webhook")
                    except Exception as e:
                        frappe.log_error(f"WEBHOOK: Fehler beim Erstellen des Payment Entry für Invoice {invoice_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: stripe_webhook")
                else:
                    frappe.log_error(f"WEBHOOK: Keine unbezahlte Invoice gefunden für Subscription {erpnext_subscription}", "WARNING: stripe_webhook")
        
        # Handle invoice.payment_failed Event (wiederkehrende Zahlungen - fehlgeschlagen)
        elif event['type'] == 'invoice.payment_failed':
            invoice_obj = event['data']['object']
            stripe_subscription_id = invoice_obj.get('subscription')
            
            if stripe_subscription_id:
                # Finde ERPNext Subscription über Stripe Subscription ID
                erpnext_subscription = None
                
                # Methode 1: Prüfe Custom Field
                if frappe.db.has_column("Subscription", "custom_stripe_subscription_id"):
                    subscriptions = frappe.get_all("Subscription",
                        filters={"custom_stripe_subscription_id": stripe_subscription_id},
                        fields=["name"],
                        limit=1
                    )
                    if subscriptions:
                        erpnext_subscription = subscriptions[0].name
                
                if erpnext_subscription:
                    # Finde die neueste Invoice für diese Subscription
                    invoices = frappe.get_all("Sales Invoice",
                        filters={
                            "subscription": erpnext_subscription,
                            "docstatus": 1
                        },
                        fields=["name"],
                        order_by="posting_date desc",
                        limit=1
                    )
                    
                    if invoices:
                        invoice_name = invoices[0].name
                        # Rechnung bleibt als "Unpaid" - das ist der Standard-Status
                        # Wir loggen nur, dass die Zahlung fehlgeschlagen ist
                        frappe.log_error(f"WEBHOOK: Zahlung fehlgeschlagen für Invoice {invoice_name} (Subscription {erpnext_subscription}) - Rechnung bleibt als Unpaid", "WARNING: stripe_webhook")
                else:
                    frappe.log_error(f"WEBHOOK: invoice.payment_failed für Stripe Subscription {stripe_subscription_id}, aber ERPNext Subscription nicht gefunden", "WARNING: stripe_webhook")
        
        return {"status": "success"}
        
    except Exception as e:
        frappe.log_error(f"Fehler im Webhook Handler: {str(e)}", "ERROR: stripe_webhook")
        return {"status": "error", "message": str(e)}

