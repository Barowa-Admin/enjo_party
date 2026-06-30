import frappe
from frappe import _
from frappe.utils import add_days, add_months, add_to_date, get_last_day, getdate, today
from enjo_party.enjo_party.utils.stripe_checkout import create_stripe_checkout_session, get_payment_link_url
from enjo_party.enjo_party.utils.stripe_subscription import cancel_stripe_subscription_at_period_end
from enjo_party.enjo_party.utils.sales_invoice_hooks import ensure_inclusive_taxes

# Stripe EUR Gateway: erste Abo-Mail (message-Feld) + Folge-Mail (Custom Fields) am selben Datensatz
STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT = "Stripe-Stripe - EUR"


def _log_err(title, message=None):
    """Frappe log_error(title, message) — Titel-Feld max. 140 Zeichen."""
    t = (title or "Error")[:140]
    frappe.log_error(title=t, message=frappe.as_unicode(message or ""))


def has_non_return_subscription_invoice_for_date(subscription_name, posting_date):
    """Idempotenz-Hilfe: nicht-stornierte Abo-Rechnung am Buchungsdatum."""
    pd = frappe.utils.getdate(posting_date)
    return bool(
        frappe.get_all(
            "Sales Invoice",
            filters={
                "subscription": subscription_name,
                "posting_date": pd,
                "docstatus": ["in", [0, 1]],
                "is_return": 0,
            },
            fields=["name"],
            limit_page_length=1,
        )
    )


def _get_existing_subscription_invoice_for_billing(
    subscription_name, posting_date, period_start=None, period_end=None
):
    """
    Liefert (invoice_name, reason) wenn für diese Abrechnung bereits eine Rechnung existiert.
    """
    pd = frappe.utils.getdate(posting_date)
    existing = frappe.get_all(
        "Sales Invoice",
        filters={
            "subscription": subscription_name,
            "posting_date": pd,
            "docstatus": ["in", [0, 1]],
            "is_return": 0,
        },
        fields=["name"],
        limit_page_length=1,
    )
    if existing:
        return existing[0].name, "posting_date"

    if period_start and period_end:
        ps = frappe.utils.getdate(period_start)
        pe = frappe.utils.getdate(period_end)
        in_period = frappe.get_all(
            "Sales Invoice",
            filters={
                "subscription": subscription_name,
                "posting_date": ["between", [ps, pe]],
                "docstatus": ["in", [0, 1]],
                "is_return": 0,
            },
            fields=["name"],
            limit_page_length=1,
        )
        if in_period:
            return in_period[0].name, "billing_period"

    return None, None


def process_subscription_billing_safe(subscription_name, posting_date, source="scheduler"):
    """
    Ruft subscription.process() nur auf, wenn noch keine Rechnung für diese Periode existiert.
    Serialisiert parallele Läufe per FOR UPDATE auf dem Abo-Datensatz.

    Kein frappe.db.begin()/rollback() auf der äußeren Transaktion — sonst wird z. B. beim
    after_insert-Hook das gerade angelegte Abo wieder verworfen (UI zeigt es, DB 404).
    """
    pd = frappe.utils.getdate(posting_date)
    rows = frappe.db.sql(
        """
        SELECT name, current_invoice_start, current_invoice_end
        FROM `tabSubscription`
        WHERE name = %s
        FOR UPDATE
        """,
        (subscription_name,),
        as_dict=True,
    )
    if not rows:
        _log_err(
            "INFO: subscription_billing_skipped",
            f"{subscription_name} posting_date={pd} reason=not_found source={source}",
        )
        return False

    sub_row = rows[0]
    existing_name, skip_reason = _get_existing_subscription_invoice_for_billing(
        subscription_name,
        pd,
        sub_row.get("current_invoice_start"),
        sub_row.get("current_invoice_end"),
    )
    if existing_name:
        _log_err(
            "INFO: subscription_billing_skipped",
            f"{subscription_name} posting_date={pd} reason={skip_reason} "
            f"invoice={existing_name} source={source}",
        )
        _log_err(
            "WARNING: subscription_billing_duplicate_prevented",
            f"{subscription_name} posting_date={pd} existing={existing_name} source={source}",
        )
        return False

    savepoint = f"sub_bill_{frappe.generate_hash(length=10)}"
    try:
        frappe.db.savepoint(savepoint)
        subscription = frappe.get_doc("Subscription", subscription_name)
        subscription.process(posting_date=str(pd))
        frappe.db.release_savepoint(savepoint)
        frappe.db.commit()
        _log_err(
            "INFO: subscription_billing_processed",
            f"{subscription_name} posting_date={pd} source={source}",
        )
        return True
    except Exception as e:
        frappe.db.rollback(save_point=savepoint)
        _log_err(
            "ERROR: subscription_billing",
            f"{subscription_name} posting_date={pd} source={source}: {str(e)}\n{frappe.get_traceback()}",
        )
        raise


def has_stripe_subscription(erpnext_subscription_name):
    """
    Prüft ob bereits eine Stripe Subscription für diese ERPNext Subscription existiert
    Gibt True zurück wenn Stripe Subscription ID gefunden wurde
    """
    try:
        # Methode 1: Prüfe Custom Field
        if frappe.db.has_column("Subscription", "custom_stripe_subscription_id"):
            stripe_subscription_id = frappe.db.get_value("Subscription", erpnext_subscription_name, "custom_stripe_subscription_id")
            if stripe_subscription_id:
                _log_err("DEBUG: stripe_subscription_check", f"Stripe Subscription ID gefunden in Custom Field: {stripe_subscription_id} für {erpnext_subscription_name}")
                return True
        
        # Methode 2: Prüfe über Payment Entries (Fallback)
        # Suche nach Payment Entries die zu dieser Subscription gehören
        invoices = frappe.get_all("Sales Invoice",
            filters={"subscription": erpnext_subscription_name, "docstatus": 1},
            fields=["name"],
            limit=5
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
                    # Prüfe ob es eine Stripe Checkout Session ID ist (beginnt mit cs_)
                    session_id = payment_entries[0].reference_no
                    if session_id.startswith("cs_"):
                        try:
                            import stripe
                            stripe_settings = frappe.get_doc("Stripe Settings", "Stripe")
                            api_key = frappe.utils.password.get_decrypted_password("Stripe Settings", "Stripe", "secret_key")
                            if api_key:
                                stripe.api_key = api_key
                                session = stripe.checkout.Session.retrieve(session_id)
                                if session.get('subscription'):
                                    _log_err("DEBUG: stripe_subscription_check", f"Stripe Subscription ID gefunden über Payment Entry: {session.get('subscription')} für {erpnext_subscription_name}")
                                    return True
                        except:
                            pass
        
        return False
    except Exception as e:
        _log_err("ERROR: stripe_subscription_check", f"Fehler beim Prüfen der Stripe Subscription für {erpnext_subscription_name}: {str(e)}")
        return False

def was_email_already_sent_for_invoice(invoice_name):
    """
    Prüft ob bereits eine Kundenmail für diese Invoice gesendet wurde.
    DATEV- und interne Empfänger werden ignoriert.
    """
    from enjo_party.enjo_party.utils.invoice_email import has_customer_invoice_email_been_sent

    return has_customer_invoice_email_been_sent(invoice_name)

def get_invoice_email_address(invoice):
    """
    Ermittelt die beste E-Mail-Adresse für die Rechnungszustellung.
    """
    if getattr(invoice, "contact_email", None):
        return invoice.contact_email

    customer_email = frappe.db.get_value("Customer", invoice.customer, "email_id")
    if customer_email:
        return customer_email

    return None


def _partner_link_doctype():
    """DocType des Subscription-Felds custom_partnerin (UI: Vertriebspartner)."""
    try:
        field = frappe.get_meta("Subscription").get_field("custom_partnerin")
        if field and field.options:
            return field.options
    except Exception:
        pass
    return "Sales Partner"


def sync_subscription_partner_to_invoice(doc, method):
    """
    Übernimmt Partnerin vom Abo auf die Rechnung (nur Entwurf), ohne manuelle Werte zu überschreiben.
    """
    if doc.doctype != "Sales Invoice" or doc.docstatus != 0 or not doc.subscription:
        return

    sub_meta = frappe.get_meta("Subscription")
    sub_fields = [
        f for f in ("custom_partnerin", "sales_partner", "custom_sales_partner")
        if sub_meta.has_field(f)
    ]
    if not sub_fields:
        return

    sub_values = frappe.db.get_value(
        "Subscription",
        doc.subscription,
        sub_fields,
        as_dict=True,
    )
    if not sub_values:
        return

    partnerin = sub_values.get("custom_partnerin")
    sales_partner = (
        sub_values.get("sales_partner")
        or sub_values.get("custom_sales_partner")
        or partnerin
    )
    si_meta = frappe.get_meta("Sales Invoice")

    if si_meta.has_field("custom_partnerin") and not doc.get("custom_partnerin") and partnerin:
        doc.custom_partnerin = partnerin
    if si_meta.has_field("sales_partner") and not doc.get("sales_partner") and sales_partner:
        doc.sales_partner = sales_partner


def _email_from_contact_doc(contact):
    for row in (getattr(contact, "email_ids", None) or []):
        if getattr(row, "is_primary", 0) and getattr(row, "email_id", None):
            return row.email_id
    contact_email = getattr(contact, "email_id", None)
    if contact_email:
        return contact_email
    for row in (getattr(contact, "email_ids", None) or []):
        if getattr(row, "email_id", None):
            return row.email_id
    return None


def _get_partnerin_email(sales_partner_name, link_doctype=None):
    """E-Mail der Vertriebspartnerin (Kontakt primär, Partner-Feld, dann User-Fallback)."""
    if not sales_partner_name:
        return None

    link_doctype = link_doctype or _partner_link_doctype()

    try:
        contact_links = frappe.get_all(
            "Dynamic Link",
            filters={
                "parenttype": "Contact",
                "link_doctype": link_doctype,
                "link_name": sales_partner_name,
            },
            fields=["parent"],
            order_by="creation asc",
        )

        for link in contact_links:
            contact_name = link.get("parent")
            if not contact_name:
                continue
            contact = frappe.get_doc("Contact", contact_name)
            email = _email_from_contact_doc(contact)
            if email:
                return email
    except Exception:
        pass

    try:
        partner_meta = frappe.get_meta(link_doctype)
        for fieldname in ("email_id", "custom_email", "primary_email"):
            if partner_meta.has_field(fieldname):
                val = frappe.db.get_value(link_doctype, sales_partner_name, fieldname)
                if val:
                    return val
        if partner_meta.has_field("user"):
            user = frappe.db.get_value(link_doctype, sales_partner_name, "user")
            if user:
                return frappe.db.get_value("User", user, "email")
    except Exception:
        pass
    return None


def _bcc_skip_reason(sales_partner_name, partnerin_email, link_doctype):
    if not sales_partner_name:
        return "kein_partner"
    if partnerin_email:
        return ""
    link_doctype = link_doctype or _partner_link_doctype()
    has_contact = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Contact",
            "link_doctype": link_doctype,
            "link_name": sales_partner_name,
        },
        limit_page_length=1,
    )
    if not has_contact:
        return "kein_kontakt"
    partner_meta = frappe.get_meta(link_doctype)
    if partner_meta.has_field("user"):
        user = frappe.db.get_value(link_doctype, sales_partner_name, "user")
        if user and not frappe.db.get_value("User", user, "email"):
            return "user_fallback_ohne_email"
    return "keine_email_am_kontakt"


