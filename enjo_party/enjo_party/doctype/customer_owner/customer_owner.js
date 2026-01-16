frappe.ui.form.on('Customer Owner', {
	refresh(frm) {
		// Aktualisiere Feld-Sichtbarkeit basierend auf Modus
		update_field_visibility(frm);
		
		// Aktualisiere alle aktuellen Owner in der Tabelle (nur im Einzel-Modus)
		if (frm.doc.mode === 'Einzelne Kunden auswählen') {
			update_all_current_owners(frm);
		}
		
		// Aktualisiere Kunden-Anzahl im Bulk-Modus
		if (frm.doc.mode === 'Alle Kunden von Owner verschieben' && frm.doc.from_owner) {
			update_bulk_preview(frm);
		}
	},
	
	mode(frm) {
		// Wenn Modus geändert wird, aktualisiere Sichtbarkeit
		update_field_visibility(frm);
		
		// Setze customer_count zurück wenn nicht im Bulk-Modus
		if (frm.doc.mode !== 'Alle Kunden von Owner verschieben') {
			frm.set_value('customer_count', '');
			frm.refresh_field('customer_count');
		} else if (frm.doc.from_owner) {
			// Wenn auf Bulk-Modus gewechselt wird und from_owner bereits gesetzt ist, aktualisiere sofort
			update_bulk_preview(frm);
		}
	},
	
	from_owner(frm) {
		// Wenn from_owner geändert wird, aktualisiere Kunden-Anzahl sofort
		if (frm.doc.mode === 'Alle Kunden von Owner verschieben') {
			if (frm.doc.from_owner) {
				// Kleine Verzögerung um sicherzustellen, dass das Feld gerendert ist
				setTimeout(() => {
					if (frm.doc.from_owner && frm.doc.mode === 'Alle Kunden von Owner verschieben') {
						update_bulk_preview(frm);
					}
				}, 100);
			} else {
				frm.set_value('customer_count', '');
				frm.refresh_field('customer_count');
			}
		} else {
			frm.set_value('customer_count', '');
			frm.refresh_field('customer_count');
		}
	},
	
	after_save(frm) {
		// Nach dem Speichern aktualisiere die Anzahl erneut (falls im Bulk-Modus)
		if (frm.doc.mode === 'Alle Kunden von Owner verschieben' && frm.doc.from_owner) {
			update_bulk_preview(frm);
		}
	}
});

frappe.ui.form.on('Customer Owner Customer', {
	customer(frm, cdt, cdn) {
		// Wenn ein Kunde in der Tabelle ausgewählt wird, lade den aktuellen Owner und Namen
		const row = locals[cdt][cdn];
		if (row.customer) {
			frappe.db.get_value('Customer', row.customer, ['owner', 'customer_name'], (r) => {
				if (r) {
					frappe.model.set_value(cdt, cdn, 'current_owner', r.owner || '');
					frappe.model.set_value(cdt, cdn, 'customer_name', r.customer_name || '');
				}
			});
		} else {
			frappe.model.set_value(cdt, cdn, 'current_owner', '');
			frappe.model.set_value(cdt, cdn, 'customer_name', '');
		}
	},
	
	customers_add(frm, cdt, cdn) {
		// Wenn eine neue Zeile hinzugefügt wird, aktualisiere den Owner wenn bereits ein Kunde ausgewählt ist
		const row = locals[cdt][cdn];
		if (row.customer) {
			frappe.db.get_value('Customer', row.customer, ['owner', 'customer_name'], (r) => {
				if (r) {
					frappe.model.set_value(cdt, cdn, 'current_owner', r.owner || '');
					frappe.model.set_value(cdt, cdn, 'customer_name', r.customer_name || '');
				}
			});
		}
	}
});

