// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Party", {
// 	refresh(frm) {

// 	},
// });

// Hilfsfunktion zum Wiederherstellen der Buttons basierend auf dem aktuellen Status
function refreshButtons(frm) {
	console.log("refreshButtons aufgerufen - Status:", frm.doc.status, "docstatus:", frm.doc.docstatus, "is_new:", frm.is_new());
	
	// Erst alle benutzerdefinierten Buttons löschen
	try {
		if (frm && frm.page) {
			if (frm.page.clear_custom_actions) frm.page.clear_custom_actions();
		}
	} catch (e) {
		console.error("Fehler beim Löschen der Buttons:", e);
	}
	
	// Dann die richtigen Buttons basierend auf dem Status hinzufügen
	if (frm.doc.docstatus === 0) { // Nicht eingereicht
		// Prüfe ob es ein neues Dokument ist (auch wenn is_new() undefined ist)
		let isNewDoc = frm.is_new() || !frm.doc.name || frm.doc.name.startsWith('new-');
		
		if (isNewDoc) {
			console.log("Neu-Modus: Standard-Buttons verwenden");
			// Im Neu-Modus: Standard-Buttons verwenden und Speichern-Button hinzufügen
			if (frm.page && frm.page.btn_primary) {
				frm.page.btn_primary.show();
				// Text auf Deutsch setzen
				setTimeout(() => {
					$(frm.wrapper).find('.btn-primary').text("Speichern");
				}, 50);
			} else {
				// Fallback: Eigenen Speichern-Button hinzufügen
				frm.add_custom_button(__("Speichern"), function() {
					frm.save();
				}).addClass("btn-primary");
			}
		} else if (frm.doc.status === "Gäste") {
			console.log("Status Gäste: Speichern-Button hinzufügen");
			// Status "Gäste": Nur Speichern-Button anzeigen
			frm.add_custom_button(__("Speichern"), function() {
				frm.save();
			}).addClass("btn-primary");
		} else if (frm.doc.status === "Produkte") {
			console.log("Status Produkte: Aufträge erstellen + Speichern Buttons hinzufügen");
			// Status "Produkte": Speichern und "Aufträge erstellen"-Button
			frm.add_custom_button(__("Aufträge erstellen"), function() {
				// Die komplette Aufträge-Erstellungslogik hier einfügen
				startAuftraegeErstellung(frm);
			}).addClass("btn-primary");
			
			// Auch einen Speichern-Button anzeigen (ohne Primärfarbe)
			frm.add_custom_button(__("Speichern"), function() {
				frm.save();
			});
		} else {
			console.log("Unbekannter Status:", frm.doc.status);
		}
	} else {
		console.log("Dokument ist eingereicht (docstatus !== 0)");
	}
}

