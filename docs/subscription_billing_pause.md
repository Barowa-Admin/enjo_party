# Abo-Automatismus pausieren

## Wo

**Buchhaltung → Abonnementeinstellungen** (`Subscription Settings`)

Checkbox: **Automatische Abo-Abrechnung pausieren**

## Was pausiert wird

| Bereich | Verhalten bei Pause |
|---------|---------------------|
| Täglicher Scheduler (`process_due_subscriptions`) | Kein Lauf, Log `INFO: subscription_automation_paused` |
| Auto-Hook beim Abo-Speichern (`force_subscription_update`) | Keine neue Rechnung |
| Catch-up (System Console) | Abbruch mit Meldung „Abo-Automatismus pausiert“ |
| ERPNext-Job `create_subscription_process` | Übersprungen |
| Abo-Kundenmails | Kein Versand (Informationsmail, Payment-Request-Mail) |

## Was weiter funktioniert

- Manuelle Rechnungen anlegen und buchen
- Abos bearbeiten, kündigen (Stripe-Kündigung beim Setzen von „cancel at period end“)
- Zahlungseingänge, Retouren, Overdue-Status
- Normale (Nicht-Abo-) Rechnungs-Mails — gesteuert über System Settings

## Zusätzlicher Schalter

**System Settings → Abo-E-Mails deaktivieren** blockiert nur Mails (ohne Pause der Abrechnung).  
Bei aktivierter Pause in den Abonnementeinstellungen sind Abo-Mails ohnehin aus.

## Fehlerprotokoll

| Titel | Bedeutung |
|-------|-----------|
| `INFO: subscription_automation_paused` | Pause aktiv, automatischer Lauf übersprungen |
| `INFO: subscription_billing_skipped` + `reason=automation_paused` | Einzelnes Abo wegen Pause nicht abgerechnet |
| `INFO: subscription_email_disabled` | Abo-Mail wegen Pause oder System Settings |

## Deploy

1. `bench migrate` (Custom Field)
2. Bench/App neu laden
3. Pause testweise aktivieren → Scheduler in Konsole sollte `message: paused` liefern
4. Pause wieder deaktivieren vor regulärem Monatslauf

## Technik

- Hilfsfunktion: `subscription_settings_helper.is_subscription_automation_paused()`
- Feld: `Subscription Settings.custom_pause_automatic_subscription_billing`
