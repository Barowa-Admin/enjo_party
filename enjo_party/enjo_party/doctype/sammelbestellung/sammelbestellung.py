# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


def get_default_warehouse():
    """
    Holt das Standard-Lager für das aktuelle Unternehmen.
    """
    try:
        company = frappe.defaults.get_global_default("company")
        if company:
            # Versuche das Standard-Lager für das Unternehmen zu finden
            warehouse = frappe.db.get_value("Warehouse", 
                {"company": company, "is_group": 0}, 
                "name", 
                order_by="creation desc")
            if warehouse:
                return warehouse
        
        # Fallback: Erstes verfügbares Lager
        warehouse = frappe.db.get_value("Warehouse", 
            {"is_group": 0}, 
            "name", 
            order_by="creation desc")
        if warehouse:
            return warehouse
            
        # Letzter Fallback
        return "Stores - " + (company or "Default")
        
    except Exception:
        return "Stores - Default"


def should_add_separator_for_customer(customer, order_info_list, partnerin=None):
    """
    Prüft, ob für einen Kunden ein Trenner hinzugefügt werden soll.
    
    Trenner werden NUR hinzugefügt für:
    - Echte Kunden/Gäste mit Produkten
    - NICHT für Vertriebspartner (partnerin)
    - NICHT wenn der Kunde nur Versandkosten-Artikel hat
    
    Args:
        customer: Der Kunde
        order_info_list: Liste von order_info Dictionaries mit 'products'
        partnerin: Optional - Name der Partnerin (Sales Partner)
    
    Returns:
        True wenn Trenner hinzugefügt werden soll, False sonst
    """
    # Prüfe ob Kunde die Partnerin ist
    if partnerin and customer == partnerin:
        return False
    
    # Prüfe ob der Kunde echte Produkte hat (nicht nur Versandkosten)
    has_real_products = False
    for order_info in order_info_list:
        if order_info.get('customer') == customer:
            products = order_info.get('products', [])
            for product in products:
                item_code = product.get('item_code', '')
                # Wenn mindestens ein Produkt NICHT shipping-* ist, hat der Kunde echte Produkte
                if item_code and not item_code.startswith('shipping-'):
                    has_real_products = True
                    break
            if has_real_products:
                break
    
    return has_real_products


class Sammelbestellung(Document):
	def before_validate(self):
		"""
		WICHTIG: Diese Funktion läuft VOR allen Frappe Core-Validierungen!
		Entferne leere Zeilen BEVOR Sales Order Item Validierungen greifen.
		"""
		# Entferne alle komplett leeren Zeilen aus den Produkttabellen BEVOR Frappe sie validiert
		self.remove_empty_product_rows()

	def before_save(self):
		# Wenn es ein neues Dokument ist, wird der Name erst nach dem Speichern generiert
		if self.is_new():
			# Setze sammelbestellung_name auf None, wird nach dem Einfügen gesetzt
			self.sammelbestellung_name = None
		
		# Status automatisch setzen
		self.set_status()
		
		# Ersten Kunden setzen
		self.set_erster_kunde()
	
	def set_erster_kunde(self):
		"""Setzt den Namen des ersten Kunden aus der Kunden-Tabelle"""
		if self.kunden and len(self.kunden) > 0:
			erster_kunde_id = self.kunden[0].kunde
			if erster_kunde_id:
				try:
					customer = frappe.get_cached_value("Customer", erster_kunde_id, "customer_name")
					self.erster_kunde = customer or erster_kunde_id
				except:
					self.erster_kunde = erster_kunde_id
		else:
			self.erster_kunde = None

	def remove_empty_product_rows(self):
		"""
		Entferne alle unvollständigen Zeilen aus den Produkttabellen.
		Eine Zeile ist nur gültig, wenn sie einen item_code UND qty > 0 hat.
		Alle anderen Zeilen werden entfernt (auch solche mit qty aber ohne item_code).
		"""
		# Kunden-Tabellen bereinigen
		for i in range(1, 16):
			field_name = f'produktauswahl_für_kunde_{i}'
			if hasattr(self, field_name):
				current_table = getattr(self, field_name)
				if current_table:
					original_count = len(current_table)
					cleaned_table = [
						row for row in current_table 
						if (row.item_code and row.item_code.strip()) and (row.qty and row.qty > 0)
					]
					setattr(self, field_name, cleaned_table)
					removed_count = original_count - len(cleaned_table)
					if removed_count > 0:
						frappe.log_error(f"Entfernt {removed_count} unvollständige Zeilen aus {field_name}", "INFO: remove_empty_rows")

	def after_insert(self):
		# Nach dem Einfügen den sammelbestellung_name auf den generierten Namen setzen
		self.db_set("sammelbestellung_name", self.name, update_modified=False)
		
	def validate(self):
		frappe.log_error(f"=== VALIDATE START für {self.name} - skip_flag: {getattr(self, 'skip_total_calculation', False)} ===", "DEBUG: validate_start")
		
		# NEUE LOGIK: Prüfe globalen Flag über frappe.local.flags
		# Dieser wird durch JavaScript-Speichern NICHT überschrieben
		skip_calculation = getattr(self, 'skip_total_calculation', False) or frappe.local.flags.get('skip_sammelbestellung_total_calculation', False)
		frappe.log_error(f"=== ERWEITERTE PRÜFUNG für {self.name} - dokument_flag: {getattr(self, 'skip_total_calculation', False)}, global_flag: {frappe.local.flags.get('skip_sammelbestellung_total_calculation', False)}, final_skip: {skip_calculation} ===", "DEBUG: validate_flags")
		
		# Stelle sicher, dass UOM Conversion Factor in allen Produkttabellen gesetzt ist
		frappe.log_error("Starte set_uom_conversion_factor", "DEBUG: validate_step")
		self.set_uom_conversion_factor()
		frappe.log_error("set_uom_conversion_factor abgeschlossen", "DEBUG: validate_step")
		
		# Berechne Gesamtumsatz NUR wenn nicht in Aufträge-Erstellung
		if not skip_calculation:
			frappe.log_error("Starte calculate_totals", "DEBUG: validate_step")
			self.calculate_totals()
			frappe.log_error("calculate_totals abgeschlossen", "DEBUG: validate_step")
		else:
			frappe.log_error("calculate_totals übersprungen (skip_flag gesetzt)", "DEBUG: validate_step")
		
		# Prüfe auf doppelte Kunden
		frappe.log_error("Starte validate_kunden_duplicates", "DEBUG: validate_step")
		self.validate_kunden_duplicates()
		frappe.log_error("validate_kunden_duplicates abgeschlossen", "DEBUG: validate_step")
		
		# NEUE ADRESSVALIDIERUNG: Prüfe alle Adressen VOR der Produktvalidierung
		# ABER NUR wenn nicht in Aufträge-Erstellung (skip_total_calculation Flag)
		if not skip_calculation:
			frappe.log_error("Starte validate_all_addresses", "DEBUG: validate_step")
			self.validate_all_addresses()
			frappe.log_error("validate_all_addresses abgeschlossen", "DEBUG: validate_step")
		else:
			frappe.log_error("validate_all_addresses übersprungen (skip_flag gesetzt)", "DEBUG: validate_step")
		
		# Prüfe, dass alle Kunden Produkte ausgewählt haben (nur wenn nicht neu UND nicht in Aufträge-Erstellung)
		if not self.is_new() and not skip_calculation:
			frappe.log_error("Starte validate_all_customers_have_products", "DEBUG: validate_step")
			self.validate_all_customers_have_products()
			frappe.log_error("validate_all_customers_have_products abgeschlossen", "DEBUG: validate_step")
		else:
			frappe.log_error("validate_all_customers_have_products übersprungen (neu oder skip_flag gesetzt)", "DEBUG: validate_step")
		
		frappe.log_error(f"=== VALIDATE ENDE für {self.name} ===", "DEBUG: validate_end")
	
	def before_submit(self):
		"""
		Vor dem Einreichen der Sammelbestellung automatisch Aufträge erstellen,
		falls noch keine existieren
		"""
		# Prüfen, ob bereits Aufträge zu dieser Sammelbestellung existieren
		existing_orders = frappe.get_all(
			"Sales Order",
			filters={"docstatus": ["!=", 2]},
			or_filters=[
				{"po_no": self.name},
				{"customer_name": self.name}
			],
			limit=1
		)
		
		# Wenn bereits Aufträge existieren, keinen neuen erstellen
		if existing_orders:
			frappe.log_error(f"Sammelbestellung {self.name}: Bestehende Aufträge gefunden: {existing_orders}", "INFO: before_submit")
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
			frappe.throw(str(e))
	
	def validate_kunden_duplicates(self):
		"""Entferne doppelte Kunden aus der Kundenliste"""
		if not self.kunden:
			return
		
		# Prüfe auf doppelte Kunden (gleicher Kunde mehrfach)
		gesehene_kunden = set()
		duplicate_indexes = []
		for i, kunde in enumerate(self.kunden):
			if kunde.kunde:
				if kunde.kunde in gesehene_kunden:
					duplicate_indexes.append(i)
				else:
					gesehene_kunden.add(kunde.kunde)
		
		# Lösche von hinten nach vorne, um Indexproblem zu vermeiden
		for index in sorted(duplicate_indexes, reverse=True):
			self.kunden.pop(index)
		
		# Wenn Elemente entfernt wurden, eine Benachrichtigung anzeigen
		if duplicate_indexes:
			frappe.msgprint("Doppelte Kunden wurden automatisch entfernt. Jeder Kunde darf nur einmal ausgewählt werden.", alert=True)
	
	def validate_all_customers_have_products(self):
		"""
		Prüft, ob alle eingetragenen Kunden Produkte ausgewählt haben
		Erlaubt das Speichern ohne Produktvalidierung, wenn neue Kunden hinzugefügt wurden
		"""
		if not self.kunden:
			return
		
		# Wenn der Status noch "Kunden" ist, erlaube Speichern ohne Produktvalidierung
		if self.status == "Kunden":
			return
		
		# Sammle alle Teilnehmer ohne Produktauswahl
		kunden_ohne_produkte = []
		
		# Prüfe alle Kunden
		for idx, kunde_row in enumerate(self.kunden):
			if not kunde_row.kunde:
				continue
				
			index = idx + 1
			field_name = f"produktauswahl_für_kunde_{index}"
			
			# Prüfen ob die Tabelle existiert und Produkte enthält
			hat_produkte = False
			if hasattr(self, field_name) and getattr(self, field_name):
				tabelle_inhalt = getattr(self, field_name)
				frappe.log_error(f"Kunde {index} ({kunde_row.kunde}) - Anzahl Zeilen in {field_name}: {len(tabelle_inhalt)}", "DEBUG: table_check")
				
				for idx_prod, produkt in enumerate(getattr(self, field_name)):
					if produkt.item_code:
						frappe.log_error(f"  Zeile {idx_prod}: item_code={produkt.item_code}, qty={produkt.qty}, rate={produkt.rate}", "DEBUG: row_check")
					if produkt.item_code and produkt.qty and produkt.qty > 0:
						hat_produkte = True
						break
			
			# Wenn keine Produkte gefunden wurden, zur Liste hinzufügen
			if not hat_produkte:
				kunden_ohne_produkte.append(f"Kunde {index} ({kunde_row.kunde})")
		
		# Wenn Kunden ohne Produkte gefunden wurden, Fehlermeldung anzeigen
		if kunden_ohne_produkte:
			anzahl_kunden = len([k for k in self.kunden if k.kunde])
			
			frappe.throw(
				f"Die folgenden Kunden haben noch keine Produkte ausgewählt: {', '.join(kunden_ohne_produkte)}. "
				f"Bitte wähle für jeden Kunden mindestens ein Produkt aus. "
				f"Alternativ kannst du Kunden ohne Bestellung aus der Liste entfernen, "
				f"jedoch müssen mindestens 2 Kunden verbleiben."
			)
	
	def set_status(self):
		# Wenn wir bereits "Gebucht" oder "Abgeschlossen" sind, nicht mehr ändern (außer durch Status-Update)
		if self.status in ["Gebucht", "Abgeschlossen"]:
			return
			
		# Prüfen, ob Produkte vorhanden sind
		has_products = False
		
		# Für alle Produktauswahl-Tabellen prüfen
		for i in range(1, 16):
			field_name = f"produktauswahl_für_kunde_{i}"
			if hasattr(self, field_name) and getattr(self, field_name):
				table = getattr(self, field_name)
				if any(item.item_code and item.qty for item in table):
					has_products = True
					break
		
		# Status setzen basierend auf dem Vorhandensein von Produkten
		if has_products:
			self.status = "Produkte"
		else:
			self.status = "Kunden"
	
	def set_uom_conversion_factor(self):
		# Für alle Produktauswahl-Tabellen
		for i in range(1, 16):
			field_name = f"produktauswahl_für_kunde_{i}"
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
								if isinstance(item.delivery_date, str):
									item.delivery_date = frappe.utils.getdate(item.delivery_date)
								else:
									item.delivery_date = frappe.utils.getdate(item.delivery_date)
							except Exception as e:
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
		"""Berechnet Gesamtumsatz"""
		total_amount = 0.0
		
		# Berechne Gesamtumsatz aus allen Produkttabellen
		for i in range(1, 16):
			field_name = f"produktauswahl_für_kunde_{i}"
			if hasattr(self, field_name) and getattr(self, field_name):
				table = getattr(self, field_name)
				for item in table:
					if item.qty and item.rate:
						total_amount += flt(item.qty) * flt(item.rate)
		
		# Setze Gesamtumsatz
		self.gesamtumsatz = total_amount

	def validate_all_addresses(self):
		"""
		Prüft, ob alle benötigten Kunden Adressen haben.
		REDUZIERT: Weniger aggressive Warnungen
		"""
		if self.is_new():
			return
		
		# NUR PRÜFEN wenn der Status "Produkte" ist und wir kurz vor der Auftragserstellung stehen
		if self.status != "Produkte":
			return
		
		kunden_ohne_adresse = []
		
		# Prüfe alle Kunden
		if self.kunden:
			for kunde_row in self.kunden:
				if not kunde_row.kunde:
					continue
					
				# Prüfe Billing-Adresse
				if not find_existing_address(kunde_row.kunde, "Billing"):
					kunden_ohne_adresse.append(f"Kunde ({kunde_row.kunde})")
		
		# REDUZIERT: Nur noch bei VIELEN fehlenden Adressen warnen
		if len(kunden_ohne_adresse) > 2:
			frappe.log_error(f"Adress-Info für Sammelbestellung {self.name}: {', '.join(kunden_ohne_adresse)}", "INFO: address_check")
		else:
			if kunden_ohne_adresse:
				frappe.log_error(f"Vereinzelte Adress-Hinweise für Sammelbestellung {self.name}: {', '.join(kunden_ohne_adresse)}", "INFO: few_address_hints")

