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
		frappe.log_error(f"=== VALIDATE START für {self.name} - skip_flag: {getattr(self, 'skip_total_calculation', False)} ===", "DEBUG: validate_start")
		
		# NEUE LOGIK: Prüfe globalen Flag über frappe.local.flags
		# Dieser wird durch JavaScript-Speichern NICHT überschrieben
		skip_calculation = getattr(self, 'skip_total_calculation', False) or frappe.local.flags.get('skip_party_total_calculation', False)
		frappe.log_error(f"=== ERWEITERTE PRÜFUNG für {self.name} - dokument_flag: {getattr(self, 'skip_total_calculation', False)}, global_flag: {frappe.local.flags.get('skip_party_total_calculation', False)}, final_skip: {skip_calculation} ===", "DEBUG: validate_flags")
		
		# Stelle sicher, dass UOM Conversion Factor in allen Produkttabellen gesetzt ist
		frappe.log_error("Starte set_uom_conversion_factor", "DEBUG: validate_step")
		self.set_uom_conversion_factor()
		frappe.log_error("set_uom_conversion_factor abgeschlossen", "DEBUG: validate_step")
		
		# Berechne Gesamtumsatz und Gutscheinwert NUR wenn nicht in Aufträge-Erstellung
		# (Schutz für Gutschrift-reduzierte Preise)
		if not skip_calculation:
			frappe.log_error("Starte calculate_totals", "DEBUG: validate_step")
			self.calculate_totals()
			frappe.log_error("calculate_totals abgeschlossen", "DEBUG: validate_step")
		else:
			frappe.log_error("calculate_totals übersprungen (skip_flag gesetzt)", "DEBUG: validate_step")
		
		# Prüfe, dass die Gastgeberin nicht auch als Gast in der Kundenliste steht
		frappe.log_error("Starte validate_gastgeberin_not_in_kunden", "DEBUG: validate_step")
		self.validate_gastgeberin_not_in_kunden()
		frappe.log_error("validate_gastgeberin_not_in_kunden abgeschlossen", "DEBUG: validate_step")
		
		# NEUE ADRESSVALIDIERUNG: Prüfe alle Adressen VOR der Produktvalidierung
		# ABER NUR wenn nicht in Aufträge-Erstellung (skip_total_calculation Flag)
		if not skip_calculation:
			frappe.log_error("Starte validate_all_addresses", "DEBUG: validate_step")
			self.validate_all_addresses()
			frappe.log_error("validate_all_addresses abgeschlossen", "DEBUG: validate_step")
		else:
			frappe.log_error("validate_all_addresses übersprungen (skip_flag gesetzt)", "DEBUG: validate_step")
		
		# Prüfe, dass alle Gäste Produkte ausgewählt haben (nur wenn nicht neu UND nicht in Aufträge-Erstellung)
		# (Schutz für Aktionsartikel während der Aufträge-Erstellung)
		if not self.is_new() and not skip_calculation:
			frappe.log_error("Starte validate_all_guests_have_products", "DEBUG: validate_step")
			self.validate_all_guests_have_products()
			frappe.log_error("validate_all_guests_have_products abgeschlossen", "DEBUG: validate_step")
		else:
			frappe.log_error("validate_all_guests_have_products übersprungen (neu oder skip_flag gesetzt)", "DEBUG: validate_step")
		
		frappe.log_error(f"=== VALIDATE ENDE für {self.name} ===", "DEBUG: validate_end")
	
	def before_submit(self):
		"""
		Vor dem Einreichen der Party automatisch Aufträge erstellen,
		falls noch keine existieren
		"""
		# Prüfen, ob bereits Aufträge zu dieser Party existieren
		existing_orders = frappe.get_all(
			"Sales Order",
			filters={"docstatus": ["!=", 2]},
			or_filters=[
				{"po_no": self.name},  # Versuche, in verschiedenen Feldern zu suchen
				{"customer_name": self.name}
			],
			limit=1
		)
		
		# Wenn bereits Aufträge existieren, keinen neuen erstellen
		if existing_orders:
			frappe.log_error(f"Party {self.name}: Bestehende Aufträge gefunden: {existing_orders}", "INFO: before_submit")
			return
			
		# Aufträge erstellen beim Submit - aber ohne weitere Fehlerbehandlung
		try:
			orders = create_invoices(self.name, from_submit=True)
			if not orders:
				frappe.throw(
					"Es konnten keine Aufträge erstellt werden. "
					"Bitte prüfe, ob Produkte ausgewählt wurden und versuche es erneut."
				)
			
		except Exception as e:
			frappe.throw(str(e))  # Fehlermeldung einfach weiterreichen, ohne weitere Verarbeitung
	
	def validate_gastgeberin_not_in_kunden(self):
		if not self.gastgeberin or not self.kunden:
			return
		
		# Entferne Gastgeberin aus der Kundenliste, falls sie dort vorkommt
		kunden_to_remove = []
		for i, kunde in enumerate(self.kunden):
			if kunde.kunde == self.gastgeberin:
				kunden_to_remove.append(i)
		
		# Prüfe auf doppelte Gäste (gleicher Kunde mehrfach)
		gesehene_kunden = set()
		duplicate_indexes = []
		for i, kunde in enumerate(self.kunden):
			if kunde.kunde:
				if kunde.kunde in gesehene_kunden:
					duplicate_indexes.append(i)
				else:
					gesehene_kunden.add(kunde.kunde)
		
		# Lösche von hinten nach vorne, um Indexproblem zu vermeiden
		for index in sorted(set(kunden_to_remove + duplicate_indexes), reverse=True):
			self.kunden.pop(index)
		
		# Wenn Elemente entfernt wurden, eine Benachrichtigung anzeigen
		if kunden_to_remove or duplicate_indexes:
			msg = []
			if kunden_to_remove:
				msg.append(f"Die Gastgeberin '{self.gastgeberin}' wurde automatisch aus der Gästeliste entfernt, da sie nicht gleichzeitig Gastgeberin und Gast sein kann.")
			if duplicate_indexes:
				msg.append("Doppelte Gäste wurden automatisch entfernt. Jeder Gast darf nur einmal ausgewählt werden.")
			frappe.msgprint("\n".join(msg), alert=True)
	
	def validate_all_guests_have_products(self):
		"""
		Prüft, ob alle eingetragenen Gäste und die Gastgeberin Produkte ausgewählt haben
		Erlaubt das Speichern ohne Produktvalidierung, wenn neue Gäste hinzugefügt wurden
		"""
		if not self.kunden:
			return
		
		# Wenn der Status noch "Gäste" ist, erlaube Speichern ohne Produktvalidierung
		# Das ermöglicht das Hinzufügen neuer Gäste auch nach dem ersten Speichern
		if self.status == "Gäste":
			return
		
		# Sammle alle Teilnehmer ohne Produktauswahl
		teilnehmer_ohne_produkte = []
		
		# Prüfe Gastgeberin
		if self.gastgeberin:
			hat_gastgeberin_produkte = False
			if hasattr(self, "produktauswahl_für_gastgeberin") and self.produktauswahl_für_gastgeberin:
				for produkt in self.produktauswahl_für_gastgeberin:
					if produkt.item_code and produkt.qty and produkt.qty > 0:
						hat_gastgeberin_produkte = True
						break
			
			if not hat_gastgeberin_produkte:
				teilnehmer_ohne_produkte.append(f"Gastgeberin ({self.gastgeberin})")
		
		# Prüfe alle Gäste
		for idx, kunde_row in enumerate(self.kunden):
			if not kunde_row.kunde:
				continue
				
			index = idx + 1
			field_name = f"produktauswahl_für_gast_{index}"
			
			# Prüfen ob die Tabelle existiert und Produkte enthält
			hat_produkte = False
			if hasattr(self, field_name) and getattr(self, field_name):
				tabelle_inhalt = getattr(self, field_name)
				frappe.log_error(f"Gast {index} ({kunde_row.kunde}) - Anzahl Zeilen in {field_name}: {len(tabelle_inhalt)}", "DEBUG: table_check")
				
				for idx_prod, produkt in enumerate(getattr(self, field_name)):
					if produkt.item_code:
						frappe.log_error(f"  Zeile {idx_prod}: item_code={produkt.item_code}, qty={produkt.qty}, rate={produkt.rate}", "DEBUG: row_check")
					if produkt.item_code and produkt.qty and produkt.qty > 0:
						hat_produkte = True
						break
			
			# Wenn keine Produkte gefunden wurden, zur Liste hinzufügen
			if not hat_produkte:
				teilnehmer_ohne_produkte.append(f"Gast {index} ({kunde_row.kunde})")
		
		# Wenn Teilnehmer ohne Produkte gefunden wurden, Fehlermeldung anzeigen
		if teilnehmer_ohne_produkte:
			anzahl_gaeste = len([k for k in self.kunden if k.kunde])
			
			frappe.throw(
				f"Die folgenden Teilnehmer haben noch keine Produkte ausgewählt: {', '.join(teilnehmer_ohne_produkte)}. "
				f"Bitte wählen Sie für jeden Teilnehmer (Gastgeberin und alle Gäste) mindestens ein Produkt aus. "
				f"Alternativ können Sie Gäste ohne Bestellung aus der Liste entfernen, "
				f"jedoch müssen mindestens 3 Gäste plus die Gastgeberin verbleiben."
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
						
						# WICHTIG: Normalisiere delivery_date Format für Datenbank-Kompatibilität
						if hasattr(item, 'delivery_date') and item.delivery_date:
							try:
								# Konvertiere ISO-String zu Date-Objekt falls nötig
								if isinstance(item.delivery_date, str):
									# Parse ISO-String und konvertiere zu Date
									item.delivery_date = frappe.utils.getdate(item.delivery_date)
								else:
									# Stelle sicher, dass es ein Date-Objekt ist
									item.delivery_date = frappe.utils.getdate(item.delivery_date)
							except Exception as e:
								# Fallback bei Parse-Fehlern
								frappe.log_error(f"Delivery Date Parse Fehler für {item.item_code}: {str(e)}", "WARNING: delivery_date_parse")
								item.delivery_date = frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7))
						
						# Weitere erforderliche Standardfelder für Sales Order Item setzen
						if not item.conversion_factor:
							item.conversion_factor = 1.0
						if not item.stock_qty:
							item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
						
						# Berechne den Betrag (amount = qty * rate)
						if item.qty and item.rate:
							item.amount = flt(item.qty) * flt(item.rate)
							item.base_amount = item.amount
		
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
					
					# WICHTIG: Normalisiere delivery_date Format für Datenbank-Kompatibilität
					if hasattr(item, 'delivery_date') and item.delivery_date:
						try:
							# Konvertiere ISO-String zu Date-Objekt falls nötig
							if isinstance(item.delivery_date, str):
								# Parse ISO-String und konvertiere zu Date
								item.delivery_date = frappe.utils.getdate(item.delivery_date)
							else:
								# Stelle sicher, dass es ein Date-Objekt ist
								item.delivery_date = frappe.utils.getdate(item.delivery_date)
						except Exception as e:
							# Fallback bei Parse-Fehlern
							frappe.log_error(f"Delivery Date Parse Fehler für {item.item_code}: {str(e)}", "WARNING: delivery_date_parse")
							item.delivery_date = frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7))
					
					# Weitere erforderliche Standardfelder für Sales Order Item setzen
					if not item.conversion_factor:
						item.conversion_factor = 1.0
					if not item.stock_qty:
						item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
					
					# Berechne den Betrag (amount = qty * rate)
					if item.qty and item.rate:
						item.amount = flt(item.qty) * flt(item.rate)
						item.base_amount = item.amount
	
	def calculate_totals(self):
		"""Berechnet Gesamtumsatz und Gutscheinwert für die Gastgeberin"""
		total_amount = 0.0
		
		# Berechne Gesamtumsatz aus allen Produkttabellen
		for i in range(1, 16):  # 1 bis 15
			field_name = f"produktauswahl_für_gast_{i}"
			if hasattr(self, field_name) and getattr(self, field_name):
				table = getattr(self, field_name)
				for item in table:
					if item.qty and item.rate:
						total_amount += flt(item.qty) * flt(item.rate)
		
		# Auch Gastgeberin-Tabelle berücksichtigen
		if hasattr(self, "produktauswahl_für_gastgeberin") and self.produktauswahl_für_gastgeberin:
			for item in self.produktauswahl_für_gastgeberin:
				if item.qty and item.rate:
					total_amount += flt(item.qty) * flt(item.rate)
		
		# Setze Gesamtumsatz
		self.gesamtumsatz = total_amount
		
		# Berechne Gutscheinwert basierend auf Präsentationsumsatz-Stufen
		self.gastgeber_gutschein_wert = self.calculate_gutschein_value(total_amount)
	
	def calculate_gutschein_value(self, total_amount):
		"""
		Berechnet den Gutscheinwert basierend auf Präsentationsumsatz-Stufen
		"""
		# Präsentationsumsatz-Stufen für Gratisprodukte
		# Format: (Mindest-Umsatz, Gutschein-Betrag)
		gutschein_stufen = [
			(0, 0),      # Unter 350€: 0€ Gutschein
			(350, 30),   # Ab 350€: 30€ Gutschein
			(600, 60),   # Ab 600€: 60€ Gutschein
			(850, 95),   # Ab 850€: 95€ Gutschein
			(1100, 130), # Ab 1100€: 130€ Gutschein
		]
		
		# Finde die passende Stufe
		gutschein_wert = 0
		for mindest_umsatz, gutschein_betrag in gutschein_stufen:
			if total_amount >= mindest_umsatz:
				gutschein_wert = gutschein_betrag
			else:
				break
		
		return gutschein_wert
	
	def check_hostess_voucher_usage(self):
		"""
		Prüft die Gutschein-Nutzung und wendet Rabatte an
		Gibt True zurück wenn alles OK ist, False wenn der Benutzer noch Produkte hinzufügen möchte
		"""
		if not hasattr(self, "produktauswahl_für_gastgeberin") or not self.produktauswahl_für_gastgeberin:
			return True
		
		if not self.gastgeber_gutschein_wert or self.gastgeber_gutschein_wert <= 0:
			return True
		
		# Sammle alle rabattfähigen Produkte der Gastgeberin
		rabattfaehige_produkte = []
		for item in self.produktauswahl_für_gastgeberin:
			if item.item_code and item.qty and item.rate:
				# Prüfe, ob das Produkt rabattfähig ist
				try:
					produkt_doc = frappe.get_cached_doc("Produkt", item.item_code)
					if getattr(produkt_doc, "custom_considered_for_action", 0):
						rabattfaehige_produkte.append(item)
				except:
					# Falls Produkt-Doctype nicht existiert, prüfe Item-Doctype
					try:
						item_doc = frappe.get_cached_doc("Item", item.item_code)
						if getattr(item_doc, "custom_considered_for_action", 0):
							rabattfaehige_produkte.append(item)
					except:
						continue
		
		# Berechne Gesamtwert der rabattfähigen Produkte
		gesamtwert_rabattfaehig = sum(flt(item.qty) * flt(item.rate) for item in rabattfaehige_produkte) if rabattfaehige_produkte else 0
		
		# Verfügbarer Gutscheinbetrag
		verfuegbarer_gutschein = flt(self.gastgeber_gutschein_wert)
		
		# Wende Rabatt an (falls möglich)
		if rabattfaehige_produkte and gesamtwert_rabattfaehig > 0:
			rabatt_betrag = min(gesamtwert_rabattfaehig, verfuegbarer_gutschein)
			self.apply_discount_to_products(rabattfaehige_produkte, rabatt_betrag)
		
		# Prüfe, ob Gutschein vollständig genutzt wird
		if not rabattfaehige_produkte or gesamtwert_rabattfaehig == 0:
			# Keine rabattfähigen Produkte
			return self.show_voucher_dialog(
				"Gutschein kann nicht genutzt werden",
				f"Die Gastgeberin hat einen Gutschein von {verfuegbarer_gutschein}€, "
				f"aber keine rabattfähigen Produkte ausgewählt.",
				f"Der komplette Gutschein von {verfuegbarer_gutschein}€ verfällt.",
				"Möchten Sie rabattfähige Produkte hinzufügen oder den Gutschein verfallen lassen?"
			)
		elif gesamtwert_rabattfaehig < verfuegbarer_gutschein:
			# Gutschein nicht vollständig genutzt
			nicht_genutzt = verfuegbarer_gutschein - gesamtwert_rabattfaehig
			return self.show_voucher_dialog(
				"Gutschein nicht vollständig genutzt",
				f"Die Gastgeberin hat einen Gutschein von {verfuegbarer_gutschein}€, "
				f"aber nur rabattfähige Produkte im Wert von {gesamtwert_rabattfaehig}€ ausgewählt.",
				f"{nicht_genutzt}€ des Gutscheins verfallen.",
				"Möchten Sie weitere rabattfähige Produkte hinzufügen oder den überschüssigen Betrag verfallen lassen?"
			)
		else:
			# Gutschein vollständig genutzt - alles OK
			frappe.msgprint(
				f"Der Gastgeber-Gutschein von {verfuegbarer_gutschein}€ wurde vollständig angewendet.",
				alert=True,
				indicator="green"
			)
			return True
	
	def show_voucher_dialog(self, title, description, warning, question):
		"""
		Zeigt einen Dialog mit der Gutschein-Warnung und gibt dem Benutzer die Wahl
		"""
		# Echten Dialog verwenden statt frappe.throw
		frappe.msgprint(
			f"<div style='text-align: center; padding: 20px;'>"
			f"<h3 style='color: #e74c3c; margin-bottom: 20px;'>{title}</h3>"
			f"<p style='font-size: 16px; margin-bottom: 15px; color: #2c3e50;'>{description}</p>"
			f"<p style='font-size: 18px; color: #e74c3c; font-weight: bold; margin-bottom: 20px;'>{warning}</p>"
			f"<p style='font-size: 14px; color: #7f8c8d; margin-bottom: 20px;'>{question}</p>"
			f"<p style='font-size: 12px; color: #95a5a6;'>"
			f"Klicken Sie 'OK' um fortzufahren.</p>"
			f"</div>",
			title=title,
			indicator="blue",
			raise_exception=False  # Wichtig: Keine Exception werfen!
		)
		return True  # Immer True zurückgeben, damit der Prozess fortgesetzt wird
	
	def apply_discount_to_products(self, products, discount_amount):
		"""
		Wendet einen Rabatt proportional auf die angegebenen Produkte an
		"""
		if not products or discount_amount <= 0:
			return
		
		# Berechne Gesamtwert der Produkte
		total_value = sum(flt(item.qty) * flt(item.rate) for item in products)
		
		if total_value <= 0:
			return
		
		# Wende proportionalen Rabatt an
		remaining_discount = flt(discount_amount)
		
		for i, item in enumerate(products):
			item_value = flt(item.qty) * flt(item.rate)
			
			if i == len(products) - 1:
				# Letztes Produkt bekommt den verbleibenden Rabatt
				item_discount = remaining_discount
			else:
				# Proportionaler Rabatt
				item_discount = (item_value / total_value) * discount_amount
				remaining_discount -= item_discount
			
			# Berechne neuen Preis
			if item.qty > 0:
				discount_per_unit = item_discount / flt(item.qty)
				new_rate = flt(item.rate) - discount_per_unit
				
				# Stelle sicher, dass der Preis nicht negativ wird
				if new_rate < 0:
					new_rate = 0
				
				item.rate = new_rate
				item.amount = flt(item.qty) * new_rate
				item.base_amount = item.amount

	def validate_all_addresses(self):
		"""
		Prüft, ob alle benötigten Teilnehmer (Gastgeberin und Gäste) Adressen haben.
		REDUZIERT: Weniger aggressive Warnungen
		"""
		if self.is_new():
			return  # Überspringe Validierung für neue Dokumente
		
		# NUR PRÜFEN wenn der Status "Produkte" ist und wir kurz vor der Auftragserstellung stehen
		if self.status != "Produkte":
			return  # Überspringe Validierung in frühen Phasen
		
		teilnehmer_ohne_adresse = []
		
		# 1. Prüfe Gastgeberin
		if self.gastgeberin:
			if not find_existing_address(self.gastgeberin, "Billing"):
				teilnehmer_ohne_adresse.append(f"Gastgeberin ({self.gastgeberin})")
		
		# 2. Prüfe alle Gäste
		if self.kunden:
			for kunde_row in self.kunden:
				if not kunde_row.kunde:
					continue
					
				# Prüfe Billing-Adresse (mindestens eine Adresse muss vorhanden sein)
				if not find_existing_address(kunde_row.kunde, "Billing"):
					teilnehmer_ohne_adresse.append(f"Gast ({kunde_row.kunde})")
		
		# REDUZIERT: Nur noch bei VIELEN fehlenden Adressen warnen, einzelne ignorieren
		if len(teilnehmer_ohne_adresse) > 2:  # Mehr als 2 Teilnehmer ohne Adresse
			fehlende_adressen = ", ".join(teilnehmer_ohne_adresse)
			
			# MELDUNG ENTFERNT: Störende Adressmeldung wird nicht mehr angezeigt
			# frappe.msgprint(
			# 	f"""INFO: {len(teilnehmer_ohne_adresse)} Teilnehmer haben möglicherweise unvollständige Adressen: {fehlende_adressen}
			# 	
			# 	Falls nötig, überprüfe die Adressen vor der Auftragserstellung.
			# 	
			# 	Die Party wird normal gespeichert.""",
			# 	alert=True,
			# 	indicator="blue"
			# )
			
			frappe.log_error(f"Adress-Info für Party {self.name}: {fehlende_adressen}", "INFO: address_check")
		else:
			# Bei wenigen fehlenden Adressen: Nur stilles Logging
			if teilnehmer_ohne_adresse:
				frappe.log_error(f"Vereinzelte Adress-Hinweise für Party {self.name}: {', '.join(teilnehmer_ohne_adresse)}", "INFO: few_address_hints")

