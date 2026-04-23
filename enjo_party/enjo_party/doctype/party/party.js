// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

// === STÖRENDE BENUTZER-MELDUNGEN AUSBLENDEN ===
// Filtere nur Benutzer-sichtbare Meldungen, Console-Logs für Entwickler bleiben
(function() {
	try {
		// Original frappe.msgprint sichern
		const originalMsgprint = frappe.msgprint;
		const originalThrow = frappe.throw;
		const originalShowAlert = frappe.show_alert;
		
		// Überschreibe frappe.msgprint um störende Meldungen zu filtern
		frappe.msgprint = function(message, title, indicator) {
			// Prüfe ob es sich um eine störende Meldung handelt
			let messageText = typeof message === 'string' ? message : 
							 (message && message.message) ? message.message : '';
			
			if (
				// Adress-Fehlermeldungen filtern
				messageText.includes('Adresse') && messageText.includes('nicht gefunden') ||
				messageText.includes('Address') && messageText.includes('not found') ||
				messageText.includes('Die Lieferadresse gehört nicht zu') ||
				// Source Map und Bundle-Fehlermeldungen
				messageText.includes('Source Map') ||
				messageText.includes('file_uploader.bundle') ||
				messageText.includes('JSON Parse error') ||
				// localStorage Meldungen
				messageText.includes('localStorage quota exceeded') ||
				// Auftrag bereits vorhanden Meldungen
				messageText.includes('bereits vorhanden') ||
				messageText.includes('zu Kunden-Bestellung bereits vorhanden')
			) {
				// Diese Meldungen nicht dem Benutzer zeigen
				console.log("GEFILTERTE BENUTZER-MELDUNG:", messageText);
				return;
			}
			
			// Alle anderen Meldungen normal anzeigen
			return originalMsgprint.apply(this, arguments);
		};
		
		// Überschreibe frappe.show_alert um störende Alerts zu filtern
		frappe.show_alert = function(message, seconds) {
			let messageText = typeof message === 'string' ? message : 
							 (message && message.message) ? message.message : '';
			
			if (
				messageText.includes('Adresse') && messageText.includes('nicht gefunden') ||
				messageText.includes('Address') && messageText.includes('not found') ||
				messageText.includes('Source Map') ||
				messageText.includes('file_uploader.bundle')
			) {
				// Diese Alerts nicht dem Benutzer zeigen
				console.log("GEFILTERTER ALERT:", messageText);
				return;
			}
			
			// Alle anderen Alerts normal anzeigen
			return originalShowAlert.apply(this, arguments);
		};
		
		console.log("Benutzer-Meldungsfilter für störende Frappe-Fehler aktiviert");
	} catch (e) {
		// Falls das Filtern fehlschlägt, normal weiter
		console.log("Benutzer-Meldungsfilter konnte nicht aktiviert werden:", e);
	}
})();

// === ENDE MELDUNGSFILTER ===

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
			console.log("Status Produkte: Gastgeber Geschenke + Speichern Buttons hinzufügen");
			// Status "Produkte": Nur "Gastgeber Geschenke"-Button (Aufträge erstellen wird erst im nächsten Schritt angezeigt)
			frm.add_custom_button(__("Gastgeber Geschenke"), function() {
				// Bestätigungsdialog anzeigen
				frappe.confirm(
					__("Damit schließt Du die Produktauswahl ab. Änderungen an den bisherigen Produkten sind danach nicht mehr möglich. Fortfahren?"),
					function() {
						// Benutzer hat "Ja" geklickt
						console.log("Benutzer hat Gastgeber Geschenke bestätigt");
						
						// WICHTIG: Erst Aktions-System durchführen, DANN zur Gastgeber-Geschenke-Tabelle wechseln
						console.log("Starte Aktions-System vor Wechsel zu Gastgeber Geschenke");
						startAktionsSystem(frm, function() {
							console.log("Aktions-System abgeschlossen - wechsle zu Gastgeber Geschenke");
							
				// Status zu "Geschenke" ändern
				frm.set_value("status", "Geschenke");
				
							// SOFORT alle anderen Produkttabellen ausblenden
							frm.toggle_display('produktauswahl_für_gastgeberin_section', false);
							for (let i = 1; i <= 15; i++) {
								frm.toggle_display(`produktauswahl_für_gast_${i}_section`, false);
							}
							
							// SOFORT Gastgebergeschenke-Tabelle einblenden
							frm.toggle_display('gastgeber_geschenke_section', true);
							frm.toggle_display('gastgeber_geschenke', true);
							
							// Tabelle rendern, falls sie noch nicht gerendert wurde
				if (frm.fields_dict['gastgeber_geschenke']) {
								frm.refresh_field('gastgeber_geschenke');
							}
							
							// Automatisch eine leere Zeile hinzufügen, wenn die Tabelle leer ist
							if (!frm.doc.gastgeber_geschenke || frm.doc.gastgeber_geschenke.length === 0) {
								let row = frm.add_child('gastgeber_geschenke');
								frm.refresh_field('gastgeber_geschenke');
								console.log("Leere Zeile zu Gastgeber Geschenke Tabelle hinzugefügt");
							}
							
							// Speichern
							frm.save().then(() => {
								// Nach dem Speichern nochmal sicherstellen
								frm.toggle_display('produktauswahl_für_gastgeberin_section', false);
								for (let i = 1; i <= 15; i++) {
									frm.toggle_display(`produktauswahl_für_gast_${i}_section`, false);
								}
								frm.toggle_display('gastgeber_geschenke_section', true);
								frm.toggle_display('gastgeber_geschenke', true);
								if (frm.fields_dict['gastgeber_geschenke']) {
									frm.refresh_field('gastgeber_geschenke');
				}
				
								// Nach dem Speichern nochmal prüfen ob eine leere Zeile da ist
								if (!frm.doc.gastgeber_geschenke || frm.doc.gastgeber_geschenke.length === 0) {
									let row = frm.add_child('gastgeber_geschenke');
									frm.refresh_field('gastgeber_geschenke');
									console.log("Leere Zeile nach Speichern zu Gastgeber Geschenke Tabelle hinzugefügt");
								}
							});
						});
					},
					function() {
						// Benutzer hat "Nein" geklickt - nichts tun
						console.log("Benutzer hat Gastgeber Geschenke abgelehnt - bleibe im Produkte-Status");
					}
				);
			}).addClass("btn-primary");
			
			// Auch einen Speichern-Button anzeigen (ohne Primärfarbe)
			frm.add_custom_button(__("Speichern"), function() {
				frm.save();
			});
		} else if (frm.doc.status === "Geschenke") {
			console.log("Status Gastgeber Geschenke: Aufträge erstellen + Speichern Buttons hinzufügen");
			// Status "Gastgeber Geschenke": Speichern und "Aufträge erstellen"-Button
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
		// Für gebuchte Parties: "Zu den Aufträgen" und "Zu den Rechnungen" Buttons anzeigen
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Zu den Aufträgen"), function() {
				frappe.set_route("List", "Sales Order", {
					"custom_party_reference": frm.doc.name
				});
			});

			frm.add_custom_button(__("Zu den Rechnungen"), function() {
				frappe.set_route("List", "Sales Invoice", {
					"custom_party_reference": frm.doc.name
				});
			});
		}
	}
}

