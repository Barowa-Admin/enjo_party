// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Subscription'] = {
    add_fields: ['party', 'custom_partnerin', 'status', 'cancel_at_period_end', 'custom_payment_status'],
    
    // Status-Farben definieren
    get_indicator: function(doc) {
        // Beendet (Cancelled oder cancel_at_period_end) - Grau
        if (doc.status === "Cancelled" || doc.cancel_at_period_end === 1) {
            return [__("Beendet"), "gray", "status,=,Cancelled"];
        }
        
        // Prüfe custom_payment_status (wird vom Scheduler gesetzt)
        if (doc.custom_payment_status) {
            // Retourniert - Blau
            if (doc.custom_payment_status === "Retourniert") {
                return [__("Retourniert"), "blue", "custom_payment_status,=,Retourniert"];
            }
            // Überfällig - Rot
            if (doc.custom_payment_status === "Überfällig") {
                return [__("Überfällig"), "red", "custom_payment_status,=,Überfällig"];
            }
            // Unbezahlt - Orange
            if (doc.custom_payment_status === "Unbezahlt") {
                return [__("Unbezahlt"), "orange", "custom_payment_status,=,Unbezahlt"];
            }
            // Bezahlt - Grün
            if (doc.custom_payment_status === "Bezahlt") {
                return [__("Bezahlt"), "green", "custom_payment_status,=,Bezahlt"];
            }
        }
        
        // Fallback auf Standard-Status
        if (doc.status === "Active") {
            return [__("Aktiv"), "green", "status,=,Active"];
        }
        if (doc.status === "Past Due Date") {
            return [__("Überfällig"), "red", "status,=,Past Due Date"];
        }
        if (doc.status === "Unpaid") {
            return [__("Unbezahlt"), "orange", "status,=,Unpaid"];
        }
        
        return [__(doc.status), "gray", "status,=," + doc.status];
    },
    
    onload: function(listview) {
        console.log('[SUBSCRIPTION FILTER] onload called');
        
        // Speichere die letzten gesetzten Werte
        listview._last_party_value = null;
        listview._last_partnerin_value = null;
        listview._is_programmatic_change = false;
        
        // Speichere Referenzen zu den Feldern
        let partyField, partnerinField;
        
        // Party-Filter hinzufügen
        partyField = listview.page.add_field({
            label: 'Kunde',
            fieldtype: 'Link',
            fieldname: 'party',
            options: 'Customer',
            change: function() {
                let party = this.get_value();
                console.log('[SUBSCRIPTION FILTER] Party field changed:', party, 'Is programmatic:', listview._is_programmatic_change);
                
                // Ignoriere wenn programmatisch gesetzt
                if (listview._is_programmatic_change) {
                    console.log('[SUBSCRIPTION FILTER] Ignoring programmatic party change');
                    return;
                }
                
                // Ignoriere wenn Wert sich nicht geändert hat
                if (party === listview._last_party_value) {
                    console.log('[SUBSCRIPTION FILTER] Party value unchanged, ignoring');
                    return;
                }
                
                // Speichere neuen Wert
                listview._last_party_value = party;
                
                // Verhindere Endlosschleife durch Debouncing
                clearTimeout(listview._party_timeout);
                listview._party_timeout = setTimeout(() => {
                    console.log('[SUBSCRIPTION FILTER] Party timeout fired, setting filter:', party);
                    if (party) {
                        // Entferne zuerst vorhandene Filter
                        listview.filter_area.remove('party');
                        // Füge neuen Filter hinzu (korrekte Array-Syntax)
                        listview.filter_area.add([['Subscription', 'party', '=', party]]);
                        console.log('[SUBSCRIPTION FILTER] Party filter added');
                    } else {
                        listview.filter_area.remove('party');
                        console.log('[SUBSCRIPTION FILTER] Party filter removed');
                    }
                    // Aktualisiere die Liste
                    console.log('[SUBSCRIPTION FILTER] Calling refresh after party change');
                    // Setze Flag VOR refresh
                    listview._is_programmatic_change = true;
                    listview.refresh();
                }, 500);
            }
        });
        
        // Partnerin-Filter hinzufügen
        partnerinField = listview.page.add_field({
            label: 'Partnerin',
            fieldtype: 'Link',
            fieldname: 'custom_partnerin',
            options: 'Sales Partner',
            change: function() {
                let partnerin = this.get_value();
                console.log('[SUBSCRIPTION FILTER] Partnerin field changed:', partnerin, 'Is programmatic:', listview._is_programmatic_change);
                
                // Ignoriere wenn programmatisch gesetzt
                if (listview._is_programmatic_change) {
                    console.log('[SUBSCRIPTION FILTER] Ignoring programmatic partnerin change');
                    return;
                }
                
                // Ignoriere wenn Wert sich nicht geändert hat
                if (partnerin === listview._last_partnerin_value) {
                    console.log('[SUBSCRIPTION FILTER] Partnerin value unchanged, ignoring');
                    return;
                }
                
                // Speichere neuen Wert
                listview._last_partnerin_value = partnerin;
                
                // Verhindere Endlosschleife durch Debouncing
                clearTimeout(listview._partnerin_timeout);
                listview._partnerin_timeout = setTimeout(() => {
                    console.log('[SUBSCRIPTION FILTER] Partnerin timeout fired, setting filter:', partnerin);
                    if (partnerin) {
                        // Entferne zuerst vorhandene Filter
                        listview.filter_area.remove('custom_partnerin');
                        // Füge neuen Filter hinzu (korrekte Array-Syntax)
                        listview.filter_area.add([['Subscription', 'custom_partnerin', '=', partnerin]]);
                        console.log('[SUBSCRIPTION FILTER] Partnerin filter added');
                    } else {
                        listview.filter_area.remove('custom_partnerin');
                        console.log('[SUBSCRIPTION FILTER] Partnerin filter removed');
                    }
                    // Aktualisiere die Liste
                    console.log('[SUBSCRIPTION FILTER] Calling refresh after partnerin change');
                    // Setze Flag VOR refresh
                    listview._is_programmatic_change = true;
                    listview.refresh();
                }, 500);
            }
        });
        
        // Wrappe listview.refresh() direkt
        const originalListViewRefresh = listview.refresh;
        let isRestoringFilters = false;
        listview.refresh = function() {
            // Verhindere Endlosschleife während der Wiederherstellung
            if (isRestoringFilters) {
                console.log('[SUBSCRIPTION FILTER] Refresh skipped - currently restoring filters');
                return;
            }
            
            console.log('[SUBSCRIPTION FILTER] listview.refresh called, flag is:', listview._is_programmatic_change);
            
            // Verwende die gespeicherten Werte statt der Feldwerte (Felder werden während Refresh zurückgesetzt)
            const currentParty = listview._last_party_value || (partyField ? partyField.get_value() : null);
            const currentPartnerin = listview._last_partnerin_value || (partnerinField ? partnerinField.get_value() : null);
            
            console.log('[SUBSCRIPTION FILTER] Current values before refresh - Party:', currentParty, 'Partnerin:', currentPartnerin);
            
            // Führe Refresh aus (dies setzt die Filter zurück)
            originalListViewRefresh.call(this);
            
            // Stelle Filter IMMER wieder her, wenn Werte vorhanden sind
            // (Refresh setzt die Filter zurück, daher müssen wir sie immer wiederherstellen)
            if (currentParty || currentPartnerin) {
                isRestoringFilters = true;
                listview._is_programmatic_change = true;
                
                setTimeout(() => {
                    console.log('[SUBSCRIPTION FILTER] Restoring filters after refresh');
                    console.log('[SUBSCRIPTION FILTER] Values to restore - Party:', currentParty, 'Partnerin:', currentPartnerin);
                    
                    // Prüfe nochmal, ob Filter bereits gesetzt sind (nach Refresh)
                    const existingFiltersAfterRefresh = listview.filter_area.get();
                    const hasPartyFilterAfter = currentParty && existingFiltersAfterRefresh.some(f => f[1] === 'party' && f[3] === currentParty);
                    const hasPartnerinFilterAfter = currentPartnerin && existingFiltersAfterRefresh.some(f => f[1] === 'custom_partnerin' && f[3] === currentPartnerin);
                    
                    console.log('[SUBSCRIPTION FILTER] Filters after refresh - Party:', hasPartyFilterAfter, 'Partnerin:', hasPartnerinFilterAfter);
                    
                    if (currentParty && partyField && !hasPartyFilterAfter) {
                        console.log('[SUBSCRIPTION FILTER] Restoring party filter:', currentParty);
                        listview._is_programmatic_change = true;
                        partyField.set_value(currentParty);
                        isRestoringFilters = true;
                        listview.filter_area.add([['Subscription', 'party', '=', currentParty]]);
                        console.log('[SUBSCRIPTION FILTER] Party filter restored');
                    }
                    
                    if (currentPartnerin && partnerinField && !hasPartnerinFilterAfter) {
                        console.log('[SUBSCRIPTION FILTER] Restoring partnerin filter:', currentPartnerin);
                        listview._is_programmatic_change = true;
                        partnerinField.set_value(currentPartnerin);
                        isRestoringFilters = true;
                        listview.filter_area.add([['Subscription', 'custom_partnerin', '=', currentPartnerin]]);
                        console.log('[SUBSCRIPTION FILTER] Partnerin filter restored');
                    }
                    
                    // Entferne Flags nach längerer Verzögerung
                    setTimeout(() => {
                        isRestoringFilters = false;
                        listview._is_programmatic_change = false;
                        console.log('[SUBSCRIPTION FILTER] Restoration complete, change events enabled again');
                    }, 1000);
                }, 300);
            } else {
                // Wenn keine Werte vorhanden, Flag sofort zurücksetzen
                setTimeout(() => {
                    listview._is_programmatic_change = false;
                }, 100);
            }
        };
        
        console.log('[SUBSCRIPTION FILTER] onload completed');
    },
    
    refresh: function(listview) {
        // CSS für ID-Spalte schmaler machen
        function addListFormattingCSS() {
            if (document.getElementById('subscription-list-css')) {
                return;
            }
            
            let css = `
                /* ID-Spalte schmaler machen (ca. 3/5 der Breite) */
                .list-container .list-row .list-row-col.list-subject,
                .list-view .list-row .list-row-col.list-subject,
                .list-container .list-row-head .list-row-col.list-subject,
                .list-view .list-row-head .list-row-col.list-subject {
                    max-width: 60% !important;
                    width: 60% !important;
                }
                
                /* Filter-Felder nach links verschieben mit CSS order */
                .page-form.flex {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: wrap !important;
                }
                
                /* Kunde Filter ganz nach links */
                .page-form .form-group[data-fieldname="party"] {
                    order: -2 !important;
                }
                
                /* Partnerin Filter nach Kunde */
                .page-form .form-group[data-fieldname="custom_partnerin"] {
                    order: -1 !important;
                }
                
                /* Alle anderen Form-Gruppen nach den Custom-Filtern */
                .page-form .form-group:not([data-fieldname="party"]):not([data-fieldname="custom_partnerin"]) {
                    order: 0 !important;
                }
            `;
            
            let style = document.createElement('style');
            style.id = 'subscription-list-css';
            style.type = 'text/css';
            style.innerHTML = css;
            document.head.appendChild(style);
        }
        
        addListFormattingCSS();
        
        // ID-Filter entfernen
        function removeIdFilter() {
            const $idFilter = $('input[data-fieldname="name"][placeholder="ID"]');
            if ($idFilter.length) {
                const $filterGroup = $idFilter.closest('.form-group');
                $filterGroup.remove();
            }
        }
        
        // Nicht mehr nötig - Filter werden über onload hinzugefügt
        function addCustomFilters() {
            // Leer
        }
        
        // Labels aus vorhandenen Filtern entfernen
        function removeFilterLabels() {
            $('.standard-filter-section .form-group').each(function() {
                const $group = $(this);
                // Entferne Labels
                $group.find('.control-label, .clearfix:contains("Kunde"), .clearfix:contains("Partnerin"), label').remove();
            });
        }
        
        // Nicht mehr nötig - Event-Handler werden über onload definiert
        function bindFilterEvents() {
            // Leer
        }
        
        // Funktionen ausführen
        function runUpdates() {
            removeIdFilter();
        }
        
        // Sofort ausführen
        runUpdates();
        
        // Nach Verzögerungen ausführen
        setTimeout(runUpdates, 100);
        setTimeout(runUpdates, 500);
        setTimeout(runUpdates, 1000);
        
        // Auch nach Refresh der Liste
        if (listview && listview.list_view) {
            listview.list_view.on('list_refresh', function() {
                setTimeout(runUpdates, 100);
                setTimeout(runUpdates, 500);
            });
        }
        
        // Observer für Filter-Bereich
        if (window.MutationObserver) {
            const observer = new MutationObserver(function(mutations) {
                setTimeout(runUpdates, 100);
            });
            
            const filterSection = document.querySelector('.standard-filter-section, .page-form');
            if (filterSection) {
                observer.observe(filterSection, {
                    childList: true,
                    subtree: true
                });
            }
        }
        
        // Auch wenn Filter-Bereich neu geladen wird
        if (listview && listview.page) {
            $(listview.page.wrapper).on('DOMNodeInserted', '.standard-filter-section, .page-form', function() {
                setTimeout(runUpdates, 100);
            });
        }
    }
};

