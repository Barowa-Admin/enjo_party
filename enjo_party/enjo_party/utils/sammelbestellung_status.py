# Copyright (c) 2025, Elia and contributors
# For license information, please see license.txt

"""
Sammelbestellungs-Status-Berechnung

Dieses Modul berechnet den korrekten Status für Sammelbestellungen basierend auf:
- Zahlungsstatus der Rechnungen (outstanding_amount)
- Lieferstatus (Delivery Note)
- Stornierte Rechnungen (Retourniert)
- Überfälligkeit (due_date + 5 Tage)

Status-Hierarchie:
1. Retourniert - Mind. 1 stornierte Rechnung (docstatus=2)
2. Überfällig - Mind. 1 Rechnung mit outstanding_amount>0 UND due_date + 5 Tage < heute
3. Ausgeliefert - Alle Rechnungen bezahlt UND Lieferschein gebucht
4. Gebucht - docstatus=1, aber noch nicht ausgeliefert oder offene Rechnungen
"""

import frappe
from frappe.utils import flt, add_days, getdate, today


# Anzahl Tage nach Fälligkeit bis "Überfällig"
OVERDUE_DAYS = 5


def calculate_sammelbestellung_status(sammelbestellung_name):
    """
    Berechnet den korrekten Status für eine Sammelbestellung.
    
    Rückgabe: Der berechnete Status-String
    
    Status-Priorität (von höchster zu niedrigster):
    1. Retourniert - Mind. 1 stornierte Rechnung vorhanden
    2. Überfällig - Mind. 1 Rechnung überfällig (due_date + 5 Tage < heute)
    3. Ausgeliefert - Alle Rechnungen bezahlt UND Lieferschein gebucht
    4. Gebucht - Default für gebuchte Sammelbestellungen
    """
    try:
        # Prüfe ob die Sammelbestellung existiert und gebucht ist
        sb_data = frappe.db.get_value("Sammelbestellung", sammelbestellung_name, 
                                       ["docstatus", "status"], as_dict=True)
        
        if not sb_data or sb_data.docstatus != 1:
            # Nicht gebucht - behalte aktuellen Status (Kunden, Produkte)
            return sb_data.status if sb_data else "Kunden"
        
        # Hole alle Rechnungen dieser Sammelbestellung
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_party_reference": sammelbestellung_name
            },
            fields=["name", "docstatus", "outstanding_amount", "due_date", "grand_total"]
        )
        
        # 1. Prüfe auf stornierte Rechnungen (Retourniert)
        cancelled_invoices = [inv for inv in invoices if inv.docstatus == 2]
        if cancelled_invoices:
            return "Retourniert"
        
        # Filtere nur gebuchte Rechnungen für weitere Prüfungen
        submitted_invoices = [inv for inv in invoices if inv.docstatus == 1]
        
        # 2. Prüfe auf überfällige Rechnungen (nur wenn Rechnungen vorhanden)
        if submitted_invoices:
            today_date = getdate(today())
            for inv in submitted_invoices:
                if flt(inv.outstanding_amount) > 0.01:
                    # Rechnung ist noch offen - prüfe Fälligkeit
                    if inv.due_date:
                        overdue_date = add_days(inv.due_date, OVERDUE_DAYS)
                        if getdate(overdue_date) < today_date:
                            return "Überfällig"
        
        # 3. HAUPTKRITERIUM: Prüfe ob alle Sales Orders ausgeliefert wurden
        # Das ist das wichtigste Kriterium, Rechnungen sind sekundär
        has_delivery = check_sammelbestellung_delivery(sammelbestellung_name)
        
        # Wenn vollständig ausgeliefert → Ausgeliefert (unabhängig von Rechnungen)
        if has_delivery:
            return "Ausgeliefert"
        
        # Sonst: Gebucht
        return "Gebucht"
        
    except Exception as e:
        frappe.log_error(f"Fehler bei Status-Berechnung für {sammelbestellung_name}: {str(e)}", 
                        "ERROR: calculate_sammelbestellung_status")
        return "Gebucht"


