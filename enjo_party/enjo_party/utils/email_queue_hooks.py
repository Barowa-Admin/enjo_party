"""
Hooks für Email Queue - versendet E-Mails sofort wenn sie erstellt werden
"""

import frappe

def send_email_immediately(doc, method):
    """
    Versendet E-Mail sofort nach dem Erstellen, falls Scheduler nicht läuft
    Wird bei Email Queue after_insert aufgerufen
    """
    try:
        # Prüfe ob E-Mail bereits versendet wurde
        if doc.status == "Not Sent":
            # Versuche E-Mail sofort zu versenden
            from frappe.email.queue import flush
            try:
                # Flush die E-Mail-Queue - das versendet alle "Not Sent" E-Mails
                flush(from_test=True)
                frappe.log_error(f"E-Mail {doc.name} wurde sofort zur Versendung markiert", "DEBUG: email_immediate_send")
            except Exception as e:
                frappe.log_error(f"Fehler beim sofortigen Versenden der E-Mail {doc.name}: {str(e)}", "ERROR: email_immediate_send")
    except Exception as e:
        frappe.log_error(f"Fehler in send_email_immediately für {doc.name}: {str(e)}", "ERROR: email_immediate_send")
