# ENJO Punkte Vergabe - Server Script
# Wird bei Sales Invoice Submit ausgelöst

import frappe
from frappe.utils import flt, today


def award_points_on_invoice_submit(doc, method):
	"""
	Vergibt ENJO Punkte basierend auf verkauften Produkten mit custom_punkte
	Wird bei Sales Invoice Submit ausgelöst
	"""
	try:
		frappe.log_error(f"ENJO Punkte: Verarbeite Invoice {doc.name}", "INFO: enjo_points")
		
		# Prüfe ob Sales Partner vorhanden ist
		sales_partner = doc.get("sales_partner")
		if not sales_partner:
			frappe.log_error(f"Invoice {doc.name} hat keinen Sales Partner - keine Punkte vergeben", "INFO: enjo_points")
			return
		
		# Durchlaufe alle Invoice Items
		for item_row in doc.items:
			if not item_row.item_code or not item_row.qty or item_row.qty <= 0:
				continue
				
			# Hole custom_punkte vom Item
			try:
				item_doc = frappe.get_cached_doc("Item", item_row.item_code)
				custom_punkte = getattr(item_doc, "custom_punkte", 0)
				
				if custom_punkte and custom_punkte > 0:
					# Erstelle ENJO Punkte Transaktion
					punkte_transaktion = frappe.get_doc({
						"doctype": "ENJO Punkte Transaktion",
						"sales_partner": sales_partner,
						"sales_invoice": doc.name,
						"item_code": item_row.item_code,
						"item_name": item_row.item_name or item_row.item_code,
						"qty": item_row.qty,
						"punkte_pro_item": custom_punkte,
						"transaction_date": doc.posting_date or today(),
						"is_cancelled": 0
					})
					
					punkte_transaktion.insert(ignore_permissions=True)
					
					frappe.log_error(
						f"ENJO Punkte vergeben: {sales_partner} erhält {flt(item_row.qty) * custom_punkte} Punkte für {item_row.item_code}",
						"SUCCESS: enjo_points"
					)
					
			except Exception as e:
				frappe.log_error(f"Fehler beim Verarbeiten von Item {item_row.item_code}: {str(e)}", "ERROR: enjo_points")
				continue
				
	except Exception as e:
		frappe.log_error(f"Allgemeiner Fehler bei ENJO Punkte Vergabe für Invoice {doc.name}: {str(e)}", "ERROR: enjo_points")


def cancel_points_on_invoice_cancel(doc, method):
	"""
	Storniert ENJO Punkte bei Sales Invoice Cancel
	Setzt is_cancelled = 1 für alle zugehörigen Transaktionen
	"""
	try:
		frappe.log_error(f"ENJO Punkte: Storniere Punkte für Invoice {doc.name}", "INFO: enjo_points_cancel")
		
		# Finde alle Punktetransaktionen für diese Invoice
		transactions = frappe.get_all(
			"ENJO Punkte Transaktion",
			filters={
				"sales_invoice": doc.name,
				"is_cancelled": 0
			},
			fields=["name"]
		)
		
		# Markiere alle als storniert
		for trans in transactions:
			trans_doc = frappe.get_doc("ENJO Punkte Transaktion", trans.name)
			trans_doc.is_cancelled = 1
			trans_doc.save(ignore_permissions=True)
			
		frappe.log_error(f"ENJO Punkte: {len(transactions)} Transaktionen storniert für Invoice {doc.name}", "SUCCESS: enjo_points_cancel")
		
	except Exception as e:
		frappe.log_error(f"Fehler beim Stornieren von ENJO Punkte für Invoice {doc.name}: {str(e)}", "ERROR: enjo_points_cancel") 