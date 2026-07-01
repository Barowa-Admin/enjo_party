import frappe


def execute():
    """Abo-Scheduler auf Daily Long (long queue, mehr Timeout) umstellen."""
    job_name = "subscription_scheduler.process_due_subscriptions"
    if not frappe.db.exists("Scheduled Job Type", job_name):
        return

    frappe.db.set_value(
        "Scheduled Job Type",
        job_name,
        {"frequency": "Daily Long", "stopped": 0},
        update_modified=False,
    )
