import frappe
import stripe
from frappe import _

def create_stripe_checkout_session(payment_request):
    """
    Erstellt eine Stripe Checkout Session mit allen Zahlungsmethoden
    """
    try:
        # Hole Stripe Settings
        stripe_settings = frappe.get_doc("Stripe Settings", "Stripe")
        
        # Setze API Key (verschlüsselt gespeichert)
        api_key = frappe.utils.password.get_decrypted_password("Stripe Settings", "Stripe", "secret_key")
        if not api_key:
            frappe.throw(_("Stripe Secret Key ist nicht konfiguriert"))
        
        stripe.api_key = api_key
        
        # Redirect URL
        redirect_url = stripe_settings.redirect_url or frappe.utils.get_url()
        
        # Standardkonfiguration – Einmalzahlung
        mode = 'payment'
        recurring_config = None
        metadata = {
            'payment_request': payment_request.name,
            'reference_doctype': payment_request.reference_doctype,
            'reference_name': payment_request.reference_name,
        }

        # Prüfe ob die Rechnung zu einem Subscription gehört
        subscription_ref = None
        if payment_request.reference_doctype == "Sales Invoice" and payment_request.reference_name:
            subscription_ref = frappe.db.get_value(
                "Sales Invoice", payment_request.reference_name, "subscription"
            )

        if subscription_ref:
            try:
                subscription_doc = frappe.get_doc("Subscription", subscription_ref)
                billing_info = subscription_doc.get_billing_cycle_and_interval()
                if billing_info:
                    interval = (billing_info[0].get("billing_interval") or "Month").lower()
                    if interval not in ["day", "week", "month", "year"]:
                        interval = "month"
                    interval_count = billing_info[0].get("billing_interval_count") or 1
                    recurring_config = {
                        'interval': interval,
                        'interval_count': interval_count,
                    }
                    mode = 'subscription'
                    metadata['subscription'] = subscription_ref
            except Exception as err:
                frappe.log_error(
                    f"Fehler beim Ermitteln des Subscription-Intervalls für {subscription_ref}: {err}",
                    "ERROR: stripe_checkout_subscription"
                )

        price_data = {
            'currency': payment_request.currency.lower(),
            'product_data': {
                'name': f'Rechnung {payment_request.reference_name}',
                'description': f"BE'motion Abonnement - Rechnung {payment_request.reference_name}",
            },
            'unit_amount': int(payment_request.grand_total * 100),
        }

        if recurring_config:
            price_data['recurring'] = recurring_config

        # WICHTIG: Reihenfolge der Zahlungsmethoden - diese Reihenfolge wird im Stripe Checkout angezeigt
        # Reihenfolge: 1. Karte, 2. SEPA, 3. Klarna
        # PayPal ist deaktiviert und wurde entfernt
        session = stripe.checkout.Session.create(
            payment_method_types=['card', 'sepa_debit', 'klarna'],
            line_items=[{
                'price_data': price_data,
                'quantity': 1,
            }],
            mode=mode,
            success_url=f'{redirect_url}?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=redirect_url,
            customer_email=payment_request.email_to,
            metadata=metadata
        )

        # Speichere die Stripe Checkout URL direkt in der Payment Request
        if not session.url:
            frappe.log_error(f"FEHLER: Stripe Session hat keine URL für Payment Request {payment_request.name}", "ERROR: stripe_checkout")
            return None
        
        payment_request.payment_url = session.url
        payment_request.flags.ignore_permissions = True
        payment_request.save(ignore_permissions=True)
        
        # WICHTIG: Commit und prüfe ob payment_url gespeichert wurde
        frappe.db.commit()
        payment_request.reload()
        if payment_request.payment_url != session.url:
            # Versuche erneut zu speichern
            payment_request.db_set('payment_url', session.url, update_modified=False)
            frappe.db.commit()
        
        # WICHTIG: Wenn es eine Subscription ist, speichere die Stripe Subscription ID in der Payment Request
        # (wird nach erfolgreichem Payment verfügbar sein)
        if mode == 'subscription' and session.get('subscription'):
            # Speichere Stripe Subscription ID in einem Custom Field oder in der Payment Request
            frappe.log_error(f"Stripe Subscription ID für Session: {session.get('subscription')}", "DEBUG: stripe_checkout")
        
        return session.url
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Erstellen der Stripe Checkout Session: {str(e)}", "ERROR: stripe_checkout")
        return None


@frappe.whitelist(allow_guest=True)
def get_stripe_checkout_url(payment_request_name):
    """
    API Endpoint um Stripe Checkout URL zu generieren
    """
    try:
        payment_request = frappe.get_doc("Payment Request", payment_request_name)
        
        # Erstelle Checkout Session
        checkout_url = create_stripe_checkout_session(payment_request)
        
        if checkout_url:
            # Speichere die URL in der Payment Request
            payment_request.db_set('payment_url', checkout_url, update_modified=False)
            return checkout_url
        else:
            frappe.throw(_("Fehler beim Erstellen der Stripe Checkout Session"))
            
    except Exception as e:
        frappe.log_error(f"Fehler in get_stripe_checkout_url: {str(e)}", "ERROR: stripe_checkout")
        frappe.throw(_("Fehler beim Generieren des Payment Links"))