def _get_sales_partner_for_invoice(invoice):
    """
    Vertriebspartner robust ermitteln:
    1) Rechnung (custom_partnerin, sales_partner, custom_sales_partner)
    2) Subscription (custom_partnerin, sales_partner, custom_sales_partner)
    3) Kunde.default_sales_partner
    """
    def _read(obj, fieldname):
        if not obj:
            return None
        if isinstance(obj, dict):
            return obj.get(fieldname)
        return getattr(obj, fieldname, None) or obj.get(fieldname)

    # 1) Direkt von der Rechnung
    for fieldname in ("custom_partnerin", "sales_partner", "custom_sales_partner"):
        sp = _read(invoice, fieldname)
        if sp:
            return sp

    # 2) Vom verknüpften Abo
    subscription_name = _read(invoice, "subscription")
    if subscription_name:
        for fieldname in ("custom_partnerin", "sales_partner", "custom_sales_partner"):
            try:
                sp = frappe.db.get_value("Subscription", subscription_name, fieldname)
            except Exception:
                sp = None
            if sp:
                return sp

    # 3) Fallback über Kunde
    customer = _read(invoice, "customer")
    if customer:
        return frappe.db.get_value("Customer", customer, "default_sales_partner")
    return None


def _log_abo_mail_partner_bcc_audit(
    kind,
    invoice_name,
    customer,
    email_to,
    sales_partner_resolved,
    partnerin_email,
    pr_name=None,
    subscription_name=None,
):
    """
    Ein Fehlerprotokoll-Eintrag pro Abo-Mail-Versand.
    Im Desk nach Titel „ABO-Mail Partner-BCC“ filtern.
    """
    link_doctype = _partner_link_doctype()
    sp_db = frappe.db.get_value("Sales Invoice", invoice_name, "sales_partner")
    si_partnerin = None
    if frappe.db.has_column("Sales Invoice", "custom_partnerin"):
        si_partnerin = frappe.db.get_value("Sales Invoice", invoice_name, "custom_partnerin")
    sub_partnerin = None
    if subscription_name:
        sub_partnerin = frappe.db.get_value("Subscription", subscription_name, "custom_partnerin")
    dsp = frappe.db.get_value("Customer", customer, "default_sales_partner") if customer else None
    bcc_disp = partnerin_email if partnerin_email else "KEINE"
    skip = _bcc_skip_reason(sales_partner_resolved, partnerin_email, link_doctype)
    reason = f" | Kein BCC: {skip}" if skip else ""
    msg = (
        f"{kind} SI={invoice_name} PR={pr_name or '-'} Empfänger={email_to} BCC={bcc_disp} | "
        f"SP_gewählt={sales_partner_resolved!r} link_doctype={link_doctype!r} | "
        f"SUB.custom_partnerin={sub_partnerin!r} SI.custom_partnerin={si_partnerin!r} | "
        f"SI.sales_partner={sp_db!r} Kunde.default_sales_partner={dsp!r}{reason}"
    )
    _log_err("ABO-Mail Partner-BCC", msg)


def _subscription_emails_disabled():
    try:
        return bool(
            frappe.db.get_single_value("System Settings", "custom_disable_subscription_emails")
        )
    except Exception:
        return False


def _send_subscription_customer_email(
    invoice,
    subject,
    message,
    attachments,
    audit_kind,
    payment_request_name=None,
):
    """
    Zentraler Abo-Kundenversand inkl. BCC an die Vertriebspartnerin.
    """
    if _subscription_emails_disabled():
        _log_err(
            "INFO: subscription_email_disabled",
            f"Abo-E-Mail Versand deaktiviert (System Settings) - Invoice {invoice.name} wird übersprungen",
        )
        return False

    email_to = get_invoice_email_address(invoice)
    if not email_to:
        return False

    from enjo_party.enjo_party.utils.invoice_email import (
        create_invoice_outbound_communication,
        filter_external_recipients,
    )

    link_doctype = _partner_link_doctype()
    sales_partner = _get_sales_partner_for_invoice(invoice)
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
        "reference_name": invoice.name,
    }
    if bcc_list:
        email_args["bcc"] = bcc_list

    email_args["communication"] = create_invoice_outbound_communication(
        invoice.name,
        subject,
        message,
        email_to,
        bcc=bcc_list or None,
    )

    enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args)

    subscription_name = getattr(invoice, "subscription", None) or invoice.get("subscription")
    _log_abo_mail_partner_bcc_audit(
        audit_kind,
        invoice.name,
        getattr(invoice, "customer", None) or invoice.get("customer"),
        email_to,
        sales_partner,
        bcc_list[0] if bcc_list else None,
        pr_name=payment_request_name,
        subscription_name=subscription_name,
    )
    return True


def _get_subscription_informational_email_subject_and_message(invoice_doc):
    """
    Informationsmail (Stripe-Abo, ohne Zahlungslink).
    Betreff: fest wie erste Abo-Mail (Payment Request). Text: Payment Gateway Account → „Abo-Folge-Mail“.
    """
    subject = f"Rechnung {invoice_doc.name}"
    default_message = (
        "Guten Tag,\n\n"
        "im Anhang finden Sie die Rechnung zu Ihrem BE'motion-Abonnement.\n\n"
        "Der vereinbarte Betrag wird wie gewohnt automatisch per Abbuchung eingezogen; "
        "eine separate Überweisung ist nicht nötig.\n\n"
        "Bei Fragen helfen wir Ihnen gerne weiter.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr BE'motion-Team"
    )
    ctx = {"doc": invoice_doc, "invoice": invoice_doc}
    message = default_message
    try:
        from frappe.utils.jinja import render_template

        msg_tpl = ""
        if frappe.db.exists("Payment Gateway Account", STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT):
            ga = frappe.get_doc("Payment Gateway Account", STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT)
            msg_tpl = (getattr(ga, "custom_abo_info_email_message", None) or "").strip()

        if msg_tpl:
            try:
                message = (render_template(msg_tpl, ctx) or "").strip() or default_message
            except Exception:
                message = default_message
    except Exception:
        message = default_message

    return subject, message


