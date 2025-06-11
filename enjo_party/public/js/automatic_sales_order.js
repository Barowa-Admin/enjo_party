// Automatische Sales Invoice Erstellung für Sales Orders
frappe.ui.form.on('Sales Order', {
    on_submit: function(frm) {
        // Zeige eine kurze Nachricht
        frappe.show_alert({
            message: __('Erstelle automatisch Sales Invoice...'),
            indicator: 'blue'
        });
        
        // Rufe die Server-Funktion auf
        frappe.call({
            method: 'enjo_party.enjo_party.utils.sales_order_hooks.create_invoice_from_sales_order',
            args: {
                sales_order_name: frm.doc.name
            },
            callback: function(response) {
                if (response && response.message) {
                    const result = response.message;
                    
                    if (result.success) {
                        // Erfolg
                        frappe.show_alert({
                            message: __('Sales Invoice {0} wurde automatisch erstellt!', [result.invoice_name]),
                            indicator: 'green'
                        });
                        
                        // Zeige einen Dialog mit Link zur Sales Invoice
                        frappe.msgprint({
                            title: __('Sales Invoice erstellt'),
                            message: __('Sales Invoice <a href="/app/sales-invoice/{0}">{0}</a> wurde automatisch erstellt und eingereicht.', [result.invoice_name]),
                            indicator: 'green'
                        });
                        
                    } else {
                        // Bereits vorhanden oder Fehler
                        if (result.message.includes('existiert bereits')) {
                            frappe.show_alert({
                                message: __('Sales Invoice existiert bereits: {0}', [result.invoice_name]),
                                indicator: 'orange'
                            });
                        } else {
                            // Echter Fehler
                            frappe.show_alert({
                                message: __('Fehler: {0}', [result.message]),
                                indicator: 'red'
                            });
                        }
                    }
                }
            },
            error: function(error) {
                frappe.show_alert({
                    message: __('Fehler bei der automatischen Rechnungserstellung'),
                    indicator: 'red'
                });
                console.error('Auto Invoice Error:', error);
            }
        });
    }
});