// Hilfsfunktion zum Starten der Aufträge-Erstellung (ohne Button-Manipulation)
function startAuftraegeErstellung(frm) {
	console.log("startAuftraegeErstellung aufgerufen");
	// Erst prüfen, ob alle Teilnehmer Produkte haben
	let teilnehmer_ohne_produkte = [];
	
	// Prüfe Gastgeberin
	if (frm.doc.gastgeberin) {
		let hat_gastgeberin_produkte = false;
		if (frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
			for (let produkt of frm.doc.produktauswahl_für_gastgeberin) {
				if (produkt.item_code && produkt.qty && produkt.qty > 0) {
					hat_gastgeberin_produkte = true;
					break;
				}
			}
		}
		
		if (!hat_gastgeberin_produkte) {
			teilnehmer_ohne_produkte.push(`${frm.doc.gastgeberin} (Gastgeberin)`);
		}
	}
	
	// Prüfe alle Gäste
	for (let i = 0; i < frm.doc.kunden.length; i++) {
		let kunde = frm.doc.kunden[i];
		if (!kunde.kunde) continue;
		
		let field_name = `produktauswahl_für_gast_${i+1}`;
		let hat_produkte = false;
		
		if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
			for (let produkt of frm.doc[field_name]) {
				if (produkt.item_code && produkt.qty && produkt.qty > 0) {
					hat_produkte = true;
					break;
				}
			}
		}
		
		if (!hat_produkte) {
			teilnehmer_ohne_produkte.push(kunde.kunde);
		}
	}
	
	console.log("Teilnehmer ohne Produkte:", teilnehmer_ohne_produkte);
	
	// Wenn alle Teilnehmer Produkte haben, prüfe Aktionen vor der Bestätigung
	if (teilnehmer_ohne_produkte.length === 0) {
		console.log("Alle Teilnehmer haben Produkte - zeige Bestätigungsdialog");
		frappe.confirm(
			__("Bist Du sicher, dass alle Produkte richtig ausgewählt wurden und Du die Bestellung abschicken möchtest? Dieser Vorgang kann nicht rückgängig gemacht werden!"),
			function() {
				console.log("Benutzer hat bestätigt - prüfe Aktionssystem");
				// Erst Gutschein-System anwenden, dann Aktions-System, dann Aufträge erstellen
				console.log("Starte Gutschein-System");
				applyGutscheinSystem(frm, function() {
					console.log("Gutschein-System abgeschlossen - starte Aktions-System");
					// Prüfe, ob Aktionssystem verfügbar ist (über Client Script "discount_window_party")
					if (typeof discount_window_party === 'function') {
						console.log("Aktionssystem verfügbar - rufe discount_window_party auf");
						// Aktionssystem ist verfügbar - prüfe Aktionen als letzten Schritt
						discount_window_party(frm, function() {
							console.log("Aktionssystem abgeschlossen - erstelle Aufträge");
							// Nach Aktionsprüfung Aufträge erstellen
							erstelleAuftraege(frm);
						});
					} else {
						console.log("Kein Aktionssystem - erstelle direkt Aufträge");
						// Kein Aktionssystem verfügbar - direkt Aufträge erstellen
						erstelleAuftraege(frm);
					}
				});
			}
		);
		return;
	}
	
	// Wenn Teilnehmer ohne Produkte gefunden wurden, Dialog mit Optionen anzeigen
	let gaeste_ohne_produkte_anzahl = teilnehmer_ohne_produkte.filter(t => !t.includes('(Gastgeberin)')).length;
	let verbleibende_gaeste = frm.doc.kunden.length - gaeste_ohne_produkte_anzahl;
	let kann_entfernen = verbleibende_gaeste >= 3;
	
	let message = `Die folgenden Teilnehmer haben noch keine Produkte ausgewählt:\n\n${teilnehmer_ohne_produkte.join('\n')}\n\n`;
	
	if (kann_entfernen) {
		message += "Was möchten Sie tun?";
	} else {
		message += "Es können nicht alle Gäste ohne Produkte entfernt werden, da dann weniger als 3 Gäste übrig bleiben würden.\nBitte wählen Sie Produkte für die fehlenden Teilnehmer aus.";
	}
	
	let dialog = new frappe.ui.Dialog({
		title: 'Teilnehmer ohne Produktauswahl',
		fields: [
			{
				fieldtype: 'HTML',
				options: `<p style="margin-bottom: 15px;">${message.replace(/\n/g, '<br>')}</p>`
			}
		],
		primary_action_label: kann_entfernen ? __('Teilnehmer entfernen') : __('OK'),
		primary_action: function() {
			if (kann_entfernen) {
				// Entferne Gäste ohne Produkte (nicht die Gastgeberin)
				let gaeste_ohne_produkte = [];
				for (let i = 0; i < frm.doc.kunden.length; i++) {
					let kunde = frm.doc.kunden[i];
					if (!kunde.kunde) continue;
					
					let field_name = `produktauswahl_für_gast_${i+1}`;
					let hat_produkte = false;
					
					if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
						for (let produkt of frm.doc[field_name]) {
							if (produkt.item_code && produkt.qty && produkt.qty > 0) {
								hat_produkte = true;
								break;
							}
						}
					}
					
					if (!hat_produkte) {
						gaeste_ohne_produkte.push({
							index: i,
							name: kunde.kunde
						});
					}
				}
				
				// Entferne von hinten nach vorne
				gaeste_ohne_produkte.sort((a, b) => b.index - a.index);
				for (let gast of gaeste_ohne_produkte) {
					frm.get_field("kunden").grid.grid_rows[gast.index].remove();
				}
				
				frm.refresh_field("kunden");
				frappe.msgprint(`${gaeste_ohne_produkte.length} Gäste wurden entfernt.`, "Erfolgreich entfernt");
				
				// Prüfe, ob Aktionssystem verfügbar ist (über Client Script "discount_window_party")
				if (typeof discount_window_party === 'function') {
					// Aktionssystem ist verfügbar - prüfe Aktionen als letzten Schritt
					discount_window_party(frm, function() {
						// Aufträge erstellen (das Speichern wird in erstelleAuftraege() gemacht)
						erstelleAuftraege(frm);
					});
				} else {
					// Kein Aktionssystem verfügbar - direkt Aufträge erstellen
					erstelleAuftraege(frm);
				}
			}
			dialog.hide();
		}
	});
	
	if (kann_entfernen) {
		dialog.set_secondary_action_label(__('Bearbeiten'));
		dialog.set_secondary_action(function() {
			dialog.hide();
			// Dialog schließen, User kann Produkte hinzufügen
		});
	}
	
	dialog.show();
}

