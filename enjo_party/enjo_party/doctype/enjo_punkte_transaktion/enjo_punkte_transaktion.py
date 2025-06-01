# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ENJOPunkteTransaktion(Document):
	def validate(self):
		# Berechne Gesamtpunkte
		self.punkte_gesamt = flt(self.qty) * flt(self.punkte_pro_item)
		
		# Item Name automatisch setzen falls leer
		if self.item_code and not self.item_name:
			item_doc = frappe.get_cached_doc("Item", self.item_code)
			self.item_name = item_doc.item_name or self.item_code 