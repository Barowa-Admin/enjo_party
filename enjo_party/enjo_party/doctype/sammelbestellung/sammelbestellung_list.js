// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Sammelbestellung'] = {
    refresh: function(listview) {
        // CSS für bessere Formatierung der Listenansicht - wie bei Party
        function addListFormattingCSS() {
            if (document.getElementById('sammelbestellung-list-css')) {
                return;
            }
            
            let css = `
                /* Fix für Sammelbestellung Listenansicht - Abstand links wie bei Party */
                .list-container .list-row-head {
                    padding-left: 15px !important;
                    margin-left: 0 !important;
                }
                
                /* Alle Header-Spalten */
                .list-container .list-row-head .list-row-col {
                    padding-left: 8px !important;
                    margin-left: 0 !important;
                }
                
                /* Erste Spalte extra Abstand */
                .list-container .list-row-head .list-row-col:first-child {
                    padding-left: 15px !important;
                }
                
                /* Alternative Selektoren für verschiedene ERPNext Versionen */
                .list-view .list-row-head {
                    padding-left: 15px !important;
                }
                
                .list-view .list-row-head .list-row-col {
                    padding-left: 8px !important;
                }
                
                .list-view .list-row-head .list-row-col:first-child {
                    padding-left: 15px !important;
                }
                
                /* Noch mehr alternative Selektoren */
                .list-container .list-row-head,
                .list-view .list-row-head,
                .list-row-head {
                    padding-left: 15px !important;
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
        
        // JavaScript Fix für Header-Formatierung - direkter Ansatz
        function fixHeaderFormatting() {
            // Finde alle Header-Zeilen und setze Abstand
            $('.list-row-head').each(function() {
                $(this).css('padding-left', '15px');
            });
            
            // Finde alle Header-Spalten und setze Abstand
            $('.list-row-head .list-row-col').each(function() {
                $(this).css('padding-left', '8px');
            });
            
            // Erste Spalte extra Abstand
            $('.list-row-head .list-row-col:first-child').each(function() {
                $(this).css('padding-left', '15px');
            });
        }
        
        // Formatierung sofort und nach Verzögerung anwenden
        fixHeaderFormatting();
        setTimeout(fixHeaderFormatting, 100);
        setTimeout(fixHeaderFormatting, 500);
        setTimeout(fixHeaderFormatting, 1000);
        
        // Titel-Anpassungen
        function changeTitleToSammelbestellung() {
            if (document.title.includes('Sammelbestellung')) {
                // Bereits korrekt
            }
            
            $('.breadcrumb a:contains("Sammelbestellung")').text('Sammelbestellung');
            $('.breadcrumb-item:contains("Sammelbestellung")').each(function() {
                $(this).text($(this).text());
            });
            $('nav[aria-label="breadcrumb"] a:contains("Sammelbestellung")').text('Sammelbestellung');
            
            $('.page-title:contains("Sammelbestellung")').each(function() {
                $(this).text($(this).text());
            });
            $('h1:contains("Sammelbestellung")').each(function() {
                $(this).text($(this).text());
            });
            
            $('.navbar a:contains("Sammelbestellung")').text('Sammelbestellung');
            
            $('.list-row-head:contains("Sammelbestellung")').each(function() {
                $(this).text($(this).text());
            });
            $('.page-head .title-text:contains("Sammelbestellung")').each(function() {
                $(this).text($(this).text());
            });
            
            $('button').each(function() {
                let text = $(this).text().trim();
                if (text.includes('Sammelbestellung') || text.includes('Hinzufügen')) {
                    if (text === 'Hinzufügen Sammelbestellung' || text === 'Sammelbestellung hinzufügen') {
                        $(this).text('Sammelbestellung hinzufügen');
                    }
                }
            });
            
            $('a').each(function() {
                let text = $(this).text().trim();
                if (text.includes('Sammelbestellung') || text.includes('Hinzufügen')) {
                    if (text === 'Hinzufügen Sammelbestellung' || text === 'Sammelbestellung hinzufügen') {
                        $(this).text('Sammelbestellung hinzufügen');
                    }
                }
            });
            
            $('.list-row-col:contains("Name der Sammelbestellung")').each(function() {
                $(this).text($(this).text());
            });
            $('.column-header:contains("Name der Sammelbestellung")').each(function() {
                $(this).text($(this).text());
            });
        }
        
        setTimeout(changeTitleToSammelbestellung, 100);
        setTimeout(changeTitleToSammelbestellung, 500);
        setTimeout(changeTitleToSammelbestellung, 1000);
    },
    
    onload: function(listview) {
        // Massenaktion zum Abbrechen
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
                                
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        }, true);
    }
};