def check_sammelbestellung_delivery(sammelbestellung_name):
    """
    Prüft ob alle Sales Orders der Sammelbestellung ausgeliefert wurden.
    
    Rückgabe: True wenn alle Orders per_delivered=100 haben, sonst False
    """
    try:
        # Finde ALLE Sales Orders der Sammelbestellung
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": sammelbestellung_name,
                "docstatus": 1
            },
            fields=["name", "per_delivered", "delivery_status"]
        )
        
        if not sales_orders:
            # Keine Sales Orders gefunden - nicht ausgeliefert
            return False
        
        # Prüfe ob ALLE Orders vollständig ausgeliefert sind (per_delivered=100)
        all_delivered = all(flt(so.per_delivered) >= 100 for so in sales_orders)
        
        return all_delivered
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Prüfen des Lieferstatus: {str(e)}", 
                        "ERROR: check_sammelbestellung_delivery")
        return False


def update_sammelbestellung_status(sammelbestellung_name):
    """
    Berechnet und aktualisiert den Status einer Sammelbestellung.
    """
    try:
        new_status = calculate_sammelbestellung_status(sammelbestellung_name)
        current_status = frappe.db.get_value("Sammelbestellung", sammelbestellung_name, "status")
        
        # Nur "Kunden" Status nicht überschreiben (initiale Erstellung)
        # Alle anderen Status (Produkte, Gebucht) können überschrieben werden
        if current_status == "Kunden":
            # Kunden-Status nicht automatisch überschreiben
            return current_status
        
        if new_status != current_status:
            frappe.db.set_value("Sammelbestellung", sammelbestellung_name, "status", new_status, 
                               update_modified=False)
            frappe.db.commit()
            
            frappe.log_error(f"Sammelbestellung {sammelbestellung_name}: Status geändert von '{current_status}' auf '{new_status}'", 
                           "INFO: status_updated")
            
            # Sende Realtime-Event
            frappe.publish_realtime(
                "party_status_updated",
                {
                    "doctype": "Sammelbestellung",
                    "name": sammelbestellung_name,
                    "status": new_status
                }
            )
        
        return new_status
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Status-Update: {str(e)}", 
                        "ERROR: update_sammelbestellung_status")
        return None


def update_sammelbestellung_status_on_payment(doc, method):
    """
    Hook für Payment Entry on_submit
    Prüft ob alle Rechnungen einer Sammelbestellung ODER Party bezahlt sind
    """
    try:
        # Importiere Party-Status-Funktionen
        from enjo_party.enjo_party.utils.party_status import update_party_status
        
        # Finde alle Sales Invoices die durch diesen Payment Entry bezahlt wurden
        for ref in doc.references:
            if ref.reference_doctype == "Sales Invoice":
                invoice = frappe.get_doc("Sales Invoice", ref.reference_name)
                
                # Prüfe ob die Invoice zu einer Sammelbestellung gehört
                party_reference = getattr(invoice, "custom_party_reference", None)
                if party_reference:
                    if frappe.db.exists("Sammelbestellung", party_reference):
                        frappe.log_error(f"Payment für Sammelbestellung {party_reference} erkannt", 
                                        "INFO: sammelbestellung_payment")
                        update_sammelbestellung_status(party_reference)
                    elif frappe.db.exists("Party", party_reference):
                        frappe.log_error(f"Payment für Party {party_reference} erkannt", 
                                        "INFO: party_payment")
                        update_party_status(party_reference)
                    
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Billing-Status nach Zahlung: {str(e)}", 
                        "ERROR: sammelbestellung_status_payment")


def update_sammelbestellung_status_on_invoice_payment(doc, method):
    """
    Hook für Sales Invoice on_update_after_submit
    Wird aufgerufen wenn der outstanding_amount sich ändert
    Prüft sowohl Sammelbestellung als auch Party
    """
    try:
        # Importiere Party-Status-Funktionen
        from enjo_party.enjo_party.utils.party_status import update_party_status
        
        party_reference = getattr(doc, "custom_party_reference", None)
        if party_reference:
            if frappe.db.exists("Sammelbestellung", party_reference):
                frappe.log_error(f"Invoice-Update für Sammelbestellung {party_reference}", 
                                "INFO: invoice_update")
                update_sammelbestellung_status(party_reference)
            elif frappe.db.exists("Party", party_reference):
                frappe.log_error(f"Invoice-Update für Party {party_reference}", 
                                "INFO: invoice_update")
                update_party_status(party_reference)
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Update nach Invoice-Update: {str(e)}", 
                        "ERROR: sammelbestellung_status_invoice")


