// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Sammelbestellung'] = {
    // Status-Farben definieren
    get_indicator: function(doc) {
        if (doc.status === "Kunden") {
            return [__("Kunden"), "orange", "status,=,Kunden"];
        } else if (doc.status === "Produkte") {
            return [__("Produkte"), "yellow", "status,=,Produkte"];
        } else if (doc.status === "Gebucht") {
            return [__("Gebucht"), "blue", "status,=,Gebucht"];
        } else if (doc.status === "Abgeschlossen") {
            return [__("Abgeschlossen"), "green", "status,=,Abgeschlossen"];
        }
        return [__(doc.status), "gray", "status,=," + doc.status];
    },
    
    refresh: function(listview) {
        try {
            // CSS für bessere Formatierung der Listenansicht - wie bei Party
            function addListFormattingCSS() {
                if (document.getElementById('sammelbestellung-list-css')) {
                    return;
                }
                
                let css = `
                    /* Erste Spalte (ID) schmaler machen */
                    .list-container .list-row .list-row-col:first-child,
                    .list-view .list-row .list-row-col:first-child {
                        max-width: 120px !important;
                        min-width: 100px !important;
                        width: 120px !important;
                    }
                    
                    .list-container .list-row-head .list-row-col:first-child,
                    .list-view .list-row-head .list-row-col:first-child {
                        max-width: 120px !important;
                        min-width: 100px !important;
                        width: 120px !important;
                    }
                `;
                
                let style = document.createElement('style');
                style.id = 'sammelbestellung-list-css';
                style.type = 'text/css';
                style.innerHTML = css;
                document.head.appendChild(style);
            }
            
            // CSS hinzufügen
            addListFormattingCSS();
        } catch (e) {
            console.error('Fehler in refresh callback:', e);
        }
    },
    
    onload: function(listview) {
        try {
            // Massenaktion zum Abbrechen
            if (listview && listview.page && listview.page.add_actions_menu_item) {
                listview.page.add_actions_menu_item(__('Cancel'), function() {
                    const selected = listview.get_checked_items();
                    if (selected.length === 0) {
                        frappe.msgprint(__("Bitte wähle mindestens eine Sammelbestellung aus."));
                        return;
                    }
                    
                    frappe.confirm(
                        __(`Möchtest Du ${selected.length} Sammelbestellung(en) wirklich abbrechen?`),
                        function() {
                            const sammelbestellung_names = selected.map(d => d.name).join(",");
                            
                            frappe.call({
                                method: "enjo_party.enjo_party.doctype.sammelbestellung.sammelbestellung.cancel_multiple_sammelbestellungen",
                                args: {
                                    sammelbestellungen: sammelbestellung_names
                                },
                                freeze: true,
                                freeze_message: __("Breche Sammelbestellungen ab..."),
                                callback: function(r) {
                                    if (r.message) {
                                        frappe.msgprint({
                                            title: __("Sammelbestellungen abgebrochen"),
                                            indicator: "green",
                                            message: __(
                                                `${r.message.cancelled} von ${r.message.total} Sammelbestellungen wurden erfolgreich abgebrochen. ${r.message.failed} fehlgeschlagen.`
                                            )
                                        });
                                        
                                        if (listview && listview.refresh) {
                                            listview.refresh();
                                        }
                                    }
                                }
                            });
                        }
                    );
                }, true);
            }
        } catch (e) {
            console.error('Fehler in onload callback:', e);
        }
    }
};