def send_subscription_invoice_informational_email(invoice_doc):
    """
    Sendet bei Folgeabbuchungen (Stripe-Abo existiert bereits) eine reine Informations-E-Mail
    mit der Rechnung als PDF – ohne Zahlungslink. Nur für die Buchhaltung/Unterlagen des Kunden.
    """
    if was_email_already_sent_for_invoice(invoice_doc.name):
        frappe.logger().info(
            f"subscription_informational_email: bereits versendet für {invoice_doc.name}"
        )
        return
    email_to = get_invoice_email_address(invoice_doc)
    if not email_to:
        _log_err(
            "WARNING: subscription_informational_email",
            f"Keine E-Mail-Adresse für Rechnung {invoice_doc.name} – Informations-Mail übersprungen",
        )
        return
    subject, message = _get_subscription_informational_email_subject_and_message(invoice_doc)
    print_format = getattr(invoice_doc.meta, "default_print_format", None) or "Standard"
    from enjo_party.enjo_party.utils.invoice_email import build_invoice_pdf_attachment

    attachment = build_invoice_pdf_attachment(invoice_doc, print_format=print_format)
    attachments = [attachment] if attachment else []
    if not _send_subscription_customer_email(
        invoice_doc,
        subject,
        message,
        attachments,
        audit_kind="Informationsmail-Abo",
    ):
        return
    _log_err(
        "INFO: subscription_informational_email",
        f"Informations-E-Mail (ohne Zahlungslink) versendet für Rechnung {invoice_doc.name} an {email_to}",
    )


def send_subscription_payment_request_email(payment_request, invoice, include_payment_link):
    """
    Sendet die E-Mail für Subscription-Payment-Requests kontrolliert aus.
    """
    if was_email_already_sent_for_invoice(invoice.name):
        frappe.logger().info(
            f"subscription_email_send: bereits versendet für {invoice.name}"
        )
        return

    email_to = payment_request.email_to or get_invoice_email_address(invoice)
    if not email_to:
        _log_err(
            "WARNING: subscription_email_send",
            f"Keine E-Mail-Adresse für Invoice {invoice.name} gefunden - Versand übersprungen",
        )
        return

    payment_request.db_set("email_to", email_to, update_modified=False)

    if include_payment_link:
        from frappe.utils.jinja import render_template
        gateway_account = frappe.get_doc(
            "Payment Gateway Account", STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT
        )
        message_template = gateway_account.message or ""
        rendered_message = render_template(
            message_template,
            {
                "doc": invoice,
                "payment_url": payment_request.payment_url,
            },
        )
        payment_request.db_set("message", rendered_message, update_modified=False)
    else:
        message = (
            f"Hallo,\n\nanbei findest du deine Rechnung {invoice.name}."
            "\n\nViele Grüße\n"
        )
        payment_request.db_set("message", message, update_modified=False)

    payment_request.db_set("subject", f"Rechnung {invoice.name}", update_modified=False)

    from enjo_party.enjo_party.utils.invoice_email import build_invoice_pdf_attachment

    attachment = build_invoice_pdf_attachment(
        invoice,
        print_format=payment_request.print_format,
    )
    attachments = [attachment] if attachment else []
    if not _send_subscription_customer_email(
        invoice,
        payment_request.subject,
        payment_request.get_message(),
        attachments,
        audit_kind="PaymentRequest-Abo",
        payment_request_name=payment_request.name,
    ):
        return

def is_first_invoice_for_subscription(invoice_name, subscription_name):
    """
    Prüft ob dies die ERSTE Invoice dieser Subscription ist
    Gibt True zurück wenn es die erste Invoice ist (dann sollte E-Mail gesendet werden)
    """
    try:
        # Finde ALLE Invoices dieser Subscription (sortiert nach Erstellung)
        invoices = frappe.get_all("Sales Invoice",
            filters={
                "subscription": subscription_name,
                "docstatus": 1
            },
            fields=["name", "creation"],
            order_by="creation asc"  # Älteste zuerst
        )
        
        if not invoices:
            # Keine Invoices gefunden - sollte nicht passieren, aber sicherheitshalber
            return True
        
        # Prüfe ob die aktuelle Invoice die erste (älteste) ist
        first_invoice = invoices[0]
        if first_invoice.name == invoice_name:
            _log_err("DEBUG: is_first_invoice", f"Erste Invoice für Subscription {subscription_name}: {invoice_name}")
            return True
        
        # Es gibt bereits eine ältere Invoice
        _log_err("DEBUG: is_first_invoice", f"Nicht erste Invoice für Subscription {subscription_name}: {invoice_name} (erste: {first_invoice.name})")
        return False
    except Exception as e:
        _log_err("ERROR: is_first_invoice", f"Fehler beim Prüfen ob erste Invoice für Subscription {subscription_name}: {str(e)}")
        # Bei Fehler: Annahme dass es die erste ist (sicherer - E-Mail wird gesendet)
        return True

def handle_subscription_cancel(doc, method):
    """
    Wird aufgerufen, wenn ein Abonnement storniert wird (on_cancel)
    Kündigt auch die Stripe Subscription
    """
    try:
        _log_err("DEBUG: subscription_hook", f"HOOK AUFGERUFEN: handle_subscription_cancel für {doc.name}, Status: {doc.status}, Method: {method}")
        
        # Prüfe ob das Abo aktiv war (nicht bereits storniert)
        if doc.status == "Cancelled":
            _log_err("DEBUG: subscription_hook", f"ABO STORNIERT {doc.name}: starte Stripe Kündigung")
            # Kündige Stripe Subscription zum Ende der Periode
            try:
                result = cancel_stripe_subscription_at_period_end(doc.name)
                if result:
                    _log_err("SUCCESS: subscription_hook", f"ABO STORNIERT {doc.name}: ERFOLGREICH - Stripe Subscription wird gekündigt")
                else:
                    _log_err("WARNING: subscription_hook", f"ABO STORNIERT {doc.name}: Fehler - Stripe Subscription ID nicht gefunden")
            except Exception as e:
                _log_err("ERROR: subscription_hook", f"ABO STORNIERT {doc.name}: Exception {str(e)}\n{frappe.get_traceback()}")
        else:
            _log_err("DEBUG: subscription_hook", f"ABO STORNIERT {doc.name}: Status ist nicht 'Cancelled' ({doc.status}), überspringe Stripe Kündigung")
    except Exception as e:
        _log_err("ERROR: subscription_hook", f"Fehler in handle_subscription_cancel für {doc.name}: {str(e)}\n{frappe.get_traceback()}")