// Hilfsfunktion zum Starten der Aufträge-Erstellung (ohne Button-Manipulation)
function startAuftraegeErstellung(frm) {
	console.log("startAuftraegeErstellung aufgerufen");
	
	// Aktiviere Pflichtfelder für die Validierung
	enableRequiredFields(frm);
	
	// Erst prüfen, ob alle Teilnehmer Produkte haben
	let teilnehmer_ohne_produkte = [];
	
	// Hilfsfunktion zum Abrufen des Kundennamens
	function getCustomerName(customerId) {
		let result = frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Customer",
				filters: { name: customerId },
				fieldname: "customer_name"
			},
			async: false
		});
		return result.message?.customer_name || customerId;
	}
	
	// Prüfe Gastgeberin
	// WICHTIG: Gastgeberin hat Produkte, wenn sie in produktauswahl_für_gastgeberin ODER gastgeber_geschenke Produkte hat
	if (frm.doc.gastgeberin) {
		let hat_gastgeberin_produkte = false;
		// Prüfe produktauswahl_für_gastgeberin
		if (frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
			for (let produkt of frm.doc.produktauswahl_für_gastgeberin) {
				// Nur gefüllte Zeilen prüfen
				if (produkt.item_code && produkt.qty && produkt.qty > 0) {
					hat_gastgeberin_produkte = true;
					break;
				}
			}
		}
		// Prüfe auch gastgeber_geschenke (falls noch keine Produkte gefunden)
		if (!hat_gastgeberin_produkte && frm.doc.gastgeber_geschenke && frm.doc.gastgeber_geschenke.length > 0) {
			for (let produkt of frm.doc.gastgeber_geschenke) {
				// Nur gefüllte Zeilen prüfen
				if (produkt.item_code && produkt.qty && produkt.qty > 0) {
					hat_gastgeberin_produkte = true;
					break;
				}
			}
		}
		
		if (!hat_gastgeberin_produkte) {
			teilnehmer_ohne_produkte.push(`${getCustomerName(frm.doc.gastgeberin)} (Gastgeberin)`);
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
				// Nur gefüllte Zeilen prüfen
				if (produkt.item_code && produkt.qty && produkt.qty > 0) {
					hat_produkte = true;
					break;
				}
			}
		}
		
		if (!hat_produkte) {
			teilnehmer_ohne_produkte.push(getCustomerName(kunde.kunde));
		}
	}
	
	console.log("Teilnehmer ohne Produkte:", teilnehmer_ohne_produkte);
	
	// Wenn alle Teilnehmer Produkte haben, prüfe Aktionen vor der Bestätigung
	if (teilnehmer_ohne_produkte.length === 0) {
		console.log("Alle Teilnehmer haben Produkte - zeige Bestätigungsdialog");
		frappe.confirm(
			__("Bist Du sicher, dass alle Produkte richtig ausgewählt wurden und Du die Bestellung abschicken möchtest? Dieser Vorgang kann nicht rückgängig gemacht werden!"),
			function() {
				console.log("Benutzer hat bestätigt - starte Gutschein-System");
				// WICHTIG: Aktions-System wurde bereits beim "Gastgeber Geschenke" Button durchgeführt
				// Jetzt nur noch Gutschein-System anwenden, dann Aufträge erstellen
				console.log("Starte Gutschein-System");
				applyGutscheinSystem(frm, function() {
					console.log("Gutschein-System abgeschlossen - erstelle Aufträge");
					// Nach Gutschein-System Aufträge erstellen
						erstelleAuftraege(frm);
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
							// Nur gefüllte Zeilen prüfen
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
				// ENTFERNT: frappe.msgprint(`${gaeste_ohne_produkte.length} Gäste wurden entfernt.`, "Erfolgreich entfernt");
				
				// WICHTIG: Auch hier das Gutschein-System durchlaufen, nicht direkt zum Aktions-System!
				console.log("Starte Gutschein-System nach Gäste-Entfernung");
				applyGutscheinSystem(frm, function() {
					console.log("Gutschein-System abgeschlossen - starte Aktions-System");
					// Aktions-System aufrufen
					startAktionsSystem(frm, function() {
						console.log("Aktions-System abgeschlossen - erstelle Aufträge");
						// Aufträge erstellen
						erstelleAuftraege(frm);
					});
				});
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

// Aktions-System: Prüft alle Teilnehmer auf Aktionsberechtigung und zeigt Dialog
function startAktionsSystem(frm, callback) {
	console.log("startAktionsSystem gestartet");
	
	// WICHTIG: Lade die Aktionseinstellungen dynamisch aus der Datenbank
	frappe.call({
		method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
		callback: function(r) {
			if (!r.message) {
				console.error("Konnte Aktionseinstellungen nicht laden");
				callback(); // Fallback: Weiter ohne Aktion
				return;
			}
			
			let settings = r.message;
			console.log("Aktionseinstellungen geladen:", settings);
			
			// Schwellwerte aus den Einstellungen
			const STAGE_1_MIN = settings.stage_1_minimum;
			const STAGE_1_MAX = settings.stage_1_maximum;
			
			// Dynamische Varianten aus den Einstellungen (neues Schema)
			const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
			const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
			
			const allStandardCodes = standardVariants.map(v => v.code).filter(Boolean);
			const allPremiumCodes = premiumVariants.map(v => v.code).filter(Boolean);
			const allAktionsCodes = [...allStandardCodes, ...allPremiumCodes];
			
			// Jetzt die eigentliche Aktions-Logik mit den geladenen Einstellungen
			processAktionsSystemWithSettings();
			
			function processAktionsSystemWithSettings() {
				// Sammle alle Teilnehmer und ihre Produkttabellen
				let teilnehmerMitProdukten = [];
				
				// Gastgeberin hinzufügen
				if (frm.doc.gastgeberin && frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
					// Hole Gastgeberin-Name
					frappe.call({
						method: "frappe.client.get_value",
						args: {
							doctype: "Customer",
							filters: {
								name: frm.doc.gastgeberin
							},
							fieldname: "customer_name"
						},
						async: false,
						callback: function(r) {
							let gastgeberinName = r.message ? r.message.customer_name : frm.doc.gastgeberin;
							teilnehmerMitProdukten.push({
								name: frm.doc.gastgeberin,
								displayName: gastgeberinName,
								typ: "Gastgeberin",
								produktfeld: "produktauswahl_für_gastgeberin",
								produkte: frm.doc.produktauswahl_für_gastgeberin
							});
						}
					});
				}
				
				// Alle Gäste hinzufügen
				let gastePromises = [];
				for (let i = 0; i < frm.doc.kunden.length; i++) {
					let kunde = frm.doc.kunden[i];
					if (!kunde.kunde) continue;
					
					let field_name = `produktauswahl_für_gast_${i+1}`;
					if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
						let hatProdukte = frm.doc[field_name].some(item => item.item_code && item.qty && item.qty > 0);
						if (hatProdukte) {
							// Hole Gast-Name
							let promise = new Promise((resolve) => {
								frappe.call({
									method: "frappe.client.get_value",
									args: {
										doctype: "Customer",
										filters: {
											name: kunde.kunde
										},
										fieldname: "customer_name"
									},
									callback: function(r) {
										let gastName = r.message ? r.message.customer_name : kunde.kunde;
										teilnehmerMitProdukten.push({
											name: kunde.kunde,
											displayName: gastName,
											typ: "Gast",
											gastNummer: i + 1,
											produktfeld: field_name,
											produkte: frm.doc[field_name]
										});
										resolve();
									}
								});
							});
							gastePromises.push(promise);
						}
					}
				}
				
				// Warte auf alle Gast-Namen
				Promise.all(gastePromises).then(() => {
					console.log("Gefundene Teilnehmer mit Produkten:", teilnehmerMitProdukten.length);
					
					if (teilnehmerMitProdukten.length === 0) {
						console.log("Keine Teilnehmer mit Produkten gefunden - überspringe Aktions-System");
						callback();
						return;
					}
					
					// Prüfe jeden Teilnehmer auf Aktionsberechtigung
					checkTeilnehmerForAction(teilnehmerMitProdukten, 0, []);
				});
			}
			
			function checkTeilnehmerForAction(teilnehmer, index, aktionsberechtigteTeilnehmer) {
				if (index >= teilnehmer.length) {
					console.log("Aktionsberechtigte Teilnehmer:", aktionsberechtigteTeilnehmer.length);
					
					if (aktionsberechtigteTeilnehmer.length > 0) {
						showAktionsDialog(aktionsberechtigteTeilnehmer);
					} else {
						console.log("Keine aktionsberechtigten Teilnehmer gefunden - fahre direkt mit Aufträge-Erstellung fort");
						// WICHTIG: Markiere dass KEINE Aktionsartikel hinzugefügt wurden
						frm._keineAktionsartikelHinzugefuegt = true;
						// Cleanup der Backup-Variablen auch wenn keine Aktion verfügbar
						delete frm._originalGesamtumsatz;
						delete frm._originalProductAmounts;
						console.log("Keine Aktionen verfügbar - Backup-Variablen aufgeräumt");
						// WICHTIG: Auch wenn keine Aktion verfügbar ist, müssen die Aufträge erstellt werden!
						callback();
					}
					return;
				}
				
				let teilnehmer_obj = teilnehmer[index];
				console.log(`Prüfe Teilnehmer: ${teilnehmer_obj.displayName} (${teilnehmer_obj.typ})`);
				
				checkItemsForAction(teilnehmer_obj.produkte, 0, [], 0, teilnehmer_obj);
				
				function checkItemsForAction(items, itemIndex, actionItems, total, teilnehmer_obj) {
					if (itemIndex >= items.length) {
						console.log(`${teilnehmer_obj.displayName}: ${actionItems.length} aktionsfähige Items, Summe: ${total}`);
						
						let hasAktionsartikel = items.some(item => allAktionsCodes.includes(item.item_code));
						
						if (actionItems.length > 0 && !hasAktionsartikel) {
							let stage = null;
							if (total >= STAGE_1_MAX) {
								stage = 2; // Premium
							} else if (total >= STAGE_1_MIN) {
								stage = 1; // Standard
							}
							
							if (stage) {
								aktionsberechtigteTeilnehmer.push({
									...teilnehmer_obj,
									aktionssumme: total,
									stage: stage,
									aktionsItems: actionItems
								});
							}
						}
						
						checkTeilnehmerForAction(teilnehmer, index + 1, aktionsberechtigteTeilnehmer);
						return;
					}
					
					let item = items[itemIndex];
					
					if (!item.item_code || !item.qty || item.qty <= 0) {
						checkItemsForAction(items, itemIndex + 1, actionItems, total, teilnehmer_obj);
						return;
					}
					
					frappe.call({
						method: "frappe.client.get_value",
						args: {
							doctype: "Item",
							filters: {
								item_code: item.item_code
							},
							fieldname: "custom_considered_for_action"
						},
						callback: function(r) {
							if (r.message && r.message.custom_considered_for_action) {
								actionItems.push(item);
								
								// WICHTIG: Für Aktionsberechnung ursprünglichen Betrag verwenden (vor Gutschein-Reduktion)
								let key = `${teilnehmer_obj.produktfeld}_${itemIndex}`;
								let originalAmount = frm._originalProductAmounts?.[key];
								let amountForAction = originalAmount || item.amount || 0;
								
								total += amountForAction;
								console.log(`${teilnehmer_obj.displayName}: Item ${item.item_code} aktionsfähig (Original: ${originalAmount || 'n/a'}, Aktuell: ${item.amount || 0}, Für Aktion: ${amountForAction} EUR)`);
							}
							
							checkItemsForAction(items, itemIndex + 1, actionItems, total, teilnehmer_obj);
						}
					});
				}
			}
			
			function showAktionsDialog(aktionsberechtigteTeilnehmer) {
				console.log("Zeige Aktions-Dialog für", aktionsberechtigteTeilnehmer.length, "Teilnehmer");
				
				let dialogFields = [
					{
						fieldtype: 'HTML',
						fieldname: 'description',
						options: `
							<div style="margin-bottom: 15px;">
								<h4>Herzlichen Glückwunsch!</h4>
								<p>Die folgenden Teilnehmer sind für unsere aktuelle Aktion berechtigt:</p>
							</div>
						`
					}
				];
				
				aktionsberechtigteTeilnehmer.forEach((teilnehmer, index) => {
					let optionen = [];
					let stageText = "";
					
					if (teilnehmer.stage === 1) {
						optionen = [""].concat(standardVariants.map(v => v.name || v.code).filter(Boolean));
						stageText = "Standard";
					} else if (teilnehmer.stage === 2) {
						optionen = [""].concat(premiumVariants.map(v => v.name || v.code).filter(Boolean));
						stageText = "Premium";
					}
					
					dialogFields.push({
						fieldtype: 'HTML',
						fieldname: `teilnehmer_info_${index}`,
						options: `
							<div style="margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
								<strong>${teilnehmer.displayName}</strong><br>
								<small>Aktionssumme: ${teilnehmer.aktionssumme.toFixed(2)} EUR - ${stageText} Aktion</small>
							</div>
						`
					});
					
					dialogFields.push({
						fieldtype: 'Select',
						fieldname: `aktion_artikel_${index}`,
						label: `Aktionsartikel für ${teilnehmer.displayName}`,
						options: optionen,
						default: ""
					});
				});
				
				dialogFields.push({
					fieldtype: 'HTML',
					fieldname: 'footer_info',
					options: `
						<div style="margin-top: 15px; padding: 10px; background-color: #fff3cd; border-radius: 5px;">
							<small><strong>Hinweis:</strong> Leer lassen = "Nein, danke" - die Aktion verfällt für diesen Teilnehmer unwiderruflich.</small>
						</div>
					`
				});
				
				let d = new frappe.ui.Dialog({
					title: 'Aktions-System',
					fields: dialogFields,
					size: 'large',
					primary_action_label: 'Aktionsartikel hinzufügen',
					primary_action: function() {
						let values = d.get_values();
						console.log("Dialog-Werte:", values);
						
						let aktionsartikelHinzugefuegt = 0;
						let verarbeitungsPromises = [];
						
						aktionsberechtigteTeilnehmer.forEach((teilnehmer, index) => {
							let selectedItem = values[`aktion_artikel_${index}`];
							
							if (selectedItem && selectedItem.trim() !== "") {
								console.log(`${teilnehmer.displayName} hat gewählt: ${selectedItem}`);
								
								let itemCode = getItemCodeFromName(selectedItem);
								
								if (itemCode) {
									let promise = addAktionsartikelToTeilnehmer(teilnehmer, itemCode, selectedItem);
									verarbeitungsPromises.push(promise);
									aktionsartikelHinzugefuegt++;
								}
							} else {
								console.log(`${teilnehmer.displayName} hat "Nein, danke" gewählt`);
							}
						});
						
						// Warte auf alle Verarbeitungen
						Promise.all(verarbeitungsPromises).then(() => {
							console.log(`${aktionsartikelHinzugefuegt} Aktionsartikel wurden hinzugefügt`);
							
							if (aktionsartikelHinzugefuegt > 0) {
								// Refresh alle betroffenen Felder (mit Fehlerbehandlung)
								try {
									// Gastgeberin-Tabelle
									if (frm.fields_dict.produktauswahl_für_gastgeberin) {
										frm.refresh_field('produktauswahl_für_gastgeberin');
									}
									
									// Gäste-Tabellen
									for (let i = 1; i <= 15; i++) {
										let fieldName = `produktauswahl_für_gast_${i}`;
										if (frm.fields_dict[fieldName]) {
											try {
												frm.refresh_field(fieldName);
											} catch (e) {
												console.log(`Konnte ${fieldName} nicht refreshen:`, e);
											}
										}
									}
								} catch (e) {
									console.log("Fehler beim Refreshen nach Aktionsartikeln:", e);
								}
								
								// WICHTIG: Dokument speichern, damit die Aktionsartikel persistiert werden!
								console.log("Speichere Dokument nach Hinzufügen der Aktionsartikel...");
							d.hide();
								frm.save().then(() => {
									console.log("Dokument erfolgreich gespeichert mit Aktionsartikeln");
									// Aktualisiere Summen nach dem Speichern
									setTimeout(() => {
										updateAllSummenAnzeigen(frm);
									}, 300);
							// Cleanup der Backup-Variablen nach erfolgreichem Aktions-System
							delete frm._originalGesamtumsatz;
							delete frm._originalProductAmounts;
							console.log("Aktions-System erfolgreich - Backup-Variablen aufgeräumt");
							callback();
								}).catch((saveError) => {
									console.error("Fehler beim Speichern nach Aktionsartikeln:", saveError);
									// Cleanup auch bei Speicherfehlern
									delete frm._originalGesamtumsatz;
									delete frm._originalProductAmounts;
									console.log("Aktions-System mit Speicherfehler - Backup-Variablen aufgeräumt");
									callback(); // Trotzdem fortfahren
								});
							} else {
								// Keine Aktionsartikel hinzugefügt
								d.hide();
								// Cleanup der Backup-Variablen nach erfolgreichem Aktions-System
								delete frm._originalGesamtumsatz;
								delete frm._originalProductAmounts;
								console.log("Aktions-System erfolgreich - Backup-Variablen aufgeräumt");
								callback();
							}
						}).catch((error) => {
							console.error("Fehler beim Hinzufügen der Aktionsartikel:", error);
							// Entferne die Fehlermeldung, da die Artikel trotzdem hinzugefügt wurden
							console.log("Artikel wurden trotz Fehler hinzugefügt - fahre fort");
							d.hide();
							// Cleanup auch bei Fehlern
							delete frm._originalGesamtumsatz;
							delete frm._originalProductAmounts;
							console.log("Aktions-System mit Fehlern - Backup-Variablen aufgeräumt");
							callback(); // Auch bei Fehlern fortfahren
						});
					},
					secondary_action_label: 'Alle ablehnen',
					secondary_action: function() {
						console.log("Alle Aktionen abgelehnt");
						d.hide();
						// Cleanup der Backup-Variablen auch bei Ablehnung
						delete frm._originalGesamtumsatz;
						delete frm._originalProductAmounts;
						console.log("Aktions-System abgelehnt - Backup-Variablen aufgeräumt");
						callback();
					}
				});
				
				d.show();
			}
			
			function getItemCodeFromName(itemName) {
				let found = standardVariants.find(v => v.name === itemName) || premiumVariants.find(v => v.name === itemName);
				return found ? found.code : null;
			}
			
			function addAktionsartikelToTeilnehmer(teilnehmer, itemCode, itemName) {
				console.log(`Füge ${itemCode} zu ${teilnehmer.displayName} hinzu`);
				
				return new Promise((resolve, reject) => {
					// Hole Item-Details
					frappe.call({
						method: "frappe.client.get_value",
						args: {
							doctype: "Item",
							filters: {
								item_code: itemCode
							},
							fieldname: ["item_name", "standard_rate", "stock_uom"]
						},
						callback: function(r) {
							if (r.message) {
								let itemDetails = r.message;
								let rate = itemDetails.standard_rate || 0;
								let stock_uom = itemDetails.stock_uom || "Stk";
								
								// WICHTIG: Verwende frm.add_child() statt Array-Manipulation!
								let neuer_eintrag = frm.add_child(teilnehmer.produktfeld);
								
								// Setze alle erforderlichen Felder
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'item_code', itemCode);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'item_name', itemDetails.item_name || itemName);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'qty', 1);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'rate', rate);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'amount', rate * 1);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'uom', stock_uom);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'stock_uom', stock_uom);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'conversion_factor', 1.0);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'uom_conversion_factor', 1.0);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'stock_qty', 1.0);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'base_amount', rate * 1);
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'base_rate', rate);
								// Setze delivery_date - Backend normalisiert das Format automatisch
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'delivery_date', frappe.datetime.add_days(frappe.datetime.get_today(), 7));
								
								// WAREHOUSE: Dynamisch über get_default_warehouse()
								frappe.call({
									method: "enjo_party.enjo_party.doctype.party.party.get_default_warehouse",
									async: false,
									callback: function(r) {
										let warehouse = r.message || "Lagerräume - BM";
										frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'warehouse', warehouse);
									}
								});
								
								// Markierung für Aktionsartikel (als separates Feld falls nötig)
								// ENTFERNT: frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, '_aktionsartikel', true);
								
								// Refresh das Feld, damit es sichtbar wird
								frm.refresh_field(teilnehmer.produktfeld);
								
								console.log(`Aktionsartikel ${itemName} zu ${teilnehmer.displayName} hinzugefügt`);
								resolve();
							} else {
								console.error(`Konnte Item-Details für ${itemCode} nicht laden`);
								reject(`Item-Details nicht gefunden`);
							}
						}
					});
				});
			}
		}
	});
}

