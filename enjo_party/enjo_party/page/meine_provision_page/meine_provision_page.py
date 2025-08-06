import frappe
from frappe.utils import flt
import calendar
from datetime import datetime


@frappe.whitelist()
def get_provision_data(month=None, year=None):
    """
    Holt Provisionsdaten für den angemeldeten User.
    Umgeht Berechtigungsprüfungen durch eigene Sicherheitslogik.
    """
    user = frappe.session.user
    
    # Automatisch den letzten abgeschlossenen Monat setzen
    if not month or not year:
        heute = datetime.now()
        import datetime as dt
        letzter_monat = heute.replace(day=1) - dt.timedelta(days=1)
        
        month_names = [
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember"
        ]
        
        if not month:
            month = month_names[letzter_monat.month - 1]
        if not year:
            year = letzter_monat.year

    # Sales Partner für aktuellen User finden
    sales_partner = None
    
    # Versuche über user-Feld
    try:
        sales_partner_meta = frappe.get_meta("Sales Partner")
        if sales_partner_meta.has_field("user"):
            sales_partner = frappe.db.get_value("Sales Partner", {"user": user}, "name")
    except:
        pass
    
    # Versuche über Namen
    if not sales_partner:
        try:
            user_full_name = frappe.db.get_value("User", user, "full_name")
            if user_full_name:
                sales_partner = frappe.db.get_value("Sales Partner", {"partner_name": user_full_name}, "name")
            if not sales_partner:
                sales_partner = frappe.db.get_value("Sales Partner", {"partner_name": user}, "name")
        except:
            pass

    # SQL Query mit eigener Sicherheitslogik
    sql_query = """
        SELECT
            si.posting_date,
            si.name,
            c.customer_name,
            si.base_net_total,
            (si.base_net_total * (COALESCE(sp.commission_rate, 20) / 100)) as provision
        FROM `tabSales Invoice` si
        LEFT JOIN `tabCustomer` c ON si.customer = c.name
        LEFT JOIN `tabSales Partner` sp ON si.sales_partner = sp.name
        WHERE si.docstatus = 1
    """
    
    sql_conditions = []
    sql_values = {}
    
    # SICHERHEIT: User sieht nur eigene Daten
    if sales_partner:
        sql_conditions.append("si.sales_partner = %(sales_partner)s")
        sql_values["sales_partner"] = sales_partner
    else:
        # Fallback: Nur eigene erstellte Rechnungen
        sql_conditions.append("si.owner = %(current_user)s")
        sql_values["current_user"] = user
    
    # Monatsfilter
    if month and year:
        month_names = [
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember"
        ]
        if month in month_names:
            month_num = month_names.index(month) + 1
            
            first_day = f"{year}-{month_num:02d}-01"
            last_day_num = calendar.monthrange(int(year), month_num)[1]
            last_day = f"{year}-{month_num:02d}-{last_day_num:02d}"
            
            sql_conditions.append("si.posting_date BETWEEN %(first_day)s AND %(last_day)s")
            sql_values["first_day"] = first_day
            sql_values["last_day"] = last_day
    
    if sql_conditions:
        sql_query += " AND " + " AND ".join(sql_conditions)
    
    sql_query += " ORDER BY si.posting_date DESC"
    
    # Führe Query aus
    try:
        invoices = frappe.db.sql(sql_query, sql_values, as_dict=True)
    except Exception as e:
        frappe.log_error(f"Fehler bei Provisionsabfrage: {str(e)}", "ERROR: provision_query")
        return []

    # Daten formatieren
    data = []
    total_provision = 0
    
    for inv in invoices:
        provision = flt(inv.provision)
        total_provision += provision
        
        data.append([
            inv.posting_date.strftime('%d.%m.%Y') if inv.posting_date else '',
            inv.name,
            inv.customer_name,
            flt(inv.base_net_total),
            provision,
        ])
    
    # Gesamtsumme hinzufügen
    if data and month:
        data.append([
            "",
            "GESAMT",
            f"Provision {month} {year}",
            "",
            total_provision,
        ])
    
    return data