# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
import types

def ensure_inclusive_taxes(doc):
    """
    Setzt automatisch Steuern auf "inklusive" für Subscription-Rechnungen
    Entspricht der Logik aus dem Client-Script
    Wird speziell für automatisch erstellte Subscription-Rechnungen verwendet
    """
    if not doc or doc.doctype != "Sales Invoice":
        return
    
    # Nur im Entwurfsmodus (docstatus == 0)
    # Diese Funktion wird nur aufgerufen, wenn die Rechnung bereits auf Draft gesetzt wurde
    if doc.docstatus != 0:
        frappe.log_error(f"ensure_inclusive_taxes: Rechnung {doc.name} ist nicht im Draft-Modus (docstatus={doc.docstatus})", "WARNING: ensure_inclusive_taxes")
        return
    
    # Setze Steuer-Template wenn nicht gesetzt
    if not doc.taxes_and_charges:
        tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
            {"company": doc.company, "is_default": 1}, "name")
        if tax_template:
            doc.taxes_and_charges = tax_template
            doc.taxes = []  # Leere bestehende Steuern
            doc.run_method("set_taxes")  # Setze Steuern neu
            frappe.log_error(f"ensure_inclusive_taxes: Steuer-Template {tax_template} gesetzt für Rechnung {doc.name}", "DEBUG: ensure_inclusive_taxes")
    
    # Setze alle Steuern auf "inklusive"
    if doc.taxes:
        changed = False
        for tax in doc.taxes:
            if tax.included_in_print_rate != 1:
                tax.included_in_print_rate = 1
                changed = True
                frappe.log_error(f"ensure_inclusive_taxes: Steuer {tax.account_head} auf inklusiv gesetzt für Rechnung {doc.name}", "DEBUG: ensure_inclusive_taxes")
        
        # Neuberechnung mit inklusiven Steuern nur wenn sich etwas geändert hat
        if changed:
            doc.calculate_taxes_and_totals()
            frappe.log_error(f"ensure_inclusive_taxes: Steuern neu berechnet für Rechnung {doc.name}", "DEBUG: ensure_inclusive_taxes")


