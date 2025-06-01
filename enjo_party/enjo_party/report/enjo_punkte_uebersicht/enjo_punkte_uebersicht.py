# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	"""Definiert die Spalten für den Report"""
	return [
		{
			"fieldname": "sales_partner",
			"label": _("Vertriebspartnerin"),
			"fieldtype": "Link",
			"options": "Sales Partner",
			"width": 200
		},
		{
			"fieldname": "partner_name",
			"label": _("Name"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "total_points",
			"label": _("Punkte Gesamt"),
			"fieldtype": "Int",
			"width": 120
		},
		{
			"fieldname": "transaction_count",
			"label": _("Anzahl Transaktionen"),
			"fieldtype": "Int",
			"width": 150
		},
		{
			"fieldname": "last_transaction",
			"label": _("Letzte Aktivität"),
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "last_invoice",
			"label": _("Letzte Rechnung"),
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 150
		}
	]


def get_data(filters):
	"""Holt die Daten für den Report"""
	conditions = get_conditions(filters)
	
	# SQL Query um Punkte pro Sales Partner zu aggregieren
	query = f"""
		SELECT 
			t.sales_partner,
			sp.partner_name,
			SUM(CASE WHEN t.is_cancelled = 0 THEN t.punkte_gesamt ELSE 0 END) as total_points,
			COUNT(CASE WHEN t.is_cancelled = 0 THEN 1 ELSE NULL END) as transaction_count,
			MAX(CASE WHEN t.is_cancelled = 0 THEN t.transaction_date ELSE NULL END) as last_transaction,
			(
				SELECT t2.sales_invoice 
				FROM `tabENJO Punkte Transaktion` t2 
				WHERE t2.sales_partner = t.sales_partner 
				AND t2.is_cancelled = 0 
				ORDER BY t2.transaction_date DESC 
				LIMIT 1
			) as last_invoice
		FROM `tabENJO Punkte Transaktion` t
		LEFT JOIN `tabSales Partner` sp ON t.sales_partner = sp.name
		WHERE 1=1 {conditions}
		GROUP BY t.sales_partner, sp.partner_name
		HAVING total_points > 0
		ORDER BY total_points DESC, sp.partner_name ASC
	"""
	
	data = frappe.db.sql(query, filters, as_dict=True)
	
	# Falls keine Daten vorhanden sind, zeige eine Info-Zeile
	if not data:
		return [{
			"sales_partner": "",
			"partner_name": "Keine ENJO Punkte Transaktionen gefunden",
			"total_points": 0,
			"transaction_count": 0,
			"last_transaction": None,
			"last_invoice": ""
		}]
	
	return data


def get_conditions(filters):
	"""Erstellt WHERE-Bedingungen basierend auf den Filtern"""
	conditions = ""
	
	if filters.get("sales_partner"):
		conditions += " AND t.sales_partner = %(sales_partner)s"
	
	if filters.get("from_date"):
		conditions += " AND t.transaction_date >= %(from_date)s"
		
	if filters.get("to_date"):
		conditions += " AND t.transaction_date <= %(to_date)s"
	
	return conditions 