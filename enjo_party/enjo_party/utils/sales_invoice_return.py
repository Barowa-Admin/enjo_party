# Copyright (c) 2026, Elia and contributors
# For license information, please see license.txt

"""
Verrechnung von Retouren/Gutschriften gegen die Original-Sales-Invoice.

Wenn ERPNext `update_outstanding_for_self=1` setzt (z. B. weil Gutschrift > Original-Outstanding),
bleibt die Original-SI mit outstanding > 0 und Status Overdue. Diese Hilfen stellen die
Verrechnung her (Payment Reconciliation / Journal Entry).
"""

import frappe
from frappe.utils import flt


def _log_return(title, message=None):
    t = (title or "Error")[:140]
    frappe.log_error(title=t, message=frappe.as_unicode(message or ""))


def ensure_return_clears_original_outstanding(doc, method=None):
    """
    before_submit: Bei Retoure mit return_against Outstanding der Original-SI aktualisieren,
    sofern die Gutschrift den offenen Betrag nicht übersteigt.
    """
    if not getattr(doc, "is_return", 0) or not getattr(doc, "return_against", None):
        return
    if getattr(doc, "is_pos", 0):
        return

    original_outstanding = flt(
        frappe.db.get_value("Sales Invoice", doc.return_against, "outstanding_amount") or 0
    )
    return_total = abs(flt(doc.rounded_total) or flt(doc.grand_total) or 0)

    # Nur wenn Gutschrift den offenen Betrag abdeckt/unterschreitet: gegen Original buchen
    if return_total <= original_outstanding + 0.01:
        doc.update_outstanding_for_self = 0


def allocate_return_against_original(doc, method=None):
    """
    on_submit: Falls Original nach Retoure noch Outstanding hat, per reconcile_dr_cr_note verrechnen.
    """
    if not getattr(doc, "is_return", 0) or not getattr(doc, "return_against", None):
        return
    if doc.docstatus != 1:
        return

    try:
        result = reconcile_return_to_original(doc.name)
        if result.get("reconciled"):
            _log_return(
                "INFO: sales_invoice_return_reconciled",
                f"return={doc.name} against={doc.return_against} "
                f"allocated={result.get('allocated_amount')}",
            )
            if doc.subscription:
                from enjo_party.enjo_party.utils.subscription_status_indicator import (
                    update_subscription_payment_status,
                )

                update_subscription_payment_status(doc.subscription)
            original_sub = frappe.db.get_value("Sales Invoice", doc.return_against, "subscription")
            if original_sub and original_sub != doc.subscription:
                from enjo_party.enjo_party.utils.subscription_status_indicator import (
                    update_subscription_payment_status,
                )

                update_subscription_payment_status(original_sub)
    except Exception as e:
        _log_return(
            "ERROR: sales_invoice_return_reconcile",
            f"return={doc.name}: {str(e)}\n{frappe.get_traceback()}",
        )


