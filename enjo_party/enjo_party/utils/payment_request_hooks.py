import frappe
from frappe import _
import types

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