// Gutschein-System: Wendet Gastgeber-Gutschein auf aktionsfähige Produkte an
function applyGutscheinSystem(frm, callback) {
	console.log("applyGutscheinSystem gestartet");
	
	// Hole den Gutscheinwert des Gastgebers
	let gutscheinWert = frm.doc.gastgeber_gutschein_wert || 0;
	console.log("Verfügbarer Gutscheinwert:", gutscheinWert);
	
	if (gutscheinWert <= 0) {
		console.log("Kein Gutscheinwert verfügbar - überspringe Gutschein-System");
		callback();
		return;
	}
	
	// Sammle nur aktionsfähige Produkte vom GASTGEBER (nicht von den Gästen!)
	let gastgeberProdukte = [];
	
	// Funktion zum Sammeln der Produkte aus der Gastgeberin-Tabelle
	function sammleGastgeberProdukte() {
		if (frm.doc.gastgeberin && frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
			frm.doc.produktauswahl_für_gastgeberin.forEach((item, index) => {
				if (item.item_code && item.qty && item.qty > 0 && item.rate && item.rate > 0) {
					gastgeberProdukte.push({
						item: item,
						produktfeld: "produktauswahl_für_gastgeberin",
						tabellenName: "Gastgeberin",
						index: index,
						originalRate: item.rate,
						originalAmount: item.amount
					});
				}
			});
		}
	}
	
	// Sammle nur Produkte von der Gastgeberin (Gastgeber-Benefit!)
	sammleGastgeberProdukte();
	
	console.log("Gefundene Gastgeber-Produkte (vor Aktionsfähigkeits-Prüfung):", gastgeberProdukte.length);
	
	if (gastgeberProdukte.length === 0) {
		console.log("Gastgeber hat keine Produkte - überspringe Gutschein-System");
		callback();
		return;
	}
	
	// Prüfe jedes Gastgeber-Produkt auf Aktionsfähigkeit
	pruefeAktionsfaehigkeitAllerProdukte(gastgeberProdukte, 0, [], function(aktionsfaehigeGastgeberProdukte) {
		console.log("Aktionsfähige Gastgeber-Produkte:", aktionsfaehigeGastgeberProdukte.length);
		
		if (aktionsfaehigeGastgeberProdukte.length === 0) {
			console.log("Gastgeber hat keine aktionsfähigen Produkte - überspringe Gutschein-System");
			callback();
			return;
		}
		
		// Wende Gutschein nur auf Gastgeber-Produkte an (Gastgeber-Benefit!)
		wendeGutscheinAn(aktionsfaehigeGastgeberProdukte, gutscheinWert, frm, callback);
	});
}

// Prüft alle Produkte auf Aktionsfähigkeit (custom_considered_for_action = 1)
function pruefeAktionsfaehigkeitAllerProdukte(alleProdukte, index, aktionsfaehigeProdukte, callback) {
	if (index >= alleProdukte.length) {
		callback(aktionsfaehigeProdukte);
		return;
	}
	
	let produkt = alleProdukte[index];
	
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Item",
			filters: {
				item_code: produkt.item.item_code
			},
			fieldname: "custom_considered_for_action"
		},
		callback: function(r) {
					if (r.message && r.message.custom_considered_for_action) {
			console.log(`Gastgeber-Produkt ${produkt.item.item_code} ist aktionsfähig für Gutschein`);
			aktionsfaehigeProdukte.push(produkt);
		}
			
			// Nächstes Produkt prüfen
			pruefeAktionsfaehigkeitAllerProdukte(alleProdukte, index + 1, aktionsfaehigeProdukte, callback);
		}
	});
}

// Wendet den Gutschein von oben nach unten auf die Gastgeber-Produkte an
function wendeGutscheinAn(aktionsfaehigeGastgeberProdukte, verfuegbarerGutschein, frm, callback) {
	console.log("Wende Gutschein auf Gastgeber-Produkte an - Verfügbar:", verfuegbarerGutschein);
	
	let verbrauchterGutschein = 0;
	let angewendeteRabatte = [];
	
	// WICHTIG: Speichere die Original-Preise für mögliche Wiederherstellung
	if (!frm.originalPricesBackup) {
		frm.originalPricesBackup = {};
	}
	
	// Gehe von oben nach unten durch die Gastgeber-Produkte
	for (let i = 0; i < aktionsfaehigeGastgeberProdukte.length && verfuegbarerGutschein > verbrauchterGutschein; i++) {
		let produkt = aktionsfaehigeGastgeberProdukte[i];
		let produktWert = produkt.originalAmount;
		let restGutschein = verfuegbarerGutschein - verbrauchterGutschein;
		
		// Speichere Original-Preis für Wiederherstellung
		let backupKey = `${produkt.produktfeld}_${produkt.index}`;
		if (!frm.originalPricesBackup[backupKey]) {
			frm.originalPricesBackup[backupKey] = {
				originalRate: produkt.originalRate,
				originalAmount: produkt.originalAmount,
				item: produkt.item
			};
			console.log(`Original-Preis gespeichert für ${produkt.item.item_code}: ${produkt.originalRate}€`);
		}
		
		if (produktWert <= restGutschein) {
			// Komplette Reduktion auf 0
			let rabatt = produktWert;
			verbrauchterGutschein += rabatt;
			
			// Setze Preis auf 0
			produkt.item.rate = 0;
			produkt.item.amount = 0;
			
			angewendeteRabatte.push({
				produkt: produkt,
				rabatt: rabatt,
				neuerPreis: 0
			});
			
			console.log(`Gastgeber-Produkt ${produkt.item.item_code}: Vollständige Reduktion um ${rabatt}€ (auf 0€)`);
		} else {
			// Teilweise Reduktion
			let rabatt = restGutschein;
			verbrauchterGutschein += rabatt;
			
			let neuerPreis = (produktWert - rabatt) / produkt.item.qty;
			let neuerBetrag = produktWert - rabatt;
			
			// Setze neuen Preis
			produkt.item.rate = neuerPreis;
			produkt.item.amount = neuerBetrag;
			
			angewendeteRabatte.push({
				produkt: produkt,
				rabatt: rabatt,
				neuerPreis: neuerPreis
			});
			
			console.log(`Gastgeber-Produkt ${produkt.item.item_code}: Teilweise Reduktion um ${rabatt}€ (neuer Preis: ${neuerPreis}€)`);
			break; // Gutschein ist aufgebraucht
		}
	}
	
	// Aktualisiere alle betroffenen Tabellen
	let betroffeneTabellen = new Set();
	angewendeteRabatte.forEach(rabatt => {
		betroffeneTabellen.add(rabatt.produkt.produktfeld);
	});
	
	betroffeneTabellen.forEach(tabelle => {
		frm.refresh_field(tabelle);
	});
	
	// Berechne Gesamtsummen neu
	calculate_party_totals(frm);
	
	let restbetrag = verfuegbarerGutschein - verbrauchterGutschein;
	console.log("Gutschein angewendet - Verbraucht:", verbrauchterGutschein, "Restbetrag:", restbetrag);
	
	if (restbetrag > 0.01) { // Kleine Rundungsfehler ignorieren
		// Zeige Restbetrag-Dialog
		zeigeRestbetragDialog(restbetrag, frm, callback);
	} else {
		// Kein Restbetrag - weiter zum nächsten Schritt
		frappe.show_alert(`Gutschein vollständig angewendet: ${verbrauchterGutschein.toFixed(2)}€`, 3);
		// Original-Preise können gelöscht werden, da der Gutschein erfolgreich angewendet wurde
		frm.originalPricesBackup = {};
		callback();
	}
}