def update_sammelbestellung_status_on_delivery(doc, method):
    """
    Hook für Delivery Note on_submit
    Prüft ob es sich um einen Gruppenversand-Lieferschein handelt
    Prüft sowohl Sammelbestellung als auch Party
    """
    try:
        # Importiere Party-Status-Funktionen
        from enjo_party.enjo_party.utils.party_status import update_party_status
        
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
        
        # Hole die Referenz (Sammelbestellung oder Party)
        party_reference = getattr(sales_order, "custom_party_reference", None)
        if party_reference:
            if frappe.db.exists("Sammelbestellung", party_reference):
                frappe.log_error(f"Gruppenversand-Lieferschein für Sammelbestellung {party_reference}", 
                               "INFO: shipping_delivery")
                update_sammelbestellung_status(party_reference)
            elif frappe.db.exists("Party", party_reference):
                frappe.log_error(f"Gruppenversand-Lieferschein für Party {party_reference}", 
                               "INFO: shipping_delivery")
                update_party_status(party_reference)
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Update nach Lieferschein: {str(e)}", 
                        "ERROR: sammelbestellung_status_delivery")


def update_sammelbestellung_billing_status(sammelbestellung_name):
    """
    Prüft ob alle Rechnungen bezahlt sind und setzt per_billed=100 
    für ALLE Sales Orders der Sammelbestellung
    
    WICHTIG: Prüft nur ob alle existierenden Rechnungen bezahlt sind.
    Orders die keine Rechnungen bekommen (z.B. Vertriebspartner-Orders, Gruppenversand) 
    werden nicht als fehlend betrachtet.
    """
    try:
        # Finde alle GEBUCHTEN Sales Invoices der Sammelbestellung
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_party_reference": sammelbestellung_name,
                "docstatus": 1
            },
            fields=["name", "outstanding_amount", "grand_total"]
        )
        
        if not invoices:
            frappe.log_error(f"Keine gebuchten Rechnungen für {sammelbestellung_name} gefunden", 
                           "DEBUG: no_invoices")
            return
        
        frappe.log_error(f"Gefunden: {len(invoices)} gebuchte Rechnungen für Sammelbestellung {sammelbestellung_name}", 
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
            frappe.log_error(f"Nicht alle Rechnungen bezahlt für {sammelbestellung_name}", 
                           "DEBUG: not_all_paid")
            return
        
        frappe.log_error(f"ALLE {len(invoices)} Rechnungen bezahlt für {sammelbestellung_name} - setze Status!", 
                        "INFO: all_paid")
        
        # Finde ALLE Sales Orders der Sammelbestellung
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": sammelbestellung_name,
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
                "custom_party_reference": sammelbestellung_name,
                "docstatus": 1
            },
            fields=["name", "per_delivered"]
        )
        if not all(flt(so.per_delivered) >= 100 for so in all_orders_check):
            update_sammelbestellung_delivery_status_if_exists(sammelbestellung_name)
        
        # Prüfen ob die Sammelbestellung abgeschlossen werden kann
        update_sammelbestellung_completion_status(sammelbestellung_name)
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Billing-Status: {str(e)}", 
                        "ERROR: update_billing_status")


