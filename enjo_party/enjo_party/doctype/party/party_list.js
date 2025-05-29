// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Party'] = {
    refresh: function(listview) {
        // Wir fügen keine direkte Aktion hinzu, sondern verwenden den onload-Hook
        
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
            
            // Spaltenheader "Name der Partei" zu "Name der Präsentation"
            $('.list-row-col:contains("Name der Partei")').each(function() {
                $(this).text($(this).text().replace('Name der Partei', 'Name der Präsentation'));
            });
            $('.column-header:contains("Name der Partei")').each(function() {
                $(this).text($(this).text().replace('Name der Partei', 'Name der Präsentation'));
            });
            
            // Hamburger-Menü (Sidebar-Toggle) ausblenden
            $('.sidebar-toggle-btn').hide();
            $('.menu-btn').hide();
            $('.navbar-toggle').hide();
            $('[data-toggle="sidebar"]').hide();
        }
        
        // Sidebar in Listenansicht ausblenden
        function hideSidebar() {
            // Verschiedene Sidebar-Selektoren
            $('.layout-side-section').hide();
            $('.sidebar-section').hide();
            $('.list-sidebar').hide();
            // Hauptinhalt breiter machen
            $('.layout-main-section').css('width', '100%');
            $('.layout-main-section').css('margin-left', '0');
        }
        
        // Mehrere Versuche mit verschiedenen Timings
        setTimeout(changeTitleToPräsentation, 100);
        setTimeout(changeTitleToPräsentation, 500);
        setTimeout(changeTitleToPräsentation, 1000);
        
        setTimeout(hideSidebar, 100);
        setTimeout(hideSidebar, 500);
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