import frappe

def copy_email_from_customer(doc, method):
    """
    Kopiert automatisch email_id vom verknüpften Customer zur Address.
    Wird aufgerufen bevor eine neue Address gespeichert wird.
    """
    # Nur wenn Address noch keine email_id hat
    if doc.email_id:
        return
    
    # Durch alle Links gehen und nach Customer suchen
    for link in doc.links:
        if link.link_doctype == "Customer" and link.link_name:
            try:
                # Customer laden
                customer = frappe.get_doc("Customer", link.link_name)
                
                # Wenn Customer eine email_id hat, übertragen
                if customer.email_id:
                    doc.email_id = customer.email_id
                    frappe.logger().info(f"E-Mail automatisch von Customer {customer.name} an Address übertragen: {customer.email_id}")
                    break
                    
            except Exception as e:
                frappe.logger().error(f"Fehler beim Kopieren der E-Mail vom Customer {link.link_name}: {str(e)}")
                continue

def notify_draft_invoices_on_address_change(doc, method):
    """
    Aktualisiert AUTOMATISCH alle offenen Rechnungen im Entwurfsmodus, die DIESE Adresse verwenden.
    """
    if method not in ["on_update", "after_insert"]:
        return
    
    try:
        # Finde alle Kunden, die mit dieser Adresse verknüpft sind
        customer_links = frappe.get_all("Dynamic Link",
            filters={
                "parent": doc.name,
                "parenttype": "Address",
                "link_doctype": "Customer"
            },
            fields=["link_name"]
        )
        
        if not customer_links:
            return
        
        # Für jeden Kunden: Finde Rechnungen im Entwurfsmodus, die DIESE Adresse verwenden
        for link in customer_links:
            customer = link.link_name
            
            # Finde alle Sales Invoices im Entwurfsmodus für diesen Kunden, die DIESE Adresse verwenden
            draft_invoices = frappe.get_all("Sales Invoice",
                filters={
                    "customer": customer,
                    "docstatus": 0,  # Entwurfsmodus
                    "customer_address": doc.name  # NUR Rechnungen mit DIESER Adresse
                },
                fields=["name"]
            )
            
            # Auch Versandadressen prüfen
            shipping_invoices = frappe.get_all("Sales Invoice",
                filters={
                    "customer": customer,
                    "docstatus": 0,  # Entwurfsmodus
                    "shipping_address_name": doc.name  # NUR Rechnungen mit DIESER Versandadresse
                },
                fields=["name"]
            )
            
            # Kombiniere beide Listen (ohne Duplikate)
            all_invoices = draft_invoices + shipping_invoices
            unique_invoices = []
            seen_names = set()
            
            for invoice in all_invoices:
                if invoice.name not in seen_names:
                    unique_invoices.append(invoice)
                    seen_names.add(invoice.name)
            
            if unique_invoices:
                # AKTUALISIERE JEDE RECHNUNG SOFORT
                for invoice in unique_invoices:
                    try:
                        # Lade die Rechnung
                        invoice_doc = frappe.get_doc("Sales Invoice", invoice.name)
                        
                        # Prüfe, ob diese Adresse in der Rechnung verwendet wird
                        needs_update = False
                        
                        # Prüfe Rechnungsadresse
                        if invoice_doc.customer_address == doc.name:
                            invoice_doc.address_display = doc.get_display()
                            needs_update = True
                        
                        # Prüfe Versandadresse
                        if invoice_doc.shipping_address_name == doc.name:
                            invoice_doc.shipping_address = doc.get_display()
                            needs_update = True
                        
                        # Speichere die Rechnung, falls Änderungen vorgenommen wurden
                        if needs_update:
                            invoice_doc.flags.ignore_permissions = True
                            invoice_doc.flags.ignore_validate = True
                            invoice_doc.save()
                            
                            frappe.log_error(
                                f"Rechnung {invoice.name} automatisch aktualisiert nach Adressänderung {doc.name}",
                                "INFO: auto_invoice_update"
                            )
                    
                    except Exception as e:
                        frappe.log_error(f"Fehler beim Aktualisieren der Rechnung {invoice.name}: {str(e)}", "ERROR: auto_invoice_update")
                
                # Benachrichtigung an den Benutzer senden
                if len(unique_invoices) > 0:
                    invoice_names = [inv.name for inv in unique_invoices]
                    
                    frappe.publish_realtime(
                        "show_alert",
                        {
                            "message": f"Adresse geändert! {len(unique_invoices)} Rechnung(en) im Entwurfsmodus wurden automatisch aktualisiert: {', '.join(invoice_names[:3])}{'...' if len(invoice_names) > 3 else ''}",
                            "indicator": "green"
                        },
                        user=frappe.session.user
                    )
    
    except Exception as e:
        frappe.log_error(f"Fehler beim automatischen Aktualisieren von Entwurfs-Rechnungen: {str(e)}", "ERROR: auto_address_update")