function update_field_visibility(frm) {
	const is_single_mode = frm.doc.mode === 'Einzelne Kunden auswählen';
	const is_bulk_mode = frm.doc.mode === 'Alle Kunden von Owner verschieben';
	
	// Zeige/verstecke Felder basierend auf Modus
	frm.toggle_display('section_break_customers', is_single_mode);
	frm.toggle_display('customers', is_single_mode);
	frm.toggle_display('section_break_bulk', is_bulk_mode);
	frm.toggle_display('from_owner', is_bulk_mode);
	frm.toggle_display('customer_count', is_bulk_mode);
	
	// Setze required Status
	frm.set_df_property('customers', 'reqd', is_single_mode ? 1 : 0);
	frm.set_df_property('from_owner', 'reqd', is_bulk_mode ? 1 : 0);
	
	// Stelle sicher, dass customer_count Feld sichtbar ist wenn im Bulk-Modus
	if (is_bulk_mode && frm.fields_dict.customer_count) {
		frm.fields_dict.customer_count.$wrapper.show();
	}
}

function update_bulk_preview(frm) {
	// Prüfe ob wir im Bulk-Modus sind
	if (frm.doc.mode !== 'Alle Kunden von Owner verschieben') {
		console.log('[Customer Owner] Nicht im Bulk-Modus, überspringe update_bulk_preview');
		return;
	}
	
	if (!frm.doc.from_owner) {
		console.log('[Customer Owner] Kein from_owner gesetzt, setze customer_count leer');
		frm.set_value('customer_count', '');
		if (frm.fields_dict.customer_count) {
			frm.refresh_field('customer_count');
		}
		return;
	}
	
	// Prüfe ob das Feld existiert
	if (!frm.fields_dict.customer_count) {
		console.warn('[Customer Owner] customer_count Feld existiert nicht');
		return;
	}
	
	// Speichere aktuellen from_owner Wert für Vergleich
	const current_from_owner = frm.doc.from_owner;
	console.log('[Customer Owner] Starte Zählung für Owner:', current_from_owner);
	
	// Setze temporär "Wird geladen..." während der Abfrage
	frm.set_value('customer_count', 'Wird geladen...');
	frm.refresh_field('customer_count');
	
	// Verwende eine direkte SQL-Abfrage statt frappe.db.count für bessere Kontrolle
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Customer',
			filters: {
				owner: current_from_owner
			},
			fields: ['name'],
			limit_page_length: 0
		},
		callback: function(r) {
			console.log('[Customer Owner] Abfrage-Ergebnis für Owner', current_from_owner, ':', r);
			
			// Prüfe ob from_owner sich nicht geändert hat während der Abfrage
			if (frm.doc.from_owner === current_from_owner && 
			    frm.doc.mode === 'Alle Kunden von Owner verschieben' &&
			    frm.fields_dict.customer_count) {
				
				let count = 0;
				if (r.message && Array.isArray(r.message)) {
					count = r.message.length;
				}
				
				console.log('[Customer Owner] Gefundene Kunden für Owner', current_from_owner, ':', count);
				
				const display_text = count > 0 ? `${count} Kunden gefunden` : 'Keine Kunden gefunden';
				frm.set_value('customer_count', display_text);
				frm.refresh_field('customer_count');
				
				// Zusätzlich: Stelle sicher dass das Feld sichtbar ist
				if (frm.fields_dict.customer_count.$wrapper) {
					frm.fields_dict.customer_count.$wrapper.show();
				}
			} else {
				console.log('[Customer Owner] Owner hat sich geändert während der Abfrage. Aktuell:', frm.doc.from_owner, 'Erwartet:', current_from_owner);
			}
		},
		error: function(r) {
			console.error('[Customer Owner] Fehler beim Zählen der Kunden:', r);
			if (frm.doc.from_owner === current_from_owner && 
			    frm.doc.mode === 'Alle Kunden von Owner verschieben' &&
			    frm.fields_dict.customer_count) {
				frm.set_value('customer_count', 'Fehler beim Laden');
				frm.refresh_field('customer_count');
			}
		}
	});
}

function update_all_current_owners(frm) {
	if (!frm.doc.customers || frm.doc.customers.length === 0) {
		return;
	}
	
	// Aktualisiere alle Owner in der Tabelle
	frm.doc.customers.forEach((row, idx) => {
		if (row.customer) {
			frappe.db.get_value('Customer', row.customer, ['owner', 'customer_name'], (r) => {
				if (r) {
					frappe.model.set_value('Customer Owner Customer', row.name, 'current_owner', r.owner || '');
					frappe.model.set_value('Customer Owner Customer', row.name, 'customer_name', r.customer_name || '');
				}
			});
		}
	});
}
