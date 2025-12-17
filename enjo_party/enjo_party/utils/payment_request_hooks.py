import frappe
from frappe import _
import types

def prevent_email_before_submit(doc, method):
    """
    Verhindert E-Mail-Versendung beim Submit, wenn automatische E-Mails deaktiviert sind
    Wird bei Payment Request before_submit aufgerufen
    """
    try:
        # Prüfe ob es eine Subscription Payment Request ist
        if doc.is_a_subscription == 1:
            # Importiere die Prüffunktion
            from enjo_party.enjo_party.utils.subscription_hooks import is_automatic_email_enabled
            
            # Prüfe ob automatische E-Mails deaktiviert sind
            if not is_automatic_email_enabled():
                # Stelle sicher, dass mute_email auf 1 gesetzt ist BEVOR submit
                doc.flags.mute_email = 1
                doc.mute_email = 1
                
                frappe.log_error(f"mute_email=1 gesetzt BEVOR submit für Payment Request {doc.name} - Automatische E-Mails deaktiviert", "DEBUG: payment_request_prevent_email")
    except Exception as e:
        frappe.log_error(f"Fehler in prevent_email_before_submit für Payment Request {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: payment_request_prevent_email")

def prevent_email_on_submit(doc, method):
    """
    Löscht E-Mail-Queue nach dem Submit, wenn automatische E-Mails deaktiviert sind
    Wird bei Payment Request on_submit aufgerufen (Fallback, falls before_submit nicht greift)
    """
    try:
        # Prüfe ob es eine Subscription Payment Request ist
        if doc.is_a_subscription == 1:
            # Importiere die Prüffunktion
            from enjo_party.enjo_party.utils.subscription_hooks import is_automatic_email_enabled
            
            # Prüfe ob automatische E-Mails deaktiviert sind
            if not is_automatic_email_enabled():
                # Stelle sicher, dass mute_email auf 1 gesetzt ist
                doc.flags.mute_email = 1
                doc.mute_email = 1
                
                # Speichere mute_email in der DB
                doc.db_set('mute_email', 1, update_modified=False)
                
                # Prüfe ob bereits eine E-Mail-Queue erstellt wurde und lösche sie
                email_queues = frappe.get_all("Email Queue",
                    filters={
                        "reference_doctype": "Payment Request",
                        "reference_name": doc.name,
                        "status": ["!=", "Sent"]
                    },
                    fields=["name"]
                )
                
                for email_queue in email_queues:
                    try:
                        frappe.delete_doc("Email Queue", email_queue.name, force=1, ignore_permissions=True)
                        frappe.log_error(f"E-Mail-Queue {email_queue.name} gelöscht - Automatische E-Mails deaktiviert für Payment Request {doc.name}", "DEBUG: payment_request_prevent_email")
                    except Exception as e:
                        frappe.log_error(f"Fehler beim Löschen der E-Mail-Queue {email_queue.name}: {str(e)}", "ERROR: payment_request_prevent_email")
                
                frappe.log_error(f"E-Mail-Versendung verhindert für Payment Request {doc.name} - Automatische E-Mails deaktiviert", "DEBUG: payment_request_prevent_email")
    except Exception as e:
        frappe.log_error(f"Fehler in prevent_email_on_submit für Payment Request {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: payment_request_prevent_email")

def validate_payment_request_subscription(doc, method):
    """
    Deaktiviert Payment Schedule Amount Validierung für Subscription Payment Requests
    Wird bei Payment Request before_validate aufgerufen
    """
    try:
        # Prüfe ob es eine Subscription Payment Request ist
        if doc.is_a_subscription == 1:
            # Die Warnung kommt aus ERPNext's validate() Methode
            # Wir überschreiben die validate Methode für diese Instanz
            # Hole die ungebundene Methode aus der Klasse
            original_validate = doc.__class__.validate
            
            def patched_validate(self):
                # Rufe die Original-Validierung auf, aber fange Payment Schedule Warnungen ab
                try:
                    original_validate(self)
                except frappe.ValidationError as e:
                    # Wenn es eine Payment Schedule Validierung ist, ignorieren wir sie
                    error_msg = str(e)
                    if "Zahlungspläne" in error_msg or "payment schedule" in error_msg.lower() or "payment plan" in error_msg.lower() or "unterscheidet sich" in error_msg.lower():
                        msg = f"Payment Schedule Validierung übersprungen für Payment Request {self.name}"
                        frappe.log_error(msg[:140], "DEBUG: payment_request_validate")
                        return  # Überspringe die Validierung
                    else:
                        raise  # Andere Fehler weiterwerfen
                except Exception as e:
                    # Für andere Exceptions prüfen wir auch die Fehlermeldung
                    error_msg = str(e)
                    if "Zahlungspläne" in error_msg or "payment schedule" in error_msg.lower() or "payment plan" in error_msg.lower() or "unterscheidet sich" in error_msg.lower():
                        msg = f"Payment Schedule Validierung übersprungen für Payment Request {self.name}"
                        frappe.log_error(msg[:140], "DEBUG: payment_request_validate")
                        return  # Überspringe die Validierung
                    else:
                        raise  # Andere Fehler weiterwerfen
            
            # Setze die überschriebene validate Methode für diese Instanz
            doc.validate = types.MethodType(patched_validate, doc)
            frappe.log_error(f"Payment Schedule Amount Validierung deaktiviert für Payment Request {doc.name} (Subscription)", "DEBUG: payment_request_validate")
    except Exception as e:
        frappe.log_error(f"Fehler bei Payment Request Validierung für {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: payment_request_validate")


def create_payment_entry_on_paid(doc, method):
    """
    Erstellt automatisch einen Payment Entry, wenn die Payment Request auf "Paid" gesetzt wird
    """
    try:
        # Prüfe ob Status auf Paid gesetzt wurde (und war vorher nicht Paid)
        if doc.status == "Paid" and doc.get("_previous_status") != "Paid":
            # Prüfe ob bereits ein Payment Entry existiert
            existing_entries = frappe.get_all("Payment Entry",
                filters={
                    "reference_doctype": "Payment Request",
                    "reference_name": doc.name,
                    "docstatus": ["!=", 2]
                }
            )
            
            if not existing_entries:
                # Erstelle Payment Entry
                payment_entry = doc.create_payment_entry()
                payment_entry.reference_no = doc.name
                payment_entry.reference_date = frappe.utils.nowdate()
                payment_entry.insert(ignore_permissions=True)
                payment_entry.submit()
                
                frappe.log_error(f"Payment Entry {payment_entry.name} automatisch erstellt für Payment Request {doc.name}", "SUCCESS: payment_request_paid")
    
    except Exception as e:
        frappe.log_error(f"Fehler beim Erstellen des Payment Entry für Payment Request {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: payment_request_paid")

