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
		
		# Status automatisch setzen
		self.set_status()

	def after_insert(self):
		# Nach dem Einfügen den party_name auf den generierten Namen setzen
		self.db_set("party_name", self.name, update_modified=False)
		
	def validate(self):
		# Stelle sicher, dass UOM Conversion Factor in allen Produkttabellen gesetzt ist
		self.set_uom_conversion_factor()
		
		# Prüfe, dass die Gastgeberin nicht auch als Gast in der Kundenliste steht
		self.validate_gastgeberin_not_in_kunden()
	
	def validate_gastgeberin_not_in_kunden(self):
		if not self.gastgeberin or not self.kunden:
			return
			
		# Entferne Gastgeberin aus der Kundenliste, falls sie dort vorkommt
		kunden_to_remove = []
		for i, kunde in enumerate(self.kunden):
			if kunde.kunde == self.gastgeberin:
				kunden_to_remove.append(i)
		
		# Lösche von hinten nach vorne, um Indexproblem zu vermeiden
		for index in sorted(kunden_to_remove, reverse=True):
			self.kunden.pop(index)
		
		# Wenn Elemente entfernt wurden, eine Benachrichtigung anzeigen
		if kunden_to_remove:
			frappe.msgprint(
				f"Die Gastgeberin '{self.gastgeberin}' wurde automatisch aus der Gästeliste entfernt, "
				"da sie nicht gleichzeitig Gastgeberin und Gast sein kann.",
				alert=True
			)
	
	def set_status(self):
		# Wenn wir bereits abgeschlossen sind, nicht mehr ändern
		if self.status == "Abgeschlossen":
			return
			
		# Prüfen, ob Produkte vorhanden sind
		has_products = False
		
		# Für alle Produktauswahl-Tabellen prüfen
		for i in range(1, 16):  # 1 bis 15
			field_name = f"produktauswahl_für_gast_{i}"
			if hasattr(self, field_name) and getattr(self, field_name):
				table = getattr(self, field_name)
				if any(item.item_code and item.qty for item in table):
					has_products = True
					break
		
		# Auch Gastgeberin-Tabelle prüfen
		if not has_products and hasattr(self, "produktauswahl_für_gastgeberin") and self.produktauswahl_für_gastgeberin:
			if any(item.item_code and item.qty for item in self.produktauswahl_für_gastgeberin):
				has_products = True
		
		# Status setzen basierend auf dem Vorhandensein von Produkten
		if has_products:
			self.status = "Produkte"
		else:
			self.status = "Gäste"
	
	def set_uom_conversion_factor(self):
		# Für alle Produktauswahl-Tabellen
		for i in range(1, 16):  # 1 bis 15
			field_name = f"produktauswahl_für_gast_{i}"
			if hasattr(self, field_name) and getattr(self, field_name):
				table = getattr(self, field_name)
				for item in table:
					if item.item_code:
						# Standard-UOM und Item-Daten vom Item abfragen
						item_doc = frappe.get_cached_doc("Item", item.item_code)
						
						# Immer explizit den UOM und UOM Conversion Factor setzen
						item.uom = item.uom or item_doc.stock_uom or "Nos"
						item.stock_uom = item_doc.stock_uom
						item.uom_conversion_factor = 1.0
						
						# Falls Item Name fehlt
						if not item.item_name:
							item.item_name = item_doc.item_name or item.item_code
						
						# Weitere erforderliche Standardfelder für Sales Order Item setzen
						if not item.conversion_factor:
							item.conversion_factor = 1.0
						if not item.stock_qty:
							item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
		
		# Auch für die Gastgeberin-Tabelle den UOM Conversion Factor setzen
		if hasattr(self, "produktauswahl_für_gastgeberin") and self.produktauswahl_für_gastgeberin:
			for item in self.produktauswahl_für_gastgeberin:
				if item.item_code:
					# Standard-UOM und Item-Daten vom Item abfragen
					item_doc = frappe.get_cached_doc("Item", item.item_code)
					
					# Immer explizit den UOM und UOM Conversion Factor setzen
					item.uom = item.uom or item_doc.stock_uom or "Nos"
					item.stock_uom = item_doc.stock_uom
					item.uom_conversion_factor = 1.0
					
					# Falls Item Name fehlt
					if not item.item_name:
						item.item_name = item_doc.item_name or item.item_code
					
					# Weitere erforderliche Standardfelder für Sales Order Item setzen
					if not item.conversion_factor:
						item.conversion_factor = 1.0
					if not item.stock_qty:
						item.stock_qty = flt(item.qty) * flt(item.conversion_factor)