# VERALTET: Diese Funktion erstellt automatisch Adressen - NICHT MEHR VERWENDEN!
def get_or_create_address(customer_name, address_type="Billing"):
	"""
	VERALTET: Verwende find_existing_address() stattdessen!
	Diese Funktion erstellt KEINE neuen Adressen mehr.
	"""
	frappe.log_error(f"WARNUNG: get_or_create_address ist veraltet! Verwende find_existing_address für '{customer_name}'", "WARNING: deprecated_function")
	return find_existing_address(customer_name, address_type)

def create_robust_fallback_address(customer_name, address_type):
	"""
	GEÄNDERT: Erstellt KEINE neuen Adressen mehr!
	Sucht nur nach existierenden Adressen und gibt None zurück wenn keine gefunden wird
	"""
	frappe.log_error(f"WARNUNG: create_robust_fallback_address aufgerufen für '{customer_name}' - suche nur nach existierenden Adressen", "WARNING: no_auto_create")
	
	# Verwende die neue find_existing_address Funktion
	existing_address = find_existing_address(customer_name, address_type)
	if existing_address:
		frappe.log_error(f"Existierende Adresse gefunden für '{customer_name}': {existing_address}", "INFO: existing_found")
		return existing_address
	else:
		frappe.log_error(f"KEINE Adresse für '{customer_name}' gefunden - erstelle KEINE neue Adresse!", "ERROR: no_address_available")
		return None

