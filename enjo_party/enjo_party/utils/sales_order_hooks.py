import frappe
from frappe import _
import types
from frappe.utils import today

# === AUTO SALES INVOICE TEMPORÄR DEAKTIVIERT ===
# Schalter für automatische Rechnungserstellung über Hooks (True = aktiv, False = deaktiviert)
ENABLE_AUTO_SALES_INVOICE_HOOKS = True  # Wieder aktiviert!
# Schalter für automatische Erstellung
# Lieferschein (Delivery Note) separat aktivierbar
ENABLE_AUTO_DELIVERY_NOTE = True
# Packliste (Pick List) separat aktivierbar
ENABLE_AUTO_PICKLIST = True


def auto_create_and_submit_sales_invoice(doc, method):
    """
    Hook für Sales Order on_submit
    Erstellt automatisch eine Sales Invoice und reicht sie ein
    ABER: Nicht für Partner-Aufträge (die werden direkt in der Sammelbestellung erstellt)
    """
    frappe.log_error(f"🚀 HOOK AUFGERRUFEN: auto_create_and_submit_sales_invoice für {doc.name}", "INFO: hook_called")
    frappe.log_error(f"DEBUG: Sales Order Doc: {doc.name}, Customer: {doc.customer}, Party Reference: {getattr(doc, 'custom_party_reference', None)}", "DEBUG: hook_input")

    # TEMPORÄR DEAKTIVIERT: Automatische Rechnungserstellung über Hooks
    if not ENABLE_AUTO_SALES_INVOICE_HOOKS:
        frappe.log_error("AUTO SALES INVOICE HOOKS ist aktuell deaktiviert (ENABLE_AUTO_SALES_INVOICE_HOOKS = False)", "INFO: auto_invoice_hooks_deactivated")
        return

    # Prüfe ob es ein Partner-Auftrag ist (po_no enthält "-SHIP-")
    if doc.po_no and "-SHIP-" in doc.po_no:
        frappe.log_error(f"Partner-Auftrag {doc.name} - überspringe Ausgangsrechnung", "INFO: skip_partner_invoice")
        return

    try:
        frappe.log_error(f"Starting auto invoice creation for Sales Order: {doc.name}", "INFO: auto_invoice_start")
        
        # KORRIGIERT: Prüfe nur nach Sales Invoices die direkt zu diesem Sales Order gehören
        frappe.log_error(f"DEBUG: Prüfe existierende Invoices für {doc.name}", "DEBUG: check_existing_invoices")
        existing_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": ["!=", 2],
                "sales_order": doc.name  # Nur für diesen spezifischen Sales Order
            },
            fields=["name"],
            limit=1
        )

        if existing_invoices:
            frappe.log_error(f"Sales Invoice already exists for Sales Order {doc.name}: {existing_invoices[0]['name']}", "INFO: invoice_exists")
            frappe.log_error(f"DEBUG: Überspringe weitere Verarbeitung wegen existierender Invoice", "DEBUG: skip_processing")
            return
        
        frappe.log_error(f"No existing invoice found - creating new one for Sales Order {doc.name}", "INFO: creating_new")
        
        # Hole Standard-Einstellungen
        company = doc.company or frappe.defaults.get_user_default("Company")
        
        # Erstelle Sales Invoice basierend auf Sales Order
        # === NEU: Mapper-Funktion verwenden, damit Steuern & weitere Felder korrekt übernommen werden ===
        try:
            from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
        except Exception as e:
            frappe.log_error(f"Import make_sales_invoice fehlgeschlagen: {str(e)}", "ERROR: mapper_import_failed")
            raise

        invoice = make_sales_invoice(doc.name)  # noch nicht gespeichert

        # Zusätzliche/benutzerdefinierte Felder anpassen
        invoice.remarks = f"Automatisch erstellt aus Sales Order: {doc.name}"
        invoice.sales_order = doc.name  # Custom-Feld für Duplikat-Prüfung

        # Custom Party/Sammelbestellung Referenz übernehmen
        if hasattr(doc, "custom_party_reference") and doc.custom_party_reference:
            try:
                # Prüfe ob es eine Party oder Sammelbestellung ist
                if frappe.db.exists("Party", doc.custom_party_reference):
                    party_doc = frappe.get_doc("Party", doc.custom_party_reference)
                    if party_doc.docstatus != 2:
                        invoice.custom_party_reference = doc.custom_party_reference
                    else:
                        frappe.log_error(f"Party {doc.custom_party_reference} ist cancelled – Referenz ignoriert", "WARNING: cancelled_party")
                elif frappe.db.exists("Sammelbestellung", doc.custom_party_reference):
                    sammelbestellung_doc = frappe.get_doc("Sammelbestellung", doc.custom_party_reference)
                    if sammelbestellung_doc.docstatus != 2:
                        invoice.custom_party_reference = doc.custom_party_reference
                    else:
                        frappe.log_error(f"Sammelbestellung {doc.custom_party_reference} ist cancelled – Referenz ignoriert", "WARNING: cancelled_sammelbestellung")
                else:
                    frappe.log_error(f"Weder Party noch Sammelbestellung {doc.custom_party_reference} gefunden", "WARNING: reference_not_found")
            except Exception as e:
                frappe.log_error(f"Fehler beim Laden der Referenz {doc.custom_party_reference}: {str(e)}", "WARNING: reference_load_error")

        if hasattr(doc, "custom_calculated_shipping_cost") and doc.custom_calculated_shipping_cost:
            invoice.custom_calculated_shipping_cost = doc.custom_calculated_shipping_cost

        # Preise exakt wie im Sales Order setzen und Validierungen deaktivieren
        invoice.flags.ignore_validate_update_after_submit = True
        invoice.flags.ignore_validate = True  # Temporär für die Validierung
        invoice.flags.ignore_mandatory = True  # Temporär für die Validierung
        invoice.flags.ignore_pricing_rule = True
        invoice.flags.ignore_item_price = True
        invoice.flags.ignore_permissions = True  # Ignoriere Berechtigungen
        invoice.flags.ignore_address_validation = True  # Ignoriere Adress-Validierung
        invoice.flags.ignore_shipping_validation = True  # Ignoriere Versand-Validierung
        invoice.flags.ignore_billing_validation = True  # Ignoriere Rechnungs-Validierung
        
        # Verhindere die Adress-Validierung komplett
        if hasattr(invoice, '_validate_shipping_address'):
            delattr(invoice, '_validate_shipping_address')
        if hasattr(invoice, '_validate_billing_address'):
            delattr(invoice, '_validate_billing_address')
        
        # Setze Steuer-Template wenn nicht gesetzt
        if not invoice.taxes_and_charges:
            tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
                {"company": invoice.company, "is_default": 1}, "name")
            if tax_template:
                invoice.taxes_and_charges = tax_template
                invoice.taxes = []  # Leere bestehende Steuern
                invoice.run_method("set_taxes")  # Setze Steuern neu

        for i, invoice_item in enumerate(invoice.items):
            so_item = doc.items[i]
            invoice_item.rate = so_item.rate
            invoice_item.price_list_rate = so_item.rate
            invoice_item.base_rate = so_item.rate
            invoice_item.base_price_list_rate = so_item.rate
            invoice_item.amount = so_item.amount
            invoice_item.base_amount = so_item.amount
            invoice_item.flags.ignore_pricing_rule = True

        # Fehlende Felder füllen & Steuern/Totals neu berechnen
        invoice.run_method("set_missing_values")
        invoice.calculate_taxes_and_totals()

        # === ADRESS-VALIDIERUNG DEAKTIVIEREN FÜR PARTY/SAMMELBESTELLUNG-RECHNUNGEN ===
        # Prüfe, ob es sich um eine Party- oder Sammelbestellung-Rechnung handelt
        if hasattr(doc, "custom_party_reference") and doc.custom_party_reference:
            frappe.log_error(f"🎉 Party/Sammelbestellung-Invoice erkannt: {invoice.name if hasattr(invoice, 'name') else 'NEW'} - Validierung angepasst (DATEV-sicher)", "INFO: party_invoice_detected")
            
            # Überschreibe die Adress-Validierungsmethoden
            def safe_validate_party_address(self, party, party_type, billing_address, shipping_address=None):
                """Überspringe die Party-Adress-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_party_address für {party} (Type: {party_type}, Billing: {billing_address}, Shipping: {shipping_address})", "INFO: skip_party_address_validation")
                pass
            
            def safe_validate_party_address_and_contact(self):
                """Überspringe die komplette Party-Adress- und Kontakt-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_party_address_and_contact für {self.customer}", "INFO: skip_party_validation")
                pass
            
            def safe_validate_shipping_address(self):
                """Überspringe die Versandadress-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_shipping_address für {self.customer}", "INFO: skip_shipping_validation")
                pass
            
            def safe_validate_billing_address(self):
                """Überspringe die Rechnungsadress-Validierung"""
                frappe.log_error(f"✅ Überspringe validate_billing_address für {self.customer}", "INFO: skip_billing_validation")
                pass
            
            # Überschreibe nur die Adress-Validierungsmethoden (wie bei Party)
            invoice.validate_party_address = types.MethodType(safe_validate_party_address, invoice)
            invoice.validate_party_address_and_contact = types.MethodType(safe_validate_party_address_and_contact, invoice)
            invoice.validate_shipping_address = types.MethodType(safe_validate_shipping_address, invoice)
            invoice.validate_billing_address = types.MethodType(safe_validate_billing_address, invoice)
            
            frappe.log_error(f"✅ Adressvalidierung für automatische Invoice deaktiviert", "SUCCESS: auto_invoice_address_validation_bypassed")

        # Jetzt speichern (nicht submitten)
        invoice.insert()
        frappe.log_error(f"Sales Invoice created: {invoice.name}", "INFO: invoice_created")

        # === NEU: Lieferschein und/oder Packliste erzeugen ===
        frappe.log_error(f"🚀 ERREICHE NEUE LOGIK für {doc.name}", "INFO: new_logic_reached")

        # Prüfe ob es ein Party/Sammelbestellung-Auftrag ist
        is_party_order = hasattr(doc, "custom_party_reference") and doc.custom_party_reference
        create_shipping_docs = True  # Standardmäßig erstellen

        # Zusätzliche Aufträge für Partner als Versandziel
        partner_orders_to_create = []

        if is_party_order:
            # Bei Party/Sammelbestellung nur erstellen wenn Kunde Versandziel ist
            create_shipping_docs = False  # Standardmäßig nicht erstellen bei Party/Sammelbestellung
            try:
                frappe.log_error(f"DEBUG: Prüfe Versandziele für Kunde {doc.customer} in {doc.custom_party_reference}", "DEBUG: shipping_target_check")

                # Prüfe ob es eine Party oder Sammelbestellung ist
                if frappe.db.exists("Party", doc.custom_party_reference):
                    party_doc = frappe.get_doc("Party", doc.custom_party_reference)
                    frappe.log_error(f"DEBUG: Party-Dokument geladen, prüfe Gastgeberin: {party_doc.gastgeberin}", "DEBUG: party_check")

                    # Prüfe für Gastgeberin
                    if party_doc.gastgeberin == doc.customer:
                        frappe.log_error(f"DEBUG: Kunde ist Gastgeberin, prüfe Versandziel: {party_doc.versand_gastgeberin}", "DEBUG: hostess_check")
                        if party_doc.versand_gastgeberin == doc.customer:
                            create_shipping_docs = True
                            frappe.log_error(f"DEBUG: Gastgeberin ist ihr eigenes Versandziel", "DEBUG: hostess_own_target")
                        else:
                            # Partner als Versandziel - zusätzlichen leeren Auftrag erstellen
                            partner_orders_to_create.append(party_doc.versand_gastgeberin)
                            frappe.log_error(f"DEBUG: Partner als Versandziel für Gastgeberin: {party_doc.versand_gastgeberin}", "DEBUG: partner_for_hostess")

                    # Prüfe für Gäste
                    for idx, kunde_row in enumerate(party_doc.kunden or []):
                        if kunde_row.kunde == doc.customer:
                            versand_field = f"versand_gast_{idx+1}"
                            frappe.log_error(f"DEBUG: Prüfe Gast {idx+1}, Feld: {versand_field}", "DEBUG: guest_check")

                            if hasattr(party_doc, versand_field):
                                versand_ziel = getattr(party_doc, versand_field)
                                frappe.log_error(f"DEBUG: Versandziel für Gast {idx+1}: {versand_ziel}", "DEBUG: guest_shipping_target")

                                if versand_ziel == doc.customer:
                                    create_shipping_docs = True
                                    frappe.log_error(f"DEBUG: Gast ist sein eigenes Versandziel", "DEBUG: guest_own_target")
                                else:
                                    # Partner als Versandziel - zusätzlichen leeren Auftrag erstellen
                                    partner_orders_to_create.append(versand_ziel)
                                    frappe.log_error(f"DEBUG: Partner als Versandziel für Gast: {versand_ziel}", "DEBUG: partner_for_guest")
                            break

                elif frappe.db.exists("Sammelbestellung", doc.custom_party_reference):
                    sammelbestellung_doc = frappe.get_doc("Sammelbestellung", doc.custom_party_reference)
                    frappe.log_error(f"DEBUG: Sammelbestellung-Dokument geladen, prüfe Kunden", "DEBUG: sammelbestellung_check")

                    # Prüfe für Kunden
                    for idx, kunde_row in enumerate(sammelbestellung_doc.kunden or []):
                        if kunde_row.kunde == doc.customer:
                            versand_field = f"versand_kunde_{idx+1}"
                            frappe.log_error(f"DEBUG: Prüfe Kunde {idx+1}, Feld: {versand_field}", "DEBUG: customer_check")

                            if hasattr(sammelbestellung_doc, versand_field):
                                versand_ziel = getattr(sammelbestellung_doc, versand_field)
                                frappe.log_error(f"DEBUG: Versandziel für Kunde {idx+1}: {versand_ziel}", "DEBUG: customer_shipping_target")

                                if versand_ziel == doc.customer:
                                    create_shipping_docs = True
                                    frappe.log_error(f"DEBUG: Kunde ist sein eigenes Versandziel", "DEBUG: customer_own_target")
                                else:
                                    # Partner als Versandziel - zusätzlichen leeren Auftrag erstellen
                                    partner_orders_to_create.append(versand_ziel)
                                    frappe.log_error(f"DEBUG: Partner als Versandziel für Kunde: {versand_ziel}", "DEBUG: partner_for_customer")
                            break

                frappe.log_error(f"DEBUG: Partner-Aufträge zu erstellen: {partner_orders_to_create}", "DEBUG: partner_orders_summary")

            except Exception as e:
                frappe.log_error(f"Fehler beim Prüfen des Versandziels: {str(e)}", "ERROR: check_shipping_target")

        # 1) Lieferschein für aktuellen Auftrag
        if ENABLE_AUTO_DELIVERY_NOTE and create_shipping_docs:
            try:
                dn = create_delivery_note_for_sales_order(doc)
                if dn:
                    frappe.log_error(f"Delivery Note created: {dn.name}", "INFO: delivery_note_created")
            except Exception as e:
                frappe.log_error(f"Error creating Delivery Note for SO {doc.name}: {str(e)}", "ERROR: delivery_note_failed")

        # 2) Packliste für aktuellen Auftrag
        if ENABLE_AUTO_PICKLIST and create_shipping_docs:
            try:
                from enjo_party.enjo_party.utils.sales_invoice_hooks import auto_create_picklist_from_invoice
                auto_create_picklist_from_invoice(invoice, "auto")
            except Exception as e:
                frappe.log_error(f"Error creating Pick List for Invoice {invoice.name}: {str(e)}", "ERROR: picklist_create_failed")

        # 3) Zusätzliche leere Aufträge für Partner als Versandziel erstellen
        frappe.log_error(f"DEBUG: Erstelle Partner-Aufträge für: {partner_orders_to_create}", "DEBUG: partner_creation_start")
        for partner_name in partner_orders_to_create:
            try:
                if partner_name and partner_name != doc.customer:
                    frappe.log_error(f"DEBUG: Erstelle Partner-Auftrag für {partner_name}", "DEBUG: creating_partner_order")
                    result = create_partner_order(doc, partner_name)
                    frappe.log_error(f"DEBUG: Partner-Auftrag erstellt: {result}", "DEBUG: partner_order_result")
                else:
                    frappe.log_error(f"DEBUG: Überspringe Partner {partner_name} - ist leer oder gleicher Kunde", "DEBUG: skip_partner")
            except Exception as e:
                frappe.log_error(f"Error creating partner order for {partner_name}: {str(e)}", "ERROR: partner_order_failed")
        
        # Reiche die Sales Invoice ein
        # invoice.submit()  # <--- AUSKOMMENTIERT: Rechnung wird NICHT gebucht, nur erstellt
        # frappe.log_error(f"Sales Invoice submitted: {invoice.name}", "SUCCESS: invoice_submitted")
        
        frappe.log_error(f"✅ SUCCESS: Auto invoice complete for SO {doc.name} -> SI {invoice.name}", "SUCCESS: auto_invoice_complete")
        
    except Exception as e:
        frappe.log_error(f"Error in auto_create_and_submit_sales_invoice for {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: auto_invoice_failed")
        # Bei Fehlern nicht den gesamten Sales Order Submit blockieren
        frappe.msgprint(
            f"Sales Order wurde erstellt, aber die automatische Rechnungserstellung ist fehlgeschlagen: {str(e)}",
            title="Warnung",
            indicator="orange"
        ) 


@frappe.whitelist()
def create_partner_orders_for_existing_sales_orders(sales_order_names=None):
    """
    Erstellt Partner-Aufträge für bereits existierende Sales Orders.
    Kann einzeln oder für mehrere Sales Orders aufgerufen werden.

    Args:
        sales_order_names: Kommagetrennte Liste von Sales Order Namen oder einzelner Name
    """
    try:
        frappe.log_error(f"Erstelle Partner-Aufträge für existierende Sales Orders: {sales_order_names}", "INFO: create_partner_orders_start")

        if not sales_order_names:
            return {"success": False, "message": "Keine Sales Order Namen angegeben"}

        # Konvertiere zu Liste
        if isinstance(sales_order_names, str):
            order_names = [name.strip() for name in sales_order_names.split(",") if name.strip()]
        else:
            order_names = sales_order_names if isinstance(sales_order_names, list) else [sales_order_names]

        created_orders = []

        for so_name in order_names:
            try:
                frappe.log_error(f"Verarbeite Sales Order: {so_name}", "DEBUG: process_so")

                # Lade den Sales Order
                so_doc = frappe.get_doc("Sales Order", so_name)
                frappe.log_error(f"Sales Order geladen: {so_doc.name}, Customer: {so_doc.customer}", "DEBUG: so_loaded")

                # Prüfe ob es ein Party/Sammelbestellung-Auftrag ist
                if not (hasattr(so_doc, "custom_party_reference") and so_doc.custom_party_reference):
                    frappe.log_error(f"Sales Order {so_name} ist kein Party/Sammelbestellung-Auftrag", "DEBUG: not_party_order")
                    continue

                party_ref = so_doc.custom_party_reference
                frappe.log_error(f"Party/Sammelbestellung Referenz: {party_ref}", "DEBUG: party_ref")

                # Finde Partner als Versandziele
                partner_orders_to_create = []

                if frappe.db.exists("Party", party_ref):
                    party_doc = frappe.get_doc("Party", party_ref)
                    frappe.log_error(f"Party-Dokument geladen: {party_doc.name}", "DEBUG: party_doc_loaded")

                    # Prüfe Gastgeberin
                    if party_doc.gastgeberin == so_doc.customer:
                        if party_doc.versand_gastgeberin != so_doc.customer:
                            partner_orders_to_create.append(party_doc.versand_gastgeberin)
                            frappe.log_error(f"Partner für Gastgeberin: {party_doc.versand_gastgeberin}", "DEBUG: hostess_partner")

                    # Prüfe Gäste
                    for idx, kunde_row in enumerate(party_doc.kunden or []):
                        if kunde_row.kunde == so_doc.customer:
                            versand_field = f"versand_gast_{idx+1}"
                            if hasattr(party_doc, versand_field) and getattr(party_doc, versand_field) != so_doc.customer:
                                partner_orders_to_create.append(getattr(party_doc, versand_field))
                                frappe.log_error(f"Partner für Gast: {getattr(party_doc, versand_field)}", "DEBUG: guest_partner")
                            break

                elif frappe.db.exists("Sammelbestellung", party_ref):
                    sammelbestellung_doc = frappe.get_doc("Sammelbestellung", party_ref)
                    frappe.log_error(f"Sammelbestellung-Dokument geladen: {sammelbestellung_doc.name}", "DEBUG: sammelbestellung_doc_loaded")

                    # Prüfe Kunden
                    for idx, kunde_row in enumerate(sammelbestellung_doc.kunden or []):
                        if kunde_row.kunde == so_doc.customer:
                            versand_field = f"versand_kunde_{idx+1}"
                            if hasattr(sammelbestellung_doc, versand_field) and getattr(sammelbestellung_doc, versand_field) != so_doc.customer:
                                partner_orders_to_create.append(getattr(sammelbestellung_doc, versand_field))
                                frappe.log_error(f"Partner für Kunde: {getattr(sammelbestellung_doc, versand_field)}", "DEBUG: customer_partner")
                            break

                frappe.log_error(f"Partner-Aufträge zu erstellen für {so_name}: {partner_orders_to_create}", "DEBUG: partners_to_create")

                # Erstelle Partner-Aufträge
                for partner_name in partner_orders_to_create:
                    if partner_name and partner_name != so_doc.customer:
                        frappe.log_error(f"Erstelle Partner-Auftrag für {partner_name}", "DEBUG: create_partner")
                        result = create_partner_order(so_doc, partner_name)
                        if result:
                            created_orders.append(result)
                            frappe.log_error(f"Partner-Auftrag erstellt: {result}", "SUCCESS: partner_created")

            except Exception as e:
                frappe.log_error(f"Fehler bei Sales Order {so_name}: {str(e)}", "ERROR: so_processing_error")
                continue

        return {
            "success": True,
            "message": f"{len(created_orders)} Partner-Aufträge erstellt",
            "created_orders": created_orders
        }

    except Exception as e:
        frappe.log_error(f"Allgemeiner Fehler: {str(e)}", "ERROR: create_partner_orders_failed")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_partner_orders_for_current_orders():
    """
    Client-Script-Funktion: Erstellt Partner-Aufträge für alle aktuellen Sales Orders
    einer Party/Sammelbestellung
    """
    try:
        # Hole alle aktuellen Sales Orders mit Party/Sammelbestellung-Referenz
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "docstatus": 1,  # Nur gebuchte Aufträge
                "custom_party_reference": ["!=", ""]
            },
            fields=["name", "customer", "custom_party_reference"],
            limit=50  # Begrenzung für Performance
        )

        if not sales_orders:
            return {"success": False, "message": "Keine Sales Orders mit Party/Sammelbestellung-Referenz gefunden"}

        frappe.log_error(f"Gefundene Sales Orders: {len(sales_orders)}", "DEBUG: found_orders")

        # Gruppiere nach Party/Sammelbestellung
        order_groups = {}
        for so in sales_orders:
            party_ref = so.custom_party_reference
            if party_ref not in order_groups:
                order_groups[party_ref] = []
            order_groups[party_ref].append(so.name)

        frappe.log_error(f"Order Groups: {list(order_groups.keys())}", "DEBUG: order_groups")

        total_created = 0

        # Verarbeite jede Gruppe
        for party_ref, order_names in order_groups.items():
            frappe.log_error(f"Verarbeite Gruppe {party_ref} mit {len(order_names)} Orders", "DEBUG: process_group")

            result = create_partner_orders_for_existing_sales_orders(order_names)

            if result.get("success"):
                created_count = len(result.get("created_orders", []))
                total_created += created_count
                frappe.log_error(f"Gruppe {party_ref}: {created_count} Partner-Aufträge erstellt", "SUCCESS: group_processed")
            else:
                frappe.log_error(f"Fehler bei Gruppe {party_ref}: {result.get('message')}", "ERROR: group_error")

        return {
            "success": True,
            "message": f"Insgesamt {total_created} Partner-Aufträge erstellt",
            "total_created": total_created
        }

    except Exception as e:
        frappe.log_error(f"Fehler in create_partner_orders_for_current_orders: {str(e)}", "ERROR: client_function_error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_invoice_from_sales_order(sales_order_name):
    """
    Erstellt eine Sales Invoice für einen Sales Order (für Client Scripts)
    """
    # TEMPORÄR DEAKTIVIERT: Auch die manuelle Client-Script Funktion deaktivieren
    if not ENABLE_AUTO_SALES_INVOICE_HOOKS:
        return {
            "success": False,
            "message": "Automatische Rechnungserstellung ist derzeit deaktiviert (ENABLE_AUTO_SALES_INVOICE_HOOKS = False)",
            "invoice_name": None
        }

    try:
        # Lade den Sales Order
        doc = frappe.get_doc("Sales Order", sales_order_name)

        frappe.log_error(f"Client Script: Starting invoice creation for Sales Order: {sales_order_name}", "INFO: client_auto_invoice_start")
        
        # Prüfe ob bereits eine Sales Invoice für diesen Sales Order existiert
        existing_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": ["!=", 2],
                "sales_order": doc.name
            },
            fields=["name"],
            limit=1
        )
        
        if existing_invoices:
            return {
                "success": False,
                "message": f"Sales Invoice existiert bereits: {existing_invoices[0]['name']}",
                "invoice_name": existing_invoices[0]['name']
            }
        
        # Erstelle Sales Invoice (verwende die gleiche Logik wie der Hook)
        auto_create_and_submit_sales_invoice(doc, "manual")
        
        # Finde die erstellte Sales Invoice
        created_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": ["!=", 2],
                "sales_order": doc.name
            },
            fields=["name"],
            limit=1
        )
        
        if created_invoices:
            return {
                "success": True,
                "message": f"Sales Invoice {created_invoices[0]['name']} wurde automatisch erstellt",
                "invoice_name": created_invoices[0]['name']
            }
        else:
            return {
                "success": False,
                "message": "Sales Invoice konnte nicht erstellt werden",
                "invoice_name": None
            }
        
    except Exception as e:
        frappe.log_error(f"Client Script Error for {sales_order_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: client_auto_invoice_failed")
        return {
            "success": False,
            "message": f"Fehler: {str(e)}",
            "invoice_name": None
        } 


# =====================
# HILFSFUNKTIONEN
# =====================

def create_delivery_note_for_sales_order(sales_order_doc):
    """Erstellt einen Lieferschein (Delivery Note) für den gegebenen Sales Order und gibt das DN-Dokument zurück.
    Nutzt die Standard-Mapper-Funktion von ERPNext. Bei Fehlern wird None zurückgegeben."""

    try:
        # Import erst hier, um Abhängigkeiten nur bei Bedarf zu laden
        from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
    except Exception as e:
        frappe.log_error(f"Import make_delivery_note fehlgeschlagen: {str(e)}", "ERROR: dn_import_failed")
        return None

    try:
        dn = make_delivery_note(sales_order_doc.name)
        dn.insert()
        return dn
    except Exception as e:
        frappe.log_error(f"Delivery Note konnte nicht erstellt werden: {str(e)}", "ERROR: dn_creation_failed")
        return None


def create_partner_order(original_order_doc, partner_name):
    """
    Erstellt einen Sales Order für einen Partner als Versandziel mit einem Dummy-Artikel.
    Der Auftrag wird gebucht und bekommt eine Packliste und einen Lieferschein als Entwurf.
    """
    try:
        frappe.log_error(f"Erstelle Partner-Auftrag für {partner_name}", "INFO: create_partner_order")
        frappe.log_error(f"DEBUG: Original Order: {original_order_doc.name}, Customer: {original_order_doc.customer}", "DEBUG: partner_order_input")

        # Hole Standard-Einstellungen
        company = original_order_doc.company or frappe.defaults.get_user_default("Company")
        currency = original_order_doc.currency or frappe.defaults.get_user_default("Currency")
        frappe.log_error(f"DEBUG: Company: {company}, Currency: {currency}", "DEBUG: partner_order_settings")

        # Finde die Adresse des Partners
        partner_address = None
        try:
            frappe.log_error(f"DEBUG: Suche Adresse für Partner {partner_name}", "DEBUG: partner_address_search")
            partner_address = find_existing_address(partner_name, "Billing")
            if not partner_address:
                partner_address = find_existing_address(partner_name, "Shipping")
            frappe.log_error(f"DEBUG: Partner-Adresse gefunden: {partner_address}", "DEBUG: partner_address_result")
        except Exception as e:
            frappe.log_error(f"Keine Adresse für Partner {partner_name} gefunden: {str(e)}", "WARNING: partner_address_not_found")

        # Hole den Dummy-Artikel "Partnerversand"
        dummy_item_code = "Partnerversand"
        try:
            frappe.log_error(f"DEBUG: Suche Dummy-Artikel {dummy_item_code}", "DEBUG: find_dummy_item")
            dummy_item = frappe.get_doc("Item", dummy_item_code)
            frappe.log_error(f"DEBUG: Dummy-Artikel gefunden: {dummy_item.item_name}", "DEBUG: dummy_item_found")
        except Exception as e:
            frappe.log_error(f"Dummy-Artikel {dummy_item_code} nicht gefunden: {str(e)}", "ERROR: dummy_item_not_found")
            return None

        # Erstelle Sales Order für den Partner mit Dummy-Artikel
        frappe.log_error(f"DEBUG: Erstelle Sales Order für Partner {partner_name} mit Dummy-Artikel", "DEBUG: create_partner_order")
        partner_order_data = {
            "doctype": "Sales Order",
            "customer": partner_name,
            "transaction_date": today(),
            "delivery_date": today(),
            "items": [
                {
                    "doctype": "Sales Order Item",
                    "item_code": dummy_item_code,
                    "item_name": dummy_item.item_name,
                    "qty": 1,
                    "rate": 0,  # Kostenloser Dummy-Artikel
                    "amount": 0,
                    "uom": dummy_item.stock_uom or "Stk",
                    "stock_uom": dummy_item.stock_uom or "Stk",
                    "conversion_factor": 1.0,
                    "stock_qty": 1.0,
                    "base_amount": 0,
                    "base_rate": 0,
                    "warehouse": get_default_warehouse(),
                    "delivery_date": today(),
                }
            ],
            "customer_address": partner_address,
            "shipping_address_name": partner_address,
            "remarks": f"Versandauftrag erstellt aus Party/Sammelbestellung | Partner: {partner_name}",
            "po_no": original_order_doc.custom_party_reference,
            "company": company,
            "currency": currency,
            "status": "Draft",
            "order_type": "Sales",
            "custom_party_reference": original_order_doc.custom_party_reference,
            "custom_calculated_shipping_cost": 0,
        }

        # Erstelle den Auftrag
        frappe.log_error(f"DEBUG: Erstelle Sales Order Dokument", "DEBUG: create_order_doc")
        partner_order = frappe.get_doc(partner_order_data)

        # Setze Adress-Validierung außer Kraft (wie bei anderen Aufträgen)
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

        partner_order.validate_party_address = types.MethodType(safe_validate_party_address, partner_order)
        partner_order.validate_shipping_address = types.MethodType(safe_validate_shipping_address, partner_order)
        partner_order.validate_billing_address = types.MethodType(safe_validate_billing_address, partner_order)

        # Speichere und reiche den Auftrag ein
        frappe.log_error(f"DEBUG: Speichere Partner-Auftrag", "DEBUG: insert_partner_order")
        partner_order.insert()
        frappe.log_error(f"DEBUG: Reiche Partner-Auftrag ein", "DEBUG: submit_partner_order")
        partner_order.submit()

        frappe.log_error(f"Partner-Auftrag erstellt und gebucht: {partner_order.name}", "SUCCESS: partner_order_created")

        # Erstelle und BUCHE die Ausgangsrechnung direkt
        try:
            frappe.log_error(f"DEBUG: Erstelle UND BUCHE Ausgangsrechnung für Partner {partner_name}", "DEBUG: create_and_submit_partner_invoice")
            from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

            invoice = make_sales_invoice(partner_order.name)

            # Setze ALLE Flags um Validierungen komplett zu umgehen
            invoice.flags.ignore_permissions = True
            invoice.flags.ignore_validate = True
            invoice.flags.ignore_mandatory = True
            invoice.flags.ignore_pricing_rule = True
            invoice.flags.ignore_item_price = True
            invoice.flags.ignore_address_validation = True
            invoice.flags.ignore_shipping_validation = True
            invoice.flags.ignore_billing_validation = True
            invoice.flags.ignore_validate_update_after_submit = True
            invoice.flags.ignore_links = True
            invoice.update_stock = 0  # Kein Lagerbestand aktualisieren

            # Überschreibe ALLE Validierungsmethoden
            import types

            def skip_all_validation(self, *args, **kwargs):
                frappe.log_error(f"✅ Überspringe Validierung für Partner-Invoice {self.customer}", "INFO: skip_all_validation")
                pass

            # Überschreibe alle Validierungsmethoden
            validation_methods = [
                'validate_party_address', 'validate_party_address_and_contact',
                'validate_shipping_address', 'validate_billing_address',
                'validate_address', 'validate_customer', 'validate_items',
                'validate_taxes', 'validate_payment_terms', 'validate_due_date'
            ]

            for method_name in validation_methods:
                if hasattr(invoice, method_name):
                    setattr(invoice, method_name, types.MethodType(skip_all_validation, invoice))

            # Setze Steuer-Template wenn nicht gesetzt
            if not invoice.taxes_and_charges:
                tax_template = frappe.db.get_value("Sales Taxes and Charges Template",
                    {"company": invoice.company, "is_default": 1}, "name")
                if tax_template:
                    invoice.taxes_and_charges = tax_template
                    invoice.taxes = []  # Leere bestehende Steuern
                    invoice.run_method("set_taxes")  # Setze Steuern neu

            # Setze Preise exakt wie im Sales Order
            for i, invoice_item in enumerate(invoice.items):
                so_item = partner_order.items[i]
                invoice_item.rate = so_item.rate
                invoice_item.price_list_rate = so_item.rate
                invoice_item.base_rate = so_item.rate
                invoice_item.base_price_list_rate = so_item.rate
                invoice_item.amount = so_item.amount
                invoice_item.base_amount = so_item.amount
                invoice_item.flags.ignore_pricing_rule = True

            # Fehlende Felder füllen & Steuern/Totals neu berechnen
            invoice.run_method("set_missing_values")
            invoice.calculate_taxes_and_totals()

            # Speichere UND BUCHE die Ausgangsrechnung direkt
            invoice.insert()
            invoice.submit()  # DIREKT BUCHEN
            frappe.log_error(f"✅ Partner-Ausgangsrechnung direkt erstellt und gebucht: {invoice.name}", "SUCCESS: partner_invoice_directly_submitted")

        except Exception as e:
            frappe.log_error(f"❌ Fehler beim Erstellen/Buchen der Ausgangsrechnung für {partner_name}: {str(e)}", "ERROR: partner_invoice_failed")
            # Bei Fehlern trotzdem fortfahren - ist nicht kritisch

        return partner_order.name

    except Exception as e:
        frappe.log_error(f"Allgemeiner Fehler beim Erstellen des Partner-Auftrags für {partner_name}: {str(e)}", "ERROR: create_partner_order_failed")
        return None 