// Gutschein-System: PRÜFT nur, wie viel Gutschein verbraucht werden würde (OHNE Preise zu ändern!)
// Die tatsächliche Anwendung passiert erst beim Erstellen der Aufträge
function applyGutscheinSystem(frm, callback) {
	console.log("applyGutscheinSystem gestartet (nur Prüfung, keine Preisänderung)");
	
	// Markiere, dass das Gutschein-System durchlaufen wird
	frm._gutscheinSystemDurchlaufen = true;
	
	// WICHTIG: Sichere den ursprünglichen Gesamtumsatz für spätere Wiederherstellung
	frm._originalGesamtumsatz = frm.doc.gesamtumsatz;
	frm._originalProductAmounts = {}; // Für Aktionsberechnung
	console.log("Ursprünglicher Gesamtumsatz gesichert:", frm._originalGesamtumsatz);
	
	// Hole den Gutscheinwert des Gastgebers
	let gutscheinWert = frm.doc.gastgeber_gutschein_wert || 0;
	console.log("Verfügbarer Gutscheinwert:", gutscheinWert);
	
	if (gutscheinWert <= 0) {
		console.log("Kein Gutscheinwert verfügbar - überspringe Gutschein-System");
		callback();
		return;
	}
	
	// Sammle nur aktionsfähige Produkte aus der GASTGEBER-GESCHENKE-Tabelle (nicht mehr aus der normalen Produkttabelle!)
	let gastgeberProdukte = [];
	
	// Funktion zum Sammeln der Produkte aus der Gastgeber-Geschenke-Tabelle
	function sammleGastgeberGeschenkeProdukte() {
		if (frm.doc.gastgeber_geschenke && frm.doc.gastgeber_geschenke.length > 0) {
			frm.doc.gastgeber_geschenke.forEach((item, index) => {
				if (item.item_code && item.qty && item.qty > 0 && item.rate && item.rate > 0) {
					gastgeberProdukte.push({
						item: item,
						produktfeld: "gastgeber_geschenke",
						tabellenName: "Gastgeber Geschenke",
						index: index,
						originalRate: item.rate,
						originalAmount: item.amount
					});
				}
			});
		}
	}
	
	// Sammle nur Produkte aus der Gastgeber-Geschenke-Tabelle (Gutschein wird NUR auf Geschenke angewendet!)
	sammleGastgeberGeschenkeProdukte();
	
	console.log("Gefundene Gastgeber-Produkte (vor Aktionsfähigkeits-Prüfung):", gastgeberProdukte.length);
	
	if (gastgeberProdukte.length === 0) {
		console.log("Gastgeber hat keine Produkte - zeige Vollbetrag-Dialog");
		// WICHTIG: Auch bei 0 Produkten den Dialog zeigen!
		zeigeRestbetragDialog(gutscheinWert, frm, callback);
		return;
	}
	
	// Prüfe jedes Gastgeber-Produkt auf Aktionsfähigkeit
	pruefeAktionsfaehigkeitAllerProdukte(gastgeberProdukte, 0, [], function(aktionsfaehigeGastgeberProdukte) {
		console.log("Aktionsfähige Gastgeber-Produkte:", aktionsfaehigeGastgeberProdukte.length);
		
		if (aktionsfaehigeGastgeberProdukte.length === 0) {
			console.log("Gastgeber hat keine aktionsfähigen Produkte - zeige Vollbetrag-Dialog");
			// WICHTIG: Auch bei 0 aktionsfähigen Produkten den Dialog zeigen!
			zeigeRestbetragDialog(gutscheinWert, frm, callback);
			return;
		}
		
		// Sichere ursprüngliche Produktbeträge für Aktionsberechnung
	aktionsfaehigeGastgeberProdukte.forEach((produkt, index) => {
		let key = `${produkt.produktfeld}_${produkt.index}`;
		frm._originalProductAmounts[key] = produkt.originalAmount;
		console.log(`Original-Betrag gesichert für Aktions-System: ${produkt.item.item_code} = ${produkt.originalAmount}€`);
	});
	
		// WICHTIG: Berechne nur, wie viel Gutschein verbraucht werden würde, aber ÄNDERE KEINE PREISE!
		// Die tatsächliche Anwendung passiert erst beim Erstellen der Aufträge
		berechneGutscheinVerbrauch(aktionsfaehigeGastgeberProdukte, gutscheinWert, frm, callback);
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

// Berechnet nur, wie viel Gutschein verbraucht werden würde (OHNE Preise zu ändern!)
// Die tatsächliche Anwendung passiert erst beim Erstellen der Aufträge
function berechneGutscheinVerbrauch(aktionsfaehigeGastgeberProdukte, verfuegbarerGutschein, frm, callback) {
	console.log("Berechne Gutschein-Verbrauch (ohne Preisänderung) - Verfügbar:", verfuegbarerGutschein);
	
	let verbrauchterGutschein = 0;
	
	// WICHTIG: Speichere die Original-Preise für spätere Anwendung beim Erstellen der Aufträge
	if (!frm.originalPricesBackup) {
		frm.originalPricesBackup = {};
	}
	
	// Gehe von oben nach unten durch die Gastgeber-Produkte und berechne nur den Verbrauch
	for (let i = 0; i < aktionsfaehigeGastgeberProdukte.length && verfuegbarerGutschein > verbrauchterGutschein; i++) {
		let produkt = aktionsfaehigeGastgeberProdukte[i];
		let produktWert = produkt.originalAmount;
		let restGutschein = verfuegbarerGutschein - verbrauchterGutschein;
		
		// Speichere Original-Preis für spätere Anwendung beim Erstellen der Aufträge
		let backupKey = `${produkt.produktfeld}_${produkt.index}`;
		if (!frm.originalPricesBackup[backupKey]) {
			frm.originalPricesBackup[backupKey] = {
				originalRate: produkt.originalRate,
				originalAmount: produkt.originalAmount,
				item: produkt.item
			};
			console.log(`Original-Preis gespeichert für spätere Gutschein-Anwendung: ${produkt.item.item_code}: ${produkt.originalRate}€`);
		}
		
		if (produktWert <= restGutschein) {
			// Komplette Reduktion würde auf 0€ gehen
			let rabatt = produktWert;
			verbrauchterGutschein += rabatt;
			console.log(`Gastgeber-Produkt ${produkt.item.item_code}: Würde vollständig reduziert werden um ${rabatt}€`);
		} else {
			// Teilweise Reduktion
			let rabatt = restGutschein;
			verbrauchterGutschein += rabatt;
			console.log(`Gastgeber-Produkt ${produkt.item.item_code}: Würde teilweise reduziert werden um ${rabatt}€`);
			break; // Gutschein wäre aufgebraucht
		}
	}
	
	let restbetrag = verfuegbarerGutschein - verbrauchterGutschein;
	console.log("Gutschein-Verbrauch berechnet - Würde verbrauchen:", verbrauchterGutschein, "Restbetrag:", restbetrag);
	
	// WICHTIG: KEINE Preisänderung hier! Preise bleiben unverändert.
	// Die Summen-Anzeige zeigt bereits den korrekten verbleibenden Gutschein basierend auf den Original-Preisen
	
	if (restbetrag > 0.01) { // Kleine Rundungsfehler ignorieren
		// Zeige Restbetrag-Dialog
		zeigeRestbetragDialog(restbetrag, frm, callback);
	} else {
		// Kein Restbetrag - weiter zum nächsten Schritt
		console.log("Gutschein würde vollständig verbraucht werden - fahre fort");
		callback();
	}
}

// Wendet den Gutschein von oben nach unten auf die Gastgeber-Produkte an
// WICHTIG: Diese Funktion wird nur noch beim tatsächlichen Erstellen der Aufträge aufgerufen!
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
			// Komplette Reduktion auf 0€
			let rabatt = produktWert;
			verbrauchterGutschein += rabatt;
			
			// Setze Preis auf 0€ und markiere als Gutschein-reduziert
			produkt.item.rate = 0;
			produkt.item.amount = 0;
			produkt.item._gutschein_angewendet = true; // WICHTIGE MARKIERUNG!
			// WICHTIG: Speichere ursprünglichen Betrag für Provisionsberechnung
			produkt.item._original_amount_for_commission = produkt.originalAmount;
			
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
			
			// Setze neuen Preis und markiere als Gutschein-reduziert
			produkt.item.rate = neuerPreis;
			produkt.item.amount = neuerBetrag;
			produkt.item._gutschein_angewendet = true; // WICHTIGE MARKIERUNG!
			// WICHTIG: Speichere ursprünglichen Betrag für Provisionsberechnung
			produkt.item._original_amount_for_commission = produkt.originalAmount;
			
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
	
	// WICHTIG: Stelle ursprünglichen Gesamtumsatz wieder her (nicht neu berechnen!)
	// Der Gutschein reduziert nur die Preise für die Aufträge, aber nicht den Party-Gesamtumsatz
	if (frm._originalGesamtumsatz) {
		frm.set_value('gesamtumsatz', frm._originalGesamtumsatz);
		console.log("Ursprünglicher Gesamtumsatz wiederhergestellt:", frm._originalGesamtumsatz);
	}
	
	let restbetrag = verfuegbarerGutschein - verbrauchterGutschein;
	console.log("Gutschein angewendet - Verbraucht:", verbrauchterGutschein, "Restbetrag:", restbetrag);
	
	// Aktualisiere die Summen-Anzeigen NACH dem Refresh der Tabellen (mit reduzierten Preisen)
	// WICHTIG: Längeres Timeout, damit die Preise sicher reduziert wurden
	// Die Summe wird auch im Dialog-Handler aktualisiert, falls nötig
	setTimeout(() => {
		updateAllSummenAnzeigen(frm);
		console.log("Summen-Anzeigen nach Gutschein-Anwendung aktualisiert (mit reduzierten Preisen)");
	}, 800);
	
	if (restbetrag > 0.01) { // Kleine Rundungsfehler ignorieren
		// Zeige Restbetrag-Dialog
		// Die Summe wird bereits oben mit setTimeout aktualisiert (nach 800ms)
		// Zusätzlich aktualisieren wir sie auch direkt vor dem Dialog, damit sie sicher korrekt ist
		setTimeout(() => {
			updateAllSummenAnzeigen(frm);
			console.log("Summen-Anzeigen direkt vor Dialog aktualisiert (mit reduzierten Preisen)");
		}, 600);
		zeigeRestbetragDialog(restbetrag, frm, callback);
	} else {
		// Kein Restbetrag - weiter zum nächsten Schritt
		// ENTFERNT: frappe.show_alert(`Gutschein vollständig angewendet: ${verbrauchterGutschein.toFixed(2)}€`, 3);
		// Original-Preise können gelöscht werden, da der Gutschein erfolgreich angewendet wurde
		frm.originalPricesBackup = {};
		// Cleanup der Backup-Variablen da Gutschein erfolgreich angewendet
		console.log("Gutschein-System erfolgreich - Backup-Variablen werden beibehalten für Aktions-System");
		callback();
	}
}

// Dialog für Restbetrag-Behandlung (auch bei Vollbetrag)
function zeigeRestbetragDialog(restbetrag, frm, callback) {
	// Prüfe, ob es ein Vollbetrag (keine aktionsfähigen Produkte) oder Restbetrag ist
	let istVollbetrag = restbetrag === (frm.doc.gastgeber_gutschein_wert || 0);
	
	let titel = istVollbetrag ? 'Gutschein kann nicht angewendet werden' : 'Gutschein-Restbetrag';
	let nachricht = istVollbetrag 
		? `Du hast ${restbetrag.toFixed(2)}€ Gutschrift, aber keine aktionsfähigen Produkte ausgewählt.`
		: `Du hast noch ${restbetrag.toFixed(2)}€ Gutschrift übrig! Der Gutschein konnte nicht vollständig auf die aktionsfähigen Produkte angewendet werden.`;
	
	let dialog = new frappe.ui.Dialog({
		title: titel,
		fields: [
			{
				fieldtype: 'HTML',
				options: `
					<div style="margin-bottom: 15px;">
						<h4>${nachricht}</h4>
						<p><strong>Was möchtest Du tun?</strong></p>
					</div>
				`
			}
		],
		primary_action_label: istVollbetrag ? 'Aktionsfähige Produkte hinzufügen' : 'Zurück zur Bearbeitung',
		primary_action: function() {
			dialog.hide();
			// WICHTIG: Preise wurden noch nicht geändert, daher keine Wiederherstellung nötig
			// Die Preise bleiben unverändert, da der Gutschein erst beim Erstellen der Aufträge angewendet wird
			if (istVollbetrag) {
				// Bei Vollbetrag: Zurück zur Bearbeitung (Produkte hinzufügen)
				refreshButtons(frm);
			} else {
				// Bei Restbetrag: Zurück zur Bearbeitung 
				refreshButtons(frm);
			}
		},
		secondary_action_label: istVollbetrag ? 'Gutschein verfallen lassen' : 'Restbetrag verfallen lassen',
			secondary_action: function() {
			dialog.hide();
			if (istVollbetrag) {
				// Bei Vollbetrag: Gutschein verfällt, aber Party wird trotzdem gebucht
				console.log("Vollbetrag-Gutschein verfällt - fahre mit Aufträge-Erstellung fort");
				// WICHTIG: Markiere dass KEIN Gutschein angewendet wurde (weil keine aktionsfähigen Produkte vorhanden)
				frm._keinGutscheinAngewendet = true;
				// WICHTIG: Preise wurden noch nicht geändert - Gutschein wird erst beim Erstellen der Aufträge angewendet
				// ENTFERNT: frappe.show_alert(`Gutschein von ${restbetrag.toFixed(2)}€ verfällt - fahre mit Bestellung fort`, 3);
				callback(); // WICHTIG: Weiter zum Aktions-System!
			} else {
				// Bei Restbetrag: Verfallen lassen und fortfahren
				// WICHTIG: Preise wurden noch nicht geändert - Gutschein wird erst beim Erstellen der Aufträge angewendet
				console.log("Restbetrag-Gutschein verfällt - fahre fort");
				let nachricht = `Restbetrag von ${restbetrag.toFixed(2)}€ verfällt`;
				// ENTFERNT: frappe.show_alert(nachricht, 3);
				// Weiter zum nächsten Schritt (Aufträge erstellen, wo dann der Gutschein angewendet wird)
				callback();
			}
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
	
	// Sammle zuerst alle betroffenen Tabellen BEVOR wir das Backup löschen
	let betroffeneTabellen = new Set();
	
	// Gehe durch alle gespeicherten Original-Preise
	for (let backupKey in frm.originalPricesBackup) {
		let backup = frm.originalPricesBackup[backupKey];
		let item = backup.item;
		
		// Stelle Original-Preis und -Betrag wieder her
		item.rate = backup.originalRate;
		item.amount = backup.originalAmount;
		// Entferne Gutschein-Markierung
		delete item._gutschein_angewendet;
		
		// Sammle die betroffene Tabelle aus dem Backup-Key
		// Backup-Key Format: "produktfeld_index" (z.B. "gastgeber_geschenke_0" oder "produktauswahl_für_gastgeberin_0")
		let parts = backupKey.split('_');
		if (backupKey.startsWith('gastgeber_geschenke')) {
			betroffeneTabellen.add('gastgeber_geschenke');
		} else if (backupKey.startsWith('produktauswahl_für_gastgeberin')) {
			betroffeneTabellen.add('produktauswahl_für_gastgeberin');
		}
		
		console.log(`Original-Preis wiederhergestellt für ${item.item_code}: ${backup.originalRate}€`);
		wiederhergestellteProdukte++;
	}
	
	// Lösche das Backup, da es nicht mehr benötigt wird
	frm.originalPricesBackup = {};
	
	// Aktualisiere alle betroffenen Tabellen
	betroffeneTabellen.forEach(tabelle => {
		if (frm.fields_dict[tabelle]) {
			frm.refresh_field(tabelle);
		}
	});
	
	// Aktualisiere auch die Summen-Anzeigen
	updateAllSummenAnzeigen(frm);
	
	// WICHTIG: Stelle ursprünglichen Gesamtumsatz wieder her (falls er durch Gutschein verändert wurde)
	if (frm._originalGesamtumsatz) {
		frm.set_value('gesamtumsatz', frm._originalGesamtumsatz);
		console.log("Gesamtumsatz nach Preiswiederherstellung korrigiert:", frm._originalGesamtumsatz);
	} else {
		// Fallback: Neu berechnen falls kein Original-Wert vorhanden
		calculate_party_totals(frm);
	}
	
	console.log(`${wiederhergestellteProdukte} Produkte auf Original-Preise zurückgesetzt`);
	// ENTFERNT: frappe.show_alert(`${wiederhergestellteProdukte} Produkte auf Original-Preise zurückgesetzt`, 3);
}

// Wendet den Gutschein JETZT an (beim Erstellen der Aufträge)
function wendeGutscheinBeimErstellenAn(frm) {
	console.log("Wende Gutschein jetzt an (beim Erstellen der Aufträge)");
	
	if (!frm.originalPricesBackup || Object.keys(frm.originalPricesBackup).length === 0) {
		console.log("Keine Gutschein-Anwendung nötig - keine gespeicherten Preise gefunden");
		return;
	}
	
	let gutscheinWert = frm.doc.gastgeber_gutschein_wert || 0;
	if (gutscheinWert <= 0) {
		console.log("Kein Gutscheinwert - überspringe Anwendung");
		return;
	}
	
	let verbrauchterGutschein = 0;
	let betroffeneTabellen = new Set();
	
	// Gehe durch alle gespeicherten Produkte und wende den Gutschein an
	for (let backupKey in frm.originalPricesBackup) {
		let backup = frm.originalPricesBackup[backupKey];
		let item = backup.item;
		let produktWert = backup.originalAmount;
		let restGutschein = gutscheinWert - verbrauchterGutschein;
		
		// Sammle die betroffene Tabelle
		if (backupKey.startsWith('gastgeber_geschenke')) {
			betroffeneTabellen.add('gastgeber_geschenke');
		}
		
		if (produktWert <= restGutschein) {
			// Komplette Reduktion auf 0€
			let rabatt = produktWert;
			verbrauchterGutschein += rabatt;
			
			item.rate = 0;
			item.amount = 0;
			item._gutschein_angewendet = true;
			item._original_amount_for_commission = backup.originalAmount;
			
			console.log(`Gutschein angewendet: ${item.item_code} auf 0€ reduziert`);
		} else {
			// Teilweise Reduktion
			let rabatt = restGutschein;
			verbrauchterGutschein += rabatt;
			
			let neuerPreis = (produktWert - rabatt) / item.qty;
			let neuerBetrag = produktWert - rabatt;
			
			item.rate = neuerPreis;
			item.amount = neuerBetrag;
			item._gutschein_angewendet = true;
			item._original_amount_for_commission = backup.originalAmount;
			
			console.log(`Gutschein angewendet: ${item.item_code} um ${rabatt}€ reduziert`);
			break; // Gutschein ist aufgebraucht
		}
	}
	
	// Aktualisiere die betroffenen Tabellen
	betroffeneTabellen.forEach(tabelle => {
		if (frm.fields_dict[tabelle]) {
			frm.refresh_field(tabelle);
		}
	});
	
	console.log(`Gutschein angewendet - Verbraucht: ${verbrauchterGutschein}€`);
}

// Hilfsfunktion zum Erstellen der Aufträge
function erstelleAuftraege(frm) {
	console.log("erstelleAuftraege aufgerufen");
	
	// WICHTIG: Wende den Gutschein JETZT an (beim Erstellen der Aufträge, nicht vorher!)
	if (frm.originalPricesBackup && Object.keys(frm.originalPricesBackup).length > 0) {
		wendeGutscheinBeimErstellenAn(frm);
	}
	
	// Aktiviere Pflichtfelder für die finale Validierung
	enableRequiredFields(frm);
	
	// WICHTIG: Setze Flags nur wenn tatsächlich Gutscheine oder Aktionsartikel angewendet wurden
	// Wenn KEIN Gutschein angewendet UND KEINE Aktionsartikel hinzugefügt wurden, 
	// dann KEINE skip-Flags setzen (normale Berechnung soll stattfinden)
	let sollteSkipFlagsSetzen = !frm._keinGutscheinAngewendet && !frm._keineAktionsartikelHinzugefuegt;
	
	if (sollteSkipFlagsSetzen) {
		console.log("Setze skip-Flags (Gutschein oder Aktionsartikel wurden angewendet)");
		frm._skipTotalCalculation = true;
		frm._skipPriceUpdates = true;
	} else {
		console.log("Setze KEINE skip-Flags (kein Gutschein und keine Aktionsartikel angewendet)");
		frm._skipTotalCalculation = false;
		frm._skipPriceUpdates = false;
	}
	
	// SOFORT den Screen "einfrieren" mit Frappe's Freeze-Mechanismus
	frappe.freeze_screen = true;
	// ENTFERNT: frappe.show_alert({
	// 	message: __("Bereite Aufträge vor..."),
	// 	indicator: "blue"
	// });
	
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
	
	// Vor dem Speichern: Alle Produkttabellen aktualisieren und Gesamtsummen neu berechnen
	console.log("Aktualisiere alle Produkttabellen vor dem Speichern...");
	
	// Refresh nur existierende Produkttabellen (mit Fehlerbehandlung)
	try {
		// Gastgeberin-Tabelle
		if (frm.doc.produktauswahl_für_gastgeberin && frm.fields_dict.produktauswahl_für_gastgeberin) {
			frm.refresh_field('produktauswahl_für_gastgeberin');
		}
		
		// Gäste-Tabellen (nur die, die tatsächlich existieren)
		for (let i = 1; i <= 15; i++) {
			let fieldName = `produktauswahl_für_gast_${i}`;
			if (frm.doc[fieldName] && frm.fields_dict[fieldName]) {
				try {
					frm.refresh_field(fieldName);
				} catch (e) {
					console.log(`Konnte ${fieldName} nicht refreshen:`, e);
				}
			}
		}
	} catch (e) {
		console.log("Fehler beim Refreshen der Tabellen:", e);
	}
	
	// Aktualisiere auch die Summen-Anzeigen
	updateAllSummenAnzeigen(frm);
	
	// SKIP: Berechne Gesamtsummen NICHT neu (wichtig nach Aktionsartikeln und Gutschrift)
	// try {
	// 	calculate_party_totals(frm);
	// } catch (e) {
	// 	console.log("Fehler beim Berechnen der Gesamtsummen:", e);
	// }
	
	// WICHTIG: Stelle sicher, dass alle Aktionsartikel korrekte Daten haben
	console.log("Validiere Aktionsartikel...");
	validateAktionsartikel(frm);
	
	// Kurze Pause, damit alle Updates verarbeitet werden
	setTimeout(() => {
		// Direkt zur API ohne explizites Speichern (Frappe speichert automatisch vor API-Aufrufen)
	// ENTFERNT: frappe.show_alert({
	// 		message: __("Erstelle Aufträge..."),
	// 		indicator: "orange"
	// 	});
		
		console.log("Rufe create_invoices API direkt auf...");
		erstelleAuftraegeDirectly(frm);
	}, 500); // Nur 0.5 Sekunden Pause
}

// Neue Funktion zur Validierung der Aktionsartikel
function validateAktionsartikel(frm) {
	console.log("Validiere Aktionsartikel...");
	
	// Lade Aktionseinstellungen dynamisch
	frappe.call({
		method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
		async: false, // Synchron laden für Validation
		callback: function(r) {
			if (!r.message) {
				console.log("Konnte Aktionseinstellungen nicht laden - verwende Fallback");
				return;
			}
			
			let settings = r.message;
			
					// Dynamische Varianten aus den Einstellungen
		const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
		const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
		const aktionsCodes = [...standardVariants, ...premiumVariants].map(v => v.code).filter(Boolean);
			
			console.log("Dynamische Aktions-Codes:", aktionsCodes);
			
			// Prüfe alle Produkttabellen
			let aktionsartikelGefunden = 0;
			
			// Gastgeberin-Tabelle
			if (frm.doc.produktauswahl_für_gastgeberin) {
				frm.doc.produktauswahl_für_gastgeberin.forEach(item => {
					if (aktionsCodes.includes(item.item_code)) {
						aktionsartikelGefunden++;
						// Stelle sicher, dass wichtige Felder gesetzt sind
						if (!item.qty) item.qty = 1;
						if (!item.uom) item.uom = "Stk";
						if (!item.stock_uom) item.stock_uom = "Stk";
						if (!item.conversion_factor) item.conversion_factor = 1;
						if (!item.delivery_date) item.delivery_date = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
						if (!item.warehouse) {
							frappe.call({
								method: "enjo_party.enjo_party.doctype.party.party.get_default_warehouse",
								async: false,
								callback: function(r) {
									item.warehouse = r.message || "Lagerräume - BM";
								}
							});
						}
						console.log(`Aktionsartikel validiert: ${item.item_code} für Gastgeberin`);
					}
				});
			}
			
			// Gäste-Tabellen
			for (let i = 1; i <= 15; i++) {
				let fieldName = `produktauswahl_für_gast_${i}`;
				if (frm.doc[fieldName]) {
					frm.doc[fieldName].forEach(item => {
						if (aktionsCodes.includes(item.item_code)) {
							aktionsartikelGefunden++;
							// Stelle sicher, dass wichtige Felder gesetzt sind
							if (!item.qty) item.qty = 1;
							if (!item.uom) item.uom = "Stk";
							if (!item.stock_uom) item.stock_uom = "Stk";
							if (!item.conversion_factor) item.conversion_factor = 1;
							if (!item.delivery_date) item.delivery_date = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
							if (!item.warehouse) {
								frappe.call({
									method: "enjo_party.enjo_party.doctype.party.party.get_default_warehouse",
									async: false,
									callback: function(r) {
										item.warehouse = r.message || "Lagerräume - BM";
									}
								});
							}
							console.log(`Aktionsartikel validiert: ${item.item_code} für Gast ${i}`);
						}
					});
				}
			}
			
			console.log(`${aktionsartikelGefunden} Aktionsartikel gefunden und validiert`);
		}
	});
}

// Hilfsfunktion für direkten API-Aufruf
function erstelleAuftraegeDirectly(frm) {
	console.log("Starte Aufträge-Erstellung via API");
	
	// SOFORT den Screen "einfrieren" mit Frappe's Freeze-Mechanismus
	frappe.freeze_screen = true;
	
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
	
	// Kurze Pause, dann API direkt aufrufen
	// ENTFERNT: setTimeout da es bei eingefrorenem Screen nicht funktioniert
	// setTimeout(() => {
		// WICHTIG: Setze skip_total_calculation Backend-Flag nur wenn Frontend-Flags gesetzt sind
		// damit calculate_totals() nur übersprungen wird wenn tatsächlich Gutschrift/Aktionsartikel angewendet wurden
		if (frm._skipTotalCalculation) {
			console.log("Setze Backend skip_total_calculation Flag");
			frm.doc.skip_total_calculation = 1;
		} else {
			console.log("Setze KEIN Backend skip_total_calculation Flag - normale Berechnung");
			frm.doc.skip_total_calculation = 0;
		}
		
		// DEBUG: Zeige aktuellen Dokument-Status
		console.log("DEBUG: Vor dem Speichern - docstatus:", frm.doc.docstatus, "is_dirty:", frm.is_dirty());
		
		// WICHTIG: Wenn das Dokument nicht dirty ist, gibt es nichts zu speichern
		// Das passiert wenn keine Gutscheine angewendet und keine Aktionsartikel hinzugefügt wurden
		if (!frm.is_dirty()) {
			console.log("Dokument unverändert - springe direkt zur Aufträge-Erstellung");
			callCreateInvoicesAPI();
			return;
		}
		
		// DANN speichern mit gesetztem Flag - aber mit besserem Error Handling
		console.log("Speichere Änderungen vor Aufträge-Erstellung...");
		
		// Timeout für das Speichern - falls es hängt
		let saveTimeout = setTimeout(() => {
			console.error("TIMEOUT: Speichern dauert zu lange!");
			frappe.freeze_screen = false;
			frappe.msgprint({
				title: "Timeout",
				message: "Das Speichern dauert zu lange. Bitte versuche es erneut oder prüfe die Server-Logs.",
				indicator: "orange"
			});
			refreshButtons(frm);
		}, 10000); // 10 Sekunden Timeout
		
		frm.save().then(() => {
			clearTimeout(saveTimeout); // Timeout löschen wenn erfolgreich
			console.log("Speichern erfolgreich - starte Aufträge-Erstellung");
			callCreateInvoicesAPI();
		}).catch((error) => {
			clearTimeout(saveTimeout); // Timeout löschen auch bei Fehler
			console.error("Fehler beim Speichern:", error);
			// Screen wieder freigeben
			
			frappe.freeze_screen = false;
			// Flag zurücksetzen bei Fehler
			frm.doc.skip_total_calculation = 0;
			
			// Detaillierte Fehlermeldung
			let errorMessage = "Fehler beim Speichern der Änderungen.";
			if (error && error.message) {
				errorMessage += "\n\nDetails: " + error.message;
			}
			if (error && error.exc) {
				errorMessage += "\n\nTechnische Details: " + error.exc;
			}
			
			frappe.msgprint({
				title: "Speicherfehler",
				message: errorMessage,
				indicator: "red"
			});
			
			// Buttons wieder herstellen
			refreshButtons(frm);
		});
	// }, 100);
	
	function callCreateInvoicesAPI() {
		console.log("Rufe Aufträge-API auf...");
		
		frappe.call({
			method: "enjo_party.enjo_party.doctype.party.party.create_invoices",
			args: {
				party: frm.doc.name,
				from_button: true  // Flag, um zu zeigen, dass der Aufruf vom Button kommt
			},
			freeze: true, // Screen-Freeze wieder aktiviert da Debugging abgeschlossen
			freeze_message: __("Erstelle und reiche Aufträge ein..."),
			callback: function(r) {
				console.log("API-Antwort erhalten - verarbeite Ergebnis");
				// Screen wieder freigeben
				frappe.freeze_screen = false;
				
				// WICHTIG: Flags zurücksetzen, damit normale Funktionalität wiederhergestellt wird
				frm.doc.skip_total_calculation = 0;
				
				if (r.message && r.message.length > 0) {
					frappe.msgprint({
						title: __("Erfolgreich gebuchte Präsentation"),
						message: __("{0} Aufträge wurden erfolgreich erstellt und eingereicht.<br><br>Das Fenster wird gleich automatisch neu geladen, um den aktuellen Status anzuzeigen.", [r.message.length]),
						indicator: "green"
					});
					// Vollständiges Neuladen der Seite, um den Status zu aktualisieren
					// Delay erhöht, damit Benutzer die Erfolgsmeldung lesen können
					setTimeout(function() {
						location.reload();
					}, 3500); // 3.5 Sekunden statt 2
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
				console.error("API-Fehler bei Aufträge-Erstellung:", r);
				// Screen wieder freigeben
				frappe.freeze_screen = false;
				
				// WICHTIG: Flags zurücksetzen auch bei Fehlern
				frm.doc.skip_total_calculation = 0;
				
				// Bei API-Fehlern - zeige vollständige Fehlermeldung
				let errorMessage = "Es ist ein Fehler beim Erstellen der Aufträge aufgetreten.";
				if (r && r.message) {
					errorMessage += "\n\nFehlermeldung: " + r.message;
				}
				if (r && r.exc) {
					errorMessage += "\n\nTechnische Details: " + r.exc;
				}
				
				frappe.msgprint({
					title: __("Fehler"),
					message: errorMessage,
					indicator: "red"
				});
				// Buttons wieder herstellen
				console.log("API-Fehler - refreshButtons wird aufgerufen");
				refreshButtons(frm);
			}
		});
	}
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
	
	// Sammle alle bereits ausgewählten Kunden (inklusive aktueller Änderungen)
	let selected_customers = [];
	if (frm.doc.kunden) {
		frm.doc.kunden.forEach(function(k) {
			if (k.kunde) {
				selected_customers.push(k.kunde);
			}
		});
	}
	
	// Setze den Filter für die Kunden-Tabelle mit verbesserter Logik
	frm.set_query("kunde", "kunden", function(doc, cdt, cdn) {
		// Hole die aktuelle Zeile
		let current_row = locals[cdt][cdn];
		
		// Sammle alle anderen ausgewählten Kunden (außer der aktuellen Zeile)
		let other_selected = [];
		if (frm.doc.kunden) {
			frm.doc.kunden.forEach(function(k, index) {
				if (k.kunde && k.name !== current_row.name) {
					other_selected.push(k.kunde);
				}
			});
		}
		
		let filters = [["name", "!=", frm.doc.gastgeberin]];
		if (other_selected.length > 0) {
			filters.push(["name", "not in", other_selected]);
		}
		return { filters: filters };
	});
}

// Neue Funktion zur sofortigen Validierung von Duplikaten
function validateKundenDuplicates(frm, current_row) {
	if (!current_row.kunde) return true;
	
	// Prüfe auf Gastgeberin
	if (current_row.kunde === frm.doc.gastgeberin) {
		frappe.msgprint({
			title: __("Fehler"),
			message: __("Die Gastgeberin kann nicht als Gast ausgewählt werden!"),
			indicator: "red"
		});
		// Leere das Feld
		setTimeout(() => {
			current_row.kunde = "";
			frm.refresh_field("kunden");
		}, 100);
		return false;
	}
	
	// Prüfe auf andere Gäste
	let duplicate_found = false;
	if (frm.doc.kunden) {
		frm.doc.kunden.forEach(function(k) {
			if (k.kunde === current_row.kunde && k.name !== current_row.name) {
				duplicate_found = true;
			}
		});
	}
	
	if (duplicate_found) {
		frappe.msgprint({
			title: __("Fehler"),
			message: __("Dieser Gast wurde bereits ausgewählt!"),
			indicator: "red"
		});
		// Leere das Feld
		setTimeout(() => {
			current_row.kunde = "";
			frm.refresh_field("kunden");
		}, 100);
		return false;
	}
	
	return true;
}

// Neue Funktion zur Validierung der Gastgeberin gegen bereits ausgewählte Gäste
function validateGastgeberinDuplicates(frm) {
	if (!frm.doc.gastgeberin) return true;
	
	// Prüfe, ob die Gastgeberin bereits als Gast ausgewählt ist
	let duplicate_found = false;
	let duplicate_guest_name = "";
	
	if (frm.doc.kunden) {
		frm.doc.kunden.forEach(function(k) {
			if (k.kunde === frm.doc.gastgeberin) {
				duplicate_found = true;
				duplicate_guest_name = k.kunde;
			}
		});
	}
	
	if (duplicate_found) {
		frappe.msgprint({
			title: __("Fehler"),
			message: __("Diese Person ist bereits als Gast ausgewählt! Bitte wähle eine andere Gastgeberin oder entferne sie aus der Gästeliste."),
			indicator: "red"
		});
		// Leere das Gastgeberin-Feld
		setTimeout(() => {
			frm.set_value('gastgeberin', '');
		}, 100);
		return false;
	}
	
	return true;
}

// Funktion zum Setzen des Gastgeberin-Filters
function updateGastgeberinFilter(frm) {
	if (!frm.fields_dict["gastgeberin"]) return;
	
	// Sammle alle bereits ausgewählten Gäste
	let selected_guests = [];
	if (frm.doc.kunden) {
		frm.doc.kunden.forEach(function(k) {
			if (k.kunde) {
				selected_guests.push(k.kunde);
			}
		});
	}
	
	// Setze den Filter für die Gastgeberin-Auswahl
	frm.set_query("gastgeberin", function() {
		let filters = [];
		if (selected_guests.length > 0) {
			filters.push(["name", "not in", selected_guests]);
		}
		return { filters: filters };
	});
}

frappe.ui.form.on('Party', {
	refresh(frm) {
		// Deaktiviere Pflichtfelder für normales Speichern
		disableRequiredFields(frm);

		// Wenn das Dokument gebucht ist, zeige den Kundennamen statt der ID für die Gastgeberin
		if (frm.doc.docstatus === 1 && frm.doc.gastgeberin) {
			frappe.db.get_value('Customer', frm.doc.gastgeberin, 'customer_name')
				.then(r => {
					if (r.message && r.message.customer_name) {
						// Finde das DOM-Element für die Gastgeberin
						const gastgeberinField = frm.fields_dict['gastgeberin'];
						if (gastgeberinField) {
							const controlWrapper = $(gastgeberinField.wrapper);
							const valueDisplay = controlWrapper.find('.control-value');

							if (valueDisplay.length > 0) {
								valueDisplay.text(r.message.customer_name);
							} else {
								const fieldInputAsDisplay = gastgeberinField.$input;
								if (fieldInputAsDisplay && fieldInputAsDisplay.is('div') && fieldInputAsDisplay.hasClass('like-disabled-input')) {
									fieldInputAsDisplay.text(r.message.customer_name);
								}
							}
						}
					}
				});
		}
		// Rest des bestehenden refresh-Codes...

		// Zeige die Produktauswahl-Tabellen für die Gäste erst nach dem Speichern
		// Alle Gäste-Tabellen werden im Neu-Modus ausgeblendet
		// WICHTIG: Im Status "Gastgeber Geschenke" werden alle Produkttabellen ausgeblendet
		// ABER: Wenn die Party abgeschlossen ist, werden alle Tabellen wieder angezeigt (für Übersicht)
		const isAbgeschlossen = frm.doc.status === "Abgeschlossen";
		const isGastgeberGeschenkeStatus = frm.doc.status === "Geschenke";
		const showProduktTabellen = !isGastgeberGeschenkeStatus || isAbgeschlossen;
		
		for (let i = 1; i <= 15; i++) {
			// Nur anzeigen, wenn das Dokument gespeichert ist UND genügend Gäste vorhanden sind
			// UND NICHT im Status "Gastgeber Geschenke" (außer wenn abgeschlossen)
			frm.toggle_display(
				`produktauswahl_für_gast_${i}_section`, 
				!frm.is_new() && frm.doc.kunden && frm.doc.kunden.length >= i && showProduktTabellen
			);
		}
		
		// Gäste-Section und Kunden-Tabelle: Ausblenden im Status "Gastgeber Geschenke" (außer wenn abgeschlossen)
		frm.toggle_display("section_break_gaeste", showProduktTabellen);
		frm.toggle_display("kunden", showProduktTabellen);
		
		// Zeige Gastgeberin-Produktauswahl nur an, wenn eine Gastgeberin eingetragen und das Dokument gespeichert ist
		// WICHTIG: Im Status "Gastgeber Geschenke" wird diese Tabelle ausgeblendet (außer wenn abgeschlossen)
		const showGastgeberinSection = !frm.is_new() && frm.doc.gastgeberin && showProduktTabellen;
		frm.toggle_display("produktauswahl_für_gastgeberin_section", showGastgeberinSection);
		frm.toggle_display("summe_gastgeberin", showGastgeberinSection);
		frm.toggle_display("versand_gastgeberin", showGastgeberinSection);
		
		// Gastgebergeschenke-Tabelle: im Status "Geschenke" bearbeiten; nach Buchung in der Übersicht (Server setzt z. B. "Gebucht", nicht "Abgeschlossen")
		const hasGastgeberGeschenke = frm.doc.gastgeber_geschenke && frm.doc.gastgeber_geschenke.length > 0 &&
			frm.doc.gastgeber_geschenke.some(item => item.item_code && item.qty && item.qty > 0);
		const statusMitGastgeberGeschenkeUebersicht = ["Gebucht", "Ausgeliefert", "Überfällig", "Retourniert", "Abgeschlossen"];
		const showGastgeberGeschenke = !frm.is_new() && (
			frm.doc.status === "Geschenke" ||
			(hasGastgeberGeschenke && (
				statusMitGastgeberGeschenkeUebersicht.includes(frm.doc.status) ||
				frm.doc.docstatus === 1
			))
		);
		frm.toggle_display("gastgeber_geschenke_section", showGastgeberGeschenke);
		frm.toggle_display("gastgeber_geschenke", showGastgeberGeschenke);
		frm.toggle_display("summe_gastgeber_geschenke", showGastgeberGeschenke);

		// Automatisch leere Zeilen zu sichtbaren, leeren Produkttabellen hinzufügen
		setTimeout(() => {
			// Spezielle Behandlung für Geschenke Status
			if (frm.doc.status === "Geschenke") {
				// Für Gastgeber Geschenke Tabelle eine leere Zeile hinzufügen
				if (!frm.doc.gastgeber_geschenke || frm.doc.gastgeber_geschenke.length === 0) {
					let row = frm.add_child('gastgeber_geschenke');
					frm.refresh_field('gastgeber_geschenke');
					console.log("Leere Zeile zu Gastgeber Geschenke Tabelle im refresh hinzugefügt");
				}
				return; // Überspringe die normalen Produkttabellen
			}
			
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
			// Summen initial anzeigen
			updateAllSummenAnzeigen(frm);
			// DIREKTE CSS-Regeln einfügen (robusteste Lösung)
			addPermanentColumnHideCSS();
		}, 500);
		
		// Verstecke das Datum-Feld auch in der Gastgeberin-Tabelle
		if (frm.fields_dict["produktauswahl_für_gastgeberin"]) {
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('delivery_date', 'hidden', 1);
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('delivery_date', 'reqd', 0);
			// Verstecke auch das Warehouse-Feld
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('warehouse', 'hidden', 1);
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('warehouse', 'reqd', 0);
			// Mache das Preisfeld schreibgeschützt
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('rate', 'read_only', 1);
		}
		
		// Sammle alle Namen: Gastgeberin, Partnerin, Gäste
		let optionen = [];
		let promises = [];
		if (frm.doc.gastgeberin) {
			promises.push(
				frappe.db.get_doc('Customer', frm.doc.gastgeberin).then(doc => {
					// Sicherstellen, dass doc und doc.customer_name existieren
					if (doc && doc.customer_name) {
						optionen.push({ value: frm.doc.gastgeberin, label: doc.customer_name });
					} else {
						optionen.push({ value: frm.doc.gastgeberin, label: frm.doc.gastgeberin }); // Fallback auf ID
					}
				}).catch(() => {
					optionen.push({ value: frm.doc.gastgeberin, label: frm.doc.gastgeberin }); // Fallback bei Fehler
				})
			);
		}
		// Partnerin als Versandziel hinzufügen
		if (frm.doc.partnerin) {
			promises.push(
				frappe.db.get_doc('Sales Partner', frm.doc.partnerin).then(doc => {
					// Sicherstellen, dass doc und doc.partner_name existieren
					if (doc && doc.partner_name) {
						optionen.push({ value: frm.doc.partnerin, label: doc.partner_name });
					} else {
						optionen.push({ value: frm.doc.partnerin, label: frm.doc.partnerin }); // Fallback auf ID
					}
				}).catch(() => {
					optionen.push({ value: frm.doc.partnerin, label: frm.doc.partnerin }); // Fallback bei Fehler
				})
			);
		}
		if (frm.doc.kunden && frm.doc.kunden.length > 0) {
			frm.doc.kunden.forEach(function(kunde_row) { // Renamed 'kunde' to 'kunde_row'
				if (kunde_row.kunde) {
					promises.push(
						frappe.db.get_doc('Customer', kunde_row.kunde).then(doc => {
							// Sicherstellen, dass doc und doc.customer_name existieren
							if (doc && doc.customer_name) {
								optionen.push({ value: kunde_row.kunde, label: doc.customer_name });
							} else {
								optionen.push({ value: kunde_row.kunde, label: kunde_row.kunde }); // Fallback auf ID
							}
						}).catch(() => {
							optionen.push({ value: kunde_row.kunde, label: kunde_row.kunde }); // Fallback bei Fehler
						})
					);
				}
			});
		}
		Promise.all(promises).then(() => {
			// Entferne Duplikate aus Optionen
			const uniqueOptionen = optionen.filter((option, index, self) =>
				index === self.findIndex((o) => (
					o.value === option.value
				))
			);

			for (let i = 1; i <= 15; i++) {
				if (frm.fields_dict[`versand_gast_${i}`]) { // Nur wenn das Feld existiert
					frm.set_df_property(`versand_gast_${i}`, 'options', uniqueOptionen);
				}
			}
			if (frm.fields_dict['versand_gastgeberin']) { // Nur wenn das Feld existiert
				frm.set_df_property('versand_gastgeberin', 'options', uniqueOptionen);
			}

			// NEUER TEIL: Wenn Dokument gebucht ist (docstatus === 1), zeige Namen statt IDs in Versand-Dropdowns
			if (frm.doc.docstatus === 1) {
				setTimeout(() => {
					const felderZuPruefen = [];
					if (frm.fields_dict['versand_gastgeberin'] && frm.doc.versand_gastgeberin) {
						felderZuPruefen.push('versand_gastgeberin');
					}
					for (let k = 1; k <= 15; k++) {
						const feldNameLoop = `versand_gast_${k}`;
						// Prüfe, ob das Feld im Formular definiert ist UND einen Wert im Dokument hat
						if (frm.fields_dict[feldNameLoop] && frm.doc[feldNameLoop]) {
							felderZuPruefen.push(feldNameLoop);
						}
					}

					felderZuPruefen.forEach(feldName => {
						const kundenId = frm.doc[feldName];
						// Sollte nicht passieren wegen der Prüfung oben, aber als Sicherheit
						if (!kundenId) return; 
						
						let kundenName = kundenId; // Fallback

						const passendeOption = uniqueOptionen.find(opt => opt.value === kundenId);
						if (passendeOption && passendeOption.label) {
							kundenName = passendeOption.label;
						} else {
							// Dieser Fall sollte selten sein, wenn uniqueOptionen aktuell ist
							console.warn(`Konnte Kundennamen für ID ${kundenId} im Feld ${feldName} nicht in den Optionen finden. Anzeige bleibt ID.`);
						}
						
						// Finde das DOM-Element, das den Wert des (nun schreibgeschützten) Select-Feldes anzeigt
						const controlWrapper = $(frm.fields_dict[feldName].wrapper);
						const valueDisplay = controlWrapper.find('.control-value');

						if (valueDisplay.length > 0) {
							valueDisplay.text(kundenName);
						} else {
							// Fallback, falls .control-value nicht existiert oder nicht das richtige Element ist.
							// In manchen Fällen wird der Text direkt im $input Element angezeigt, wenn es ein Div ist.
							const fieldInputAsDisplay = frm.fields_dict[feldName].$input;
							if (fieldInputAsDisplay && fieldInputAsDisplay.is('div') && fieldInputAsDisplay.hasClass('like-disabled-input')) {
								fieldInputAsDisplay.text(kundenName);
							} else {
								console.warn(`Konnte .control-value oder alternatives Anzeigeelement für Feld ${feldName} nicht finden, um Kundennamen anzuzeigen.`);
							}
						}
					});
				}, 800); // Verzögerung, um Rendering und read-only Status abzuwarten
			}
		});
		
		// Verstecke das Datum-Feld in allen Produktauswahl-Tabellen und setze Item-Filter
		for (let i = 1; i <= 15; i++) {
			const fieldName = `produktauswahl_für_gast_${i}`;
			if (frm.fields_dict[fieldName]) {
				// Verstecke das Datum-Feld in der Tabelle (damit kein Kalender erscheint)
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'hidden', 1);
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'reqd', 0);
				// Verstecke auch das Warehouse-Feld
				frm.fields_dict[fieldName].grid.update_docfield_property('warehouse', 'hidden', 1);
				frm.fields_dict[fieldName].grid.update_docfield_property('warehouse', 'reqd', 0);
				// Mache das Preisfeld schreibgeschützt
				frm.fields_dict[fieldName].grid.update_docfield_property('rate', 'read_only', 1);
				
				// Automatische Spaltenbreiten - CSS-Regeln entfernt
				// Zusätzlich: Verstecke die Spalten per CSS (robustere Methode)
				setTimeout(() => {
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-body .data-row .col[data-fieldname="delivery_date"]`).hide();
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-body .data-row .col[data-fieldname="warehouse"]`).hide();
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-heading-row .col[data-fieldname="delivery_date"]`).hide();
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-heading-row .col[data-fieldname="warehouse"]`).hide();
				
				}, 500);
				
				// Setze Standard-Spaltenbreiten wie in der manuellen Konfiguration
				if (frm.fields_dict[fieldName].grid) {
					// Spaltenbreiten entfernt - lasse Frappe automatisch wählen  
					// frm.fields_dict[fieldName].grid.update_docfield_property('item_code', 'columns', 4);
					// frm.fields_dict[fieldName].grid.update_docfield_property('qty', 'columns', 1);
					// frm.fields_dict[fieldName].grid.update_docfield_property('rate', 'columns', 2);
					// frm.fields_dict[fieldName].grid.update_docfield_property('amount', 'columns', 2);
				}
				
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
			// Verstecke auch das Warehouse-Feld
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('warehouse', 'hidden', 1);
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('warehouse', 'reqd', 0);
			// Mache das Preisfeld schreibgeschützt
			frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('rate', 'read_only', 1);
			
			// Zusätzlich: Verstecke die Spalten per CSS (robustere Methode)
			setTimeout(() => {
				$(frm.wrapper).find('[data-fieldname="produktauswahl_für_gastgeberin"] .grid-body .data-row .col[data-fieldname="delivery_date"]').hide();
				$(frm.wrapper).find('[data-fieldname="produktauswahl_für_gastgeberin"] .grid-body .data-row .col[data-fieldname="warehouse"]').hide();
				$(frm.wrapper).find('[data-fieldname="produktauswahl_für_gastgeberin"] .grid-heading-row .col[data-fieldname="delivery_date"]').hide();
				$(frm.wrapper).find('[data-fieldname="produktauswahl_für_gastgeberin"] .grid-heading-row .col[data-fieldname="warehouse"]').hide();
			}, 500);
			
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
		
		// Auch für die Gastgeber-Geschenke-Tabelle (gleiche Formatierung wie Produkttabellen)
		if (frm.fields_dict["gastgeber_geschenke"]) {
			frm.fields_dict["gastgeber_geschenke"].grid.update_docfield_property('delivery_date', 'hidden', 1);
			frm.fields_dict["gastgeber_geschenke"].grid.update_docfield_property('delivery_date', 'reqd', 0);
			// Verstecke auch das Warehouse-Feld
			frm.fields_dict["gastgeber_geschenke"].grid.update_docfield_property('warehouse', 'hidden', 1);
			frm.fields_dict["gastgeber_geschenke"].grid.update_docfield_property('warehouse', 'reqd', 0);
			// Mache das Preisfeld schreibgeschützt
			frm.fields_dict["gastgeber_geschenke"].grid.update_docfield_property('rate', 'read_only', 1);
			
			// Zusätzlich: Verstecke die Spalten per CSS (robustere Methode)
			setTimeout(() => {
				$(frm.wrapper).find('[data-fieldname="gastgeber_geschenke"] .grid-body .data-row .col[data-fieldname="delivery_date"]').hide();
				$(frm.wrapper).find('[data-fieldname="gastgeber_geschenke"] .grid-body .data-row .col[data-fieldname="warehouse"]').hide();
				$(frm.wrapper).find('[data-fieldname="gastgeber_geschenke"] .grid-heading-row .col[data-fieldname="delivery_date"]').hide();
				$(frm.wrapper).find('[data-fieldname="gastgeber_geschenke"] .grid-heading-row .col[data-fieldname="warehouse"]').hide();
			}, 500);
			
			// Setze Filter für Item-Auswahl (nur aktionsfähige Sales Items mit custom_considered_for_action = 1)
			if (frm.fields_dict["gastgeber_geschenke"].grid.get_field('item_code')) {
				frm.fields_dict["gastgeber_geschenke"].grid.get_field('item_code').get_query = function() {
					return {
						filters: {
							'is_sales_item': 1,
							'disabled': 0,
							'custom_considered_for_action': 1
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
		
		// Blauen Submit-Banner ausblenden
		setTimeout(() => {
			$(frm.wrapper).find('.form-message.blue').hide();
			$(frm.wrapper).find('.msgprint').hide();
			// Auch für zukünftige Banner
			$(frm.wrapper).find('[data-fieldtype="HTML"][data-fieldname*="submit"]').hide();
		}, 200);
		
		// Status-Feld ausblenden (wird automatisch verwaltet)
		frm.toggle_display('status', false);
		
		// Label ändern: "Name der Partei" zu "Name der Präsentation"
		frm.set_df_property('party_name', 'label', 'Name der Präsentation');
		
		// Titel im Browser-Tab und Breadcrumb ändern (robustere Methode)
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
		}
		
		// Zusätzliche UI-Verbesserungen
		function hideUnwantedElements() {
			// "Teilnehmer" Überschrift ausblenden
			$('h4:contains("Teilnehmer")').hide();
			$('.section-head:contains("Teilnehmer")').hide();
			$('[data-label="Teilnehmer"]').hide();
			
			// NUR das nicht-editierbare Eingabefeld "Name der Präsentation" ausblenden
			// NICHT den fetten Seitentitel oben links
			$('[data-fieldname="party_name"]').hide();
			$('.form-control[data-fieldname="party_name"]').hide();
			
			// Drucken-Button ausblenden
			$('.btn-default:contains("Drucken")').hide();
			$('.dropdown-item:contains("Drucken")').hide();
			$('[data-label="Drucken"]').hide();
			
			// Seitenleiste (Sidebar) ausblenden - nur für Party-Formular
			$(frm.wrapper).find('.layout-side-section').hide();
			$(frm.wrapper).find('.sidebar-area').hide();
			$(frm.wrapper).find('.form-sidebar').hide();
			// Hauptinhalt auf volle Breite erweitern
			$(frm.wrapper).find('.layout-main-section').css({
				'margin-right': '0',
				'width': '100%'
			});
			$(frm.wrapper).find('.form-layout').css({
				'margin-right': '0',
				'width': '100%'
			});
			
			// Kommentar/Mail/Aktivität-Bereiche mit weißem Abstand statt radikalem Abschnitt
			$('.form-comments').css({
				'display': 'none'
			});
			$('.comment-box').css({
				'display': 'none'
			});
			$('.form-timeline').css({
				'display': 'none'
			});
			$('.form-activity').css({
				'display': 'none'
			});
			$('.timeline-content').css({
				'display': 'none'
			});
			$('.comment-input-wrapper').css({
				'display': 'none'
			});
			$('.new-email').css({
				'display': 'none'
			});
			$('.timeline-dot').css({
				'display': 'none'
			});
		$('.scroll-to-top').css({
			'display': 'none'
		});
		$('.new-timeline').css({
			'display': 'none'
		});
		$('.comment-input-wrapper').css({
				'display': 'none'
			});
			
			// Weißen Abstand am Ende hinzufügen statt radikalem Abschnitt
			if (!$('.custom-bottom-spacing').length) {
				$('.form-layout').append('<div class="custom-bottom-spacing" style="height: 50px; background: white;"></div>');
			}
			
			// Spezifische Bereiche nach Überschrift sanft ausblenden
			$('h4:contains("Kommentare")').parent().css('display', 'none');
			$('h4:contains("Aktivität")').parent().css('display', 'none');
			$('h4:contains("E-Mail")').parent().css('display', 'none');
		}
		
		// Mehrere Versuche mit verschiedenen Timings
		setTimeout(changeTitleToPräsentation, 100);
		setTimeout(changeTitleToPräsentation, 500);
		setTimeout(changeTitleToPräsentation, 1000);
		
		setTimeout(hideUnwantedElements, 100);
		setTimeout(hideUnwantedElements, 500);
		setTimeout(hideUnwantedElements, 1000);
		
		if (frm.doc.docstatus === 1) {
			// Dokument ist eingereicht/abgeschlossen
			// Keine Änderungen mehr möglich
			frm.disable_save();
		}

		// Gutscheinstufen: erst nach dem üblichen Formular-Aufbau laden (nicht in onload)
		if (!frm._enjo_praesentation_stufen_fetch) {
			frm._enjo_praesentation_stufen_fetch = true;
			frappe.call({
				method:
					"enjo_party.enjo_party.doctype.enjo_praesentationseinstellungen.enjo_praesentationseinstellungen.get_praesentationseinstellungen",
				callback: function (r) {
					if (r.message && r.message.stufen && r.message.stufen.length) {
						frm._praesentation_stufen = r.message.stufen.map(function (s) {
							return [flt(s.mindest_umsatz), flt(s.gutschein_betrag)];
						});
					} else {
						frm._praesentation_stufen = null;
					}
					calculate_party_totals(frm);
				},
				error: function () {
					frm._praesentation_stufen = null;
				},
			});
		}
	},
	
	// Füge einen Event-Handler für die Gastgeberin hinzu
	gastgeberin: function(frm) {
		// SOFORTIGE Validierung auf Duplikate mit bereits ausgewählten Gästen
		if (!validateGastgeberinDuplicates(frm)) {
			return; // Stoppe hier, wenn Duplikat gefunden
		}
		
		// SOFORTIGE Filter-Aktualisierung
		updateKundenFilter(frm);
		
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
		
		// Header-Updates mit minimaler Verzögerung
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 100);
		
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
		// Partnerin als Versandoption hinzufügen
		if (frm.doc.partnerin) {
			promises.push(
				frappe.db.get_doc('Sales Partner', frm.doc.partnerin).then(doc => {
					optionen.push({ value: frm.doc.partnerin, label: doc.partner_name });
				})
			);
		}
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
		updateGastgeberinFilter(frm);
	},
	
	// Nach dem Speichern automatisch die Preise für alle leeren Produkte laden
	after_save(frm) {
		if (frm.doc.docstatus === 0 && !frm._skipPriceUpdates) {
			refresh_item_prices(frm);
			// Berechne auch die Gesamtsummen neu
			calculate_party_totals(frm);
		}
		// Aktualisiere die Summen-Anzeigen nach dem Speichern
		setTimeout(() => {
			updateAllSummenAnzeigen(frm);
		}, 500);
	},
	
	// Aktualisiere auch wenn Kunden hinzugefügt oder entfernt werden
	kunden_add: function(frm) {
		// SOFORTIGE Filter-Aktualisierung
		updateKundenFilter(frm);
		updateGastgeberinFilter(frm);
		
		// Header-Updates mit minimaler Verzögerung
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 100);
	},
	kunden_remove: function(frm) {
		// SOFORTIGE Filter-Aktualisierung
		updateKundenFilter(frm);
		updateGastgeberinFilter(frm);
		
		// Header-Updates mit minimaler Verzögerung
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 100);
	}
});

// Event-Handler für Party Kunde (die Zeilen in der Kundentabelle)
frappe.ui.form.on('Party Kunde', {
	kunde: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let idx = row.idx;
		
		// SOFORTIGE Validierung auf Duplikate
		if (!validateKundenDuplicates(frm, row)) {
			return; // Stoppe hier, wenn Duplikat gefunden
		}
		
		// Sofort das Versand-Label aktualisieren
		if (row.kunde) {
			frm.set_df_property(`versand_gast_${idx}`, 'label', `Versand für ${row.kunde} an:`);
		}
		
		// SOFORTIGE Filter-Aktualisierung (ohne Verzögerung)
		updateKundenFilter(frm);
		updateGastgeberinFilter(frm);
		
		// Header-Updates mit minimaler Verzögerung
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 100);
	},
	
	// Zusätzlicher Event-Handler für das Verlassen des Feldes
	kunde_on_form_rendered: function(frm, cdt, cdn) {
		// Stelle sicher, dass Filter immer aktuell sind
		updateKundenFilter(frm);
		updateGastgeberinFilter(frm);
	},
	
	// Event-Handler für das Entfernen von Zeilen
	before_kunden_remove: function(frm, cdt, cdn) {
		// Filter nach dem Entfernen aktualisieren
		setTimeout(() => {
			updateKundenFilter(frm);
			updateGastgeberinFilter(frm);
			updateCustomHeaders(frm);
		}, 50);
	}
});

// Event-Handler für Sales Order Item - Nur Menge automatisch auf 1 setzen
frappe.ui.form.on('Sales Order Item', {
	item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.item_code) {
			setTimeout(() => updateAllSummenAnzeigen(frm), 300);
			return;
		}
		// flt: auch String "0" / leere Menge zuverlässig erkennen (Race mit Preis-Callback vermeiden)
		if (flt(row.qty) <= 0) {
			frappe.model.set_value(cdt, cdn, 'qty', 1);
		}
		row = locals[cdt][cdn];

		const requested_item_code = row.item_code;
		frappe.db.get_doc("Item", requested_item_code)
			.then(item_doc => {
				const r = locals[cdt][cdn];
				if (!r || r.item_code !== requested_item_code || item_doc.name !== requested_item_code) {
					return;
				}
				frappe.model.set_value(cdt, cdn, 'uom', item_doc.stock_uom);
				frappe.model.set_value(cdt, cdn, 'stock_uom', item_doc.stock_uom);
				frappe.model.set_value(cdt, cdn, 'conversion_factor', 1.0);
				frappe.model.set_value(cdt, cdn, 'uom_conversion_factor', 1.0);
				if (!r.item_name) {
					frappe.model.set_value(cdt, cdn, 'item_name', item_doc.item_name);
				}
				const r2 = locals[cdt][cdn];
				if (!flt(r2.stock_qty)) {
					frappe.model.set_value(cdt, cdn, 'stock_qty', flt(r2.qty) || 1);
				}
			})
			.catch(() => {});

		get_item_price(frm, locals[cdt][cdn]);

		setTimeout(() => {
			updateAllSummenAnzeigen(frm);
		}, 500);
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
			// Aktualisiere die Summen-Anzeigen
			updateAllSummenAnzeigen(frm);
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
			// Aktualisiere die Summen-Anzeigen
			updateAllSummenAnzeigen(frm);
		}
	}
});

