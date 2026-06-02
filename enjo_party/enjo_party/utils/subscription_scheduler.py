#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import frappe

from enjo_party.enjo_party.utils.subscription_hooks import (
    has_non_return_subscription_invoice_for_date,
    process_subscription_billing_safe,
)


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
    return None


def process_due_subscriptions(posting_date=None, limit=2000):
    """
    Täglicher Job: fällige Subscriptions abrechnen (idempotent, mit Zeilen-Lock).
    """
    today_date = frappe.utils.getdate(posting_date or frappe.utils.today())

    frappe.log_error(
        f"Subscription-Scheduler gestartet (today={today_date})",
        "INFO: subscription_scheduler",
    )

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

            # Schneller Vorfilter (authoritative Prüfung in process_subscription_billing_safe)
            if has_non_return_subscription_invoice_for_date(name, pd):
                skipped += 1
                continue

            if process_subscription_billing_safe(name, pd, source="scheduler"):
                processed += 1
            else:
                skipped += 1

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
