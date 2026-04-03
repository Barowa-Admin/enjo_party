import frappe


def execute():
    """Entfernt Betreff-Custom-Field; Folge-Mail-Feld direkt unter Section Break (Layout wie Standard Payment Request Message)."""
    msg_cf = frappe.db.get_value(
        "Custom Field",
        {"dt": "Payment Gateway Account", "fieldname": "custom_abo_info_email_message"},
        "name",
    )
    if msg_cf:
        frappe.db.set_value(
            "Custom Field",
            msg_cf,
            {
                "insert_after": "custom_abo_email_section",
                "label": "Abo-Folge-Mail",
                "description": "Jinja wie bei Abo-Mail. Leer = Standardtext. Betreff fest: „Rechnung …“.",
            },
        )

    subject_names = frappe.get_all(
        "Custom Field",
        filters={
            "dt": "Payment Gateway Account",
            "fieldname": "custom_abo_info_email_subject",
        },
        pluck="name",
    )
    for cf_name in subject_names:
        frappe.delete_doc("Custom Field", cf_name, force=True, ignore_permissions=True)

    section_cf = frappe.db.get_value(
        "Custom Field",
        {"dt": "Payment Gateway Account", "fieldname": "custom_abo_email_section"},
        "name",
    )
    if section_cf:
        frappe.db.set_value("Custom Field", section_cf, "label", "")
        frappe.db.set_value("Custom Field", section_cf, "description", "")

    frappe.clear_cache()