def get_available_country():
	"""
	VERALTET: Diese Funktion wird nicht mehr benötigt,
	da wir keine neuen Adressen mehr erstellen
	"""
	frappe.log_error("get_available_country ist veraltet - keine neuen Adressen mehr!", "WARNING: deprecated")
	return "Germany"

# ENTFERNT: Diese Funktion erstellt neue Adressen - nicht mehr verwenden!
def create_new_address(customer_name, address_type):
	"""VERALTET: Erstellt KEINE neuen Adressen mehr!"""
	frappe.log_error(f"create_new_address für '{customer_name}' aufgerufen - erstelle KEINE Adresse!", "ERROR: no_auto_create")
	return None

# ENTFERNT: Diese Funktion erstellt neue Adressen - nicht mehr verwenden!
def create_fallback_address():
	"""VERALTET: Erstellt KEINE neuen Adressen mehr!"""
	frappe.log_error("create_fallback_address aufgerufen - erstelle KEINE Adresse!", "ERROR: no_auto_create")
	return None

# Neue Funktion für das Verknüpfen einer Adresse mit einem Kunden
def link_address_to_customer(address_name, customer_name):
	"""Verknüpft eine Adresse mit einem Kunden, falls die Verknüpfung noch nicht existiert."""
	# Prüfen ob die Verknüpfung bereits existiert
	existing_link = frappe.db.exists("Dynamic Link", {
		"parent": address_name,
		"parenttype": "Address",
		"link_doctype": "Customer",
		"link_name": customer_name
	})
	
	if not existing_link:
		# Füge eine neue Verknüpfung hinzu
		link = frappe.get_doc({
			"doctype": "Dynamic Link",
			"parent": address_name,
			"parenttype": "Address",
			"link_doctype": "Customer",
			"link_name": customer_name
		})
		link.insert(ignore_permissions=True)

# Warehouse-Hilfsfunktion hinzufügen
@frappe.whitelist()
def get_default_warehouse():
	"""
	Ermittelt das Standard-Warehouse flexibel für verschiedene Installationen
	"""
	# Versuche zuerst das Benutzer-Default-Warehouse
	warehouse = frappe.defaults.get_user_default("Warehouse")
	if warehouse:
		return warehouse
	
	# Fallback: Erstes verfügbares nicht-Gruppen-Warehouse
	warehouses = frappe.get_all("Warehouse", 
		filters={"is_group": 0}, 
		fields=["name"], 
		limit=1
	)
	
	if warehouses:
		return warehouses[0].name
	
	# Letzter Fallback: Erstes verfügbares Warehouse überhaupt
	all_warehouses = frappe.get_all("Warehouse", fields=["name"], limit=1)
	if all_warehouses:
		return all_warehouses[0].name
	
	# Wenn gar nichts gefunden wird, verwende einen Standard-Namen
	return "Stores - Main"

