#!/usr/bin/env python3
"""Debug Script für Party Status"""

import frappe
from frappe.utils import flt

def debug_party_status(party_name):
    """Zeigt alle Details für eine Party"""
    from enjo_party.enjo_party.utils.party_status import calculate_party_status, update_party_status
    
    # Party Info
    party = frappe.get_doc("Party", party_name)
    print(f"\n=== Party {party_name} ===")
    print(f"Aktueller Status: {party.status}")
    print(f"Docstatus: {party.docstatus}")
    
    # Sales Orders
    print(f"\n--- Sales Orders ---")
    sales_orders = frappe.get_all(
        "Sales Order",
        filters={
            "custom_party_reference": party_name,
            "docstatus": 1
        },
        fields=["name", "per_delivered", "per_billed", "status", "delivery_status"]
    )
    
    for so in sales_orders:
        print(f"{so.name}: per_delivered={so.per_delivered}%, per_billed={so.per_billed}%, status={so.status}")
    
    all_delivered = all(flt(so.per_delivered) >= 100 for so in sales_orders)
    print(f"\nAlle ausgeliefert (per_delivered=100)? {all_delivered}")
    
    # Invoices
    print(f"\n--- Sales Invoices ---")
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_party_reference": party_name,
            "docstatus": 1
        },
        fields=["name", "outstanding_amount", "grand_total", "due_date"]
    )
    
    for inv in invoices:
        paid = "✓ BEZAHLT" if flt(inv.outstanding_amount) <= 0.01 else f"✗ OFFEN ({inv.outstanding_amount}€)"
        print(f"{inv.name}: {paid}, Total: {inv.grand_total}€")
    
    all_paid = all(flt(inv.outstanding_amount) <= 0.01 for inv in invoices) if invoices else True
    print(f"\nAlle bezahlt (outstanding_amount=0)? {all_paid}")
    
    # Berechne Status
    print(f"\n--- Status-Berechnung ---")
    calculated_status = calculate_party_status(party_name)
    print(f"Berechneter Status: {calculated_status}")
    
    # Versuche Update
    print(f"\n--- Update-Versuch ---")
    try:
        result = update_party_status(party_name)
        print(f"Update-Ergebnis: {result}")
        
        # Prüfe neuen Status
        new_status = frappe.db.get_value("Party", party_name, "status")
        print(f"Status nach Update: {new_status}")
    except Exception as e:
        print(f"FEHLER beim Update: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    # Teste P260530 (die Party die der User gerade offen hat)
    debug_party_status("P260530")