// Event-Handler speziell für Gastgeber-Geschenke Tabelle
frappe.ui.form.on('Party', {
	gastgeber_geschenke_add: function(frm) {
		// Aktualisiere die Summe wenn eine Zeile hinzugefügt wird
		setTimeout(() => {
			updateGastgeberGeschenkeSumme(frm);
		}, 300);
	},
	gastgeber_geschenke_remove: function(frm) {
		// Aktualisiere die Summe wenn eine Zeile entfernt wird
		setTimeout(() => {
			updateGastgeberGeschenkeSumme(frm);
		}, 300);
	}
});

// Funktion, um alle Tabellen mit Preisen zu aktualisieren
function refresh_item_prices(frm) {
	// Finde alle Produkte mit fehlenden Preisen und aktualisiere sie
	update_all_empty_prices(frm);
}

// Funktion, um den Preis eines Artikels abzurufen
function get_item_price(frm, row) {
	if (!row || !row.item_code || !row.doctype || !row.name) {
		return;
	}
	const cdt = row.doctype;
	const cdn = row.name;
	const item_code_requested = row.item_code;

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
				conversion_factor: flt(row.conversion_factor) || 1.0,
				qty: flt(row.qty) || 1.0,
				price_list_uom_dependant: 1,
				transaction_date: frappe.datetime.get_today()
			}
		},
		callback: function(r) {
			const line = locals[cdt] && locals[cdt][cdn];
			if (!line || line.item_code !== item_code_requested) {
				return;
			}
			if (!r.message) {
				return;
			}
			// Nach async-Response: Menge kann noch 0 gewesen sein → sonst kein Betrag
			if (flt(line.qty) <= 0) {
				frappe.model.set_value(cdt, cdn, 'qty', 1);
			}
			const fresh = locals[cdt][cdn];
			const list_rate = flt(r.message.price_list_rate);
			fresh.rate = list_rate;
			fresh.price_list_rate = list_rate;
			fresh.base_price_list_rate = list_rate;
			fresh.base_rate = list_rate;
			fresh.item_name = r.message.item_name || fresh.item_code;
			fresh.price_list = r.message.price_list;
			if (r.message.uom) {
				fresh.uom = r.message.uom;
			}
			fresh.conversion_factor = flt(r.message.conversion_factor) || 1.0;
			if (r.message.stock_uom) {
				fresh.stock_uom = r.message.stock_uom;
			}

			const q = flt(fresh.qty) || 1;
			fresh.amount = q * flt(fresh.rate);
			fresh.base_amount = fresh.amount;

			if (fresh.parentfield) {
				frm.refresh_field(fresh.parentfield);
			}
			calculate_party_totals(frm);
			updateAllSummenAnzeigen(frm);
		}
	});
}