# Funktion zum Erstellen oder Finden einer Adresse für einen Kunden
def get_or_create_address(customer_name, address_type="Billing"):
	# Prüfen, ob bereits eine Adresse für diesen Kunden existiert
	address_links = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Customer", "link_name": customer_name},
		fields=["parent"]
	)
	
	existing_addresses = []
	for link in address_links:
		addr = frappe.get_doc("Address", link.parent)
		if addr.address_type == address_type:
			return addr.name
		existing_addresses.append(addr.name)
	
	# Wenn keine Adresse gefunden wurde, erstelle eine neue
	if not existing_addresses:
		# Erstelle eine neue Adresse für den Kunden
		new_address = frappe.get_doc({
			"doctype": "Address",
			"address_title": f"{customer_name}-{address_type}",
			"address_type": address_type,
			"address_line1": customer_name,  # Als Platzhalter den Kundennamen verwenden
			"city": "Stadt",  # Platzhalter
			"country": "Deutschland",  # Standardwert
			"links": [{"link_doctype": "Customer", "link_name": customer_name}]
		})
		new_address.insert(ignore_permissions=True)
		return new_address.name
	
	# Falls es Adressen gibt, aber keine vom gesuchten Typ, verwende die erste
	return existing_addresses[0]

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
	
	# Stelle sicher, dass für die Gastgeberin eine Adresse existiert
	gastgeberin_address = get_or_create_address(party_doc.gastgeberin, "Shipping")
	
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
		
		# Stelle sicher, dass der Kunde eine Adresse hat
		if not versand_zu:  # Wenn der Kunde seine eigene Adresse verwendet
			get_or_create_address(kunde.kunde, "Shipping")
		
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
	
	# Berechne Einzelbeträge der Bestellungen für Versandpreise
	bestellungsbeträge = {}
	
	# Für Kunden
	for idx, kunde in enumerate(party_doc.kunden or []):
		index = idx + 1
		produktauswahl_field = f"produktauswahl_für_gast_{index}"
		
		if hasattr(party_doc, produktauswahl_field) and getattr(party_doc, produktauswahl_field):
			produkte = getattr(party_doc, produktauswahl_field)
			summe = 0
			
			for produkt in produkte:
				if produkt.item_code and produkt.qty:
					summe += flt(produkt.qty) * flt(produkt.rate or 0)
			
			bestellungsbeträge[kunde.kunde] = summe
	
	# Für Gastgeberin
	if hasattr(party_doc, "produktauswahl_für_gastgeberin") and party_doc.produktauswahl_für_gastgeberin:
		summe = 0
		for produkt in party_doc.produktauswahl_für_gastgeberin:
			if produkt.item_code and produkt.qty:
				summe += flt(produkt.qty) * flt(produkt.rate or 0)
		
		bestellungsbeträge[party_doc.gastgeberin] = summe
	
	# Versandkosten pro Gruppe berechnen
	FREE_SHIPPING_THRESHOLD = 199.0
	SHIPPING_COST = 7.0
	
	for ship_to, customers in shipping_groups.items():
		# Berechne Gesamtsumme für die Versandgruppe
		total_group_amount = 0
		for customer_info in customers:
			customer_name = customer_info["kunde"]
			total_group_amount += bestellungsbeträge.get(customer_name, 0)
		
		# Versandkosten für die Gruppe festlegen
		is_free_shipping = total_group_amount >= FREE_SHIPPING_THRESHOLD
		
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
			
			# Versandkosten als Notiz in der Beschreibung hinzufügen statt als eigenes Item
			shipping_note = ""
			if not is_free_shipping:
				shipping_cost_per_customer = SHIPPING_COST / len(customers)
				shipping_note = f"Inkl. Versandkosten: {shipping_cost_per_customer:.2f} EUR"
			
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
				# Stelle sicher, dass wir eine gültige Versandadresse für diesen Kunden haben
				billing_address = get_or_create_address(customer_name, "Billing")
				shipping_address = None
				
				if ship_to == customer_name:
					# Der Kunde erhält an seine eigene Adresse
					shipping_address = get_or_create_address(customer_name, "Shipping")
				else:
					# Der Kunde erhält an die Adresse eines anderen Kunden
					# (vermutlich der Gastgeberin)
					shipping_address = get_or_create_address(ship_to, "Shipping")
				
				# Rechnungsdaten zusammenstellen
				invoice_data = {
					"doctype": "Sales Invoice",
					"customer": customer_name,
					"party_reference": party_doc.name,  # Custom Feld zur Verknüpfung mit Party
					"posting_date": today(),
					"items": items,
					"customer_address": billing_address,  # Rechnungsadresse
					"shipping_address_name": shipping_address,  # Versandziel für die Rechnung
					"party_gastgeberin": party_doc.gastgeberin,
					"party_partnerin": party_doc.partnerin
				}
				
				# Versandhinweis als Notiz hinzufügen, wenn vorhanden
				if shipping_note:
					invoice_data["terms"] = shipping_note
				
				# Rechnung erstellen
				invoice = frappe.get_doc(invoice_data)
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
		# Status auf "Abgeschlossen" setzen
		party_doc.status = "Abgeschlossen"
		party_doc.save()
		
		# Party-Dokument abschließen/einreichen (submit)
		party_doc.submit()
	
	return created_invoices
