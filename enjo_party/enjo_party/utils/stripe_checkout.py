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

        try:
            grand_total = float(payment_request.grand_total)
        except (TypeError, ValueError):
            grand_total = 0.0
        if grand_total <= 0:
            frappe.log_error(f"create_stripe_checkout_session: grand_total ungültig für {payment_request.name}", "stripe_checkout")
            return None
        currency = (getattr(payment_request, "currency", None) or "eur").lower()[:3]
        price_data = {
            'currency': currency,
            'product_data': {
                'name': f'Rechnung {payment_request.reference_name}',
                'description': f"BE'motion Abonnement - Rechnung {payment_request.reference_name}",
            },
            'unit_amount': int(round(grand_total * 100)),
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
            customer_email=payment_request.email_to or None,
            metadata=metadata
        )

        # Speichere die Stripe Checkout URL in der Payment Request nur bei Draft (vor Submit)
        # Bei bereits submitted Payment Request (z.B. Aufruf aus redirect_to_stripe_checkout) nicht
        # überschreiben – sonst UpdateAfterSubmitError; die DB behält den Dauer-Link.
        if not session.url:
            frappe.log_error(f"Stripe Session ohne URL für {payment_request.name}", "stripe_checkout")
            return None
        
        if payment_request.docstatus == 0:
            payment_request.payment_url = session.url
            payment_request.flags.ignore_permissions = True
            payment_request.save(ignore_permissions=True)
            frappe.db.commit()
            payment_request.reload()
            if payment_request.payment_url != session.url:
                payment_request.db_set('payment_url', session.url, update_modified=False)
                frappe.db.commit()
        
        # WICHTIG: Wenn es eine Subscription ist, speichere die Stripe Subscription ID in der Payment Request
        # (wird nach erfolgreichem Payment verfügbar sein)
        if mode == 'subscription' and session.get('subscription'):
            # Speichere Stripe Subscription ID in einem Custom Field oder in der Payment Request
            frappe.log_error(f"Stripe Subscription ID für Session: {session.get('subscription')}", "DEBUG: stripe_checkout")
        
        return session.url
        
    except Exception as e:
        frappe.log_error(
            f"create_stripe_checkout_session {getattr(payment_request, 'name', '?')}: {str(e)}\n{frappe.get_traceback()}",
            "stripe_checkout",
        )
        return None


def get_payment_link_url(payment_request_name):
    """
    Gibt die dauerhafte Zahlungs-URL zurück. Dieser Link leitet bei jedem Klick
    auf eine frische Stripe Checkout Session weiter (gültig 24h), sodass der
    Link in E-Mail/Rechnung nicht nach 24 Stunden abläuft.
    """
    base = frappe.utils.get_url()
    from urllib.parse import quote
    return f"{base}/api/method/enjo_party.enjo_party.utils.stripe_checkout.redirect_to_stripe_checkout?payment_request_name={quote(str(payment_request_name))}"


@frappe.whitelist(allow_guest=True)
def redirect_to_stripe_checkout(payment_request_name):
    """
    Erstellt bei jedem Aufruf eine neue Stripe Checkout Session und leitet
    dorthin weiter. So bleibt der Link in E-Mails/Rechnungen dauerhaft nutzbar
    (Stripe-Sessions laufen nach 24h ab, dieser Link nicht).
    """
    try:
        if not payment_request_name:
            frappe.respond_as_web_page(
                _("Ungültiger Link"),
                _("Zahlungslink ist ungültig."),
                indicator_color="red",
                http_status_code=400,
            )
            return
        if not frappe.db.exists("Payment Request", payment_request_name):
            frappe.respond_as_web_page(
                _("Link ungültig"),
                _("Zahlungsanfrage wurde nicht gefunden."),
                indicator_color="red",
                http_status_code=404,
            )
            return
        frappe.set_user("Administrator")
        payment_request = frappe.get_doc("Payment Request", payment_request_name)
        if payment_request.status == "Paid":
            redirect_url = frappe.utils.get_url()
            frappe.redirect(redirect_url)
            return
        # Stripe braucht oft customer_email – falls leer, aus Kunde nachladen
        if not payment_request.email_to and getattr(payment_request, "party_type", None) == "Customer" and payment_request.party:
            customer_email = frappe.db.get_value("Customer", payment_request.party, "email_id")
            if customer_email:
                payment_request.email_to = customer_email
        checkout_url = create_stripe_checkout_session(payment_request)
        if checkout_url:
            frappe.redirect(checkout_url)
        else:
            frappe.respond_as_web_page(
                _("Zahlungslink konnte nicht erstellt werden"),
                _("Bitte versuche es später erneut oder kontaktiere uns."),
                indicator_color="red",
                http_status_code=500,
            )
    except frappe.Redirect:
        raise  # frappe.redirect() wirft diese Exception für die Weiterleitung – nicht als Fehler behandeln
    except Exception as e:
        frappe.log_error(f"redirect_to_stripe_checkout: {type(e).__name__}: {str(e)}\n{frappe.get_traceback()}", "stripe_checkout")
        frappe.respond_as_web_page(
            _("Fehler"),
            _("Zahlungslink konnte nicht geladen werden."),
            indicator_color="red",
            http_status_code=500,
        )


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
        frappe.log_error(f"get_stripe_checkout_url: {str(e)[:200]}", "stripe_checkout")
        frappe.throw(_("Fehler beim Generieren des Payment Links"))