# Warehouse-Hilfsfunktion
@frappe.whitelist()
def get_default_warehouse():
	"""
	Ermittelt das Standard-Warehouse flexibel für verschiedene Installationen
	"""
	warehouse = frappe.defaults.get_user_default("Warehouse")
	if warehouse:
		return warehouse
	
	warehouses = frappe.get_all("Warehouse", 
		filters={"is_group": 0}, 
		fields=["name"], 
		limit=1
	)
	
	if warehouses:
		return warehouses[0].name
	
	all_warehouses = frappe.get_all("Warehouse", fields=["name"], limit=1)
	if all_warehouses:
		return all_warehouses[0].name
	
	return "Stores - Main"

def calculate_shipping_costs_for_sammelbestellung(sammelbestellung_doc):
    """
    Berechnet Versandkosten für eine Sammelbestellung und erstellt Order-Informationen
    LOGIK: Verwendet 7 verschiedene Versandartikel statt ERPNext Versandregeln
    """
    all_orders = []
    
    frappe.log_error(f"=== CALCULATE_SHIPPING_COSTS START für {sammelbestellung_doc.name} ===", "DEBUG: shipping_start")
    
    # Kunden verarbeiten
    frappe.log_error(f"Verarbeite {len(sammelbestellung_doc.kunden)} Kunden", "DEBUG: process_customers")
    for idx, kunde_row in enumerate(sammelbestellung_doc.kunden):
        if not kunde_row.kunde:
            frappe.log_error(f"Kunde {idx+1}: Kein Kunde angegeben - überspringe", "DEBUG: customer_no_customer")
            continue
            
        index = idx + 1
        field_name = f"produktauswahl_für_kunde_{index}"
        versand_field = f"versand_kunde_{index}"
        
        frappe.log_error(f"=== Verarbeite Kunde {index}: {kunde_row.kunde} ===", "DEBUG: customer_start")
        
        if not hasattr(sammelbestellung_doc, field_name) or not getattr(sammelbestellung_doc, field_name):
            frappe.log_error(f"Kunde {index} ({kunde_row.kunde}): Keine Produkttabelle {field_name} gefunden", "DEBUG: no_product_table")
            continue
        
        produkte_kunde = []
        total_kunde = 0
        
        tabelle_inhalt = getattr(sammelbestellung_doc, field_name)
        frappe.log_error(f"Kunde {index} ({kunde_row.kunde}) - Anzahl Zeilen in {field_name}: {len(tabelle_inhalt)}", "DEBUG: table_check")
        
        for idx_prod, produkt in enumerate(getattr(sammelbestellung_doc, field_name)):
            frappe.log_error(f"  Kunde {index} Zeile {idx_prod}: item_code={produkt.item_code}, qty={produkt.qty}, rate={produkt.rate}", "DEBUG: customer_item")
            if produkt.item_code and produkt.qty and produkt.qty > 0:
                frappe.log_error(f"  -> Kunde {index} Produkt akzeptiert: {produkt.item_code}", "DEBUG: customer_accepted")
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
                    "_force_zero_rate": float(produkt.rate or 0) == 0.0
                }
                
                produkte_kunde.append(product_dict)
                total_kunde += flt(produkt.qty) * flt(produkt.rate or 0)
                frappe.log_error(f"  -> Kunde {index} Produkt hinzugefügt, neue Summe: {total_kunde}", "DEBUG: customer_added")
        
        if produkte_kunde:
            # Versandziel für Kunde
            versand_ziel = getattr(sammelbestellung_doc, versand_field, kunde_row.kunde)
            if not versand_ziel:
                versand_ziel = kunde_row.kunde
                
            frappe.log_error(f"Kunde {index} ({kunde_row.kunde}) hat {len(produkte_kunde)} Produkte, Total: {total_kunde}", "DEBUG: customer_order")
                
            # Bestimme shipping_target_type
            shipping_target_type = "customer"
            if versand_ziel == sammelbestellung_doc.partnerin:
                shipping_target_type = "partner"
            
            all_orders.append({
                "customer": kunde_row.kunde,
                "shipping_target": versand_ziel,
                "products": produkte_kunde,
                "total": total_kunde,
                "order_type": "kunde",
                "customer_index": index,
                "shipping_target_type": shipping_target_type,
                "shipping_cost": 0.0,  # Wird später berechnet
                "shipping_note": None,
                "shipping_item_code": None
            })
        else:
            frappe.log_error(f"Kunde {index} ({kunde_row.kunde}): Keine gültigen Produkte in {field_name} gefunden", "DEBUG: customer_no_products")
    
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
    
    # NEUE VERSANDLOGIK: Versand nur an Versandziel, keine Aufteilung mehr
    for target, orders in shipping_groups.items():
        total_value_for_target = sum(order["total"] for order in orders)
        num_orders = len(orders)
        
        frappe.log_error(f"Versandziel {target}: {num_orders} Aufträge, Gesamtwert: {total_value_for_target}€", "DEBUG: shipping_calculation")
        
        # Prüfe ob alle Artikel an Partnerin gehen
        all_to_partner = all(order.get("shipping_target_type") == "partner" for order in orders)
        shipping_types = [order.get('shipping_target_type') for order in orders]
        frappe.log_error(
            f"Partner-Erkennung für {target}\nall_to_partner={all_to_partner}\nshipping_target_types={shipping_types}",
            "Partner-Erkennung"
        )
        
        if total_value_for_target >= 200:
            # Versandkostenfrei - keine Versandkosten
            shipping_cost = 0.0
            shipping_item_code = None
            shipping_note = f"Versandkostenfrei (Gesamtwert: {total_value_for_target:.2f}€ >= 200€)"
            frappe.log_error(f"Versandkostenfrei für {target}", "DEBUG: shipping_free")
        else:
            # Versandkosten: 7€ nur an Versandziel
            shipping_cost = 7.0
            shipping_item_code = "shipping-7"
            shipping_note = f"Versandkosten: 7€ an Versandziel {target} (Gesamtwert: {total_value_for_target:.2f}€ < 200€)"
            frappe.log_error(f"Versandkosten für {target}: 7€ shipping-7", "DEBUG: shipping_charged")
        
        # SPEZIALFALL: Wenn alle Artikel an Partnerin gehen, erstelle separaten Partner-Versand-Auftrag
        if all_to_partner and total_value_for_target < 200 and shipping_cost > 0:
            # Erstelle zusätzlichen Partner-Versand-Auftrag
            partner_shipping_order = {
                "customer": target,  # Partnerin
                "shipping_target": target,  # Partnerin (Versand an sich selbst)
                "products": [],
                "total": shipping_cost,
                "shipping_cost": shipping_cost,
                "shipping_note": f"Partner-Versand: 7€ (Gesamtwert: {total_value_for_target:.2f}€ < 200€)",
                "shipping_item_code": shipping_item_code,
                "shipping_target_type": "partner",
                "is_partner_shipping_order": True
            }
            
            # Füge Versand-Artikel hinzu
            if shipping_item_code:
                try:
                    shipping_item_doc = frappe.get_doc("Item", shipping_item_code)
                    
                    shipping_product = {
                        "item_code": shipping_item_code,
                        "item_name": shipping_item_doc.item_name or "Versand",
                        "qty": 1,
                        "rate": shipping_cost,
                        "amount": shipping_cost,
                        "uom": shipping_item_doc.stock_uom or "Stk",
                        "stock_uom": shipping_item_doc.stock_uom or "Stk",
                        "conversion_factor": 1.0,
                        "stock_qty": 1.0,
                        "base_amount": shipping_cost,
                        "base_rate": shipping_cost,
                        "warehouse": get_default_warehouse(),
                        "delivery_date": frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7)),
                        "_force_zero_rate": False,
                        "_shipping_item": True
                    }
                    
                    partner_shipping_order["products"].append(shipping_product)
                    all_orders.append(partner_shipping_order)
                    
                    frappe.log_error(f"Partner-Versand-Auftrag erstellt für {target}: {shipping_cost}€", "DEBUG: partner_shipping_order_created")
                    
                except Exception as e:
                    frappe.log_error(f"Fehler beim Erstellen des Partner-Versand-Auftrags: {str(e)}", "ERROR: partner_shipping_error")
            
            # Alle normalen Aufträge bekommen KEINE Versandkosten
            for order in orders:
                order["shipping_cost"] = 0.0
                order["shipping_note"] = f"Keine Versandkosten (Partner-Versand-Auftrag erstellt)"
                order["shipping_item_code"] = None
        else:
            # NORMALE LOGIK: Versandkosten nur an Versandziel hinzufügen (nicht aufgeteilt)
            if shipping_cost > 0 and shipping_item_code:
                # Finde den Versandziel-Auftrag (der Kunde, der die Ware tatsächlich empfängt)
                # WICHTIG: Versandkosten gehen an den Kunden, dessen customer == shipping_target
                shipping_order = None
                for order in orders:
                    if order["customer"] == target:
                        shipping_order = order
                        frappe.log_error(f"Versandkosten gehen an {target} (empfängt die Ware)", "DEBUG: shipping_to_receiver")
                        break
                
                # Fallback: Wenn kein Kunde das Versandziel ist, nimm die erste Bestellung
                if not shipping_order:
                    shipping_order = orders[0]
                    frappe.log_error(f"Fallback: Versandkosten an erste Bestellung ({shipping_order['customer']})", "DEBUG: shipping_fallback")
                
                try:
                    shipping_item_doc = frappe.get_doc("Item", shipping_item_code)
                    
                    shipping_product = {
                        "item_code": shipping_item_code,
                        "item_name": shipping_item_doc.item_name or "Versand",
                        "qty": 1,
                        "rate": shipping_cost,
                        "amount": shipping_cost,
                        "uom": shipping_item_doc.stock_uom or "Stk",
                        "stock_uom": shipping_item_doc.stock_uom or "Stk",
                        "conversion_factor": 1.0,
                        "stock_qty": 1.0,
                        "base_amount": shipping_cost,
                        "base_rate": shipping_cost,
                        "warehouse": get_default_warehouse(),
                        "delivery_date": frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7)),
                        "_force_zero_rate": False,
                        "_shipping_item": True
                    }
                    
                    shipping_order["products"].append(shipping_product)
                    shipping_order["total"] += shipping_cost
                    shipping_order["shipping_cost"] = shipping_cost
                    shipping_order["shipping_note"] = shipping_note
                    shipping_order["shipping_item_code"] = shipping_item_code
                    
                    frappe.log_error(f"Versandartikel {shipping_item_code} hinzugefügt zu Versandziel {target}: {shipping_cost}€", "DEBUG: shipping_item_added")
                    
                except Exception as e:
                    frappe.log_error(f"Fehler beim Laden des Versandartikels {shipping_item_code}: {str(e)}", "ERROR: shipping_item_error")
                    if shipping_order:
                        shipping_product = {
                            "item_code": shipping_item_code,
                            "item_name": "Versand",
                            "qty": 1,
                            "rate": shipping_cost,
                            "amount": shipping_cost,
                            "uom": "Stk",
                            "stock_uom": "Stk",
                            "conversion_factor": 1.0,
                            "stock_qty": 1.0,
                            "base_amount": shipping_cost,
                            "base_rate": shipping_cost,
                            "warehouse": get_default_warehouse(),
                            "delivery_date": frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7)),
                            "_force_zero_rate": False,
                            "_shipping_item": True
                        }
                        
                        shipping_order["products"].append(shipping_product)
                        shipping_order["total"] += shipping_cost
                        shipping_order["shipping_cost"] = shipping_cost
                        shipping_order["shipping_note"] = shipping_note
                        shipping_order["shipping_item_code"] = shipping_item_code
            
            # Alle anderen Bestellungen bekommen keine Versandkosten
            for order in orders[1:]:  # Alle außer der ersten (Versandziel)
                order["shipping_cost"] = 0.0
                order["shipping_note"] = f"Keine Versandkosten (Versandziel: {target})"
                order["shipping_item_code"] = None
    
    frappe.log_error(f"=== ENDERGEBNIS calculate_shipping_costs_for_sammelbestellung ===", "DEBUG: shipping_calc_end")
    frappe.log_error(f"FINALE Anzahl Orders: {len(all_orders)}", "DEBUG: orders_count")
    for i, order in enumerate(all_orders):
        frappe.log_error(f"Order {i+1}: Customer={order['customer']}, Produkte={len(order['products'])}, Total={order['total']}", "DEBUG: final_order")
    frappe.log_error(f"SUCCESS: final_result", "SUCCESS: final_result")
    return all_orders