def before_validate_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_validate
    Umgeht die Adress-Validierung für Party-Rechnungen und fremde Lieferadressen
    Überträgt Party-Referenz von Sales Order zu Sales Invoice
    Aktualisiert Adressen automatisch im Entwurfsmodus
    Setzt custom_auftrag Feld aus Sales Order
    """
    if doc.doctype != "Sales Invoice":
        return
    
    # Setze custom_auftrag Feld aus Sales Order
    if doc.items and not doc.custom_auftrag:
        for item in doc.items:
            if item.sales_order:
                doc.custom_auftrag = item.sales_order
                break
    
    # Für Party/Sammelbestellung-Rechnungen: Deaktiviere Validierungen und setze Steuern
    if hasattr(doc, "custom_party_reference") and doc.custom_party_reference:
        # Deaktiviere ERPNext-Validierungen
        doc.flags.ignore_validate_update_after_submit = True
        doc.flags.ignore_validate = True  # Temporär für die Validierung
        doc.flags.ignore_mandatory = True  # Temporär für die Validierung
        doc.flags.ignore_pricing_rule = True
        doc.flags.ignore_item_price = True
        
        # Setze Steuer-Template wenn nicht gesetzt (falls ensure_inclusive_taxes es nicht schon gemacht hat)
        if not doc.taxes_and_charges:
            tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
                {"company": doc.company, "is_default": 1}, "name")
            if tax_template:
                doc.taxes_and_charges = tax_template
                doc.taxes = []  # Leere bestehende Steuern
                doc.run_method("set_taxes")  # Setze Steuern neu
                
                # Setze alle Steuern auf "inklusive"
                if doc.taxes:
                    for tax in doc.taxes:
                        tax.included_in_print_rate = 1
                    # Neuberechnung mit inklusiven Steuern
                    doc.calculate_taxes_and_totals()
    
    # AUSKOMMENTIERT: Adress-Synchronisation im Entwurfsmodus deaktiviert
    # if doc.docstatus == 0:  # Nur im Entwurfsmodus
    #     sync_addresses_in_draft(doc)
    
    # AUSKOMMENTIERT: Adress-Synchronisation beim Buchen deaktiviert
    # if doc.docstatus == 1 and hasattr(doc, '_doc_before_save'):
    #     sync_addresses_before_submit(doc)
    
    # Prüfe, ob es sich um eine Party/Sammelbestellung-Rechnung handelt und übertrage Referenz
    is_party_invoice = False
    party_reference = None
    
    if doc.items:
        for item in doc.items:
            if item.sales_order:
                party_ref = frappe.db.get_value("Sales Order", item.sales_order, "custom_party_reference")
                if party_ref:
                    is_party_invoice = True
                    party_reference = party_ref
                    break
    
    # Setze Party/Sammelbestellung-Referenz, falls noch nicht gesetzt
    if party_reference and not getattr(doc, "custom_party_reference", None):
        doc.custom_party_reference = party_reference
        frappe.log_error(f"Party/Sammelbestellung-Referenz {party_reference} zu Sales Invoice {doc.name} übertragen", "INFO: party_reference_transferred")
    
    # Prüfe, ob fremde Lieferadresse verwendet wird
    is_foreign_shipping = False
    if doc.shipping_address_name and doc.customer:
        # Finde heraus, welcher Customer zur Lieferadresse gehört
        links = frappe.get_all("Dynamic Link", 
            filters={
                "parent": doc.shipping_address_name,
                "parenttype": "Address",
                "link_doctype": "Customer"
            },
            fields=["link_name"]
        )
        if links:
            shipping_customer = links[0].link_name
            if shipping_customer != doc.customer:
                is_foreign_shipping = True
    
    # Deaktiviere Validierungen für Party/Sammelbestellung-Rechnungen
    if is_party_invoice or is_foreign_shipping:
        # Deaktiviere ERPNext-Validierungen
        doc.flags.ignore_validate_update_after_submit = True
        doc.flags.ignore_validate = True  # Temporär für die Validierung
        doc.flags.ignore_mandatory = True  # Temporär für die Validierung
        doc.flags.ignore_links = True  # Ignoriere Link-Validierungen
        doc.flags.ignore_permissions = True  # Ignoriere Berechtigungen
        doc.flags.ignore_address_validation = True  # Ignoriere Adress-Validierung
        doc.flags.ignore_shipping_validation = True  # Ignoriere Versand-Validierung
        doc.flags.ignore_billing_validation = True  # Ignoriere Rechnungs-Validierung
        
        # Verhindere die Adress-Validierung komplett
        if hasattr(doc, '_validate_shipping_address'):
            delattr(doc, '_validate_shipping_address')
        if hasattr(doc, '_validate_billing_address'):
            delattr(doc, '_validate_billing_address')
        
        # Deaktiviere Adress-Validierungen
        def safe_validate_party_address(self, *args, **kwargs):
            frappe.log_error(f"✅ Überspringe validate_party_address für {self.customer}", "INFO: skip_party_address_validation")
            pass
        
        def safe_validate_party_address_and_contact(self):
            frappe.log_error(f"✅ Überspringe validate_party_address_and_contact für {self.customer}", "INFO: skip_party_validation")
            pass
        
        def safe_validate_shipping_address(self):
            frappe.log_error(f"✅ Überspringe validate_shipping_address für {self.customer}", "INFO: skip_shipping_validation")
            pass
        
        def safe_validate_billing_address(self):
            frappe.log_error(f"✅ Überspringe validate_billing_address für {self.customer}", "INFO: skip_billing_validation")
            pass
        
        def safe_validate_address(self):
            frappe.log_error(f"✅ Überspringe validate_address für {self.customer}", "INFO: skip_address_validation")
            pass
        
        # Überschreibe alle Validierungsmethoden
        doc.validate_party_address = types.MethodType(safe_validate_party_address, doc)
        doc.validate_party_address_and_contact = types.MethodType(safe_validate_party_address_and_contact, doc)
        doc.validate_shipping_address = types.MethodType(safe_validate_shipping_address, doc)
        doc.validate_billing_address = types.MethodType(safe_validate_billing_address, doc)
        doc.validate_address = types.MethodType(safe_validate_address, doc)
        
        # Setze Steuer-Template wenn nicht gesetzt
        if not doc.taxes_and_charges:
            tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
                {"company": doc.company, "is_default": 1}, "name")
            if tax_template:
                doc.taxes_and_charges = tax_template
                doc.taxes = []  # Leere bestehende Steuern
                doc.run_method("set_taxes")  # Setze Steuern neu
                
                # Setze alle Steuern auf "inklusive"
                if doc.taxes:
                    for tax in doc.taxes:
                        tax.included_in_print_rate = 1
                    # Neuberechnung mit inklusiven Steuern
                    doc.calculate_taxes_and_totals()

def sync_addresses_in_draft(doc):
    """
    Synchronisiert Adressen in Rechnungen im Entwurfsmodus mit den aktuellen Kundenadressen.
    Wird nur aufgerufen wenn docstatus == 0 (Entwurfsmodus).
    """
    if not doc.customer:
        return
    
    try:
        # Finde die aktuelle Standard-Billing-Adresse des Kunden
        current_billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": doc.customer,
                "parenttype": "Address"
            },
            fields=["parent"],
            limit=1
        )
        
        if current_billing_address:
            current_billing_address = current_billing_address[0].parent
            
            # Prüfe, ob die aktuelle Adresse in der Rechnung anders ist
            if doc.customer_address != current_billing_address:
                # Lade die neue Adresse
                new_address = frappe.get_doc("Address", current_billing_address)
                
                # Aktualisiere die Rechnungsadresse
                doc.customer_address = current_billing_address
                doc.address_display = new_address.get_display()
                
                frappe.log_error(
                    f"Adresse in Rechnung {doc.name} aktualisiert: {doc.customer_address} -> {current_billing_address}",
                    "INFO: address_sync_draft"
                )
        
        # AUSKOMMENTIERT: Automatische Versandadresse-Synchronisation deaktiviert
        # Das überschreibt manuell ausgewählte Versandadressen
        # Optional: Auch Versandadresse synchronisieren, falls sie zum gleichen Kunden gehört
        """
        if doc.shipping_address_name:
            # Prüfe, ob die Versandadresse zum Kunden gehört
            shipping_links = frappe.get_all("Dynamic Link",
                filters={
                    "parent": doc.shipping_address_name,
                    "parenttype": "Address",
                    "link_doctype": "Customer",
                    "link_name": doc.customer
                },
                fields=["parent"]
            )
            
            if shipping_links:
                # Versandadresse gehört zum Kunden - finde die aktuelle Standard-Versandadresse
                current_shipping_address = frappe.get_all("Dynamic Link",
                    filters={
                        "link_doctype": "Customer",
                        "link_name": doc.customer,
                        "parenttype": "Address"
                    },
                    fields=["parent"],
                    limit=1
                )
                
                if current_shipping_address:
                    current_shipping_address = current_shipping_address[0].parent
                    
                    if doc.shipping_address_name != current_shipping_address:
                        # Lade die neue Versandadresse
                        new_shipping_address = frappe.get_doc("Address", current_shipping_address)
                        
                        # Aktualisiere die Versandadresse
                        doc.shipping_address_name = current_shipping_address
                        doc.shipping_address = new_shipping_address.get_display()
                        
                        frappe.log_error(
                            f"Versandadresse in Rechnung {doc.name} aktualisiert: {doc.shipping_address_name} -> {current_shipping_address}",
                            "INFO: shipping_address_sync_draft"
                        )
        """
    
    except Exception as e:
        frappe.log_error(f"Fehler beim Synchronisieren der Adressen in Rechnung {doc.name}: {str(e)}", "ERROR: address_sync")

def sync_addresses_before_submit(doc):
    """
    Synchronisiert Adressen BEVOR die Rechnung gebucht wird.
    Zeigt eine Warnung an, wenn Adressen geändert wurden.
    """
    if not doc.customer:
        return
    
    try:
        # Finde die aktuelle Standard-Billing-Adresse des Kunden
        current_billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": doc.customer,
                "parenttype": "Address"
            },
            fields=["parent"],
            limit=1
        )
        
        if current_billing_address:
            current_billing_address = current_billing_address[0].parent
            
            # Prüfe, ob die aktuelle Adresse in der Rechnung anders ist
            if doc.customer_address != current_billing_address:
                # Lade die neue Adresse
                new_address = frappe.get_doc("Address", current_billing_address)
                
                # Aktualisiere die Rechnungsadresse
                old_address = doc.customer_address
                doc.customer_address = current_billing_address
                doc.address_display = new_address.get_display()
                
                # Zeige eine Warnung an
                frappe.msgprint(
                    f"Die Rechnungsadresse wurde automatisch von '{old_address}' auf '{current_billing_address}' aktualisiert.",
                    title="Adresse aktualisiert",
                    indicator="blue"
                )
                
                frappe.log_error(
                    f"Adresse in Rechnung {doc.name} beim Buchen aktualisiert: {old_address} -> {current_billing_address}",
                    "INFO: address_sync_before_submit"
                )
        
        # Optional: Auch Versandadresse synchronisieren
        if doc.shipping_address_name:
            # Prüfe, ob die Versandadresse zum Kunden gehört
            shipping_links = frappe.get_all("Dynamic Link",
                filters={
                    "parent": doc.shipping_address_name,
                    "parenttype": "Address",
                    "link_doctype": "Customer",
                    "link_name": doc.customer
                },
                fields=["parent"]
            )
            
            if shipping_links:
                # Versandadresse gehört zum Kunden - finde die aktuelle Standard-Versandadresse
                current_shipping_address = frappe.get_all("Dynamic Link",
                    filters={
                        "link_doctype": "Customer",
                        "link_name": doc.customer,
                        "parenttype": "Address"
                    },
                    fields=["parent"],
                    limit=1
                )
                
                if current_shipping_address:
                    current_shipping_address = current_shipping_address[0].parent
                    
                    if doc.shipping_address_name != current_shipping_address:
                        # Lade die neue Versandadresse
                        new_shipping_address = frappe.get_doc("Address", current_shipping_address)
                        
                        # Aktualisiere die Versandadresse
                        old_shipping_address = doc.shipping_address_name
                        doc.shipping_address_name = current_shipping_address
                        doc.shipping_address = new_shipping_address.get_display()
                        
                        # Zeige eine Warnung an
                        frappe.msgprint(
                            f"Die Versandadresse wurde automatisch von '{old_shipping_address}' auf '{current_shipping_address}' aktualisiert.",
                            title="Versandadresse aktualisiert",
                            indicator="blue"
                        )
                        
                        frappe.log_error(
                            f"Versandadresse in Rechnung {doc.name} beim Buchen aktualisiert: {old_shipping_address} -> {current_shipping_address}",
                            "INFO: shipping_address_sync_before_submit"
                        )
    
    except Exception as e:
        frappe.log_error(f"Fehler beim Synchronisieren der Adressen beim Buchen der Rechnung {doc.name}: {str(e)}", "ERROR: address_sync_before_submit")

@frappe.whitelist()
def get_current_customer_addresses(customer):
    """
    Gibt die aktuellen Standard-Adressen eines Kunden zurück.
    Wird von JavaScript aufgerufen für sofortige Adress-Synchronisation.
    """
    try:
        # Finde die aktuelle Standard-Billing-Adresse (bevorzugte Rechnungsadresse)
        billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": customer,
                "parenttype": "Address"
            },
            fields=["parent"]
        )
        
        billing_address_name = None
        billing_display = None
        
        if billing_address:
            # Suche zuerst nach bevorzugter Rechnungsadresse
            for addr_link in billing_address:
                addr_doc = frappe.get_doc("Address", addr_link.parent)
                if addr_doc.is_primary_address:
                    billing_address_name = addr_link.parent
                    billing_display = addr_doc.get_display()
                    break
            
            # Falls keine bevorzugte gefunden, nimm die erste verfügbare
            if not billing_address_name:
                billing_address_name = billing_address[0].parent
                billing_doc = frappe.get_doc("Address", billing_address_name)
                billing_display = billing_doc.get_display()
        
        # Finde die aktuelle Standard-Versandadresse (bevorzugte Lieferadresse)
        shipping_address_name = None
        shipping_display = None
        
        if billing_address:
            # Suche zuerst nach bevorzugter Lieferadresse
            for addr_link in billing_address:
                addr_doc = frappe.get_doc("Address", addr_link.parent)
                if addr_doc.is_shipping_address:
                    shipping_address_name = addr_link.parent
                    shipping_display = addr_doc.get_display()
                    break
            
            # Falls keine bevorzugte gefunden, nimm die Billing-Adresse
            if not shipping_address_name:
                shipping_address_name = billing_address_name
                shipping_display = billing_display
        
        return {
            "billing_address": billing_address_name,
            "billing_display": billing_display,
            "shipping_address": shipping_address_name,
            "shipping_display": shipping_display
        }
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Abrufen der Kundenadressen für {customer}: {str(e)}", "ERROR: get_customer_addresses")
        return {
            "billing_address": None,
            "billing_display": None,
            "shipping_address": None,
            "shipping_display": None
        }

def after_insert_sales_invoice(doc, method):
    """Hook für Sales Invoice after_insert - keine spezielle Logik mehr nötig"""
    pass


def before_submit_netto_invoice_totals(doc, method):
    """
    Hook für Sales Invoice before_submit
    Bei Netto-Rechnungen (custom_brutto_netto): Setzt grand_total = net_total und Steuern auf 0.
    Damit exportiert die E-Rechnung den korrekten Zahlbetrag (net_total statt grand_total).
    Die Buchhaltung bucht dann korrekt nur den Nettobetrag (typisch für Kleinunternehmer §19 UStG).
    """
    if doc.doctype != "Sales Invoice":
        return
    if not doc.get("custom_brutto_netto"):
        return

    old_grand_total = flt(doc.grand_total)
    new_grand_total = flt(doc.net_total, doc.precision("grand_total"))

    # Steuerbeträge auf 0 setzen
    if doc.get("taxes"):
        for tax in doc.taxes:
            tax.tax_amount = 0
            tax.base_tax_amount = 0
            tax.tax_amount_after_discount_amount = 0
            tax.base_tax_amount_after_discount_amount = 0
            tax.total = flt(doc.net_total, tax.precision("total"))
            tax.base_total = flt(doc.base_net_total, tax.precision("base_total"))

    # Gesamtsummen auf Netto setzen
    doc.total_taxes_and_charges = 0
    doc.base_total_taxes_and_charges = 0
    doc.grand_total = new_grand_total
    doc.base_grand_total = flt(doc.base_net_total, doc.precision("base_grand_total"))

    # Rounded Total: Wenn verwendet, auf gerundeten Nettobetrag setzen
    if not doc.get("disable_rounded_total"):
        doc.rounded_total = flt(doc.grand_total, 0)  # Auf ganze Einheit runden
        doc.base_rounded_total = flt(doc.base_grand_total, 0)
        doc.rounding_adjustment = flt(doc.rounded_total - doc.grand_total, doc.precision("rounding_adjustment"))
        doc.base_rounding_adjustment = flt(doc.base_rounded_total - doc.base_grand_total, doc.precision("base_rounding_adjustment"))

    # Payment Schedule: Beträge proportional anpassen (von Brutto auf Netto)
    if doc.get("payment_schedule") and old_grand_total and old_grand_total != new_grand_total:
        for row in doc.payment_schedule:
            if row.payment_amount:
                row.payment_amount = flt(row.payment_amount * new_grand_total / old_grand_total, doc.precision("grand_total"))


def after_save_sales_invoice(doc, method):
    """
    Hook für Sales Invoice after_save
    Sendet automatisch eine E-Mail mit der Rechnung an den Kunden, wenn die Rechnung gebucht wurde
    """
    # Debug-Log um zu sehen, ob die Funktion aufgerufen wird
    frappe.log_error(f"after_save_sales_invoice aufgerufen für {doc.name}, docstatus: {doc.docstatus}", "DEBUG: after_save_sales_invoice")
    
    if doc.doctype != "Sales Invoice":
        return
    
    # Nur wenn die Rechnung gebucht wurde (docstatus == 1)
    if doc.docstatus != 1:
        frappe.log_error(f"Rechnung {doc.name} ist nicht gebucht (docstatus={doc.docstatus}) - E-Mail wird nicht versendet", "DEBUG: after_save_sales_invoice")
        return
    
    # Prüfe ob bereits eine E-Mail für diese Rechnung gesendet wurde
    try:
        # Prüfe ob bereits eine Email Queue für diese Invoice existiert
        email_queues = frappe.get_all("Email Queue",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": doc.name,
                "status": ["!=", "Error"]
            },
            fields=["name"],
            limit=1
        )
        
        if email_queues:
            frappe.log_error(f"E-Mail bereits gesendet für Invoice {doc.name} (Email Queue gefunden: {email_queues[0].name})", "DEBUG: invoice_email_already_sent")
            return
        
        # Prüfe ob bereits eine Communication für diese Invoice existiert
        communications = frappe.get_all("Communication",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": doc.name,
                "communication_type": "Communication",
                "sent_or_received": "Sent"
            },
            fields=["name"],
            limit=1
        )
        
        if communications:
            frappe.log_error(f"E-Mail bereits gesendet für Invoice {doc.name} (Communication gefunden: {communications[0].name})", "DEBUG: invoice_email_already_sent")
            return
        
        # Hole E-Mail-Adresse des Kunden
        email_to = None
        
        # Versuche zuerst contact_email aus der Rechnung
        if getattr(doc, "contact_email", None):
            email_to = doc.contact_email
        
        # Falls nicht vorhanden, hole E-Mail vom Customer
        if not email_to:
            email_to = frappe.db.get_value("Customer", doc.customer, "email_id")
        
        # Falls immer noch keine E-Mail-Adresse, überspringe Versand
        if not email_to:
            frappe.log_error(f"Keine E-Mail-Adresse für Invoice {doc.name} gefunden - Versand übersprungen", "WARNING: invoice_email_no_address")
            return
        
        # Sende E-Mail mit Rechnung via communication.email._make
        # Damit erscheint die E-Mail in der Mail Queue und in der Aktivität der Rechnung
        try:
            # Lade das Dokument neu, um sicherzustellen, dass alle Daten aktuell sind
            invoice_doc = frappe.get_doc("Sales Invoice", doc.name)
            
            # Lade das E-Mail-Template "Rechnung" explizit
            from frappe.email.doctype.email_template.email_template import get_email_template
            
            email_template_name = "Rechnung"
            email_template = get_email_template(email_template_name, doc=invoice_doc.as_dict())
            template_subject = email_template.get("subject") if email_template else None
            template_message = email_template.get("message") if email_template else None
            
            print_format = invoice_doc.meta.default_print_format or "Standard"
            
            # communication.email._make erstellt eine Communication (Aktivität) und fügt die E-Mail der Mail Queue hinzu
            from frappe.core.doctype.communication.email import _make
            
            _make(
                doctype="Sales Invoice",
                name=invoice_doc.name,
                recipients=[email_to],
                subject=template_subject,
                content=template_message,
                send_email=True,
                print_format=print_format,  # Rechnung-PDF wird automatisch angehängt
                communication_type="Communication",
                now=False,  # False = E-Mail kommt in die Mail Queue (sichtbar), True = sofort senden
            )
            
            frappe.log_error(f"E-Mail in Queue/Activity eingetragen für Invoice {invoice_doc.name} an {email_to} (Template '{email_template_name}')", "INFO: invoice_email_sent")
            
        except Exception as e:
            frappe.log_error(f"Fehler beim Versenden der E-Mail für Invoice {doc.name}: {str(e)}", "ERROR: invoice_email_send_failed")
            import traceback
            frappe.log_error(f"Traceback: {traceback.format_exc()}", "ERROR: invoice_email_send_failed_traceback")
    
    except Exception as e:
        frappe.log_error(f"Fehler in after_save_sales_invoice für {doc.name}: {str(e)}", "ERROR: after_save_sales_invoice")

def onload_sales_invoice(doc, method):
    """
    Hook für Sales Invoice onload
    AUSKOMMENTIERT: Adress-Synchronisation beim Laden deaktiviert
    """
    # AUSKOMMENTIERT: Adress-Synchronisation beim Laden deaktiviert
    # Das überschreibt manuell ausgewählte Adressen
    return
    
    if doc.doctype != "Sales Invoice":
        return
    
    # Nur im Entwurfsmodus
    if doc.docstatus != 0:
        return
    
    if not doc.customer:
        return
    
    try:
        # Prüfe, ob Adressen synchronisiert werden müssen
        needs_sync = False
        
        # Finde die aktuelle Standard-Billing-Adresse des Kunden
        current_billing_address = frappe.get_all("Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": doc.customer,
                "parenttype": "Address"
            },
            fields=["parent"],
            limit=1
        )
        
        if current_billing_address:
            current_billing_address = current_billing_address[0].parent
            
            # Prüfe, ob die aktuelle Adresse in der Rechnung anders ist
            if doc.customer_address != current_billing_address:
                needs_sync = True
                
                # Lade die neue Adresse
                new_address = frappe.get_doc("Address", current_billing_address)
                
                # Aktualisiere die Rechnungsadresse
                doc.customer_address = current_billing_address
                doc.address_display = new_address.get_display()
                
                frappe.log_error(
                    f"Adresse in Rechnung {doc.name} beim Laden aktualisiert: {doc.customer_address} -> {current_billing_address}",
                    "INFO: address_sync_onload"
                )
        
        # Optional: Auch Versandadresse synchronisieren
        if doc.shipping_address_name:
            # Prüfe, ob die Versandadresse zum Kunden gehört
            shipping_links = frappe.get_all("Dynamic Link",
                filters={
                    "parent": doc.shipping_address_name,
                    "parenttype": "Address",
                    "link_doctype": "Customer",
                    "link_name": doc.customer
                },
                fields=["parent"]
            )
            
            if shipping_links:
                # Versandadresse gehört zum Kunden - finde die aktuelle Standard-Versandadresse
                current_shipping_address = frappe.get_all("Dynamic Link",
                    filters={
                        "link_doctype": "Customer",
                        "link_name": doc.customer,
                        "parenttype": "Address"
                    },
                    fields=["parent"],
                    limit=1
                )
                
                if current_shipping_address:
                    current_shipping_address = current_shipping_address[0].parent
                    
                    if doc.shipping_address_name != current_shipping_address:
                        needs_sync = True
                        
                        # Lade die neue Versandadresse
                        new_shipping_address = frappe.get_doc("Address", current_shipping_address)
                        
                        # Aktualisiere die Versandadresse
                        doc.shipping_address_name = current_shipping_address
                        doc.shipping_address = new_shipping_address.get_display()
                        
                        frappe.log_error(
                            f"Versandadresse in Rechnung {doc.name} beim Laden aktualisiert: {doc.shipping_address_name} -> {current_shipping_address}",
                            "INFO: shipping_address_sync_onload"
                        )
        
        # Wenn Adressen aktualisiert wurden, zeige eine Nachricht
        if needs_sync:
            frappe.msgprint(
                "Die Adressen wurden automatisch mit den aktuellen Kundenadressen synchronisiert.",
                title="Adressen aktualisiert",
                indicator="blue"
            )
    
    except Exception as e:
        frappe.log_error(f"Fehler beim Synchronisieren der Adressen beim Laden der Rechnung {doc.name}: {str(e)}", "ERROR: address_sync_onload")

def get_shipping_account():
    """Gibt das Standard-Versandkonto zurück"""
    try:
        company = frappe.defaults.get_global_default('company')
        if not company:
            company = frappe.get_all("Company", limit=1)[0].name
        
        cash_account = frappe.get_cached_value("Company", company, "default_cash_account")
        if cash_account:
            return cash_account
            
        account = frappe.get_all("Account", 
            filters={
                "company": company,
                "is_group": 0, 
                "account_type": ["in", ["Cash", "Bank"]],
                "disabled": 0
            },
            fields=["name"],
            limit=1)
        
        if account:
            return account[0].name
            
        account = frappe.get_all("Account", 
            filters={
                "company": company,
                "is_group": 0, 
                "root_type": "Asset",
                "disabled": 0
            },
            fields=["name"],
            limit=1)
        
        if account:
            return account[0].name
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Ermitteln des Versandkontos: {str(e)}", "ERROR: get_shipping_account")
    
    return "Bargeld - BM"

def add_shipping_to_sales_invoice(doc, method):
    """
    Hook für Sales Invoice before_save
    Fügt automatisch Versandkosten hinzu, wenn sie im referenzierten Sales Order vorhanden sind
    """
    if getattr(doc, "docstatus", 0) != 0:
        return
    
    if doc.doctype != "Sales Invoice" or not doc.items:
        return
    
    # Hole Versandkosten aus Sales Orders
    total_shipping_cost = 0
    processed_orders = set()
    
    for item in doc.items:
        if item.sales_order and item.sales_order not in processed_orders:
            so_doc = frappe.get_doc("Sales Order", item.sales_order)
            shipping_cost = so_doc.get("custom_calculated_shipping_cost") or 0
            
            if shipping_cost > 0:
                total_shipping_cost += shipping_cost
                processed_orders.add(item.sales_order)
    
    if total_shipping_cost <= 0:
        return
    
    # Prüfe ob bereits Versandkosten vorhanden sind
    existing_shipping = False
    if doc.taxes:
        for tax in doc.taxes:
            if tax.description and "versand" in tax.description.lower():
                existing_shipping = True
                break
    
    if existing_shipping:
        return
    
    # Füge Versandkosten hinzu
    tax_row = doc.append("taxes", {})
    tax_row.description = "Versandkosten"
    tax_row.account_head = get_shipping_account()
    tax_row.charge_type = "Actual"
    tax_row.tax_amount = flt(total_shipping_cost)
    tax_row.add_deduct_tax = "Add"

def auto_create_picklist_from_invoice(doc, method):
    """
    Hook für Sales Invoice on_submit
    Erstellt automatisch eine Picklist für die eingereichte Sales Invoice
    WICHTIG: Die Picklist wird IMMER nur als Entwurf erstellt, nie automatisch gebucht!
    """
    # Sicherstellen, dass die Picklist nie automatisch gebucht wird
    if method == "auto":
        method = None
    try:
        # Prüfe ob bereits eine Picklist existiert
        existing_picklists = frappe.get_all(
            "Pick List",
            filters={
                "docstatus": ["!=", 2],
                "custom_invoice_references": ["like", f"%{doc.name}%"]
            },
            fields=["name"],
            limit=1
        )
        
        if existing_picklists:
            return
        
        # Sammle Sales Order Informationen
        sales_orders = set()
        for item in doc.items:
            if item.sales_order:
                sales_orders.add(item.sales_order)
        
        if not sales_orders:
            return
        
        # Erstelle Picklist Items
        picklist_items = []
        
        for so_name in sales_orders:
            try:
                so_doc = frappe.get_doc("Sales Order", so_name)
                
                for so_item in so_doc.items:
                    if so_item.item_code and so_item.item_code.startswith("shipping-"):
                        continue
                    
                    warehouse = so_item.warehouse
                    if not warehouse:
                        warehouse = frappe.defaults.get_user_default("Warehouse")
                        if not warehouse:
                            warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, fields=["name"], limit=1)
                            warehouse = warehouses[0].name if warehouses else "Stores - Main"
                    
                    # Prüfe ob Item ein Product Bundle ist
                    bundle_items = frappe.get_all("Product Bundle Item", 
                                                 filters={"parent": so_item.item_code}, 
                                                 fields=["item_code", "qty", "uom", "description"])
                    
                    if bundle_items:
                        # Item ist ein Product Bundle - füge Bundle Items hinzu
                        frappe.log_error(f"Product Bundle erkannt: {so_item.item_code} mit {len(bundle_items)} Items", "INFO: bundle_detected")
                        for bundle_item in bundle_items:
                            bundle_qty = float(bundle_item.qty) * float(so_item.qty)
                            
                            picklist_item = {
                                "doctype": "Pick List Item",
                                "item_code": bundle_item.item_code,
                                "item_name": bundle_item.description or frappe.get_value("Item", bundle_item.item_code, "item_name"),
                                "qty": bundle_qty,
                                "stock_qty": bundle_qty,
                                "picked_qty": 0.0,
                                "stock_reserved_qty": 0.0,
                                "uom": bundle_item.uom or so_item.uom,
                                "stock_uom": bundle_item.uom or so_item.stock_uom or so_item.uom,
                                "conversion_factor": 1.0,
                                "warehouse": warehouse,
                                "sales_order": so_name,
                                "sales_order_item": so_item.name,
                                "batch_no": None,
                                "serial_no": None,
                                "use_serial_batch_fields": 0,
                                "serial_and_batch_bundle": None,
                                "product_bundle_item": so_item.item_code,  # Referenz zum Original Bundle
                                "material_request": None,
                                "material_request_item": None
                            }
                            
                            picklist_items.append(picklist_item)
                            frappe.log_error(f"Bundle Item hinzugefügt: {bundle_item.item_code} (Qty: {bundle_qty}) für Bundle {so_item.item_code}", "INFO: bundle_item_added")
                    else:
                        # Normaler Artikel - wie bisher
                        picklist_item = {
                            "doctype": "Pick List Item",
                            "item_code": so_item.item_code,
                            "item_name": so_item.item_name,
                            "qty": float(so_item.qty),
                            "stock_qty": float(so_item.stock_qty or so_item.qty),
                            "picked_qty": 0.0,
                            "stock_reserved_qty": 0.0,
                            "uom": so_item.uom,
                            "stock_uom": so_item.stock_uom or so_item.uom,
                            "conversion_factor": float(so_item.conversion_factor or 1.0),
                            "warehouse": warehouse,
                            "sales_order": so_name,
                            "sales_order_item": so_item.name,
                            "batch_no": None,
                            "serial_no": None,
                            "use_serial_batch_fields": 0,
                            "serial_and_batch_bundle": None,
                            "product_bundle_item": None,
                            "material_request": None,
                            "material_request_item": None
                        }
                        
                        picklist_items.append(picklist_item)
                    
            except Exception as e:
                continue
        
        if not picklist_items:
            return
        
        # Erstelle Invoice Reference
        try:
            customer_doc = frappe.get_doc("Customer", doc.customer)
            customer_display_name = customer_doc.customer_name or doc.customer
            if len(customer_display_name) > 15:
                customer_display_name = customer_display_name[:12] + "..."
        except:
            customer_display_name = doc.customer
        
        invoice_reference = f"{doc.name} ({customer_display_name})"
        
        # Erstelle Picklist
        picklist_data = {
            "doctype": "Pick List",
            "purpose": "Delivery",
            "company": doc.company,
            "customer": doc.customer,
            "custom_invoice_references": invoice_reference,
            "remarks": f"Automatisch erstellt für Rechnung: {doc.name}",
            "locations": picklist_items
        }
        
        picklist = frappe.get_doc(picklist_data)
        
        # Flags setzen um Lagerbestand-Validierung zu umgehen
        picklist.flags.ignore_permissions = True
        picklist.flags.ignore_mandatory = True
        picklist.flags.ignore_validate = True  # Ignoriere alle Validierungen
        picklist.docstatus = 0  # Explizit als Entwurf markieren
        
        # Überschreibe validate_for_qty um Lagerbestand-Prüfung zu umgehen
        def safe_validate_for_qty(self):
            pass
        
        import types
        picklist.validate_for_qty = types.MethodType(safe_validate_for_qty, picklist)
        
        # Stelle sicher, dass die Picklist als Entwurf erstellt wird
        picklist.insert()
        
        # WICHTIG: Stelle sicher, dass item_name für Trenn-Items erhalten bleibt
        # Frappe könnte den item_name beim Erstellen überschreiben, daher aktualisieren wir ihn
        picklist.reload()  # Lade die Pickliste neu
        separator_updated = False
        for picklist_item in picklist.locations:
            if picklist_item.item_code == '---':
                # Finde das entsprechende Sales Order Item
                if picklist_item.sales_order_item:
                    try:
                        so_item = frappe.get_doc("Sales Order Item", picklist_item.sales_order_item)
                        if so_item.item_name and "Bestellung für:" in so_item.item_name:
                            # item_name aus Sales Order hat Kundennamen - übernehme ihn
                            picklist_item.item_name = so_item.item_name
                            separator_updated = True
                            frappe.log_error(f"📋 Trenn-Item item_name aktualisiert in Pick List (aus Invoice): {picklist_item.item_name}", "DEBUG: separator_item_name_updated_picklist_invoice")
                    except Exception as e:
                        frappe.log_error(f"⚠️ Fehler beim Aktualisieren von item_name für Trenn-Item: {str(e)}", "WARNING: separator_item_name_update_failed_invoice")
        
        if separator_updated:
            picklist.save()  # Speichere die Änderungen
            frappe.log_error(f"✅ Pick List {picklist.name} Trenn-Item Namen aktualisiert (aus Invoice)", "INFO: separator_item_names_updated_picklist_invoice")
        
        # NICHT automatisch einreichen - da Artikel möglicherweise nicht lagernd sind
        # Die Picklist kann manuell eingereicht werden, wenn alle Artikel verfügbar sind
        
        frappe.publish_realtime(
            "show_alert",
            {"message": f"Picklist {picklist.name} wurde automatisch erstellt!", "indicator": "green"},
            user=frappe.session.user
        )
        
    except Exception as e:
        pass