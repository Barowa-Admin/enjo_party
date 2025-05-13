# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class Party(Document):
	def before_save(self):
		# Wenn es ein neues Dokument ist, wird der Name erst nach dem Speichern generiert
		if self.is_new():
			# Setze party_name auf None, wird nach dem Einfügen gesetzt
			self.party_name = None

	def after_insert(self):
		# Nach dem Einfügen den party_name auf den generierten Namen setzen
		self.db_set("party_name", self.name, update_modified=False)
		
	def validate(self):
		# Stelle sicher, dass UOM Conversion Factor in allen Produkttabellen gesetzt ist
		self.set_uom_conversion_factor()
	
	def set_uom_conversion_factor(self):
		# Für alle Produktauswahl-Tabellen
		for i in range(1, 16):  # 1 bis 15
			field_name = f"produktauswahl_für_gast_{i}"
			if hasattr(self, field_name) and getattr(self, field_name):
				table = getattr(self, field_name)
				for item in table:
					if item.item_code:
						# Immer explizit den UOM Conversion Factor setzen
						item.uom = item.uom or "Nos"
						item.uom_conversion_factor = 1
						
						# Falls Item Name fehlt
						if not item.item_name:
							item_data = frappe.db.get_value("Item", item.item_code, "item_name")
							item.item_name = item_data or item.item_code
		
		# Auch für die Gastgeberin-Tabelle den UOM Conversion Factor setzen
		if hasattr(self, "produktauswahl_für_gastgeberin") and self.produktauswahl_für_gastgeberin:
			for item in self.produktauswahl_für_gastgeberin:
				if item.item_code:
					# Immer explizit den UOM Conversion Factor setzen
					item.uom = item.uom or "Nos"
					item.uom_conversion_factor = 1
					
					# Falls Item Name fehlt
					if not item.item_name:
						item_data = frappe.db.get_value("Item", item.item_code, "item_name")
						item.item_name = item_data or item.item_code

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
	
	# Kunden hinzufügen
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
		shipping_groups[ship_to].append({"kunde": kunde.kunde, "type": "gast", "index": index})
	
	# Gastgeberin hinzufügen (wenn sie auch Produkte hat)
	if hasattr(party_doc, "produktauswahl_für_gastgeberin") and party_doc.produktauswahl_für_gastgeberin:
		if any(p.item_code and p.qty for p in party_doc.produktauswahl_für_gastgeberin):
			versand_zu = party_doc.versand_gastgeberin if hasattr(party_doc, "versand_gastgeberin") else None
			ship_to = versand_zu or party_doc.gastgeberin
			
			if ship_to not in shipping_groups:
				shipping_groups[ship_to] = []
			shipping_groups[ship_to].append({"kunde": party_doc.gastgeberin, "type": "gastgeberin"})
	
	# Versandkosten pro Gruppe berechnen
	FREE_SHIPPING_THRESHOLD = 199.0
	SHIPPING_COST = 7.0
	
	for ship_to, customers in shipping_groups.items():
		# Berechne Gesamtsumme für die Versandgruppe (vorübergehend, wird später genauer berechnet)
		# Hier müssten wir eigentlich die tatsächlichen Bestellsummen addieren
		total_group_amount = 0  # Wird später genauer berechnet
		
		# Versandkosten für die Gruppe festlegen
		is_free_shipping = total_group_amount >= FREE_SHIPPING_THRESHOLD
		shipping_per_customer = 0 if is_free_shipping else SHIPPING_COST / len(customers)
		
		# Für jeden Kunden in der Gruppe Rechnung erstellen
		for customer_info in customers:
			# Bestellungen für diesen Kunden zusammenstellen
			items = []
			customer_type = customer_info["type"]
			customer_name = customer_info["kunde"]
			
			# Produktauswahl-Tabelle für diesen Kunden finden
			if customer_type == "gast":
				gast_idx = customer_info["index"]
				produktauswahl_field = f"produktauswahl_für_gast_{gast_idx}"
			else:  # Gastgeberin
				produktauswahl_field = "produktauswahl_für_gastgeberin"
			
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
			is_gastgeber = customer_name == party_doc.gastgeberin
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
					"customer": customer_name,
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
				frappe.log_error(f"Fehler beim Erstellen der Rechnung für {customer_name}: {str(e)}")
				frappe.db.rollback()
				continue
	
	# Wenn mindestens eine Rechnung erstellt wurde, Party-Status aktualisieren
	if created_invoices:
		party_doc.status = "Abgeschlossen"
		party_doc.save()
	
	return created_invoices