@frappe.whitelist()
def create_invoices(sammelbestellung, from_submit=False, from_button=False):
    """
    Erstellt Sales Orders für eine Sammelbestellung
    """
    # BACKEND-SICHERUNG: Setze skip_total_calculation Flag falls vom Button aufgerufen
    if from_button:
        try:
            sammelbestellung_doc = frappe.get_doc("Sammelbestellung", sammelbestellung)
            if not getattr(sammelbestellung_doc, 'skip_total_calculation', False):
                frappe.log_error(f"Backend-Sicherung: Setze skip_total_calculation für {sammelbestellung}", "INFO: backend_flag_set")
                sammelbestellung_doc.skip_total_calculation = 1
                sammelbestellung_doc.flags.ignore_permissions = True
                sammelbestellung_doc.save()
                frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Backend-Sicherung Fehler: {str(e)}", "WARNING: backend_flag_failed")
    
    try:
        frappe.log_error(f"Starte Auftragserstellung für Sammelbestellung {sammelbestellung} (from_submit={from_submit}, from_button={from_button})", "DEBUG: create_orders Start")
        
        # Prüfen, ob die Sammelbestellung bereits Aufträge hat
        existing_orders = frappe.get_all(
            "Sales Order",
            filters={"docstatus": ["!=", 2]},
            or_filters=[
                {"po_no": sammelbestellung},
                {"customer_name": sammelbestellung}
            ],
            limit=1
        )
        
        if existing_orders and from_button:
            frappe.log_error(f"Aufträge gefunden: {existing_orders}", "DEBUG: create_orders - Gefundene Aufträge")
            return existing_orders
        
        if from_button and from_submit:
            frappe.log_error("Verhinderte doppelte Ausführung (from_button und from_submit sind beide True)", "DEBUG: create_orders")
            return []
        
        # Hole Standard-Einstellungen
        company = frappe.defaults.get_user_default("Company")
        if not company:
            frappe.log_error("Keine Standard-Firma gefunden!", "ERROR: create_orders")
            frappe.throw("Bitte lege eine Standard-Firma in deinen Einstellungen fest.")
            
        currency = frappe.defaults.get_user_default("Currency")
        if not currency:
            frappe.log_error("Keine Standard-Währung gefunden!", "ERROR: create_orders")
            frappe.throw("Bitte lege eine Standard-Währung in deinen Einstellungen fest.")
            
        # Sammelbestellung-Dokument laden
        try:
            sammelbestellung_doc = frappe.get_doc("Sammelbestellung", sammelbestellung)
            sammelbestellung_doc.skip_total_calculation = 1
                
        except Exception as e:
            frappe.log_error(f"Sammelbestellung-Dokument konnte nicht geladen werden: {str(e)}", "ERROR: create_orders")
            frappe.throw("Das Sammelbestellung-Dokument konnte nicht geladen werden.")
        
        # Prüfen, ob die Sammelbestellung bereits abgeschlossen ist
        if sammelbestellung_doc.status == "Abgeschlossen" and sammelbestellung_doc.docstatus == 1:
            return []
        
        # Kundenliste prüfen
        if not sammelbestellung_doc.kunden or len(sammelbestellung_doc.kunden) < 2:
            frappe.throw("Es müssen mindestens 2 Kunden zur Sammelbestellung hinzugefügt werden.")
            
        # Vollständige Produktvalidierung für alle Kunden
        kunden_ohne_produkte = []
        
        for idx, kunde_row in enumerate(sammelbestellung_doc.kunden):
            if not kunde_row.kunde:
                continue
                
            index = idx + 1
            field_name = f"produktauswahl_für_kunde_{index}"
            
            hat_produkte = False
            if hasattr(sammelbestellung_doc, field_name) and getattr(sammelbestellung_doc, field_name):
                for produkt in getattr(sammelbestellung_doc, field_name):
                    if produkt.item_code and produkt.qty and produkt.qty > 0:
                        hat_produkte = True
                        break
            
            if not hat_produkte:
                kunden_ohne_produkte.append(f"Kunde {index} ({kunde_row.kunde})")
        
        if kunden_ohne_produkte:
            frappe.throw(
                f"Die folgenden Kunden haben noch keine Produkte ausgewählt: {', '.join(kunden_ohne_produkte)}. "
                f"Bitte wähle für jeden Kunden mindestens ein Produkt aus, "
                f"bevor du die Aufträge erstellst. Du kannst auch Kunden ohne Bestellung aus der Kundenliste entfernen."
            )
        
        # Produkte-Check: Hat irgendein Kunde Produkte?
        produkte_vorhanden = False
        
        for idx, _ in enumerate(sammelbestellung_doc.kunden or []):
            field_name = f"produktauswahl_für_kunde_{idx+1}"
            if hasattr(sammelbestellung_doc, field_name) and getattr(sammelbestellung_doc, field_name):
                for produkt in getattr(sammelbestellung_doc, field_name):
                    if produkt.item_code and produkt.qty and produkt.qty > 0:
                        produkte_vorhanden = True
                        break
                if produkte_vorhanden:
                    break
        
        if not produkte_vorhanden:
            frappe.throw("Es wurden keine Produkte ausgewählt. Bitte wähle mindestens ein Produkt aus, bevor du Aufträge erstellst.")
        
        # VERSANDKOSTENLOGIK
        frappe.log_error(f"=== AUFRUF calculate_shipping_costs_for_sammelbestellung ===", "DEBUG: before_calc")
        all_orders_with_shipping = calculate_shipping_costs_for_sammelbestellung(sammelbestellung_doc)
        frappe.log_error(f"=== RÜCKKEHR von calculate_shipping_costs_for_sammelbestellung ===", "DEBUG: after_calc")
        
        frappe.log_error(f"Anzahl Orders mit Versandkosten: {len(all_orders_with_shipping)}", "DEBUG: orders_count")
        for i, order in enumerate(all_orders_with_shipping):
            frappe.log_error(f"Erhaltene Order {i+1}: Customer={order.get('customer')}, Products={len(order.get('products', []))}, Total={order.get('total')}", "DEBUG: received_order")
        
        if not all_orders_with_shipping:
            frappe.log_error("Keine Bestellungen gefunden - calculate_shipping_costs_for_sammelbestellung gab leere Liste zurück", "ERROR: no_orders_calculated")
            return []
        
        if all_orders_with_shipping:
            first_order = all_orders_with_shipping[0]
            frappe.log_error(f"Erste Bestellung: Customer={first_order.get('customer')}, Products={len(first_order.get('products', []))}", "DEBUG: first_order")
        
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
                
                billing_address = None
                shipping_address = None
                
                frappe.log_error(f"=== ADRESS-DEBUG START für Customer: {customer}, Shipping_Target: {shipping_target} ===", "DEBUG: address_search")
                
                # RECHNUNGSADRESSE: Vom Kunden der bestellt
                frappe.log_error(f"Suche Billing-Adresse für Customer: '{customer}'", "DEBUG: billing_search")
                billing_address = find_existing_address(customer, "Billing")
                frappe.log_error(f"DEBUG: billing_address für {customer} = {billing_address} (Typ: {type(billing_address)})", "DEBUG: address_result")
                
                if not billing_address:
                    frappe.log_error(f"KRITISCH: Keine Adresse für Kunde '{customer}' gefunden", "ERROR: no_billing")
                    continue
                
                frappe.log_error(f"✅ Billing-Adresse für Kunde '{customer}': {billing_address}", "INFO: billing_found")
                
                # VERSANDADRESSE: Erst Shipping vom Versandziel, dann Billing vom Versandziel
                frappe.log_error(f"Suche Shipping-Adresse für Versandziel: '{shipping_target}'", "DEBUG: shipping_search")
                shipping_address = find_existing_address(shipping_target, "Shipping")
                frappe.log_error(f"DEBUG: shipping_address (Shipping) für {shipping_target} = {shipping_address} (Typ: {type(shipping_address)})", "DEBUG: address_result")
                
                if not shipping_address:
                    frappe.log_error(f"Suche Billing-Fallback für Versandziel: '{shipping_target}'", "DEBUG: shipping_fallback_search")
                    shipping_address = find_existing_address(shipping_target, "Billing")
                    frappe.log_error(f"DEBUG: shipping_address (Billing Fallback) für {shipping_target} = {shipping_address} (Typ: {type(shipping_address)})", "DEBUG: address_result")
                    
                    if shipping_address:
                        frappe.log_error(f"✅ Versand-Fallback: Billing-Adresse von '{shipping_target}': {shipping_address}", "INFO: shipping_fallback")
                    else:
                        frappe.log_error(f"KRITISCH: Keine Adresse für Versandziel '{shipping_target}' gefunden", "ERROR: no_shipping")
                        continue
                else:
                    frappe.log_error(f"✅ Shipping-Adresse für Versandziel '{shipping_target}': {shipping_address}", "INFO: shipping_found")
                
                frappe.log_error(f"=== FINALE ADRESSEN: Billing={billing_address}, Shipping={shipping_address} ===", "DEBUG: final_addresses")

                # Auftragsdaten
                order_data = {
                    "doctype": "Sales Order",
                    "customer": customer,
                    "transaction_date": today(),
                    "delivery_date": today(),
                    "items": [
                        {
                            **product,
                            "doctype": "Sales Order Item"
                        } for product in products
                    ],
                    "customer_address": billing_address,
                    "shipping_address_name": shipping_address,
                    "remarks": f"Erstellt aus Sammelbestellung: {sammelbestellung} | Kunde: {customer} | Versand an: {shipping_target}",
                    "po_no": sammelbestellung,
                    "company": company,
                    "currency": currency,
                    "status": "Draft",
                    "order_type": "Sales",
                    "sales_partner": sammelbestellung_doc.partnerin if sammelbestellung_doc.partnerin else None,
                    "custom_party_reference": sammelbestellung,
                    "custom_calculated_shipping_cost": shipping_cost,
                    "sales_order": sammelbestellung_doc.name,
                    # Steuer-Template korrekt setzen
                    "taxes_and_charges": None,  # Wird automatisch von ERPNext gesetzt
                    "selling_price_list": frappe.defaults.get_global_default("selling_price_list"),
                }
                
                
                frappe.log_error(f"DEBUG: Order-Daten für {customer}: customer_address={billing_address}, shipping_address_name={shipping_address}", "DEBUG: order_data")
                frappe.log_error(f"Erstelle Auftrag für '{customer}'", "INFO: creating_order")
                
                order = frappe.get_doc(order_data)
                
                # WICHTIG: Nach der Erstellung die korrekten Preise aus dem Sammelbestellung-Dokument setzen
                # um zu verhindern, dass Preise überschrieben werden
                for i, item in enumerate(order.items):
                    original_product = products[i]
                    
                    is_shipping = original_product.get('_shipping_item', False)
                    item_code = original_product.get('item_code', 'Unknown')
                    frappe.log_error(f"DEBUG COMBO: Item {i}: {item_code}, Shipping: {is_shipping}, Rate: {original_product.get('rate', 'N/A')}", "DEBUG: combo_check")
                    
                    force_zero = original_product.get('_force_zero_rate', False)
                    frappe.log_error(f"DEBUG: Item {item.item_code}, Rate: {original_product.get('rate', 'N/A')}, Force Zero: {force_zero}", "DEBUG: flag_check")
                    
                    if force_zero:
                        frappe.log_error(f"Setze Aktions-Preis für {item.item_code}: 0€ (Force Zero Flag)", "INFO: action_price")
                        item.rate = 0
                        item.price_list_rate = 0
                        item.base_rate = 0
                        item.base_price_list_rate = 0
                        item.amount = 0
                        item.base_amount = 0
                        if hasattr(item, 'custom_aktionsartikel'):
                            item.custom_aktionsartikel = 1
                    else:
                        if hasattr(original_product, 'rate') and original_product.rate is not None:
                            item.rate = original_product.rate
                            item.base_rate = original_product.rate
                            item.amount = flt(item.qty) * flt(original_product.rate) 
                            item.base_amount = item.amount
                
                # WICHTIG: Steuern und Totals korrekt berechnen (wie bei Party)
                order.run_method("set_missing_values")
                order.calculate_taxes_and_totals()
                
                # Setze alle Steuern auf "inklusive"
                if order.taxes:
                    for tax in order.taxes:
                        tax.included_in_print_rate = 1
                    # Neuberechnung mit inklusiven Steuern
                    order.calculate_taxes_and_totals()
                
                frappe.log_error(f"DEBUG FINAL ORDER: Customer={order.customer}, Items={len(order.items)}", "DEBUG: final_order_data")
                for i, item in enumerate(order.items):
                    frappe.log_error(f"  Item {i}: {item.item_code}, Qty: {item.qty}, Rate: {item.rate}, Amount: {item.amount}", "DEBUG: final_item_data")
                
                import types
                
                def safe_validate_party_address(self, *args, **kwargs):
                    frappe.log_error(f"Überspringe party_address für {self.customer}", "INFO: skip_validation")
                    pass
                
                def safe_validate_shipping_address(self, *args, **kwargs):
                    frappe.log_error(f"Überspringe shipping_address für {self.customer}", "INFO: skip_validation")
                    pass
                
                def safe_validate_billing_address(self, *args, **kwargs):
                    frappe.log_error(f"Überspringe billing_address für {self.customer}", "INFO: skip_validation")
                    pass
                
                order.validate_party_address = types.MethodType(safe_validate_party_address, order)
                order.validate_shipping_address = types.MethodType(safe_validate_shipping_address, order)
                order.validate_billing_address = types.MethodType(safe_validate_billing_address, order)
                
                frappe.log_error(f"Führe order.insert() aus für '{customer}'...", "INFO: order_insert")
                
                try:
                    order.insert()
                    frappe.log_error(f"Order.insert() erfolgreich für '{customer}': {order.name}", "INFO: order_created")
                    
                    frappe.log_error(f"Führe order.submit() aus für '{customer}'...", "INFO: order_submit")
                    order.submit()
                    frappe.log_error(f"Auftrag für {customer} eingereicht: {order.name}", "SUCCESS: order_complete")
                    
                except Exception as e:
                    frappe.log_error(f"KRITISCHER FEHLER bei Order für {customer}: {str(e)}\nTraceback: {frappe.get_traceback()}", "ERROR: order_error_detailed")
                    if hasattr(order, 'name') and order.name:
                        created_orders.append(order.name)
                        frappe.log_error(f"Fehlerhafter Auftrag {order.name} trotzdem hinzugefügt. Anzahl: {len(created_orders)}", "INFO: error_order_added")
                    else:
                        continue
                
                if not (hasattr(order, 'name') and order.name in created_orders):
                    created_orders.append(order.name)
                    frappe.log_error(f"Auftrag {order.name} hinzugefügt. Anzahl: {len(created_orders)}", "INFO: order_added")
                
            except Exception as e:
                frappe.log_error(f"Kritischer Fehler für {order_info.get('customer', 'Unbekannt')}: {str(e)}", "ERROR: critical_order_error")
                continue
        
        # Wenn mindestens ein Auftrag erstellt wurde, Sammelbestellung-Status aktualisieren
        if created_orders:
            # Partner-Auftrag erstellen (falls Produkte an Partnerin gehen)
            # ABER NUR wenn nicht alle Kunden an Partnerin senden (dann nur Partner-Versand-Auftrag)
            try:
                # Prüfe ob es einen Partner-Versand-Auftrag gibt (nur Versandkosten)
                has_partner_shipping_order = any(
                    order_info.get('is_partner_shipping_order', False)
                    for order_info in all_orders_with_shipping
                )
                
                # Prüfe ob alle Kunden an Partnerin senden
                all_customers_send_to_partner = all(
                    order_info.get('shipping_target') == sammelbestellung_doc.partnerin 
                    for order_info in all_orders_with_shipping
                )
                
                if all_customers_send_to_partner and has_partner_shipping_order:
                    frappe.log_error("Alle Kunden senden an Partnerin UND Partner-Versand-Auftrag existiert - kein zusätzlicher Partner-Auftrag nötig", "INFO: skip_partner_order")
                else:
                    partner_order = create_single_partner_order_for_sammelbestellung(sammelbestellung_doc, all_orders_with_shipping)
                    if partner_order:
                        created_orders.append(partner_order)
                        frappe.log_error(f"Partner-Auftrag erstellt: {partner_order}", "SUCCESS: partner_order_created")
            except Exception as e:
                frappe.log_error(f"Fehler beim Erstellen des Partner-Auftrags: {str(e)}", "ERROR: partner_order_failed")
            
            # Versandaufträge für andere Kunden erstellen (falls Produkte an andere Kunden gehen)
            try:
                shipping_orders = create_shipping_orders_for_customers(sammelbestellung_doc, all_orders_with_shipping)
                if shipping_orders:
                    created_orders.extend(shipping_orders)
                    frappe.log_error(f"Versandaufträge erstellt: {shipping_orders}", "SUCCESS: shipping_orders_created")
            except Exception as e:
                frappe.log_error(f"Fehler beim Erstellen der Versandaufträge: {str(e)}", "ERROR: shipping_orders_failed")
            
            # Pick Lists werden jetzt über das Versandauftrag-System erstellt
            # (automatische Picklist-Erstellung deaktiviert)
            frappe.log_error("Picklists werden über Versandauftrag-System erstellt", "INFO: picklists_via_shipping_orders")
            created_picklists = []
            
            # Delivery Notes für Kunden erstellen, die Produkte empfangen
            try:
                create_delivery_notes_for_receiving_customers(sammelbestellung_doc, all_orders_with_shipping, created_orders)
            except Exception as e:
                frappe.log_error(f"Fehler beim Erstellen der Delivery Notes: {str(e)}", "ERROR: delivery_notes_failed")
            
            sammelbestellung_doc.set_status = lambda: None
            sammelbestellung_doc.status = "Gebucht"  # "Abgeschlossen" erst wenn alle Aufträge completed sind
            sammelbestellung_doc.save()
            sammelbestellung_doc.submit()
            
            picklist_msg = f" und {len(created_picklists)} Auswahllisten" if created_picklists else ""
            frappe.msgprint(
                f"{len(created_orders)} Aufträge wurden erfolgreich erstellt und gebucht.<br><br>Das Fenster wird gleich automatisch neu geladen, um den aktuellen Status anzuzeigen.",
                title="Erfolgreich gebuchte Sammelbestellung",
                indicator="green"
            )
        else:
            frappe.log_error(f"Keine Aufträge erstellt für Sammelbestellung {sammelbestellung}. Einträge: {len(all_orders_with_shipping)}", "ERROR: no_orders_created")
            if all_orders_with_shipping:
                frappe.log_error(f"Fehlgeschlagene Kunden: {[order.get('customer', 'Unknown') for order in all_orders_with_shipping]}", "ERROR: failed_customers")
        
        frappe.db.commit()
        
        # Kürze die Log-Nachricht um Fehler zu vermeiden
        if len(str(created_orders)) > 100:
            log_message = f"create_invoices beendet. {len(created_orders)} Aufträge erstellt"
        else:
            log_message = f"create_invoices beendet. Rückgabe: {created_orders}"
        frappe.log_error(log_message, "INFO: function_end")
        
        if hasattr(sammelbestellung_doc, 'skip_total_calculation'):
            delattr(sammelbestellung_doc, 'skip_total_calculation')
            frappe.log_error("skip_total_calculation Flag aufgeräumt", "INFO: flag_cleanup")
        
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
        frappe.db.rollback()
        frappe.log_error(f"Allgemeiner Fehler: {str(e)}\n{frappe.get_traceback()}", f"ERROR: Auftragserstellung für Sammelbestellung {sammelbestellung}")
        
        try:
            if hasattr(sammelbestellung_doc, 'skip_total_calculation'):
                delattr(sammelbestellung_doc, 'skip_total_calculation')
                frappe.log_error("skip_total_calculation Flag bei Fehler aufgeräumt", "INFO: error_flag_cleanup")
        except:
            pass
        
        if from_submit:
            raise e
        else:
            frappe.throw(f"Fehler beim Erstellen der Aufträge: {str(e)}")

