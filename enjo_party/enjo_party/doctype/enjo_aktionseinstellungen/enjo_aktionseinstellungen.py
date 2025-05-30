# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ENJOAktionseinstellungen(Document):
	pass


@frappe.whitelist()
def get_aktionseinstellungen():
	"""Hilfsfunktion um die aktuellen Aktionseinstellungen zu laden."""
	settings = frappe.get_single("ENJO Aktionseinstellungen")
	
	# Falls noch keine Einstellungen existieren, Defaults zurückgeben
	if not settings:
		return {
			"stage_1_minimum": 99,
			"stage_1_maximum": 199,
			"v1_code": "50238-Aktion",
			"v1_name": "V1: Duo-Ministar",
			"v2_code": "52004-Aktion", 
			"v2_name": "V2: Lavendelbl. Waschmittel",
			"v3_code": "50320-Aktion",
			"v3_name": "V3: ENJOfil Wohnen",
			"v4_code": "15312a-Aktion",
			"v4_name": "V4: Multi-Tool Platte & Faser Stark",
			"v5_code": "15313-Aktion",
			"v5_name": "V5: Duo-Ministar & Lavendelbl.",
			"v6_code": "15308-Aktion",
			"v6_name": "V6: Duo-Ministar & ENJOfil",
			"v7_code": "15312b-Aktion",
			"v7_name": "V7: Multi-Tool Platte & Faser Stark"
		}
	
	return {
		"stage_1_minimum": settings.stage_1_minimum or 99,
		"stage_1_maximum": settings.stage_1_maximum or 199,
		"v1_code": settings.v1_code or "50238-Aktion",
		"v1_name": settings.v1_name or "V1: Duo-Ministar",
		"v2_code": settings.v2_code or "52004-Aktion",
		"v2_name": settings.v2_name or "V2: Lavendelbl. Waschmittel",
		"v3_code": settings.v3_code or "50320-Aktion",
		"v3_name": settings.v3_name or "V3: ENJOfil Wohnen",
		"v4_code": settings.v4_code or "15312a-Aktion",
		"v4_name": settings.v4_name or "V4: Multi-Tool Platte & Faser Stark",
		"v5_code": settings.v5_code or "15313-Aktion",
		"v5_name": settings.v5_name or "V5: Duo-Ministar & Lavendelbl.",
		"v6_code": settings.v6_code or "15308-Aktion",
		"v6_name": settings.v6_name or "V6: Duo-Ministar & ENJOfil",
		"v7_code": settings.v7_code or "15312b-Aktion",
		"v7_name": settings.v7_name or "V7: Multi-Tool Platte & Faser Stark"
	} 