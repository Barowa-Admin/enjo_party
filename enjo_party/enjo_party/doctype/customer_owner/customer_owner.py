# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CustomerOwner(Document):
	def find_sales_partner_for_user(self, user_email):
		"""
		Findet einen Sales Partner für einen User.
		Suchreihenfolge:
		1. Sales Partner mit user-Feld = user_email
		2. Sales Partner mit partner_name = full_name des Users
		3. Sales Partner mit partner_name = user_email
		"""
		sales_partner = None
		
		# 1. Versuche über user-Feld
		try:
			sales_partner_meta = frappe.get_meta("Sales Partner")
			if sales_partner_meta.has_field("user"):
				sales_partner = frappe.db.get_value("Sales Partner", {"user": user_email}, "name")
		except:
			pass
		
		# 2. Versuche über partner_name mit full_name
		if not sales_partner:
			try:
				user_full_name = frappe.db.get_value("User", user_email, "full_name")
				if user_full_name:
					sales_partner = frappe.db.get_value("Sales Partner", {"partner_name": user_full_name}, "name")
			except:
				pass
		
		# 3. Versuche über partner_name mit user_email direkt
		if not sales_partner:
			try:
				sales_partner = frappe.db.get_value("Sales Partner", {"partner_name": user_email}, "name")
			except:
				pass
		
		return sales_partner
	
	def validate(self):
		"""Validiere je nach Modus"""
		# Standard Modus prüfen
		mode = getattr(self, 'mode', 'Einzelne Kunden auswählen')
		
		if not self.new_owner:
			frappe.throw("Bitte wähle einen neuen Owner aus.")
		
		# Prüfe ob new_owner User existiert
		if not frappe.db.exists("User", self.new_owner):
			frappe.throw(f"Benutzer {self.new_owner} existiert nicht.")
		
		if mode == "Einzelne Kunden auswählen":
			# Validierung für Einzel-Modus
			if not self.customers or len(self.customers) == 0:
				frappe.throw("Bitte wähle mindestens einen Kunden aus.")
			
			# Prüfe ob alle Kunden existieren
			for customer_row in self.customers:
				if not customer_row.customer:
					frappe.throw("Bitte fülle alle Kundenfelder aus.")
				
				if not frappe.db.exists("Customer", customer_row.customer):
					frappe.throw(f"Kunde {customer_row.customer} existiert nicht.")
		
		elif mode == "Alle Kunden von Owner verschieben":
			# Kunden-Tabelle wird im Bulk-Modus nicht genutzt
			self.customers = []

			# Validierung für Bulk-Modus
			if not self.from_owner:
				frappe.throw("Bitte wähle einen 'Von Owner' aus.")
			
			# Prüfe ob from_owner User existiert
			if not frappe.db.exists("User", self.from_owner):
				frappe.throw(f"Benutzer {self.from_owner} existiert nicht.")
			
			# Prüfe dass from_owner und new_owner unterschiedlich sind
			if self.from_owner == self.new_owner:
				frappe.throw("'Von Owner' und 'Neuer Owner' müssen unterschiedlich sein.")
	
	def before_save(self):
		"""Ändere den Owner aller Kunden bevor das Dokument gespeichert wird"""
		mode = getattr(self, 'mode', 'Einzelne Kunden auswählen')
		
		if not self.new_owner:
			return
		
		if mode == "Einzelne Kunden auswählen":
			# Bestehende Logik für Einzel-Modus
			if not self.customers or len(self.customers) == 0:
				return
			
			success_count = 0
			failed_customers = []
			
			# Finde Sales Partner für neuen Owner
			sales_partner = self.find_sales_partner_for_user(self.new_owner)
			
			# Ändere den Owner für jeden Kunden
			for customer_row in self.customers:
				if customer_row.customer:
					try:
						# Ändere den Owner des Kunden
						frappe.db.set_value("Customer", customer_row.customer, "owner", self.new_owner, update_modified=False)
						
						# Setze auch den default_sales_partner
						if sales_partner:
							frappe.db.set_value("Customer", customer_row.customer, "default_sales_partner", sales_partner, update_modified=False)
						else:
							# Wenn kein Sales Partner gefunden, setze auf leer
							frappe.db.set_value("Customer", customer_row.customer, "default_sales_partner", "", update_modified=False)
						
						success_count += 1
						
						# Aktualisiere die Felder in der Tabelle
						customer_name = frappe.db.get_value("Customer", customer_row.customer, "customer_name")
						customer_row.customer_name = customer_name
						customer_row.current_owner = self.new_owner
					except Exception as e:
						failed_customers.append(f"{customer_row.customer}: {str(e)}")
			
			# Commit alle Änderungen
			frappe.db.commit()
			
			# Speichere Liste der verschobenen Kunden im Dokument (für Einzel-Modus)
			if success_count > 0:
				moved_customers_list = []
				for customer_row in self.customers:
					if customer_row.customer:
						customer_name = frappe.db.get_value("Customer", customer_row.customer, "customer_name")
						moved_customers_list.append(f"{customer_row.customer} - {customer_name}")
				
				if moved_customers_list:
					self.moved_customers_list = "\n".join(moved_customers_list)
			
			# Zeige Erfolgsmeldung (ohne Notification)
			if success_count > 0:
				message = f"✓ Erfolg! Owner für {success_count} Kunde(n) wurde auf {self.new_owner} geändert."
				if failed_customers:
					message += f"\n\nFehler bei {len(failed_customers)} Kunde(n):\n" + "\n".join(failed_customers)
				
				frappe.msgprint(
					message,
					indicator="green" if not failed_customers else "orange",
					alert=False
				)
		
		elif mode == "Alle Kunden von Owner verschieben":
			# Neue Logik für Bulk-Modus
			if not self.from_owner:
				return
			
			# Suche alle Kunden mit dem from_owner
			customers_to_move = frappe.db.sql("""
				SELECT name, customer_name 
				FROM `tabCustomer` 
				WHERE owner = %s
				ORDER BY customer_name
			""", (self.from_owner,), as_dict=True)
			
			if not customers_to_move:
				frappe.msgprint(
					f"Keine Kunden mit Owner '{self.from_owner}' gefunden.",
					indicator="orange",
					alert=True
				)
				return
			
			# Finde Sales Partner für neuen Owner
			sales_partner = self.find_sales_partner_for_user(self.new_owner)
			
			success_count = 0
			failed_customers = []
			moved_customers = []
			
			# Ändere den Owner für alle gefundenen Kunden
			for customer in customers_to_move:
				try:
					# Ändere den Owner des Kunden
					frappe.db.set_value("Customer", customer.name, "owner", self.new_owner, update_modified=False)
					
					# Setze auch den default_sales_partner
					if sales_partner:
						frappe.db.set_value("Customer", customer.name, "default_sales_partner", sales_partner, update_modified=False)
					else:
						# Wenn kein Sales Partner gefunden, setze auf leer
						frappe.db.set_value("Customer", customer.name, "default_sales_partner", "", update_modified=False)
					
					success_count += 1
					moved_customers.append(f"{customer.name} - {customer.customer_name}")
				except Exception as e:
					failed_customers.append(f"{customer.name} ({customer.customer_name}): {str(e)}")
			
			# Speichere Liste der verschobenen Kunden im Dokument
			if moved_customers:
				customers_list_text = "\n".join(moved_customers)
				self.moved_customers_list = customers_list_text
			else:
				self.moved_customers_list = ""
			
			# Commit alle Änderungen
			frappe.db.commit()
			
			# Zeige einfache Erfolgsmeldung (ohne Notification)
			if success_count > 0:
				message = f"✓ Erfolg! Owner für {success_count} Kunde(n) von '{self.from_owner}' wurde auf '{self.new_owner}' geändert."
				if failed_customers:
					message += f"\n\nFehler bei {len(failed_customers)} Kunde(n):\n" + "\n".join(failed_customers)
				
				frappe.msgprint(
					message,
					indicator="green" if not failed_customers else "orange",
					alert=False
				)
