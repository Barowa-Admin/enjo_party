# Copyright (c) 2026, Elia and contributors
# For license information, please see license.txt

"""
Einmalige Catch-up-Hilfen für Abo Phase C (System Manager / System Console).
"""

import frappe
from frappe.utils import getdate, today

from enjo_party.enjo_party.utils.subscription_settings_helper import (
    ensure_subscription_automation_not_paused,
)


def _log_catchup(title, message=None):
    t = (title or "Error")[:140]
    frappe.log_error(title=t, message=frappe.as_unicode(message or ""))


@frappe.whitelist()
def advance_settled_subscription_periods(limit=200):
    """
    Lässt den Scheduler Deadlock-Abos (bezahlt, Periode abgelaufen) vorrücken
    und erzeugt ggf. die nächste fällige Rechnung (max. eine SI pro Abo und Lauf).
    """
    frappe.only_for("System Manager")
    ensure_subscription_automation_not_paused("advance_settled_subscription_periods")
    from enjo_party.enjo_party.utils.subscription_scheduler import process_due_subscriptions

    limit = int(limit or 200)
    return process_due_subscriptions(limit=limit)


@frappe.whitelist()
def force_process_subscription(subscription_name, posting_date=None):
    """
    Erzwingt process_subscription_billing_safe für ein einzelnes Abo.
    posting_date default: current_invoice_start bzw. today.
    """
    frappe.only_for("System Manager")
    if not subscription_name:
        frappe.throw("subscription_name erforderlich")

    ensure_subscription_automation_not_paused(
        f"force_process_subscription subscription={subscription_name}"
    )

    from enjo_party.enjo_party.utils.subscription_hooks import (
        _get_processing_date_for_subscription,
        process_subscription_billing_safe,
    )

    sub = frappe.get_doc("Subscription", subscription_name)
    if posting_date:
        pd = getdate(posting_date)
    else:
        pd = getdate(_get_processing_date_for_subscription(sub) or sub.current_invoice_start or today())

    outcome = process_subscription_billing_safe(subscription_name, pd, source="catchup")
    sub.reload()
    return {
        "subscription": subscription_name,
        "posting_date": str(pd),
        "outcome": outcome,
        "current_invoice_start": str(sub.current_invoice_start) if sub.current_invoice_start else None,
        "current_invoice_end": str(sub.current_invoice_end) if sub.current_invoice_end else None,
        "status": sub.status,
    }


@frappe.whitelist()
def link_sales_invoice_to_subscription(invoice_name, subscription_name):
    """Verknüpft eine Sales Invoice manuell mit einem Abo und aktualisiert den Zahlungsstatus."""
    frappe.only_for("System Manager")
    if not invoice_name or not subscription_name:
        frappe.throw("invoice_name und subscription_name erforderlich")

    if not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(f"Sales Invoice {invoice_name} nicht gefunden")
    if not frappe.db.exists("Subscription", subscription_name):
        frappe.throw(f"Subscription {subscription_name} nicht gefunden")

    frappe.db.set_value("Sales Invoice", invoice_name, "subscription", subscription_name)
    frappe.db.commit()

    from enjo_party.enjo_party.utils.subscription_status_indicator import (
        update_subscription_payment_status,
    )

    status = update_subscription_payment_status(subscription_name)
    return {
        "invoice": invoice_name,
        "subscription": subscription_name,
        "custom_payment_status": status,
    }


@frappe.whitelist()
def repair_cancelled_subscription_payment_status():
    """Setzt custom_payment_status=Beendet für alle Cancelled-Abos."""
    frappe.only_for("System Manager")
    if not frappe.db.has_column("Subscription", "custom_payment_status"):
        return {"updated": 0, "reason": "no_custom_payment_status_column"}

    names = frappe.get_all(
        "Subscription",
        filters={"status": "Cancelled", "custom_payment_status": ["!=", "Beendet"]},
        pluck="name",
    )
    for name in names:
        frappe.db.set_value(
            "Subscription",
            name,
            "custom_payment_status",
            "Beendet",
            update_modified=False,
        )
    frappe.db.commit()
    return {"updated": len(names)}


@frappe.whitelist()
def catchup_phase_c_known_cases():
    """
    Bekannte Einzelfälle aus der Diagnose (Ildiko, Marie) + Cancelled-Status-Cleanup.
    Retouren separat: sales_invoice_return.repair_unallocated_returns()
    """
    frappe.only_for("System Manager")
    results = {}

    # Marie Eckert: manuelle SI ohne subscription
    try:
        results["marie_link"] = link_sales_invoice_to_subscription(
            "ACC-SINV-2026-00531",
            "ACC-SUB-2026-00014",
        )
    except Exception as e:
        results["marie_link"] = {"error": str(e)}
        _log_catchup("ERROR: catchup_marie", frappe.get_traceback())

    # Ildiko: fällige Juli-Periode ohne SI
    try:
        results["ildiko_process"] = force_process_subscription("ACC-SUB-2026-00027")
    except Exception as e:
        results["ildiko_process"] = {"error": str(e)}
        _log_catchup("ERROR: catchup_ildiko", frappe.get_traceback())

    try:
        results["cancelled_status"] = repair_cancelled_subscription_payment_status()
    except Exception as e:
        results["cancelled_status"] = {"error": str(e)}

    return results
