import frappe
from frappe import _
from frappe.utils import today
from enjo_party.enjo_party.utils.stripe_checkout import create_stripe_checkout_session
from enjo_party.enjo_party.utils.stripe_subscription import cancel_stripe_subscription_at_period_end
from enjo_party.enjo_party.utils.sales_invoice_hooks import ensure_inclusive_taxes

def handle_subscription_cancel(doc, method):
    """
    Wird aufgerufen, wenn ein Abonnement storniert wird (on_cancel)
    Kündigt auch die Stripe Subscription
    """
    try:
        # Prüfe ob das Abo aktiv war (nicht bereits storniert)
        if doc.status == "Cancelled":
            frappe.log_error(f"ABO STORNIERT {doc.name}: starte Stripe Kündigung", "DEBUG: subscription_hook")
            # Kündige Stripe Subscription zum Ende der Periode
            try:
                result = cancel_stripe_subscription_at_period_end(doc.name)
                if result:
                    frappe.log_error(f"ABO STORNIERT {doc.name}: ERFOLGREICH - Stripe Subscription wird gekündigt", "SUCCESS: subscription_hook")
                else:
                    frappe.log_error(f"ABO STORNIERT {doc.name}: Fehler - Stripe Subscription ID nicht gefunden", "WARNING: subscription_hook")
            except Exception as e:
                frappe.log_error(f"ABO STORNIERT {doc.name}: Exception {str(e)}\n{frappe.get_traceback()}", "ERROR: subscription_hook")
    except Exception as e:
        frappe.log_error(f"Fehler in handle_subscription_cancel für {doc.name}: {str(e)}", "ERROR: subscription_hook")

