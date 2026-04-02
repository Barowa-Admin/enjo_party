#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import frappe


def _get_processing_date(subscription_row, today_date):
    generate_invoice_at = subscription_row.get("generate_invoice_at")
    if generate_invoice_at == "Beginning of the current subscription period":
        return subscription_row.get("current_invoice_start")
    if generate_invoice_at == "End of the current subscription period":
        return subscription_row.get("current_invoice_end")
    if generate_invoice_at == "Days before the current subscription period":
        cis = subscription_row.get("current_invoice_start")
        if not cis:
            return None
        nd = subscription_row.get("number_of_days") or 0
        return frappe.utils.add_days(cis, -nd)
    # Fallback: wenn generate_invoice_at unerwartet ist, nichts tun
    return None


def _has_non_return_invoice_for_date(subscription_name, posting_date):
    """
    Idempotenz: wenn für das Abo bereits eine (nicht-Retoure) Rechnung an diesem Datum existiert,
    dann nicht nochmal process() aufrufen.
    """
    inv = frappe.get_all(
        "Sales Invoice",
        filters={
            "subscription": subscription_name,
            "posting_date": posting_date,
            "docstatus": ["in", [0, 1]],
            "is_return": 0,
        },
        fields=["name"],
        limit_page_length=1,
    )
    return bool(inv)


def process_due_subscriptions(posting_date=None, limit=2000):
    """
    Täglicher Job:
    - sucht Subscriptions, deren processing_date <= today ist
    - ruft subscription.process(posting_date=processing_date) auf
    - ist idempotent über bestehende Rechnungen (nicht-Retoure) am processing_date

    Hinweis: bewusst defensiv — wir loggen Fehler pro Subscription, damit der Job nicht komplett abbricht.
    """
    today_date = frappe.utils.getdate(posting_date or frappe.utils.today())

    frappe.log_error(
        f"Subscription-Scheduler gestartet (today={today_date})",
        "INFO: subscription_scheduler",
    )

    # Nur relevante Status: Active/Past Due/Unpaid (ERPNext nutzt diese häufig für Subscription)
    subscriptions = frappe.get_all(
        "Subscription",
        filters={
            "docstatus": ["!=", 2],
            "status": ["in", ["Active", "Past Due Date", "Unpaid"]],
        },
        fields=[
            "name",
            "status",
            "start_date",
            "generate_invoice_at",
            "current_invoice_start",
            "current_invoice_end",
            "number_of_days",
        ],
        limit_page_length=limit,
    )

    processed = 0
    skipped = 0
    failed = 0

    for s in subscriptions:
        name = s.get("name")
        try:
            # Startdatum in Zukunft: skip
            start_date = s.get("start_date")
            if start_date and frappe.utils.getdate(start_date) > today_date:
                skipped += 1
                continue

            processing_date = _get_processing_date(s, today_date)
            if not processing_date:
                skipped += 1
                continue

            pd = frappe.utils.getdate(processing_date)
            if pd > today_date:
                skipped += 1
                continue

            # Idempotenz
            if _has_non_return_invoice_for_date(name, pd):
                skipped += 1
                continue

            doc = frappe.get_doc("Subscription", name)
            doc.process(posting_date=str(pd))
            frappe.db.commit()
            processed += 1

        except Exception as e:
            frappe.db.rollback()
            failed += 1
            frappe.log_error(
                f"Subscription-Scheduler Fehler bei {name}: {str(e)}\n{frappe.get_traceback()}",
                "ERROR: subscription_scheduler",
            )

    frappe.log_error(
        f"Subscription-Scheduler fertig: processed={processed}, skipped={skipped}, failed={failed}",
        "INFO: subscription_scheduler",
    )