// Dialog für Restbetrag-Behandlung
function zeigeRestbetragDialog(restbetrag, frm, callback) {
	let dialog = new frappe.ui.Dialog({
		title: 'Gutschein-Restbetrag',
		fields: [
			{
				fieldtype: 'HTML',
				options: `
					<div style="margin-bottom: 15px;">
						<h4>Du hast noch ${restbetrag.toFixed(2)}€ Gutschrift übrig!</h4>
						<p>Der Gutschein konnte nicht vollständig auf die aktionsfähigen Produkte angewendet werden.</p>
						<p><strong>Was möchtest Du tun?</strong></p>
					</div>
				`
			}
		],
		primary_action_label: 'Zurück zur Bearbeitung',
		primary_action: function() {
			dialog.hide();
			// WICHTIG: Original-Preise wiederherstellen!
			stelleOriginalPreiseWieder(frm);
			
			// Zurück zur Party-Bearbeitung - kompletter Neustart
			frappe.msgprint({
				title: "Zurück zur Bearbeitung",
				message: "Die Original-Preise wurden wiederhergestellt. Du kannst jetzt weitere aktionsfähige Produkte hinzufügen und dann erneut 'Aufträge erstellen' klicken.",
				indicator: "blue"
			});
			// Buttons wieder herstellen
			refreshButtons(frm);
		},
		secondary_action_label: 'Restbetrag verfallen lassen',
		secondary_action: function() {
			dialog.hide();
			frappe.show_alert(`Restbetrag von ${restbetrag.toFixed(2)}€ verfällt`, 3);
			// Weiter zum nächsten Schritt
			callback();
		}
	});
	
	dialog.show();
}

// Stellt die Original-Preise aller Produkte wieder her
function stelleOriginalPreiseWieder(frm) {
	console.log("Stelle Original-Preise wieder her...");
	
	if (!frm.originalPricesBackup) {
		console.log("Keine Original-Preise zum Wiederherstellen gefunden");
		return;
	}
	
	let wiederhergestellteProdukte = 0;
	
	// Gehe durch alle gespeicherten Original-Preise
	for (let backupKey in frm.originalPricesBackup) {
		let backup = frm.originalPricesBackup[backupKey];
		let item = backup.item;
		
		// Stelle Original-Preis und -Betrag wieder her
		item.rate = backup.originalRate;
		item.amount = backup.originalAmount;
		
		console.log(`Original-Preis wiederhergestellt für ${item.item_code}: ${backup.originalRate}€`);
		wiederhergestellteProdukte++;
	}
	
	// Lösche das Backup, da es nicht mehr benötigt wird
	frm.originalPricesBackup = {};
	
	// Aktualisiere alle betroffenen Tabellen
	frm.refresh_field("produktauswahl_für_gastgeberin");
	
	// Berechne Gesamtsummen neu
	calculate_party_totals(frm);
	
	console.log(`${wiederhergestellteProdukte} Produkte auf Original-Preise zurückgesetzt`);
	frappe.show_alert(`${wiederhergestellteProdukte} Produkte auf Original-Preise zurückgesetzt`, 3);
}

