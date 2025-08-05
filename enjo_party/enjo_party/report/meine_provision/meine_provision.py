import frappe
from frappe import _
from frappe.utils import flt, getdate, today, add_months
import calendar
from datetime import datetime


def execute(filters=None):
    """Liefert eine einfache Übersicht aller gebuchten Rechnungen, für die die
    aktuelle Benutzerin als *Sales Partner* hinterlegt ist. Zeigt
    Rechnungsbetrag, Provisionssatz und berechnete Provision an.
    """
    # Fallback: Falls Filter in JSON nicht geladen werden, hier definieren
    if not filters:
        filters = {}
    
    # Debug: Filter-Werte anzeigen
    frappe.log_error(f"Filter empfangen: {filters}", "DEBUG: meine_provision")
    user = frappe.session.user
    
    # Sicherheitscheck: Darf der User überhaupt Sales Invoices sehen?
    if not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw("Sie haben keine Berechtigung, Rechnungen einzusehen.")

    # Versuche automatisch die Sales-Partnerin zum aktuellen Benutzer zu finden.
    sales_partner = None
    
    # Erster Versuch: Über user-Feld (falls vorhanden)
    sales_partner_meta = frappe.get_meta("Sales Partner")
    if sales_partner_meta.has_field("user"):
        sales_partner = frappe.db.get_value("Sales Partner", {"user": user}, "name")
    
    # Zweiter Versuch: Direkte Namenssuche (User = Sales Partner Name)
    if not sales_partner:
        # Hole den vollständigen Namen des Benutzers
        user_full_name = frappe.db.get_value("User", user, "full_name")
        if user_full_name:
            # Suche Sales Partner mit gleichem Namen
            sales_partner = frappe.db.get_value("Sales Partner", {"partner_name": user_full_name}, "name")
            
        # Falls kein full_name gefunden, versuche den username direkt
        if not sales_partner:
            sales_partner = frappe.db.get_value("Sales Partner", {"partner_name": user}, "name")

    # Fallback: Falls keine automatische Verknüpfung gefunden wird,
    # kann die Benutzerin im Filterdialog selbst einen Sales Partner wählen.
    if filters and filters.get("sales_partner"):
        sales_partner = filters.get("sales_partner")
    
    frappe.log_error(f"User: {user}, gefundener Sales Partner: {sales_partner}", "DEBUG: sales_partner_lookup")

    conditions = {"docstatus": 1}
    if sales_partner:
        conditions["sales_partner"] = sales_partner
    
    # Monats- und Jahresfilter anwenden
    if filters:
        month_name = filters.get("month")
        year = filters.get("year")
        
        if month_name and year:
            # Monatsnamen zu Monatsnummer konvertieren
            month_names = [
                "Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember"
            ]
            if month_name in month_names:
                month_num = month_names.index(month_name) + 1
                
                # Ersten und letzten Tag des Monats bestimmen
                first_day = f"{year}-{month_num:02d}-01"
                last_day_num = calendar.monthrange(int(year), month_num)[1]
                last_day = f"{year}-{month_num:02d}-{last_day_num:02d}"
                
                conditions["posting_date"] = ["between", [first_day, last_day]]

    # Prüfe, ob die Felder existieren
    invoice_meta = frappe.get_meta("Sales Invoice")
    has_comm_rate = invoice_meta.has_field("commission_rate")
    has_comm_amount = invoice_meta.has_field("commission_amount")

    field_list = [
        "name as sales_invoice",
        "posting_date",
        "customer_name",
        "grand_total",
        "status",
    ]
    if has_comm_rate:
        field_list.append("commission_rate")
    if has_comm_amount:
        field_list.append("commission_amount")

    # Erweiterte SQL-Abfrage für bessere Daten
    sql_query = """
        SELECT
            si.posting_date,
            si.name,
            c.customer_name,
            si.base_net_total,
            COALESCE(sp.commission_rate, 20) as commission_rate,
            (si.base_net_total * (COALESCE(sp.commission_rate, 20) / 100)) as provision
        FROM `tabSales Invoice` si
        LEFT JOIN `tabCustomer` c ON si.customer = c.name
        LEFT JOIN `tabSales Partner` sp ON si.sales_partner = sp.name
        WHERE si.docstatus = 1
    """
    
    # Filter hinzufügen
    sql_conditions = []
    sql_values = {}
    
    if sales_partner:
        sql_conditions.append("si.sales_partner = %(sales_partner)s")
        sql_values["sales_partner"] = sales_partner
    else:
        # Falls kein Sales Partner gefunden wurde, aber "only if creator" aktiv ist,
        # zusätzlich nach owner filtern
        sql_conditions.append("si.owner = %(current_user)s")
        sql_values["current_user"] = user
    
    if filters.get("month") and filters.get("year"):
        month_name = filters.get("month")
        year = filters.get("year")
        
        if month_name:
            month_names = [
                "Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember"
            ]
            if month_name in month_names:
                month_num = month_names.index(month_name) + 1
                
                first_day = f"{year}-{month_num:02d}-01"
                last_day_num = calendar.monthrange(int(year), month_num)[1]
                last_day = f"{year}-{month_num:02d}-{last_day_num:02d}"
                
                sql_conditions.append("si.posting_date BETWEEN %(first_day)s AND %(last_day)s")
                sql_values["first_day"] = first_day
                sql_values["last_day"] = last_day
    
    if sql_conditions:
        sql_query += " AND " + " AND ".join(sql_conditions)
    
    sql_query += " ORDER BY si.posting_date DESC"
    
    invoices = frappe.db.sql(sql_query, sql_values, as_dict=True)

    data = []
    for inv in invoices:
        data.append([
            inv.posting_date,
            inv.name,
            inv.customer_name,
            flt(inv.base_net_total),
            flt(inv.provision),
        ])

    columns = [
        {
            "fieldname": "posting_date",
            "label": _("Datum"),
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "sales_invoice",
            "label": _("Rechnung"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 230,
        },
        {
            "fieldname": "customer_name",
            "label": _("Kundenname"),
            "fieldtype": "Data",
            "width": 350,
        },
        {
            "fieldname": "base_net_total",
            "label": _("Betrag"),
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "provision",
            "label": _("Provision"),
            "fieldtype": "Currency",
            "width": 120,
        },
    ]

    # Entferne eventuelle None-Einträge (falls bestimmte Felder fehlen)
    columns = [c for c in columns if c]
    
    # Gesamtsumme der Provisionen berechnen (optional für Anzeige am Ende)
    total_commission = sum(row[4] for row in data)  # Spalte 4 = provision
    if data and filters and filters.get("month"):
        # Zusätzliche Info-Zeile mit Gesamtsumme hinzufügen
        data.append([
            "",  # Datum
            "GESAMT",  # Rechnung
            f"Provision {filters.get('month')} {filters.get('year', '')}",  # Kundenname
            "",  # Betrag
            total_commission,  # Provision
        ])

    return columns, data
