# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

"""
Party-Status-Manipulation

Dieses Modul manipuliert den ECHTEN ERPNext-Status (per_billed, per_delivered, 
billing_status, delivery_status) für Parties.

Problem:
- Einzelne Kunden-Aufträge bekommen Rechnungen aber keine Lieferscheine
- Gruppenversand bekommt Lieferscheine aber keine Rechnungen
- ERPNext berechnet Status falsch weil die Dokumente "getrennt" sind

Lösung:
- Wenn ALLE Rechnungen der Party bezahlt sind → setze per_billed=100 
  für ALLE Sales Orders (inkl. Gruppenversand)
- Wenn Gruppenversand-Lieferschein gebucht → setze per_delivered=100 
  für ALLE Sales Orders (inkl. Kunden-Aufträge)
"""

import frappe
from frappe.utils import flt


def update_party_status_on_payment(doc, method):
    """
    Hook für Payment Entry on_submit
    Prüft ob alle Rechnungen einer Party bezahlt sind
    """
    try:
        # Finde alle Sales Invoices die durch diesen Payment Entry bezahlt wurden
        for ref in doc.references:
            if ref.reference_doctype == "Sales Invoice":
                invoice = frappe.get_doc("Sales Invoice", ref.reference_name)
                
                # Prüfe ob die Invoice zu einer Party gehört
                party_reference = getattr(invoice, "custom_party_reference", None)
                if party_reference and frappe.db.exists("Party", party_reference):
                    frappe.log_error(f"Payment für Party {party_reference} erkannt", 
                                    "INFO: party_payment")
                    update_party_billing_status(party_reference)
                    
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Billing-Status nach Zahlung: {str(e)}", 
                        "ERROR: party_status_payment")


def update_party_status_on_invoice_payment(doc, method):
    """
    Hook für Sales Invoice on_update_after_submit
    Wird aufgerufen wenn der outstanding_amount sich ändert
    """
    try:
        party_reference = getattr(doc, "custom_party_reference", None)
        if party_reference and frappe.db.exists("Party", party_reference):
            frappe.log_error(f"Invoice-Update für Party {party_reference}", 
                            "INFO: invoice_update")
            update_party_billing_status(party_reference)
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Update nach Invoice-Update: {str(e)}", 
                        "ERROR: party_status_invoice")


def update_party_status_on_delivery(doc, method):
    """
    Hook für Delivery Note on_submit
    Prüft ob es sich um einen Gruppenversand-Lieferschein handelt
    """
    try:
        # Finde den Sales Order für diesen Lieferschein
        sales_order_name = None
        for item in doc.items:
            if item.against_sales_order:
                sales_order_name = item.against_sales_order
                break
        
        if not sales_order_name:
            return
        
        # Hole den Sales Order
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        
        # Prüfe ob es ein Gruppenversand ist (custom_shipping_order = 1)
        is_shipping_order = getattr(sales_order, "custom_shipping_order", 0)
        if not is_shipping_order:
            return
        
        # Hole die Party-Referenz
        party_reference = getattr(sales_order, "custom_party_reference", None)
        if party_reference and frappe.db.exists("Party", party_reference):
            frappe.log_error(f"Gruppenversand-Lieferschein für Party {party_reference}", 
                           "INFO: shipping_delivery")
            update_party_delivery_status(party_reference)
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Update nach Lieferschein: {str(e)}", 
                        "ERROR: party_status_delivery")