// Hilfsfunktion zum Erstellen der Aufträge
function erstelleAuftraege(frm) {
	console.log("erstelleAuftraege aufgerufen");
	// Sofort Button deaktivieren, um Doppelklicks zu verhindern
	try {
		if (frm && frm.page) {
			if (frm.page.btn_primary) frm.page.btn_primary.hide();
			if (frm.page.clear_primary_action) frm.page.clear_primary_action();
			if (frm.page.clear_secondary_action) frm.page.clear_secondary_action();
			if (frm.page.clear_custom_actions) frm.page.clear_custom_actions();
		}
	} catch (e) {
		console.error("Fehler beim Deaktivieren der Buttons:", e);
	}
	
	// Erst speichern, dann Aufträge erstellen
	frappe.show_alert({
		message: __("Speichere aktuelle Änderungen..."),
		indicator: "blue"
	});
	
	console.log("Versuche Dokument zu speichern...");
	frm.save().then(() => {
		console.log("Dokument gespeichert - rufe create_invoices API auf");
		// Nach erfolgreichem Speichern die Aufträge erstellen
		frappe.call({
			method: "enjo_party.enjo_party.doctype.party.party.create_invoices",
			args: {
				party: frm.doc.name,
				from_button: true  // Flag, um zu zeigen, dass der Aufruf vom Button kommt
			},
			freeze: true,
			freeze_message: __("Erstelle Aufträge..."),
			callback: function(r) {
				console.log("API-Antwort erhalten:", r);
				if (r.message && r.message.length > 0) {
					frappe.msgprint({
						title: __("Erfolg"),
						message: __("Es wurden {0} Aufträge erstellt und eingereicht!", [r.message.length]),
						indicator: "green"
					});
					// Vollständiges Neuladen der Seite, um den Status zu aktualisieren
					setTimeout(function() {
						location.reload();
					}, 2000);
				} else {
					console.log("Keine Aufträge erstellt - refreshButtons wird aufgerufen");
					frappe.msgprint({
						title: __("Hinweis"),
						message: __("Es wurden keine Aufträge erstellt. Bitte überprüfen Sie, ob Produkte ausgewählt wurden."),
						indicator: "orange"
					});
					// Buttons wieder herstellen statt reload
					console.log("Keine Aufträge erstellt - refreshButtons wird aufgerufen");
					refreshButtons(frm);
				}
			},
			error: function(r) {
				console.log("API-Fehler aufgetreten - refreshButtons wird aufgerufen");
				// WICHTIG: Bei Fehlern Original-Preise wiederherstellen
				stelleOriginalPreiseWieder(frm);
				
				// Bei API-Fehlern
				frappe.msgprint({
					title: __("Fehler"),
					message: __("Es ist ein Fehler beim Erstellen der Aufträge aufgetreten. Die Original-Preise wurden wiederhergestellt. Bitte versuchen Sie es erneut."),
					indicator: "red"
				});
				// Buttons wieder herstellen
				console.log("API-Fehler - refreshButtons wird aufgerufen");
				refreshButtons(frm);
			}
		});
	}).catch((error) => {
		console.log("Speicherfehler aufgetreten:", error);
		console.log("Speicherfehler aufgetreten - refreshButtons wird aufgerufen");
		// WICHTIG: Bei Speicherfehlern Original-Preise wiederherstellen
		stelleOriginalPreiseWieder(frm);
		
		// Falls das Speichern fehlschlägt, Fehlermeldung anzeigen und Buttons wieder aktivieren
		frappe.msgprint({
			title: __("Fehler beim Speichern"),
			message: __("Das Dokument konnte nicht gespeichert werden. Die Original-Preise wurden wiederhergestellt. Bitte beheben Sie die Fehler und versuchen Sie es erneut."),
			indicator: "red"
		});
		// Buttons wieder herstellen statt reload
		console.log("Speicherfehler - refreshButtons wird aufgerufen");
		refreshButtons(frm);
	});
}

// Funktion zum Aktualisieren der benutzerdefinierten Überschriften
function updateCustomHeaders(frm) {
	if (!frm.doc.kunden) return;
	
	// Zuerst für die Gastgeberin, wenn vorhanden
	if (frm.doc.gastgeberin) {
		let sectionId = "produktauswahl_für_gastgeberin_section";
		let sectionHeader = document.querySelector(`[data-fieldname="${sectionId}"] .section-head`);
		
		if (sectionHeader) {
			// Hole den echten Kundennamen asynchron (wie bei den Gästen)
			frappe.db.get_doc('Customer', frm.doc.gastgeberin).then(customer_doc => {
				let kundenName = customer_doc.customer_name || frm.doc.gastgeberin;
				
				// Wende den Stil direkt auf das Kopfelement an
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
				frm.set_df_property('versand_gastgeberin', 'label', `Versand für ${kundenName} an:`);
			}).catch(error => {
				// Falls der Customer nicht gefunden wird, verwende die ID als Fallback
				console.log("Konnte Customer für Gastgeberin nicht laden:", error);
				sectionHeader.style.fontWeight = "500";
				sectionHeader.style.fontSize = "1em";
				sectionHeader.style.color = "#6C7680";
				
				if (!sectionHeader.querySelector('.custom-header')) {
					sectionHeader.innerHTML = `Produktauswahl für <span class="custom-header" style="font-weight: 600; color: #1F272E;">${frm.doc.gastgeberin}</span>`;
				} else {
					sectionHeader.querySelector('.custom-header').textContent = frm.doc.gastgeberin;
				}
				frm.set_df_property('versand_gastgeberin', 'label', `Versand für ${frm.doc.gastgeberin} an:`);
			});
		}
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
			// Hole den echten Kundennamen asynchron
			frappe.db.get_doc('Customer', kundeRow.kunde).then(customer_doc => {
				let kundenName = customer_doc.customer_name || kundeRow.kunde;
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
				frm.set_df_property(`versand_gast_${i}`, 'label', `Versand für ${kundenName} an:`);
			});
		}
	}
}

