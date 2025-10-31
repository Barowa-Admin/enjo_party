import frappe
from frappe import _

def create_payment_entry_on_paid(doc, method):
    """
    Erstellt automatisch einen Payment Entry, wenn die Payment Request auf "Paid" gesetzt wird
    """
    try:
        # Prüfe ob Status auf Paid gesetzt wurde
        if doc.status == "Paid":
            # Prüfe ob bereits ein Payment Entry existiert
            existing_entries = frappe.get_all("Payment Entry",
                filters={
                    "reference_no": doc.name,
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
        frappe.log_error(f"Fehler beim Erstellen des Payment Entry für Payment Request {doc.name}: {str(e)}", "ERROR: payment_request_paid")