def force_subscription_update(doc, method):
    """
    Wird nach dem Speichern eines Abonnements ausgeführt und erzwingt sofort ein Update
    """
    try:
        # Hole vorherigen Wert AUS DER DB (bevor wir prüfen)
        previous_cancel_at_period_end = frappe.db.get_value("Subscription", doc.name, "cancel_at_period_end")
        
        _log_err("DEBUG: subscription_hook", f"HOOK {doc.name}: cancel={doc.cancel_at_period_end}, vorher={previous_cancel_at_period_end}, method={method}")
        
        # Prüfe ob cancel_at_period_end auf True gesetzt wurde
        # Wenn cancel_at_period_end jetzt True ist UND vorher False/None/0 war
        if doc.cancel_at_period_end == 1 and not previous_cancel_at_period_end:
            _log_err("DEBUG: subscription_hook", f"KÜNDIGUNG {doc.name}: starte Stripe Kündigung (cancel_at_period_end wurde gesetzt)")
            # Kündige Stripe Subscription zum Ende der Periode
            try:
                result = cancel_stripe_subscription_at_period_end(doc.name)
                if result:
                    _log_err("SUCCESS: subscription_hook", f"KÜNDIGUNG {doc.name}: ERFOLGREICH - Stripe Subscription wird zum Periodenende gekündigt")
                else:
                    _log_err("ERROR: subscription_hook", f"KÜNDIGUNG {doc.name}: Fehler - Stripe Subscription ID nicht gefunden")
            except Exception as e:
                _log_err("ERROR: subscription_hook", f"KÜNDIGUNG {doc.name}: Exception {str(e)}\n{frappe.get_traceback()}")
        elif doc.cancel_at_period_end == 1:
            _log_err("DEBUG: subscription_hook", f"HOOK {doc.name}: cancel_at_period_end bereits True (wurde schon behandelt)")
        
        # Prüfe ob das Abo aktiv ist (Status "Active") und das Startdatum erreicht ist
        subscription = frappe.get_doc("Subscription", doc.name)
        start_date_reached = subscription.start_date and frappe.utils.getdate(subscription.start_date) <= frappe.utils.getdate()
        
        if start_date_reached:
            _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist erreicht, prüfe Fälligkeit")

            processing_date = None
            if subscription.generate_invoice_at == "Beginning of the current subscription period":
                processing_date = subscription.current_invoice_start
            elif subscription.generate_invoice_at == "End of the current subscription period":
                processing_date = subscription.current_invoice_end
            elif subscription.generate_invoice_at == "Days before the current subscription period":
                processing_date = add_days(subscription.current_invoice_start, -subscription.number_of_days)

            # WICHTIG: Fälligkeitsprüfung - process() nur ausführen wenn der Termin heute oder in der Vergangenheit liegt
            today_date = frappe.utils.getdate()
            processing_date_obj = frappe.utils.getdate(processing_date) if processing_date else None
            
            if not processing_date_obj or processing_date_obj > today_date:
                _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Fälligkeit noch nicht erreicht für {doc.name} (processing_date={processing_date}, heute={today_date}) - überspringe process()")
                return
            
            _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Fälligkeit erreicht für {doc.name} (processing_date={processing_date}), führe process() aus")
            process_subscription_billing_safe(
                doc.name, processing_date, source="force_subscription_update"
            )

            _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: process() abgeschlossen für {doc.name}")
            
            # Erstelle Payment Request für die generierte Rechnung
            invoices = frappe.get_all("Sales Invoice", 
                filters={
                    "subscription": doc.name,
                    "docstatus": 1
                },
                order_by="creation desc",
                limit=1
            )
            
            _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Gefundene Invoices: {len(invoices)}")
            
            if invoices:
                invoice_name = invoices[0].name
                
                # WICHTIG: Prüfe ob bereits eine Stripe Subscription existiert
                # Wenn ja, wird Stripe automatisch abbuchen - keine Payment Request nötig
                if has_stripe_subscription(doc.name):
                    frappe.logger().info(
                        f"subscription_hook: Stripe-Abo für {doc.name}, Informationsmail für {invoice_name}"
                    )
                    send_subscription_invoice_informational_email(
                        frappe.get_doc("Sales Invoice", invoice_name)
                    )
                    return
                
                # WICHTIG: Commit vor Prüfung, damit create_payment_request_for_subscription_invoice die Payment Request findet
                frappe.db.commit()
                
                # Prüfe ob bereits eine Payment Request existiert (auch Draft-Status)
                existing_requests = frappe.get_all("Payment Request",
                    filters={
                        "reference_doctype": "Sales Invoice",
                        "reference_name": invoice_name,
                        "docstatus": ["!=", 2]  # Nicht storniert
                    }
                )
                
                if existing_requests:
                    if not was_email_already_sent_for_invoice(invoice_name):
                        payment_request = frappe.get_doc(
                            "Payment Request", existing_requests[0].name
                        )
                        invoice = frappe.get_doc("Sales Invoice", invoice_name)
                        is_first_invoice = is_first_invoice_for_subscription(
                            invoice_name, doc.name
                        )
                        send_subscription_payment_request_email(
                            payment_request,
                            invoice,
                            include_payment_link=is_first_invoice,
                        )
                    return
                
                # WICHTIG: Invoice neu aus DB laden, um sicherzustellen, dass alle Werte korrekt sind
                frappe.db.commit()  # Sicherstellen, dass Invoice vollständig gespeichert ist
                invoice = frappe.get_doc("Sales Invoice", invoice_name)
                invoice.reload()  # Neu laden
                
                # WICHTIG: Stelle sicher, dass Steuern auf "inklusive" gesetzt sind
                # Da subscription.process() die Rechnung direkt submitted, müssen wir sie temporär auf Draft setzen,
                # die Steuern anwenden, und dann wieder submiten
                try:
                    # Prüfe ob Steuern vorhanden sind und ob sie auf "inklusive" gesetzt sind
                    needs_tax_update = False
                    if invoice.taxes:
                        for tax in invoice.taxes:
                            if tax.included_in_print_rate != 1:
                                needs_tax_update = True
                                break
                    elif not invoice.taxes_and_charges:
                        # Keine Steuern vorhanden - muss Steuer-Template setzen
                        needs_tax_update = True
                    
                    if needs_tax_update:
                        _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Steuern müssen aktualisiert werden für Invoice {invoice_name}")
                        # Setze Rechnung auf Draft (nur wenn sie submitted ist)
                        if invoice.docstatus == 1:
                            invoice.docstatus = 0
                            invoice.flags.ignore_validate_update_after_submit = True
                            invoice.flags.ignore_validate = True
                            invoice.save(ignore_permissions=True)
                            frappe.db.commit()
                        
                        # Wende Steuerlogik an
                        ensure_inclusive_taxes(invoice)
                        
                        # Speichere Änderungen
                        invoice.save(ignore_permissions=True)
                        frappe.db.commit()
                        
                        # Submit wieder (nur wenn sie vorher submitted war)
                        if invoice.docstatus == 0:
                            invoice.submit()
                            frappe.db.commit()
                            _log_err("SUCCESS: subscription_hook", f"SUBSCRIPTION HOOK: Invoice {invoice_name} mit Steuern aktualisiert und wieder submitted")
                except Exception as e:
                    _log_err("ERROR: subscription_hook", f"SUBSCRIPTION HOOK: Fehler beim Aktualisieren der Steuern für Invoice {invoice_name}: {str(e)}\n{frappe.get_traceback()}")
                    # Weiter mit der normalen Verarbeitung, auch wenn Steuer-Update fehlgeschlagen ist
                
                # Betrag direkt aus DB lesen für exakte Übereinstimmung
                invoice_grand_total = frappe.db.get_value("Sales Invoice", invoice_name, "grand_total")
                
                msg = f"Erstelle Payment Request für Invoice {invoice_name}, total={invoice_grand_total}"
                _log_err("DEBUG: subscription_hook", msg[:140])
                
                # Payment Request erstellen (ohne message zuerst)
                payment_request = frappe.get_doc({
                    "doctype": "Payment Request",
                    "payment_request_type": "Inward",
                    "transaction_date": invoice.posting_date,
                    "party_type": "Customer",
                    "party": invoice.customer,
                    "reference_doctype": "Sales Invoice",
                    "reference_name": invoice.name,
                    "payment_gateway_account": STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT,
                    "grand_total": invoice_grand_total,
                    "currency": invoice.currency,
                    "email_to": get_invoice_email_address(invoice),
                    "subject": f"Rechnung {invoice.name}",
                    "is_a_subscription": 1,
                    "payment_channel": "Email",
                    "mute_email": 1
                })
                
                # Füge Subscription Plans hinzu (notwendig für Validierung)
                subscription = frappe.get_doc("Subscription", doc.name)
                
                # Prüfe welches payment_gateway_account in den Subscription Plans vorhanden ist
                gateway_account = payment_request.payment_gateway_account
                if subscription.plans:
                    for plan_detail in subscription.plans:
                        # Prüfe ob dieser Plan ein payment_gateway_account hat
                        plan_gateway = getattr(plan_detail, 'payment_gateway_account', None)
                        if plan_gateway:
                            _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hat payment_gateway_account: {plan_gateway}")
                            gateway_account = plan_gateway
                            # Setze Payment Request auf dasselbe Account
                            payment_request.payment_gateway_account = gateway_account
                            break  # Verwende das erste gefundene Account
                
                # Stelle sicher, dass Payment Request das gateway_account hat
                payment_request.payment_gateway_account = gateway_account
                _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Verwende payment_gateway_account: {gateway_account}")
                
                for plan_detail in subscription.plans:
                    # Prüfe und aktualisiere das payment_gateway im Subscription Plan DocType
                    plan_doc = frappe.get_doc("Subscription Plan", plan_detail.plan)
                    if plan_doc.payment_gateway != gateway_account:
                        msg = f"Plan {plan_detail.plan}: payment_gateway={plan_doc.payment_gateway}, setze auf {gateway_account}"
                        _log_err("DEBUG: subscription_hook", msg[:140])
                        plan_doc.payment_gateway = gateway_account
                        plan_doc.save(ignore_permissions=True)
                    
                    # IMMER dasselbe payment_gateway_account für alle Plans verwenden
                    plan_row = payment_request.append("subscription_plans", {
                        "plan": plan_detail.plan,
                        "qty": plan_detail.qty,
                        "payment_gateway_account": gateway_account
                    })
                    _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hinzugefügt mit payment_gateway_account: {plan_row.payment_gateway_account}")
                
                # Stelle sicher, dass payment_gateway_account auch NACH dem Hinzufügen der Plans noch gesetzt ist
                payment_request.payment_gateway_account = gateway_account
                _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Payment Request payment_gateway_account vor insert: {payment_request.payment_gateway_account}")
                
                payment_request.insert(ignore_permissions=True)
                # WICHTIG: Sofort committen, damit create_payment_request_for_subscription_invoice die Payment Request findet
                frappe.db.commit()

                # Stripe-Checkout erzeugen und URL setzen
                stripe_url = create_stripe_checkout_session(payment_request)
                
                # Prüfe ob payment_url gesetzt wurde (Retry-Logik)
                if not stripe_url:
                    _log_err("WARNING: subscription_hook", f"SUBSCRIPTION HOOK: Stripe URL ist leer, versuche erneut für Payment Request {payment_request.name}")
                    # Reload Payment Request
                    payment_request.reload()
                    stripe_url = create_stripe_checkout_session(payment_request)
                
                if stripe_url:
                    # Dauerhafte Zahlungs-URL verwenden (bei Klick wird neue Stripe-Session erzeugt, Link läuft nicht nach 24h ab)
                    payment_link_url = get_payment_link_url(payment_request.name)
                    payment_request.payment_url = payment_link_url
                    # WICHTIG: Lokale Checkout-Seite dauerhaft deaktivieren.
                    # Durch das Leeren von payment_gateway verhindert ERPNext das Generieren von /stripe_checkout-Links.
                    # payment_gateway_account NICHT löschen, da Subscription Plans es benötigen
                    payment_request.db_set('payment_gateway', '', update_modified=False)
                    # Speichere payment_url in DB (dauerhafter Link)
                    payment_request.db_set('payment_url', payment_link_url, update_modified=False)
                    frappe.db.commit()
                    # Prüfe nochmal ob payment_url gesetzt wurde
                    payment_request.reload()
                    if payment_request.payment_url != payment_link_url:
                        _log_err("WARNING: subscription_hook", f"SUBSCRIPTION HOOK: payment_url wurde nicht gespeichert, setze erneut")
                        payment_request.db_set('payment_url', payment_link_url, update_modified=False)
                        frappe.db.commit()
                    _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: payment_url (dauerhafter Link) gesetzt")
                    
                    # Rendere Message Template aus Payment Gateway Account (mit dauerhaftem payment_url)
                    from frappe.utils.jinja import render_template
                    gateway_account = frappe.get_doc(
                        "Payment Gateway Account", STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT
                    )
                    message_template = gateway_account.message or ""
                    rendered_message = render_template(message_template, {
                        "doc": invoice,
                        "payment_url": payment_link_url
                    })
                    payment_request.message = rendered_message
                    payment_request.save(ignore_permissions=True)
                else:
                    _log_err("ERROR: subscription_hook", f"SUBSCRIPTION HOOK: FEHLER - payment_url konnte nicht erstellt werden für Payment Request {payment_request.name}")

                # Submit Payment Request (E-Mail wird manuell gesteuert)
                payment_request.flags.mute_email = True
                payment_request.submit()
                
                # WICHTIG: payment_url NACH Submit nochmal setzen, da ERPNext es möglicherweise überschreibt
                if stripe_url:
                    payment_request.db_set('payment_url', payment_link_url, update_modified=False)
                    frappe.db.commit()
                    _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: payment_url nach submit erneut gesetzt")
                
                # E-Mail versenden (erste Rechnung mit Link, Folge ohne Link)
                is_first_invoice = is_first_invoice_for_subscription(invoice.name, doc.name)
                send_subscription_payment_request_email(
                    payment_request,
                    invoice,
                    include_payment_link=is_first_invoice,
                )

                _log_err(
                    "SUCCESS: subscription_hook",
                    f"SUBSCRIPTION HOOK: Payment Request {payment_request.name} erstellt",
                )
                
                # Erstelle zusätzlich einen Sales Order und verknüpfe ihn mit der bestehenden Invoice
                try:
                    sales_order = create_sales_order_from_invoice(invoice)
                    if sales_order:
                        msg = f"Sales Order {sales_order.name} aus Invoice {invoice_name} erstellt"
                        _log_err("SUCCESS: subscription_hook", msg[:140])
                        # Verknüpfe Invoice mit Sales Order
                        link_invoice_to_sales_order(invoice, sales_order)
                        frappe.db.commit()
                        _log_err("SUCCESS: subscription_hook", f"SUBSCRIPTION HOOK: Invoice {invoice_name} mit Sales Order {sales_order.name} verknüpft")
                        
                        # Submit Sales Order - das triggert automatisch Delivery Note und Packing List
                        # Da die Invoice bereits verknüpft ist, wird keine neue Invoice erstellt
                        sales_order.submit()
                        frappe.db.commit()
                        _log_err("SUCCESS: subscription_hook", f"SUBSCRIPTION HOOK: Sales Order {sales_order.name} submitted - Delivery Note und Packing List sollten erstellt werden")
                except Exception as e:
                    _log_err("ERROR: create_sales_order_from_invoice", f"Fehler beim Erstellen des Sales Order aus Invoice {invoice_name}: {str(e)}\n{frappe.get_traceback()}")
                
                frappe.msgprint(_("Abonnement-Update und Payment Request wurden automatisch erstellt"))
        else:
            _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist noch nicht erreicht")
            frappe.msgprint(_("Abonnement-Update wird erst am Startdatum ausgeführt"))
            
    except Exception as e:
        _log_err("ERROR: subscription_hook", f"SUBSCRIPTION HOOK FEHLER für {doc.name}: {str(e)}")


