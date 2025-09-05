# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ENJOAktionseinstellungen(Document):
	def validate(self):
		# Zeitraum 1: Von/Bis valide
		p1_from = getattr(self, "period_1_from", None)
		p1_to = getattr(self, "period_1_to", None)
		if p1_from and p1_to and p1_from > p1_to:
			frappe.throw("Zeitraum 1: 'Von' darf nicht nach 'Bis' liegen.")

		# Zeitraum 2: Von/Bis valide
		p2_from = getattr(self, "period_2_from", None)
		p2_to = getattr(self, "period_2_to", None)
		if p2_from and p2_to and p2_from > p2_to:
			frappe.throw("Zeitraum 2: 'Von' darf nicht nach 'Bis' liegen.")

		# Überschneidung verhindern (nur prüfen, wenn beide gesetzt)
		if p1_from and p1_to and p2_from and p2_to:
			# kein overlap: p1_to < p2_from oder p2_to < p1_from
			if not (p1_to < p2_from or p2_to < p1_from):
				frappe.throw("Zeitraum 1 und 2 dürfen sich nicht überschneiden.")


@frappe.whitelist()
def get_aktionseinstellungen():
	"""Schwellwerte + dynamische S/P-Varianten liefern (aktive Periode)."""
	settings = frappe.get_single("ENJO Aktionseinstellungen")

	# Aktive Periode anhand heutigem Datum bestimmen
	today = frappe.utils.getdate()
	p1_from = getattr(settings, "period_1_from", None)
	p1_to = getattr(settings, "period_1_to", None)
	p2_from = getattr(settings, "period_2_from", None)
	p2_to = getattr(settings, "period_2_to", None)

	def is_active(p_from, p_to):
		if not p_from or not p_to:
			return False
		# Konvertiere String-Datumsangaben zu datetime.date
		if isinstance(p_from, str):
			p_from = frappe.utils.getdate(p_from)
		if isinstance(p_to, str):
			p_to = frappe.utils.getdate(p_to)
		return p_from <= today <= p_to

	active_period = 1 if is_active(p1_from, p1_to) else (2 if is_active(p2_from, p2_to) else None)

	def collect(prefix: str):
		result = []
		for grp in range(1, 6):
			# Prüfe erst, ob die Hauptkategorie (Position 1) ausgefüllt ist
			main_code = getattr(settings, f"{prefix}{grp}_1_code", None) or ""
			main_name = getattr(settings, f"{prefix}{grp}_1_name", None) or ""
			
			# Nur wenn Hauptkategorie ausgefüllt ist, sammle alle Positionen dieser Gruppe
			if main_code or main_name:
				for pos in range(1, 7):
					code = getattr(settings, f"{prefix}{grp}_{pos}_code", None) or ""
					name = getattr(settings, f"{prefix}{grp}_{pos}_name", None) or ""
					if code or name:
						result.append({"code": code, "name": name or code})
		return result

	def collect_z2(prefix: str):
		result = []
		for grp in range(1, 6):
			# Prüfe erst, ob die Hauptkategorie (Position 1) ausgefüllt ist
			main_code = getattr(settings, f"z2_{prefix}{grp}_1_code", None) or ""
			main_name = getattr(settings, f"z2_{prefix}{grp}_1_name", None) or ""
			
			# Nur wenn Hauptkategorie ausgefüllt ist, sammle alle Positionen dieser Gruppe
			if main_code or main_name:
				for pos in range(1, 7):
					code = getattr(settings, f"z2_{prefix}{grp}_{pos}_code", None) or ""
					name = getattr(settings, f"z2_{prefix}{grp}_{pos}_name", None) or ""
					if code or name:
						result.append({"code": code, "name": name or code})
		return result

	if active_period == 2:
		stage_min = float(getattr(settings, "stage_1_minimum_z2", 0) or 0)
		stage_max = float(getattr(settings, "stage_1_maximum_z2", 0) or 0)
		std = collect_z2("s")
		pre = collect_z2("p")
	else:
		stage_min = float(getattr(settings, "stage_1_minimum", 0) or 0)
		stage_max = float(getattr(settings, "stage_1_maximum", 0) or 0)
		std = collect("s")
		pre = collect("p")

	return {
		"active_period": active_period,
		"stage_1_minimum": stage_min,
		"stage_1_maximum": stage_max,
		"variants": {"standard": std, "premium": pre}
	}