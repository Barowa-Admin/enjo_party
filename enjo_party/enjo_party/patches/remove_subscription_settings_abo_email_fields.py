import frappe


def execute():
    """Entfernt Abo-Folge-Mail Custom Fields von Subscription Settings (Umzug nach Payment Gateway Account)."""
    fieldnames = (
        "custom_abo_info_email_message",
        "custom_abo_info_email_subject",
        "custom_abo_email_section",
    )
    for fieldname in fieldnames:
        names = frappe.get_all(
            "Custom Field",
            filters={"dt": "Subscription Settings", "fieldname": fieldname},
            pluck="name",
        )
        for cf_name in names:
            frappe.delete_doc("Custom Field", cf_name, force=True, ignore_permissions=True)