def create_payment_request_for_subscription_invoice(doc, method):
    """
    Erstellt automatisch Payment Request für alle Sales Invoices die zu einem Abonnement gehören
    Wird bei Sales Invoice on_submit ausgelöst
    WICHTIG: Diese Funktion wird NUR aufgerufen, wenn die Payment Request NICHT bereits von force_subscription_update erstellt wurde
    """
    try:
        # Prüfe ob die Rechnung zu einem Abonnement gehört
        if doc.subscription and doc.docstatus == 1:
            # WICHTIG: Prüfe ob bereits eine Stripe Subscription existiert
            # Wenn ja, wird Stripe automatisch abbuchen - keine Payment Request nötig;
            # Kunde erhält nur eine Informations-E-Mail mit Rechnung (ohne Zahlungslink)
            if has_stripe_subscription(doc.subscription):
                frappe.logger().info(
                    f"subscription_payment_request: Stripe-Abo {doc.subscription}, Informationsmail"
                )
                send_subscription_invoice_informational_email(doc)
                fulfill_subscription_invoice_with_sales_order(doc)
                return  # Keine Payment Request erstellen, Stripe bucht automatisch ab
            
            # WICHTIG: Prüfe ob das Startdatum des Abos erreicht ist
            # E-Mail soll nur gesendet werden, wenn das Startdatum erreicht ist
            subscription = frappe.get_doc("Subscription", doc.subscription)
            start_date_reached = subscription.start_date and frappe.utils.getdate(subscription.start_date) <= frappe.utils.getdate()
            
            if not start_date_reached:
                _log_err("DEBUG: subscription_payment_request", f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist noch nicht erreicht für Invoice {doc.name} - überspringe Payment Request Erstellung")
                return  # Keine Payment Request erstellen, wenn Startdatum noch nicht erreicht ist
            
            # Prüfe ob bereits eine Payment Request existiert
            # WICHTIG: Commit vor der Prüfung, um sicherzustellen, dass alle vorherigen Änderungen gespeichert sind
            frappe.db.commit()
            
            existing_requests = frappe.get_all("Payment Request",
                filters={
                    "reference_doctype": "Sales Invoice",
                    "reference_name": doc.name,
                    "docstatus": ["!=", 2]  # Nicht storniert
                }
            )
            
            if existing_requests:
                if not was_email_already_sent_for_invoice(doc.name):
                    payment_request = frappe.get_doc("Payment Request", existing_requests[0].name)
                    is_first_invoice = is_first_invoice_for_subscription(
                        doc.name, doc.subscription
                    )
                    send_subscription_payment_request_email(
                        payment_request,
                        doc,
                        include_payment_link=is_first_invoice,
                    )
                return
            
            # Keine Payment Request gefunden - erstelle neue
            if not existing_requests:
                # Hole Subscription Details für Subscription Plans
                subscription = frappe.get_doc("Subscription", doc.subscription)
                
                # Payment Request erstellen (ohne message zuerst)
                payment_request = frappe.get_doc({
                    "doctype": "Payment Request",
                    "payment_request_type": "Inward",
                    "transaction_date": doc.posting_date,
                    "party_type": "Customer",
                    "party": doc.customer,
                    "reference_doctype": "Sales Invoice",
                    "reference_name": doc.name,
                    "payment_gateway_account": STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT,
                    "grand_total": doc.grand_total,
                    "currency": doc.currency,
                    "email_to": get_invoice_email_address(doc),
                    "subject": f"Rechnung {doc.name}",
                    "is_a_subscription": 1,
                    "payment_channel": "Email",
                    "mute_email": 1
                })
                
                # Füge Subscription Plans hinzu (notwendig für Validierung)
                # Prüfe welches payment_gateway_account in den Subscription Plans vorhanden ist
                gateway_account = payment_request.payment_gateway_account
                if subscription.plans:
                    for plan_detail in subscription.plans:
                        # Prüfe ob dieser Plan ein payment_gateway_account hat
                        plan_gateway = getattr(plan_detail, 'payment_gateway_account', None)
                        if plan_gateway:
                            _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hat payment_gateway_account: {plan_gateway}")
                            gateway_account = plan_gateway
                            # Setze Payment Request auf dasselbe Account
                            payment_request.payment_gateway_account = gateway_account
                            break  # Verwende das erste gefundene Account
                
                # Stelle sicher, dass Payment Request das gateway_account hat
                payment_request.payment_gateway_account = gateway_account
                _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Verwende payment_gateway_account: {gateway_account}")
                
                for plan_detail in subscription.plans:
                    # Prüfe und aktualisiere das payment_gateway im Subscription Plan DocType
                    plan_doc = frappe.get_doc("Subscription Plan", plan_detail.plan)
                    if plan_doc.payment_gateway != gateway_account:
                        msg = f"Plan {plan_detail.plan}: payment_gateway={plan_doc.payment_gateway}, setze auf {gateway_account}"
                        _log_err("DEBUG: subscription_hook", msg[:140])
                        plan_doc.payment_gateway = gateway_account
                        plan_doc.save(ignore_permissions=True)
                    
                    # IMMER dasselbe payment_gateway_account für alle Plans verwenden
                    plan_row = payment_request.append("subscription_plans", {
                        "plan": plan_detail.plan,
                        "qty": plan_detail.qty,
                        "payment_gateway_account": gateway_account
                    })
                    _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hinzugefügt mit payment_gateway_account: {plan_row.payment_gateway_account}")
                
                # Stelle sicher, dass payment_gateway_account auch NACH dem Hinzufügen der Plans noch gesetzt ist
                payment_request.payment_gateway_account = gateway_account
                _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: Payment Request payment_gateway_account vor insert: {payment_request.payment_gateway_account}")
                
                payment_request.insert(ignore_permissions=True)
                # WICHTIG: Sofort committen, damit force_subscription_update die Payment Request findet
                frappe.db.commit()

                # Stripe-Checkout erzeugen und URL setzen
                stripe_url = create_stripe_checkout_session(payment_request)
                
                # Prüfe ob payment_url gesetzt wurde (Retry-Logik)
                if not stripe_url:
                    _log_err("WARNING: subscription_hook", f"SUBSCRIPTION HOOK: Stripe URL ist leer, versuche erneut für Payment Request {payment_request.name}")
                    # Reload Payment Request
                    payment_request.reload()
                    stripe_url = create_stripe_checkout_session(payment_request)
                
                if stripe_url:
                    # Dauerhafte Zahlungs-URL verwenden (bei Klick wird neue Stripe-Session erzeugt, Link läuft nicht nach 24h ab)
                    payment_link_url = get_payment_link_url(payment_request.name)
                    payment_request.payment_url = payment_link_url
                    # WICHTIG: Lokale Checkout-Seite dauerhaft deaktivieren.
                    # Durch das Leeren von payment_gateway verhindert ERPNext das Generieren von /stripe_checkout-Links.
                    # payment_gateway_account NICHT löschen, da Subscription Plans es benötigen
                    payment_request.db_set('payment_gateway', '', update_modified=False)
                    # Speichere payment_url in DB (dauerhafter Link)
                    payment_request.db_set('payment_url', payment_link_url, update_modified=False)
                    frappe.db.commit()
                    # Prüfe nochmal ob payment_url gesetzt wurde
                    payment_request.reload()
                    if payment_request.payment_url != payment_link_url:
                        _log_err("WARNING: subscription_hook", f"SUBSCRIPTION HOOK: payment_url wurde nicht gespeichert, setze erneut")
                        payment_request.db_set('payment_url', payment_link_url, update_modified=False)
                        frappe.db.commit()
                    _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: payment_url (dauerhafter Link) gesetzt")
                    
                    # Rendere Message Template aus Payment Gateway Account (mit dauerhaftem payment_url)
                    from frappe.utils.jinja import render_template
                    gateway_account = frappe.get_doc(
                        "Payment Gateway Account", STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT
                    )
                    message_template = gateway_account.message or ""
                    rendered_message = render_template(message_template, {
                        "doc": doc,
                        "payment_url": payment_link_url
                    })
                    payment_request.message = rendered_message
                    payment_request.save(ignore_permissions=True)
                else:
                    _log_err("ERROR: subscription_hook", f"SUBSCRIPTION HOOK: FEHLER - payment_url konnte nicht erstellt werden für Payment Request {payment_request.name}")

                # Submit Payment Request (E-Mail wird manuell gesteuert)
                payment_request.flags.mute_email = True
                payment_request.submit()
                
                # WICHTIG: payment_url NACH Submit nochmal setzen, da ERPNext es möglicherweise überschreibt
                if stripe_url:
                    payment_request.db_set('payment_url', payment_link_url, update_modified=False)
                    frappe.db.commit()
                    _log_err("DEBUG: subscription_hook", f"SUBSCRIPTION HOOK: payment_url nach submit erneut gesetzt")
                
                # E-Mail versenden (erste Rechnung mit Link, Folge ohne Link)
                is_first_invoice = is_first_invoice_for_subscription(doc.name, doc.subscription)
                send_subscription_payment_request_email(
                    payment_request,
                    doc,
                    include_payment_link=is_first_invoice,
                )

                _log_err(
                    "SUCCESS: subscription_payment_request",
                    f"Payment Request {payment_request.name} für Subscription Invoice {doc.name} erstellt",
                )
                
                fulfill_subscription_invoice_with_sales_order(doc)
            
    except Exception as e:
        _log_err("ERROR: subscription_payment_request", f"Fehler beim Erstellen der Payment Request für Subscription Invoice {doc.name}: {str(e)}")


def set_default_payment_gateway(doc, method):
    """
    Setzt automatisch Payment Gateway auf STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT wenn leer
    Wird bei Subscription Plan before_save/validate aufgerufen
    """
    try:
        if not doc.payment_gateway:
            doc.payment_gateway = STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT
            # Prüfe ob Payment Gateway Account existiert
            if not frappe.db.exists("Payment Gateway Account", STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT):
                _log_err(
                    "WARNING: subscription_plan",
                    f"Payment Gateway Account '{STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT}' existiert nicht",
                )
            else:
                _log_err(
                    "DEBUG: subscription_plan",
                    f"Payment Gateway auf {STRIPE_EUR_PAYMENT_GATEWAY_ACCOUNT} gesetzt für Plan {doc.name}",
                )
    except Exception as e:
        _log_err("ERROR: subscription_plan", f"Fehler beim Setzen des Payment Gateways für Plan {doc.name}: {str(e)}")


def validate_subscription_end_date(doc, method):
    """
    Deaktiviert Enddatum-Validierung wenn "Folgen Sie den Kalendermonaten" aktiviert ist
    Wird bei Subscription before_validate aufgerufen
    Überschreibt ERPNext's validate_to_follow_calendar_months Methode
    """
    try:
        # Prüfe ob "Folgen Sie den Kalendermonaten" aktiviert ist
        if doc.follow_calendar_months == 1:
            # Überschreibe die validate_to_follow_calendar_months Methode
            # um die Enddatum-Validierung zu deaktivieren
            def patched_validate_to_follow_calendar_months(self):
                # Überschreibe die Original-Methode - mache einfach nichts
                # Das deaktiviert die Validierung komplett
                pass
            
            # Setze die überschriebene Methode
            import types
            doc.validate_to_follow_calendar_months = types.MethodType(patched_validate_to_follow_calendar_months, doc)
            
            _log_err("DEBUG: subscription_validate", f"Enddatum-Validierung deaktiviert für Subscription {doc.name} (follow_calendar_months aktiviert)")
    except Exception as e:
        _log_err("ERROR: subscription_validate", f"Fehler bei Enddatum-Validierung für Subscription {doc.name}: {str(e)}")


def ensure_subscription_invoice_taxes_before_validate(doc, method):
    """
    Stellt sicher, dass Subscription-Invoices Steuern haben BEVOR sie validiert werden
    Wird bei Sales Invoice before_validate aufgerufen
    """
    try:
        # Nur für Subscription-Invoices
        if not doc.subscription:
            return
        
        # Nur im Draft-Modus
        if doc.docstatus != 0:
            return
        
        # Prüfe ob Steuern vorhanden sind und korrekt gesetzt sind
        needs_tax_update = False
        
        if not doc.taxes_and_charges:
            # Keine Steuern vorhanden - muss Steuer-Template setzen
            needs_tax_update = True
        elif not doc.taxes or len(doc.taxes) == 0:
            # Keine Steuer-Zeilen vorhanden
            needs_tax_update = True
        elif doc.taxes:
            # Prüfe ob Steuern auf "inklusive" gesetzt sind
            for tax in doc.taxes:
                if tax.included_in_print_rate != 1:
                    needs_tax_update = True
                    break
        
        if needs_tax_update:
            msg = f"Steuern müssen gesetzt werden für Invoice {doc.name} (Subscription: {doc.subscription})"
            _log_err("DEBUG: subscription_invoice_taxes", msg[:140])
            
            # Setze Steuer-Template wenn nicht gesetzt
            if not doc.taxes_and_charges:
                tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
                    {"company": doc.company, "is_default": 1}, "name")
                if tax_template:
                    doc.taxes_and_charges = tax_template
                    doc.taxes = []  # Leere bestehende Steuern
                    doc.run_method("set_taxes")  # Setze Steuern neu
                    _log_err("DEBUG: subscription_invoice_taxes", f"Steuer-Template {tax_template} gesetzt für Invoice {doc.name}")
            
            # Wende Steuerlogik an
            ensure_inclusive_taxes(doc)
            
            # Entferne alle Steuern außer 19% MWST
            if doc.taxes:
                taxes_to_remove = []
                for tax in doc.taxes:
                    # Prüfe ob es eine 19% Steuer ist
                    tax_rate = getattr(tax, 'rate', 0) or 0
                    description = getattr(tax, 'description', '') or ''
                    
                    # Behalte nur Steuern mit 19% (prüfe rate oder description)
                    if tax_rate != 19 and '19' not in description and '19%' not in description:
                        taxes_to_remove.append(tax)
                
                # Entferne Steuern die nicht 19% sind
                for tax in taxes_to_remove:
                    doc.remove(tax)
                    msg = f"Steuer {tax.description or tax.account_head} (Rate: {tax.rate}) entfernt - nur 19%"
                    _log_err("DEBUG: subscription_invoice_taxes", msg[:140])
            
            # Neuberechnung mit Steuern
            doc.calculate_taxes_and_totals()
            
            _log_err("SUCCESS: subscription_invoice_taxes", f"Steuern gesetzt für Invoice {doc.name} (nur 19% MWST)")
    except Exception as e:
        _log_err("ERROR: subscription_invoice_taxes", f"Fehler beim Setzen der Steuern für Subscription Invoice {doc.name}: {str(e)}\n{frappe.get_traceback()}")