def update_party_billing_status(party_name):
    """
    Prüft ob alle Rechnungen bezahlt sind und setzt per_billed=100 
    für ALLE Sales Orders der Party
    
    WICHTIG: Prüft nur ob alle existierenden Rechnungen bezahlt sind.
    Orders die keine Rechnungen bekommen (z.B. Vertriebspartner-Orders, Gruppenversand) 
    werden nicht als fehlend betrachtet.
    """
    try:
        # Finde alle GEBUCHTEN Sales Invoices der Party
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name", "outstanding_amount", "grand_total"]
        )
        
        if not invoices:
            frappe.log_error(f"Keine gebuchten Rechnungen für {party_name} gefunden", 
                           "DEBUG: no_invoices")
            return
        
        frappe.log_error(f"Gefunden: {len(invoices)} gebuchte Rechnungen für Party {party_name}", 
                        "DEBUG: invoice_count")
        
        # Prüfe ob ALLE Rechnungen bezahlt sind (outstanding_amount = 0)
        all_paid = True
        for inv in invoices:
            if flt(inv.outstanding_amount) > 0.01:
                all_paid = False
                frappe.log_error(f"Rechnung {inv.name} noch nicht bezahlt: {inv.outstanding_amount}", 
                               "DEBUG: invoice_not_paid")
                break
        
        if not all_paid:
            frappe.log_error(f"Nicht alle Rechnungen bezahlt für {party_name}", 
                           "DEBUG: not_all_paid")
            return
        
        frappe.log_error(f"ALLE {len(invoices)} Rechnungen bezahlt für {party_name} - setze Status!", 
                        "INFO: all_paid")
        
        # Finde ALLE Sales Orders der Party
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        # Setze per_billed=100 und billing_status="Fully Billed" für ALLE (inkl. Gruppenversand!)
        for so in sales_orders:
            # Lade das Dokument um den aktuellen per_delivered Status zu prüfen
            so_doc = frappe.get_doc("Sales Order", so.name)
            current_per_delivered = flt(so_doc.per_delivered) or 0
            
            # Setze Billing-Status
            frappe.db.set_value("Sales Order", so.name, {
                "per_billed": 100,
                "billing_status": "Fully Billed"
            }, update_modified=False)
            
            # Wenn bereits ausgeliefert (per_delivered=100), dann sollte Status "Completed" sein
            # Aktualisiere den Gesamtstatus
            so_doc.reload()
            so_doc.set_status(update=True)
            
            frappe.log_error(f"Sales Order {so.name}: per_billed=100, billing_status=Fully Billed, per_delivered={current_per_delivered}, Status={so_doc.status}", 
                           "SUCCESS: billing_status_updated")
        
        frappe.db.commit()
        
        # Nach dem Billing-Update: Prüfe auch ob bereits Delivery vorhanden ist
        # Falls ja, sollten alle Orders bereits "Completed" sein
        # (nur wenn noch nicht alle Orders per_delivered=100 haben)
        all_orders_check = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name", "per_delivered"]
        )
        if not all(flt(so.per_delivered) >= 100 for so in all_orders_check):
            update_party_delivery_status_if_exists(party_name)
        
        # Prüfen ob die Party abgeschlossen werden kann
        update_party_completion_status(party_name)
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Billing-Status: {str(e)}", 
                        "ERROR: update_billing_status")


def update_party_billing_status_if_exists(party_name):
    """
    Prüft ob bereits alle Rechnungen bezahlt sind
    und aktualisiert dann den Billing-Status für alle Orders
    Wird nach dem Delivery-Update aufgerufen, um sicherzustellen dass beide Status gesetzt sind
    """
    try:
        # Prüfe zuerst ob Billing-Status bereits gesetzt ist (verhindert Endlosschleife)
        all_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name", "per_billed"]
        )
        
        # Wenn bereits alle Orders per_billed=100 haben, nichts tun
        if all_orders and all(flt(so.per_billed) >= 100 for so in all_orders):
            frappe.log_error(f"Billing-Status bereits gesetzt für {party_name}", 
                           "DEBUG: billing_already_set")
            return
        
        # Finde alle GEBUCHTEN Sales Invoices der Party
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name", "outstanding_amount"]
        )
        
        if not invoices:
            return
        
        # Prüfe ob ALLE Rechnungen bezahlt sind
        all_paid = all(flt(inv.outstanding_amount) <= 0.01 for inv in invoices)
        
        if all_paid:
            # Alle Rechnungen bezahlt → setze Billing-Status direkt (ohne erneute Delivery-Prüfung)
            frappe.log_error(f"Alle Rechnungen bereits bezahlt für {party_name} - setze Billing-Status direkt", 
                           "DEBUG: billing_already_paid")
            
            # Finde ALLE Sales Orders der Party (inkl. Gruppenversand)
            all_orders = frappe.get_all(
                "Sales Order",
                filters={
                    "custom_party_reference": party_name,
                    "docstatus": 1
                },
                fields=["name"]
            )
            
            # Setze per_billed=100 für ALLE
            for so in all_orders:
                so_doc = frappe.get_doc("Sales Order", so.name)
                frappe.db.set_value("Sales Order", so.name, {
                    "per_billed": 100,
                    "billing_status": "Fully Billed"
                }, update_modified=False)
                so_doc.reload()
                so_doc.set_status(update=True)
            
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Prüfen des Billing-Status: {str(e)}", 
                        "ERROR: check_billing_status")


