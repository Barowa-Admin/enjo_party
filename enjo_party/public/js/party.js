// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

frappe.ui.form.on('Party', {
	refresh(frm) {
		// Zeige die Produktauswahl-Tabellen für die Gäste erst nach dem Speichern
		// Die ersten drei Sections werden immer angezeigt
		frm.toggle_display('produktauswahl_für_gast_1_section', !frm.is_new());
		frm.toggle_display('produktauswahl_für_gast_2_section', !frm.is_new());
		frm.toggle_display('produktauswahl_für_gast_3_section', !frm.is_new());
		
		// Ab dem vierten Gast nur anzeigen, wenn es genügend Gäste gibt
		if (!frm.is_new() && frm.doc.kunden) {
			// Für Gäste 4-9: Nur anzeigen, wenn es auch so viele Gäste gibt
			for (let i = 4; i <= 9; i++) {
				frm.toggle_display(
					`produktauswahl_für_gast_${i}_section`, 
					frm.doc.kunden.length >= i && !frm.is_new()
				);
			}
		}
		
		// Sammle alle Namen: Gastgeberin, Partnerin, Gäste
		let optionen = [];
		if (frm.doc.gastgeberin) optionen.push(frm.doc.gastgeberin);
		if (frm.doc.partnerin) optionen.push(frm.doc.partnerin);
		if (frm.doc.kunden && frm.doc.kunden.length > 0) {
			frm.doc.kunden.forEach(function(kunde) {
				if (kunde.kunde && !optionen.includes(kunde.kunde)) {
					optionen.push(kunde.kunde);
				}
			});
		}
		
		// Setze die Optionen für alle Versand-Select-Felder
		for (let i = 1; i <= 9; i++) {
			frm.set_df_property(`versand_gast_${i}`, 'options', optionen.join('\n'));
		}
		
		// Füge Button für die Rechnungserstellung hinzu, nur wenn das Dokument gespeichert und noch nicht abgeschlossen ist
		if (!frm.is_new() && frm.doc.status !== 'Abgeschlossen') {
			frm.add_custom_button(__('Rechnungen erstellen'), function() {
				// Bestätigungsdialog anzeigen
				frappe.confirm(
					'Möchtest Du Rechnungen für alle Gäste mit Bestellungen erstellen?',
					function() {
						// Führe die Rechnungserstellung aus wenn bestätigt
						frappe.call({
							method: 'enjo_party.enjo_party.doctype.party.party.create_invoices',
							args: {
								party: frm.doc.name
							},
							freeze: true,
							freeze_message: 'Erstelle Rechnungen...',
							callback: function(r) {
								if (r.message) {
									frappe.msgprint({
										title: __('Rechnungen erstellt'),
										indicator: 'green',
										message: __('Es wurden {0} Rechnungen erstellt.', [r.message.length])
									});
									// Formular neu laden
									frm.reload_doc();
								}
							}
						});
					},
					function() {
						// Wenn der Benutzer abbricht, nichts tun
					}
				);
			}, __('Aktionen'));
		}
	},
	
	onload(frm) {
		// Stelle sicher, dass mindestens 3 Zeilen in der Kunden-Tabelle sind
		if (frm.is_new() && (!frm.doc.kunden || frm.doc.kunden.length < 3)) {
			// Berechnen, wie viele Zeilen fehlen
			const benötigteZeilen = 3 - (frm.doc.kunden ? frm.doc.kunden.length : 0);
			
			// Füge die fehlenden Zeilen hinzu
			for (let i = 0; i < benötigteZeilen; i++) {
				let row = frm.add_child('kunden');
				// Hier könntest du Standardwerte setzen, falls nötig
			}
			
			// Aktualisiere die Tabelle im Formular
			frm.refresh_field('kunden');
		}
	},
	
	// Nach dem Speichern automatisch die Preise für alle leeren Produkte laden
	after_save(frm) {
		if (frm.doc.docstatus === 0) {
			refresh_item_prices(frm);
		}
	}
}); 

// Generische Funktion für jede Produkttabelle, um Preise zu aktualisieren
function setup_item_price_update(frm, field_name) {
    frm.fields_dict[field_name].grid.get_field('item_code').get_query = function() {
        return {
            filters: {
                'is_sales_item': 1,
				'disabled': 0
            }
        };
    };

    frm.fields_dict[field_name].grid.add_hook('on_update', function(doc, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code && (!row.rate || row.rate == 0)) {
            get_item_price(frm, row);
        }
    });
}

// Funktion, um alle Tabellen mit Preisen zu aktualisieren
function refresh_item_prices(frm) {
    // Alle Produkttabellen durchgehen und die Preisfunktion hinzufügen
    for (let i = 1; i <= 15; i++) {
        setup_item_price_update(frm, `produktauswahl_für_gast_${i}`);
    }
    
    // Auch für die Gastgeberin-Tabelle
    setup_item_price_update(frm, 'produktauswahl_für_gastgeberin');
    
    // Finde alle Produkte mit fehlenden Preisen und aktualisiere sie
    update_all_empty_prices(frm);
}

// Funktion, um den Preis eines Artikels abzurufen
function get_item_price(frm, row) {
    if (!row.item_code) return;
    
    frappe.call({
        method: 'erpnext.stock.get_item_details.get_item_details',
        args: {
            args: {
                item_code: row.item_code,
                customer: frm.doc.gastgeberin,
                company: frappe.defaults.get_user_default('Company'),
                conversion_rate: 1.0,
                price_list: frappe.defaults.get_global_default('selling_price_list'),
                plc_conversion_rate: 1.0,
                doctype: 'Sales Order',
                currency: frappe.defaults.get_global_default('currency'),
                update_stock: 0,
                conversion_factor: row.conversion_factor || 1.0,
                qty: row.qty || 1.0,
                price_list_uom_dependant: 1
            }
        },
        callback: function(r) {
            if (r.message) {
                row.rate = r.message.price_list_rate || 0;
                row.price_list_rate = r.message.price_list_rate || 0;
                row.base_price_list_rate = r.message.price_list_rate || 0;
                row.base_rate = r.message.price_list_rate || 0;
                row.item_name = r.message.item_name || row.item_code;
                row.price_list = r.message.price_list;
                row.uom = r.message.uom;
                row.conversion_factor = r.message.conversion_factor || 1.0;

                if (r.message.stock_uom) {
                    row.stock_uom = r.message.stock_uom;
                }

                frm.refresh_field(row.parentfield);
                console.log(`Preis für ${row.item_code} auf ${row.rate} gesetzt`);
            }
        }
    });
}

// Aktualisiere alle leeren Preise in allen Produkttabellen
function update_all_empty_prices(frm) {
    // Für jede Produkttabelle durchgehen
    for (let i = 1; i <= 15; i++) {
        const field_name = `produktauswahl_für_gast_${i}`;
        if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
            frm.doc[field_name].forEach(function(item) {
                if (item.item_code && (!item.rate || item.rate == 0)) {
                    get_item_price(frm, item);
                }
            });
        }
    }
    
    // Auch für die Gastgeberin-Tabelle
    if (frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
        frm.doc.produktauswahl_für_gastgeberin.forEach(function(item) {
            if (item.item_code && (!item.rate || item.rate == 0)) {
                get_item_price(frm, item);
            }
        });
    }
}

// Installiere den Event-Handler für jede Sales Order Item Row
frappe.ui.form.on('Sales Order Item', {
    item_code: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code && (!row.rate || row.rate == 0)) {
            get_item_price(frm, row);
        }
    }
}); 