def calculate_shipping_costs_for_party(party_doc):
    """
    Berechnet Versandkosten für eine Party und erstellt Order-Informationen
    NEUE LOGIK: Verwendet 7 verschiedene Versandartikel statt ERPNext Versandregeln
    """
    all_orders = []
    
    frappe.log_error(f"=== CALCULATE_SHIPPING_COSTS START für {party_doc.name} ===", "DEBUG: shipping_start")
    
    # Gastgeberin verarbeiten
    if party_doc.gastgeberin and hasattr(party_doc, 'produktauswahl_für_gastgeberin') and party_doc.produktauswahl_für_gastgeberin:
        frappe.log_error(f"Verarbeite Gastgeberin: {party_doc.gastgeberin}", "DEBUG: process_host")
        
        produkte_gastgeberin = []
        total_gastgeberin = 0
        
        for idx_prod, produkt in enumerate(party_doc.produktauswahl_für_gastgeberin):
            frappe.log_error(f"  Gastgeberin Zeile {idx_prod}: item_code={produkt.item_code}, qty={produkt.qty}, rate={produkt.rate}", "DEBUG: host_item")
            if produkt.item_code and produkt.qty and produkt.qty > 0:
                frappe.log_error(f"  -> Gastgeberin Produkt akzeptiert: {produkt.item_code}", "DEBUG: host_accepted")
                # WICHTIG: Übertrage ALLE Produktdaten, nicht nur die Basics!
                product_dict = {
                    "item_code": produkt.item_code,
                    "item_name": produkt.item_name or produkt.item_code,
                    "qty": produkt.qty,
                    "rate": produkt.rate or 0,
                    "amount": produkt.amount or (flt(produkt.qty) * flt(produkt.rate or 0)),
                    "uom": getattr(produkt, 'uom', 'Stk'),
                    "stock_uom": getattr(produkt, 'stock_uom', 'Stk'),
                    "conversion_factor": getattr(produkt, 'conversion_factor', 1.0),
                    "stock_qty": getattr(produkt, 'stock_qty', flt(produkt.qty)),
                    "base_amount": getattr(produkt, 'base_amount', produkt.amount or (flt(produkt.qty) * flt(produkt.rate or 0))),
                    "base_rate": getattr(produkt, 'base_rate', produkt.rate or 0),
                    "warehouse": getattr(produkt, 'warehouse', get_default_warehouse()),
                    "delivery_date": frappe.utils.getdate(getattr(produkt, 'delivery_date', frappe.utils.add_days(frappe.utils.today(), 7))),
                    # WICHTIG: Flag für Gutschein-reduzierte 0€-Artikel
                    "_force_zero_rate": float(produkt.rate or 0) == 0.0
                }
                
                produkte_gastgeberin.append(product_dict)
                total_gastgeberin += flt(produkt.qty) * flt(produkt.rate or 0)
                frappe.log_error(f"  -> Gastgeberin Produkt hinzugefügt, neue Summe: {total_gastgeberin}", "DEBUG: host_added")
        
        if produkte_gastgeberin:
            # Versandziel für Gastgeberin
            versand_ziel = getattr(party_doc, 'versand_gastgeberin', party_doc.gastgeberin)
            if not versand_ziel:
                versand_ziel = party_doc.gastgeberin
                
            frappe.log_error(f"Gastgeberin ({party_doc.gastgeberin}) hat {len(produkte_gastgeberin)} Produkte, Total: {total_gastgeberin}", "DEBUG: host_order")
                
            all_orders.append({
                "customer": party_doc.gastgeberin,
                "shipping_target": versand_ziel,
                "products": produkte_gastgeberin,
                "total": total_gastgeberin,
                "order_type": "gastgeberin"
            })
        else:
            frappe.log_error(f"Gastgeberin: Keine gültigen Produkte gefunden", "DEBUG: host_no_products")
    
    # Gäste verarbeiten
    frappe.log_error(f"Verarbeite {len(party_doc.kunden)} Gäste", "DEBUG: process_guests")
    for idx, kunde_row in enumerate(party_doc.kunden):
        if not kunde_row.kunde:
            frappe.log_error(f"Gast {idx+1}: Kein Kunde angegeben - überspringe", "DEBUG: guest_no_customer")
            continue
            
        index = idx + 1
        field_name = f"produktauswahl_für_gast_{index}"
        versand_field = f"versand_gast_{index}"
        
        frappe.log_error(f"=== Verarbeite Gast {index}: {kunde_row.kunde} ===", "DEBUG: guest_start")
        
        if not hasattr(party_doc, field_name) or not getattr(party_doc, field_name):
            frappe.log_error(f"Gast {index} ({kunde_row.kunde}): Keine Produkttabelle {field_name} gefunden", "DEBUG: no_product_table")
            continue
        
        produkte_gast = []
        total_gast = 0
        
        tabelle_inhalt = getattr(party_doc, field_name)
        frappe.log_error(f"Gast {index} ({kunde_row.kunde}) - Anzahl Zeilen in {field_name}: {len(tabelle_inhalt)}", "DEBUG: table_check")
        
        for idx_prod, produkt in enumerate(getattr(party_doc, field_name)):
            frappe.log_error(f"  Gast {index} Zeile {idx_prod}: item_code={produkt.item_code}, qty={produkt.qty}, rate={produkt.rate}", "DEBUG: guest_item")
            if produkt.item_code and produkt.qty and produkt.qty > 0:
                frappe.log_error(f"  -> Gast {index} Produkt akzeptiert: {produkt.item_code}", "DEBUG: guest_accepted")
                # WICHTIG: Übertrage ALLE Produktdaten, nicht nur die Basics!
                product_dict = {
                    "item_code": produkt.item_code,
                    "item_name": produkt.item_name or produkt.item_code,
                    "qty": produkt.qty,
                    "rate": produkt.rate or 0,
                    "amount": produkt.amount or (flt(produkt.qty) * flt(produkt.rate or 0)),
                    "uom": getattr(produkt, 'uom', 'Stk'),
                    "stock_uom": getattr(produkt, 'stock_uom', 'Stk'),
                    "conversion_factor": getattr(produkt, 'conversion_factor', 1.0),
                    "stock_qty": getattr(produkt, 'stock_qty', flt(produkt.qty)),
                    "base_amount": getattr(produkt, 'base_amount', produkt.amount or (flt(produkt.qty) * flt(produkt.rate or 0))),
                    "base_rate": getattr(produkt, 'base_rate', produkt.rate or 0),
                    "warehouse": getattr(produkt, 'warehouse', get_default_warehouse()),
                    "delivery_date": frappe.utils.getdate(getattr(produkt, 'delivery_date', frappe.utils.add_days(frappe.utils.today(), 7))),
                    # WICHTIG: Flag für Gutschein-reduzierte 0€-Artikel
                    "_force_zero_rate": float(produkt.rate or 0) == 0.0
                }
                
                produkte_gast.append(product_dict)
                total_gast += flt(produkt.qty) * flt(produkt.rate or 0)
                frappe.log_error(f"  -> Gast {index} Produkt hinzugefügt, neue Summe: {total_gast}", "DEBUG: guest_added")
        
        if produkte_gast:
            # Versandziel für Gast
            versand_ziel = getattr(party_doc, versand_field, kunde_row.kunde)
            if not versand_ziel:
                versand_ziel = kunde_row.kunde
                
            frappe.log_error(f"Gast {index} ({kunde_row.kunde}) hat {len(produkte_gast)} Produkte, Total: {total_gast}", "DEBUG: guest_order")
                
            all_orders.append({
                "customer": kunde_row.kunde,
                "shipping_target": versand_ziel,
                "products": produkte_gast,
                "total": total_gast,
                "order_type": "gast",
                "guest_index": index
            })
        else:
            frappe.log_error(f"Gast {index} ({kunde_row.kunde}): Keine gültigen Produkte in {field_name} gefunden", "DEBUG: guest_no_products")
    
    # Gruppiere Bestellungen nach Versandziel
    shipping_groups = {}
    for order in all_orders:
        target = order["shipping_target"]
        if target not in shipping_groups:
            shipping_groups[target] = []
        shipping_groups[target].append(order)
    
    frappe.log_error(f"=== SHIPPING GROUPS ERSTELLUNG ===", "DEBUG: shipping_groups")
    frappe.log_error(f"Anzahl Orders vor Gruppierung: {len(all_orders)}", "DEBUG: orders_count")
    for target, orders in shipping_groups.items():
        frappe.log_error(f"Versandziel {target}: {len(orders)} Orders", "DEBUG: group_detail")
    
    # NEUE VERSANDLOGIK: Berechne Versandkosten pro Gruppe und füge Versandartikel hinzu
    for target, orders in shipping_groups.items():
        total_value_for_target = sum(order["total"] for order in orders)
        num_orders = len(orders)
        
        frappe.log_error(f"Versandziel {target}: {num_orders} Aufträge, Gesamtwert: {total_value_for_target}€", "DEBUG: shipping_calculation")
        
        if total_value_for_target >= 200:
            # Versandkostenfrei für alle Bestellungen an dieses Ziel
            shipping_cost_per_order = 0.0
            shipping_item_code = None
            shipping_note = f"Versandkostenfrei (Gesamtwert: {total_value_for_target:.2f}€ >= 200€)"
            frappe.log_error(f"Versandkostenfrei für {target}", "DEBUG: shipping_free")
        else:
            # 7€ Versandkosten aufteilen - bestimme den richtigen Versandartikel
            shipping_cost_per_order = round(7.0 / num_orders, 2)
            
            # Bestimme Versandartikel basierend auf Anzahl der Aufträge
            shipping_items = {
                1: "shipping-7",      # 7€ für 1 Person
                2: "shipping-3.5",    # 3.5€ für 2 Personen
                3: "shipping-2.33",   # 2.33€ für 3 Personen
                4: "shipping-1.75",   # 1.75€ für 4 Personen
                5: "shipping-1.4",    # 1.4€ für 5 Personen
                6: "shipping-1.17",   # 1.17€ für 6 Personen
                7: "shipping-1"       # 1€ für 7 Personen
            }
            
            # Fallback für mehr als 7 Personen - verwende shipping-1
            shipping_item_code = shipping_items.get(num_orders, "shipping-1")
            
            shipping_note = f"Versandkosten aufgeteilt: {num_orders} Bestellung(en) à {shipping_cost_per_order:.2f}€ (Gesamtwert: {total_value_for_target:.2f}€ < 200€) - Artikel: {shipping_item_code}"
            frappe.log_error(f"Versandkosten für {target}: {shipping_item_code} à {shipping_cost_per_order}€", "DEBUG: shipping_charged")
        
        # Versandkosten zu jeder Bestellung hinzufügen
        for order in orders:
            order["shipping_cost"] = shipping_cost_per_order
            order["shipping_note"] = shipping_note
            order["shipping_item_code"] = shipping_item_code  # Neues Feld für Versandartikel
            
            # Versandartikel zu den Produkten hinzufügen, wenn Versandkosten anfallen
            if shipping_cost_per_order > 0 and shipping_item_code:
                # Hole Versandartikel-Details
                try:
                    shipping_item_doc = frappe.get_doc("Item", shipping_item_code)
                    
                    shipping_product = {
                        "item_code": shipping_item_code,
                        "item_name": shipping_item_doc.item_name or "Versand",
                        "qty": 1,
                        "rate": shipping_cost_per_order,
                        "amount": shipping_cost_per_order,
                        "uom": shipping_item_doc.stock_uom or "Stk",
                        "stock_uom": shipping_item_doc.stock_uom or "Stk",
                        "conversion_factor": 1.0,
                        "stock_qty": 1.0,
                        "base_amount": shipping_cost_per_order,
                        "base_rate": shipping_cost_per_order,
                        "warehouse": get_default_warehouse(),
                        "delivery_date": frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7)),
                        "_force_zero_rate": False,
                        "_shipping_item": True  # Markierung als Versandartikel
                    }
                    
                    # Versandartikel zu den Produkten hinzufügen
                    order["products"].append(shipping_product)
                    order["total"] += shipping_cost_per_order  # Gesamtsumme des Auftrags aktualisieren
                    
                    frappe.log_error(f"Versandartikel {shipping_item_code} hinzugefügt zu {order['customer']}: {shipping_cost_per_order}€", "DEBUG: shipping_item_added")
                    
                except Exception as e:
                    frappe.log_error(f"Fehler beim Laden des Versandartikels {shipping_item_code}: {str(e)}", "ERROR: shipping_item_error")
                    # Fallback: Verwende Standard-Versandartikel-Daten
                    shipping_product = {
                        "item_code": shipping_item_code,
                        "item_name": "Versand",
                        "qty": 1,
                        "rate": shipping_cost_per_order,
                        "amount": shipping_cost_per_order,
                        "uom": "Stk",
                        "stock_uom": "Stk",
                        "conversion_factor": 1.0,
                        "stock_qty": 1.0,
                        "base_amount": shipping_cost_per_order,
                        "base_rate": shipping_cost_per_order,
                        "warehouse": get_default_warehouse(),
                        "delivery_date": frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7)),
                        "_force_zero_rate": False,
                        "_shipping_item": True
                    }
                    order["products"].append(shipping_product)
                    order["total"] += shipping_cost_per_order
    
    frappe.log_error(f"=== ENDERGEBNIS calculate_shipping_costs_for_party ===", "DEBUG: shipping_calc_end")
    frappe.log_error(f"FINALE Anzahl Orders: {len(all_orders)}", "DEBUG: orders_count")
    for i, order in enumerate(all_orders):
        frappe.log_error(f"Order {i+1}: Customer={order['customer']}, Produkte={len(order['products'])}, Total={order['total']}", "DEBUG: final_order")
    frappe.log_error(f"SUCCESS: final_result", "SUCCESS: final_result")
    return all_orders