def update_party_delivery_status_if_exists(party_name):
    """
    Prüft ob bereits ein Lieferschein für den Gruppenversand existiert
    und aktualisiert dann den Delivery-Status für alle Orders
    Wird nach dem Billing-Update aufgerufen, um sicherzustellen dass beide Status gesetzt sind
    """
    try:
        # Prüfe zuerst ob Delivery-Status bereits gesetzt ist (verhindert Endlosschleife)
        all_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name", "per_delivered"]
        )
        
        # Wenn bereits alle Orders per_delivered=100 haben, nichts tun
        if all_orders and all(flt(so.per_delivered) >= 100 for so in all_orders):
            frappe.log_error(f"Delivery-Status bereits gesetzt für {party_name}", 
                           "DEBUG: delivery_already_set")
            return
        
        # Finde den Gruppenversand-Auftrag
        shipping_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "custom_shipping_order": 1,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        if not shipping_orders:
            return
        
        shipping_order_name = shipping_orders[0].name
        
        # Prüfe ob ein gebuchter Lieferschein existiert
        delivery_notes = frappe.get_all(
            "Delivery Note Item",
            filters={
                "against_sales_order": shipping_order_name,
                "docstatus": 1
            },
            fields=["parent"],
            distinct=True
        )
        
        if delivery_notes:
            # Lieferschein existiert bereits → setze Delivery-Status direkt (ohne erneute Billing-Prüfung)
            frappe.log_error(f"Lieferschein bereits vorhanden für {party_name} - setze Delivery-Status direkt", 
                           "DEBUG: delivery_already_exists")
            
            # Finde ALLE Sales Orders der Party
            all_orders = frappe.get_all(
                "Sales Order",
                filters={
                    "custom_party_reference": party_name,
                    "docstatus": 1
                },
                fields=["name"]
            )
            
            # Setze per_delivered=100 für ALLE
            for so in all_orders:
                so_doc = frappe.get_doc("Sales Order", so.name)
                frappe.db.set_value("Sales Order", so.name, {
                    "per_delivered": 100,
                    "delivery_status": "Fully Delivered"
                }, update_modified=False)
                so_doc.reload()
                so_doc.set_status(update=True)
            
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Prüfen des Delivery-Status: {str(e)}", 
                        "ERROR: check_delivery_status")


def update_party_delivery_status(party_name):
    """
    Prüft ob der Gruppenversand ausgeliefert wurde und setzt per_delivered=100 
    für ALLE Sales Orders der Party
    """
    try:
        # Finde den Gruppenversand-Auftrag
        shipping_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "custom_shipping_order": 1,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        if not shipping_orders:
            frappe.log_error(f"Kein Gruppenversand für {party_name} gefunden", 
                           "DEBUG: no_shipping_order")
            return
        
        shipping_order_name = shipping_orders[0].name
        
        # Prüfe ob ein gebuchter Lieferschein existiert
        delivery_notes = frappe.get_all(
            "Delivery Note Item",
            filters={
                "against_sales_order": shipping_order_name,
                "docstatus": 1
            },
            fields=["parent"],
            distinct=True
        )
        
        if not delivery_notes:
            frappe.log_error(f"Kein Lieferschein für Gruppenversand {shipping_order_name}", 
                           "DEBUG: no_delivery_note")
            return
        
        frappe.log_error(f"Gruppenversand {shipping_order_name} ausgeliefert - setze Status!", 
                        "INFO: shipping_delivered")
        
        # Finde ALLE Sales Orders der Party
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        # Setze per_delivered=100 und delivery_status="Fully Delivered" für ALLE (inkl. Kunden-Aufträge!)
        for so in sales_orders:
            # Lade das Dokument um den aktuellen per_billed Status zu prüfen
            so_doc = frappe.get_doc("Sales Order", so.name)
            current_per_billed = flt(so_doc.per_billed) or 0
            
            # Setze Delivery-Status
            frappe.db.set_value("Sales Order", so.name, {
                "per_delivered": 100,
                "delivery_status": "Fully Delivered"
            }, update_modified=False)
            
            # Wenn bereits bezahlt (per_billed=100), dann sollte Status "Completed" sein
            # Aktualisiere den Gesamtstatus
            so_doc.reload()
            so_doc.set_status(update=True)
            
            frappe.log_error(f"Sales Order {so.name}: per_delivered=100, delivery_status=Fully Delivered, per_billed={current_per_billed}, Status={so_doc.status}", 
                           "SUCCESS: delivery_status_updated")
        
        frappe.db.commit()
        
        # Nach dem Delivery-Update: Prüfe auch ob bereits Billing vorhanden ist
        # Falls ja, sollten alle Orders bereits "Completed" sein
        # (nur wenn noch nicht alle Orders per_billed=100 haben)
        all_orders_check = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name", "per_billed"]
        )
        if not all(flt(so.per_billed) >= 100 for so in all_orders_check):
            update_party_billing_status_if_exists(party_name)
        
        # Prüfen ob die Party abgeschlossen werden kann
        update_party_completion_status(party_name)
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Delivery-Status: {str(e)}", 
                        "ERROR: update_delivery_status")


