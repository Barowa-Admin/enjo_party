import frappe

def has_app_permission():
    """
    Prüft, ob der aktuelle Nutzer die Berechtigung hat, die Enjo Party App zu verwenden.
    Erlaubt Zugriff für Nutzer mit Sales-Rollen.
    """
    if frappe.session.user == "Administrator":
        return True
    
    user_roles = frappe.get_roles(frappe.session.user)
    
    # Erlaubte Sales-Rollen
    allowed_roles = ["Sales User", "Sales Manager", "Sales Master Manager"]
    
    for role in allowed_roles:
        if role in user_roles:
            return True
    
    return False 