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
	}
}); 