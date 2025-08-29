# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ENJOAktionseinstellungen(Document):
	pass


@frappe.whitelist()
def get_aktionseinstellungen():
	"""Schwellwerte + dynamische S/P-Varianten liefern (S1..S5, P1..P5; je .1.. .6)."""
	settings = frappe.get_single("ENJO Aktionseinstellungen")

	def collect(prefix: str):
		result = []
		for grp in range(1, 6):
			for pos in range(1, 7):
				code = getattr(settings, f"{prefix}{grp}_{pos}_code", None) or ""
				name = getattr(settings, f"{prefix}{grp}_{pos}_name", None) or ""
				if code or name:
					result.append({"code": code, "name": name or code})
		return result

	return {
		"stage_1_minimum": float(getattr(settings, "stage_1_minimum", 0) or 0),
		"stage_1_maximum": float(getattr(settings, "stage_1_maximum", 0) or 0),
		"variants": {
			"standard": collect("s"),
			"premium": collect("p")
		}
	}