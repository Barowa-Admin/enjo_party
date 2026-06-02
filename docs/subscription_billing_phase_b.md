# Abo-Rechnungsmail Phase B (BCC Vertriebspartnerin)

## Technik

- Ein Versandpfad: `_send_subscription_customer_email()` in `subscription_hooks.py`
- BCC aus `custom_partnerin` (Link DocType laut Meta, Standard: Sales Partner / UI „Vertriebspartner“)
- E-Mail der Partnerin: Kontakt (primäre E-Mail) → Partner-Felder → User-Fallback
- Vor dem Buchen: `sync_subscription_partner_to_invoice` übernimmt Partnerin vom Abo auf die Rechnung (Entwurf)

## Nach Deploy

1. `bench migrate` (Custom Field `Sales Invoice-custom_partnerin` aus Fixtures)
2. `bench restart`

## Fehlerprotokoll filtern

| Titel | Bedeutung |
|-------|-----------|
| `ABO-Mail Partner-BCC` | Pro Versand: Empfänger, `BCC=…`, `SUB.custom_partnerin`, `SI.custom_partnerin` |
| `INFO: subscription_email_disabled` | System Settings: Abo-E-Mails aus |

Mögliche BCC-Gründe im Log (`Kein BCC: …`):

- `kein_partner` – kein Sales Partner ermittelt
- `kein_kontakt` – Partner ohne verknüpften Kontakt
- `keine_email_am_kontakt` – Kontakt ohne nutzbare E-Mail
- `user_fallback_ohne_email` – nur User-Link, aber User ohne E-Mail

## Prüfung im Desk

1. Test-Abo mit gesetzter **Partnerin** und Kontakt mit **primärer E-Mail**
2. Rechnung auslösen (Scheduler oder Test)
3. **Email Queue**: Feld `recipients` = Kunde, Feld `bcc` = Partnerin-E-Mail
4. Partnerin bestätigt Empfang im Postfach

## Regression

- Abo ohne Partnerin: eine Kundenmail, Log `BCC=KEINE`, `kein_partner`
- Rechnung ohne `subscription`: unverändert (Phase A: kein Standard-Template-Hook für Abos)

## Siehe auch

- [subscription_billing_phase_a.md](subscription_billing_phase_a.md) – Doppel-Rechnungen verhindern
