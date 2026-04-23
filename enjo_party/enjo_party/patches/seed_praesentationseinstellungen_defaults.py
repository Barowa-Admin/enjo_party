import frappe

from enjo_party.enjo_party.doctype.enjo_praesentationseinstellungen.enjo_praesentationseinstellungen import (
	DEFAULT_GUTSCHEIN_STUFEN,
)


def execute():
	if not frappe.db.exists("DocType", "ENJO Praesentationseinstellungen"):
		return
	doc = frappe.get_single("ENJO Praesentationseinstellungen")
	if doc.stufen:
		return
	for min_u, gut in DEFAULT_GUTSCHEIN_STUFEN:
		doc.append("stufen", {"mindest_umsatz": min_u, "gutschein_betrag": gut})
	doc.save(ignore_permissions=True)
