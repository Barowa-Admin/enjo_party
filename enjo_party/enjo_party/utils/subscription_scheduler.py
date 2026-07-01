#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import frappe

from enjo_party.enjo_party.utils.subscription_hooks import (
    has_non_return_subscription_invoice_for_date,
    process_subscription_billing_safe,
)

# Nur wirklich fällige Abos laden (statt aller Active/Unpaid).
DEFAULT_CANDIDATE_LIMIT = 500
BATCH_PROGRESS_EVERY = 25


def _log_scheduler(message, title="INFO: subscription_scheduler"):
    frappe.log_error(title=title, message=frappe.as_unicode(message or ""))


def _get_processing_date(subscription_row, today_date):
    generate_invoice_at = subscription_row.get("generate_invoice_at")
    if not generate_invoice_at or generate_invoice_at == "Beginning of the current subscription period":
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


def _get_due_subscription_candidates(today_date, limit=DEFAULT_CANDIDATE_LIMIT):
    """
    SQL-Vorfilter: nur Abos laden, deren processing_date heute oder früher ist.
    Sortierung: älteste Fälligkeit zuerst (nicht modified DESC).
    """
    today = frappe.utils.getdate(today_date)
    return frappe.db.sql(
        """
        SELECT
            name,
            status,
            start_date,
            generate_invoice_at,
            current_invoice_start,
            current_invoice_end,
            number_of_days
        FROM `tabSubscription`
        WHERE docstatus != 2
          AND status IN ('Active', 'Past Due Date', 'Unpaid')
          AND (start_date IS NULL OR start_date <= %(today)s)
          AND (
            (
                IFNULL(
                    generate_invoice_at,
                    'Beginning of the current subscription period'
                ) = 'Beginning of the current subscription period'
                AND current_invoice_start IS NOT NULL
                AND current_invoice_start <= %(today)s
            )
            OR (
                generate_invoice_at = 'End of the current subscription period'
                AND current_invoice_end IS NOT NULL
                AND current_invoice_end <= %(today)s
            )
            OR (
                generate_invoice_at = 'Days before the current subscription period'
                AND current_invoice_start IS NOT NULL
                AND DATE_SUB(
                    current_invoice_start,
                    INTERVAL IFNULL(number_of_days, 0) DAY
                ) <= %(today)s
            )
          )
        ORDER BY current_invoice_start ASC, name ASC
        LIMIT %(limit)s
        """,
        {"today": today, "limit": limit},
        as_dict=True,
    )


def process_due_subscriptions(posting_date=None, limit=None, batch_log_every=None):
    """
    Täglicher Job: fällige Subscriptions abrechnen (idempotent, mit Zeilen-Lock).

    Lädt nur SQL-vorgefilterte Kandidaten (nicht alle Active-Abos) und verarbeitet
    älteste Fälligkeiten zuerst. Abschluss-Log in finally, damit Abbrüche sichtbar sind.
    """
    today_date = frappe.utils.getdate(posting_date or frappe.utils.today())
    candidate_limit = limit or DEFAULT_CANDIDATE_LIMIT
    progress_every = batch_log_every if batch_log_every is not None else BATCH_PROGRESS_EVERY

    processed = 0
    skipped = 0
    failed = 0
    candidates = []
    aborted = False
    abort_reason = None

    _log_scheduler(f"Subscription-Scheduler gestartet (today={today_date}, limit={candidate_limit})")

    try:
        candidates = _get_due_subscription_candidates(today_date, candidate_limit)
        _log_scheduler(
            f"Subscription-Scheduler Kandidaten: {len(candidates)} "
            f"(SQL-gefiltert, sortiert nach current_invoice_start ASC)"
        )

        for idx, s in enumerate(candidates, start=1):
            name = s.get("name")
            try:
                processing_date = _get_processing_date(s, today_date)
                if not processing_date:
                    skipped += 1
                    continue

                pd = frappe.utils.getdate(processing_date)
                if pd > today_date:
                    skipped += 1
                    continue

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
                _log_scheduler(
                    f"Subscription-Scheduler Fehler bei {name}: {str(e)}\n{frappe.get_traceback()}",
                    title="ERROR: subscription_scheduler",
                )

            if progress_every and idx % progress_every == 0:
                _log_scheduler(
                    f"Subscription-Scheduler Fortschritt: {idx}/{len(candidates)} "
                    f"processed={processed} skipped={skipped} failed={failed}"
                )

    except Exception as e:
        aborted = True
        abort_reason = str(e)
        _log_scheduler(
            f"Subscription-Scheduler abgebrochen: {str(e)}\n{frappe.get_traceback()}",
            title="ERROR: subscription_scheduler",
        )
        raise
    finally:
        summary = (
            f"Subscription-Scheduler fertig: processed={processed}, skipped={skipped}, "
            f"failed={failed}, candidates={len(candidates)}"
        )
        if aborted:
            summary += f", ABORTED={abort_reason}"
        _log_scheduler(summary)