def update_sammelbestellung_billing_status_if_exists(sammelbestellung_name):
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
                "custom_party_reference": sammelbestellung_name,
                "docstatus": 1
            },
            fields=["name", "per_billed"]
        )
        
        # Wenn bereits alle Orders per_billed=100 haben, nichts tun
        if all_orders and all(flt(so.per_billed) >= 100 for so in all_orders):
            frappe.log_error(f"Billing-Status bereits gesetzt für {sammelbestellung_name}", 
                           "DEBUG: billing_already_set")
            return
        
        # Finde alle GEBUCHTEN Sales Invoices der Sammelbestellung
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_party_reference": sammelbestellung_name,
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
            frappe.log_error(f"Alle Rechnungen bereits bezahlt für {sammelbestellung_name} - setze Billing-Status direkt", 
                           "DEBUG: billing_already_paid")
            
            # Finde ALLE Sales Orders der Sammelbestellung (inkl. Gruppenversand)
            all_orders = frappe.get_all(
                "Sales Order",
                filters={
                    "custom_party_reference": sammelbestellung_name,
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


def update_sammelbestellung_delivery_status_if_exists(sammelbestellung_name):
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
                "custom_party_reference": sammelbestellung_name,
                "docstatus": 1
            },
            fields=["name", "per_delivered"]
        )
        
        # Wenn bereits alle Orders per_delivered=100 haben, nichts tun
        if all_orders and all(flt(so.per_delivered) >= 100 for so in all_orders):
            frappe.log_error(f"Delivery-Status bereits gesetzt für {sammelbestellung_name}", 
                           "DEBUG: delivery_already_set")
            return
        
        # Finde den Gruppenversand-Auftrag
        shipping_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": sammelbestellung_name,
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
            frappe.log_error(f"Lieferschein bereits vorhanden für {sammelbestellung_name} - setze Delivery-Status direkt", 
                           "DEBUG: delivery_already_exists")
            
            # Finde ALLE Sales Orders der Sammelbestellung
            all_orders = frappe.get_all(
                "Sales Order",
                filters={
                    "custom_party_reference": sammelbestellung_name,
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


def update_sammelbestellung_delivery_status(sammelbestellung_name):
    """
    Prüft ob der Gruppenversand ausgeliefert wurde und setzt per_delivered=100 
    für ALLE Sales Orders der Sammelbestellung
    """
    try:
        # Finde den Gruppenversand-Auftrag
        shipping_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": sammelbestellung_name,
                "custom_shipping_order": 1,
                "docstatus": 1
            },
            fields=["name"]
        )
        
        if not shipping_orders:
            frappe.log_error(f"Kein Gruppenversand für {sammelbestellung_name} gefunden", 
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
        
        # Finde ALLE Sales Orders der Sammelbestellung
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "custom_party_reference": sammelbestellung_name,
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
                "custom_party_reference": sammelbestellung_name,
                "docstatus": 1
            },
            fields=["name", "per_billed"]
        )
        if not all(flt(so.per_billed) >= 100 for so in all_orders_check):
            update_sammelbestellung_billing_status_if_exists(sammelbestellung_name)
        
        # Prüfen ob die Sammelbestellung abgeschlossen werden kann
        update_sammelbestellung_completion_status(sammelbestellung_name)
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Update des Delivery-Status: {str(e)}", 
                        "ERROR: update_delivery_status")


def update_sammelbestellung_completion_status(sammelbestellung_name):
    """
    DEPRECATED: Wird durch update_sammelbestellung_status ersetzt.
    Behalten für Abwärtskompatibilität.
    """
    update_sammelbestellung_status(sammelbestellung_name)


@frappe.whitelist()
def recalculate_sammelbestellung_status(sammelbestellung_name):
    """
    Manuelles Neuberechnen des Status für eine Sammelbestellung
    """
    try:
        frappe.log_error(f"Manuelles Status-Update für {sammelbestellung_name}", 
                        "INFO: manual_update")
        
        # Aktualisiere auch die Sales Order Status-Felder (für ERPNext-Kompatibilität)
        update_sammelbestellung_billing_status(sammelbestellung_name)
        update_sammelbestellung_delivery_status(sammelbestellung_name)
        
        # Berechne und setze den neuen Sammelbestellung-Status
        new_status = update_sammelbestellung_status(sammelbestellung_name)
        
        return {
            "success": True,
            "message": f"Status wurde aktualisiert (Sammelbestellung: {new_status})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def recalculate_all_sammelbestellung_status():
    """
    Berechnet den Status für ALLE Sammelbestellungen neu
    """
    try:
        sammelbestellungen = frappe.get_all(
            "Sammelbestellung",
            filters={"docstatus": 1},
            fields=["name"]
        )
        
        updated = 0
        for sb in sammelbestellungen:
            try:
                # Aktualisiere Sales Order Status-Felder
                update_sammelbestellung_billing_status(sb.name)
                update_sammelbestellung_delivery_status(sb.name)
                # Berechne und setze den Sammelbestellung-Status
                update_sammelbestellung_status(sb.name)
                updated += 1
            except Exception as e:
                frappe.log_error(f"Fehler bei {sb.name}: {str(e)}", 
                               "ERROR: batch_update")
        
        return {
            "success": True,
            "message": f"{updated} Sammelbestellungen aktualisiert"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