// Aktualisiere alle leeren Preise in allen Produkttabellen
function update_all_empty_prices(frm) {
	// Lade Aktionseinstellungen dynamisch, um Aktionsartikel-Codes zu bekommen
	frappe.call({
		method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
		async: false,
		callback: function(r) {
			let aktionsCodes = [];
			if (r.message) {
				let settings = r.message;
				const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
				const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
				aktionsCodes = [...standardVariants, ...premiumVariants].map(v => v.code).filter(Boolean);
			}
			console.log("Schutz für Aktionsartikel-Codes:", aktionsCodes);
			
			// Für jede Produkttabelle durchgehen
			for (let i = 1; i <= 15; i++) {
				const field_name = `produktauswahl_für_gast_${i}`;
				if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
					frm.doc[field_name].forEach(function(item) {
						// WICHTIG: Nicht überschreiben, wenn es ein Gutschein-reduzierter Artikel oder Aktionsartikel ist!
						let istAktionsartikel = aktionsCodes.includes(item.item_code);
						if (item.item_code && (!item.rate || item.rate == 0) && !item._gutschein_angewendet && !istAktionsartikel) {
							get_item_price(frm, item);
						}
					});
				}
			}
			
			// Auch für die Gastgeberin-Tabelle
			if (frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
				frm.doc.produktauswahl_für_gastgeberin.forEach(function(item) {
					// WICHTIG: Nicht überschreiben, wenn es ein Gutschein-reduzierter Artikel oder Aktionsartikel ist!
					let istAktionsartikel = aktionsCodes.includes(item.item_code);
					if (item.item_code && (!item.rate || item.rate == 0) && !item._gutschein_angewendet && !istAktionsartikel) {
						get_item_price(frm, item);
					}
				});
			}

			// Gastgeber-Geschenke (gleiche Logik wie andere Produkttabellen)
			if (frm.doc.gastgeber_geschenke && frm.doc.gastgeber_geschenke.length > 0) {
				frm.doc.gastgeber_geschenke.forEach(function(item) {
					let istAktionsartikel = aktionsCodes.includes(item.item_code);
					if (item.item_code && (!item.rate || item.rate == 0) && !item._gutschein_angewendet && !istAktionsartikel) {
						get_item_price(frm, item);
					}
				});
			}
		}
	});
}

