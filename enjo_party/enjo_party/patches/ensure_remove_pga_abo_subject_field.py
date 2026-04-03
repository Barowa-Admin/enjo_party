import frappe


def execute():
    """Entfernt ggf. verbliebenes Betreff-Feld (Folge) am Payment Gateway Account – idempotent."""
    names = frappe.get_all(
        "Custom Field",
        filters={
            "dt": "Payment Gateway Account",
            "fieldname": "custom_abo_info_email_subject",
        },
        pluck="name",
    )
    for cf_name in names:
        frappe.delete_doc("Custom Field", cf_name, force=True, ignore_permissions=True)
    frappe.clear_cache()