def ensure_subscription_invoice_taxes(doc, method):
    """
    Stellt sicher, dass Subscription-Invoices Steuern haben BEVOR sie submitted werden
    Wird bei Sales Invoice before_submit aufgerufen
    """
    try:
        # Nur für Subscription-Invoices
        if not doc.subscription:
            return
        
        # Nur im Draft-Modus (bevor submit)
        if doc.docstatus != 0:
            return
        
        # Prüfe ob Steuern vorhanden sind und korrekt gesetzt sind
        needs_tax_update = False
        
        if not doc.taxes_and_charges:
            # Keine Steuern vorhanden - muss Steuer-Template setzen
            needs_tax_update = True
        elif doc.taxes:
            # Prüfe ob Steuern auf "inklusive" gesetzt sind
            for tax in doc.taxes:
                if tax.included_in_print_rate != 1:
                    needs_tax_update = True
                    break
        
        if needs_tax_update:
            msg = f"Steuern müssen gesetzt werden für Invoice {doc.name} (Subscription: {doc.subscription})"
            _log_err("DEBUG: subscription_invoice_taxes", msg[:140])
            
            # Wende Steuerlogik an
            ensure_inclusive_taxes(doc)
            
            # Entferne alle Steuern außer 19% MWST
            if doc.taxes:
                taxes_to_remove = []
                for tax in doc.taxes:
                    # Prüfe ob es eine 19% Steuer ist
                    tax_rate = getattr(tax, 'rate', 0) or 0
                    description = getattr(tax, 'description', '') or ''
                    
                    # Behalte nur Steuern mit 19% (prüfe rate oder description)
                    if tax_rate != 19 and '19' not in description and '19%' not in description:
                        taxes_to_remove.append(tax)
                
                # Entferne Steuern die nicht 19% sind
                for tax in taxes_to_remove:
                    doc.remove(tax)
                    msg = f"Steuer {tax.description or tax.account_head} (Rate: {tax.rate}) entfernt - nur 19%"
                    _log_err("DEBUG: subscription_invoice_taxes", msg[:140])
            
            # Neuberechnung mit Steuern
            doc.calculate_taxes_and_totals()
            
            _log_err("SUCCESS: subscription_invoice_taxes", f"Steuern gesetzt für Invoice {doc.name} (nur 19% MWST)")
    except Exception as e:
        _log_err("ERROR: subscription_invoice_taxes", f"Fehler beim Setzen der Steuern für Subscription Invoice {doc.name}: {str(e)}")