// Funktion zur Berechnung der Party-Gesamtsummen
function calculate_party_totals(frm) {
	let total_amount = 0.0;
	
	// Berechne Gesamtumsatz aus allen Produkttabellen
	// HINWEIS: Versandkosten werden NICHT hier berechnet, sondern automatisch 
	// beim Erstellen der Aufträge basierend auf der neuen 7-Artikel-Versandlogik hinzugefügt
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
	
	// Setze Gesamtumsatz NUR wenn wir nicht in der Aufträge-Erstellung sind
	// (um Gutschrift-reduzierten Gesamtumsatz zu bewahren)
	if (!frm._skipTotalCalculation) {
		frm.set_value('gesamtumsatz', total_amount);

		// Berechne Gutscheinwert basierend auf Präsentationsumsatz-Stufen
		// NUR für Party-Dokumente (prüfe ob das Feld existiert)
		if (frm.doc.gastgeberin && frm.fields_dict.gastgeber_gutschein_wert) {
			const gutschein_wert = calculate_gutschein_value(total_amount, frm);
			frm.set_value('gastgeber_gutschein_wert', gutschein_wert);
		}
	}
}

// Gutschein-Stufen: gleiche Default wie Server, bis get_praesentationseinstellungen geladen hat
function calculate_gutschein_value(total_amount, frm) {
	const fallback_stufen = [
		[0, 0],
		[350, 30],
		[600, 60],
		[850, 95],
		[1100, 130],
	];
	const stufen =
		frm && frm._praesentation_stufen && frm._praesentation_stufen.length
			? frm._praesentation_stufen
			: fallback_stufen;
	let gutschein_wert = 0;
	for (let i = 0; i < stufen.length; i++) {
		const mindest_umsatz = stufen[i][0];
		const gutschein_betrag = stufen[i][1];
		if (total_amount >= mindest_umsatz) {
			gutschein_wert = gutschein_betrag;
		} else {
			break;
		}
	}
	return gutschein_wert;
}

