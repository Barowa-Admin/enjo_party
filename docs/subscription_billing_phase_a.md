# Abo-Abrechnung Phase A (Doppel-Rechnungen verhindern)

## Technik

- Zentrale Abrechnung: `process_subscription_billing_safe()` in `subscription_hooks.py`
- Täglicher Job: `subscription_scheduler.process_due_subscriptions`
- Abo-Rechnungs-Mails nur über `subscription_hooks` (nicht `after_save_sales_invoice`)

## Fehlerprotokoll filtern

| Titel | Bedeutung |
|-------|-----------|
| `INFO: subscription_billing_processed` | Eine Rechnung wurde erzeugt |
| `INFO: subscription_billing_skipped` | Bewusst übersprungen (bereits Rechnung / Abo fehlt) |
| `WARNING: subscription_billing_duplicate_prevented` | Zweiter paralleler Lauf blockiert |
| `INFO: subscription_so_invoice_exists` | SO-Fulfillment ohne zweite SI |

## Staging-Tests

1. Test-Abo (ohne Stripe), Fälligkeit heute.
2. Bench-Konsole: `process_due_subscriptions()` zweimal → maximal eine neue SI.
3. SI submit → keine Standard-Mail „Rechnung“ bei gesetztem Feld `subscription`.
4. Normale Sales Order ohne Abo → Rechnungs-Mail wie bisher.

## Produktions-Checkliste (einmalig nach Deploy)

1. **Scheduled Job Type:** Nur ein aktiver Job für `process_due_subscriptions` (kein zweiter ERPNext-Subscription-Job parallel).
2. **Scheduler:** Nur ein `bench schedule`-Prozess / kein doppelter Cron auf zwei Servern.
3. **System Settings:** `custom_disable_invoice_emails` betrifft nur Nicht-Abo-Rechnungen; Abo-Mails laufen über Payment Request / Informationsmail.
4. **Abonnementeinstellungen:** Pause-Schalter — siehe [subscription_billing_pause.md](subscription_billing_pause.md).

## Nächster Monatslauf

Am 1. des Folgemonats Fehlerprotokoll auf `subscription_billing_*` prüfen: kein zweites SI pro Abo und Periode.
