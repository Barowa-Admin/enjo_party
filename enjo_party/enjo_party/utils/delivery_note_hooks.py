# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
import types

def before_validate_delivery_note(doc, method):
    """
    Hook für Delivery Note before_validate
    Umgeht die Adress-Validierung für fremde Lieferadressen
    """
    if doc.doctype != "Delivery Note":
        return
    
    # Prüfe, ob es sich um eine fremde Lieferadresse handelt
    is_foreign_shipping = False
    
    if doc.shipping_address_name and doc.customer:
        # Prüfe, ob die Versandadresse zu einem anderen Kunden gehört
        try:
            # Suche alle Adressen die mit der shipping_address_name verknüpft sind
            address_links = frappe.get_all(
                "Dynamic Link",
                filters={"parent": doc.shipping_address_name, "parenttype": "Address"},
                fields=["link_doctype", "link_name"]
            )
            
            # Prüfe, ob die Adresse zu einem anderen Kunden gehört
            for link in address_links:
                if link.link_doctype == "Customer" and link.link_name != doc.customer:
                    is_foreign_shipping = True
                    frappe.log_error(f"Fremde Lieferadresse erkannt: {doc.shipping_address_name} gehört zu Kunde {link.link_name}, aber Delivery Note ist für Kunde {doc.customer}", "INFO: foreign_shipping_detected")
                    break
        except Exception as e:
            frappe.log_error(f"Fehler beim Prüfen der Versandadresse: {str(e)}", "WARNING: address_check_error")
    
    # Deaktiviere Validierungen für fremde Lieferadressen
    if is_foreign_shipping:
        frappe.log_error(f"✅ Fremde Lieferadresse erkannt für Delivery Note {doc.name} - Validierung deaktiviert", "INFO: foreign_shipping_detected")
        
        # Deaktiviere ERPNext-Validierungen
        doc.flags.ignore_validate = True
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_links = True
        doc.flags.ignore_permissions = True
        doc.flags.ignore_address_validation = True
        doc.flags.ignore_shipping_validation = True
        doc.flags.ignore_billing_validation = True
        
        # Überschreibe die Adress-Validierungsmethoden
        def safe_validate_party_address(self, *args, **kwargs):
            frappe.log_error(f"✅ Überspringe validate_party_address für {self.customer}", "INFO: skip_party_address_validation")
            pass
        
        def safe_validate_shipping_address(self):
            frappe.log_error(f"✅ Überspringe validate_shipping_address für {self.customer}", "INFO: skip_shipping_validation")
            pass
        
        def safe_validate_billing_address(self):
            frappe.log_error(f"✅ Überspringe validate_billing_address für {self.customer}", "INFO: skip_billing_validation")
            pass
        
        # Überschreibe nur die Adress-Validierungsmethoden
        doc.validate_party_address = types.MethodType(safe_validate_party_address, doc)
        doc.validate_shipping_address = types.MethodType(safe_validate_shipping_address, doc)
        doc.validate_billing_address = types.MethodType(safe_validate_billing_address, doc)