@frappe.whitelist()
def cancel_multiple_sammelbestellungen(sammelbestellungen):
    """
    Bricht mehrere Sammelbestellungen gleichzeitig ab
    """
    if not sammelbestellungen:
        return
        
    if isinstance(sammelbestellungen, str):
        sammelbestellung_list = sammelbestellungen.split(",")
    else:
        sammelbestellung_list = sammelbestellungen
    
    cancelled_count = 0
    failed_count = 0
    for sammelbestellung_name in sammelbestellung_list:
        try:
            sammelbestellung_doc = frappe.get_doc("Sammelbestellung", sammelbestellung_name)
            
            if sammelbestellung_doc.docstatus == 0 and sammelbestellung_doc.status in ["Kunden", "Produkte"]:
                sammelbestellung_doc.status = "Cancelled"
                sammelbestellung_doc.save()
                cancelled_count += 1
            elif sammelbestellung_doc.docstatus == 1:
                sammelbestellung_doc.cancel()
                cancelled_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            frappe.log_error(f"Fehler beim Abbrechen der Sammelbestellung {sammelbestellung_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: cancel_sammelbestellung")
            failed_count += 1
            
    frappe.db.commit()
    
    return {
        "cancelled": cancelled_count,
        "failed": failed_count,
        "total": len(sammelbestellung_list)
    }

def find_existing_address(entity_name, preferred_type="Billing"):
    """
    Findet eine vorhandene Adresse für einen Kunden oder Sales Partner
    """
    frappe.log_error(f"=== find_existing_address START: Entity='{entity_name}', Type='{preferred_type}' ===", "DEBUG: find_address_start")
    
    try:
        entity_type = None
        entity_doc = None
        display_name = entity_name
        
        if frappe.db.exists("Customer", entity_name):
            entity_type = "Customer"
            entity_doc = frappe.get_doc("Customer", entity_name)
            display_name = entity_doc.customer_name or entity_name
            frappe.log_error(f"✅ Customer '{entity_name}' existiert", "DEBUG: customer_exists")
        elif frappe.db.exists("Sales Partner", entity_name):
            entity_type = "Sales Partner"
            entity_doc = frappe.get_doc("Sales Partner", entity_name)
            display_name = entity_doc.partner_name or entity_name
            frappe.log_error(f"✅ Sales Partner '{entity_name}' existiert", "DEBUG: sales_partner_exists")
        else:
            frappe.log_error(f"❌ Weder Customer noch Sales Partner '{entity_name}' existiert!", "ERROR: find_address")
            return None
        
        frappe.log_error(f"Entity Display Name: '{display_name}' (Typ: {entity_type})", "DEBUG: entity_name")
        
        address_links = []
        
        frappe.log_error(f"Suche direkte {entity_type}-Links für '{entity_name}'...", "DEBUG: search_entity_links")
        entity_links = frappe.get_all(
            "Dynamic Link",
            filters={"link_doctype": entity_type, "link_name": entity_name},
            fields=["parent"]
        )
        frappe.log_error(f"Gefunden: {len(entity_links)} direkte {entity_type}-Links: {[link['parent'] for link in entity_links]}", "DEBUG: entity_links_found")
        address_links.extend(entity_links)
        
        try:
            frappe.log_error(f"Suche Contact-Links für '{entity_name}'...", "DEBUG: search_contact_links")
            contact_links = frappe.get_all(
                "Dynamic Link", 
                filters={"link_doctype": "Contact"},
                fields=["parent", "link_name"]
            )
            frappe.log_error(f"Alle Contact-Links gefunden: {len(contact_links)}", "DEBUG: all_contacts")
            
            contact_count = 0
            for contact_link in contact_links:
                if contact_link.parent and frappe.db.exists("Contact", contact_link.link_name):
                    contact_entity_links = frappe.get_all(
                        "Dynamic Link",
                        filters={
                            "parent": contact_link.link_name,
                            "parenttype": "Contact", 
                            "link_doctype": entity_type,
                            "link_name": entity_name
                        },
                        fields=["parent"]
                    )
                    
                    if contact_entity_links:
                        address_links.append({"parent": contact_link.parent})
                        contact_count += 1
                        frappe.log_error(f"✅ Contact-Adresse #{contact_count} gefunden für '{display_name}': {contact_link.parent}", "INFO: contact_address_found")
            
            frappe.log_error(f"Gefunden: {contact_count} Contact-Adressen für '{entity_name}'", "DEBUG: contact_summary")
        except Exception as e:
            frappe.log_error(f"❌ Fehler beim Suchen von Contact-Adressen für '{display_name}': {str(e)}", "WARNING: contact_search_error")
        
        unique_addresses = list({link["parent"]: link for link in address_links if link.get("parent")}.values())
        frappe.log_error(f"Unique Adressen gefunden: {len(unique_addresses)} - {[link['parent'] for link in unique_addresses]}", "DEBUG: unique_addresses")
        
        if not unique_addresses:
            frappe.log_error(f"❌ Keine Adressen für {entity_type} '{display_name}' gefunden", "WARNING: no_addresses")
            return None
        
        preferred_addresses = []
        other_addresses = []
        
        frappe.log_error(f"Analysiere {len(unique_addresses)} Adressen nach Typ '{preferred_type}'...", "DEBUG: analyze_addresses")
        
        for i, link in enumerate(unique_addresses):
            try:
                addr_name = link["parent"]
                frappe.log_error(f"Lade Adresse #{i+1}: {addr_name}...", "DEBUG: load_address")
                addr = frappe.get_doc("Address", addr_name)
                
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
        frappe.log_error(f"❌ Kritischer Fehler beim Suchen von Adressen für '{entity_name}': {str(e)}\n{frappe.get_traceback()}", "ERROR: find_address_error")
        return None
    
    finally:
        frappe.log_error(f"=== find_existing_address ENDE für '{entity_name}' ===", "DEBUG: find_address_end")

