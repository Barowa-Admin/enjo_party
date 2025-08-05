import frappe
from frappe.utils import getdate, add_months
from frappe import _

@frappe.whitelist()
def get_data(month: str = None):
    """
    Gibt Provisionen für den aktuellen User und gewählten Monat zurück.
    month: 'YYYY-MM' (z.B. '2025-07')
    """
    user = frappe.session.user
    sales_partner = frappe.db.get_value("Sales Partner", {"name": user})
    if not sales_partner:
        return {"error": _(f"Kein Sales Partner für User {user} gefunden.")}

    # Datumsbereich für den Monat bestimmen
    if not month:
        today = getdate()
        month = today.strftime("%Y-%m")
    year, mon = map(int, month.split("-"))
    from_date = f"{year}-{mon:02d}-01"
    to_date = add_months(from_date, 1)

    # Query wie im Beispiel, aber gefiltert auf Partner und Monat
    data = frappe.db.sql(f'''
        SELECT
            si.posting_date      AS datum,
            si.name              AS rechnung,
            c.customer_name      AS kundenname,
            si.base_net_total    AS betrag,
            (si.base_net_total * (sp.commission_rate / 100)) AS provision
        FROM `tabSales Invoice` si
        LEFT JOIN `tabCustomer` c ON si.customer = c.name
        LEFT JOIN `tabSales Partner` sp ON si.sales_partner = sp.name
        WHERE si.sales_partner = %s
          AND si.docstatus = 1
          AND si.posting_date >= %s
          AND si.posting_date < %s
        ORDER BY si.posting_date ASC
    ''', (user, from_date, to_date), as_dict=True)

    # Summen berechnen
    sum_betrag = sum(row['betrag'] for row in data)
    sum_provision = sum(row['provision'] for row in data)

    return {
        "data": data,
        "sum_betrag": sum_betrag,
        "sum_provision": sum_provision,
        "from_date": from_date,
        "to_date": to_date,
        "sales_partner": user
    }