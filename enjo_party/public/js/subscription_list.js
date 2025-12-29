// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.listview_settings['Subscription'] = {
    refresh: function(listview) {
        // CSS für bessere Formatierung der Listenansicht
        function addListFormattingCSS() {
            if (document.getElementById('subscription-list-css')) {
                return;
            }
            
            let css = `
                /* Checkbox-Spalte sichtbar halten */
                .list-container .list-row .list-row-col input[type="checkbox"],
                .list-view .list-row .list-row-col input[type="checkbox"],
                .list-container .list-row-head .list-row-col input[type="checkbox"],
                .list-view .list-row-head .list-row-col input[type="checkbox"] {
                    display: inline-block !important;
                    visibility: visible !important;
                    opacity: 1 !important;
                }
                
                /* Erste Spalte (ID) breiter machen für Kundenname - aber Checkboxen nicht verstecken */
                .list-container .list-row .list-row-col:first-child,
                .list-view .list-row .list-row-col:first-child {
                    min-width: 200px !important;
                    max-width: 300px !important;
                }
                
                .list-container .list-row-head .list-row-col:first-child,
                .list-view .list-row-head .list-row-col:first-child {
                    min-width: 200px !important;
                    max-width: 300px !important;
                }
                
                /* Kunde-Spalte ausblenden */
                .list-container .list-row .list-row-col[data-fieldname="party"],
                .list-view .list-row .list-row-col[data-fieldname="party"],
                .list-container .list-row-head .list-row-col[data-fieldname="party"],
                .list-view .list-row-head .list-row-col[data-fieldname="party"] {
                    display: none !important;
                }
                
                /* Partnerin-Spalte breiter machen */
                .list-container .list-row .list-row-col[data-fieldname="custom_partnerin"],
                .list-view .list-row .list-row-col[data-fieldname="custom_partnerin"] {
                    min-width: 180px !important;
                    max-width: 250px !important;
                }
                
                .list-container .list-row-head .list-row-col[data-fieldname="custom_partnerin"],
                .list-view .list-row-head .list-row-col[data-fieldname="custom_partnerin"] {
                    min-width: 180px !important;
                    max-width: 250px !important;
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
            // Finde das ID-Filter-Feld
            const $idFilter = $('input[data-fieldname="name"][placeholder="ID"]');
            if ($idFilter.length) {
                const $filterGroup = $idFilter.closest('.form-group');
                $filterGroup.remove();
            }
        }
        
        // Header der ID-Spalte ändern - finde die Spalte mit "ID" Text oder list-subject Klasse
        function updateFirstColumnHeader() {
            // Finde die Header-Spalte mit list-subject Klasse oder "ID" Text
            let $targetHeader = $('.list-row-head .list-row-col.list-subject');
            
            // Fallback: Suche nach "ID" Text
            if (!$targetHeader.length) {
                $('.list-row-head .list-row-col').each(function() {
                    const $header = $(this);
                    const text = $header.text().trim();
                    if (text === 'ID' || text.includes('ID')) {
                        $targetHeader = $header;
                        return false;
                    }
                });
            }
            
            if ($targetHeader.length && !$targetHeader.attr('data-header-updated')) {
                // Finde das span-Element mit "ID" Text
                const $idSpan = $targetHeader.find('span:contains("ID")');
                if ($idSpan.length) {
                    $idSpan.text('Kunde');
                    $idSpan.css('margin-left', '15px');
                } else {
                    // Sonst ändere den gesamten Inhalt
                    $targetHeader.find('span.level-item').text('Kunde');
                    $targetHeader.find('span.level-item').css('margin-left', '15px');
                }
                
                $targetHeader.attr('data-header-updated', 'true');
            }
        }
        
        // ID-Spalte durch Kundenname ersetzen - finde die Spalte mit list-subject Klasse
        function updateFirstColumnWithCustomerName() {
            $('.list-row').each(function() {
                const $row = $(this);
                
                // Finde die Spalte mit list-subject Klasse (das ist die ID-Spalte)
                let $targetCell = $row.find('.list-row-col.list-subject');
                
                // Fallback: Suche nach Spalte mit Subscription-ID
                if (!$targetCell.length) {
                    $row.find('.list-row-col').each(function() {
                        const $cell = $(this);
                        const text = $cell.text().trim();
                        if ($cell.find('input[type="checkbox"]').length === 0 && text.match(/^ACC-SUB-/)) {
                            $targetCell = $cell;
                            return false;
                        }
                    });
                }
                
                if (!$targetCell.length) {
                    return;
                }
                
                // Prüfe ob bereits aktualisiert wurde
                if ($targetCell.attr('data-customer-name-updated')) {
                    return;
                }
                
                // Hole Subscription ID aus dem Link oder Text
                let subscriptionId = null;
                const $link = $targetCell.find('a.ellipsis');
                if ($link.length) {
                    subscriptionId = $link.attr('data-name') || $link.attr('href')?.replace('/app/subscription/', '').split('/')[0];
                }
                if (!subscriptionId) {
                    subscriptionId = $row.attr('data-name');
                }
                if (!subscriptionId) {
                    const text = $targetCell.text().trim();
                    if (text.match(/^ACC-SUB-/)) {
                        subscriptionId = text;
                    }
                }
                
                if (!subscriptionId) {
                    return;
                }
                
                // Hole direkt aus Subscription-Dokument
                frappe.db.get_value('Subscription', subscriptionId, 'party', function(r) {
                    if (r && r.party) {
                        const customerId = r.party;
                        
                        // Hole Kundenname
                        frappe.db.get_value('Customer', customerId, 'customer_name', function(customerResult) {
                            if (customerResult && customerResult.customer_name && $targetCell.length) {
                                // Erstelle Link mit Kundenname - mit normalem Frappe-Abstand
                                const link = '/app/subscription/' + frappe.utils.escape_html(subscriptionId);
                                
                                // Ersetze den Link-Inhalt
                                if ($link.length) {
                                    $link.text(customerResult.customer_name);
                                    $link.css('margin-left', '15px');
                                    $link.attr('title', 'Subscription: ' + subscriptionId + ' | Kunde: ' + customerId);
                                } else {
                                    $targetCell.html('<a href="' + link + '" class="ellipsis" data-doctype="Subscription" data-name="' + 
                                                   frappe.utils.escape_html(subscriptionId) + '" style="margin-left: 15px;">' + 
                                                   frappe.utils.escape_html(customerResult.customer_name) + '</a>');
                                }
                                
                                $targetCell.attr('data-customer-name-updated', 'true');
                            }
                        });
                    }
                });
            });
        }
        
        // Partnerin/Vertrieblerin Spalte hinzufügen
        function addPartnerinColumn() {
            // Füge Header hinzu - nach der ersten Daten-Spalte (nicht Checkbox)
            const $headerRow = $('.list-row-head');
            if ($headerRow.length) {
                let $existingHeader = $headerRow.find('.list-row-col[data-fieldname="custom_partnerin"]');
                
                if ($existingHeader.length === 0) {
                    const $firstHeader = $headerRow.find('.list-row-col:first-child');
                    const hasCheckbox = $firstHeader.find('input[type="checkbox"]').length > 0;
                    const $targetHeader = hasCheckbox ? $headerRow.find('.list-row-col:nth-child(2)') : $firstHeader;
                    
                    if ($targetHeader.length) {
                        const $newHeader = $('<div>')
                            .addClass('list-row-col')
                            .attr('data-fieldname', 'custom_partnerin')
                            .css({
                                'min-width': '180px',
                                'max-width': '250px'
                            })
                            .text('Partnerin/Vertrieblerin');
                        
                        // Füge nach der Ziel-Spalte ein
                        $targetHeader.after($newHeader);
                    }
                }
            }
            
            // Funktion zum Laden der Partnerin-Daten für eine Zeile
            function loadPartnerinForRow($row, $cell) {
                // Prüfe ob bereits geladen wurde (nicht nur ob Spalte existiert)
                if ($cell.attr('data-partnerin-loaded') === 'true') {
                    return;
                }
                
                // Hole Subscription Name aus der Zeile
                let subscriptionName = $row.attr('data-name');
                if (!subscriptionName) {
                    const $link = $row.find('a[data-doctype="Subscription"]');
                    if ($link.length) {
                        subscriptionName = $link.attr('data-name') || $link.attr('href')?.replace('/app/subscription/', '').split('/')[0];
                    }
                }
                if (!subscriptionName) {
                    const href = $row.find('a').attr('href');
                    if (href && href.includes('/app/subscription/')) {
                        subscriptionName = href.replace('/app/subscription/', '').split('/')[0];
                    }
                }
                if (!subscriptionName) {
                    const $targetCell = $row.find('.list-row-col.list-subject, .list-row-col:has(a[href*="/app/subscription/"])').first();
                    if ($targetCell.length) {
                        const href = $targetCell.find('a').attr('href');
                        if (href && href.includes('/app/subscription/')) {
                            subscriptionName = href.replace('/app/subscription/', '').split('/')[0];
                        }
                    }
                }
                if (!subscriptionName) {
                    const text = $cell.text().trim();
                    if (text && text.match(/^ACC-SUB-/)) {
                        subscriptionName = text;
                    }
                }
                
                if (!subscriptionName) {
                    $cell.text('-');
                    $cell.attr('data-partnerin-loaded', 'true');
                    return;
                }
                
                // Setze Placeholder
                if ($cell.text().trim() === '' || $cell.text().trim() === '...') {
                    $cell.text('...');
                }
                
                // Hole Partnerin aus der ersten Sales Invoice mit Retry
                function fetchPartnerin(retryCount = 0) {
                    frappe.call({
                        method: 'frappe.client.get_list',
                        args: {
                            doctype: 'Sales Invoice',
                            filters: {
                                subscription: subscriptionName,
                                docstatus: 1
                            },
                            fields: ['sales_partner'],
                            limit: 1,
                            order_by: 'posting_date asc'
                        },
                        callback: function(r) {
                            if (r && r.message && r.message.length > 0 && r.message[0].sales_partner) {
                                const salesPartnerId = r.message[0].sales_partner;
                                
                                // Hole den Namen des Sales Partners
                                frappe.db.get_value('Sales Partner', salesPartnerId, 'partner_name', function(partnerResult) {
                                    if ($cell.length) {
                                        if (partnerResult && partnerResult.partner_name) {
                                            $cell.text(partnerResult.partner_name);
                                            $cell.attr('title', salesPartnerId); // Tooltip mit ID
                                        } else {
                                            $cell.text(salesPartnerId || '-');
                                        }
                                        $cell.attr('data-partnerin-loaded', 'true');
                                    }
                                });
                            } else if ($cell.length) {
                                $cell.text('-');
                                $cell.attr('data-partnerin-loaded', 'true');
                            } else if (retryCount < 2) {
                                // Retry nach kurzer Verzögerung
                                setTimeout(function() {
                                    fetchPartnerin(retryCount + 1);
                                }, 500);
                            }
                        },
                        error: function(r) {
                            if (retryCount < 2 && $cell.length) {
                                // Retry bei Fehler
                                setTimeout(function() {
                                    fetchPartnerin(retryCount + 1);
                                }, 500);
                            } else if ($cell.length) {
                                $cell.text('-');
                                $cell.attr('data-partnerin-loaded', 'true');
                            }
                        }
                    });
                }
                
                fetchPartnerin();
            }
            
            // Füge Datenzeilen hinzu oder aktualisiere vorhandene
            $('.list-row').each(function() {
                const $row = $(this);
                const $firstCell = $row.find('.list-row-col:first-child');
                const hasCheckbox = $firstCell.find('input[type="checkbox"]').length > 0;
                const $targetCell = hasCheckbox ? $row.find('.list-row-col:nth-child(2)') : $firstCell;
                
                if (!$targetCell.length) {
                    return;
                }
                
                // Prüfe ob Spalte bereits existiert
                let $partnerinCell = $row.find('.list-row-col[data-fieldname="custom_partnerin"]');
                
                if ($partnerinCell.length === 0) {
                    // Erstelle neue Spalte
                    $partnerinCell = $('<div>')
                        .addClass('list-row-col')
                        .attr('data-fieldname', 'custom_partnerin')
                        .css({
                            'min-width': '180px',
                            'max-width': '250px'
                        })
                        .text('...');
                    
                    // Füge nach der Ziel-Spalte ein
                    $targetCell.after($partnerinCell);
                }
                
                // Lade Daten (auch wenn Spalte bereits existiert, falls noch nicht geladen)
                loadPartnerinForRow($row, $partnerinCell);
            });
        }
        
        // Funktionen mehrfach ausführen um sicherzustellen dass sie greifen
        function runUpdates() {
            removeIdFilter();
            updateFirstColumnHeader();
            updateFirstColumnWithCustomerName();
            addPartnerinColumn();
        }
        
        // Sofort ausführen
        runUpdates();
        
        // Nach verschiedenen Verzögerungen ausführen
        setTimeout(runUpdates, 100);
        setTimeout(runUpdates, 500);
        setTimeout(runUpdates, 1000);
        setTimeout(runUpdates, 1500);
        setTimeout(runUpdates, 2500);
        setTimeout(runUpdates, 4000);
        
        // Auch nach Refresh der Liste
        if (listview && listview.list_view) {
            listview.list_view.on('list_refresh', function() {
                setTimeout(runUpdates, 100);
                setTimeout(runUpdates, 500);
                setTimeout(runUpdates, 1000);
            });
        }
        
        // Auch wenn sich die Liste ändert
        if (listview && listview.list_view && listview.list_view.wrapper) {
            $(listview.list_view.wrapper).on('DOMNodeInserted', function() {
                setTimeout(runUpdates, 100);
            });
        }
        
        // Observer für Änderungen in der Liste und Filter-Bereich
        if (window.MutationObserver) {
            const observer = new MutationObserver(function(mutations) {
                setTimeout(runUpdates, 100);
            });
            
            const listContainer = document.querySelector('.list-view-container, .list-container');
            if (listContainer) {
                observer.observe(listContainer, {
                    childList: true,
                    subtree: true
                });
            }
            
            // Auch Filter-Bereich beobachten
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
                setTimeout(removeIdFilter, 100);
            });
        }
    }
};