def create_picklists_for_sammelbestellung(sammelbestellung_doc, all_orders_with_shipping, created_order_names):
    """
    Erstellt Picklists (Auswahllisten) gruppiert nach Versandziel
    """
    try:
        frappe.log_error(f"🎯 create_picklists_for_sammelbestellung gestartet", "INFO: picklist_function")
        
        shipping_groups = {}
        
        for order_info in all_orders_with_shipping:
            customer = order_info["customer"]
            shipping_target = order_info["shipping_target"]
            
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
        
        for shipping_target, orders_for_target in shipping_groups.items():
            try:
                frappe.log_error(f"🏭 Erstelle Picklist für Versandziel: {shipping_target}", "INFO: creating_picklist")
                
                all_picklist_items = []
                invoice_data = []
                order_numbers = []
                # Mapping für Trenn-Items: Speichere Kundennamen für spätere Aktualisierung
                separator_customer_mapping = []
                
                # Prüfe ob Gruppenversand (mehrere Kunden an dasselbe Versandziel)
                is_group_shipping = len(orders_for_target) > 1
                
                for idx, order_data in enumerate(orders_for_target):
                    customer = order_data["customer"]
                    sales_order_name = order_data["sales_order"]
                    order_info = order_data["order_info"]
                    
                    order_numbers.append(sales_order_name)
                    
                    # Hole Kundenname für Anzeige
                    try:
                        customer_doc = frappe.get_doc("Customer", customer)
                        customer_display_name = customer_doc.customer_name or customer
                    except:
                        customer_display_name = customer
                    
                    # WICHTIG: Prüfe ob Trenner hinzugefügt werden soll
                    # Trenner nur für echte Kunden mit Produkten, NICHT für Vertriebspartner oder nur Versandkosten
                    # WICHTIG: Filtere nach aktuellem Versandziel, nicht nach allen Versandzielen!
                    customer_order_infos = [oi for oi in all_orders_with_shipping if oi.get('customer') == customer and oi.get('shipping_target') == shipping_target]
                    should_add_separator = should_add_separator_for_customer(customer, customer_order_infos, sammelbestellung_doc.partnerin)
                    
                    # WICHTIG: Füge Trenner hinzu für JEDEN Kunden (auch den ersten) bei Gruppenversand UND Kunde hat echte Produkte
                    # Genau wie bei Party! (siehe party.py)
                    if is_group_shipping and should_add_separator:
                        # Erstelle Trenn-Item mit dem existierenden Item "---"
                        try:
                            # Prüfe, ob das Trenn-Item existiert
                            trenner_item = frappe.get_doc("Item", "---")
                            
                            separator_item_name = f"📦 Bestellung für: {customer_display_name}"
                            separator_item = {
                                "doctype": "Pick List Item",
                                "item_code": "---",
                                "item_name": separator_item_name,
                                "qty": 0.001,  # Sehr kleine Menge, damit es angezeigt wird aber nicht gepackt wird
                                "stock_qty": 0.001,
                                "picked_qty": 0.0,
                                "stock_reserved_qty": 0.0,
                                "uom": trenner_item.stock_uom or "Stk",
                                "stock_uom": trenner_item.stock_uom or "Stk",
                                "conversion_factor": 1.0,
                                "warehouse": get_default_warehouse(),
                                "sales_order": None,  # Kein Sales Order für Trenn-Item
                                "sales_order_item": None,
                                "batch_no": None,
                                "serial_no": None,
                                "use_serial_batch_fields": 0,
                                "serial_and_batch_bundle": None,
                                "product_bundle_item": None,
                                "material_request": None,
                                "material_request_item": None
                            }
                            all_picklist_items.append(separator_item)
                            # Speichere Mapping für spätere Aktualisierung
                            separator_customer_mapping.append({
                                "customer_name": customer_display_name,
                                "item_name": separator_item_name
                            })
                            frappe.log_error(f"📋 Trenn-Item hinzugefügt für Kunde: {customer_display_name} (Index: {idx}) - item_code: {separator_item.get('item_code')}, item_name: {separator_item.get('item_name')}", "INFO: separator_item_added")
                        except Exception as e:
                            # Falls das Trenn-Item nicht existiert, logge Warnung aber mache weiter
                            frappe.log_error(f"⚠️ Trenn-Item '---' konnte nicht gefunden werden: {str(e)}", "WARNING: separator_item_not_found")
                    elif not should_add_separator:
                        frappe.log_error(f"⏭️ Überspringe Trenner für {customer_display_name} (Vertriebspartner oder nur Versandkosten)", "DEBUG: skip_separator_for_partner_picklist")
                    
                    try:
                        frappe.log_error(f"🔍 Suche Sales Invoices für SO: {sales_order_name}", "DEBUG: invoice_search_start")
                        current_invoices = frappe.get_all(
                            "Sales Invoice",
                            filters={
                                "sales_order": sales_order_name,
                                "docstatus": 1
                            },
                            fields=["name"]
                        )
                        
                        frappe.log_error(f"📋 Gefundene Invoices für SO {sales_order_name}: {len(current_invoices)} - {[inv.name for inv in current_invoices]}", "DEBUG: invoice_search_result")
                        
                        for inv in current_invoices:
                            invoice_with_customer = f"{inv.name} ({customer_display_name})"
                            invoice_data.append(invoice_with_customer)
                            frappe.log_error(f"💳 Sales Invoice für SO {sales_order_name} gefunden: {invoice_with_customer}", "INFO: invoice_found_for_picklist")
                            
                    except Exception as e:
                        frappe.log_error(f"⚠️ Fehler beim Finden der Sales Invoice für {sales_order_name}: {str(e)}", "WARNING: invoice_search")
                    
                    try:
                        so_doc = frappe.get_doc("Sales Order", sales_order_name)
                    except:
                        frappe.log_error(f"❌ Sales Order {sales_order_name} nicht gefunden", "ERROR: so_not_found")
                        continue
                    
                    for product in order_info["products"]:
                        if product.get("_shipping_item", False):
                            frappe.log_error(f"📦 Versandartikel übersprungen für Picklist: {product['item_code']}", "INFO: shipping_item_skipped")
                            continue
                        
                        # WICHTIG: Trenn-Items (item_code == "---") nicht als Bundle prüfen
                        if product["item_code"] == "---":
                            # Trenn-Item direkt hinzufügen ohne Bundle-Prüfung
                            so_warehouse = product.get("warehouse", get_default_warehouse())
                            so_item_name = None
                            for so_item in so_doc.items:
                                if so_item.item_code == product["item_code"] and so_item.qty == product["qty"]:
                                    so_warehouse = so_item.warehouse or get_default_warehouse()
                                    so_item_name = so_item.name
                                    break
                            
                            picklist_item = {
                                "doctype": "Pick List Item",
                                "item_code": product["item_code"],
                                "item_name": product["item_name"],
                                "qty": float(product["qty"]),
                                "stock_qty": float(product.get("stock_qty", product["qty"])),
                                "picked_qty": 0.0,
                                "stock_reserved_qty": 0.0,
                                "uom": product.get("uom", "Stk"),
                                "stock_uom": product.get("stock_uom", "Stk"),
                                "conversion_factor": float(product.get("conversion_factor", 1.0)),
                                "warehouse": so_warehouse,
                                "sales_order": sales_order_name,
                                "sales_order_item": so_item_name,
                                "batch_no": None,
                                "serial_no": None,
                                "use_serial_batch_fields": 0,
                                "serial_and_batch_bundle": None,
                                "product_bundle_item": None,
                                "material_request": None,
                                "material_request_item": None
                            }
                            all_picklist_items.append(picklist_item)
                            continue
                        
                        so_warehouse = product.get("warehouse", get_default_warehouse())
                        so_item_name = None
                        so_item = None
                        for so_item_iter in so_doc.items:
                            if so_item_iter.item_code == product["item_code"] and so_item_iter.qty == product["qty"]:
                                so_warehouse = so_item_iter.warehouse or get_default_warehouse()
                                so_item_name = so_item_iter.name
                                so_item = so_item_iter
                                break
                        
                        # Prüfe ob Item ein Product Bundle ist
                        bundle_items = frappe.get_all("Product Bundle Item", 
                                                     filters={"parent": product["item_code"]}, 
                                                     fields=["item_code", "qty", "uom", "description"])
                        
                        if bundle_items:
                            # Item ist ein Product Bundle - füge Bundle Items hinzu
                            frappe.log_error(f"Product Bundle erkannt: {product['item_code']} mit {len(bundle_items)} Items", "INFO: bundle_detected")
                            for bundle_item in bundle_items:
                                bundle_qty = float(bundle_item.qty) * float(product["qty"])
                                
                                # Hole item_name für Bundle-Item
                                bundle_item_name = bundle_item.description or frappe.get_value("Item", bundle_item.item_code, "item_name") or bundle_item.item_code
                                
                                picklist_item = {
                                    "doctype": "Pick List Item",
                                    "item_code": bundle_item.item_code,
                                    "item_name": bundle_item_name,
                                    "qty": bundle_qty,
                                    "stock_qty": bundle_qty,
                                    "picked_qty": 0.0,
                                    "stock_reserved_qty": 0.0,
                                    "uom": bundle_item.uom or product.get("uom", "Stk"),
                                    "stock_uom": bundle_item.uom or product.get("stock_uom", "Stk"),
                                    "conversion_factor": 1.0,
                                    "warehouse": so_warehouse,
                                    "sales_order": sales_order_name,
                                    "sales_order_item": so_item_name,  # Referenz zum Original SO Item
                                    "batch_no": None,
                                    "serial_no": None,
                                    "use_serial_batch_fields": 0,
                                    "serial_and_batch_bundle": None,
                                    "product_bundle_item": product["item_code"],  # Referenz zum Original Bundle
                                    "material_request": None,
                                    "material_request_item": None
                                }
                                
                                all_picklist_items.append(picklist_item)
                                frappe.log_error(f"Bundle Item hinzugefügt: {bundle_item.item_code} (Qty: {bundle_qty}) für Bundle {product['item_code']}", "INFO: bundle_item_added")
                        else:
                            # Normaler Artikel - wie bisher
                            picklist_item = {
                                "doctype": "Pick List Item",
                                "item_code": product["item_code"],
                                "item_name": product["item_name"],
                                "qty": float(product["qty"]),
                                "stock_qty": float(product.get("stock_qty", product["qty"])),
                                "picked_qty": 0.0,
                                "stock_reserved_qty": 0.0,
                                "uom": product.get("uom", "Stk"),
                                "stock_uom": product.get("stock_uom", "Stk"),
                                "conversion_factor": float(product.get("conversion_factor", 1.0)),
                                "warehouse": so_warehouse,
                                "sales_order": sales_order_name,
                                "sales_order_item": so_item_name,
                                "batch_no": None,
                                "serial_no": None,
                                "use_serial_batch_fields": 0,
                                "serial_and_batch_bundle": None,
                                "product_bundle_item": None,
                                "material_request": None,
                                "material_request_item": None
                            }
                            
                            all_picklist_items.append(picklist_item)
                            frappe.log_error(f"✅ Picklist Item hinzugefügt: {product['item_code']} (SO: {sales_order_name}, SO-Item: {so_item_name}, Customer: {customer})", "INFO: picklist_item_added")
                
                if not all_picklist_items:
                    frappe.log_error(f"⚠️ Keine Items für Versandziel {shipping_target} gefunden", "WARNING: no_picklist_items")
                    continue
                
                invoice_data = list(set(invoice_data))
                order_numbers = list(set(order_numbers))
                
                if invoice_data:
                    invoice_text = "\n".join(sorted(invoice_data))
                    remarks = f"Sammelbestellung: {sammelbestellung_doc.name} | {len(invoice_data)} Rechnungen"
                    frappe.log_error(f"✅ Picklist mit {len(invoice_data)} Rechnungen erstellt", "INFO: picklist_created_with_invoices")
                else:
                    order_text = ", ".join(sorted(order_numbers))
                    remarks = f"Sammelbestellung: {sammelbestellung_doc.name} | {len(order_numbers)} Aufträge"
                    frappe.log_error(f"⚠️ Picklist ohne Rechnungen - {len(order_numbers)} Aufträge", "WARNING: picklist_no_invoices")
                
                picklist_data = {
                    "doctype": "Pick List",
                    "purpose": "Delivery",
                    "company": frappe.defaults.get_user_default("Company"),
                    "customer": shipping_target,
                    "custom_invoice_references": "\n".join(sorted(invoice_data)) if invoice_data else None,
                    "remarks": remarks,
                    "locations": all_picklist_items
                }
                
                frappe.log_error(f"🎯 Erstelle Picklist für {shipping_target} mit {len(all_picklist_items)} Items", "INFO: picklist_creation")
                
                # Debug: Prüfe ob Trenner-Items vorhanden sind
                trenner_count = sum(1 for item in all_picklist_items if item.get('item_code') == '---')
                frappe.log_error(f"🔍 Trenner-Items in Picklist: {trenner_count} von {len(all_picklist_items)} Items", "DEBUG: separator_items_check")
                
                picklist = frappe.get_doc(picklist_data)
                picklist.insert()
                
                # Debug: Prüfe ob Trenner-Items nach insert noch vorhanden sind
                trenner_after_insert = sum(1 for item in picklist.locations if item.item_code == '---')
                frappe.log_error(f"🔍 Trenner-Items nach insert: {trenner_after_insert} von {len(picklist.locations)} Items", "DEBUG: separator_items_after_insert")
                
                # WICHTIG: Stelle sicher, dass item_name für Trenn-Items erhalten bleibt
                # Frappe könnte den item_name beim Erstellen überschreiben, daher aktualisieren wir ihn
                if is_group_shipping and separator_customer_mapping:
                    picklist.reload()  # Lade die Pickliste neu
                    # Finde alle Trenn-Items in der Picklist und aktualisiere sie
                    separator_index = 0
                    for picklist_item in picklist.locations:
                        if picklist_item.item_code == '---':
                            # Verwende das Mapping um den richtigen Kundennamen zu finden
                            if separator_index < len(separator_customer_mapping):
                                mapping = separator_customer_mapping[separator_index]
                                picklist_item.item_name = mapping["item_name"]
                                frappe.log_error(f"📋 Trenn-Item #{separator_index} item_name aktualisiert: {picklist_item.item_name} (Kunde: {mapping['customer_name']})", "DEBUG: separator_item_name_updated")
                                separator_index += 1
                    picklist.save()  # Speichere die Änderungen
                    frappe.log_error(f"✅ Picklist {picklist.name} Trenn-Item Namen aktualisiert ({separator_index} Trenn-Items)", "INFO: separator_item_names_updated")
                
                frappe.log_error(f"✅ Picklist erstellt: {picklist.name}", "SUCCESS: picklist_created")
                
                try:
                    picklist.submit()
                    frappe.log_error(f"🎉 Picklist eingereicht: {picklist.name}", "SUCCESS: picklist_submitted")
                except Exception as e:
                    frappe.log_error(f"⚠️ Picklist konnte nicht eingereicht werden: {str(e)}", "WARNING: picklist_submit_failed")
                
                created_picklists.append(picklist.name)
                
            except Exception as e:
                frappe.log_error(f"❌ Fehler beim Erstellen der Picklist für {shipping_target}: {str(e)}", "ERROR: picklist_creation_error")
                continue
        
        frappe.log_error(f"🎉 Picklists erstellt: {created_picklists}", "SUCCESS: all_picklists_created")
        return created_picklists
        
    except Exception as e:
        frappe.log_error(f"💥 Allgemeiner Fehler in create_picklists_for_sammelbestellung: {str(e)}\n{frappe.get_traceback()}", "ERROR: picklist_function_error")
        return []