// Funktion zum Aktualisieren der Kunden-Filter
function updateKundenFilter(frm) {
	if (!frm.fields_dict["kunden"]) return;
	
	// Sammle alle bereits ausgewählten Kunden
	let selected_customers = [];
	if (frm.doc.kunden) {
		frm.doc.kunden.forEach(function(k) {
			if (k.kunde) {
				selected_customers.push(k.kunde);
			}
		});
	}
	
	// Setze den Filter für die Kunden-Tabelle
	frm.set_query("kunde", "kunden", function() {
		let filters = [["name", "!=", frm.doc.gastgeberin]];
		if (selected_customers.length > 0) {
			filters.push(["name", "not in", selected_customers]);
		}
		return { filters: filters };
	});
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

		// Automatisch leere Zeilen zu sichtbaren, leeren Produkttabellen hinzufügen
		setTimeout(() => {
			// Für Gastgeberin-Tabelle
			if (!frm.is_new() && frm.doc.gastgeberin) {
				if (!frm.doc.produktauswahl_für_gastgeberin || frm.doc.produktauswahl_für_gastgeberin.length === 0) {
					let row = frm.add_child('produktauswahl_für_gastgeberin');
					frm.refresh_field('produktauswahl_für_gastgeberin');
				}
			}
			
			// Für Gäste-Tabellen
			for (let i = 1; i <= 15; i++) {
				if (!frm.is_new() && frm.doc.kunden && frm.doc.kunden.length >= i) {
					let field_name = `produktauswahl_für_gast_${i}`;
					if (!frm.doc[field_name] || frm.doc[field_name].length === 0) {
						let row = frm.add_child(field_name);
						frm.refresh_field(field_name);
					}
				}
			}
		}, 100);

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
		let promises = [];
		if (frm.doc.gastgeberin) {
			promises.push(
				frappe.db.get_doc('Customer', frm.doc.gastgeberin).then(doc => {
					optionen.push({ value: frm.doc.gastgeberin, label: doc.customer_name });
				})
			);
		}
		// Partnerin wird NICHT als Customer abgefragt!
		// Die Partnerin kann als Versandziel nicht ausgewählt werden
		if (frm.doc.kunden && frm.doc.kunden.length > 0) {
			frm.doc.kunden.forEach(function(kunde) {
				if (kunde.kunde) {
					promises.push(
						frappe.db.get_doc('Customer', kunde.kunde).then(doc => {
							optionen.push({ value: kunde.kunde, label: doc.customer_name });
						})
					);
				}
			});
		}
		Promise.all(promises).then(() => {
			for (let i = 1; i <= 15; i++) {
				frm.set_df_property(`versand_gast_${i}`, 'options', optionen);
			}
			frm.set_df_property('versand_gastgeberin', 'options', optionen);
		});
		
		// Verstecke das Datum-Feld in allen Produktauswahl-Tabellen und setze Item-Filter
		for (let i = 1; i <= 15; i++) {
			const fieldName = `produktauswahl_für_gast_${i}`;
			if (frm.fields_dict[fieldName]) {
				// Verstecke das Datum-Feld in der Tabelle (damit kein Kalender erscheint)
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'hidden', 1);
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'reqd', 0);
				
				// Setze Filter für Item-Auswahl (nur Sales Items, nicht disabled)
				if (frm.fields_dict[fieldName].grid.get_field('item_code')) {
					frm.fields_dict[fieldName].grid.get_field('item_code').get_query = function() {
						return {
							filters: {
								'is_sales_item': 1,
								'disabled': 0
							}
						};
					};
				}
			}
		}
		
		// Auch für die Gastgeberin-Tabelle
		if (frm.fields_dict["produktauswahl_für_gastgeberin"]) {
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('delivery_date', 'hidden', 1);
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('delivery_date', 'reqd', 0);
			
			// Setze Filter für Item-Auswahl
			if (frm.fields_dict["produktauswahl_für_gastgeberin"].grid.get_field('item_code')) {
				frm.fields_dict["produktauswahl_für_gastgeberin"].grid.get_field('item_code').get_query = function() {
					return {
						filters: {
							'is_sales_item': 1,
							'disabled': 0
						}
					};
				};
			}
		}
		
		// Standard-Submit-Button ausblenden - aber nur wenn nicht im Neu-Modus
		if (!frm.is_new() && frm.page && frm.page.btn_primary) {
			frm.page.btn_primary.hide();
		}
		
		// Komplett das Aktionen-Dropdown ausblenden, aber NUR für Party-Formulare
		setTimeout(() => {
			try {
				// Aktionen-Button nur im aktuellen Formular ausblenden
				$(frm.wrapper).find('.actions-btn-group').hide();
				// Alternative Methode, falls die erste nicht funktioniert
				$(frm.wrapper).find('.dropdown-btn[data-label="Aktionen"]').hide();
			} catch (e) {
				console.error("Fehler beim Ausblenden der Aktionsbuttons:", e);
			}
		}, 300);
		
		// Custom Buttons basierend auf dem Status anzeigen - verwende die zentrale Funktion
		// Verzögere den Aufruf, damit alle anderen Initialisierungen abgeschlossen sind
		setTimeout(() => {
			refreshButtons(frm);
		}, 200);
		
		if (frm.doc.docstatus === 1) {
			// Dokument ist eingereicht/abgeschlossen
			// Keine Änderungen mehr möglich
			frm.disable_save();
		}
	},
	
	// Füge einen Event-Handler für die Gastgeberin hinzu
	gastgeberin: function(frm) {
		// Wenn die Gastgeberin geändert wird, setze sie als Standard für den Versand
		if (frm.doc.gastgeberin) {
			// Aktualisiere das Label für die Gastgeberin
			frm.set_df_property('versand_gastgeberin', 'label', `Versand für ${frm.doc.gastgeberin} an:`);
			
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
		let promises = [];
		if (frm.doc.gastgeberin) {
			promises.push(
				frappe.db.get_doc('Customer', frm.doc.gastgeberin).then(doc => {
					optionen.push({ value: frm.doc.gastgeberin, label: doc.customer_name });
				})
			);
		}
		// Partnerin wird NICHT als Versandoption hinzugefügt, da sie kein Kunde ist
		if (frm.doc.kunden && frm.doc.kunden.length > 0) {
			frm.doc.kunden.forEach(function(kunde) {
				if (kunde.kunde && !optionen.some(opt => opt.value === kunde.kunde)) {
					promises.push(
						frappe.db.get_doc('Customer', kunde.kunde).then(doc => {
							optionen.push({ value: kunde.kunde, label: doc.customer_name });
						})
					);
				}
			});
		}
		
		Promise.all(promises).then(() => {
			for (let i = 1; i <= 15; i++) {
				frm.set_df_property(`versand_gast_${i}`, 'options', optionen);
			}
			frm.set_df_property('versand_gastgeberin', 'options', optionen);
		});
		
		// Aktualisiere die Kunden-Tabelle, um Gastgeberin aus den Optionen zu entfernen
		if (frm.doc.gastgeberin && frm.fields_dict["kunden"]) {
			frm.set_query("kunde", "kunden", function() {
				return {
					filters: {
						"name": ["!=", frm.doc.gastgeberin]
					}
				};
			});
		}
	},
	
	onload: function(frm) {
		// Automatisch Datum auf heute setzen
		if (frm.is_new() && !frm.doc.party_date) {
			frm.set_value('party_date', frappe.datetime.get_today());
		}
		
		// Automatisch Partnerin setzen, wenn der aktuelle Benutzer als Sales Partner existiert
		if (frm.is_new() && !frm.doc.partnerin) {
			// Hole den aktuellen Benutzernamen
			let current_user = frappe.session.user_fullname || frappe.session.user;
			
			// Prüfe, ob ein Sales Partner mit diesem Namen existiert
			frappe.db.get_list('Sales Partner', {
				filters: {
					'partner_name': current_user
				},
				fields: ['name', 'partner_name'],
				limit: 1
			}).then(partners => {
				if (partners && partners.length > 0) {
					// Setze den gefundenen Sales Partner als Partnerin (ohne Benachrichtigung)
					frm.set_value('partnerin', partners[0].name);
				}
			}).catch(error => {
				// Fehler beim Suchen ignorieren (z.B. wenn keine Berechtigung)
				console.log("Konnte nicht nach Sales Partner suchen:", error);
			});
		}
		
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
		
		// Filtere Gastgeberin aus Kunden-Dropdown
		if (frm.doc.gastgeberin && frm.fields_dict["kunden"]) {
			frm.set_query("kunde", "kunden", function() {
				return {
					filters: {
						"name": ["!=", frm.doc.gastgeberin]
					}
				};
			});
		}
		
		// Überschreibe den Standard-Bestätigungstext für den Submit-Dialog
		frm.confirm_on_submit = __("Bist Du sicher, dass alle Produkte richtig ausgewählt wurden und Du die Bestellung abschicken möchtest? Dieser Vorgang kann nicht rückgängig gemacht werden!");
		
		// Initiale Filterung
		updateKundenFilter(frm);
	},
	
	// Nach dem Speichern automatisch die Preise für alle leeren Produkte laden
	after_save(frm) {
		if (frm.doc.docstatus === 0) {
			refresh_item_prices(frm);
			// Berechne auch die Gesamtsummen neu
			calculate_party_totals(frm);
		}
	},
	
	// Aktualisiere auch wenn Kunden hinzugefügt oder entfernt werden
	kunden_add: function(frm) {
		setTimeout(() => {
			updateCustomHeaders(frm);
			updateKundenFilter(frm);
		}, 500);
	},
	kunden_remove: function(frm) {
		setTimeout(() => {
			updateCustomHeaders(frm);
			updateKundenFilter(frm);
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
			frm.set_df_property(`versand_gast_${idx}`, 'label', `Versand für ${row.kunde} an:`);
		}
		
		// Aktualisiere die benutzerdefinierten Header und Filter
		setTimeout(() => {
			updateCustomHeaders(frm);
			updateKundenFilter(frm);
		}, 500);
	}
});

