// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Party'] = {
    refresh: function(listview) {
        // Wir fügen keine direkte Aktion hinzu, sondern verwenden den onload-Hook
    },
    
    onload: function(listview) {
        // Definiere benutzerdefinierte Massenaktion
        listview.page.add_actions_menu_item(__('Cancel'), function() {
            // Prüfen, ob Datensätze ausgewählt wurden
            const selected = listview.get_checked_items();
            if (selected.length === 0) {
                frappe.msgprint(__("Bitte wähle mindestens eine Party aus."));
                return;
            }
            
            // Zeige Bestätigungsdialog
            frappe.confirm(
                __(`Möchtest Du ${selected.length} Party(s) wirklich abbrechen?`),
                function() {
                    // Sammle die Namen der ausgewählten Parties
                    const party_names = selected.map(d => d.name).join(",");
                    
                    // Rufe die Python-Funktion auf
                    frappe.call({
                        method: "enjo_party.enjo_party.doctype.party.party.cancel_multiple_parties",
                        args: {
                            parties: party_names
                        },
                        freeze: true,
                        freeze_message: __("Breche Parties ab..."),
                        callback: function(r) {
                            if (r.message) {
                                // Zeige Erfolgsmeldung
                                frappe.msgprint({
                                    title: __("Parties abgebrochen"),
                                    indicator: "green",
                                    message: __(
                                        `${r.message.cancelled} von ${r.message.total} Parties wurden erfolgreich abgebrochen. ${r.message.failed} fehlgeschlagen.`
                                    )
                                });
                                
                                // Aktualisiere die Liste
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        }, true); // true bedeutet, dass dieser Punkt nur bei Auswahl angezeigt wird
    }
}; 