def create_shipping_orders_for_customers(sammelbestellung_doc, all_orders_with_shipping):
    """
    Erstellt Versandaufträge für alle Kunden, die als Versandziel fungieren.
    Gruppiert Produkte nach Versandziel und erstellt einen Versandauftrag pro Ziel.
    """
    try:
        frappe.log_error(f"=== create_shipping_orders_for_customers START ===", "INFO: shipping_orders_start")
        
        # Gruppiere nach Versandziel (außer Partnerin, die wird separat behandelt)
        shipping_groups = {}
        
        for order_info in all_orders_with_shipping:
            customer = order_info.get('customer')
            shipping_target = order_info.get('shipping_target')
            products = order_info.get('products', [])
            
            # Überspringe NUR wenn Versandziel = Kunde selbst (Kunde erhält seine eigenen Produkte)
            # WICHTIG: Wenn Kunde an Partnerin sendet, MUSS ein Gruppenversand-Auftrag erstellt werden!
            if shipping_target == customer:
                frappe.log_error(f"Überspringe {customer} - empfängt eigene Produkte", "DEBUG: skip_self_shipping")
                continue
                
            # Sammle alle Produkte für dieses Versandziel (inkl. Partnerin!)
            if shipping_target not in shipping_groups:
                shipping_groups[shipping_target] = []
            
            # Füge alle Produkte hinzu (außer Versandkosten)
            for product in products:
                if product.get('item_code') and not product.get('item_code', '').startswith('shipping-'):
                    shipping_groups[shipping_target].append({
                        'product': product,
                        'from_customer': customer
                    })
        
        if not shipping_groups:
            frappe.log_error("Keine Versandaufträge nötig - alle Ware geht an Kunden selbst oder Partnerin", "INFO: no_shipping_orders_needed")
            return []
        
        created_shipping_orders = []
        
        for shipping_target, products_list in shipping_groups.items():
            try:
                frappe.log_error(f"Erstelle Versandauftrag für {shipping_target} mit {len(products_list)} Produkten", "INFO: create_shipping_order")
                
                # Hole die korrekte Lieferadresse des Versandziels
                # Verwende die find_existing_address Funktion, die bereits die richtige Logik hat
                shipping_address = None
                try:
                    # Suche nach Shipping-Adresse mit der bewährten Funktion
                    shipping_address = find_existing_address(shipping_target, "Shipping")
                    
                    # Fallback: Suche nach Billing-Adresse
                    if not shipping_address:
                        shipping_address = find_existing_address(shipping_target, "Billing")
                        
                except Exception as e:
                    frappe.log_error(f"Fehler beim Suchen der Adresse für {shipping_target}: {str(e)}", "ERROR: address_search_error")
                
                if not shipping_address:
                    frappe.log_error(f"Keine Adresse für Versandziel {shipping_target} gefunden - überspringe", "WARNING: no_shipping_address")
                    continue
                
                # Sammle alle Kunden, die an dieses Versandziel senden
                all_customers_for_target = []
                for order_info in all_orders_with_shipping:
                    if order_info.get('shipping_target') == shipping_target:
                        customer = order_info.get('customer')
                        if customer and customer not in all_customers_for_target:
                            all_customers_for_target.append(customer)
                
                # Sortiere Kunden für konsistente Reihenfolge
                all_customers_for_target.sort()
                
                # Sammle ALLE Produkte mit Trennern (wie bei Party!)
                products_by_customer = []
                
                for idx, customer in enumerate(all_customers_for_target):
                    # Hole Kundenname für Anzeige
                    try:
                        customer_doc = frappe.get_doc("Customer", customer)
                        customer_display_name = customer_doc.customer_name or customer
                    except:
                        customer_display_name = customer
                    
                    # WICHTIG: Prüfe ob Trenner hinzugefügt werden soll
                    # Trenner nur für echte Kunden mit Produkten, NICHT für Vertriebspartner oder nur Versandkosten
                    customer_order_infos = [oi for oi in all_orders_with_shipping if oi.get('customer') == customer and oi.get('shipping_target') == shipping_target]
                    should_add_separator = should_add_separator_for_customer(customer, customer_order_infos, sammelbestellung_doc.partnerin)
                    
                    # WICHTIG: Füge Trenn-Item hinzu für JEDEN Kunden (auch den ersten) wenn mehrere Kunden UND Kunde hat echte Produkte
                    # Genau wie bei Party! (siehe party.py Zeile 1854)
                    if len(all_customers_for_target) > 1 and should_add_separator:
                        # Erstelle Trenn-Item (Überschrift für jeden Kunden)
                        try:
                            trenner_item = frappe.get_doc("Item", "---")
                            separator_item_data = {
                                "doctype": "Sales Order Item",
                                "item_code": "---",
                                "item_name": f"📦 Bestellung für: {customer_display_name}",
                                "qty": 0.001,  # Sehr kleine Menge, damit es angezeigt wird aber nicht gepackt wird
                                "rate": 0,
                                "amount": 0,
                                "uom": trenner_item.stock_uom or "Stk",
                                "stock_uom": trenner_item.stock_uom or "Stk",
                                "conversion_factor": 1.0,
                                "stock_qty": 0.001,
                                "base_amount": 0,
                                "base_rate": 0,
                                "warehouse": get_default_warehouse(),
                                "delivery_date": today(),
                                "net_weight": 0.0,  # Trenner haben kein Gewicht
                            }
                            products_by_customer.append(separator_item_data)
                            frappe.log_error(f"📋 Trenn-Item (Überschrift) im Gruppenversand-Auftrag hinzugefügt für Kunde: {customer_display_name} (Index: {idx})", "INFO: separator_item_in_order")
                        except Exception as e:
                            frappe.log_error(f"⚠️ Trenn-Item '---' konnte nicht gefunden werden: {str(e)}", "WARNING: separator_item_not_found")
                    elif not should_add_separator:
                        frappe.log_error(f"⏭️ Überspringe Trenner für {customer_display_name} (Vertriebspartner oder nur Versandkosten)", "DEBUG: skip_separator_for_partner")
                    
                    # Füge alle Produkte dieses Kunden hinzu
                    for order_info in all_orders_with_shipping:
                        if order_info.get('shipping_target') == shipping_target and order_info.get('customer') == customer:
                            for product in order_info.get('products', []):
                                if product.get('item_code') and not product.get('item_code', '').startswith('shipping-'):
                                    # WICHTIG: Bei Gruppenversand Kunden-Namen als Präfix zum Item-Namen hinzufügen
                                    item_name_display = product.get('item_name', product.get('item_code'))
                                    try:
                                        customer_doc = frappe.get_doc("Customer", customer)
                                        customer_display_name = customer_doc.customer_name or customer
                                    except:
                                        customer_display_name = customer
                                    
                                    if len(all_customers_for_target) > 1:
                                        item_name_display = f"[{customer_display_name}] {item_name_display}"
                                    
                                    # Hole Gewicht vom Item-Dokument
                                    item_weight = 0.0
                                    item_code = product.get('item_code')
                                    qty = product.get('qty', 1)
                                    try:
                                        item_doc = frappe.get_cached_doc("Item", item_code)
                                        if hasattr(item_doc, 'weight_per_unit') and item_doc.weight_per_unit:
                                            weight_per_unit = flt(item_doc.weight_per_unit)
                                            item_weight = weight_per_unit * qty
                                            
                                            # Umrechnung auf Gramm, falls nötig
                                            if hasattr(item_doc, 'weight_uom') and item_doc.weight_uom:
                                                if item_doc.weight_uom.lower() in ['kg', 'kilogram']:
                                                    item_weight = item_weight * 1000  # kg zu g
                                            
                                            frappe.log_error(
                                                f"  Sales Order Item {item_code}: Gewicht {weight_per_unit} {getattr(item_doc, 'weight_uom', 'g')} * qty {qty} = {item_weight}g",
                                                "DEBUG: weight_calc_so_creation"
                                            )
                                        else:
                                            frappe.log_error(
                                                f"  Sales Order Item {item_code}: Kein weight_per_unit im Item-Dokument",
                                                "WARNING: weight_missing_so_creation"
                                            )
                                    except Exception as e:
                                        frappe.log_error(
                                            f"⚠️ Konnte Gewicht für Sales Order Item {item_code} nicht berechnen: {str(e)}",
                                            "WARNING: weight_calc_error_so_creation"
                                        )
                                    
                                    products_by_customer.append({
                                        "doctype": "Sales Order Item",
                                        "item_code": item_code,
                                        "item_name": item_name_display,
                                        "qty": qty,
                                        "rate": 0,  # WICHTIG: Keine Rechnung = 0€ Rate
                                        "amount": 0,  # WICHTIG: Keine Rechnung = 0€ Amount
                                        "uom": product.get('uom', 'Stk'),
                                        "stock_uom": product.get('stock_uom', 'Stk'),
                                        "conversion_factor": product.get('conversion_factor', 1.0),
                                        "stock_qty": product.get('stock_qty', qty),
                                        "base_amount": 0,  # WICHTIG: Keine Rechnung = 0€ Base Amount
                                        "base_rate": 0,  # WICHTIG: Keine Rechnung = 0€ Base Rate
                                        "warehouse": product.get('warehouse', get_default_warehouse()),
                                        "delivery_date": product.get('delivery_date', today()),
                                        "net_weight": item_weight,  # Setze Gewicht für jedes Item
                                    })
                
                frappe.log_error(f"Versandauftrag für {shipping_target}: {len(products_by_customer)} Items (inkl. Trenn-Items) von {len(all_customers_for_target)} Kunden", "INFO: shipping_order_products")
                frappe.log_error(f"DEBUG: shipping_address = {shipping_address}", "DEBUG: address_debug")
                
                # Erstelle Versandauftrag
                shipping_order_data = {
                    "doctype": "Sales Order",
                    "customer": "Gruppenversand",  # Immer Gruppenversand als Customer
                    "transaction_date": today(),
                    "delivery_date": today(),
                    "items": products_by_customer,
                    "customer_address": None,  # Gruppenversand hat keine eigene Adresse
                    "shipping_address_name": shipping_address,  # Korrekte Versandadresse
                    "remarks": f"Versandauftrag aus Sammelbestellung: {sammelbestellung_doc.name} | Versandziel: {shipping_target} | {len(products_by_customer)} Items (inkl. Trenn-Items) von {len(all_customers_for_target)} Kunden",
                    "po_no": sammelbestellung_doc.name,
                    "company": frappe.defaults.get_global_default("company"),
                    "currency": frappe.defaults.get_global_default("currency"),
                    "status": "Draft",
                    "order_type": "Sales",
                    "sales_partner": sammelbestellung_doc.partnerin if sammelbestellung_doc.partnerin else None,
                    "custom_party_reference": sammelbestellung_doc.name,
                    "custom_calculated_shipping_cost": 0.0,
                    "custom_shipping_order": 1,  # Markierung als Versandauftrag
                    "sales_order": sammelbestellung_doc.name,
                    "taxes_and_charges": None,
                    "selling_price_list": frappe.defaults.get_global_default("selling_price_list"),
                }
                
                # Erstelle und buche den Versandauftrag
                shipping_order = frappe.get_doc(shipping_order_data)
                
                # Flags setzen um Adressvalidierung zu umgehen
                shipping_order.flags.ignore_permissions = True
                shipping_order.flags.ignore_validate = True
                shipping_order.flags.ignore_mandatory = True
                shipping_order.flags.ignore_address_validation = True
                shipping_order.flags.ignore_shipping_validation = True
                shipping_order.flags.ignore_billing_validation = True
                
                shipping_order.insert()
                
                # WICHTIG: Berechne total_net_weight aus den Items und setze es
                try:
                    total_weight = 0.0
                    for item in shipping_order.items:
                        if item.item_code != "---" and hasattr(item, 'net_weight') and item.net_weight:
                            total_weight += flt(item.net_weight) * flt(item.qty)
                    
                    shipping_order.total_net_weight = total_weight
                    shipping_order.db_update()  # Speichere direkt in der DB
                    
                    frappe.log_error(
                        f"✅ total_net_weight für Sales Order {shipping_order.name} gesetzt: {total_weight}g",
                        "INFO: total_weight_set_so"
                    )
                except Exception as e:
                    frappe.log_error(
                        f"⚠️ Fehler beim Setzen des Gewichts für Sales Order: {str(e)}",
                        "WARNING: weight_set_error_so"
                    )
                
                shipping_order.submit()
                
                frappe.log_error(f"Versandauftrag erfolgreich erstellt: {shipping_order.name} (total_net_weight: {shipping_order.total_net_weight}g)", "SUCCESS: shipping_order_created")
                created_shipping_orders.append(shipping_order.name)
                
            except Exception as e:
                frappe.log_error(f"Fehler beim Erstellen des Versandauftrags für {shipping_target}: {str(e)}", "ERROR: shipping_order_creation_failed")
                continue
        
        frappe.log_error(f"=== create_shipping_orders_for_customers ENDE: {len(created_shipping_orders)} Aufträge erstellt ===", "INFO: shipping_orders_end")
        return created_shipping_orders
        
    except Exception as e:
        frappe.log_error(f"Fehler in create_shipping_orders_for_customers: {str(e)}", "ERROR: shipping_orders_function_failed")
        return []


