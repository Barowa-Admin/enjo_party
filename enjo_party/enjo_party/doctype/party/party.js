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
		// Für gebuchte Parties: "Zu den Aufträgen" Button anzeigen
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Zu den Aufträgen"), function() {
				frappe.set_route("List", "Sales Order", {
					"custom_party_reference": frm.doc.name
				});
			}).addClass("btn-primary");
		}
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
					// Aktions-System direkt aufrufen
					startAktionsSystem(frm, function() {
						console.log("Aktions-System abgeschlossen - erstelle Aufträge");
						// Nach Aktionsprüfung Aufträge erstellen
						erstelleAuftraege(frm);
					});
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
			
			// Artikelvariablen aus den Einstellungen
			const v1_code = settings.v1_code;
			const v2_code = settings.v2_code;
			const v3_code = settings.v3_code;
			const v4_code = settings.v4_code;
			const v5_code = settings.v5_code;
			const v6_code = settings.v6_code;
			const v7_code = settings.v7_code;
			
			// Artikelnamen aus den Einstellungen
			const v1_name = settings.v1_name;
			const v2_name = settings.v2_name;
			const v3_name = settings.v3_name;
			const v4_name = settings.v4_name;
			const v5_name = settings.v5_name;
			const v6_name = settings.v6_name;
			const v7_name = settings.v7_name;
			
			// Array mit allen Aktionsartikeln
			const allAktionsCodes = [v1_code, v2_code, v3_code, v4_code, v5_code, v6_code, v7_code];
			
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
							if (total > STAGE_1_MAX) {
								stage = 2; // Premium
							} else if (total > STAGE_1_MIN) {
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
								total += item.amount || 0;
								console.log(`${teilnehmer_obj.displayName}: Item ${item.item_code} aktionsfähig (${item.amount || 0} EUR)`);
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
						optionen = ["", v1_name, v2_name, v3_name, v4_name];
						stageText = "Standard";
					} else if (teilnehmer.stage === 2) {
						optionen = ["", v5_name, v6_name, v7_name];
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
								
								frappe.show_alert(`${aktionsartikelHinzugefuegt} Aktionsartikel wurden hinzugefügt!`, 5);
							}
							
							d.hide();
							callback();
						}).catch((error) => {
							console.error("Fehler beim Hinzufügen der Aktionsartikel:", error);
							// Entferne die Fehlermeldung, da die Artikel trotzdem hinzugefügt wurden
							console.log("Artikel wurden trotz Fehler hinzugefügt - fahre fort");
							d.hide();
							callback(); // Auch bei Fehlern fortfahren
						});
					},
					secondary_action_label: 'Alle ablehnen',
					secondary_action: function() {
						console.log("Alle Aktionen abgelehnt");
						d.hide();
						callback();
					}
				});
				
				d.show();
			}
			
			function getItemCodeFromName(itemName) {
				switch(itemName) {
					case v1_name: return v1_code;
					case v2_name: return v2_code;
					case v3_name: return v3_code;
					case v4_name: return v4_code;
					case v5_name: return v5_code;
					case v6_name: return v6_code;
					case v7_name: return v7_code;
					default: return null;
				}
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
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'delivery_date', frappe.datetime.add_days(frappe.datetime.nowdate(), 7));
								
								// FLEXIBLES WAREHOUSE: Verwende Standard-Warehouse oder erstes verfügbares
								let warehouse = frappe.defaults.get_user_default("Warehouse");
								if (!warehouse) {
									// Fallback: Verwende erstes verfügbares nicht-Gruppen-Warehouse
									frappe.call({
										method: "frappe.client.get_list",
										args: {
											doctype: "Warehouse",
											filters: {"is_group": 0},
											fields: ["name"],
											limit: 1
										},
										async: false,
										callback: function(wh_r) {
											if (wh_r.message && wh_r.message.length > 0) {
												warehouse = wh_r.message[0].name;
											}
										}
									});
								}
								
								if (warehouse) {
									frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'warehouse', warehouse);
								}
								
								// Markierung für Aktionsartikel (als separates Feld falls nötig)
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, '_aktionsartikel', true);
								
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
			console.log("Gastgeber hat keine aktionsfähigen Produkte - zeige Vollbetrag-Dialog");
			// WICHTIG: Auch bei 0 aktionsfähigen Produkten den Dialog zeigen!
			zeigeRestbetragDialog(gutscheinWert, frm, callback);
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
			
			// Setze Preis auf 0 und markiere als Gutschein-reduziert
			produkt.item.rate = 0;
			produkt.item.amount = 0;
			produkt.item._gutschein_angewendet = true; // WICHTIGE MARKIERUNG!
			
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
			if (istVollbetrag) {
				// Bei Vollbetrag: Zurück zur Bearbeitung (Produkte hinzufügen)
				stelleOriginalPreiseWieder(frm);
				refreshButtons(frm);
			} else {
				// Bei Restbetrag: Zurück zur Bearbeitung
				stelleOriginalPreiseWieder(frm);
				refreshButtons(frm);
			}
		},
		secondary_action_label: istVollbetrag ? 'Gutschein verfallen lassen' : 'Restbetrag verfallen lassen',
		secondary_action: function() {
			dialog.hide();
			if (istVollbetrag) {
				// Bei Vollbetrag: Gutschein verfällt, aber Party wird trotzdem gebucht
				console.log("DEBUG: Vollbetrag - Gutschein verfällt, rufe callback auf");
				frappe.show_alert(`Gutschein von ${restbetrag.toFixed(2)}€ verfällt - fahre mit Bestellung fort`, 3);
				callback(); // WICHTIG: Weiter zum Aktions-System!
			} else {
				// Bei Restbetrag: Verfallen lassen und fortfahren
				console.log("DEBUG: Restbetrag - verfällt, rufe callback auf");
				let nachricht = `Restbetrag von ${restbetrag.toFixed(2)}€ verfällt`;
				frappe.show_alert(nachricht, 3);
				// Weiter zum nächsten Schritt
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
	
	// Gehe durch alle gespeicherten Original-Preise
	for (let backupKey in frm.originalPricesBackup) {
		let backup = frm.originalPricesBackup[backupKey];
		let item = backup.item;
		
		// Stelle Original-Preis und -Betrag wieder her
		item.rate = backup.originalRate;
		item.amount = backup.originalAmount;
		// Entferne Gutschein-Markierung
		delete item._gutschein_angewendet;
		
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
	
	// WICHTIG: Setze Flags, um automatische Updates zu verhindern
	frm._skipTotalCalculation = true;
	frm._skipPriceUpdates = true;
	
	// SOFORT den Screen "einfrieren" mit Frappe's Freeze-Mechanismus
	frappe.freeze_screen = true;
	frappe.show_alert({
		message: __("Bereite Aufträge vor..."),
		indicator: "blue"
	});
	
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
	frappe.show_alert({
			message: __("Erstelle Aufträge..."),
			indicator: "orange"
		});
		
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
			
			// Aktionsartikel-Codes aus den Einstellungen
			const aktionsCodes = [
				settings.v1_code,
				settings.v2_code, 
				settings.v3_code,
				settings.v4_code,
				settings.v5_code,
				settings.v6_code,
				settings.v7_code
			].filter(code => code); // Filter leere Codes heraus
			
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
						if (!item.rate) item.rate = 0;
						if (!item.amount) item.amount = 0;
						if (!item.uom) item.uom = "Stk";
						if (!item.stock_uom) item.stock_uom = "Stk";
						if (!item.conversion_factor) item.conversion_factor = 1;
						if (!item.delivery_date) item.delivery_date = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
						if (!item.warehouse) item.warehouse = "Lagerräume - BM";
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
							if (!item.rate) item.rate = 0;
							if (!item.amount) item.amount = 0;
							if (!item.uom) item.uom = "Stk";
							if (!item.stock_uom) item.stock_uom = "Stk";
							if (!item.conversion_factor) item.conversion_factor = 1;
							if (!item.delivery_date) item.delivery_date = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
							if (!item.warehouse) item.warehouse = "Lagerräume - BM";
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
	console.log("DEBUG: erstelleAuftraegeDirectly aufgerufen - NEUE VERSION");
	console.log("erstelleAuftraegeDirectly aufgerufen");
	
	// WICHTIG: Setze Schutz-Flag direkt im Dokument
	frm.doc._skip_total_calculation = 1;
	
	// SKIP: Das Speichern verursacht Probleme - die API macht das automatisch
	console.log("DEBUG: Überspringe Speichern - rufe API direkt auf");
	callCreateInvoicesAPI();
	
	// ALTE PROBLEMATISCHE LOGIK (auskommentiert):
	// KRITISCH: ERST das Dokument speichern, damit Aktionsartikel in die DB geschrieben werden!
	// console.log("SPEICHERE DOKUMENT VOR API-AUFRUF...");
	// frm.save().then(() => {
	// 	console.log("DEBUG: Dokument erfolgreich gespeichert - rufe jetzt API auf");
	// 	callCreateInvoicesAPI();
	// }).catch((error) => {
	// 	console.error("DEBUG: Fehler beim Speichern des Dokuments:", error);
	// 	console.log("DEBUG: Speichern fehlgeschlagen - versuche API trotzdem (wird automatisch speichern)");
	// 	// Versuche trotzdem die API aufzurufen - die API speichert automatisch
	// 	callCreateInvoicesAPI();
	// });
	
	function callCreateInvoicesAPI() {
		console.log("DEBUG: Starte API-Aufruf");
		frappe.call({
			method: "enjo_party.enjo_party.doctype.party.party.create_invoices",
			args: {
				party: frm.doc.name,
				from_button: true  // Flag, um zu zeigen, dass der Aufruf vom Button kommt
			},
			freeze: true,
		freeze_message: __("Erstelle und reiche Aufträge ein..."),
			callback: function(r) {
			console.log("DEBUG: API-Antwort erhalten:", r);
			// Screen wieder freigeben
			frappe.freeze_screen = false;
			
			// WICHTIG: Flags zurücksetzen, damit normale Funktionalität wiederhergestellt wird
			delete frm._skipTotalCalculation;
			delete frm._skipPriceUpdates;
			delete frm.doc._skip_total_calculation;
			
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
			console.log("DEBUG: API-Fehler aufgetreten:", r);
			// Screen wieder freigeben
			frappe.freeze_screen = false;
			
			// WICHTIG: Flags zurücksetzen auch bei Fehlern
			delete frm._skipTotalCalculation;
			delete frm._skipPriceUpdates;
			delete frm.doc._skip_total_calculation;
			
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
					
					// Mache die Artikel-Code Spalte breiter
					// $(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-heading-row .col[data-fieldname="item_code"]`).css('width', '300px');
					// $(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-body .data-row .col[data-fieldname="item_code"]`).css('width', '300px');
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
				// WICHTIG: Nicht überschreiben, wenn es ein Gutschein-reduzierter Artikel oder Aktionsartikel ist!
				if (item.item_code && (!item.rate || item.rate == 0) && !item._gutschein_angewendet && !item._aktionsartikel) {
					get_item_price(frm, item);
				}
			});
		}
	}
	
	// Auch für die Gastgeberin-Tabelle
	if (frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
		frm.doc.produktauswahl_für_gastgeberin.forEach(function(item) {
			// WICHTIG: Nicht überschreiben, wenn es ein Gutschein-reduzierter Artikel oder Aktionsartikel ist!
			if (item.item_code && (!item.rate || item.rate == 0) && !item._gutschein_angewendet && !item._aktionsartikel) {
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
	
	// Setze Gesamtumsatz NUR wenn wir nicht in der Aufträge-Erstellung sind
	// (um Gutschrift-reduzierten Gesamtumsatz zu bewahren)
	if (!frm._skipTotalCalculation) {
		frm.set_value('gesamtumsatz', total_amount);
		
		// Berechne Gutscheinwert basierend auf Präsentationsumsatz-Stufen
		const gutschein_wert = calculate_gutschein_value(total_amount);
		frm.set_value('gastgeber_gutschein_wert', gutschein_wert);
	}
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