// Neue Hilfsfunktionen zum Aktivieren/Deaktivieren der Pflichtfelder
function disableRequiredFields(frm) {
	// Für Gastgeberin-Tabelle
	if (frm.fields_dict["produktauswahl_für_gastgeberin"]) {
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('item_code', 'reqd', 0);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('item_name', 'reqd', 0);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('qty', 'reqd', 0);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('uom', 'reqd', 0);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('conversion_factor', 'reqd', 0);
	}

	// Für alle Gäste-Tabellen
	for (let i = 1; i <= 15; i++) {
		let fieldName = `produktauswahl_für_gast_${i}`;
		if (frm.fields_dict[fieldName]) {
			frm.fields_dict[fieldName].grid.update_docfield_property('item_code', 'reqd', 0);
			frm.fields_dict[fieldName].grid.update_docfield_property('item_name', 'reqd', 0);
			frm.fields_dict[fieldName].grid.update_docfield_property('qty', 'reqd', 0);
			frm.fields_dict[fieldName].grid.update_docfield_property('uom', 'reqd', 0);
			frm.fields_dict[fieldName].grid.update_docfield_property('conversion_factor', 'reqd', 0);
		}
	}
}

function enableRequiredFields(frm) {
	// Für Gastgeberin-Tabelle
	if (frm.fields_dict["produktauswahl_für_gastgeberin"]) {
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('item_code', 'reqd', 1);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('item_name', 'reqd', 1);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('qty', 'reqd', 1);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('uom', 'reqd', 1);
		frm.fields_dict["produktauswahl_für_gastgeberin"].grid.update_docfield_property('conversion_factor', 'reqd', 1);
	}

	// Für alle Gäste-Tabellen
	for (let i = 1; i <= 15; i++) {
		let fieldName = `produktauswahl_für_gast_${i}`;
		if (frm.fields_dict[fieldName]) {
			frm.fields_dict[fieldName].grid.update_docfield_property('item_code', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('item_name', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('qty', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('uom', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('conversion_factor', 'reqd', 1);
		}
	}
}
// Neue Funktion zur Warehouse-Korrektur vor dem Speichern
function fixAllWarehouses(frm) {
	// Funktion nicht mehr benötigt - get_default_warehouse() wird direkt verwendet
	console.log("fixAllWarehouses aufgerufen, aber nicht mehr benötigt");
}

// === CSS-REGELN FÜR SPALTEN-VERSTECKEN ===

// Funktion zum Einfügen permanenter CSS-Regeln die Spalten verstecken
function addPermanentColumnHideCSS() {
	// Prüfe ob die CSS-Regeln schon existieren
	if (document.getElementById('party-column-hide-css')) {
		return; // Bereits eingefügt
	}
	
	// Erstelle CSS-Regeln zum Verstecken der delivery_date und warehouse Spalten
	let css = `
		/* Verstecke delivery_date und warehouse Spalten in allen Party-Produkttabellen */
		[data-fieldname*="produktauswahl_für_gast"] .grid-heading-row .col[data-fieldname="delivery_date"],
		[data-fieldname*="produktauswahl_für_gast"] .grid-body .data-row .col[data-fieldname="delivery_date"],
		[data-fieldname*="produktauswahl_für_gast"] .grid-heading-row .col[data-fieldname="warehouse"],
		[data-fieldname*="produktauswahl_für_gast"] .grid-body .data-row .col[data-fieldname="warehouse"],
		[data-fieldname="produktauswahl_für_gastgeberin"] .grid-heading-row .col[data-fieldname="delivery_date"],
		[data-fieldname="produktauswahl_für_gastgeberin"] .grid-body .data-row .col[data-fieldname="delivery_date"],
		[data-fieldname="produktauswahl_für_gastgeberin"] .grid-heading-row .col[data-fieldname="warehouse"],
		[data-fieldname="produktauswahl_für_gastgeberin"] .grid-body .data-row .col[data-fieldname="warehouse"],
		[data-fieldname="gastgeber_geschenke"] .grid-heading-row .col[data-fieldname="delivery_date"],
		[data-fieldname="gastgeber_geschenke"] .grid-body .data-row .col[data-fieldname="delivery_date"],
		[data-fieldname="gastgeber_geschenke"] .grid-heading-row .col[data-fieldname="warehouse"],
		[data-fieldname="gastgeber_geschenke"] .grid-body .data-row .col[data-fieldname="warehouse"] {
			display: none !important;
		}
	`;
	
	// Füge CSS in den Head ein
	let style = document.createElement('style');
	style.id = 'party-column-hide-css';
	style.type = 'text/css';
	style.innerHTML = css;
	document.head.appendChild(style);
	
	console.log("Permanente CSS-Regeln zum Verstecken der Spalten hinzugefügt");
}

// === SUMMEN-ANZEIGE FUNKTIONEN ===

// Funktion zum Berechnen und Anzeigen der Summe für eine Tabelle
function updateSummeForTable(frm, tableName, sumFieldName) {
	let sum = 0;
	let aktionsfaehigeItems = [];
	
	if (frm.doc[tableName] && frm.doc[tableName].length > 0) {
		frm.doc[tableName].forEach(function(item) {
			if (item.qty && item.rate) {
				sum += flt(item.qty) * flt(item.rate);
				// Sammle Items für Aktionsfähigkeits-Prüfung
				aktionsfaehigeItems.push(item);
			}
		});
	}
	
	// Prüfe Aktionsfähigkeit und zeige Summe an
	if (aktionsfaehigeItems.length > 0) {
		checkAktionsfaehigkeitForSumme(aktionsfaehigeItems, sum, frm, sumFieldName);
	} else {
		if (frm.fields_dict[sumFieldName]) {
			let htmlContent = `<div style="text-align: right; font-weight: bold; color: black; margin-top: 5px; margin-bottom: 10px;">Summe: ${format_currency(sum)}</div>`;
			frm.fields_dict[sumFieldName].$wrapper.html(htmlContent);
		}
	}
}

function checkAktionsfaehigkeitForSumme(items, gesamtsumme, frm, sumFieldName) {
	// Lade Aktionseinstellungen
	frappe.call({
		method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
		async: true,
		callback: function(r) {
			let aktionsCodes = [];
			if (r.message) {
				let settings = r.message;
				const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
				const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
				aktionsCodes = [...standardVariants, ...premiumVariants].map(v => v.code).filter(Boolean);
			}
			
			// Berechne Summe der aktionsfähigen Produkte
			let aktionsfaehigeSumme = 0;
			let checkedCount = 0;
			
			items.forEach(function(item, index) {
				if (!item.item_code) {
					checkedCount++;
					if (checkedCount === items.length) {
						displaySummeWithAktionsfaehig();
					}
					return;
				}
				
				// Prüfe zuerst ob es ein Aktionsartikel-Code ist
				let istAktionsartikelCode = aktionsCodes.includes(item.item_code);
				
				if (istAktionsartikelCode) {
					aktionsfaehigeSumme += flt(item.qty) * flt(item.rate);
					checkedCount++;
					if (checkedCount === items.length) {
						displaySummeWithAktionsfaehig();
					}
					return;
				}
				
				// Prüfe auch custom_considered_for_action Feld
				frappe.call({
					method: "frappe.client.get_value",
					args: {
						doctype: "Item",
						filters: {
							item_code: item.item_code
						},
						fieldname: "custom_considered_for_action"
					},
					async: true,
					callback: function(result) {
						if (result.message && result.message.custom_considered_for_action) {
							aktionsfaehigeSumme += flt(item.qty) * flt(item.rate);
						}
						
						checkedCount++;
						if (checkedCount === items.length) {
							displaySummeWithAktionsfaehig();
						}
					}
				});
			});
			
			function displaySummeWithAktionsfaehig() {
				if (frm.fields_dict[sumFieldName]) {
					let htmlContent = `
						<div style="text-align: right; margin-top: 5px; margin-bottom: 10px;">
							<div style="font-weight: bold; color: black;">Summe: ${format_currency(gesamtsumme)}</div>
							${aktionsfaehigeSumme > 0 ? `<div style="font-size: 0.9em; color: #666; margin-top: 3px;">Davon aktionsfähig: ${format_currency(aktionsfaehigeSumme)}</div>` : ''}
						</div>
					`;
					frm.fields_dict[sumFieldName].$wrapper.html(htmlContent);
				}
			}
		}
	});
}

// Funktion zum Berechnen und Anzeigen der Gastgeber-Geschenke Summe mit Gutschein-Verbrauch
function updateGastgeberGeschenkeSumme(frm) {
	let sum = 0;
	let sumReferenz = 0; // Referenz-Warenwert (Listenpreis / Backup) für Zuzahlen
	let gutscheinAusPreisdelta = 0;
	const rows = [];

	if (frm.doc.gastgeber_geschenke && frm.doc.gastgeber_geschenke.length > 0) {
		frm.doc.gastgeber_geschenke.forEach(function(item, index) {
			if (!item.item_code || flt(item.qty) <= 0) {
				return;
			}
			const qty = flt(item.qty);
			const rate = flt(item.rate);
			const cur = flt(item.amount) || (qty * rate);
			sum += cur;
			rows.push({ item: item, index: index, cur: cur });

			const backupKey = `gastgeber_geschenke_${index}`;
			let refTotal = cur;
			if (frm.originalPricesBackup && frm.originalPricesBackup[backupKey]) {
				refTotal = flt(frm.originalPricesBackup[backupKey].originalAmount);
			} else {
				const pls = flt(item.price_list_rate);
				if (pls > rate + 0.001) {
					refTotal = qty * pls;
				}
			}
			sumReferenz += refTotal;
			gutscheinAusPreisdelta += Math.max(0, refTotal - cur);
		});
	}

	let gutscheinWert = flt(frm.doc.gastgeber_gutschein_wert || 0);
	gutscheinAusPreisdelta = Math.min(gutscheinWert, gutscheinAusPreisdelta);

	function renderSummeGastgeberGeschenke(anzeigeGutschein) {
		let zuzahlen = Math.max(0, sumReferenz - anzeigeGutschein);
		if (!frm.fields_dict['summe_gastgeber_geschenke']) {
			return;
		}
		const zeigeGutscheinZeile = gutscheinWert > 0 || anzeigeGutschein > 0;
		let htmlContent = `
			<div style="text-align: right; margin-top: 10px; margin-bottom: 10px;">
				<div style="font-weight: bold; color: black; margin-bottom: 5px;">
					Gesamt: ${format_currency(sum)}
				</div>
				${zeigeGutscheinZeile ? `<div style="color: #666; font-size: 0.9em; margin-bottom: 3px;">
					Davon über Gutschein: ${format_currency(anzeigeGutschein)}
				</div>` : ''}
				${zuzahlen > 0 ? `<div style="font-size: 0.9em; color: #666; margin-top: 3px;">Selbst gezahlt: ${format_currency(zuzahlen)}</div>` : ''}
			</div>
		`;
		frm.fields_dict['summe_gastgeber_geschenke'].$wrapper.html(htmlContent);
	}

	// Bereits im Betrag sichtbarer Gutschein (nach Anwendung / reduzierten Preisen)
	if (gutscheinAusPreisdelta >= 0.01) {
		renderSummeGastgeberGeschenke(gutscheinAusPreisdelta);
		return;
	}

	if (gutscheinWert <= 0 || rows.length === 0) {
		renderSummeGastgeberGeschenke(0);
		return;
	}

	// Vorschau: wie berechneGutscheinVerbrauch – nur aktionsfähige Artikel, Reihenfolge der Tabelle
	let checked = 0;
	const eligibleByIndex = [];

	function finishVorschauGutschein() {
		eligibleByIndex.sort(function (a, b) {
			return a.index - b.index;
		});
		let rest = gutscheinWert;
		let verbraucht = 0;
		for (let i = 0; i < eligibleByIndex.length && rest > 0; i++) {
			const line = eligibleByIndex[i];
			const take = Math.min(rest, line.amount);
			verbraucht += take;
			rest -= take;
		}
		renderSummeGastgeberGeschenke(Math.min(gutscheinWert, verbraucht));
	}

	function oneRowChecked() {
		checked++;
		if (checked === rows.length) {
			finishVorschauGutschein();
		}
	}

	rows.forEach(function (row) {
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Item",
				filters: { item_code: row.item.item_code },
				fieldname: 'custom_considered_for_action',
			},
			callback: function (r) {
				if (r && r.message && r.message.custom_considered_for_action) {
					eligibleByIndex.push({ index: row.index, amount: row.cur });
				}
				oneRowChecked();
			},
			error: function () {
				oneRowChecked();
			},
		});
	});
}

// Funktion zum Aktualisieren aller Summen-Anzeigen
function updateAllSummenAnzeigen(frm) {
	// Gastgeberin-Summe
	updateSummeForTable(frm, 'produktauswahl_für_gastgeberin', 'summe_gastgeberin');
	
	// Gäste-Summen
	for (let i = 1; i <= 15; i++) {
		let tableName = `produktauswahl_für_gast_${i}`;
		let sumFieldName = `summe_gast_${i}`;
		updateSummeForTable(frm, tableName, sumFieldName);
	}
	
	// Gastgeber-Geschenke Summe (auch bei gebuchter Party / Übersicht)
	updateGastgeberGeschenkeSumme(frm);
}

// === ENDE SUMMEN-ANZEIGE FUNKTIONEN ===

// Realtime-Event-Listener für Status-Updates
frappe.realtime.on("party_status_updated", function(data) {
	if (data && data.doctype === "Party" && data.name) {
		// Prüfe ob das Dokument aktuell geöffnet ist
		let frm = frappe.get_route()[0] === "Form" && 
		          frappe.get_route()[1] === "Party" && 
		          frappe.get_route()[2] === data.name ?
		          cur_frm : null;
		
		if (frm && frm.doc && frm.doc.name === data.name) {
			// Dokument ist geöffnet - lade es neu
			frm.reload_doc();
		}
	}
});

// Validiere Aktionsartikel...