// Event-Handler für Sales Order Item - Nur Menge automatisch auf 1 setzen
frappe.ui.form.on('Sales Order Item', {
	item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_code && !row.qty) {
			frappe.model.set_value(cdt, cdn, 'qty', 1);
			
			// Holen der Item-Details und Setzen der UOM-Felder
			frappe.db.get_doc("Item", row.item_code)
				.then(item_doc => {
					// UOM Felder setzen
					frappe.model.set_value(cdt, cdn, 'uom', item_doc.stock_uom);
					frappe.model.set_value(cdt, cdn, 'stock_uom', item_doc.stock_uom);
					frappe.model.set_value(cdt, cdn, 'conversion_factor', 1.0);
					frappe.model.set_value(cdt, cdn, 'uom_conversion_factor', 1.0);
					
					// Item Name setzen
					if (!row.item_name) {
						frappe.model.set_value(cdt, cdn, 'item_name', item_doc.item_name);
					}
					
					// Weitere erforderliche Felder
					if (!row.stock_qty) {
						let stock_qty = parseFloat(row.qty || 0) * 1.0;
						frappe.model.set_value(cdt, cdn, 'stock_qty', stock_qty);
					}
				});
		}
		
		// Automatisch Preis laden (immer, auch wenn schon einer vorhanden ist)
		if (row.item_code) {
			get_item_price(frm, row);
		}
	},
	qty: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		// Berechne den Betrag neu, wenn sich die Menge ändert
		if (row.qty && row.rate) {
			row.amount = flt(row.qty) * flt(row.rate);
			row.base_amount = row.amount;
			frm.refresh_field(row.parentfield);
			// Berechne auch die Gesamtsummen neu
			calculate_party_totals(frm);
		}
	},
	rate: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		// Berechne den Betrag neu, wenn sich der Preis ändert
		if (row.qty && row.rate) {
			row.amount = flt(row.qty) * flt(row.rate);
			row.base_amount = row.amount;
			frm.refresh_field(row.parentfield);
			// Berechne auch die Gesamtsummen neu
			calculate_party_totals(frm);
		}
	}
});