@frappe.whitelist()
def create_invoices(party, from_submit=False, from_button=False):
    """
    Erstellt Sales Orders für eine Party
    - party: Name des Party-Dokuments
    - from_submit: Ob die Funktion vom Submit-Button aufgerufen wurde
    - from_button: Ob die Funktion vom "Aufträge erstellen"-Button aufgerufen wurde
    """
    # BACKEND-SICHERUNG: Setze skip_total_calculation Flag falls vom Button aufgerufen
    if from_button:
        try:
            party_doc = frappe.get_doc("Party", party)
            if not getattr(party_doc, 'skip_total_calculation', False):
                frappe.log_error(f"Backend-Sicherung: Setze skip_total_calculation für {party}", "INFO: backend_flag_set")
                party_doc.skip_total_calculation = 1
                party_doc.flags.ignore_permissions = True
                party_doc.save()
                frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Backend-Sicherung Fehler: {str(e)}", "WARNING: backend_flag_failed")
    
    try:
        # Grundlegende Fehlerprotokollierung aktivieren
        frappe.log_error(f"Starte Auftragserstellung für Party {party} (from_submit={from_submit}, from_button={from_button})", "DEBUG: create_orders Start")
        
        # Prüfen, ob die Party bereits Aufträge hat
        existing_orders = frappe.get_all(
            "Sales Order",
            filters={"docstatus": ["!=", 2]},
            or_filters=[
                {"po_no": party},  # Versuche, in verschiedenen Feldern zu suchen
                {"customer_name": party}
            ],
            limit=1
        )
        
        # Wenn es bereits Aufträge gibt und der Aufruf vom Button kommt, blockieren
        if existing_orders and from_button:
            frappe.log_error(f"Aufträge gefunden: {existing_orders}", "DEBUG: create_orders - Gefundene Aufträge")
            # ENTFERNT: frappe.msgprint("Diese Party hat bereits Aufträge. Es werden keine neuen Aufträge erstellt.", alert=True)
            return existing_orders
        
        # Wenn die Funktion sowohl von before_submit als auch vom Button aufgerufen wird, 
        # verhindere Doppelausführung
        if from_button and from_submit:
            frappe.log_error("Verhinderte doppelte Ausführung (from_button und from_submit sind beide True)", "DEBUG: create_orders")
            return []
        
        # Hole Standard-Einstellungen
        company = frappe.defaults.get_user_default("Company")
        if not company:
            frappe.log_error("Keine Standard-Firma gefunden!", "ERROR: create_orders")
            frappe.throw("Bitte legen Sie eine Standard-Firma in Ihren Einstellungen fest.")
            
        currency = frappe.defaults.get_user_default("Currency")
        if not currency:
            frappe.log_error("Keine Standard-Währung gefunden!", "ERROR: create_orders")
            frappe.throw("Bitte legen Sie eine Standard-Währung in Ihren Einstellungen fest.")
            
        # Party-Dokument laden
        try:
            party_doc = frappe.get_doc("Party", party)
            party_doc.skip_total_calculation = 1  # <-- HIER!
                
        except Exception as e:
            frappe.log_error(f"Party-Dokument konnte nicht geladen werden: {str(e)}", "ERROR: create_orders")
            frappe.throw("Das Party-Dokument konnte nicht geladen werden.")
        
        # Prüfen, ob die Party bereits abgeschlossen ist
        if party_doc.status == "Abgeschlossen" and party_doc.docstatus == 1:
            # ENTFERNT: frappe.msgprint("Diese Party ist bereits abgeschlossen und hat wahrscheinlich bereits Aufträge.", alert=True)
            return []
        
        # Gästeliste prüfen
        if not party_doc.kunden or len(party_doc.kunden) < 3:
            frappe.throw("Es müssen mindestens 3 Gäste/Kunden zur Party hinzugefügt werden.")
            
        # Prüfe, ob die Gastgeberin existiert
        if not party_doc.gastgeberin:
            frappe.throw("Es wurde keine Gastgeberin angegeben.")
            
        # Vollständige Produktvalidierung für alle Teilnehmer
        teilnehmer_ohne_produkte = []
        
        # Prüfe Gastgeberin
        if party_doc.gastgeberin:
            hat_gastgeberin_produkte = False
            if hasattr(party_doc, "produktauswahl_für_gastgeberin") and party_doc.produktauswahl_für_gastgeberin:
                for produkt in party_doc.produktauswahl_für_gastgeberin:
                    if produkt.item_code and produkt.qty and produkt.qty > 0:
                        hat_gastgeberin_produkte = True
                        break
            
            if not hat_gastgeberin_produkte:
                teilnehmer_ohne_produkte.append(f"Gastgeberin ({party_doc.gastgeberin})")
        
        # Prüfe alle Gäste
        for idx, kunde_row in enumerate(party_doc.kunden):
            if not kunde_row.kunde:
                continue
                
            index = idx + 1
            field_name = f"produktauswahl_für_gast_{index}"
            
            # Prüfen ob die Tabelle existiert und Produkte enthält
            hat_produkte = False
            if hasattr(party_doc, field_name) and getattr(party_doc, field_name):
                for produkt in getattr(party_doc, field_name):
                    if produkt.item_code and produkt.qty and produkt.qty > 0:
                        hat_produkte = True
                        break
            
            # Wenn keine Produkte gefunden wurden, zur Liste hinzufügen
            if not hat_produkte:
                teilnehmer_ohne_produkte.append(f"Gast {index} ({kunde_row.kunde})")
        
        # Wenn Teilnehmer ohne Produkte gefunden wurden, Fehlermeldung anzeigen
        if teilnehmer_ohne_produkte:
            frappe.throw(
                f"Die folgenden Teilnehmer haben noch keine Produkte ausgewählt: {', '.join(teilnehmer_ohne_produkte)}. "
                f"Bitte wählen Sie für jeden Teilnehmer (Gastgeberin und alle Gäste) mindestens ein Produkt aus, "
                f"bevor Sie die Aufträge erstellen. Sie können auch Gäste ohne Bestellung aus der Gästeliste entfernen."
            )
        
        # Produkte-Check: Hat irgendein Kunde oder die Gastgeberin Produkte?
        produkte_vorhanden = False
        
        # Prüfe Gastgeberin
        if hasattr(party_doc, "produktauswahl_für_gastgeberin") and party_doc.produktauswahl_für_gastgeberin:
            for produkt in party_doc.produktauswahl_für_gastgeberin:
                if produkt.item_code and produkt.qty and produkt.qty > 0:
                    produkte_vorhanden = True
                    break
        
        # Prüfe alle Kunden
        if not produkte_vorhanden:
            for idx, _ in enumerate(party_doc.kunden or []):
                field_name = f"produktauswahl_für_gast_{idx+1}"
                if hasattr(party_doc, field_name) and getattr(party_doc, field_name):
                    for produkt in getattr(party_doc, field_name):
                        if produkt.item_code and produkt.qty and produkt.qty > 0:
                            produkte_vorhanden = True
                            break
                    if produkte_vorhanden:
                        break
        
        if not produkte_vorhanden:
            frappe.throw("Es wurden keine Produkte ausgewählt. Bitte wählen Sie mindestens ein Produkt aus, bevor Sie Aufträge erstellen.")
        
        # NEUE VERSANDKOSTENLOGIK
        # Sammle alle Bestellungen mit ihren Versandzielen und berechne Versandkosten
        frappe.log_error(f"=== AUFRUF calculate_shipping_costs_for_party ===", "DEBUG: before_calc")
        all_orders_with_shipping = calculate_shipping_costs_for_party(party_doc)
        frappe.log_error(f"=== RÜCKKEHR von calculate_shipping_costs_for_party ===", "DEBUG: after_calc")
        
        frappe.log_error(f"Anzahl Orders mit Versandkosten: {len(all_orders_with_shipping)}", "DEBUG: orders_count")
        for i, order in enumerate(all_orders_with_shipping):
            frappe.log_error(f"Erhaltene Order {i+1}: Customer={order.get('customer')}, Products={len(order.get('products', []))}, Total={order.get('total')}", "DEBUG: received_order")
        
        if not all_orders_with_shipping:
            frappe.log_error("Keine Bestellungen gefunden - calculate_shipping_costs_for_party gab leere Liste zurück", "ERROR: no_orders_calculated")
            # ENTFERNT: frappe.msgprint("Keine Bestellungen gefunden. Bitte prüfe die Logs und versuche es erneut.", alert=True)
            return []
        
        # Debug: Zeige Details der ersten Bestellung
        if all_orders_with_shipping:
            first_order = all_orders_with_shipping[0]
            frappe.log_error(f"Erste Bestellung: Customer={first_order.get('customer')}, Products={len(first_order.get('products', []))}", "DEBUG: first_order")
        
        # Erstelle eine Liste für die erstellten Aufträge
        created_orders = []
        
        # Erstelle Aufträge basierend auf der Versandkostenberechnung
        for order_info in all_orders_with_shipping:
            try:
                customer = order_info["customer"]
                shipping_target = order_info["shipping_target"]
                products = order_info["products"]
                shipping_cost = order_info["shipping_cost"]
                shipping_note = order_info["shipping_note"]
                
                frappe.log_error(f"Verarbeite: Customer={customer}, Shipping_Target={shipping_target}", "DEBUG: order_processing")
                
                # NEUE EINFACHE ADRESS-LOGIK:
                # Rechnungsadresse: IMMER Billing vom Kunden (der bestellt)
                # Versandadresse: Shipping vom Versandziel, Fallback auf Billing vom Versandziel
                
                billing_address = None
                shipping_address = None
                
                frappe.log_error(f"=== ADRESS-DEBUG START für Customer: {customer}, Shipping_Target: {shipping_target} ===", "DEBUG: address_search")
                
                # 1. RECHNUNGSADRESSE: Immer vom Kunden der bestellt
                frappe.log_error(f"Suche Billing-Adresse für Customer: '{customer}'", "DEBUG: billing_search")
                billing_address = find_existing_address(customer, "Billing")
                frappe.log_error(f"DEBUG: billing_address für {customer} = {billing_address} (Typ: {type(billing_address)})", "DEBUG: address_result")
                
                if not billing_address:
                    frappe.log_error(f"KRITISCH: Keine Adresse für Kunde '{customer}' gefunden", "ERROR: no_billing")
                    # ENTFERNT: frappe.msgprint(f"Kunde {customer} hat keine Adresse hinterlegt. Auftrag wird übersprungen.", alert=True)
                    continue
                
                frappe.log_error(f"✅ Billing-Adresse für Kunde '{customer}': {billing_address}", "INFO: billing_found")
                
                # 2. VERSANDADRESSE: Erst Shipping vom Versandziel, dann Billing vom Versandziel
                frappe.log_error(f"Suche Shipping-Adresse für Versandziel: '{shipping_target}'", "DEBUG: shipping_search")
                shipping_address = find_existing_address(shipping_target, "Shipping")
                frappe.log_error(f"DEBUG: shipping_address (Shipping) für {shipping_target} = {shipping_address} (Typ: {type(shipping_address)})", "DEBUG: address_result")
                
                if not shipping_address:
                    # Fallback: Billing-Adresse vom Versandziel
                    frappe.log_error(f"Suche Billing-Fallback für Versandziel: '{shipping_target}'", "DEBUG: shipping_fallback_search")
                    shipping_address = find_existing_address(shipping_target, "Billing")
                    frappe.log_error(f"DEBUG: shipping_address (Billing Fallback) für {shipping_target} = {shipping_address} (Typ: {type(shipping_address)})", "DEBUG: address_result")
                    
                    if shipping_address:
                        frappe.log_error(f"✅ Versand-Fallback: Billing-Adresse von '{shipping_target}': {shipping_address}", "INFO: shipping_fallback")
                    else:
                        frappe.log_error(f"KRITISCH: Keine Adresse für Versandziel '{shipping_target}' gefunden", "ERROR: no_shipping")
                        # ENTFERNT: frappe.msgprint(f"Versandziel {shipping_target} hat keine Adresse hinterlegt. Auftrag wird übersprungen.", alert=True)
                        continue
                else:
                    frappe.log_error(f"✅ Shipping-Adresse für Versandziel '{shipping_target}': {shipping_address}", "INFO: shipping_found")
                
                frappe.log_error(f"=== FINALE ADRESSEN: Billing={billing_address}, Shipping={shipping_address} ===", "DEBUG: final_addresses")

                # Auftragsdaten mit klarer Adress-Dokumentation
                order_data = {
                    "doctype": "Sales Order",
                    "customer": customer,
                    "transaction_date": today(),
                    "delivery_date": today(),
                    "items": [
                        {
                            **product,  # Alle Produktdaten übernehmen
                            "doctype": "Sales Order Item"
                        } for product in products
                    ],
                    "customer_address": billing_address,  # Rechnungsadresse des Kunden
                    "shipping_address_name": shipping_address,  # Versandadresse (kann andere Person sein)
                    "remarks": f"Erstellt aus Party: {party} | Kunde: {customer} | Versand an: {shipping_target}",
                    "po_no": party,  # Party-Referenz in po_no speichern
                    "company": company,
                    "currency": currency,
                    "status": "Draft",
                    "order_type": "Sales",
                    # Sales Partner aus der Party übernehmen (Priorität vor Customer Sales Partner)
                    "sales_partner": party_doc.partnerin if party_doc.partnerin else None,
                    # Custom Fields für Versandinformationen
                    "custom_party_reference": party,
                    "custom_calculated_shipping_cost": shipping_cost,
                }
                
                frappe.log_error(f"DEBUG: Order-Daten für {customer}: customer_address={billing_address}, shipping_address_name={shipping_address}", "DEBUG: order_data")
                frappe.log_error(f"Erstelle Auftrag für '{customer}'", "INFO: creating_order")
                
                # Auftrag erstellen
                order = frappe.get_doc(order_data)
                
                # WICHTIG: Nach der Erstellung die korrekten Preise aus dem Party-Dokument setzen
                # um zu verhindern, dass Gutschein-reduzierte Preise überschrieben werden
                for i, item in enumerate(order.items):
                    original_product = products[i]
                    
                    # DEBUG: Spezifisches Logging für Aktionsartikel + Versandartikel Kombination
                    is_shipping = original_product.get('_shipping_item', False)
                    item_code = original_product.get('item_code', 'Unknown')
                    frappe.log_error(f"DEBUG COMBO: Item {i}: {item_code}, Shipping: {is_shipping}, Rate: {original_product.get('rate', 'N/A')}", "DEBUG: combo_check")
                    
                    # DEBUG: Zeige Flag-Status für jedes Produkt
                    force_zero = original_product.get('_force_zero_rate', False)
                    frappe.log_error(f"DEBUG: Item {item.item_code}, Rate: {original_product.get('rate', 'N/A')}, Force Zero: {force_zero}", "DEBUG: flag_check")
                    
                    # NEUE LOGIK: Prüfe das _force_zero_rate Flag für Gutschein-reduzierte 0€-Artikel
                    if force_zero:
                        frappe.log_error(f"Setze Gutschein-Preis für {item.item_code}: 0€ (Force Zero Flag)", "INFO: gutschein_price")
                        # Setze alle preis-relevanten Felder explizit auf 0
                        item.rate = 0
                        item.price_list_rate = 0
                        item.base_rate = 0
                        item.base_price_list_rate = 0
                        item.amount = 0
                        item.base_amount = 0
                        # Markiere, dass dies ein Gutschein-Artikel ist (falls Custom Field existiert)
                        if hasattr(item, 'custom_gutschein_reduziert'):
                            item.custom_gutschein_reduziert = 1
                    else:
                        # Für normale Artikel die Original-Preise verwenden
                        if hasattr(original_product, 'rate') and original_product.rate is not None:
                            item.rate = original_product.rate
                            item.base_rate = original_product.rate
                            item.amount = flt(item.qty) * flt(original_product.rate) 
                            item.base_amount = item.amount
                
                # DEBUG: Zeige finale Order-Daten vor dem Insert
                frappe.log_error(f"DEBUG FINAL ORDER: Customer={order.customer}, Items={len(order.items)}", "DEBUG: final_order_data")
                for i, item in enumerate(order.items):
                    frappe.log_error(f"  Item {i}: {item.item_code}, Qty: {item.qty}, Rate: {item.rate}, Amount: {item.amount}", "DEBUG: final_item_data")
                
                # SAUBERE LÖSUNG: Nur spezifische Adress-Validierungen umgehen, 
                # aber Sales Partner Provisionsberechnung NICHT beeinträchtigen
                import types
                
                def safe_validate_party_address(self, *args, **kwargs):
                    # Nur kritische Adress-Validierung überspringen, falls Adressen existieren
                    frappe.log_error(f"Überspringe party_address für {self.customer}", "INFO: skip_validation")
                    pass
                
                def safe_validate_shipping_address(self, *args, **kwargs):
                    # Nur Versandadress-Validierung überspringen
                    frappe.log_error(f"Überspringe shipping_address für {self.customer}", "INFO: skip_validation")
                    pass
                
                def safe_validate_billing_address(self, *args, **kwargs):
                    # Nur Rechnungsadress-Validierung überspringen  
                    frappe.log_error(f"Überspringe billing_address für {self.customer}", "INFO: skip_validation")
                    pass
                
                # Nur die spezifischen Adress-Validierungen deaktivieren
                order.validate_party_address = types.MethodType(safe_validate_party_address, order)
                order.validate_shipping_address = types.MethodType(safe_validate_shipping_address, order)
                order.validate_billing_address = types.MethodType(safe_validate_billing_address, order)
                
                # WICHTIG: validate(), validate_links(), Sales Partner Validierung etc. NICHT deaktivieren!
                # Diese sind für Provisionsberechnung essentiell
                
                frappe.log_error(f"Führe order.insert() aus für '{customer}'...", "INFO: order_insert")
                
                try:
                    order.insert()
                    frappe.log_error(f"Order.insert() erfolgreich für '{customer}': {order.name}", "INFO: order_created")
                    
                    # Versuche den Auftrag einzureichen
                    frappe.log_error(f"Führe order.submit() aus für '{customer}'...", "INFO: order_submit")
                    order.submit()
                    frappe.log_error(f"Auftrag für {customer} eingereicht: {order.name}", "SUCCESS: order_complete")
                    
                    # ========== NEU: AUTOMATISCHE SALES INVOICE ERSTELLUNG ==========
                    try:
                        frappe.log_error(f"Starte automatische Sales Invoice Erstellung für Sales Order: {order.name}", "INFO: auto_invoice_start")
                        
                        # Prüfe ob bereits eine Sales Invoice für diesen Sales Order existiert
                        existing_invoices = frappe.get_all(
                            "Sales Invoice",
                            filters={
                                "docstatus": ["!=", 2],
                                "sales_order": order.name  # Prüfe nur auf diesen spezifischen Sales Order
                            },
                            fields=["name", "customer"],
                            limit=1
                        )
                        
                        if not existing_invoices:
                            # Erstelle Sales Invoice basierend auf Sales Order
                            invoice_data = {
                                "doctype": "Sales Invoice",
                                "customer": order.customer,
                                "posting_date": frappe.utils.today(),
                                "due_date": frappe.utils.today(),
                                "customer_address": order.customer_address,
                                "shipping_address_name": order.shipping_address_name,
                                "po_no": order.po_no,
                                "po_date": order.transaction_date,
                                "company": order.company,
                                "currency": order.currency,
                                "selling_price_list": order.selling_price_list,
                                "sales_partner": order.sales_partner,
                                "remarks": f"Automatisch erstellt aus Sales Order: {order.name}",
                                "items": []
                            }
                            
                            # Sichere Behandlung von custom fields
                            if hasattr(order, 'custom_party_reference') and order.custom_party_reference:
                                # Prüfe ob die Party noch aktiv ist (nicht cancelled)
                                try:
                                    party_ref_doc = frappe.get_doc("Party", order.custom_party_reference)
                                    if party_ref_doc.docstatus != 2:  # Nicht cancelled
                                        invoice_data["custom_party_reference"] = order.custom_party_reference
                                    else:
                                        frappe.log_error(f"Party {order.custom_party_reference} ist cancelled - überspringe Referenz", "WARNING: cancelled_party_in_invoice")
                                except Exception as e:
                                    frappe.log_error(f"Fehler beim Laden der Party {order.custom_party_reference}: {str(e)}", "WARNING: party_ref_load_error")
                                    
                            if hasattr(order, 'custom_calculated_shipping_cost') and order.custom_calculated_shipping_cost:
                                invoice_data["custom_calculated_shipping_cost"] = order.custom_calculated_shipping_cost
                            
                            # Kopiere alle Items vom Sales Order
                            for item in order.items:
                                invoice_item = {
                                    "doctype": "Sales Invoice Item",
                                    "item_code": item.item_code,
                                    "item_name": item.item_name,
                                    "description": item.description,
                                    "qty": item.qty,
                                    "rate": item.rate,
                                    "amount": item.amount,
                                    "uom": item.uom,
                                    "conversion_factor": item.conversion_factor,
                                    "warehouse": item.warehouse,
                                    "cost_center": item.cost_center,
                                    "income_account": item.income_account,
                                    "sales_order": order.name,
                                    "so_detail": item.name
                                }
                                invoice_data["items"].append(invoice_item)
                            
                            # Erstelle die Sales Invoice
                            invoice = frappe.get_doc(invoice_data)
                            invoice.insert()
                            frappe.log_error(f"Sales Invoice erstellt: {invoice.name}", "INFO: invoice_created")
                            
                            # Reiche die Sales Invoice ein
                            invoice.submit()
                            frappe.log_error(f"Sales Invoice eingereicht: {invoice.name}", "SUCCESS: invoice_submitted")
                            
                            frappe.log_error(f"✅ Automatische Rechnung für {customer} erstellt: {invoice.name}", "SUCCESS: auto_invoice_complete")
                            
                        else:
                            frappe.log_error(f"Sales Invoice existiert bereits für Sales Order {order.name}: {existing_invoices[0]['name']}", "INFO: invoice_already_exists")
                            
                    except Exception as invoice_error:
                        frappe.log_error(f"❌ Fehler bei automatischer Rechnungserstellung für {order.name}: {str(invoice_error)}\n{frappe.get_traceback()}", "ERROR: auto_invoice_failed")
                        # Fehler nicht weiterwerfen - Sales Order soll trotzdem erfolgreich sein
                    # ========== ENDE: AUTOMATISCHE SALES INVOICE ERSTELLUNG ==========
                    
                except Exception as e:
                    frappe.log_error(f"KRITISCHER FEHLER bei Order für {customer}: {str(e)}\nTraceback: {frappe.get_traceback()}", "ERROR: order_error_detailed")
                    # Den Auftrag trotzdem zur Liste hinzufügen wenn er erstellt wurde
                    if hasattr(order, 'name') and order.name:
                        # ENTFERNT: frappe.msgprint(f"Auftrag für {customer} wurde erstellt ({order.name}), konnte aber nicht eingereicht werden: {str(e)}", alert=True)
                        created_orders.append(order.name)  # WICHTIG: Auch fehlerhafte Orders hinzufügen!
                        frappe.log_error(f"Fehlerhafter Auftrag {order.name} trotzdem hinzugefügt. Anzahl: {len(created_orders)}", "INFO: error_order_added")
                    else:
                        # ENTFERNT: frappe.msgprint(f"Auftrag für {customer} konnte nicht erstellt werden: {str(e)}", alert=True)
                        continue
                
                # Zur Liste der erstellten Aufträge hinzufügen (nur wenn nicht schon bei Fehler hinzugefügt)
                if not (hasattr(order, 'name') and order.name in created_orders):
                    created_orders.append(order.name)
                    frappe.log_error(f"Auftrag {order.name} hinzugefügt. Anzahl: {len(created_orders)}", "INFO: order_added")
                
            except Exception as e:
                frappe.log_error(f"Kritischer Fehler für {order_info.get('customer', 'Unbekannt')}: {str(e)}", "ERROR: critical_order_error")
                # Bei kritischen Fehlern den Auftrag überspringen, aber weitermachen mit den anderen
                # ENTFERNT: frappe.msgprint(f"Auftrag für {order_info.get('customer', 'Unbekannt')} konnte nicht erstellt werden: {str(e)}", alert=True)
                continue
        
        # Wenn mindestens ein Auftrag erstellt wurde, Party-Status aktualisieren
        if created_orders:
            # NEU: Erstelle Picklists (Auswahllisten) nach Versandzielen gruppiert
            try:
                frappe.log_error(f"Starte Picklist Erstellung für {len(created_orders)} Aufträge", "INFO: picklist_start")
                created_picklists = create_picklists_for_party(party_doc, all_orders_with_shipping, created_orders)
                frappe.log_error(f"Picklists erstellt: {created_picklists}", "INFO: picklists_created")
            except Exception as e:
                frappe.log_error(f"Fehler bei Picklist Erstellung: {str(e)}", "ERROR: picklist_creation")
                created_picklists = []  # Fallback für Fehlerfälle
            
            # Status auf "Abgeschlossen" setzen
            party_doc.set_status = lambda: None  # Überschreibe die Methode temporär
            party_doc.status = "Abgeschlossen"
            party_doc.save()
            party_doc.submit()
            
            # Erfolgsmeldung anzeigen
            picklist_msg = f" und {len(created_picklists)} Auswahllisten" if created_picklists else ""
            frappe.msgprint(
                f"{len(created_orders)} Aufträge wurden erfolgreich erstellt und gebucht.<br><br>Das Fenster wird gleich automatisch neu geladen, um den aktuellen Status anzuzeigen.",
                title="Erfolgreich gebuchte Präsentation",
                indicator="green"
            )
        else:
            frappe.log_error(f"Keine Aufträge erstellt für Party {party}. Einträge: {len(all_orders_with_shipping)}", "ERROR: no_orders_created")
            if all_orders_with_shipping:
                frappe.log_error(f"Fehlgeschlagene Kunden: {[order.get('customer', 'Unknown') for order in all_orders_with_shipping]}", "ERROR: failed_customers")
            # ENTFERNT: frappe.msgprint("Es wurden keine Aufträge erstellt. Bitte prüfe die Logs und versuche es erneut.", alert=True)
        
        frappe.db.commit()
        frappe.log_error(f"create_invoices beendet. Rückgabe: {created_orders}", "INFO: function_end")
        
        # WICHTIG: Räume das skip_total_calculation Flag auf, damit es nicht hängen bleibt
        if hasattr(party_doc, 'skip_total_calculation'):
            delattr(party_doc, 'skip_total_calculation')
            frappe.log_error("skip_total_calculation Flag aufgeräumt", "INFO: flag_cleanup")
        
        # === FILTER FÜR STÖRENDE _SERVER_MESSAGES ===
        # Entferne die störenden "Adresse -100539 nicht gefunden" Meldungen
        # bevor sie an das Frontend gesendet werden
        if hasattr(frappe.local, 'message_log') and frappe.local.message_log:
            original_count = len(frappe.local.message_log)
            frappe.local.message_log = [
                msg for msg in frappe.local.message_log 
                if not (
                    isinstance(msg, dict) and 
                    msg.get('message') and 
                    isinstance(msg['message'], str) and
                    (
                        ('adresse' in msg['message'].lower() and 'nicht gefunden' in msg['message'].lower()) or
                        ('address' in msg['message'].lower() and 'not found' in msg['message'].lower()) or
                        (msg['message'].startswith('Adresse -') and 'nicht gefunden' in msg['message'])
                    )
                )
            ]
            filtered_count = original_count - len(frappe.local.message_log)
            if filtered_count > 0:
                frappe.log_error(f"FILTERED: {filtered_count} störende Adressmeldungen entfernt", "INFO: messages_filtered")
        
        return created_orders
        
    except Exception as e:
        # Bei Fehlern Rollback und Fehlermeldung
        frappe.db.rollback()
        frappe.log_error(f"Allgemeiner Fehler: {str(e)}\n{frappe.get_traceback()}", f"ERROR: Auftragserstellung für Party {party}")
        
        # WICHTIG: Auch bei Fehlern das Flag aufräumen
        try:
            if hasattr(party_doc, 'skip_total_calculation'):
                delattr(party_doc, 'skip_total_calculation')
                frappe.log_error("skip_total_calculation Flag bei Fehler aufgeräumt", "INFO: error_flag_cleanup")
        except:
            pass  # Falls party_doc nicht existiert, ignoriere den Fehler
        
        # Wenn der Aufruf aus before_submit kommt, müssen wir den Fehler einfach weiterreichen
        if from_submit:
            raise e
        else:
            # Nur bei direktem Aufruf über die API eine Fehlermeldung anzeigen
            frappe.throw(f"Fehler beim Erstellen der Aufträge: {str(e)}")

