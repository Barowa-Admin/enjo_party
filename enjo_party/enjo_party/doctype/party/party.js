// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Party", {
// 	refresh(frm) {

// 	},
// });

// Funktion zum Aktualisieren der benutzerdefinierten Überschriften
function updateCustomHeaders(frm) {
	if (!frm.doc.kunden) return;
	
	// Zuerst für die Gastgeberin, wenn vorhanden
	if (frm.doc.gastgeberin) {
		let sectionId = "produktauswahl_für_gastgeberin_section";
		let sectionHeader = document.querySelector(`[data-fieldname="${sectionId}"] .section-head`);
		
		if (sectionHeader) {
			// Wende den Stil direkt auf das Kopfelement an
			sectionHeader.style.fontWeight = "500";
			sectionHeader.style.fontSize = "1em";
			sectionHeader.style.color = "#6C7680";
			
			// Prüfe, ob wir bereits einen angepassten Header haben
			if (!sectionHeader.querySelector('.custom-header')) {
				// Erstelle einen neuen Inhalt mit einem benutzerdefinierten span
				sectionHeader.innerHTML = `Produktauswahl für <span class="custom-header" style="font-weight: 600; color: #1F272E;">${frm.doc.gastgeberin}</span>`;
			} else {
				// Aktualisiere nur den Text des benutzerdefinierten Spans
				sectionHeader.querySelector('.custom-header').textContent = frm.doc.gastgeberin;
			}
		}
		
		// Auch das Label für das Versand-Dropdown anpassen
		frm.set_df_property('versand_gastgeberin', 'label', `Versand zu ${frm.doc.gastgeberin}`);
	}
	
	// Dann für jeden Kunden
	for (let i = 1; i <= frm.doc.kunden.length; i++) {
		if (i > 15) break; // Maximale Anzahl von Tabs
		
		let kundeRow = frm.doc.kunden[i-1];
		if (!kundeRow || !kundeRow.kunde) continue;
		
		// Finde den entsprechenden Section-Header im DOM
		let sectionId = `produktauswahl_für_gast_${i}_section`;
		let sectionHeader = document.querySelector(`[data-fieldname="${sectionId}"] .section-head`);
		
		if (sectionHeader) {
			// Erzeuge einen benutzerdefinierten Header mit dem Kundennamen
			let kundenName = kundeRow.kunde;
			
			// Wende den Stil direkt auf das Kopfelement an, anstatt den innerHTML zu ersetzen
			sectionHeader.style.fontWeight = "500";
			sectionHeader.style.fontSize = "1em";
			sectionHeader.style.color = "#6C7680";
			
			// Prüfe, ob wir bereits einen angepassten Header haben
			if (!sectionHeader.querySelector('.custom-header')) {
				// Erstelle einen neuen Inhalt mit einem benutzerdefinierten span
				sectionHeader.innerHTML = `Produktauswahl für <span class="custom-header" style="font-weight: 600; color: #1F272E;">${kundenName}</span>`;
			} else {
				// Aktualisiere nur den Text des benutzerdefinierten Spans
				sectionHeader.querySelector('.custom-header').textContent = kundenName;
			}
			
			// Auch das Label für das Versand-Dropdown anpassen
			frm.set_df_property(`versand_gast_${i}`, 'label', `Versand zu ${kundenName}`);
		}
	}
}