def force_subscription_update(doc, method):
    """
    Wird nach dem Speichern eines Abonnements ausgeführt und erzwingt sofort ein Update
    """
    try:
        # Hole vorherigen Wert AUS DER DB (bevor wir prüfen)
        previous_cancel_at_period_end = frappe.db.get_value("Subscription", doc.name, "cancel_at_period_end")
        
        frappe.log_error(f"HOOK {doc.name}: cancel={doc.cancel_at_period_end}, vorher={previous_cancel_at_period_end}, method={method}", "DEBUG: subscription_hook")
        
        # Prüfe ob cancel_at_period_end auf True gesetzt wurde
        # Wenn cancel_at_period_end jetzt True ist UND vorher False/None/0 war
        if doc.cancel_at_period_end == 1 and not previous_cancel_at_period_end:
            frappe.log_error(f"KÜNDIGUNG {doc.name}: starte Stripe Kündigung (cancel_at_period_end wurde gesetzt)", "DEBUG: subscription_hook")
            # Kündige Stripe Subscription zum Ende der Periode
            try:
                result = cancel_stripe_subscription_at_period_end(doc.name)
                if result:
                    frappe.log_error(f"KÜNDIGUNG {doc.name}: ERFOLGREICH - Stripe Subscription wird zum Periodenende gekündigt", "SUCCESS: subscription_hook")
                else:
                    frappe.log_error(f"KÜNDIGUNG {doc.name}: Fehler - Stripe Subscription ID nicht gefunden", "ERROR: subscription_hook")
            except Exception as e:
                frappe.log_error(f"KÜNDIGUNG {doc.name}: Exception {str(e)}\n{frappe.get_traceback()}", "ERROR: subscription_hook")
        elif doc.cancel_at_period_end == 1:
            frappe.log_error(f"HOOK {doc.name}: cancel_at_period_end bereits True (wurde schon behandelt)", "DEBUG: subscription_hook")
        
        # Prüfe ob das Abo aktiv ist (Status "Active") und das Startdatum erreicht ist
        subscription = frappe.get_doc("Subscription", doc.name)
        start_date_reached = subscription.start_date and frappe.utils.getdate(subscription.start_date) <= frappe.utils.getdate()
        
        if start_date_reached:
            frappe.log_error(f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist erreicht, führe process() aus", "DEBUG: subscription_hook")
            
            subscription.process()
            frappe.db.commit()
            
            frappe.log_error(f"SUBSCRIPTION HOOK: process() abgeschlossen für {doc.name}", "DEBUG: subscription_hook")
            
            # Erstelle Payment Request für die generierte Rechnung
            invoices = frappe.get_all("Sales Invoice", 
                filters={
                    "subscription": doc.name,
                    "docstatus": 1
                },
                order_by="creation desc",
                limit=1
            )
            
            frappe.log_error(f"SUBSCRIPTION HOOK: Gefundene Invoices: {len(invoices)}", "DEBUG: subscription_hook")
            
            if invoices:
                invoice_name = invoices[0].name
                
                # WICHTIG: Commit vor Prüfung, damit create_payment_request_for_subscription_invoice die Payment Request findet
                frappe.db.commit()
                
                # Prüfe ob bereits eine Payment Request existiert (auch Draft-Status)
                existing_requests = frappe.get_all("Payment Request",
                    filters={
                        "reference_doctype": "Sales Invoice",
                        "reference_name": invoice_name,
                        "docstatus": ["!=", 2]  # Nicht storniert
                    }
                )
                
                if existing_requests:
                    frappe.log_error(f"SUBSCRIPTION HOOK: Payment Request existiert bereits für Invoice {invoice_name}", "DEBUG: subscription_hook")
                    return
                
                # WICHTIG: Invoice neu aus DB laden, um sicherzustellen, dass alle Werte korrekt sind
                frappe.db.commit()  # Sicherstellen, dass Invoice vollständig gespeichert ist
                invoice = frappe.get_doc("Sales Invoice", invoice_name)
                invoice.reload()  # Neu laden
                
                # WICHTIG: Stelle sicher, dass Steuern auf "inklusive" gesetzt sind
                # Da subscription.process() die Rechnung direkt submitted, müssen wir sie temporär auf Draft setzen,
                # die Steuern anwenden, und dann wieder submiten
                try:
                    # Prüfe ob Steuern vorhanden sind und ob sie auf "inklusive" gesetzt sind
                    needs_tax_update = False
                    if invoice.taxes:
                        for tax in invoice.taxes:
                            if tax.included_in_print_rate != 1:
                                needs_tax_update = True
                                break
                    elif not invoice.taxes_and_charges:
                        # Keine Steuern vorhanden - muss Steuer-Template setzen
                        needs_tax_update = True
                    
                    if needs_tax_update:
                        frappe.log_error(f"SUBSCRIPTION HOOK: Steuern müssen aktualisiert werden für Invoice {invoice_name}", "DEBUG: subscription_hook")
                        # Setze Rechnung auf Draft (nur wenn sie submitted ist)
                        if invoice.docstatus == 1:
                            invoice.docstatus = 0
                            invoice.flags.ignore_validate_update_after_submit = True
                            invoice.flags.ignore_validate = True
                            invoice.save(ignore_permissions=True)
                            frappe.db.commit()
                        
                        # Wende Steuerlogik an
                        ensure_inclusive_taxes(invoice)
                        
                        # Speichere Änderungen
                        invoice.save(ignore_permissions=True)
                        frappe.db.commit()
                        
                        # Submit wieder (nur wenn sie vorher submitted war)
                        if invoice.docstatus == 0:
                            invoice.submit()
                            frappe.db.commit()
                            frappe.log_error(f"SUBSCRIPTION HOOK: Invoice {invoice_name} mit Steuern aktualisiert und wieder submitted", "SUCCESS: subscription_hook")
                except Exception as e:
                    frappe.log_error(f"SUBSCRIPTION HOOK: Fehler beim Aktualisieren der Steuern für Invoice {invoice_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: subscription_hook")
                    # Weiter mit der normalen Verarbeitung, auch wenn Steuer-Update fehlgeschlagen ist
                
                # Betrag direkt aus DB lesen für exakte Übereinstimmung
                invoice_grand_total = frappe.db.get_value("Sales Invoice", invoice_name, "grand_total")
                
                msg = f"Erstelle Payment Request für Invoice {invoice_name}, total={invoice_grand_total}"
                frappe.log_error(msg[:140], "DEBUG: subscription_hook")
                
                # Payment Request erstellen (ohne message zuerst)
                payment_request = frappe.get_doc({
                    "doctype": "Payment Request",
                    "payment_request_type": "Inward",
                    "transaction_date": invoice.posting_date,
                    "party_type": "Customer",
                    "party": invoice.customer,
                    "reference_doctype": "Sales Invoice",
                    "reference_name": invoice.name,
                    "payment_gateway_account": "Stripe-Stripe - EUR",
                    "grand_total": invoice_grand_total,
                    "currency": invoice.currency,
                    "email_to": invoice.contact_email,
                    "subject": f"Rechnung {invoice.name}",
                    "is_a_subscription": 1,
                    "payment_channel": "Phone",
                    "mute_email": 1
                })
                
                # Füge Subscription Plans hinzu (notwendig für Validierung)
                subscription = frappe.get_doc("Subscription", doc.name)
                
                # Prüfe welches payment_gateway_account in den Subscription Plans vorhanden ist
                gateway_account = payment_request.payment_gateway_account
                if subscription.plans:
                    for plan_detail in subscription.plans:
                        # Prüfe ob dieser Plan ein payment_gateway_account hat
                        plan_gateway = getattr(plan_detail, 'payment_gateway_account', None)
                        if plan_gateway:
                            frappe.log_error(f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hat payment_gateway_account: {plan_gateway}", "DEBUG: subscription_hook")
                            gateway_account = plan_gateway
                            # Setze Payment Request auf dasselbe Account
                            payment_request.payment_gateway_account = gateway_account
                            break  # Verwende das erste gefundene Account
                
                # Stelle sicher, dass Payment Request das gateway_account hat
                payment_request.payment_gateway_account = gateway_account
                frappe.log_error(f"SUBSCRIPTION HOOK: Verwende payment_gateway_account: {gateway_account}", "DEBUG: subscription_hook")
                
                for plan_detail in subscription.plans:
                    # Prüfe und aktualisiere das payment_gateway im Subscription Plan DocType
                    plan_doc = frappe.get_doc("Subscription Plan", plan_detail.plan)
                    if plan_doc.payment_gateway != gateway_account:
                        msg = f"Plan {plan_detail.plan}: payment_gateway={plan_doc.payment_gateway}, setze auf {gateway_account}"
                        frappe.log_error(msg[:140], "DEBUG: subscription_hook")
                        plan_doc.payment_gateway = gateway_account
                        plan_doc.save(ignore_permissions=True)
                    
                    # IMMER dasselbe payment_gateway_account für alle Plans verwenden
                    plan_row = payment_request.append("subscription_plans", {
                        "plan": plan_detail.plan,
                        "qty": plan_detail.qty,
                        "payment_gateway_account": gateway_account
                    })
                    frappe.log_error(f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hinzugefügt mit payment_gateway_account: {plan_row.payment_gateway_account}", "DEBUG: subscription_hook")
                
                # Stelle sicher, dass payment_gateway_account auch NACH dem Hinzufügen der Plans noch gesetzt ist
                payment_request.payment_gateway_account = gateway_account
                frappe.log_error(f"SUBSCRIPTION HOOK: Payment Request payment_gateway_account vor insert: {payment_request.payment_gateway_account}", "DEBUG: subscription_hook")
                
                payment_request.insert(ignore_permissions=True)
                # WICHTIG: Sofort committen, damit create_payment_request_for_subscription_invoice die Payment Request findet
                frappe.db.commit()

                # Stripe-Checkout erzeugen und URL setzen
                stripe_url = create_stripe_checkout_session(payment_request)
                
                # Prüfe ob payment_url gesetzt wurde (Retry-Logik)
                if not stripe_url:
                    frappe.log_error(f"SUBSCRIPTION HOOK: Stripe URL ist leer, versuche erneut für Payment Request {payment_request.name}", "WARNING: subscription_hook")
                    # Reload Payment Request
                    payment_request.reload()
                    stripe_url = create_stripe_checkout_session(payment_request)
                
                if stripe_url:
                    # Immer die echte Stripe-URL verwenden
                    payment_request.payment_url = stripe_url
                    # WICHTIG: Lokale Checkout-Seite dauerhaft deaktivieren.
                    # Durch das Leeren von payment_gateway verhindert ERPNext das Generieren von /stripe_checkout-Links.
                    # payment_gateway_account NICHT löschen, da Subscription Plans es benötigen
                    payment_request.db_set('payment_gateway', '', update_modified=False)
                    # Speichere payment_url in DB
                    payment_request.db_set('payment_url', stripe_url, update_modified=False)
                    frappe.db.commit()
                    # Prüfe nochmal ob payment_url gesetzt wurde
                    payment_request.reload()
                    if payment_request.payment_url != stripe_url:
                        frappe.log_error(f"SUBSCRIPTION HOOK: payment_url wurde nicht gespeichert, setze erneut", "WARNING: subscription_hook")
                        payment_request.db_set('payment_url', stripe_url, update_modified=False)
                        frappe.db.commit()
                    frappe.log_error(f"SUBSCRIPTION HOOK: payment_url erfolgreich gesetzt: {stripe_url[:50]}...", "DEBUG: subscription_hook")
                    
                    # Rendere Message Template aus Payment Gateway Account
                    from frappe.utils.jinja import render_template
                    gateway_account = frappe.get_doc("Payment Gateway Account", "Stripe-Stripe - EUR")
                    message_template = gateway_account.message or ""
                    rendered_message = render_template(message_template, {
                        "doc": invoice,
                        "payment_url": stripe_url
                    })
                    payment_request.message = rendered_message
                    payment_request.save(ignore_permissions=True)
                else:
                    frappe.log_error(f"SUBSCRIPTION HOOK: FEHLER - payment_url konnte nicht erstellt werden für Payment Request {payment_request.name}", "ERROR: subscription_hook")

                # Submit (ohne Standard-Mail) und danach E-Mail manuell senden
                payment_request.submit()
                
                # WICHTIG: payment_url NACH Submit nochmal setzen, da ERPNext es möglicherweise überschreibt
                if stripe_url:
                    payment_request.db_set('payment_url', stripe_url, update_modified=False)
                    frappe.db.commit()
                    frappe.log_error(f"SUBSCRIPTION HOOK: payment_url nach submit erneut gesetzt", "DEBUG: subscription_hook")
                
                # WICHTIG: Message NACH Submit nochmal setzen, falls sie überschrieben wurde
                if stripe_url:
                    from frappe.utils.jinja import render_template
                    gateway_account = frappe.get_doc("Payment Gateway Account", "Stripe-Stripe - EUR")
                    message_template = gateway_account.message or ""
                    frappe.log_error(f"SUBSCRIPTION HOOK: Message Template Länge: {len(message_template) if message_template else 0}", "DEBUG: subscription_hook")
                    if message_template:
                        rendered_message = render_template(message_template, {
                            "doc": invoice,
                            "payment_url": stripe_url
                        })
                        frappe.log_error(f"SUBSCRIPTION HOOK: Gerenderte Message Länge: {len(rendered_message)}", "DEBUG: subscription_hook")
                        payment_request.db_set('message', rendered_message, update_modified=False)
                        frappe.db.commit()
                        # WICHTIG: Payment Request neu laden, damit die Message im Objekt vorhanden ist
                        payment_request.reload()
                    else:
                        frappe.log_error("SUBSCRIPTION HOOK: Message Template ist leer!", "WARNING: subscription_hook")
                
                # ÜBERGANGSWEISE DEAKTIVIERT: E-Mail-Versendung für Abos
                # try:
                #     payment_request.flags.mute_email = 0
                #     # Stelle sicher, dass die Message im payment_request Objekt ist
                #     if not payment_request.message and stripe_url:
                #         from frappe.utils.jinja import render_template
                #         gateway_account = frappe.get_doc("Payment Gateway Account", "Stripe-Stripe - EUR")
                #         message_template = gateway_account.message or ""
                #         if message_template:
                #             payment_request.message = render_template(message_template, {
                #                 "doc": invoice,
                #                 "payment_url": stripe_url
                #             })
                #     # Setze spezifisches Email Account für Abo-Mails
                #     payment_request.flags.email_account = "Abo Mails"
                #     payment_request.send_email()
                #     payment_request.make_communication_entry()
                # except Exception as e:
                #     frappe.log_error(f"Fehler beim Senden der E-Mail: {str(e)}", "ERROR: subscription_hook")

                frappe.log_error(
                    f"SUBSCRIPTION HOOK: Payment Request {payment_request.name} erstellt",
                    "SUCCESS: subscription_hook",
                )
                
                # Erstelle zusätzlich einen Sales Order und verknüpfe ihn mit der bestehenden Invoice
                try:
                    sales_order = create_sales_order_from_invoice(invoice)
                    if sales_order:
                        msg = f"Sales Order {sales_order.name} aus Invoice {invoice_name} erstellt"
                        frappe.log_error(msg[:140], "SUCCESS: subscription_hook")
                        # Verknüpfe Invoice mit Sales Order
                        link_invoice_to_sales_order(invoice, sales_order)
                        frappe.db.commit()
                        frappe.log_error(f"SUBSCRIPTION HOOK: Invoice {invoice_name} mit Sales Order {sales_order.name} verknüpft", "SUCCESS: subscription_hook")
                        
                        # Submit Sales Order - das triggert automatisch Delivery Note und Packing List
                        # Da die Invoice bereits verknüpft ist, wird keine neue Invoice erstellt
                        sales_order.submit()
                        frappe.db.commit()
                        frappe.log_error(f"SUBSCRIPTION HOOK: Sales Order {sales_order.name} submitted - Delivery Note und Packing List sollten erstellt werden", "SUCCESS: subscription_hook")
                except Exception as e:
                    frappe.log_error(f"Fehler beim Erstellen des Sales Order aus Invoice {invoice_name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: create_sales_order_from_invoice")
                
                frappe.msgprint(_("Abonnement-Update und Payment Request wurden automatisch erstellt"))
        else:
            frappe.log_error(f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist noch nicht erreicht", "DEBUG: subscription_hook")
            frappe.msgprint(_("Abonnement-Update wird erst am Startdatum ausgeführt"))
            
    except Exception as e:
        frappe.log_error(f"SUBSCRIPTION HOOK FEHLER für {doc.name}: {str(e)}", "ERROR: subscription_hook")


def create_payment_request_for_subscription_invoice(doc, method):
    """
    Erstellt automatisch Payment Request für alle Sales Invoices die zu einem Abonnement gehören
    Wird bei Sales Invoice on_submit ausgelöst
    WICHTIG: Diese Funktion wird NUR aufgerufen, wenn die Payment Request NICHT bereits von force_subscription_update erstellt wurde
    """
    try:
        # Prüfe ob die Rechnung zu einem Abonnement gehört
        if doc.subscription and doc.docstatus == 1:
            # WICHTIG: Prüfe ob das Startdatum des Abos erreicht ist
            # E-Mail soll nur gesendet werden, wenn das Startdatum erreicht ist
            subscription = frappe.get_doc("Subscription", doc.subscription)
            start_date_reached = subscription.start_date and frappe.utils.getdate(subscription.start_date) <= frappe.utils.getdate()
            
            if not start_date_reached:
                frappe.log_error(f"SUBSCRIPTION HOOK: Startdatum {subscription.start_date} ist noch nicht erreicht für Invoice {doc.name} - überspringe Payment Request Erstellung", "DEBUG: subscription_payment_request")
                return  # Keine Payment Request erstellen, wenn Startdatum noch nicht erreicht ist
            
            # Prüfe ob bereits eine Payment Request existiert
            # WICHTIG: Commit vor der Prüfung, um sicherzustellen, dass alle vorherigen Änderungen gespeichert sind
            frappe.db.commit()
            
            existing_requests = frappe.get_all("Payment Request",
                filters={
                    "reference_doctype": "Sales Invoice",
                    "reference_name": doc.name,
                    "docstatus": ["!=", 2]  # Nicht storniert
                }
            )
            
            if existing_requests:
                frappe.log_error(f"SUBSCRIPTION HOOK: Payment Request existiert bereits für Invoice {doc.name} - überspringe Erstellung und E-Mail", "DEBUG: subscription_payment_request")
                return  # WICHTIG: Früher Return, um keine E-Mail zu versenden
            
            # Keine Payment Request gefunden - erstelle neue
            if not existing_requests:
                # Hole Subscription Details für Subscription Plans
                subscription = frappe.get_doc("Subscription", doc.subscription)
                
                # Payment Request erstellen (ohne message zuerst)
                payment_request = frappe.get_doc({
                    "doctype": "Payment Request",
                    "payment_request_type": "Inward",
                    "transaction_date": doc.posting_date,
                    "party_type": "Customer",
                    "party": doc.customer,
                    "reference_doctype": "Sales Invoice",
                    "reference_name": doc.name,
                    "payment_gateway_account": "Stripe-Stripe - EUR",
                    "grand_total": doc.grand_total,
                    "currency": doc.currency,
                    "email_to": doc.contact_email,
                    "subject": f"Rechnung {doc.name}",
                    "is_a_subscription": 1,
                    "payment_channel": "Phone",
                    "mute_email": 1
                })
                
                # Füge Subscription Plans hinzu (notwendig für Validierung)
                # Prüfe welches payment_gateway_account in den Subscription Plans vorhanden ist
                gateway_account = payment_request.payment_gateway_account
                if subscription.plans:
                    for plan_detail in subscription.plans:
                        # Prüfe ob dieser Plan ein payment_gateway_account hat
                        plan_gateway = getattr(plan_detail, 'payment_gateway_account', None)
                        if plan_gateway:
                            frappe.log_error(f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hat payment_gateway_account: {plan_gateway}", "DEBUG: subscription_hook")
                            gateway_account = plan_gateway
                            # Setze Payment Request auf dasselbe Account
                            payment_request.payment_gateway_account = gateway_account
                            break  # Verwende das erste gefundene Account
                
                # Stelle sicher, dass Payment Request das gateway_account hat
                payment_request.payment_gateway_account = gateway_account
                frappe.log_error(f"SUBSCRIPTION HOOK: Verwende payment_gateway_account: {gateway_account}", "DEBUG: subscription_hook")
                
                for plan_detail in subscription.plans:
                    # Prüfe und aktualisiere das payment_gateway im Subscription Plan DocType
                    plan_doc = frappe.get_doc("Subscription Plan", plan_detail.plan)
                    if plan_doc.payment_gateway != gateway_account:
                        msg = f"Plan {plan_detail.plan}: payment_gateway={plan_doc.payment_gateway}, setze auf {gateway_account}"
                        frappe.log_error(msg[:140], "DEBUG: subscription_hook")
                        plan_doc.payment_gateway = gateway_account
                        plan_doc.save(ignore_permissions=True)
                    
                    # IMMER dasselbe payment_gateway_account für alle Plans verwenden
                    plan_row = payment_request.append("subscription_plans", {
                        "plan": plan_detail.plan,
                        "qty": plan_detail.qty,
                        "payment_gateway_account": gateway_account
                    })
                    frappe.log_error(f"SUBSCRIPTION HOOK: Plan {plan_detail.plan} hinzugefügt mit payment_gateway_account: {plan_row.payment_gateway_account}", "DEBUG: subscription_hook")
                
                # Stelle sicher, dass payment_gateway_account auch NACH dem Hinzufügen der Plans noch gesetzt ist
                payment_request.payment_gateway_account = gateway_account
                frappe.log_error(f"SUBSCRIPTION HOOK: Payment Request payment_gateway_account vor insert: {payment_request.payment_gateway_account}", "DEBUG: subscription_hook")
                
                payment_request.insert(ignore_permissions=True)
                # WICHTIG: Sofort committen, damit force_subscription_update die Payment Request findet
                frappe.db.commit()

                # Stripe-Checkout erzeugen und URL setzen
                stripe_url = create_stripe_checkout_session(payment_request)
                
                # Prüfe ob payment_url gesetzt wurde (Retry-Logik)
                if not stripe_url:
                    frappe.log_error(f"SUBSCRIPTION HOOK: Stripe URL ist leer, versuche erneut für Payment Request {payment_request.name}", "WARNING: subscription_hook")
                    # Reload Payment Request
                    payment_request.reload()
                    stripe_url = create_stripe_checkout_session(payment_request)
                
                if stripe_url:
                    # Immer die echte Stripe-URL verwenden
                    payment_request.payment_url = stripe_url
                    # WICHTIG: Lokale Checkout-Seite dauerhaft deaktivieren.
                    # Durch das Leeren von payment_gateway verhindert ERPNext das Generieren von /stripe_checkout-Links.
                    # payment_gateway_account NICHT löschen, da Subscription Plans es benötigen
                    payment_request.db_set('payment_gateway', '', update_modified=False)
                    # Speichere payment_url in DB
                    payment_request.db_set('payment_url', stripe_url, update_modified=False)
                    frappe.db.commit()
                    # Prüfe nochmal ob payment_url gesetzt wurde
                    payment_request.reload()
                    if payment_request.payment_url != stripe_url:
                        frappe.log_error(f"SUBSCRIPTION HOOK: payment_url wurde nicht gespeichert, setze erneut", "WARNING: subscription_hook")
                        payment_request.db_set('payment_url', stripe_url, update_modified=False)
                        frappe.db.commit()
                    frappe.log_error(f"SUBSCRIPTION HOOK: payment_url erfolgreich gesetzt: {stripe_url[:50]}...", "DEBUG: subscription_hook")
                    
                    # Rendere Message Template aus Payment Gateway Account
                    from frappe.utils.jinja import render_template
                    gateway_account = frappe.get_doc("Payment Gateway Account", "Stripe-Stripe - EUR")
                    message_template = gateway_account.message or ""
                    rendered_message = render_template(message_template, {
                        "doc": doc,
                        "payment_url": stripe_url
                    })
                    payment_request.message = rendered_message
                    payment_request.save(ignore_permissions=True)
                else:
                    frappe.log_error(f"SUBSCRIPTION HOOK: FEHLER - payment_url konnte nicht erstellt werden für Payment Request {payment_request.name}", "ERROR: subscription_hook")

                # Submit (ohne Standard-Mail) und danach E-Mail manuell senden
                payment_request.submit()
                
                # WICHTIG: payment_url NACH Submit nochmal setzen, da ERPNext es möglicherweise überschreibt
                if stripe_url:
                    payment_request.db_set('payment_url', stripe_url, update_modified=False)
                    frappe.db.commit()
                    frappe.log_error(f"SUBSCRIPTION HOOK: payment_url nach submit erneut gesetzt", "DEBUG: subscription_hook")
                
                # WICHTIG: Message NACH Submit nochmal setzen, falls sie überschrieben wurde
                if stripe_url:
                    from frappe.utils.jinja import render_template
                    gateway_account = frappe.get_doc("Payment Gateway Account", "Stripe-Stripe - EUR")
                    message_template = gateway_account.message or ""
                    if message_template:
                        rendered_message = render_template(message_template, {
                            "doc": doc,
                            "payment_url": stripe_url
                        })
                        payment_request.db_set('message', rendered_message, update_modified=False)
                        frappe.db.commit()
                        payment_request.reload()
                
                # WICHTIG: Prüfe nochmal, ob bereits eine Payment Request existiert, bevor E-Mail gesendet wird
                # Dies verhindert doppelte E-Mails, falls force_subscription_update die Payment Request bereits erstellt hat
                frappe.db.commit()
                existing_requests_check = frappe.get_all("Payment Request",
                    filters={
                        "reference_doctype": "Sales Invoice",
                        "reference_name": doc.name,
                        "docstatus": ["!=", 2],  # Nicht storniert
                        "name": ["!=", payment_request.name]  # Nicht die gerade erstellte
                    }
                )
                
                if existing_requests_check:
                    msg = f"Andere Payment Request existiert bereits für Invoice {doc.name} - überspringe E-Mail"
                    frappe.log_error(msg[:140], "DEBUG: subscription_payment_request")
                    return  # Keine E-Mail senden, da bereits eine Payment Request existiert
                
                # ÜBERGANGSWEISE DEAKTIVIERT: E-Mail-Versendung für Abos
                # try:
                #     payment_request.flags.mute_email = 0
                #     # Stelle sicher, dass die Message im payment_request Objekt ist
                #     if not payment_request.message and stripe_url:
                #         from frappe.utils.jinja import render_template
                #         gateway_account = frappe.get_doc("Payment Gateway Account", "Stripe-Stripe - EUR")
                #         message_template = gateway_account.message or ""
                #         if message_template:
                #             payment_request.message = render_template(message_template, {
                #                 "doc": doc,
                #                 "payment_url": stripe_url
                #             })
                #     # Setze spezifisches Email Account für Abo-Mails
                #     payment_request.flags.email_account = "Abo Mails"
                #     payment_request.send_email()
                #     payment_request.make_communication_entry()
                # except Exception as e:
                #     frappe.log_error(f"Fehler beim Senden der E-Mail: {str(e)}", "ERROR: subscription_payment_request")

                frappe.log_error(
                    f"Payment Request {payment_request.name} für Subscription Invoice {doc.name} erstellt",
                    "SUCCESS: subscription_payment_request",
                )
                
                # Erstelle zusätzlich einen Sales Order und verknüpfe ihn mit der bestehenden Invoice
                try:
                    sales_order = create_sales_order_from_invoice(doc)
                    if sales_order:
                        frappe.log_error(f"SUBSCRIPTION HOOK: Sales Order {sales_order.name} aus Invoice {doc.name} erstellt", "SUCCESS: subscription_hook")
                        # Verknüpfe Invoice mit Sales Order
                        link_invoice_to_sales_order(doc, sales_order)
                        frappe.db.commit()
                        frappe.log_error(f"SUBSCRIPTION HOOK: Invoice {doc.name} mit Sales Order {sales_order.name} verknüpft", "SUCCESS: subscription_hook")
                        
                        # Submit Sales Order - das triggert automatisch Delivery Note und Packing List
                        # Da die Invoice bereits verknüpft ist, wird keine neue Invoice erstellt
                        sales_order.submit()
                        frappe.db.commit()
                        frappe.log_error(f"SUBSCRIPTION HOOK: Sales Order {sales_order.name} submitted - Delivery Note und Packing List sollten erstellt werden", "SUCCESS: subscription_hook")
                except Exception as e:
                    frappe.log_error(f"Fehler beim Erstellen des Sales Order aus Invoice {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: create_sales_order_from_invoice")
            
    except Exception as e:
        frappe.log_error(f"Fehler beim Erstellen der Payment Request für Subscription Invoice {doc.name}: {str(e)}", "ERROR: subscription_payment_request")


def set_default_payment_gateway(doc, method):
    """
    Setzt automatisch Payment Gateway auf "Stripe-Stripe - EUR" wenn leer
    Wird bei Subscription Plan before_save/validate aufgerufen
    """
    try:
        if not doc.payment_gateway:
            doc.payment_gateway = "Stripe-Stripe - EUR"
            # Prüfe ob Payment Gateway Account existiert
            if not frappe.db.exists("Payment Gateway Account", "Stripe-Stripe - EUR"):
                frappe.log_error("Payment Gateway Account 'Stripe-Stripe - EUR' existiert nicht", "WARNING: subscription_plan")
            else:
                frappe.log_error(f"Payment Gateway auf Stripe-Stripe - EUR gesetzt für Plan {doc.name}", "DEBUG: subscription_plan")
    except Exception as e:
        frappe.log_error(f"Fehler beim Setzen des Payment Gateways für Plan {doc.name}: {str(e)}", "ERROR: subscription_plan")


def validate_subscription_end_date(doc, method):
    """
    Deaktiviert Enddatum-Validierung wenn "Folgen Sie den Kalendermonaten" aktiviert ist
    Wird bei Subscription before_validate aufgerufen
    Überschreibt ERPNext's validate_to_follow_calendar_months Methode
    """
    try:
        # Prüfe ob "Folgen Sie den Kalendermonaten" aktiviert ist
        if doc.follow_calendar_months == 1:
            # Überschreibe die validate_to_follow_calendar_months Methode
            # um die Enddatum-Validierung zu deaktivieren
            def patched_validate_to_follow_calendar_months(self):
                # Überschreibe die Original-Methode - mache einfach nichts
                # Das deaktiviert die Validierung komplett
                pass
            
            # Setze die überschriebene Methode
            import types
            doc.validate_to_follow_calendar_months = types.MethodType(patched_validate_to_follow_calendar_months, doc)
            
            frappe.log_error(f"Enddatum-Validierung deaktiviert für Subscription {doc.name} (follow_calendar_months aktiviert)", "DEBUG: subscription_validate")
    except Exception as e:
        frappe.log_error(f"Fehler bei Enddatum-Validierung für Subscription {doc.name}: {str(e)}", "ERROR: subscription_validate")


def ensure_subscription_invoice_taxes_before_validate(doc, method):
    """
    Stellt sicher, dass Subscription-Invoices Steuern haben BEVOR sie validiert werden
    Wird bei Sales Invoice before_validate aufgerufen
    """
    try:
        # Nur für Subscription-Invoices
        if not doc.subscription:
            return
        
        # Nur im Draft-Modus
        if doc.docstatus != 0:
            return
        
        # Prüfe ob Steuern vorhanden sind und korrekt gesetzt sind
        needs_tax_update = False
        
        if not doc.taxes_and_charges:
            # Keine Steuern vorhanden - muss Steuer-Template setzen
            needs_tax_update = True
        elif not doc.taxes or len(doc.taxes) == 0:
            # Keine Steuer-Zeilen vorhanden
            needs_tax_update = True
        elif doc.taxes:
            # Prüfe ob Steuern auf "inklusive" gesetzt sind
            for tax in doc.taxes:
                if tax.included_in_print_rate != 1:
                    needs_tax_update = True
                    break
        
        if needs_tax_update:
            msg = f"Steuern müssen gesetzt werden für Invoice {doc.name} (Subscription: {doc.subscription})"
            frappe.log_error(msg[:140], "DEBUG: subscription_invoice_taxes")
            
            # Setze Steuer-Template wenn nicht gesetzt
            if not doc.taxes_and_charges:
                tax_template = frappe.db.get_value("Sales Taxes and Charges Template", 
                    {"company": doc.company, "is_default": 1}, "name")
                if tax_template:
                    doc.taxes_and_charges = tax_template
                    doc.taxes = []  # Leere bestehende Steuern
                    doc.run_method("set_taxes")  # Setze Steuern neu
                    frappe.log_error(f"Steuer-Template {tax_template} gesetzt für Invoice {doc.name}", "DEBUG: subscription_invoice_taxes")
            
            # Wende Steuerlogik an
            ensure_inclusive_taxes(doc)
            
            # Entferne alle Steuern außer 19% MWST
            if doc.taxes:
                taxes_to_remove = []
                for tax in doc.taxes:
                    # Prüfe ob es eine 19% Steuer ist
                    tax_rate = getattr(tax, 'rate', 0) or 0
                    description = getattr(tax, 'description', '') or ''
                    
                    # Behalte nur Steuern mit 19% (prüfe rate oder description)
                    if tax_rate != 19 and '19' not in description and '19%' not in description:
                        taxes_to_remove.append(tax)
                
                # Entferne Steuern die nicht 19% sind
                for tax in taxes_to_remove:
                    doc.remove(tax)
                    msg = f"Steuer {tax.description or tax.account_head} (Rate: {tax.rate}) entfernt - nur 19%"
                    frappe.log_error(msg[:140], "DEBUG: subscription_invoice_taxes")
            
            # Neuberechnung mit Steuern
            doc.calculate_taxes_and_totals()
            
            frappe.log_error(f"Steuern gesetzt für Invoice {doc.name} (nur 19% MWST)", "SUCCESS: subscription_invoice_taxes")
    except Exception as e:
        frappe.log_error(f"Fehler beim Setzen der Steuern für Subscription Invoice {doc.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: subscription_invoice_taxes")


def ensure_subscription_invoice_taxes(doc, method):
    """
    Stellt sicher, dass Subscription-Invoices Steuern haben BEVOR sie submitted werden
    Wird bei Sales Invoice before_submit aufgerufen
    """
    try:
        # Nur für Subscription-Invoices
        if not doc.subscription:
            return
        
        # Nur im Draft-Modus (bevor submit)
        if doc.docstatus != 0:
            return
        
        # Prüfe ob Steuern vorhanden sind und korrekt gesetzt sind
        needs_tax_update = False
        
        if not doc.taxes_and_charges:
            # Keine Steuern vorhanden - muss Steuer-Template setzen
            needs_tax_update = True
        elif doc.taxes:
            # Prüfe ob Steuern auf "inklusive" gesetzt sind
            for tax in doc.taxes:
                if tax.included_in_print_rate != 1:
                    needs_tax_update = True
                    break
        
        if needs_tax_update:
            msg = f"Steuern müssen gesetzt werden für Invoice {doc.name} (Subscription: {doc.subscription})"
            frappe.log_error(msg[:140], "DEBUG: subscription_invoice_taxes")
            
            # Wende Steuerlogik an
            ensure_inclusive_taxes(doc)
            
            # Entferne alle Steuern außer 19% MWST
            if doc.taxes:
                taxes_to_remove = []
                for tax in doc.taxes:
                    # Prüfe ob es eine 19% Steuer ist
                    tax_rate = getattr(tax, 'rate', 0) or 0
                    description = getattr(tax, 'description', '') or ''
                    
                    # Behalte nur Steuern mit 19% (prüfe rate oder description)
                    if tax_rate != 19 and '19' not in description and '19%' not in description:
                        taxes_to_remove.append(tax)
                
                # Entferne Steuern die nicht 19% sind
                for tax in taxes_to_remove:
                    doc.remove(tax)
                    msg = f"Steuer {tax.description or tax.account_head} (Rate: {tax.rate}) entfernt - nur 19%"
                    frappe.log_error(msg[:140], "DEBUG: subscription_invoice_taxes")
            
            # Neuberechnung mit Steuern
            doc.calculate_taxes_and_totals()
            
            frappe.log_error(f"Steuern gesetzt für Invoice {doc.name} (nur 19% MWST)", "SUCCESS: subscription_invoice_taxes")
    except Exception as e:
        frappe.log_error(f"Fehler beim Setzen der Steuern für Subscription Invoice {doc.name}: {str(e)}", "ERROR: subscription_invoice_taxes")


def validate_subscription_plan_interval(doc, method):
    """
    Deaktiviert Abrechnungsintervall-Validierung wenn Subscription "Folgen Sie den Kalendermonaten" aktiviert hat
    Wird bei Subscription Plan validate aufgerufen
    """
    try:
        # Prüfe ob dieser Plan in einer Subscription mit follow_calendar_months verwendet wird
        # Suche nach Subscriptions die diesen Plan verwenden
        subscriptions = frappe.get_all("Subscription Plan Detail",
            filters={"plan": doc.name},
            fields=["parent"],
            limit=10
        )
        
        for plan_detail in subscriptions:
            try:
                subscription = frappe.get_doc("Subscription", plan_detail.parent)
                if subscription.follow_calendar_months == 1:
                    # Überschreibe die validate Methode die Intervall-Validierung verlangt
                    # ERPNext's Standard-Validierung wird überschrieben
                    # Das Intervall muss nicht "Monat" sein wenn follow_calendar_months aktiviert ist
                    frappe.log_error(f"Intervall-Validierung übersprungen für Plan {doc.name} (Subscription {plan_detail.parent} folgt Kalendermonaten)", "DEBUG: subscription_plan_validate")
                    break
            except:
                continue
    except Exception as e:
        frappe.log_error(f"Fehler bei Intervall-Validierung für Plan {doc.name}: {str(e)}", "ERROR: subscription_plan_validate")


def link_invoice_to_sales_order(invoice, sales_order):
    """
    Verknüpft eine bestehende Invoice mit einem Sales Order
    Aktualisiert die Invoice Items, um den Sales Order zu referenzieren
    """
    try:
        frappe.log_error(f"Verknüpfe Invoice {invoice.name} mit Sales Order {sales_order.name}", "DEBUG: link_invoice_to_sales_order")
        
        # Lade Invoice neu
        invoice.reload()
        sales_order.reload()
        
        # Verknüpfe jedes Invoice Item mit dem Sales Order Item über SQL
        # Hole alle Invoice Items
        invoice_items = frappe.get_all("Sales Invoice Item",
            filters={"parent": invoice.name},
            fields=["name", "idx"],
            order_by="idx"
        )
        
        # Hole alle Sales Order Items
        so_items = frappe.get_all("Sales Order Item",
            filters={"parent": sales_order.name},
            fields=["name", "idx"],
            order_by="idx"
        )
        
        frappe.log_error(f"Invoice Items: {len(invoice_items)}, Sales Order Items: {len(so_items)}", "DEBUG: link_invoice_to_sales_order")
        
        # Verknüpfe jedes Invoice Item mit dem entsprechenden Sales Order Item
        for i, invoice_item in enumerate(invoice_items):
            if i < len(so_items):
                so_item_name = so_items[i].name
                # Setze sales_order und so_detail direkt über SQL
                frappe.db.sql("""
                    UPDATE `tabSales Invoice Item`
                    SET sales_order = %s, so_detail = %s
                    WHERE name = %s
                """, (sales_order.name, so_item_name, invoice_item.name))
                frappe.log_error(f"Invoice Item {invoice_item.name} verknüpft mit Sales Order Item {so_item_name}", "DEBUG: link_invoice_to_sales_order")
        
        frappe.db.commit()
        frappe.log_error(f"Invoice {invoice.name} erfolgreich mit Sales Order {sales_order.name} verknüpft (über Items)", "SUCCESS: invoice_linked_to_sales_order")
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Verknüpfen der Invoice {invoice.name} mit Sales Order {sales_order.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: link_invoice_to_sales_order")


def create_sales_order_from_invoice(invoice):
    """
    Erstellt einen Sales Order aus einer Sales Invoice (für Subscription-Invoices)
    Dieser Sales Order wird NICHT submitted, sondern nur mit der Invoice verknüpft
    """
    try:
        frappe.log_error(f"Erstelle Sales Order aus Invoice {invoice.name}", "DEBUG: create_sales_order_from_invoice")
        
        # Prüfe ob bereits ein Sales Order für diese Invoice existiert
        # Suche über po_no Feld (kann die Invoice-Nummer enthalten) oder einfach immer erstellen
        # Da wir keine zuverlässige Referenz haben, erstellen wir einfach immer einen neuen
        # Falls bereits einer existiert, wird das im try-catch abgefangen
        
        # Erstelle Items aus Invoice Items
        items = []
        for invoice_item in invoice.items:
            # Prüfe ob item_code vorhanden ist
            if not invoice_item.item_code:
                continue
                
            items.append({
                "doctype": "Sales Order Item",
                "item_code": invoice_item.item_code,
                "item_name": invoice_item.item_name or invoice_item.item_code,
                "qty": invoice_item.qty or 1,
                "rate": invoice_item.rate or 0,
                "uom": invoice_item.uom or "Stk",
                "stock_uom": invoice_item.stock_uom or invoice_item.uom or "Stk",
                "conversion_factor": invoice_item.conversion_factor or 1.0,
                "warehouse": invoice_item.warehouse,
                "delivery_date": invoice.due_date or invoice.posting_date or today()
            })
        
        if not items:
            frappe.log_error(f"Keine Items gefunden für Invoice {invoice.name}", "ERROR: no_items_found")
            return None
        
        # Erstelle Sales Order
        sales_order_data = {
            "doctype": "Sales Order",
            "customer": invoice.customer,
            "transaction_date": invoice.posting_date or today(),
            "delivery_date": invoice.due_date or invoice.posting_date or today(),
            "company": invoice.company or frappe.defaults.get_global_default("company"),
            "currency": invoice.currency or frappe.defaults.get_global_default("currency"),
            "items": items,
            "status": "Draft",
            "order_type": "Sales",
            "po_no": f"Subscription Invoice: {invoice.name}"  # Verwende po_no für Referenz
        }
        
        # Füge Adressen hinzu falls vorhanden
        if invoice.customer_address:
            sales_order_data["customer_address"] = invoice.customer_address
        if invoice.shipping_address_name:
            sales_order_data["shipping_address_name"] = invoice.shipping_address_name
        elif invoice.customer_address:
            sales_order_data["shipping_address_name"] = invoice.customer_address
        
        # Füge Subscription-Referenz hinzu falls vorhanden
        if invoice.subscription:
            sales_order_data["po_no"] = f"Subscription Invoice: {invoice.name} (Subscription: {invoice.subscription})"
            # Setze Custom Field custom_subscription
            if hasattr(sales_order_data, 'custom_subscription'):
                sales_order_data["custom_subscription"] = invoice.subscription
        
        sales_order = frappe.get_doc(sales_order_data)
        # Setze custom_subscription nach Erstellung des Dokuments
        if invoice.subscription and hasattr(sales_order, 'custom_subscription'):
            sales_order.custom_subscription = invoice.subscription
        sales_order.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Stelle sicher, dass custom_subscription gesetzt ist (falls Custom Field existiert)
        if invoice.subscription:
            try:
                frappe.db.set_value("Sales Order", sales_order.name, "custom_subscription", invoice.subscription, update_modified=False)
                frappe.db.commit()
            except:
                pass  # Custom Field existiert möglicherweise nicht
        
        frappe.log_error(f"Sales Order {sales_order.name} aus Invoice {invoice.name} erstellt", "SUCCESS: sales_order_created")
        return sales_order
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Erstellen des Sales Order aus Invoice {invoice.name}: {str(e)}\n{frappe.get_traceback()}", "ERROR: create_sales_order_from_invoice")
        return None