def update_party_completion_status(party_name):
    """
    Prüft ob ALLE Sales Orders einer Party wirklich "Completed" sind
    (per_billed=100 UND per_delivered=100) und setzt dann den Status der 
    Party selbst auf "Abgeschlossen"
    
    WICHTIG: Setzt nur auf "Abgeschlossen", wenn wirklich beide Bedingungen erfüllt sind
    und der Status noch nicht "Abgeschlossen" ist (um alte Daten nicht zu überschreiben)
    """
    try:
        # Prüfe zuerst ob die Party überhaupt submitted ist
        party_docstatus = frappe.db.get_value("Party", party_name, "docstatus")
        if party_docstatus != 1:
            # Party ist nicht submitted - keine Status-Änderung
            frappe.log_error(f"Party {party_name} ist nicht submitted (docstatus={party_docstatus}) - überspringe", 
                           "DEBUG: party_not_submitted")
            return
        
        # Prüfe zuerst den aktuellen Status der Party
        current_status = frappe.db.get_value("Party", party_name, "status")
        
        # Wenn bereits "Abgeschlossen", nichts tun (verhindert Überschreibung alter Daten)
        if current_status == "Abgeschlossen":
            frappe.log_error(f"Party {party_name} bereits 'Abgeschlossen' - überspringe", 
                           "DEBUG: already_completed")
            return
        
        # WICHTIG: Nur prüfen wenn Party im Status "Geschenke" oder "Gebucht" ist
        # In früheren Status ("Gäste", "Produkte") sollten noch keine Orders existieren
        if current_status not in ["Geschenke", "Gebucht"]:
            frappe.log_error(f"Party {party_name} ist im Status '{current_status}' - noch keine Orders erwartet, überspringe", 
                           "DEBUG: party_not_ready")
            return
        
        # Finde alle Sales Orders der Party mit ihren Status-Werten
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": party_name,
                "docstatus": 1
            },
            fields=["name", "status", "per_billed", "per_delivered", "billing_status", "delivery_status"]
        )
        
        if not sales_orders:
            # Keine Orders gefunden - Party sollte nicht auf "Abgeschlossen" gesetzt werden
            frappe.log_error(f"Party {party_name}: Keine Sales Orders gefunden - überspringe", 
                           "DEBUG: no_orders")
            return
        
        # WICHTIG: Prüfe nicht nur den Status, sondern auch ob wirklich per_billed=100 UND per_delivered=100
        # Das verhindert, dass alte Orders die zufällig "Completed" sind, die Party auf "Abgeschlossen" setzen
        all_really_completed = True
        for so in sales_orders:
            per_billed = flt(so.per_billed) or 0
            per_delivered = flt(so.per_delivered) or 0
            
            # Nur wenn wirklich beide 100% sind UND Status "Completed", dann ist es wirklich abgeschlossen
            if not (per_billed >= 100 and per_delivered >= 100 and so.status == "Completed"):
                all_really_completed = False
                frappe.log_error(f"Sales Order {so.name}: per_billed={per_billed}, per_delivered={per_delivered}, status={so.status} - NICHT wirklich completed", 
                               "DEBUG: not_really_completed")
                break
        
        frappe.log_error(f"Party {party_name}: {len(sales_orders)} Orders, alle wirklich completed: {all_really_completed}", 
                        "DEBUG: completion_check")
        
        if all_really_completed:
            # Setze den Status der Party auf "Abgeschlossen"
            frappe.db.set_value("Party", party_name, "status", "Abgeschlossen", 
                               update_modified=False)
            frappe.db.commit()
            frappe.log_error(f"Party {party_name} auf 'Abgeschlossen' gesetzt!", 
                           "SUCCESS: party_completed")
            
            # Sende Realtime-Event um geöffnete Dokumente zu aktualisieren
            frappe.publish_realtime(
                "party_status_updated",
                {
                    "doctype": "Party",
                    "name": party_name,
                    "status": "Abgeschlossen"
                }
            )
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Party-Status: {str(e)}", 
                        "ERROR: completion_status")


@frappe.whitelist()
def recalculate_party_status(party_name):
    """
    Manuelles Neuberechnen des Status für eine Party
    """
    try:
        frappe.log_error(f"Manuelles Status-Update für {party_name}", 
                        "INFO: manual_update")
        
        update_party_billing_status(party_name)
        update_party_delivery_status(party_name)
        
        # Auch den Completion-Status prüfen
        update_party_completion_status(party_name)
        
        # Aktuellen Status holen
        current_status = frappe.db.get_value("Party", party_name, "status")
        
        return {
            "success": True,
            "message": f"Status wurde aktualisiert (Party: {current_status})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def recalculate_all_party_status():
    """
    Berechnet den Status für ALLE Parties neu
    """
    try:
        parties = frappe.get_all(
            "Party",
            filters={"docstatus": 1},
            fields=["name"]
        )
        
        updated = 0
        for party in parties:
            try:
                update_party_billing_status(party.name)
                update_party_delivery_status(party.name)
                updated += 1
            except Exception as e:
                frappe.log_error(f"Fehler bei {party.name}: {str(e)}", 
                               "ERROR: batch_update")
        
        return {
            "success": True,
            "message": f"{updated} Parties aktualisiert"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

