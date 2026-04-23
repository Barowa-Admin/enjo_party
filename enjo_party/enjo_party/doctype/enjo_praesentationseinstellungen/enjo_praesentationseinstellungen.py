# Copyright (c) 2026, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

# Fallback wenn Kindtabelle leer (bisheriges Verhalten)
DEFAULT_GUTSCHEIN_STUFEN = (
	(0, 0),
	(350, 30),
	(600, 60),
	(850, 95),
	(1100, 130),
)


class ENJOPraesentationseinstellungen(Document):
	pass


def get_gutschein_stufen_tuples():
	"""Sortierte Liste (mindest_umsatz, gutschein_betrag). Leer → DEFAULT."""
	settings = frappe.get_single("ENJO Praesentationseinstellungen")
	rows = []
	for row in settings.stufen or []:
		rows.append((flt(row.mindest_umsatz), flt(row.gutschein_betrag)))
	if not rows:
		return list(DEFAULT_GUTSCHEIN_STUFEN)
	rows.sort(key=lambda x: x[0])
	return rows


def calculate_gutschein_value_from_stufen(total_amount, stufen=None):
	total_amount = flt(total_amount)
	if stufen is None:
		stufen = get_gutschein_stufen_tuples()
	gutschein_wert = 0.0
	for mindest_umsatz, gutschein_betrag in stufen:
		if total_amount >= mindest_umsatz:
			gutschein_wert = gutschein_betrag
		else:
			break
	return gutschein_wert


@frappe.whitelist()
def get_praesentationseinstellungen():
	stufen = get_gutschein_stufen_tuples()
	return {
		"stufen": [
			{"mindest_umsatz": s[0], "gutschein_betrag": s[1]}
			for s in stufen
		],
	}