@frappe.whitelist()
def cancel_multiple_parties(parties):
    """
    Bricht mehrere Parties gleichzeitig ab
    Args:
        parties: Eine kommagetrennte Liste von Party-Namen
    """
    if not parties:
        return
        
    # String in Liste umwandeln
    if isinstance(parties, str):
        party_list = parties.split(",")
    else:
        party_list = parties
    
    cancelled_count = 0
    failed_count = 0
    for party_name in party_list:
        try:
            # Party-Dokument laden
            party_doc = frappe.get_doc("Party", party_name)
            
            # Nur Dokumente im Status "Gäste" oder "Produkte" können abgebrochen werden
            if party_doc.docstatus == 0 and party_doc.status in ["Gäste", "Produkte"]:
                party_doc.status = "Cancelled"
                party_doc.save()
                cancelled_count += 1
            elif party_doc.docstatus == 1:
                # Wenn das Dokument bereits eingereicht wurde, führe ein Cancel durch
                party_doc.cancel()
                cancelled_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            frappe.log_error(f"Fehler beim Abbrechen der Party {party_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: cancel_party")
            failed_count += 1
            
    frappe.db.commit()
    
    # Rückgabe
    return {
        "cancelled": cancelled_count,
        "failed": failed_count,
        "total": len(party_list)
    }

