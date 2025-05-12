# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class Party(Document):
	pass

@frappe.whitelist()
def create_invoices(party):
	"""
	Erstellt Rechnungen für alle Teilnehmer einer Party
	"""
	# Party-Dokument laden
	party_doc = frappe.get_doc("Party", party)
	created_invoices = []
	
	# Prüfen ob die Party gültig ist
	if len(party_doc.kunden or []) < 3:
		frappe.throw("Es müssen mindestens 3 Gäste/Kunden zur Party hinzugefügt werden.")
	
	# Gruppiere Kunden nach Versandziel
	shipping_groups = {}
	for idx, kunde in enumerate(party_doc.kunden or []):
		# Versandziel bestimmen (1-basiert für die feldnamen)
		index = idx + 1
		versandziel_field = f"versand_gast_{index}"
		
		# Versandziel aus Party-Dokument holen, wenn das Feld existiert
		versand_zu = None
		if hasattr(party_doc, versandziel_field):
			versand_zu = getattr(party_doc, versandziel_field)
		
		# Fallback auf die eigene Adresse, wenn kein Versandziel angegeben
		ship_to = versand_zu or kunde.kunde
		
		# Zu Versandgruppen hinzufügen
		if ship_to not in shipping_groups:
			shipping_groups[ship_to] = []
		shipping_groups[ship_to].append(kunde)
	
	# Versandkosten pro Gruppe berechnen
	FREE_SHIPPING_THRESHOLD = 199.0
	SHIPPING_COST = 7.0
	
	for ship_to, customers in shipping_groups.items():
		# Berechne Gesamtsumme für die Versandgruppe
		total_group_amount = sum(flt(c.bestellsumme or 0) for c in customers)
		
		# Versandkosten für die Gruppe festlegen
		is_free_shipping = total_group_amount >= FREE_SHIPPING_THRESHOLD
		shipping_per_customer = 0 if is_free_shipping else SHIPPING_COST / len(customers)
		
		# Für jeden Kunden in der Gruppe Rechnung erstellen
		for kunde in customers:
			# Bestellungen für diesen Kunden zusammenstellen
			items = []
			gast_idx = None
			
			# Bestimme den Index des Kunden in der Kundenliste
			for i, k in enumerate(party_doc.kunden):
				if k.name == kunde.name:
					gast_idx = i + 1  # 1-basiert
					break
			
			# Wenn wir keinen Index gefunden haben, überspringen
			if gast_idx is None:
				continue
			
			# Produktauswahl-Tabelle für diesen Gast finden
			produktauswahl_field = f"produktauswahl_für_gast_{gast_idx}"
			
			# Prüfen ob die Tabelle existiert und befüllt ist
			if hasattr(party_doc, produktauswahl_field) and getattr(party_doc, produktauswahl_field):
				produkte = getattr(party_doc, produktauswahl_field)
				
				# Produkte zur Rechnung hinzufügen
				for produkt in produkte:
					# Nur hinzufügen, wenn Produkt und Menge angegeben sind
					if produkt.item_code and produkt.qty:
						items.append({
							"item_code": produkt.item_code,
							"qty": produkt.qty,
							"rate": produkt.rate or 0
						})
			
			# Wenn keine Produkte vorhanden sind, keine Rechnung erstellen
			if not items:
				continue
			
			# Versandkosten als eigene Position hinzufügen, wenn nicht kostenlos
			if not is_free_shipping and shipping_per_customer > 0:
				items.append({
					"item_code": "VERSAND",  # Item-Code für Versandkosten (muss im System existieren)
					"qty": 1,
					"rate": shipping_per_customer
				})
			
			# Gastgeber-Gutschein als Rabattposition, falls für Gastgeber
			is_gastgeber = kunde.kunde == party_doc.gastgeberin
			gutschein_wert = flt(party_doc.gastgeber_gutschein_wert or 0)
			
			if is_gastgeber and gutschein_wert > 0:
				items.append({
					"item_code": "GUTSCHEIN",  # Item-Code für Gutschein (muss im System existieren)
					"qty": 1,
					"rate": -gutschein_wert  # Negativ für Rabatt
				})
			
			# Rechnung erstellen
			try:
				invoice = frappe.get_doc({
					"doctype": "Sales Invoice",
					"customer": kunde.kunde,
					"party_reference": party_doc.name,  # Custom Feld zur Verknüpfung mit Party
					"posting_date": today(),
					"items": items,
					"shipping_address_name": ship_to,  # Versandziel für die Rechnung
					"party_gastgeberin": party_doc.gastgeberin,
					"party_partnerin": party_doc.partnerin
				})
				
				# Rechnung speichern (als Entwurf)
				invoice.insert()
				
				# Zur Liste der erstellten Rechnungen hinzufügen
				created_invoices.append(invoice.name)
				
				frappe.db.commit()
				
			except Exception as e:
				frappe.log_error(f"Fehler beim Erstellen der Rechnung für {kunde.kunde}: {str(e)}")
				frappe.db.rollback()
				continue
	
	# Wenn mindestens eine Rechnung erstellt wurde, Party-Status aktualisieren
	if created_invoices:
		party_doc.status = "Abgeschlossen"
		party_doc.save()
	
	return created_invoices