def reconcile_return_to_original(return_invoice_name):
    """
    Verrechnet eine gebuchte Retoure gegen ihre Original-SI, falls nötig.
    Returns dict: reconciled, allocated_amount, reason, original, return_invoice
    """
    ret = frappe.get_doc("Sales Invoice", return_invoice_name)
    if not ret.is_return or not ret.return_against or ret.docstatus != 1:
        return {
            "reconciled": False,
            "reason": "not_a_submitted_return",
            "return_invoice": return_invoice_name,
        }

    original_outstanding = flt(
        frappe.db.get_value("Sales Invoice", ret.return_against, "outstanding_amount") or 0
    )
    if original_outstanding <= 0.01:
        return {
            "reconciled": False,
            "reason": "original_already_cleared",
            "return_invoice": return_invoice_name,
            "original": ret.return_against,
            "allocated_amount": 0,
        }

    # Offener Betrag der Gutschrift (negativ als outstanding, positiv als abs)
    return_outstanding = abs(flt(ret.outstanding_amount))
    if return_outstanding <= 0.01:
        # Kein eigener Outstanding auf der CN → GL hat vermutlich schon gegen Original gebucht,
        # aber Original-Outstanding stimmt nicht. Neu berechnen versuchen.
        from erpnext.accounts.utils import update_voucher_outstanding

        try:
            update_voucher_outstanding(
                "Sales Invoice",
                ret.return_against,
                ret.debit_to,
                "Customer",
                ret.customer,
            )
        except Exception:
            pass
        original_outstanding = flt(
            frappe.db.get_value("Sales Invoice", ret.return_against, "outstanding_amount") or 0
        )
        if original_outstanding <= 0.01:
            return {
                "reconciled": False,
                "reason": "original_cleared_after_refresh",
                "return_invoice": return_invoice_name,
                "original": ret.return_against,
                "allocated_amount": 0,
            }
        # Ohne CN-Outstanding keine JE-Verrechnung möglich
        return {
            "reconciled": False,
            "reason": "return_has_no_outstanding",
            "return_invoice": return_invoice_name,
            "original": ret.return_against,
            "original_outstanding": original_outstanding,
        }

    allocated = min(original_outstanding, return_outstanding, abs(flt(ret.grand_total)))
    if allocated <= 0.01:
        return {
            "reconciled": False,
            "reason": "nothing_to_allocate",
            "return_invoice": return_invoice_name,
            "original": ret.return_against,
        }

    from erpnext.accounts.doctype.payment_reconciliation.payment_reconciliation import (
        reconcile_dr_cr_note,
    )

    note = frappe._dict(
        {
            "voucher_type": "Sales Invoice",
            "voucher_no": ret.name,
            "against_voucher_type": "Sales Invoice",
            "against_voucher": ret.return_against,
            "account": ret.debit_to,
            "party_type": "Customer",
            "party": ret.customer,
            "dr_or_cr": "credit_in_account_currency",
            "unadjusted_amount": return_outstanding,
            "unreconciled_amount": return_outstanding,
            "allocated_amount": allocated,
            "difference_amount": 0,
            "currency": ret.currency,
            "cost_center": ret.cost_center,
            "exchange_rate": ret.conversion_rate or 1,
        }
    )
    reconcile_dr_cr_note([note], ret.company)
    frappe.db.commit()

    return {
        "reconciled": True,
        "reason": "reconciled",
        "return_invoice": return_invoice_name,
        "original": ret.return_against,
        "allocated_amount": allocated,
    }


@frappe.whitelist()
def repair_unallocated_returns(limit=100):
    """
    Einmalige Altlasten-Bereinigung: gebuchte Retouren, deren Original noch Outstanding > 0 hat.
    Nur System Manager.
    """
    frappe.only_for("System Manager")
    limit = int(limit or 100)

    rows = frappe.db.sql(
        """
        SELECT
            r.name AS return_name,
            r.return_against AS original_name,
            o.outstanding_amount AS original_outstanding
        FROM `tabSales Invoice` r
        INNER JOIN `tabSales Invoice` o ON o.name = r.return_against
        WHERE r.docstatus = 1
          AND r.is_return = 1
          AND r.return_against IS NOT NULL
          AND r.return_against != ''
          AND o.docstatus = 1
          AND o.outstanding_amount > 0.01
        ORDER BY r.creation ASC
        LIMIT %(limit)s
        """,
        {"limit": limit},
        as_dict=True,
    )

    results = []
    reconciled = 0
    failed = 0
    skipped = 0

    for row in rows:
        try:
            outcome = reconcile_return_to_original(row.return_name)
            results.append(outcome)
            if outcome.get("reconciled"):
                reconciled += 1
            else:
                skipped += 1
        except Exception as e:
            failed += 1
            results.append(
                {
                    "reconciled": False,
                    "reason": f"error: {str(e)}",
                    "return_invoice": row.return_name,
                    "original": row.original_name,
                }
            )
            _log_return(
                "ERROR: repair_unallocated_returns",
                f"{row.return_name}: {str(e)}\n{frappe.get_traceback()}",
            )

    return {
        "candidates": len(rows),
        "reconciled": reconciled,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
