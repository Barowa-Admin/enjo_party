import frappe

INTERNAL_EMAILS = frozenset(
    {
        "esther.buchroth@bemotionme.com",
        "office@bemotionme.com",
    }
)
DATEV_EMAIL_DOMAIN = "uploadmail.datev.de"


def is_internal_or_system_recipient(email):
    if not email:
        return True
    normalized = email.strip().lower()
    if normalized in INTERNAL_EMAILS:
        return True
    if DATEV_EMAIL_DOMAIN in normalized:
        return True
    return False


def filter_external_recipients(emails):
    """Entfernt interne/DATEV-Adressen aus einer Empfängerliste."""
    if not emails:
        return []
    if isinstance(emails, str):
        emails = emails.replace(";", ",").split(",")
    result = []
    seen = set()
    for entry in emails:
        for part in str(entry).replace(";", ",").split(","):
            part = part.strip()
            if not part or is_internal_or_system_recipient(part):
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(part)
    return result


def has_customer_invoice_email_been_sent(invoice_name):
    """
    True wenn bereits eine Kundenmail zur Rechnung existiert.
    DATEV- und interne Empfänger werden ignoriert.
    """
    try:
        queue_rows = frappe.db.sql(
            """
            SELECT er.recipient
            FROM `tabEmail Queue` eq
            INNER JOIN `tabEmail Queue Recipient` er ON er.parent = eq.name
            WHERE eq.reference_doctype = 'Sales Invoice'
              AND eq.reference_name = %s
              AND eq.status NOT IN ('Error', 'Cancelled')
            """,
            (invoice_name,),
            as_dict=True,
        )
        for row in queue_rows:
            if not is_internal_or_system_recipient(row.recipient):
                return True

        communications = frappe.get_all(
            "Communication",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice_name,
                "communication_type": "Communication",
                "sent_or_received": "Sent",
            },
            fields=["recipients", "cc", "bcc"],
        )
        for comm in communications:
            for fieldname in ("recipients", "cc", "bcc"):
                if filter_external_recipients(comm.get(fieldname)):
                    return True

        payment_requests = frappe.get_all(
            "Payment Request",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice_name,
                "docstatus": ["!=", 2],
            },
            fields=["name"],
            limit=1,
        )
        if payment_requests:
            pr_comms = frappe.get_all(
                "Communication",
                filters={
                    "reference_doctype": "Payment Request",
                    "reference_name": payment_requests[0].name,
                    "communication_type": "Communication",
                    "sent_or_received": "Sent",
                },
                fields=["recipients", "cc", "bcc"],
            )
            for comm in pr_comms:
                for fieldname in ("recipients", "cc", "bcc"):
                    if filter_external_recipients(comm.get(fieldname)):
                        return True

        return False
    except Exception as e:
        frappe.log_error(
            title="ERROR: invoice_email_check",
            message=f"Fehler beim Prüfen der Kundenmail für {invoice_name}: {e}",
        )
        return False


def build_invoice_pdf_attachment(invoice_doc, print_format=None):
    """
    PDF-Anhang für Rechnungsmails; bei eu_einvoice-Fehler Fallback auf Standard.
  """
    invoice_name = invoice_doc.name
    primary_format = print_format or getattr(invoice_doc.meta, "default_print_format", None) or "Standard"
    formats_to_try = [primary_format]
    if primary_format != "Standard":
        formats_to_try.append("Standard")

    last_error = None
    for fmt in formats_to_try:
        try:
            return frappe.attach_print(
                "Sales Invoice",
                invoice_name,
                file_name=invoice_name,
                doc=invoice_doc,
                print_format=fmt,
            )
        except Exception as e:
            last_error = e
            frappe.logger().warning(
                f"invoice_pdf_attachment failed SI={invoice_name} format={fmt}: {e}"
            )

    frappe.log_error(
        title="WARNING: invoice_pdf_attachment_failed",
        message=f"PDF-Anhang für {invoice_name} fehlgeschlagen: {last_error}",
    )
    return None


def invoice_emails_disabled():
    try:
        return bool(
            frappe.db.get_single_value("System Settings", "custom_disable_invoice_emails")
        )
    except Exception:
        return False


def send_customer_invoice_email(invoice_doc):
    """
    Automatischer Kundenversand für Nicht-Abo-Rechnungen (TO Kunde, BCC VP, kein CC).
    """
    from enjo_party.enjo_party.utils.subscription_hooks import (
        _get_partnerin_email,
        _get_sales_partner_for_invoice,
        _partner_link_doctype,
        get_invoice_email_address,
    )

    if invoice_emails_disabled():
        frappe.logger().info(
            f"invoice_email_disabled: Invoice {invoice_doc.name} übersprungen"
        )
        return False

    if getattr(invoice_doc, "subscription", None):
        return False

    if has_customer_invoice_email_been_sent(invoice_doc.name):
        frappe.logger().info(
            f"invoice_email_already_sent: Invoice {invoice_doc.name} übersprungen"
        )
        return False

    email_to = get_invoice_email_address(invoice_doc)
    if not email_to:
        frappe.log_error(
            title="WARNING: invoice_email_no_address",
            message=f"Keine E-Mail-Adresse für Invoice {invoice_doc.name}",
        )
        return False

    from frappe.email.doctype.email_template.email_template import get_email_template

    email_template = get_email_template("Rechnung", doc=invoice_doc.as_dict())
    subject = (email_template or {}).get("subject") or f"Rechnung {invoice_doc.name}"
    message = (email_template or {}).get("message") or ""

    print_format = invoice_doc.meta.default_print_format or "Standard"
    attachment = build_invoice_pdf_attachment(invoice_doc, print_format=print_format)
    attachments = [attachment] if attachment else []

    link_doctype = _partner_link_doctype()
    sales_partner = _get_sales_partner_for_invoice(invoice_doc)
    partnerin_email = _get_partnerin_email(sales_partner, link_doctype) if sales_partner else None
    bcc_list = filter_external_recipients([partnerin_email] if partnerin_email else [])

    from frappe.utils.background_jobs import enqueue

    email_args = {
        "recipients": email_to,
        "sender": None,
        "reply_to": "enjo@bemotionme.com",
        "subject": subject,
        "message": message,
        "now": True,
        "attachments": attachments,
        "reference_doctype": "Sales Invoice",
        "reference_name": invoice_doc.name,
    }
    if bcc_list:
        email_args["bcc"] = bcc_list

    enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args)

    bcc_disp = ", ".join(bcc_list) if bcc_list else "KEINE"
    frappe.log_error(
        title="INFO: invoice_email_sent",
        message=(
            f"Rechnungsmail SI={invoice_doc.name} Empfänger={email_to} BCC={bcc_disp} "
            f"SP={sales_partner!r}"
        ),
    )
    return True