def create_single_partner_order_for_sammelbestellung(sammelbestellung_doc, all_orders_with_shipping):
    """
    Erstellt EINEN einzigen Partner-Auftrag für alle Produkte, die an die Partnerin gehen.
    Nur erstellt, wenn tatsächlich Produkte an die Partnerin geschickt werden.
    """
    try:
        # Prüfe ob es eine Partnerin gibt
        if not sammelbestellung_doc.partnerin:
            frappe.log_error("Keine Partnerin in Sammelbestellung - kein Partner-Auftrag nötig", "INFO: no_partnerin")
            return None
        
        # Prüfe ob es Partner-Versand-Aufträge gibt (nur Versandkosten, keine Produkte)
        # Diese Prüfung wird entfernt, da Partner-Versand-Aufträge als separate Aufträge erstellt werden
        # und nicht in all_orders_with_shipping enthalten sind
        
        # Sammle alle Produkte, die an die Partnerin gehen
        partner_products = []
        
        for order_info in all_orders_with_shipping:
            customer = order_info.get('customer')
            shipping_target = order_info.get('shipping_target')
            products = order_info.get('products', [])
            
            # Nur wenn das Versandziel die Partnerin ist
            if shipping_target == sammelbestellung_doc.partnerin:
                frappe.log_error(f"Kunde {customer} sendet an Partnerin {shipping_target} - {len(products)} Produkte", "DEBUG: partner_shipping")
                
                # Füge alle Produkte hinzu (außer Versandkosten)
                for product in products:
                    if product.get('item_code') and not product.get('item_code', '').startswith('shipping-'):
                        partner_products.append(product)
                        frappe.log_error(f"  -> Produkt hinzugefügt: {product.get('item_code')} x{product.get('qty')}", "DEBUG: product_added")
        
        # Wenn keine Produkte an die Partnerin gehen, keinen Partner-Auftrag erstellen
        if not partner_products:
            frappe.log_error("Keine Produkte gehen an die Partnerin - kein Partner-Auftrag nötig", "INFO: no_partner_products")
            return None
        
        # RADIKALE LÖSUNG: Wenn alle Kunden an Partnerin senden, KEINEN zusätzlichen Partner-Auftrag erstellen
        # Der Partner-Versand-Auftrag (7€) wird bereits als normaler Auftrag erstellt
        all_customers_send_to_partner = all(
            order_info.get('shipping_target') == sammelbestellung_doc.partnerin 
            for order_info in all_orders_with_shipping
        )
        
        if all_customers_send_to_partner:
            frappe.log_error("Alle Kunden senden an Partnerin - nur Partner-Versand-Auftrag nötig, KEIN zusätzlicher Partner-Auftrag", "INFO: only_shipping_order_needed")
            return None
        
        frappe.log_error(f"Erstelle Partner-Auftrag für Partnerin {sammelbestellung_doc.partnerin} mit {len(partner_products)} Produkten", "INFO: create_partner_order")
        
        # Hole die korrekte Lieferadresse der Partnerin
        # Verwende die find_existing_address Funktion, die bereits die richtige Logik hat
        partner_address = None
        try:
            # Suche nach Shipping-Adresse der Partnerin
            partner_address = find_existing_address(sammelbestellung_doc.partnerin, "Shipping")
            
            # Fallback: Suche nach Billing-Adresse der Partnerin
            if not partner_address:
                partner_address = find_existing_address(sammelbestellung_doc.partnerin, "Billing")
                    
        except Exception as e:
            frappe.log_error(f"Partner-Adresse nicht gefunden: {str(e)}", "WARNING: partner_address_not_found")
            partner_address = None
        
        frappe.log_error(f"DEBUG: partner_address = {partner_address}", "DEBUG: partner_address_debug")
        
        # Berechne Gewichte für Partner-Produkte
        partner_items_with_weight = []
        for product in partner_products:
            item_code = product.get('item_code')
            qty = product.get('qty', 1)
            
            # Hole Gewicht vom Item-Dokument
            item_weight = 0.0
            try:
                item_doc = frappe.get_cached_doc("Item", item_code)
                if hasattr(item_doc, 'weight_per_unit') and item_doc.weight_per_unit:
                    weight_per_unit = flt(item_doc.weight_per_unit)
                    item_weight = weight_per_unit * qty
                    
                    # Umrechnung auf Gramm, falls nötig
                    if hasattr(item_doc, 'weight_uom') and item_doc.weight_uom:
                        if item_doc.weight_uom.lower() in ['kg', 'kilogram']:
                            item_weight = item_weight * 1000  # kg zu g
            except Exception as e:
                frappe.log_error(
                    f"⚠️ Konnte Gewicht für Partner-Item {item_code} nicht berechnen: {str(e)}",
                    "WARNING: weight_calc_error_partner"
                )
            
            partner_items_with_weight.append({
                    "doctype": "Sales Order Item",
                "item_code": item_code,
                "item_name": product.get('item_name', item_code),
                "qty": qty,
                    "rate": product.get('rate', 0),
                    "amount": product.get('amount', 0),
                    "uom": product.get('uom', 'Stk'),
                    "stock_uom": product.get('stock_uom', 'Stk'),
                    "conversion_factor": product.get('conversion_factor', 1.0),
                "stock_qty": product.get('stock_qty', qty),
                    "base_amount": product.get('base_amount', product.get('amount', 0)),
                    "base_rate": product.get('base_rate', product.get('rate', 0)),
                    "warehouse": product.get('warehouse', get_default_warehouse()),
                    "delivery_date": product.get('delivery_date', today()),
                "net_weight": item_weight,  # Setze Gewicht für jedes Item
            })
        
        # Erstelle Sales Order für die Partnerin mit echten Produkten
        partner_order_data = {
            "doctype": "Sales Order",
            "customer": "Gruppenversand",  # Immer Gruppenversand als Customer
            "transaction_date": today(),
            "delivery_date": today(),
            "items": partner_items_with_weight,
            "customer_address": None,  # Gruppenversand hat keine eigene Adresse
            "shipping_address_name": partner_address,  # Korrekte Versandadresse der Partnerin
            "remarks": f"Partner-Versandauftrag aus Sammelbestellung: {sammelbestellung_doc.name} | Partnerin: {sammelbestellung_doc.partnerin} | {len(partner_products)} Produkte",
            "po_no": sammelbestellung_doc.name,
            "company": frappe.defaults.get_global_default("company"),
            "currency": frappe.defaults.get_global_default("currency"),
            "status": "Draft",
            "order_type": "Sales",
            "sales_partner": sammelbestellung_doc.partnerin if sammelbestellung_doc.partnerin else None,
            "custom_party_reference": sammelbestellung_doc.name,
            "custom_calculated_shipping_cost": 0.0,
            "custom_shipping_order": 1,  # Markierung als Versandauftrag
            "sales_order": sammelbestellung_doc.name,
            "taxes_and_charges": None,
            "selling_price_list": frappe.defaults.get_global_default("selling_price_list"),
        }
        
        # Erstelle und buche den Partner-Auftrag
        partner_order = frappe.get_doc(partner_order_data)
        
        # Flags setzen um Adressvalidierung zu umgehen
        partner_order.flags.ignore_permissions = True
        partner_order.flags.ignore_validate = True
        partner_order.flags.ignore_mandatory = True
        partner_order.flags.ignore_address_validation = True
        partner_order.flags.ignore_shipping_validation = True
        partner_order.flags.ignore_billing_validation = True
        
        partner_order.insert()
        
        # WICHTIG: Berechne total_net_weight aus den Items und setze es
        try:
            total_weight = 0.0
            for item in partner_order.items:
                if hasattr(item, 'net_weight') and item.net_weight:
                    total_weight += flt(item.net_weight) * flt(item.qty)
            
            partner_order.total_net_weight = total_weight
            partner_order.db_update()  # Speichere direkt in der DB
            
            frappe.log_error(
                f"✅ total_net_weight für Partner-Auftrag {partner_order.name} gesetzt: {total_weight}g",
                "INFO: total_weight_set_partner"
            )
        except Exception as e:
            frappe.log_error(
                f"⚠️ Fehler beim Setzen des Gewichts für Partner-Auftrag: {str(e)}",
                "WARNING: weight_set_error_partner"
            )
        
        partner_order.submit()
        
        frappe.log_error(f"Partner-Auftrag erfolgreich erstellt und gebucht: {partner_order.name} (total_net_weight: {partner_order.total_net_weight}g)", "SUCCESS: partner_order_created")
        return partner_order.name
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Erstellen des Partner-Auftrags: {str(e)}", "ERROR: partner_order_creation_failed")
        return None


