// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Subscription'] = {
    add_fields: ['party', 'custom_partnerin'],
    
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
        
        // Filter für Party und Partnerin hinzufügen (echte Frappe Standard-Filter)
        function addCustomFilters() {
            // Verwende Frappe's Standard-Filter-API
            if (listview && listview.page && listview.page.add_standard_filter) {
                // Party-Filter hinzufügen
                if (!$('input[data-fieldname="party"]').length) {
                    try {
                        listview.page.add_standard_filter('party', 'Customer');
                    } catch(e) {
                        console.log('Standard-Filter-API nicht verfügbar, verwende Fallback');
                    }
                }
                
                // Partnerin-Filter hinzufügen
                if (!$('input[data-fieldname="custom_partnerin"]').length) {
                    try {
                        listview.page.add_standard_filter('custom_partnerin', 'Sales Partner');
                    } catch(e) {
                        console.log('Standard-Filter-API nicht verfügbar, verwende Fallback');
                    }
                }
                
                // Warte kurz und binde dann Event-Handler für die Standard-Filter
                setTimeout(function() {
                    bindFilterEvents();
                }, 500);
            } else {
                // Fallback: Manuell erstellen ohne Labels
                const $standardFilters = $('.standard-filter-section');
                if (!$standardFilters.length) {
                    return;
                }
                
                // Prüfe ob Filter bereits existieren
                let $partyFilter = $('input[data-fieldname="party"]');
                let $partnerinFilter = $('input[data-fieldname="custom_partnerin"]');
                
                // Party (Kunde)-Filter hinzufügen
                if ($partyFilter.length === 0) {
                    const $partyGroup = $(`
                        <div class="form-group frappe-control input-max-width col-md-2">
                            <div class="frappe-input"></div>
                        </div>
                    `);
                    
                    $standardFilters.append($partyGroup);
                    
                    const partyControl = frappe.ui.form.make_control({
                        parent: $partyGroup.find('.frappe-input'),
                        df: {
                            fieldtype: 'Link',
                            fieldname: 'party',
                            options: 'Customer',
                            placeholder: 'Kunde',
                            label: ''
                        },
                        render_input: true,
                        frm: null
                    });
                    
                    // Entferne Label falls vorhanden
                    setTimeout(function() {
                        $partyGroup.find('.control-label, .clearfix, label').remove();
                    }, 100);
                    
                    if (partyControl && partyControl.$input) {
                        // Binde an Frappe's Standard-Filter-System
                        partyControl.$input.on('change', function() {
                            const value = partyControl.get_value();
                            if (value && listview) {
                                // Entferne zuerst vorhandene party-Filter
                                if (listview.filter_area) {
                                    listview.filter_area.remove('party');
                                }
                                // Füge neuen Filter hinzu
                                if (listview.filter_area) {
                                    listview.filter_area.add([['Subscription', 'party', '=', value]]);
                                }
                                // Aktualisiere die Liste
                                if (listview.list_view && listview.list_view.refresh) {
                                    listview.list_view.refresh();
                                } else if (listview.refresh) {
                                    listview.refresh();
                                }
                            } else if (!value && listview) {
                                // Entferne Filter wenn leer
                                if (listview.filter_area) {
                                    listview.filter_area.remove('party');
                                }
                                // Aktualisiere die Liste
                                if (listview.list_view && listview.list_view.refresh) {
                                    listview.list_view.refresh();
                                } else if (listview.refresh) {
                                    listview.refresh();
                                }
                            }
                        });
                    }
                }
                
                // Partnerin-Filter hinzufügen
                if ($partnerinFilter.length === 0) {
                    const $partnerinGroup = $(`
                        <div class="form-group frappe-control input-max-width col-md-2">
                            <div class="frappe-input"></div>
                        </div>
                    `);
                    
                    $standardFilters.append($partnerinGroup);
                    
                    const partnerinControl = frappe.ui.form.make_control({
                        parent: $partnerinGroup.find('.frappe-input'),
                        df: {
                            fieldtype: 'Link',
                            fieldname: 'custom_partnerin',
                            options: 'Sales Partner',
                            placeholder: 'Partnerin',
                            label: ''
                        },
                        render_input: true,
                        frm: null
                    });
                    
                    // Entferne Label falls vorhanden
                    setTimeout(function() {
                        $partnerinGroup.find('.control-label, .clearfix, label').remove();
                    }, 100);
                    
                    if (partnerinControl && partnerinControl.$input) {
                        // Binde an Frappe's Standard-Filter-System
                        partnerinControl.$input.on('change', function() {
                            const value = partnerinControl.get_value();
                            if (value && listview) {
                                // Entferne zuerst vorhandene custom_partnerin-Filter
                                if (listview.filter_area) {
                                    listview.filter_area.remove('custom_partnerin');
                                }
                                // Füge neuen Filter hinzu
                                if (listview.filter_area) {
                                    listview.filter_area.add([['Subscription', 'custom_partnerin', '=', value]]);
                                }
                                // Aktualisiere die Liste
                                if (listview.list_view && listview.list_view.refresh) {
                                    listview.list_view.refresh();
                                } else if (listview.refresh) {
                                    listview.refresh();
                                }
                            } else if (!value && listview) {
                                // Entferne Filter wenn leer
                                if (listview.filter_area) {
                                    listview.filter_area.remove('custom_partnerin');
                                }
                                // Aktualisiere die Liste
                                if (listview.list_view && listview.list_view.refresh) {
                                    listview.list_view.refresh();
                                } else if (listview.refresh) {
                                    listview.refresh();
                                }
                            }
                        });
                    }
                }
            }
        }
        
        // Labels aus vorhandenen Filtern entfernen
        function removeFilterLabels() {
            $('.standard-filter-section .form-group').each(function() {
                const $group = $(this);
                // Entferne Labels
                $group.find('.control-label, .clearfix:contains("Kunde"), .clearfix:contains("Partnerin"), label').remove();
            });
        }
        
        // Event-Handler für Standard-Filter binden
        function bindFilterEvents() {
            // Party-Filter
            const $partyInput = $('input[data-fieldname="party"]');
            if ($partyInput.length) {
                $partyInput.off('change.filter').on('change.filter', function() {
                    const value = $(this).val();
                    if (value && listview) {
                        if (listview.filter_area) {
                            listview.filter_area.remove('party');
                            listview.filter_area.add([['Subscription', 'party', '=', value]]);
                        }
                        if (listview.list_view && listview.list_view.refresh) {
                            listview.list_view.refresh();
                        }
                    } else if (!value && listview && listview.filter_area) {
                        listview.filter_area.remove('party');
                        if (listview.list_view && listview.list_view.refresh) {
                            listview.list_view.refresh();
                        }
                    }
                });
            }
            
            // Partnerin-Filter
            const $partnerinInput = $('input[data-fieldname="custom_partnerin"]');
            if ($partnerinInput.length) {
                $partnerinInput.off('change.filter').on('change.filter', function() {
                    const value = $(this).val();
                    if (value && listview) {
                        if (listview.filter_area) {
                            listview.filter_area.remove('custom_partnerin');
                            listview.filter_area.add([['Subscription', 'custom_partnerin', '=', value]]);
                        }
                        if (listview.list_view && listview.list_view.refresh) {
                            listview.list_view.refresh();
                        }
                    } else if (!value && listview && listview.filter_area) {
                        listview.filter_area.remove('custom_partnerin');
                        if (listview.list_view && listview.list_view.refresh) {
                            listview.list_view.refresh();
                        }
                    }
                });
            }
        }
        
        // Funktionen ausführen
        function runUpdates() {
            removeIdFilter();
            addCustomFilters();
            removeFilterLabels();
            bindFilterEvents();
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