# Einfache Funktion zum Finden vorhandener Adressen (OHNE automatische Erstellung)
def find_existing_address(customer_name, preferred_type="Billing"):
    """
    Findet eine vorhandene Adresse für einen Kunden
    - preferred_type: "Billing" oder "Shipping" 
    - Falls preferred_type nicht gefunden wird, nimm andere verfügbare Adresse
    - NIEMALS neue Adressen erstellen!
    - ERWEITERT: Sucht auch in Contact-verknüpften Adressen
    """
    frappe.log_error(f"=== find_existing_address START: Customer='{customer_name}', Type='{preferred_type}' ===", "DEBUG: find_address_start")
    
    try:
        # Prüfen, ob der Customer überhaupt existiert
        if not frappe.db.exists("Customer", customer_name):
            frappe.log_error(f"❌ Customer '{customer_name}' existiert nicht!", "ERROR: find_address")
            return None
        
        frappe.log_error(f"✅ Customer '{customer_name}' existiert", "DEBUG: customer_exists")
        
        # Hole den echten Kundennamen für bessere Fehlermeldungen
        customer_doc = frappe.get_doc("Customer", customer_name)
        display_name = customer_doc.customer_name or customer_name
        frappe.log_error(f"Customer Display Name: '{display_name}'", "DEBUG: customer_name")
        
        # ERWEITERT: Finde alle Adressen für diesen Kunden (Customer + Contact Links)
        address_links = []
        
        # 1. Direkte Customer-Links
        frappe.log_error(f"Suche direkte Customer-Links für '{customer_name}'...", "DEBUG: search_customer_links")
        customer_links = frappe.get_all(
            "Dynamic Link",
            filters={"link_doctype": "Customer", "link_name": customer_name},
            fields=["parent"]
        )
        frappe.log_error(f"Gefunden: {len(customer_links)} direkte Customer-Links: {[link['parent'] for link in customer_links]}", "DEBUG: customer_links_found")
        address_links.extend(customer_links)
        
        # 2. Contact-Links (Adressen die über Kontakte verknüpft sind)
        try:
            frappe.log_error(f"Suche Contact-Links für '{customer_name}'...", "DEBUG: search_contact_links")
            contact_links = frappe.get_all(
                "Dynamic Link", 
                filters={"link_doctype": "Contact"},
                fields=["parent", "link_name"]
            )
            frappe.log_error(f"Alle Contact-Links gefunden: {len(contact_links)}", "DEBUG: all_contacts")
            
            # Prüfe welche Kontakte zu diesem Customer gehören
            contact_count = 0
            for contact_link in contact_links:
                if contact_link.parent and frappe.db.exists("Contact", contact_link.link_name):
                    # Prüfe, ob dieser Contact mit unserem Customer verknüpft ist
                    contact_customer_links = frappe.get_all(
                        "Dynamic Link",
                        filters={
                            "parent": contact_link.link_name,
                            "parenttype": "Contact", 
                            "link_doctype": "Customer",
                            "link_name": customer_name
                        },
                        fields=["parent"]
                    )
                    
                    if contact_customer_links:
                        # Dieser Contact gehört zu unserem Customer, also verwende seine Adresse
                        address_links.append({"parent": contact_link.parent})
                        contact_count += 1
                        frappe.log_error(f"✅ Contact-Adresse #{contact_count} gefunden für '{display_name}': {contact_link.parent}", "INFO: contact_address_found")
            
            frappe.log_error(f"Gefunden: {contact_count} Contact-Adressen für '{customer_name}'", "DEBUG: contact_summary")
        except Exception as e:
            frappe.log_error(f"❌ Fehler beim Suchen von Contact-Adressen für '{display_name}': {str(e)}", "WARNING: contact_search_error")
        
        # Entferne Duplikate
        unique_addresses = list({link["parent"]: link for link in address_links if link.get("parent")}.values())
        frappe.log_error(f"Unique Adressen gefunden: {len(unique_addresses)} - {[link['parent'] for link in unique_addresses]}", "DEBUG: unique_addresses")
        
        if not unique_addresses:
            frappe.log_error(f"❌ Keine Adressen für Customer '{display_name}' gefunden", "WARNING: no_addresses")
            return None
        
        # Sammle Adressen nach Typ
        preferred_addresses = []
        other_addresses = []
        
        frappe.log_error(f"Analysiere {len(unique_addresses)} Adressen nach Typ '{preferred_type}'...", "DEBUG: analyze_addresses")
        
        for i, link in enumerate(unique_addresses):
            try:
                addr_name = link["parent"]
                frappe.log_error(f"Lade Adresse #{i+1}: {addr_name}...", "DEBUG: load_address")
                addr = frappe.get_doc("Address", addr_name)
                
                # Prüfe, ob die Adresse vollständig ist
                if not addr.address_line1 or not addr.city or not addr.country:
                    frappe.log_error(f"❌ Unvollständige Adresse #{i+1} für '{display_name}': {addr.name} (Line1: {bool(addr.address_line1)}, City: {bool(addr.city)}, Country: {bool(addr.country)})", "WARNING: incomplete_address")
                    continue
                
                frappe.log_error(f"✅ Vollständige Adresse #{i+1}: {addr.name}, Typ: {addr.address_type}", "DEBUG: complete_address")
                    
                if addr.address_type == preferred_type:
                    preferred_addresses.append(addr.name)
                    frappe.log_error(f"✅ {preferred_type}-Adresse gefunden: {addr.name}", "DEBUG: preferred_found")
                else:
                    other_addresses.append(addr.name)
                    frappe.log_error(f"📋 Andere Adresse gefunden: {addr.name} (Typ: {addr.address_type})", "DEBUG: other_found")
            except Exception as e:
                frappe.log_error(f"❌ Fehler beim Laden der Adresse {link['parent']}: {str(e)}", "ERROR: load_address")
                continue
        
        # Rückgabe-Logik
        frappe.log_error(f"Adress-Analyse abgeschlossen: {len(preferred_addresses)} {preferred_type}, {len(other_addresses)} andere", "DEBUG: analysis_complete")
        
        if preferred_addresses:
            result = preferred_addresses[0]
            frappe.log_error(f"🎯 RÜCKGABE: {preferred_type}-Adresse für '{display_name}': {result}", "INFO: address_found")
            return result
        elif other_addresses:
            result = other_addresses[0]
            frappe.log_error(f"🔄 RÜCKGABE: Fallback-Adresse für '{display_name}': {result} (kein {preferred_type} gefunden)", "INFO: address_fallback")
            return result
        else:
            frappe.log_error(f"❌ RÜCKGABE: None - Keine verwendbaren Adressen für '{display_name}' gefunden", "WARNING: no_usable_address")
            return None
            
    except Exception as e:
        frappe.log_error(f"❌ Kritischer Fehler beim Suchen von Adressen für '{customer_name}': {str(e)}\n{frappe.get_traceback()}", "ERROR: find_address_error")
        return None
    
    finally:
        frappe.log_error(f"=== find_existing_address ENDE für '{customer_name}' ===", "DEBUG: find_address_end")

