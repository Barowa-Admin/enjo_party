# Rechnungs-E-Mail (Kunde + VP)

## Automatischer Versand

| Rechnungstyp | Auslöser | Pfad |
|---|---|---|
| Normale Rechnung (ohne `subscription`) | `on_submit` | `invoice_email.send_customer_invoice_email` |
| Abo-Rechnung | `on_submit` / Subscription-Hooks | `subscription_hooks` (Payment Request oder Informationsmail) |

- **TO:** Kunde (`contact_email` → `Customer.email_id`)
- **BCC:** Vertriebspartnerin (Kontakt am Sales Partner)
- **Kein CC** an interne Adressen im automatischen Versand
- DATEV-Mails (`uploadmail.datev.de`) blockieren den Kundenversand **nicht**

## Nach Deploy

1. `bench migrate` (falls Custom Fields fehlen)
2. `bench restart`

## Fehlerprotokoll filtern

| Titel | Bedeutung |
|---|---|
| `INFO: invoice_email_sent` | Normale Rechnungsmail versendet |
| `WARNING: invoice_email_no_address` | Keine Kunden-E-Mail |
| `WARNING: invoice_pdf_attachment_failed` | PDF fehlgeschlagen, Mail ggf. ohne Anhang |
| `ABO-Mail Partner-BCC` | Abo-Mail versendet (siehe Phase B) |

## Test

1. Party-Rechnung buchen → Email Queue: Kunde in TO, VP in BCC
2. DATEV-Eintrag darf zusätzlich existieren
3. Zweites Buchen / erneuter Hook → keine zweite Kundenmail

## Siehe auch

- [subscription_billing_phase_b.md](subscription_billing_phase_b.md)
