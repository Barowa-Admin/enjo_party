// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Party'] = {
    // Status-Farben definieren
    get_indicator: function(doc) {
        if (doc.status === "Gäste") {
            return [__("Gäste"), "orange", "status,=,Gäste"];
        } else if (doc.status === "Produkte") {
            return [__("Produkte"), "yellow", "status,=,Produkte"];
        } else if (doc.status === "Geschenke") {
            return [__("Geschenke"), "blue", "status,=,Geschenke"];
        } else if (doc.status === "Gebucht") {
            return [__("Gebucht"), "blue", "status,=,Gebucht"];
        } else if (doc.status === "Abgeschlossen") {
            return [__("Abgeschlossen"), "green", "status,=,Abgeschlossen"];
        }
        return [__(doc.status), "gray", "status,=," + doc.status];
    },
    
    
    refresh: function(listview) {
        // Wir fügen keine direkte Aktion hinzu, sondern verwenden den onload-Hook
        
        // CSS für schmalere erste Spalte (ID) hinzufügen
        function addColumnWidthCSS() {
            if (document.getElementById('party-list-column-width-css')) {
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
                
                /* Header erste Spalte */
                .list-container .list-row-head .list-row-col:first-child,
                .list-view .list-row-head .list-row-col:first-child {
                    max-width: 120px !important;
                    min-width: 100px !important;
                    width: 120px !important;
                }
                
                /* Gastgeber-Spalte schmaler machen */
                .list-container .list-row .list-row-col[data-fieldname="gastgeberin"],
                .list-view .list-row .list-row-col[data-fieldname="gastgeberin"] {
                    max-width: 180px !important;
                    min-width: 150px !important;
                    width: 180px !important;
                }
                
                .list-container .list-row-head .list-row-col[data-fieldname="gastgeberin"],
                .list-view .list-row-head .list-row-col[data-fieldname="gastgeberin"] {
                    max-width: 180px !important;
                    min-width: 150px !important;
                    width: 180px !important;
                }
                
                /* Status-Spalte schmaler machen */
                .list-container .list-row .list-row-col[data-fieldname="status"],
                .list-view .list-row .list-row-col[data-fieldname="status"] {
                    max-width: 120px !important;
                    min-width: 100px !important;
                    width: 120px !important;
                }
                
                .list-container .list-row-head .list-row-col[data-fieldname="status"],
                .list-view .list-row-head .list-row-col[data-fieldname="status"] {
                    max-width: 120px !important;
                    min-width: 100px !important;
                    width: 120px !important;
                }
                
                /* Datum-Spalte schmaler machen */
                .list-container .list-row .list-row-col[data-fieldname="party_date"],
                .list-view .list-row .list-row-col[data-fieldname="party_date"] {
                    max-width: 120px !important;
                    min-width: 100px !important;
                    width: 120px !important;
                }
                
                .list-container .list-row-head .list-row-col[data-fieldname="party_date"],
                .list-view .list-row-head .list-row-col[data-fieldname="party_date"] {
                    max-width: 120px !important;
                    min-width: 100px !important;
                    width: 120px !important;
                }
            `;
            
            let style = document.createElement('style');
            style.id = 'party-list-column-width-css';
            style.type = 'text/css';
            style.innerHTML = css;
            document.head.appendChild(style);
        }
        
        addColumnWidthCSS();
        
        // JavaScript Fix für Spaltenbreiten - direkter Ansatz
        function fixColumnWidths() {
            // Erste Spalte (ID) schmaler machen
            $('.list-row .list-row-col:first-child').each(function() {
                $(this).css({
                    'max-width': '120px',
                    'min-width': '100px',
                    'width': '120px'
                });
            });
            
            $('.list-row-head .list-row-col:first-child').each(function() {
                $(this).css({
                    'max-width': '120px',
                    'min-width': '100px',
                    'width': '120px'
                });
            });
            
            // Gastgeber-Spalte schmaler machen
            $('.list-row .list-row-col[data-fieldname="gastgeberin"]').each(function() {
                $(this).css({
                    'max-width': '180px',
                    'min-width': '150px',
                    'width': '180px'
                });
            });
            
            $('.list-row-head .list-row-col[data-fieldname="gastgeberin"]').each(function() {
                $(this).css({
                    'max-width': '180px',
                    'min-width': '150px',
                    'width': '180px'
                });
            });
            
            // Status-Spalte schmaler machen
            $('.list-row .list-row-col[data-fieldname="status"]').each(function() {
                $(this).css({
                    'max-width': '120px',
                    'min-width': '100px',
                    'width': '120px'
                });
            });
            
            $('.list-row-head .list-row-col[data-fieldname="status"]').each(function() {
                $(this).css({
                    'max-width': '120px',
                    'min-width': '100px',
                    'width': '120px'
                });
            });
            
            // Datum-Spalte schmaler machen
            $('.list-row .list-row-col[data-fieldname="party_date"]').each(function() {
                $(this).css({
                    'max-width': '120px',
                    'min-width': '100px',
                    'width': '120px'
                });
            });
            
            $('.list-row-head .list-row-col[data-fieldname="party_date"]').each(function() {
                $(this).css({
                    'max-width': '120px',
                    'min-width': '100px',
                    'width': '120px'
                });
            });
        }
        
        // Formatierung sofort und nach Verzögerung anwenden
        fixColumnWidths();
        setTimeout(fixColumnWidths, 100);
        setTimeout(fixColumnWidths, 500);
        setTimeout(fixColumnWidths, 1000);
        
        // Gastgeber-Namen statt ID anzeigen
        function updateGastgeberNames() {
            $('.list-row').each(function() {
                const $row = $(this);
                const $gastgeberCell = $row.find('.list-row-col[data-fieldname="gastgeberin"]');
                if ($gastgeberCell.length) {
                    const cellText = $gastgeberCell.text().trim();
                    const gastgeberId = $gastgeberCell.attr('data-value') || 
                                       $gastgeberCell.attr('data-id') || 
                                       cellText;
                    
                    // Wenn es nur eine Zahl ist (ID), hole den Namen
                    if (gastgeberId && /^\d+$/.test(gastgeberId.toString())) {
                        frappe.db.get_value('Customer', gastgeberId, 'customer_name', function(r) {
                            if (r && r.customer_name && $gastgeberCell.length) {
                                $gastgeberCell.text(r.customer_name);
                            }
                        });
                    }
                }
            });
        }
        
        setTimeout(updateGastgeberNames, 500);
        setTimeout(updateGastgeberNames, 1500);
        setTimeout(updateGastgeberNames, 2500);
        
        // Titel von "Party" zu "Präsentation" ändern (wie im Formular)
        function changeTitleToPräsentation() {
            // Browser-Tab Titel ändern
            if (document.title.includes('Party')) {
                document.title = document.title.replace(/Party/g, 'Präsentation');
            }
            
            // Verschiedene Breadcrumb-Selektoren versuchen
            $('.breadcrumb a:contains("Party")').text('Präsentation');
            $('.breadcrumb-item:contains("Party")').each(function() {
                $(this).text($(this).text().replace('Party', 'Präsentation'));
            });
            $('nav[aria-label="breadcrumb"] a:contains("Party")').text('Präsentation');
            
            // Page-Header und andere Titel
            $('.page-title:contains("Party")').each(function() {
                $(this).text($(this).text().replace('Party', 'Präsentation'));
            });
            $('h1:contains("Party")').each(function() {
                $(this).text($(this).text().replace('Party', 'Präsentation'));
            });
            
            // Auch im Hauptnavigationsbereich
            $('.navbar a:contains("Party")').text('Präsentation');
            
            // Spezifisch für Listenansicht
            $('.list-row-head:contains("Party")').each(function() {
                $(this).text($(this).text().replace('Party', 'Präsentation'));
            });
            $('.page-head .title-text:contains("Party")').each(function() {
                $(this).text($(this).text().replace('Party', 'Präsentation'));
            });
            
            // ROBUSTE Button-Änderung - alle möglichen Selektoren
            $('button').each(function() {
                let text = $(this).text().trim();
                if (text.includes('Party') || text.includes('Hinzufügen')) {
                    if (text === 'Hinzufügen Party' || text === 'Party hinzufügen' || text === 'Hinzufügen Präsentation') {
                        $(this).text('Präsentation hinzufügen');
                    }
                }
            });
            
            $('a').each(function() {
                let text = $(this).text().trim();
                if (text.includes('Party') || text.includes('Hinzufügen')) {
                    if (text === 'Hinzufügen Party' || text === 'Party hinzufügen' || text === 'Hinzufügen Präsentation') {
                        $(this).text('Präsentation hinzufügen');
                    }
                }
            });
            
            // Alle Elemente mit Party-Text durchgehen
            $('*').contents().filter(function() {
                return this.nodeType === 3 && this.nodeValue.includes('Party');
            }).each(function() {
                this.nodeValue = this.nodeValue.replace('Hinzufügen Party', 'Präsentation hinzufügen');
                this.nodeValue = this.nodeValue.replace('Party hinzufügen', 'Präsentation hinzufügen');
            });
            
            // Spaltenheader "Gastgeberin" zu "Gastgeber" ändern
            $('.list-row-col:contains("Gastgeberin")').each(function() {
                $(this).text($(this).text().replace('Gastgeberin', 'Gastgeber'));
            });
            $('.column-header:contains("Gastgeberin")').each(function() {
                $(this).text($(this).text().replace('Gastgeberin', 'Gastgeber'));
            });
            // Auch "Name der Präsentation" zu "Gastgeber" ändern (falls noch vorhanden)
            $('.list-row-col:contains("Name der Präsentation")').each(function() {
                $(this).text($(this).text().replace('Name der Präsentation', 'Gastgeber'));
            });
            $('.column-header:contains("Name der Präsentation")').each(function() {
                $(this).text($(this).text().replace('Name der Präsentation', 'Gastgeber'));
            });
            $('.list-row-col:contains("Name der Partei")').each(function() {
                $(this).text($(this).text().replace('Name der Partei', 'Gastgeber'));
            });
            $('.column-header:contains("Name der Partei")').each(function() {
                $(this).text($(this).text().replace('Name der Partei', 'Gastgeber'));
            });
        }
        
        // Mehrere Versuche mit verschiedenen Timings
        setTimeout(changeTitleToPräsentation, 100);
        setTimeout(changeTitleToPräsentation, 500);
        setTimeout(changeTitleToPräsentation, 1000);
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