def create_picklists_for_party(party_doc, all_orders_with_shipping, created_order_names):
	"""
	Erstellt Picklists (Auswahllisten) gruppiert nach Versandziel
	WICHTIG: Aufträge werden NICHT vermischt - jeder Sales Order behält seine eigenen Items
	NEU: Zeigt Rechnungsnummern im Header an
	
	Args:
		party_doc: Das Party-Dokument
		all_orders_with_shipping: Liste der Order-Infos mit Versandziel
		created_order_names: Liste der tatsächlich erstellten Sales Order Namen
	
	Returns:
		Liste der erstellten Picklist Namen
	"""
	try:
		frappe.log_error(f"🎯 create_picklists_for_party gestartet", "INFO: picklist_function")
		
		# Gruppiere nach Versandziel
		shipping_groups = {}
		
		# Erstelle ein Mapping von Customer zu Sales Order Name
		for order_info in all_orders_with_shipping:
			customer = order_info["customer"]
			shipping_target = order_info["shipping_target"]
			
			# Finde den entsprechenden Sales Order Namen
			sales_order_name = None
			for order_name in created_order_names:
				try:
					order_doc = frappe.get_doc("Sales Order", order_name)
					if order_doc.customer == customer:
						sales_order_name = order_name
						break
				except:
					continue
			
			if sales_order_name:
				if shipping_target not in shipping_groups:
					shipping_groups[shipping_target] = []
				shipping_groups[shipping_target].append({
					"customer": customer,
					"sales_order": sales_order_name,
					"order_info": order_info
				})
		
		frappe.log_error(f"📦 Picklist Shipping Groups: {list(shipping_groups.keys())}", "INFO: picklist_groups")
		
		created_picklists = []
		
		# Erstelle eine Picklist pro Versandziel
		for shipping_target, orders_for_target in shipping_groups.items():
			try:
				frappe.log_error(f"🏭 Erstelle Picklist für Versandziel: {shipping_target}", "INFO: creating_picklist")
				
				# Sammle alle Items für dieses Versandziel (OHNE Vermischung!)
				all_picklist_items = []
				invoice_data = []  # Ändere zu Liste mit Customer-Info
				order_numbers = []
				
				for order_data in orders_for_target:
					customer = order_data["customer"]
					sales_order_name = order_data["sales_order"]
					order_info = order_data["order_info"]
					
					order_numbers.append(sales_order_name)
					
					# Finde Sales Invoices für diesen Sales Order
					try:
						frappe.log_error(f"🔍 Suche Sales Invoices für SO: {sales_order_name}", "DEBUG: invoice_search_start")
						current_invoices = frappe.get_all(
							"Sales Invoice",
							filters={
								"sales_order": sales_order_name,
								"docstatus": 1  # Nur eingereichte Rechnungen
							},
							fields=["name"]  # order_by entfernt - verursacht SQL Fehler
						)
						
						frappe.log_error(f"📋 Gefundene Invoices für SO {sales_order_name}: {len(current_invoices)} - {[inv.name for inv in current_invoices]}", "DEBUG: invoice_search_result")
						
						for inv in current_invoices:
							# Sammle Invoice mit Kundenname
							customer_name = customer
							try:
								customer_doc = frappe.get_doc("Customer", customer)
								customer_display_name = customer_doc.customer_name or customer
							except:
								customer_display_name = customer
							
							invoice_with_customer = f"{inv.name} ({customer_display_name})"
							invoice_data.append(invoice_with_customer)
							frappe.log_error(f"💳 Sales Invoice für SO {sales_order_name} gefunden: {invoice_with_customer}", "INFO: invoice_found_for_picklist")
							
					except Exception as e:
						frappe.log_error(f"⚠️ Fehler beim Finden der Sales Invoice für {sales_order_name}: {str(e)}", "WARNING: invoice_search")
					
					# Hole den Sales Order für Warehouse-Info
					try:
						so_doc = frappe.get_doc("Sales Order", sales_order_name)
					except:
						frappe.log_error(f"❌ Sales Order {sales_order_name} nicht gefunden", "ERROR: so_not_found")
						continue
					
					# Füge alle Produkte dieses Kunden hinzu (OHNE Vermischung mit anderen!)
					for product in order_info["products"]:
						# Überspringe Versandartikel für die Picklist (nur echte Produkte)
						if product.get("_shipping_item", False):
							frappe.log_error(f"📦 Versandartikel übersprungen für Picklist: {product['item_code']}", "INFO: shipping_item_skipped")
							continue
						
						# Finde das entsprechende SO Item für Warehouse
						so_warehouse = product.get("warehouse", get_default_warehouse())
						so_item_name = None
						for so_item in so_doc.items:
							if so_item.item_code == product["item_code"] and so_item.qty == product["qty"]:
								so_warehouse = so_item.warehouse or get_default_warehouse()
								so_item_name = so_item.name  # Wichtig: Sales Order Item Reference!
								break
						
						picklist_item = {
							"doctype": "Pick List Item",  # WICHTIG: DocType
							"item_code": product["item_code"],
							"item_name": product["item_name"],
							"qty": float(product["qty"]),  # WICHTIG: Als Float!
							"stock_qty": float(product.get("stock_qty", product["qty"])),
							"picked_qty": 0.0,  # Standardwert
							"stock_reserved_qty": 0.0,  # Standardwert  
							"uom": product.get("uom", "Stk"),
							"stock_uom": product.get("stock_uom", "Stk"),
							"conversion_factor": float(product.get("conversion_factor", 1.0)),
							"warehouse": so_warehouse,
							"sales_order": sales_order_name,
							"sales_order_item": so_item_name,  # WICHTIG: SO Item Reference
							"batch_no": None,
							"serial_no": None,
							"use_serial_batch_fields": 0,  # Standardwert
							"serial_and_batch_bundle": None,  # Standardwert
							"product_bundle_item": None,  # Standardwert
							"material_request": None,  # Standardwert
							"material_request_item": None  # Standardwert
						}
						
						all_picklist_items.append(picklist_item)
						frappe.log_error(f"✅ Picklist Item hinzugefügt: {product['item_code']} (SO: {sales_order_name}, SO-Item: {so_item_name}, Customer: {customer})", "INFO: picklist_item_added")
				
				if not all_picklist_items:
					frappe.log_error(f"⚠️ Keine Items für Versandziel {shipping_target} gefunden", "WARNING: no_picklist_items")
					continue
				
				# Entferne Duplikate und sortiere
				invoice_data = list(set(invoice_data))
				order_numbers = list(set(order_numbers))
				
				# Erstelle Header-Bemerkung mit Rechnungsnummern im Fokus
				if invoice_data:
					invoice_text = "\n".join(sorted(invoice_data))  # Zeilenumbruch statt Komma
					# Einfache remarks - Details stehen im Custom Field
					remarks = f"Party: {party_doc.name} | {len(invoice_data)} Rechnungen"
					frappe.log_error(f"✅ Picklist mit {len(invoice_data)} Rechnungen erstellt", "INFO: picklist_created_with_invoices")
				else:
					# Fallback falls keine Rechnungen gefunden
					order_text = ", ".join(sorted(order_numbers))
					remarks = f"Party: {party_doc.name} | {len(order_numbers)} Aufträge"
					frappe.log_error(f"⚠️ Picklist ohne Rechnungen - {len(order_numbers)} Aufträge", "WARNING: picklist_no_invoices")
				
				# Picklist Daten
				picklist_data = {
					"doctype": "Pick List",
					"purpose": "Delivery",
					"company": frappe.defaults.get_user_default("Company"),
					"customer": shipping_target,  # Das Versandziel als Customer
					"custom_invoice_references": "\n".join(sorted(invoice_data)) if invoice_data else None,  # Zeilenumbruch statt Komma!
					"remarks": remarks,  # Zusätzlich in Bemerkungen
					"locations": all_picklist_items  # DIREKT verwenden!
				}
				
				frappe.log_error(f"🎯 Erstelle Picklist für {shipping_target} mit {len(all_picklist_items)} Items", "INFO: picklist_creation")
				
				# Erstelle Picklist
				picklist = frappe.get_doc(picklist_data)
				picklist.insert()
				frappe.log_error(f"✅ Picklist erstellt: {picklist.name}", "SUCCESS: picklist_created")
				
				# Reiche die Picklist ein
				try:
					picklist.submit()
					frappe.log_error(f"🎉 Picklist eingereicht: {picklist.name}", "SUCCESS: picklist_submitted")
				except Exception as e:
					frappe.log_error(f"⚠️ Picklist konnte nicht eingereicht werden: {str(e)}", "WARNING: picklist_submit_failed")
					# Trotzdem weitermachen - Picklist ist erstellt
				
				created_picklists.append(picklist.name)
				
			except Exception as e:
				frappe.log_error(f"❌ Fehler beim Erstellen der Picklist für {shipping_target}: {str(e)}", "ERROR: picklist_creation_error")
				continue
		
		frappe.log_error(f"🎉 Picklists erstellt: {created_picklists}", "SUCCESS: all_picklists_created")
		return created_picklists
		
	except Exception as e:
		frappe.log_error(f"💥 Allgemeiner Fehler in create_picklists_for_party: {str(e)}\n{frappe.get_traceback()}", "ERROR: picklist_function_error")
		return []