def validate_subscription_plan_interval(doc, method):
    """
    Deaktiviert Abrechnungsintervall-Validierung wenn Subscription "Folgen Sie den Kalendermonaten" aktiviert hat
    Wird bei Subscription Plan validate aufgerufen
    """
    try:
        # Prüfe ob dieser Plan in einer Subscription mit follow_calendar_months verwendet wird
        # Suche nach Subscriptions die diesen Plan verwenden
        subscriptions = frappe.get_all("Subscription Plan Detail",
            filters={"plan": doc.name},
            fields=["parent"],
            limit=10
        )
        
        for plan_detail in subscriptions:
            try:
                subscription = frappe.get_doc("Subscription", plan_detail.parent)
                if subscription.follow_calendar_months == 1:
                    # Überschreibe die validate Methode die Intervall-Validierung verlangt
                    # ERPNext's Standard-Validierung wird überschrieben
                    # Das Intervall muss nicht "Monat" sein wenn follow_calendar_months aktiviert ist
                    _log_err("DEBUG: subscription_plan_validate", f"Intervall-Validierung übersprungen für Plan {doc.name} (Subscription {plan_detail.parent} folgt Kalendermonaten)")
                    break
            except:
                continue
    except Exception as e:
        _log_err("ERROR: subscription_plan_validate", f"Fehler bei Intervall-Validierung für Plan {doc.name}: {str(e)}")


def link_invoice_to_sales_order(invoice, sales_order):
    """
    Verknüpft eine bestehende Invoice mit einem Sales Order
    Aktualisiert die Invoice Items, um den Sales Order zu referenzieren
    """
    try:
        _log_err("DEBUG: link_invoice_to_sales_order", f"Verknüpfe Invoice {invoice.name} mit Sales Order {sales_order.name}")
        
        # Lade Invoice neu
        invoice.reload()
        sales_order.reload()
        
        # Verknüpfe jedes Invoice Item mit dem Sales Order Item über SQL
        # Hole alle Invoice Items
        invoice_items = frappe.get_all("Sales Invoice Item",
            filters={"parent": invoice.name},
            fields=["name", "idx"],
            order_by="idx"
        )
        
        # Hole alle Sales Order Items
        so_items = frappe.get_all("Sales Order Item",
            filters={"parent": sales_order.name},
            fields=["name", "idx"],
            order_by="idx"
        )
        
        _log_err("DEBUG: link_invoice_to_sales_order", f"Invoice Items: {len(invoice_items)}, Sales Order Items: {len(so_items)}")
        
        # Verknüpfe jedes Invoice Item mit dem entsprechenden Sales Order Item
        for i, invoice_item in enumerate(invoice_items):
            if i < len(so_items):
                so_item_name = so_items[i].name
                # Setze sales_order und so_detail direkt über SQL
                frappe.db.sql("""
                    UPDATE `tabSales Invoice Item`
                    SET sales_order = %s, so_detail = %s
                    WHERE name = %s
                """, (sales_order.name, so_item_name, invoice_item.name))
                _log_err("DEBUG: link_invoice_to_sales_order", f"Invoice Item {invoice_item.name} verknüpft mit Sales Order Item {so_item_name}")
        
        try:
            frappe.db.set_value(
                "Sales Invoice",
                invoice.name,
                "sales_order",
                sales_order.name,
                update_modified=False,
            )
        except Exception:
            pass
        frappe.db.commit()
        _log_err("SUCCESS: invoice_linked_to_sales_order", f"Invoice {invoice.name} erfolgreich mit Sales Order {sales_order.name} verknüpft (über Items)")
        
    except Exception as e:
        _log_err("ERROR: link_invoice_to_sales_order", f"Fehler beim Verknüpfen der Invoice {invoice.name} mit Sales Order {sales_order.name}: {str(e)}\n{frappe.get_traceback()}")


def create_sales_order_from_invoice(invoice):
    """
    Erstellt einen Sales Order aus einer Sales Invoice (für Subscription-Invoices)
    Dieser Sales Order wird NICHT submitted, sondern nur mit der Invoice verknüpft
    """
    try:
        _log_err("DEBUG: create_sales_order_from_invoice", f"Erstelle Sales Order aus Invoice {invoice.name}")
        
        # Prüfe ob bereits ein Sales Order für diese Invoice existiert
        # Suche über po_no Feld (kann die Invoice-Nummer enthalten) oder einfach immer erstellen
        # Da wir keine zuverlässige Referenz haben, erstellen wir einfach immer einen neuen
        # Falls bereits einer existiert, wird das im try-catch abgefangen
        
        # Erstelle Items aus Invoice Items
        items = []
        for invoice_item in invoice.items:
            # Prüfe ob item_code vorhanden ist
            if not invoice_item.item_code:
                continue
                
            items.append({
                "doctype": "Sales Order Item",
                "item_code": invoice_item.item_code,
                "item_name": invoice_item.item_name or invoice_item.item_code,
                "qty": invoice_item.qty or 1,
                "rate": invoice_item.rate or 0,
                "uom": invoice_item.uom or "Stk",
                "stock_uom": invoice_item.stock_uom or invoice_item.uom or "Stk",
                "conversion_factor": invoice_item.conversion_factor or 1.0,
                "warehouse": invoice_item.warehouse,
                "delivery_date": invoice.due_date or invoice.posting_date or today()
            })
        
        if not items:
            _log_err("ERROR: no_items_found", f"Keine Items gefunden für Invoice {invoice.name}")
            return None
        
        # Erstelle Sales Order
        sales_order_data = {
            "doctype": "Sales Order",
            "customer": invoice.customer,
            "transaction_date": invoice.posting_date or today(),
            "delivery_date": invoice.due_date or invoice.posting_date or today(),
            "company": invoice.company or frappe.defaults.get_global_default("company"),
            "currency": invoice.currency or frappe.defaults.get_global_default("currency"),
            "items": items,
            "status": "Draft",
            "order_type": "Sales",
            "po_no": f"Subscription Invoice: {invoice.name}"  # Verwende po_no für Referenz
        }
        
        # Füge Adressen hinzu falls vorhanden
        if invoice.customer_address:
            sales_order_data["customer_address"] = invoice.customer_address
        if invoice.shipping_address_name:
            sales_order_data["shipping_address_name"] = invoice.shipping_address_name
        elif invoice.customer_address:
            sales_order_data["shipping_address_name"] = invoice.customer_address
        
        # Füge Subscription-Referenz hinzu falls vorhanden
        if invoice.subscription:
            sales_order_data["po_no"] = f"Subscription Invoice: {invoice.name} (Subscription: {invoice.subscription})"
            # Setze Custom Field custom_subscription
            if hasattr(sales_order_data, 'custom_subscription'):
                sales_order_data["custom_subscription"] = invoice.subscription
        
        sales_order = frappe.get_doc(sales_order_data)
        # Setze custom_subscription nach Erstellung des Dokuments
        if invoice.subscription and hasattr(sales_order, 'custom_subscription'):
            sales_order.custom_subscription = invoice.subscription
        sales_order.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Stelle sicher, dass custom_subscription gesetzt ist (falls Custom Field existiert)
        if invoice.subscription:
            try:
                frappe.db.set_value("Sales Order", sales_order.name, "custom_subscription", invoice.subscription, update_modified=False)
                frappe.db.commit()
            except:
                pass  # Custom Field existiert möglicherweise nicht
        
        _log_err("SUCCESS: sales_order_created", f"Sales Order {sales_order.name} aus Invoice {invoice.name} erstellt")
        return sales_order
        
    except Exception as e:
        _log_err("ERROR: create_sales_order_from_invoice", f"Fehler beim Erstellen des Sales Order aus Invoice {invoice.name}: {str(e)}\n{frappe.get_traceback()}")
        return None