frappe.ui.form.on('Party', {
	refresh(frm) {
		// Zeige die Produktauswahl-Tabellen für die Gäste erst nach dem Speichern
		// Alle Gäste-Tabellen werden im Neu-Modus ausgeblendet
		for (let i = 1; i <= 15; i++) {
			// Nur anzeigen, wenn das Dokument gespeichert ist UND genügend Gäste vorhanden sind
			frm.toggle_display(
				`produktauswahl_für_gast_${i}_section`, 
				!frm.is_new() && frm.doc.kunden && frm.doc.kunden.length >= i
			);
		}
		
		// Zeige Gastgeberin-Produktauswahl nur an, wenn eine Gastgeberin eingetragen und das Dokument gespeichert ist
		frm.toggle_display(
			"produktauswahl_für_gastgeberin_section", 
			!frm.is_new() && frm.doc.gastgeberin
		);

		// Kundennamen in Überschriften einfügen (nach DOM-Rendering)
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 500);
		
		// Verstecke das Datum-Feld auch in der Gastgeberin-Tabelle
		if (frm.fields_dict["produktauswahl_für_gastgeberin"]) {
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('delivery_date', 'hidden', 1);
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('delivery_date', 'reqd', 0);
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
		for (let i = 1; i <= 15; i++) {
			frm.set_df_property(`versand_gast_${i}`, 'options', optionen.join('\n'));
			
			// Setze die Gastgeberin als Standardwert für den Versand, falls vorhanden und kein Wert gesetzt ist
			// Setze immer die Gastgeberin als Standardwert
			if (frm.doc.gastgeberin && (!frm.doc[`versand_gast_${i}`])) {
				frm.set_value(`versand_gast_${i}`, frm.doc.gastgeberin);
			}
		}
		
		// Setze auch die Versandoptionen für die Gastgeberin
		frm.set_df_property('versand_gastgeberin', 'options', optionen.join('\n'));
		
		// Setze die Gastgeberin als Standardversand für sich selbst
		if (frm.doc.gastgeberin && !frm.doc.versand_gastgeberin) {
			frm.set_value('versand_gastgeberin', frm.doc.gastgeberin);
		}
		
		// Verstecke das Datum-Feld in allen Produktauswahl-Tabellen
		for (let i = 1; i <= 15; i++) {
			const fieldName = `produktauswahl_für_gast_${i}`;
			if (frm.fields_dict[fieldName]) {
				// Verstecke das Datum-Feld in der Tabelle (damit kein Kalender erscheint)
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'hidden', 1);
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'reqd', 0);
			}
		}
	},
	
	// Füge einen Event-Handler für die Gastgeberin hinzu
	gastgeberin: function(frm) {
		// Wenn die Gastgeberin geändert wird, setze sie als Standard für den Versand
		if (frm.doc.gastgeberin) {
			// Aktualisiere das Label für die Gastgeberin
			frm.set_df_property('versand_gastgeberin', 'label', `Versand zu ${frm.doc.gastgeberin}`);
			
			for (let i = 1; i <= 15; i++) {
				// Immer die Gastgeberin als Versandziel setzen
				frm.set_value(`versand_gast_${i}`, frm.doc.gastgeberin);
			}
			
			// Auch für die Gastgeberin selbst
			frm.set_value('versand_gastgeberin', frm.doc.gastgeberin);
		}
		
		// Aktualisiere auch die Überschriften
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 500);
		
		// Aktualisiere die Optionen für die Versandfelder
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
		
		for (let i = 1; i <= 15; i++) {
			frm.set_df_property(`versand_gast_${i}`, 'options', optionen.join('\n'));
		}
		
		// Auch für die Gastgeberin aktualisieren
		frm.set_df_property('versand_gastgeberin', 'options', optionen.join('\n'));
	},
	
	onload: function(frm) {
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
	
	// Aktualisiere auch wenn Kunden hinzugefügt oder entfernt werden
	kunden_add: function(frm) {
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 500);
	},
	kunden_remove: function(frm) {
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 500);
	}
});

// Event-Handler für Party Kunde (die Zeilen in der Kundentabelle)
frappe.ui.form.on('Party Kunde', {
	kunde: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let idx = row.idx;
		
		// Sofort das Versand-Label aktualisieren
		if (row.kunde) {
			frm.set_df_property(`versand_gast_${idx}`, 'label', `Versand zu ${row.kunde}`);
		}
		
		// Aktualisiere die benutzerdefinierten Header
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 500);
	}
});

// Event-Handler für Sales Order Item - Nur Menge automatisch auf 1 setzen
frappe.ui.form.on('Sales Order Item', {
	item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_code && !row.qty) {
			frappe.model.set_value(cdt, cdn, 'qty', 1);
		}
	}
});

