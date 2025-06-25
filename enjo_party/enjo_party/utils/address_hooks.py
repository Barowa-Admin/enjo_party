import frappe

def copy_email_from_customer(doc, method):
    """
    Kopiert automatisch email_id vom verknüpften Customer zur Address.
    Wird aufgerufen bevor eine neue Address gespeichert wird.
    """
    # Nur wenn Address noch keine email_id hat
    if doc.email_id:
        return
    
    # Durch alle Links gehen und nach Customer suchen
    for link in doc.links:
        if link.link_doctype == "Customer" and link.link_name:
            try:
                # Customer laden
                customer = frappe.get_doc("Customer", link.link_name)
                
                # Wenn Customer eine email_id hat, übertragen
                if customer.email_id:
                    doc.email_id = customer.email_id
                    frappe.logger().info(f"E-Mail automatisch von Customer {customer.name} an Address übertragen: {customer.email_id}")
                    break
                    
            except Exception as e:
                frappe.logger().error(f"Fehler beim Kopieren der E-Mail vom Customer {link.link_name}: {str(e)}")
                continue