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
        
        # Erstelle Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card', 'sepa_debit'],  # Nur aktivierte Zahlungsmethoden
            line_items=[{
                'price_data': {
                    'currency': payment_request.currency.lower(),
                    'product_data': {
                        'name': f'Rechnung {payment_request.reference_name}',
                        'description': payment_request.message or f'Zahlung für {payment_request.reference_name}',
                    },
                    'unit_amount': int(payment_request.grand_total * 100),  # Betrag in Cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{redirect_url}?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=redirect_url,
            customer_email=payment_request.email_to,
            metadata={
                'payment_request': payment_request.name,
                'reference_doctype': payment_request.reference_doctype,
                'reference_name': payment_request.reference_name,
            }
        )
        
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

