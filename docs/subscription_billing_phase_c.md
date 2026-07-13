# Abo-Abrechnung Phase C (Perioden-Deadlock, Retouren, Betriebs-Klarheit)

## Was wurde gelöst

1. **Perioden-Deadlock:** Bezahlte Perioden-SI blockierte den Scheduler dauerhaft. Jetzt: settled → Periode vorrücken (`current_invoice_end + 1`), fehlende fällige SI → `process()`, unbezahlte SI → warten.
2. **Retoure / Overdue:** Neue Retouren setzen `update_outstanding_for_self=0` wenn möglich und verrechnen per `reconcile_dr_cr_note`, falls Original-Outstanding bleibt.
3. **Betriebs-Klarheit:** Zweites Active-Abo pro Kunde wird blockiert; SI ohne `subscription` wird bei genau einem Active-Abo verknüpft; Cancelled setzt `custom_payment_status=Beendet`.

## Technik

| Bereich | Datei / Funktion |
|--------|-------------------|
| Billing | `process_subscription_billing_safe()` in `subscription_hooks.py` |
| Scheduler | `subscription_scheduler.process_due_subscriptions` (kein SI-Vorfilter mehr) |
| Retoure | `sales_invoice_return.py` |
| Catch-up | `subscription_catchup.py` |

### Fehlerprotokoll

| Titel | Bedeutung |
|-------|-----------|
| `INFO: subscription_billing_processed` | Neue SI erzeugt |
| `INFO: subscription_billing_advanced` | Periode nach settled SI vorgerückt |
| `INFO: subscription_billing_skipped` | Skip mit Reason (`unpaid_invoice`, `draft_invoice`, …) |
| `INFO: sales_invoice_return_reconciled` | Retoure gegen Original verrechnet |

## Nach Deploy

1. App deployen / Worker neu starten (Hooks laden).
2. Catch-up in **System Console** (als System Manager):

```python
# 1) Deadlock-Abos vorrücken / fällige SI erzeugen
frappe.call("enjo_party.enjo_party.utils.subscription_catchup.advance_settled_subscription_periods", limit=200)

# 2) Bekannte Fälle Ildiko + Marie + Cancelled-Status
frappe.call("enjo_party.enjo_party.utils.subscription_catchup.catchup_phase_c_known_cases")

# 3) Altlasten Retoure ↔ Outstanding (~44)
frappe.call("enjo_party.enjo_party.utils.sales_invoice_return.repair_unallocated_returns", limit=100)
```

3. Spot-Checks:
   - Ildiko `ACC-SUB-2026-00027`: neue SI für aktuelle Periode bzw. Periode korrekt
   - Marie `ACC-SINV-2026-00531`: Feld `subscription` = `ACC-SUB-2026-00014`
   - Ein Overdue+Return-Paar: Original `outstanding_amount` ≈ 0
   - Janina: zwei Active-Abos bleiben (Büro entscheidet); neue zweiten Active-Abos werden blockiert

## Override Mehrfach-Abo

Bestehende doppelte Active-Abos (Altlast) können weiter gespeichert werden. Blockiert werden nur **neue** Active-Abos bzw. Reaktivierung, solange bereits ein Active-Abo existiert.

Nur für Migration / Catch-up:

```python
frappe.flags.ignore_multiple_active_subscriptions = True
# … Speichern …
frappe.flags.ignore_multiple_active_subscriptions = False
```

## Mail-Entwurf an Esther (Büro)

Betreff: Abo-Abrechnung – Ursachen gefunden und behoben

Hallo Esther,

wir haben die von Dir gemeldeten Abo-Probleme strukturell behoben:

1. **Bezahlt, aber keine neue Abo-Rechnung:** Nach Zahlung blieb die Abrechnungsperiode hängen – der Automat hat deshalb keine Folgerechnung erzeugt. Das ist korrigiert; bestehende hängende Abos werden nachgezogen.
2. **Retoure, aber Rechnung weiter „überfällig“:** Gutschriften werden künftig gegen die Originalrechnung verrechnet, sodass der offene Betrag verschwindet. Alte Fälle bereinigen wir einmalig.
3. **Mehrere Abos / manuelle Rechnungen:** Es kann pro Kundin nur noch ein aktives Abo geben. Manuelle Rechnungen werden bei genau einem aktiven Abo automatisch verknüpft. Beendete Abos zeigen nicht mehr irreführende Zahlungsstatus.

Bitte prüft kurz:
- Kundin Janina Frömmigen: aktuell noch zwei aktive Abos – welches soll aktiv bleiben?
- Kundin Marie Eckert: Rechnungsverknüpfung nachziehen (technisch vorbereitet).

Bei Auffälligkeiten einfach melden.

Viele Grüße