def fulfill_subscription_invoice_with_sales_order(invoice_doc):
    """
    Idempotent: Sales Order aus Abo-Rechnung, Verknüpfung, Submit (Lieferschein/Packliste via Sales-Order-Hook).
    Wird bei Stripe-Abo benötigt, weil dort kein Payment-Request-Zweig läuft.
    """
    try:
        if not getattr(invoice_doc, "subscription", None):
            return
        invoice_doc.reload()
        for row in invoice_doc.items:
            if getattr(row, "sales_order", None):
                _log_err(
                    "DEBUG: subscription_fulfillment",
                    f"Invoice {invoice_doc.name} hat bereits Sales Order auf Positionen ({row.sales_order}) – überspringe",
                )
                return
        rows = frappe.db.sql(
            """
            select name from `tabSales Order`
            where po_no like %s and docstatus != 2
            limit 1
            """,
            (f"Subscription Invoice: {invoice_doc.name}%",),
        )
        if rows:
            existing_so = rows[0][0]
            so_doc = frappe.get_doc("Sales Order", existing_so)
            _log_err(
                "DEBUG: subscription_fulfillment",
                f"Invoice {invoice_doc.name}: bestehender SO {existing_so} (po_no) – verknüpfen/submit",
            )
            link_invoice_to_sales_order(invoice_doc, so_doc)
            frappe.db.commit()
            if so_doc.docstatus == 0:
                so_doc.reload()
                so_doc.submit()
                frappe.db.commit()
            return
        sales_order = create_sales_order_from_invoice(invoice_doc)
        if not sales_order:
            return
        _log_err(
            "SUCCESS: subscription_hook",
            f"SUBSCRIPTION HOOK: Sales Order {sales_order.name} aus Invoice {invoice_doc.name} erstellt",
        )
        link_invoice_to_sales_order(invoice_doc, sales_order)
        frappe.db.commit()
        _log_err(
            "SUCCESS: subscription_hook",
            f"SUBSCRIPTION HOOK: Invoice {invoice_doc.name} mit Sales Order {sales_order.name} verknüpft",
        )
        sales_order.submit()
        frappe.db.commit()
        _log_err(
            "SUCCESS: subscription_hook",
            f"SUBSCRIPTION HOOK: Sales Order {sales_order.name} submitted – Delivery Note / Packliste",
        )
    except Exception as e:
        _log_err(
            "ERROR: subscription_fulfillment_so",
            f"Fehler Fulfillment SO für Invoice {getattr(invoice_doc, 'name', '?')}: {str(e)}\n{frappe.get_traceback()}",
        )


def _get_last_subscription_invoice(subscription_name):
    rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "subscription": subscription_name,
            "docstatus": ["!=", 2],
            "is_return": 0,
        },
        fields=["posting_date", "from_date", "to_date"],
        order_by="posting_date desc",
        limit=1,
    )
    return rows[0] if rows else None


def _get_subscription_period_anchor_date(sub, last_invoice=None):
    """
    Anker für die Neuberechnung: letzte Auslösung (Rechnung) oder Abo-Start.
    """
    last_invoice = last_invoice or _get_last_subscription_invoice(sub.name)
    if not last_invoice:
        return sub.start_date, _("Abo-Start")

    generate_at = sub.generate_invoice_at or "Beginning of the current subscription period"

    if generate_at == "Beginning of the current subscription period":
        anchor = last_invoice.posting_date
    elif generate_at == "End of the current subscription period":
        anchor = last_invoice.from_date or last_invoice.posting_date
    else:
        anchor = last_invoice.from_date or last_invoice.posting_date

    return anchor, _("letzte Auslösung")


def _resolve_recalculated_period(sub, anchor, last_invoice):
    """
    Leitet die neue Abo-Periode ab.

    - Verkürzung (Peggy): bestehende Rechnung deckt länger ab als der neue Plan → Periode am Anker kürzen.
    - Laufendes Abo (Marzinke): letzte Auslösung liegt zurück → nächste Periode eintragen, nicht erneut öffnen.
    """
    anchor = getdate(anchor)
    period_end_from_anchor = getdate(_compute_subscription_period_end(sub, anchor))

    if last_invoice:
        inv_to = last_invoice.get("to_date")
        inv_posting = getdate(last_invoice.get("posting_date"))

        if inv_to and getdate(inv_to) >= period_end_from_anchor and inv_posting <= getdate(today()):
            return anchor, period_end_from_anchor

        if inv_posting <= getdate(today()):
            next_start = add_days(period_end_from_anchor, 1)
            return getdate(next_start), getdate(_compute_subscription_period_end(sub, next_start))

    return anchor, period_end_from_anchor


def _get_next_subscription_term(sub, period_start, period_end):
    generate_at = sub.generate_invoice_at or "Beginning of the current subscription period"
    if generate_at == "Beginning of the current subscription period":
        return getdate(period_start)
    if generate_at == "End of the current subscription period":
        return getdate(period_end)
    return getdate(add_days(period_start, -(sub.number_of_days or 0)))


def _compute_subscription_period_end(sub, period_start):
    """Periodenende aus Startdatum und aktuellem Plan (ohne ERPNext-Rückfall auf Abo-Start)."""
    billing_cycle_info = sub.get_billing_cycle_data()
    if not billing_cycle_info:
        frappe.throw(_("Kein Abrechnungsintervall im Abonnement-Plan gefunden."))

    period_start = getdate(period_start)
    period_end = add_to_date(period_start, **billing_cycle_info)

    if sub.follow_calendar_months:
        billing_info = sub.get_billing_cycle_and_interval()
        if billing_info:
            billing_interval_count = billing_info[0]["billing_interval_count"]
            period_end = get_last_day(add_months(period_start, billing_interval_count - 1))

    if sub.end_date and getdate(period_end) > getdate(sub.end_date):
        period_end = sub.end_date

    return period_end


@frappe.whitelist()
def recalculate_subscription_period(subscription_name):
    """
    Berechnet current_invoice_start/end neu anhand des aktuellen Plans.
    Laufende Abos: ab letzter Auslösung. Neue Abos ohne Rechnung: ab Abo-Start.
    """
    frappe.has_permission("Subscription", "write", subscription_name, throw=True)

    sub = frappe.get_doc("Subscription", subscription_name)
    if not sub.start_date:
        frappe.throw(_("Bitte zuerst ein Startdatum für das Abonnement setzen."))

    old_start = sub.current_invoice_start
    old_end = sub.current_invoice_end

    last_invoice = _get_last_subscription_invoice(sub.name)
    anchor, anchor_source = _get_subscription_period_anchor_date(sub, last_invoice)
    if not anchor:
        frappe.throw(_("Kein gültiges Ankerdatum für die Neuberechnung gefunden."))

    period_start, period_end = _resolve_recalculated_period(sub, anchor, last_invoice)

    if getdate(period_end) < getdate(period_start):
        frappe.throw(
            _("Berechnetes Periodenende ({0}) liegt vor dem Periodenstart ({1}).").format(
                period_end, period_start
            )
        )

    sub.current_invoice_start = period_start
    sub.current_invoice_end = period_end
    sub.save()

    next_term = _get_next_subscription_term(sub, period_start, period_end)

    _log_err(
        "INFO: subscription_period_recalc",
        f"{subscription_name} (Anker={anchor_source} {period_start}): "
        f"{old_start} -> {old_end} wurde {period_start} -> {period_end}, "
        f"nächster Termin {next_term}",
    )

    return {
        "success": True,
        "old_period": f"{old_start} → {old_end}",
        "new_period": f"{period_start} → {period_end}",
        "next_term": str(next_term),
        "anchor_source": str(anchor_source),
        "message": _(
            "Abo-Periode neu berechnet (Anker: {0}, {1}). Nächster Termin: {2}. Bitte Stripe separat prüfen."
        ).format(anchor_source, period_start, next_term),
    }