def create_delivery_notes_for_receiving_customers(sammelbestellung_doc, all_orders_with_shipping, created_orders):
    """
    Erstellt Delivery Notes für Kunden, die Produkte empfangen.
    Gruppiert nach Versandziel (shipping_target).
    """
    try:
        # Gruppiere nach Versandziel
        shipping_groups = {}
        
        for order_info in all_orders_with_shipping:
            customer = order_info["customer"]
            shipping_target = order_info["shipping_target"]
            
            # Finde den Sales Order für diesen Kunden
            sales_order_name = None
            for order_name in created_orders:
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
        
        frappe.log_error(f"📦 Delivery Note Shipping Groups: {list(shipping_groups.keys())}", "INFO: delivery_note_groups")
        
        created_delivery_notes = []
        
        for shipping_target, orders_for_target in shipping_groups.items():
            try:
                frappe.log_error(f"🏭 Erstelle Delivery Note für Versandziel: {shipping_target}", "INFO: creating_delivery_note")
                
                # Sammle alle Produkte für dieses Versandziel
                all_products = []
                invoice_data = []
                order_numbers = []
                
                # Prüfe ob Gruppenversand (mehrere Kunden an dasselbe Versandziel)
                is_group_shipping = len(orders_for_target) > 1
                
                for idx, order_data in enumerate(orders_for_target):
                    customer = order_data["customer"]
                    sales_order_name = order_data["sales_order"]
                    order_info = order_data["order_info"]
                    products = order_info.get("products", [])
                    
                    order_numbers.append(sales_order_name)
                    
                    # Hole Kundenname für Anzeige
                    try:
                        customer_doc = frappe.get_doc("Customer", customer)
                        customer_display_name = customer_doc.customer_name or customer
                    except:
                        customer_display_name = customer
                    
                    # WICHTIG: Prüfe ob Trenner hinzugefügt werden soll
                    # Trenner nur für echte Kunden mit Produkten, NICHT für Vertriebspartner oder nur Versandkosten
                    # WICHTIG: Filtere nach aktuellem Versandziel, nicht nach allen Versandzielen!
                    customer_order_infos = [oi for oi in all_orders_with_shipping if oi.get('customer') == customer and oi.get('shipping_target') == shipping_target]
                    should_add_separator = should_add_separator_for_customer(customer, customer_order_infos, sammelbestellung_doc.partnerin)
                    
                    # WICHTIG: Füge Trenner hinzu für JEDEN Kunden (auch den ersten) bei Gruppenversand UND Kunde hat echte Produkte
                    # Genau wie bei Party! (siehe party.py)
                    if is_group_shipping and should_add_separator:
                        # Erstelle Trenn-Item mit dem existierenden Item "---"
                        try:
                            # Prüfe, ob das Trenn-Item existiert
                            trenner_item = frappe.get_doc("Item", "---")
                            
                            separator_item = {
                                "doctype": "Delivery Note Item",
                                "item_code": "---",
                                "item_name": f"📦 Bestellung für: {customer_display_name}",
                                "qty": 0.001,  # Sehr kleine Menge, damit es angezeigt wird aber nicht geliefert wird
                                "rate": 0,
                                "amount": 0,
                                "uom": trenner_item.stock_uom or "Stk",
                                "stock_uom": trenner_item.stock_uom or "Stk",
                                "conversion_factor": 1.0,
                                "stock_qty": 0.001,
                                "base_amount": 0,
                                "base_rate": 0,
                                "warehouse": get_default_warehouse(),
                                "sales_order": sales_order_name,  # WICHTIG: Verwende Sales Order damit Item nicht entfernt wird
                                "sales_order_item": None,
                                "allow_zero_valuation_rate": 1,
                            }
                            all_products.append({
                                'product': separator_item,
                                'from_customer': customer,
                                'sales_order': sales_order_name  # Verwende Sales Order statt None
                            })
                            frappe.log_error(f"📋 Trenn-Item hinzugefügt für Kunde: {customer_display_name} - item_code: {separator_item.get('item_code')}, item_name: {separator_item.get('item_name')}", "INFO: separator_item_added")
                        except Exception as e:
                            # Falls das Trenn-Item nicht existiert, logge Warnung aber mache weiter
                            frappe.log_error(f"⚠️ Trenn-Item '---' konnte nicht gefunden werden: {str(e)}", "WARNING: separator_item_not_found")
                    elif not should_add_separator:
                        frappe.log_error(f"⏭️ Überspringe Trenner für {customer_display_name} (Vertriebspartner oder nur Versandkosten)", "DEBUG: skip_separator_for_partner_dn")
                    
                    # Füge alle Produkte hinzu (außer Versandkosten)
                    for product in products:
                        if product.get('item_code') and not product.get('item_code', '').startswith('shipping-'):
                            all_products.append({
                                'product': product,
                                'from_customer': customer,
                                'sales_order': sales_order_name
                            })
                
                if not all_products:
                    frappe.log_error(f"⚠️ Keine Produkte für Versandziel {shipping_target} gefunden", "WARNING: no_delivery_note_products")
                    continue
                
                # Finde den Sales Order für das Versandziel (für Adressdaten)
                target_sales_order = None
                for order_name in created_orders:
                    try:
                        order_doc = frappe.get_doc("Sales Order", order_name)
                        if order_doc.customer == shipping_target:
                            target_sales_order = order_doc
                            break
                    except:
                        continue
                
                if not target_sales_order:
                    frappe.log_error(f"Kein Sales Order für Versandziel {shipping_target} gefunden", "WARNING: no_target_sales_order")
                    continue
                
                # Berechne Gesamtgewicht VOR der Erstellung der Delivery Note
                total_net_weight = 0.0
                delivery_note_items = []
                
                for item in all_products:
                    item_code = item['product'].get('item_code')
                    qty = flt(item['product'].get('qty', 1))
                    
                    # Überspringe Trenner-Items
                    if item_code == "---":
                        delivery_note_items.append({
                            "doctype": "Delivery Note Item",
                            "item_code": item_code,
                            "item_name": item['product'].get('item_name', item_code),
                            "qty": item['product'].get('qty', 0.001),
                            "rate": 0,
                            "amount": 0,
                            "uom": item['product'].get('uom', 'Stk'),
                            "stock_uom": item['product'].get('stock_uom', 'Stk'),
                            "conversion_factor": 1.0,
                            "stock_qty": item['product'].get('stock_qty', 0.001),
                            "base_amount": 0,
                            "base_rate": 0,
                            "warehouse": item['product'].get('warehouse', get_default_warehouse()),
                            "delivery_date": item['product'].get('delivery_date', today()),
                            "sales_order": item['sales_order'],
                            "sales_order_item": None,
                            "allow_zero_valuation_rate": 1,
                            "net_weight": 0.0,  # Trenner haben kein Gewicht
                        })
                        continue
                    
                    # Hole Gewicht vom Item-Dokument
                    item_weight = 0.0
                    try:
                        item_doc = frappe.get_cached_doc("Item", item_code)
                        if hasattr(item_doc, 'weight_per_unit') and item_doc.weight_per_unit:
                            weight_per_unit = flt(item_doc.weight_per_unit)
                            item_weight = weight_per_unit * qty
                            
                            # Umrechnung auf Gramm, falls nötig
                            if hasattr(item_doc, 'weight_uom') and item_doc.weight_uom:
                                if item_doc.weight_uom.lower() in ['kg', 'kilogram']:
                                    item_weight = item_weight * 1000  # kg zu g
                            
                            total_net_weight += item_weight
                            frappe.log_error(
                                f"  Item {item_code}: Gewicht {weight_per_unit} {getattr(item_doc, 'weight_uom', 'g')} * qty {qty} = {item_weight}g",
                                "DEBUG: weight_calc_dn_creation"
                            )
                        else:
                            frappe.log_error(
                                f"  Item {item_code}: Kein weight_per_unit im Item-Dokument",
                                "WARNING: weight_missing_dn_creation"
                            )
                    except Exception as e:
                        frappe.log_error(
                            f"⚠️ Konnte Gewicht für Item {item_code} nicht berechnen: {str(e)}",
                            "WARNING: weight_calc_error_dn_creation"
                        )
                    
                    delivery_note_items.append({
                        "doctype": "Delivery Note Item",
                        "item_code": item_code,
                        "item_name": item['product'].get('item_name', item_code),
                        "qty": qty,
                            "rate": item['product'].get('rate', 0),
                            "amount": item['product'].get('amount', 0),
                            "uom": item['product'].get('uom', 'Stk'),
                            "stock_uom": item['product'].get('stock_uom', 'Stk'),
                            "conversion_factor": item['product'].get('conversion_factor', 1.0),
                        "stock_qty": item['product'].get('stock_qty', qty),
                            "base_amount": item['product'].get('base_amount', item['product'].get('amount', 0)),
                            "base_rate": item['product'].get('base_rate', item['product'].get('rate', 0)),
                            "warehouse": item['product'].get('warehouse', get_default_warehouse()),
                            "delivery_date": item['product'].get('delivery_date', today()),
                            "sales_order": item['sales_order'],
                            "sales_order_item": None,
                            "allow_zero_valuation_rate": 1,
                        "net_weight": item_weight,  # Setze Gewicht für jedes Item
                    })
                
                frappe.log_error(
                    f"✅ Gesamtgewicht berechnet: {total_net_weight}g für Delivery Note",
                    "INFO: total_weight_calculated_dn"
                )
                
                # Erstelle Delivery Note
                delivery_note_data = {
                    "doctype": "Delivery Note",
                    "customer": shipping_target,
                    "posting_date": today(),
                    "posting_time": frappe.utils.nowtime(),
                    "items": delivery_note_items,
                    "customer_address": target_sales_order.customer_address,
                    "shipping_address_name": target_sales_order.shipping_address_name,
                    "remarks": f"Delivery Note aus Sammelbestellung: {sammelbestellung_doc.name} | Versandziel: {shipping_target} | {len(all_products)} Produkte von {len(orders_for_target)} Kunden",
                    "po_no": target_sales_order.po_no,
                    "company": target_sales_order.company,
                    "currency": target_sales_order.currency,
                    "status": "Draft",
                    "custom_party_reference": target_sales_order.custom_party_reference,
                    "taxes_and_charges": None,
                    "selling_price_list": target_sales_order.selling_price_list,
                    "total_net_weight": total_net_weight,  # Setze Gesamtgewicht
                }
                
                # Debug: Prüfe ob Trenner-Items vorhanden sind
                trenner_count = sum(1 for item in all_products if item.get('product', {}).get('item_code') == '---')
                frappe.log_error(f"🔍 Trenner-Items in Delivery Note: {trenner_count} von {len(all_products)} Items", "DEBUG: separator_items_check_dn")
                
                delivery_note = frappe.get_doc(delivery_note_data)
                
                # Debug: Prüfe ob Trenner-Items nach doc creation vorhanden sind
                trenner_after_doc = sum(1 for item in delivery_note.items if item.item_code == '---')
                frappe.log_error(f"🔍 Trenner-Items nach doc creation: {trenner_after_doc} von {len(delivery_note.items)} Items", "DEBUG: separator_items_after_doc")
                
                # WICHTIG: Setze Flags VOR dem insert, damit Validierungen übersprungen werden
                # Dies ist eine zusätzliche Sicherheitsmaßnahme, falls der Hook nicht greift
                delivery_note.flags.ignore_warehouse_validation = True
                delivery_note.flags.ignore_stock_validation = True
                delivery_note.flags.ignore_gl_entries = True
                delivery_note.flags.ignore_valuation_rate = True
                
                # Stelle sicher, dass alle Items "Allow Zero Valuation" haben
                if hasattr(delivery_note, 'items') and delivery_note.items:
                    for item in delivery_note.items:
                        if hasattr(item, 'allow_zero_valuation_rate'):
                            item.allow_zero_valuation_rate = 1
                        elif hasattr(item, 'allow_zero_valuation'):
                            item.allow_zero_valuation = 1
                
                delivery_note.insert()
                
                # WICHTIG: Setze total_net_weight direkt NACH dem insert und speichere
                # DeliveryNote hat keine calculate_total() Methode, daher setzen wir es direkt
                try:
                    # Berechne total_net_weight aus den Items
                    calculated_weight = 0.0
                    for item in delivery_note.items:
                        if item.item_code != "---" and hasattr(item, 'net_weight') and item.net_weight:
                            calculated_weight += flt(item.net_weight) * flt(item.qty)
                    
                    # Setze das Gewicht direkt
                    delivery_note.total_net_weight = calculated_weight
                    delivery_note.db_update()  # Speichere direkt in der DB
                    
                    frappe.log_error(
                        f"✅ total_net_weight nach insert gesetzt: {delivery_note.total_net_weight}g",
                        "INFO: total_weight_set_after_insert"
                    )
                except Exception as e:
                    frappe.log_error(
                        f"⚠️ Fehler beim Setzen des Gewichts: {str(e)}",
                        "WARNING: weight_set_error"
                    )
                
                # Debug: Prüfe ob Trenner-Items nach insert noch vorhanden sind
                trenner_after_insert = sum(1 for item in delivery_note.items if item.item_code == '---')
                frappe.log_error(f"🔍 Trenner-Items nach insert: {trenner_after_insert} von {len(delivery_note.items)} Items", "DEBUG: separator_items_after_insert_dn")
                
                # Debug: Zeige Details aller Trenner-Items
                for idx, item in enumerate(delivery_note.items):
                    if item.item_code == '---':
                        frappe.log_error(f"🔍 Trenner-Item #{idx}: item_code='{item.item_code}', item_name='{item.item_name}', qty={item.qty}", "DEBUG: separator_item_details")
                
                frappe.log_error(
                    f"✅ Delivery Note erstellt: {delivery_note.name} für {shipping_target} (total_net_weight: {delivery_note.total_net_weight}g)",
                    "SUCCESS: delivery_note_created"
                )
                
                # Delivery Note NICHT einreichen - nur als Entwurf speichern
                # Das Buchen kommt später von woanders
                
                created_delivery_notes.append(delivery_note.name)
                
            except Exception as e:
                frappe.log_error(f"❌ Fehler beim Erstellen der Delivery Note für {shipping_target}: {str(e)}", "ERROR: delivery_note_creation_error")
                continue
        
        frappe.log_error(f"🎉 Delivery Notes erstellt: {created_delivery_notes}", "SUCCESS: all_delivery_notes_created")
        return created_delivery_notes
        
    except Exception as e:
        frappe.log_error(f"💥 Allgemeiner Fehler in create_delivery_notes_for_receiving_customers: {str(e)}\n{frappe.get_traceback()}", "ERROR: delivery_note_function_error")
        return []



