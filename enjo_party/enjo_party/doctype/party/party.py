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
			frappe.msgprint("Party hat bereits zugeordnete Aufträge. Es werden keine neuen erstellt.", alert=True)
			return
			
		frappe.msgprint("Party wird eingereicht und Aufträge werden erstellt...", alert=True)
		
		# Aufträge erstellen beim Submit - aber ohne weitere Fehlerbehandlung
		try:
			orders = create_invoices(self.name, from_submit=True)
			if not orders:
				frappe.throw(
					"Es konnten keine Aufträge erstellt werden. "
					"Bitte prüfe, ob Produkte ausgewählt wurden und versuche es erneut."
				)
			
			# Erfolgsmeldung
			frappe.msgprint(f"Es wurden erfolgreich {len(orders)} Aufträge erstellt!", alert=True)
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

@frappe.whitelist()
def create_invoices(party, from_submit=False, from_button=False):
    """
    Erstellt Aufträge für alle Teilnehmer einer Party
    Hinweis: Die Funktion heißt weiterhin create_invoices für die Kompatibilität mit JavaScript
    """
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
            frappe.msgprint("Diese Party hat bereits Aufträge. Es werden keine neuen Aufträge erstellt.", alert=True)
            return existing_orders
        
        # Wenn die Funktion sowohl von before_submit als auch vom Button aufgerufen wird, 
        # verhindere Doppelausführung
        if from_button and from_submit:
            frappe.log_error("Verhinderte doppelte Ausführung (from_button und from_submit sind beide True)", "DEBUG: create_orders")
            return []
        
        # Firmeneinstellungen überprüfen
        company = frappe.defaults.get_user_default("Company")
        if not company:
            frappe.log_error("Keine Standard-Firma gefunden!", "ERROR: create_orders")
            frappe.throw("Bitte legen Sie eine Standard-Firma in Ihren Einstellungen fest.")
            
        # Währung überprüfen
        currency = frappe.defaults.get_user_default("Currency")
        if not currency:
            frappe.log_error("Keine Standard-Währung gefunden!", "ERROR: create_orders")
            frappe.throw("Bitte legen Sie eine Standard-Währung in Ihren Einstellungen fest.")
            
        # Party-Dokument laden
        try:
            party_doc = frappe.get_doc("Party", party)
        except Exception as e:
            frappe.log_error(f"Party-Dokument konnte nicht geladen werden: {str(e)}", "ERROR: create_orders")
            frappe.throw("Das Party-Dokument konnte nicht geladen werden.")
        
        # Prüfen, ob die Party bereits abgeschlossen ist
        if party_doc.status == "Abgeschlossen" and party_doc.docstatus == 1:
            frappe.msgprint("Diese Party ist bereits abgeschlossen und hat wahrscheinlich bereits Aufträge.", alert=True)
            return []
        
        # Gästeliste prüfen
        if not party_doc.kunden or len(party_doc.kunden) < 3:
            frappe.throw("Es müssen mindestens 3 Gäste/Kunden zur Party hinzugefügt werden.")
            
        # Prüfe, ob die Gastgeberin existiert
        if not party_doc.gastgeberin:
            frappe.throw("Es wurde keine Gastgeberin angegeben.")
        
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
            
        # Stelle sicher, dass für die Gastgeberin eine Adresse existiert
        gastgeberin_address = get_or_create_address(party_doc.gastgeberin, "Shipping")
        
        # Erstelle eine Liste für die erstellten Aufträge
        created_orders = []
        
        # Prüfe, ob Produkte für Gastgeberin vorhanden sind
        if hasattr(party_doc, "produktauswahl_für_gastgeberin") and party_doc.produktauswahl_für_gastgeberin:
            hat_produkte = False
            produkte_gastgeberin = []
            
            for produkt in party_doc.produktauswahl_für_gastgeberin:
                if produkt.item_code and produkt.qty and produkt.qty > 0:
                    hat_produkte = True
                    produkte_gastgeberin.append({
                        "item_code": produkt.item_code,
                        "qty": produkt.qty,
                        "rate": produkt.rate or 0
                    })
            
            # Wenn Produkte vorhanden sind, erstelle Auftrag für Gastgeberin
            if hat_produkte:
                try:
                    # Adresse besorgen
                    billing_address = get_or_create_address(party_doc.gastgeberin, "Billing")
                    shipping_address = get_or_create_address(party_doc.gastgeberin, "Shipping")
                    
                    # Auftragsdaten
                    order_data = {
                        "doctype": "Sales Order",
                        "customer": party_doc.gastgeberin,
                        "transaction_date": today(),
                        "delivery_date": today(),
                        "items": produkte_gastgeberin,
                        "customer_address": billing_address,
                        "shipping_address_name": shipping_address,
                        "remarks": f"Erstellt aus Party: {party}",
                        "po_no": party,  # Party-Referenz in po_no speichern
                        "company": company,
                        "currency": currency,
                        "status": "Draft",
                        "order_type": "Sales"
                    }
                    
                    # Auftrag erstellen
                    order = frappe.get_doc(order_data)
                    order.insert()
                    
                    # Versuche den Auftrag einzureichen
                    try:
                        order.submit()
                        frappe.log_error(f"Auftrag für Gastgeberin {party_doc.gastgeberin} erstellt und eingereicht", "INFO: Auftragserstellung")
                    except Exception as e:
                        frappe.log_error(f"Auftrag für Gastgeberin {party_doc.gastgeberin} konnte nicht eingereicht werden: {str(e)}", "ERROR: Auftrag Submit")
                        # Den Auftrag trotzdem zur Liste hinzufügen, da er erstellt wurde
                        frappe.msgprint(f"Auftrag für {party_doc.gastgeberin} wurde erstellt, konnte aber nicht eingereicht werden: {str(e)}", alert=True)
                    
                    # Zur Liste der erstellten Aufträge hinzufügen
                    created_orders.append(order.name)
                except Exception as e:
                    frappe.log_error(f"Fehler bei Auftragserstellung für Gastgeberin: {str(e)}\n{frappe.get_traceback()}", 
                                    "ERROR: Auftragserstellung Gastgeberin")
        
        # Für jeden Gast prüfen
        for idx, kunde_row in enumerate(party_doc.kunden):
            try:
                if not kunde_row.kunde:
                    continue
                    
                index = idx + 1
                field_name = f"produktauswahl_für_gast_{index}"
                
                # Prüfen ob die Tabelle existiert
                if not hasattr(party_doc, field_name) or not getattr(party_doc, field_name):
                    continue
                
                produkte_gast = []
                for produkt in getattr(party_doc, field_name):
                    if produkt.item_code and produkt.qty and produkt.qty > 0:
                        produkte_gast.append({
                            "item_code": produkt.item_code,
                            "qty": produkt.qty,
                            "rate": produkt.rate or 0
                        })
                
                # Wenn keine Produkte vorhanden sind, überspringe diesen Gast
                if not produkte_gast:
                    continue
                
                # Adresse besorgen
                billing_address = get_or_create_address(kunde_row.kunde, "Billing")
                shipping_address = get_or_create_address(kunde_row.kunde, "Shipping")
                
                # Auftragsdaten
                order_data = {
                    "doctype": "Sales Order",
                    "customer": kunde_row.kunde,
                    "transaction_date": today(),
                    "delivery_date": today(),
                    "items": produkte_gast,
                    "customer_address": billing_address,
                    "shipping_address_name": shipping_address,
                    "remarks": f"Erstellt aus Party: {party}",
                    "po_no": party,  # Party-Referenz in po_no speichern
                    "company": company,
                    "currency": currency,
                    "status": "Draft",
                    "order_type": "Sales"
                }
                
                # Auftrag erstellen
                order = frappe.get_doc(order_data)
                order.insert()
                
                # Versuche den Auftrag einzureichen
                try:
                    order.submit()
                    frappe.log_error(f"Auftrag für Gast {kunde_row.kunde} erstellt und eingereicht", "INFO: Auftragserstellung")
                except Exception as e:
                    frappe.log_error(f"Auftrag für Gast {kunde_row.kunde} konnte nicht eingereicht werden: {str(e)}", "ERROR: Auftrag Submit")
                    # Den Auftrag trotzdem zur Liste hinzufügen, da er erstellt wurde
                    frappe.msgprint(f"Auftrag für {kunde_row.kunde} wurde erstellt, konnte aber nicht eingereicht werden: {str(e)}", alert=True)
                
                # Zur Liste der erstellten Aufträge hinzufügen
                created_orders.append(order.name)
                
            except Exception as e:
                frappe.log_error(f"Fehler bei Auftragserstellung für Gast {idx+1}/{kunde_row.kunde}: {str(e)}\n{frappe.get_traceback()}", 
                               "ERROR: Auftragserstellung Gast")
        
        # Wenn mindestens ein Auftrag erstellt wurde, Party-Status aktualisieren
        if created_orders:
            # Status auf "Abgeschlossen" setzen
            party_doc.status = "Abgeschlossen"
            
            # Party-Dokument abschließen/einreichen (submit), aber nur wenn 
            # die Funktion nicht aus before_submit aufgerufen wurde
            if party_doc.docstatus == 0 and not from_submit:
                try:
                    # Party speichern und submitten
                    party_doc.save()
                    party_doc.submit()
                    frappe.db.commit()
                    frappe.msgprint("Party wurde erfolgreich abgeschlossen und eingereicht.", alert=True)
                except Exception as e:
                    frappe.log_error(f"Party konnte nicht eingereicht werden: {str(e)}", "ERROR: Party Submit")
                    frappe.msgprint(f"Aufträge wurden erstellt, aber die Party konnte nicht eingereicht werden: {str(e)}", alert=True)
            
            # Erfolgsmeldung anzeigen
            frappe.msgprint(f"Es wurden {len(created_orders)} Aufträge erfolgreich erstellt und eingereicht.", alert=True)
        else:
            frappe.msgprint("Es wurden keine Aufträge erstellt. Bitte prüfe, ob Produkte für mindestens einen Kunden ausgewählt wurden.", alert=True)
        
        frappe.db.commit()
        return created_orders
        
    except Exception as e:
        # Bei Fehlern Rollback und Fehlermeldung
        frappe.db.rollback()
        frappe.log_error(f"Allgemeiner Fehler: {str(e)}\n{frappe.get_traceback()}", f"ERROR: Auftragserstellung für Party {party}")
        
        # Wenn der Aufruf aus before_submit kommt, müssen wir den Fehler einfach weiterreichen
        if from_submit:
            raise e
        else:
            # Nur bei direktem Aufruf über die API eine Fehlermeldung anzeigen
            frappe.throw(f"Fehler beim Erstellen der Aufträge: {str(e)}")