// Funktion, um alle Tabellen mit Preisen zu aktualisieren
function refresh_item_prices(frm) {
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

				// Berechne den Betrag (amount = qty * rate)
				if (row.qty && row.rate) {
					row.amount = flt(row.qty) * flt(row.rate);
					row.base_amount = row.amount;
				}

				frm.refresh_field(row.parentfield);
				console.log(`Preis für ${row.item_code} auf ${row.rate} gesetzt, Betrag: ${row.amount}`);
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

// Funktion zur Berechnung der Party-Gesamtsummen
function calculate_party_totals(frm) {
	let total_amount = 0.0;
	
	// Berechne Gesamtumsatz aus allen Produkttabellen
	for (let i = 1; i <= 15; i++) {
		const field_name = `produktauswahl_für_gast_${i}`;
		if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
			frm.doc[field_name].forEach(function(item) {
				if (item.qty && item.rate) {
					total_amount += flt(item.qty) * flt(item.rate);
				}
			});
		}
	}
	
	// Auch Gastgeberin-Tabelle berücksichtigen
	if (frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
		frm.doc.produktauswahl_für_gastgeberin.forEach(function(item) {
			if (item.qty && item.rate) {
				total_amount += flt(item.qty) * flt(item.rate);
			}
		});
	}
	
	// Setze Gesamtumsatz
	frm.set_value('gesamtumsatz', total_amount);
	
	// Berechne Gutscheinwert basierend auf Präsentationsumsatz-Stufen
	const gutschein_wert = calculate_gutschein_value(total_amount);
	frm.set_value('gastgeber_gutschein_wert', gutschein_wert);
}

// Funktion zur Berechnung des Gutscheinwerts basierend auf Präsentationsumsatz-Stufen
function calculate_gutschein_value(total_amount) {
	// Präsentationsumsatz-Stufen für Gratisprodukte
	// Format: [Mindest-Umsatz, Gutschein-Betrag]
	const gutschein_stufen = [
		[0, 0],      // Unter 350€: 0€ Gutschein
		[350, 30],   // Ab 350€: 30€ Gutschein
		[600, 60],   // Ab 600€: 60€ Gutschein
		[850, 95],   // Ab 850€: 95€ Gutschein
		[1100, 130], // Ab 1100€: 130€ Gutschein
	];
	
	// Finde die passende Stufe
	let gutschein_wert = 0;
	for (let i = 0; i < gutschein_stufen.length; i++) {
		const [mindest_umsatz, gutschein_betrag] = gutschein_stufen[i];
		if (total_amount >= mindest_umsatz) {
			gutschein_wert = gutschein_betrag;
		} else {
			break;
		}
	}
	
	return gutschein_wert;
}

