# Copyright (c) 2026, Elia and contributors
# For license information, please see license.txt

import frappe

AUTOMATED_BILLING_SOURCES = frozenset({
    "scheduler",
    "catchup",
    "force_subscription_update",
})

PAUSE_FIELD = "custom_pause_automatic_subscription_billing"


def is_subscription_automation_paused():
    try:
        return bool(
            frappe.db.get_single_value("Subscription Settings", PAUSE_FIELD)
        )
    except Exception:
        return False


def log_subscription_automation_paused(context):
    frappe.log_error(
        title="INFO: subscription_automation_paused",
        message=frappe.as_unicode(context or ""),
    )


def ensure_subscription_automation_not_paused(context):
    if is_subscription_automation_paused():
        log_subscription_automation_paused(context)
        frappe.throw(
            "Automatische Abo-Abrechnung ist pausiert (Abonnementeinstellungen). "
            "Bitte Pause deaktivieren, bevor Catch-up oder Scheduler manuell ausgeführt wird.",
            title="Abo-Automatismus pausiert",
        )
