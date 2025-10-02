// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

// === STÖRENDE BENUTZER-MELDUNGEN AUSBLENDEN ===
(function() {
	try {
		const originalMsgprint = frappe.msgprint;
		const originalThrow = frappe.throw;
		const originalShowAlert = frappe.show_alert;
		
		frappe.msgprint = function(message, title, indicator) {
			let messageText = typeof message === 'string' ? message : 
							 (message && message.message) ? message.message : '';
			
			if (
				messageText.includes('Adresse') && messageText.includes('nicht gefunden') ||
				messageText.includes('Address') && messageText.includes('not found') ||
				messageText.includes('Source Map') ||
				messageText.includes('file_uploader.bundle') ||
				messageText.includes('JSON Parse error') ||
				messageText.includes('localStorage quota exceeded')
			) {
				console.log("GEFILTERTE BENUTZER-MELDUNG:", messageText);
				return;
			}
			
			return originalMsgprint.apply(this, arguments);
		};
		
		frappe.show_alert = function(message, seconds) {
			let messageText = typeof message === 'string' ? message : 
							 (message && message.message) ? message.message : '';
			
			if (
				messageText.includes('Adresse') && messageText.includes('nicht gefunden') ||
				messageText.includes('Address') && messageText.includes('not found') ||
				messageText.includes('Source Map') ||
				messageText.includes('file_uploader.bundle')
			) {
				console.log("GEFILTERTER ALERT:", messageText);
				return;
			}
			
			return originalShowAlert.apply(this, arguments);
		};
		
		console.log("Benutzer-Meldungsfilter für störende Frappe-Fehler aktiviert");
	} catch (e) {
		console.log("Benutzer-Meldungsfilter konnte nicht aktiviert werden:", e);
	}
})();

// === ENDE MELDUNGSFILTER ===

// Hilfsfunktion zum Wiederherstellen der Buttons basierend auf dem aktuellen Status
function refreshButtons(frm) {
	console.log("refreshButtons aufgerufen - Status:", frm.doc.status, "docstatus:", frm.doc.docstatus, "is_new:", frm.is_new());
	
	try {
		if (frm && frm.page) {
			if (frm.page.clear_custom_actions) frm.page.clear_custom_actions();
		}
	} catch (e) {
		console.error("Fehler beim Löschen der Buttons:", e);
	}
	
	if (frm.doc.docstatus === 0) {
		let isNewDoc = frm.is_new() || !frm.doc.name || frm.doc.name.startsWith('new-');
		
		if (isNewDoc) {
			console.log("Neu-Modus: Standard-Buttons verwenden");
			if (frm.page && frm.page.btn_primary) {
				frm.page.btn_primary.show();
				setTimeout(() => {
					$(frm.wrapper).find('.btn-primary').text("Speichern");
				}, 50);
			} else {
				frm.add_custom_button(__("Speichern"), function() {
					frm.save();
				}).addClass("btn-primary");
			}
		} else if (frm.doc.status === "Kunden") {
			console.log("Status Kunden: Speichern-Button hinzufügen");
			frm.add_custom_button(__("Speichern"), function() {
				frm.save();
			}).addClass("btn-primary");
		} else if (frm.doc.status === "Produkte") {
			console.log("Status Produkte: Aufträge erstellen + Speichern Buttons hinzufügen");
			frm.add_custom_button(__("Aufträge erstellen"), function() {
				startAuftraegeErstellung(frm);
			}).addClass("btn-primary");
			
			frm.add_custom_button(__("Speichern"), function() {
				frm.save();
			});
		} else {
			console.log("Unbekannter Status:", frm.doc.status);
		}
	} else {
		console.log("Dokument ist eingereicht (docstatus !== 0)");
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Zu den Aufträgen"), function() {
				frappe.set_route("List", "Sales Order", {
					"custom_party_reference": frm.doc.name
				});
			}).addClass("btn-primary");
		}
	}
}

// Hilfsfunktion zum Starten der Aufträge-Erstellung
function startAuftraegeErstellung(frm) {
	console.log("startAuftraegeErstellung aufgerufen");
	
	enableRequiredFields(frm);
	
	let kunden_ohne_produkte = [];
	
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
	
	// Prüfe alle Kunden
	for (let i = 0; i < frm.doc.kunden.length; i++) {
		let kunde = frm.doc.kunden[i];
		if (!kunde.kunde) continue;
		
		let field_name = `produktauswahl_für_kunde_${i+1}`;
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
			kunden_ohne_produkte.push(getCustomerName(kunde.kunde));
		}
	}
	
	console.log("Kunden ohne Produkte:", kunden_ohne_produkte);
	
	// Wenn alle Kunden Produkte haben, prüfe Aktionen vor der Bestätigung
	if (kunden_ohne_produkte.length === 0) {
		console.log("Alle Kunden haben Produkte - zeige Bestätigungsdialog");
		frappe.confirm(
			__("Bist Du sicher, dass alle Produkte richtig ausgewählt wurden und Du die Bestellung abschicken möchtest? Dieser Vorgang kann nicht rückgängig gemacht werden!"),
			function() {
				console.log("Benutzer hat bestätigt - starte Aktions-System");
				// Direkt zum Aktions-System (KEIN Gutschein-System mehr!)
				startAktionsSystem(frm, function() {
					console.log("Aktions-System abgeschlossen - erstelle Aufträge");
					erstelleAuftraege(frm);
				});
			}
		);
		return;
	}
	
	// Wenn Kunden ohne Produkte gefunden wurden, Dialog mit Optionen anzeigen
	let verbleibende_kunden = frm.doc.kunden.length - kunden_ohne_produkte.length;
	let kann_entfernen = verbleibende_kunden >= 2;
	
	let message = `Die folgenden Kunden haben noch keine Produkte ausgewählt:\n\n${kunden_ohne_produkte.join('\n')}\n\n`;
	
	if (kann_entfernen) {
		message += "Was möchtest Du tun?";
	} else {
		message += "Es können nicht alle Kunden ohne Produkte entfernt werden, da dann weniger als 2 Kunden übrig bleiben würden.\nBitte wähle Produkte für die fehlenden Kunden aus.";
	}
	
	let dialog = new frappe.ui.Dialog({
		title: 'Kunden ohne Produktauswahl',
		fields: [
			{
				fieldtype: 'HTML',
				options: `<p style="margin-bottom: 15px;">${message.replace(/\n/g, '<br>')}</p>`
			}
		],
		primary_action_label: kann_entfernen ? __('Kunden entfernen') : __('OK'),
		primary_action: function() {
			if (kann_entfernen) {
				let kunden_ohne_produkte_indexes = [];
				for (let i = 0; i < frm.doc.kunden.length; i++) {
					let kunde = frm.doc.kunden[i];
					if (!kunde.kunde) continue;
					
					let field_name = `produktauswahl_für_kunde_${i+1}`;
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
						kunden_ohne_produkte_indexes.push({
							index: i,
							name: kunde.kunde
						});
					}
				}
				
				kunden_ohne_produkte_indexes.sort((a, b) => b.index - a.index);
				for (let kunde of kunden_ohne_produkte_indexes) {
					frm.get_field("kunden").grid.grid_rows[kunde.index].remove();
				}
				
				frm.refresh_field("kunden");
				
				// Direkt zum Aktions-System (KEIN Gutschein-System!)
				startAktionsSystem(frm, function() {
					console.log("Aktions-System abgeschlossen - erstelle Aufträge");
					erstelleAuftraege(frm);
				});
			}
			dialog.hide();
		}
	});
	
	if (kann_entfernen) {
		dialog.set_secondary_action_label(__('Bearbeiten'));
		dialog.set_secondary_action(function() {
			dialog.hide();
		});
	}
	
	dialog.show();
}

// Aktions-System: Prüft alle Kunden auf Aktionsberechtigung und zeigt Dialog
function startAktionsSystem(frm, callback) {
	console.log("startAktionsSystem gestartet");
	
	frappe.call({
		method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
		callback: function(r) {
			if (!r.message) {
				console.error("Konnte Aktionseinstellungen nicht laden");
				callback();
				return;
			}
			
			let settings = r.message;
			console.log("Aktionseinstellungen geladen:", settings);
			
			const STAGE_1_MIN = settings.stage_1_minimum;
			const STAGE_1_MAX = settings.stage_1_maximum;
			
			const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
			const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
			
			const allStandardCodes = standardVariants.map(v => v.code).filter(Boolean);
			const allPremiumCodes = premiumVariants.map(v => v.code).filter(Boolean);
			const allAktionsCodes = [...allStandardCodes, ...allPremiumCodes];
			
			processAktionsSystemWithSettings();
			
			function processAktionsSystemWithSettings() {
				let kundenMitProdukten = [];
				
				// Alle Kunden hinzufügen
				let kundenPromises = [];
				for (let i = 0; i < frm.doc.kunden.length; i++) {
					let kunde = frm.doc.kunden[i];
					if (!kunde.kunde) continue;
					
					let field_name = `produktauswahl_für_kunde_${i+1}`;
					if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
						let hatProdukte = frm.doc[field_name].some(item => item.item_code && item.qty && item.qty > 0);
						if (hatProdukte) {
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
										let kundeName = r.message ? r.message.customer_name : kunde.kunde;
										kundenMitProdukten.push({
											name: kunde.kunde,
											displayName: kundeName,
											typ: "Kunde",
											kundeNummer: i + 1,
											produktfeld: field_name,
											produkte: frm.doc[field_name]
										});
										resolve();
									}
								});
							});
							kundenPromises.push(promise);
						}
					}
				}
				
				Promise.all(kundenPromises).then(() => {
					console.log("Gefundene Kunden mit Produkten:", kundenMitProdukten.length);
					
					if (kundenMitProdukten.length === 0) {
						console.log("Keine Kunden mit Produkten gefunden - überspringe Aktions-System");
						callback();
						return;
					}
					
					checkKundenForAction(kundenMitProdukten, 0, []);
				});
			}
			
			function checkKundenForAction(kunden, index, aktionsberechtigteKunden) {
				if (index >= kunden.length) {
					console.log("Aktionsberechtigte Kunden:", aktionsberechtigteKunden.length);
					
					if (aktionsberechtigteKunden.length > 0) {
						showAktionsDialog(aktionsberechtigteKunden);
					} else {
						console.log("Keine aktionsberechtigten Kunden gefunden");
						callback();
					}
					return;
				}
				
				let kunde_obj = kunden[index];
				console.log(`Prüfe Kunde: ${kunde_obj.displayName} (${kunde_obj.typ})`);
				
				checkItemsForAction(kunde_obj.produkte, 0, [], 0, kunde_obj);
				
				function checkItemsForAction(items, itemIndex, actionItems, total, kunde_obj) {
					if (itemIndex >= items.length) {
						console.log(`${kunde_obj.displayName}: ${actionItems.length} aktionsfähige Items, Summe: ${total}`);
						
						let hasAktionsartikel = items.some(item => allAktionsCodes.includes(item.item_code));
						
						if (actionItems.length > 0 && !hasAktionsartikel) {
							let stage = null;
							if (total >= STAGE_1_MAX) {
								stage = 2;
							} else if (total >= STAGE_1_MIN) {
								stage = 1;
							}
							
							if (stage) {
								aktionsberechtigteKunden.push({
									...kunde_obj,
									aktionssumme: total,
									stage: stage,
									aktionsItems: actionItems
								});
							}
						}
						
						checkKundenForAction(kunden, index + 1, aktionsberechtigteKunden);
						return;
					}
					
					let item = items[itemIndex];
					
					if (!item.item_code || !item.qty || item.qty <= 0) {
						checkItemsForAction(items, itemIndex + 1, actionItems, total, kunde_obj);
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
								console.log(`${kunde_obj.displayName}: Item ${item.item_code} aktionsfähig (${item.amount || 0} EUR)`);
							}
							
							checkItemsForAction(items, itemIndex + 1, actionItems, total, kunde_obj);
						}
					});
				}
			}
			
			function showAktionsDialog(aktionsberechtigteKunden) {
				console.log("Zeige Aktions-Dialog für", aktionsberechtigteKunden.length, "Kunden");
				
				let dialogFields = [
					{
						fieldtype: 'HTML',
						fieldname: 'description',
						options: `
							<div style="margin-bottom: 15px;">
								<h4>Herzlichen Glückwunsch!</h4>
								<p>Die folgenden Kunden sind für unsere aktuelle Aktion berechtigt:</p>
							</div>
						`
					}
				];
				
				aktionsberechtigteKunden.forEach((kunde, index) => {
					let optionen = [];
					let stageText = "";
					
					if (kunde.stage === 1) {
						optionen = [""].concat(standardVariants.map(v => v.name || v.code).filter(Boolean));
						stageText = "Standard";
					} else if (kunde.stage === 2) {
						optionen = [""].concat(premiumVariants.map(v => v.name || v.code).filter(Boolean));
						stageText = "Premium";
					}
					
					dialogFields.push({
						fieldtype: 'HTML',
						fieldname: `kunde_info_${index}`,
						options: `
							<div style="margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
								<strong>${kunde.displayName}</strong><br>
								<small>Aktionssumme: ${kunde.aktionssumme.toFixed(2)} EUR - ${stageText} Aktion</small>
							</div>
						`
					});
					
					dialogFields.push({
						fieldtype: 'Select',
						fieldname: `aktion_artikel_${index}`,
						label: `Aktionsartikel für ${kunde.displayName}`,
						options: optionen,
						default: ""
					});
				});
				
				dialogFields.push({
					fieldtype: 'HTML',
					fieldname: 'footer_info',
					options: `
						<div style="margin-top: 15px; padding: 10px; background-color: #fff3cd; border-radius: 5px;">
							<small><strong>Hinweis:</strong> Leer lassen = "Nein, danke" - die Aktion verfällt für diesen Kunden unwiderruflich.</small>
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
						
						aktionsberechtigteKunden.forEach((kunde, index) => {
							let selectedItem = values[`aktion_artikel_${index}`];
							
							if (selectedItem && selectedItem.trim() !== "") {
								console.log(`${kunde.displayName} hat gewählt: ${selectedItem}`);
								
								let itemCode = getItemCodeFromName(selectedItem);
								
								if (itemCode) {
									let promise = addAktionsartikelToKunde(kunde, itemCode, selectedItem);
									verarbeitungsPromises.push(promise);
									aktionsartikelHinzugefuegt++;
								}
							} else {
								console.log(`${kunde.displayName} hat "Nein, danke" gewählt`);
							}
						});
						
						Promise.all(verarbeitungsPromises).then(() => {
							console.log(`${aktionsartikelHinzugefuegt} Aktionsartikel wurden hinzugefügt`);
							
							if (aktionsartikelHinzugefuegt > 0) {
								try {
									for (let i = 1; i <= 15; i++) {
										let fieldName = `produktauswahl_für_kunde_${i}`;
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
							}
							
							d.hide();
							callback();
						}).catch((error) => {
							console.error("Fehler beim Hinzufügen der Aktionsartikel:", error);
							console.log("Artikel wurden trotz Fehler hinzugefügt - fahre fort");
							d.hide();
							callback();
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
				let found = standardVariants.find(v => v.name === itemName) || premiumVariants.find(v => v.name === itemName);
				return found ? found.code : null;
			}
			
			function addAktionsartikelToKunde(kunde, itemCode, itemName) {
				console.log(`Füge ${itemCode} zu ${kunde.displayName} hinzu`);
				
				return new Promise((resolve, reject) => {
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
								
								let neuer_eintrag = frm.add_child(kunde.produktfeld);
								
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
								frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'delivery_date', frappe.datetime.add_days(frappe.datetime.get_today(), 7));
								
								frappe.call({
									method: "enjo_party.enjo_party.doctype.sammelbestellung.sammelbestellung.get_default_warehouse",
									async: false,
									callback: function(r) {
										let warehouse = r.message || "Lagerräume - BM";
										frappe.model.set_value(neuer_eintrag.doctype, neuer_eintrag.name, 'warehouse', warehouse);
									}
								});
								
								frm.refresh_field(kunde.produktfeld);
								
								console.log(`Aktionsartikel ${itemName} zu ${kunde.displayName} hinzugefügt`);
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

// Hilfsfunktion zum Erstellen der Aufträge
function erstelleAuftraege(frm) {
	console.log("erstelleAuftraege aufgerufen");
	
	enableRequiredFields(frm);
	
	frappe.freeze_screen = true;
	
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
	
	console.log("Aktualisiere alle Produkttabellen vor dem Speichern...");
	
	try {
		for (let i = 1; i <= 15; i++) {
			let fieldName = `produktauswahl_für_kunde_${i}`;
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
	
	updateAllSummenAnzeigen(frm);
	
	console.log("Validiere Aktionsartikel...");
	validateAktionsartikel(frm);
	
	setTimeout(() => {
		console.log("Rufe create_invoices API direkt auf...");
		erstelleAuftraegeDirectly(frm);
	}, 500);
}

// Neue Funktion zur Validierung der Aktionsartikel
function validateAktionsartikel(frm) {
	console.log("Validiere Aktionsartikel...");
	
	frappe.call({
		method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
		async: false,
		callback: function(r) {
			if (!r.message) {
				console.log("Konnte Aktionseinstellungen nicht laden - verwende Fallback");
				return;
			}
			
			let settings = r.message;
			
			const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
			const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
			const aktionsCodes = [...standardVariants, ...premiumVariants].map(v => v.code).filter(Boolean);
			
			console.log("Dynamische Aktions-Codes:", aktionsCodes);
			
			let aktionsartikelGefunden = 0;
			
			for (let i = 1; i <= 15; i++) {
				let fieldName = `produktauswahl_für_kunde_${i}`;
				if (frm.doc[fieldName]) {
					frm.doc[fieldName].forEach(item => {
						if (aktionsCodes.includes(item.item_code)) {
							aktionsartikelGefunden++;
							if (!item.qty) item.qty = 1;
							if (!item.uom) item.uom = "Stk";
							if (!item.stock_uom) item.stock_uom = "Stk";
							if (!item.conversion_factor) item.conversion_factor = 1;
							if (!item.delivery_date) item.delivery_date = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
							if (!item.warehouse) {
								frappe.call({
									method: "enjo_party.enjo_party.doctype.sammelbestellung.sammelbestellung.get_default_warehouse",
									async: false,
									callback: function(r) {
										item.warehouse = r.message || "Lagerräume - BM";
									}
								});
							}
							console.log(`Aktionsartikel validiert: ${item.item_code} für Kunde ${i}`);
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
	
	frappe.freeze_screen = true;
	
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
	
	frm.doc.skip_total_calculation = 1;
	
	console.log("DEBUG: Vor dem Speichern - docstatus:", frm.doc.docstatus, "is_dirty:", frm.is_dirty());
	
	if (!frm.is_dirty()) {
		console.log("Dokument unverändert - springe direkt zur Aufträge-Erstellung");
		callCreateInvoicesAPI();
		return;
	}
	
	console.log("Speichere Änderungen vor Aufträge-Erstellung...");
	
	let saveTimeout = setTimeout(() => {
		console.error("TIMEOUT: Speichern dauert zu lange!");
		frappe.freeze_screen = false;
		frappe.msgprint({
			title: "Timeout",
			message: "Das Speichern dauert zu lange. Bitte versuche es erneut oder prüfe die Server-Logs.",
			indicator: "orange"
		});
		refreshButtons(frm);
	}, 10000);
	
	frm.save().then(() => {
		clearTimeout(saveTimeout);
		console.log("Speichern erfolgreich - starte Aufträge-Erstellung");
		callCreateInvoicesAPI();
	}).catch((error) => {
		clearTimeout(saveTimeout);
		console.error("Fehler beim Speichern:", error);
		
		frappe.freeze_screen = false;
		frm.doc.skip_total_calculation = 0;
		
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
		
		refreshButtons(frm);
	});
	
	function callCreateInvoicesAPI() {
		console.log("Rufe Aufträge-API auf...");
		
		frappe.call({
			method: "enjo_party.enjo_party.doctype.sammelbestellung.sammelbestellung.create_invoices",
			args: {
				sammelbestellung: frm.doc.name,
				from_button: true
			},
			freeze: true,
			freeze_message: __("Erstelle und reiche Aufträge ein..."),
			callback: function(r) {
				console.log("API-Antwort erhalten - verarbeite Ergebnis");
				frappe.freeze_screen = false;
				
				frm.doc.skip_total_calculation = 0;
				
				if (r.message && r.message.length > 0) {
					frappe.msgprint({
						title: __("Erfolgreich gebuchte Sammelbestellung"),
						message: __("{0} Aufträge wurden erfolgreich erstellt und eingereicht.<br><br>Das Fenster wird gleich automatisch neu geladen, um den aktuellen Status anzuzeigen.", [r.message.length]),
						indicator: "green"
					});
					setTimeout(function() {
						location.reload();
					}, 3500);
				} else {
					console.log("Keine Aufträge erstellt - refreshButtons wird aufgerufen");
					frappe.msgprint({
						title: __("Hinweis"),
						message: __("Es wurden keine Aufträge erstellt. Bitte überprüfe, ob Produkte ausgewählt wurden."),
						indicator: "orange"
					});
					console.log("Keine Aufträge erstellt - refreshButtons wird aufgerufen");
					refreshButtons(frm);
				}
			},
			error: function(r) {
				console.error("API-Fehler bei Aufträge-Erstellung:", r);
				frappe.freeze_screen = false;
				
				frm.doc.skip_total_calculation = 0;
				
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
				console.log("API-Fehler - refreshButtons wird aufgerufen");
				refreshButtons(frm);
			}
		});
	}
}

// Funktion zum Aktualisieren der benutzerdefinierten Überschriften
function updateCustomHeaders(frm) {
	if (!frm.doc.kunden) return;
	
	for (let i = 1; i <= frm.doc.kunden.length; i++) {
		if (i > 15) break;
		
		let kundeRow = frm.doc.kunden[i-1];
		if (!kundeRow || !kundeRow.kunde) continue;
		
		let sectionId = `produktauswahl_für_kunde_${i}_section`;
		let sectionHeader = document.querySelector(`[data-fieldname="${sectionId}"] .section-head`);
		
		if (sectionHeader) {
			frappe.db.get_doc('Customer', kundeRow.kunde).then(customer_doc => {
				let kundenName = customer_doc.customer_name || kundeRow.kunde;
				sectionHeader.style.fontWeight = "500";
				sectionHeader.style.fontSize = "1em";
				sectionHeader.style.color = "#6C7680";
				if (!sectionHeader.querySelector('.custom-header')) {
					sectionHeader.innerHTML = `Produktauswahl für <span class="custom-header" style="font-weight: 600; color: #1F272E;">${kundenName}</span>`;
				} else {
					sectionHeader.querySelector('.custom-header').textContent = kundenName;
				}
				frm.set_df_property(`versand_kunde_${i}`, 'label', `Versand für ${kundenName} an:`);
			});
		}
	}
}

// Funktion zum Aktualisieren der Kunden-Filter
function updateKundenFilter(frm) {
	if (!frm.fields_dict["kunden"]) return;
	
	frm.set_query("kunde", "kunden", function(doc, cdt, cdn) {
		let current_row = locals[cdt][cdn];
		
		let other_selected = [];
		if (frm.doc.kunden) {
			frm.doc.kunden.forEach(function(k, index) {
				if (k.kunde && k.name !== current_row.name) {
					other_selected.push(k.kunde);
				}
			});
		}
		
		let filters = [];
		if (other_selected.length > 0) {
			filters.push(["name", "not in", other_selected]);
		}
		return { filters: filters };
	});
}

// Neue Funktion zur sofortigen Validierung von Duplikaten
function validateKundenDuplicates(frm, current_row) {
	if (!current_row.kunde) return true;
	
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
			message: __("Dieser Kunde wurde bereits ausgewählt!"),
			indicator: "red"
		});
		setTimeout(() => {
			current_row.kunde = "";
			frm.refresh_field("kunden");
		}, 100);
		return false;
	}
	
	return true;
}

frappe.ui.form.on('Sammelbestellung', {
	refresh(frm) {
		disableRequiredFields(frm);

		// Zeige die Produktauswahl-Tabellen erst nach dem Speichern
		for (let i = 1; i <= 15; i++) {
			frm.toggle_display(
				`produktauswahl_für_kunde_${i}_section`, 
				!frm.is_new() && frm.doc.kunden && frm.doc.kunden.length >= i
			);
		}

		// Automatisch leere Zeilen zu sichtbaren, leeren Produkttabellen hinzufügen
		setTimeout(() => {
			for (let i = 1; i <= 15; i++) {
				if (!frm.is_new() && frm.doc.kunden && frm.doc.kunden.length >= i) {
					let field_name = `produktauswahl_für_kunde_${i}`;
					if (!frm.doc[field_name] || frm.doc[field_name].length === 0) {
						let row = frm.add_child(field_name);
						frm.refresh_field(field_name);
					}
				}
			}
		}, 100);

		// Kundennamen in Überschriften einfügen
		setTimeout(() => {
			updateCustomHeaders(frm);
			updateAllSummenAnzeigen(frm);
			addPermanentColumnHideCSS();
		}, 500);
		
		// Verstecke das Datum-Feld in allen Produktauswahl-Tabellen
		for (let i = 1; i <= 15; i++) {
			const fieldName = `produktauswahl_für_kunde_${i}`;
			if (frm.fields_dict[fieldName]) {
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'hidden', 1);
				frm.fields_dict[fieldName].grid.update_docfield_property('delivery_date', 'reqd', 0);
				frm.fields_dict[fieldName].grid.update_docfield_property('warehouse', 'hidden', 1);
				frm.fields_dict[fieldName].grid.update_docfield_property('warehouse', 'reqd', 0);
				frm.fields_dict[fieldName].grid.update_docfield_property('rate', 'read_only', 1);
				
				setTimeout(() => {
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-body .data-row .col[data-fieldname="delivery_date"]`).hide();
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-body .data-row .col[data-fieldname="warehouse"]`).hide();
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-heading-row .col[data-fieldname="delivery_date"]`).hide();
					$(frm.wrapper).find(`[data-fieldname="${fieldName}"] .grid-heading-row .col[data-fieldname="warehouse"]`).hide();
				}, 500);
				
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
		
		// Sammle alle Namen: Partnerin, Kunden
		let optionen = [];
		let promises = [];
		
		// Partnerin als Versandziel hinzufügen
		if (frm.doc.partnerin) {
			promises.push(
				frappe.db.get_doc('Sales Partner', frm.doc.partnerin).then(doc => {
					if (doc && doc.partner_name) {
						optionen.push({ value: frm.doc.partnerin, label: doc.partner_name });
					} else {
						optionen.push({ value: frm.doc.partnerin, label: frm.doc.partnerin });
					}
				}).catch(() => {
					optionen.push({ value: frm.doc.partnerin, label: frm.doc.partnerin });
				})
			);
		}
		if (frm.doc.kunden && frm.doc.kunden.length > 0) {
			frm.doc.kunden.forEach(function(kunde_row) {
				if (kunde_row.kunde) {
					promises.push(
						frappe.db.get_doc('Customer', kunde_row.kunde).then(doc => {
							if (doc && doc.customer_name) {
								optionen.push({ value: kunde_row.kunde, label: doc.customer_name });
							} else {
								optionen.push({ value: kunde_row.kunde, label: kunde_row.kunde });
							}
						}).catch(() => {
							optionen.push({ value: kunde_row.kunde, label: kunde_row.kunde });
						})
					);
				}
			});
		}
		Promise.all(promises).then(() => {
			const uniqueOptionen = optionen.filter((option, index, self) =>
				index === self.findIndex((o) => (
					o.value === option.value
				))
			);

			for (let i = 1; i <= 15; i++) {
				if (frm.fields_dict[`versand_kunde_${i}`]) {
					frm.set_df_property(`versand_kunde_${i}`, 'options', uniqueOptionen);
				}
			}
		});
		
		// Standard-Submit-Button ausblenden
		if (!frm.is_new() && frm.page && frm.page.btn_primary) {
			frm.page.btn_primary.hide();
		}
		
		setTimeout(() => {
			try {
				$(frm.wrapper).find('.actions-btn-group').hide();
				$(frm.wrapper).find('.dropdown-btn[data-label="Aktionen"]').hide();
			} catch (e) {
				console.error("Fehler beim Ausblenden der Aktionsbuttons:", e);
			}
		}, 300);
		
		setTimeout(() => {
			refreshButtons(frm);
		}, 200);
		
		setTimeout(() => {
			$(frm.wrapper).find('.form-message.blue').hide();
			$(frm.wrapper).find('.msgprint').hide();
			$(frm.wrapper).find('[data-fieldtype="HTML"][data-fieldname*="submit"]').hide();
		}, 200);
		
		frm.toggle_display('status', false);
		
		frm.set_df_property('sammelbestellung_name', 'label', 'Name der Sammelbestellung');
		
		function changeTitleToSammelbestellung() {
			if (document.title.includes('Sammelbestellung')) {
				// Bereits korrekt
			}
			
			$('.breadcrumb a:contains("Sammelbestellung")').text('Sammelbestellung');
			$('.breadcrumb-item:contains("Sammelbestellung")').each(function() {
				$(this).text($(this).text());
			});
			$('nav[aria-label="breadcrumb"] a:contains("Sammelbestellung")').text('Sammelbestellung');
			
			$('.page-title:contains("Sammelbestellung")').each(function() {
				$(this).text($(this).text());
			});
			$('h1:contains("Sammelbestellung")').each(function() {
				$(this).text($(this).text());
			});
			
			$('.navbar a:contains("Sammelbestellung")').text('Sammelbestellung');
		}
		
		function hideUnwantedElements() {
			$('h4:contains("Teilnehmer")').hide();
			$('.section-head:contains("Teilnehmer")').hide();
			$('[data-label="Teilnehmer"]').hide();
			
			$('[data-fieldname="sammelbestellung_name"]').hide();
			$('.form-control[data-fieldname="sammelbestellung_name"]').hide();
			
			$('.btn-default:contains("Drucken")').hide();
			$('.dropdown-item:contains("Drucken")').hide();
			$('[data-label="Drucken"]').hide();
			
			$(frm.wrapper).find('.layout-side-section').hide();
			$(frm.wrapper).find('.sidebar-area').hide();
			$(frm.wrapper).find('.form-sidebar').hide();
			$(frm.wrapper).find('.layout-main-section').css({
				'margin-right': '0',
				'width': '100%'
			});
			$(frm.wrapper).find('.form-layout').css({
				'margin-right': '0',
				'width': '100%'
			});
			
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
			
			if (!$('.custom-bottom-spacing').length) {
				$('.form-layout').append('<div class="custom-bottom-spacing" style="height: 50px; background: white;"></div>');
			}
			
			$('h4:contains("Kommentare")').parent().css('display', 'none');
			$('h4:contains("Aktivität")').parent().css('display', 'none');
			$('h4:contains("E-Mail")').parent().css('display', 'none');
		}
		
		setTimeout(changeTitleToSammelbestellung, 100);
		setTimeout(changeTitleToSammelbestellung, 500);
		setTimeout(changeTitleToSammelbestellung, 1000);
		
		setTimeout(hideUnwantedElements, 100);
		setTimeout(hideUnwantedElements, 500);
		setTimeout(hideUnwantedElements, 1000);
		
		if (frm.doc.docstatus === 1) {
			frm.disable_save();
		}
	},
	
	partnerin: function(frm) {
		updateKundenFilter(frm);
		
		// Wenn die Partnerin geändert wird, setze sie als Standard für den Versand
		if (frm.doc.partnerin) {
			for (let i = 1; i <= 15; i++) {
				frm.set_value(`versand_kunde_${i}`, frm.doc.partnerin);
			}
		}
		
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 100);
		
		// Aktualisiere die Optionen für die Versandfelder
		let optionen = [];
		let promises = [];
		
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
				frm.set_df_property(`versand_kunde_${i}`, 'options', optionen);
			}
		});
	},
	
	onload: function(frm) {
		// Automatisch Datum auf heute setzen
		if (frm.is_new() && !frm.doc.sammelbestellung_date) {
			frm.set_value('sammelbestellung_date', frappe.datetime.get_today());
		}
		
		// Automatisch Partnerin setzen, wenn der aktuelle Benutzer als Sales Partner existiert
		if (frm.is_new() && !frm.doc.partnerin) {
			let current_user = frappe.session.user_fullname || frappe.session.user;
			
			frappe.db.get_list('Sales Partner', {
				filters: {
					'partner_name': current_user
				},
				fields: ['name', 'partner_name'],
				limit: 1
			}).then(partners => {
				if (partners && partners.length > 0) {
					frm.set_value('partnerin', partners[0].name);
				}
			}).catch(error => {
				console.log("Konnte nicht nach Sales Partner suchen:", error);
			});
		}
		
		// Stelle sicher, dass mindestens 2 Zeilen in der Kunden-Tabelle sind
		if (frm.is_new() && (!frm.doc.kunden || frm.doc.kunden.length < 2)) {
			const benötigteZeilen = 2 - (frm.doc.kunden ? frm.doc.kunden.length : 0);
			
			for (let i = 0; i < benötigteZeilen; i++) {
				let row = frm.add_child('kunden');
			}
			
			frm.refresh_field('kunden');
		}
		
		updateKundenFilter(frm);
	},
	
	after_save(frm) {
		if (frm.doc.docstatus === 0 && !frm._skipPriceUpdates) {
			refresh_item_prices(frm);
			calculate_sammelbestellung_totals(frm);
		}
		setTimeout(() => {
			updateAllSummenAnzeigen(frm);
		}, 500);
	},
	
	kunden_add: function(frm) {
		updateKundenFilter(frm);
		
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 100);
	},
	kunden_remove: function(frm) {
		updateKundenFilter(frm);
		
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
		
		if (!validateKundenDuplicates(frm, row)) {
			return;
		}
		
		if (row.kunde) {
			frm.set_df_property(`versand_kunde_${idx}`, 'label', `Versand für ${row.kunde} an:`);
		}
		
		updateKundenFilter(frm);
		
		setTimeout(() => {
			updateCustomHeaders(frm);
		}, 100);
	},
	
	kunde_on_form_rendered: function(frm, cdt, cdn) {
		updateKundenFilter(frm);
	},
	
	before_kunden_remove: function(frm, cdt, cdn) {
		setTimeout(() => {
			updateKundenFilter(frm);
			updateCustomHeaders(frm);
		}, 50);
	}
});

// Event-Handler für Sales Order Item
frappe.ui.form.on('Sales Order Item', {
	item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_code && !row.qty) {
			frappe.model.set_value(cdt, cdn, 'qty', 1);
			
			frappe.db.get_doc("Item", row.item_code)
				.then(item_doc => {
					frappe.model.set_value(cdt, cdn, 'uom', item_doc.stock_uom);
					frappe.model.set_value(cdt, cdn, 'stock_uom', item_doc.stock_uom);
					frappe.model.set_value(cdt, cdn, 'conversion_factor', 1.0);
					frappe.model.set_value(cdt, cdn, 'uom_conversion_factor', 1.0);
					
					if (!row.item_name) {
						frappe.model.set_value(cdt, cdn, 'item_name', item_doc.item_name);
					}
					
					if (!row.stock_qty) {
						let stock_qty = parseFloat(row.qty || 0) * 1.0;
						frappe.model.set_value(cdt, cdn, 'stock_qty', stock_qty);
					}
				});
		}
		
		if (row.item_code) {
			get_item_price(frm, row);
		}
		
		setTimeout(() => {
			updateAllSummenAnzeigen(frm);
		}, 500);
	},
	qty: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.qty && row.rate) {
			row.amount = flt(row.qty) * flt(row.rate);
			row.base_amount = row.amount;
			frm.refresh_field(row.parentfield);
			calculate_sammelbestellung_totals(frm);
			updateAllSummenAnzeigen(frm);
		}
	},
	rate: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.qty && row.rate) {
			row.amount = flt(row.qty) * flt(row.rate);
			row.base_amount = row.amount;
			frm.refresh_field(row.parentfield);
			calculate_sammelbestellung_totals(frm);
			updateAllSummenAnzeigen(frm);
		}
	}
});

// Funktion, um alle Tabellen mit Preisen zu aktualisieren
function refresh_item_prices(frm) {
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
				customer: frm.doc.partnerin,
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
			
			for (let i = 1; i <= 15; i++) {
				const field_name = `produktauswahl_für_kunde_${i}`;
				if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
					frm.doc[field_name].forEach(function(item) {
						let istAktionsartikel = aktionsCodes.includes(item.item_code);
						if (item.item_code && (!item.rate || item.rate == 0) && !istAktionsartikel) {
							get_item_price(frm, item);
						}
					});
				}
			}
		}
	});
}

// Funktion zur Berechnung der Sammelbestellung-Gesamtsummen
function calculate_sammelbestellung_totals(frm) {
	let total_amount = 0.0;
	
	for (let i = 1; i <= 15; i++) {
		const field_name = `produktauswahl_für_kunde_${i}`;
		if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
			frm.doc[field_name].forEach(function(item) {
				if (item.qty && item.rate) {
					total_amount += flt(item.qty) * flt(item.rate);
				}
			});
		}
	}
	
	if (!frm._skipTotalCalculation) {
		frm.set_value('gesamtumsatz', total_amount);
	}
}

// Hilfsfunktionen zum Aktivieren/Deaktivieren der Pflichtfelder
function disableRequiredFields(frm) {
	for (let i = 1; i <= 15; i++) {
		let fieldName = `produktauswahl_für_kunde_${i}`;
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
	for (let i = 1; i <= 15; i++) {
		let fieldName = `produktauswahl_für_kunde_${i}`;
		if (frm.fields_dict[fieldName]) {
			frm.fields_dict[fieldName].grid.update_docfield_property('item_code', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('item_name', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('qty', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('uom', 'reqd', 1);
			frm.fields_dict[fieldName].grid.update_docfield_property('conversion_factor', 'reqd', 1);
		}
	}
}

// CSS-REGELN FÜR SPALTEN-VERSTECKEN
function addPermanentColumnHideCSS() {
	if (document.getElementById('sammelbestellung-column-hide-css')) {
		return;
	}
	
	let css = `
		[data-fieldname*="produktauswahl_für_kunde"] .grid-heading-row .col[data-fieldname="delivery_date"],
		[data-fieldname*="produktauswahl_für_kunde"] .grid-body .data-row .col[data-fieldname="delivery_date"],
		[data-fieldname*="produktauswahl_für_kunde"] .grid-heading-row .col[data-fieldname="warehouse"],
		[data-fieldname*="produktauswahl_für_kunde"] .grid-body .data-row .col[data-fieldname="warehouse"] {
			display: none !important;
		}
	`;
	
	let style = document.createElement('style');
	style.id = 'sammelbestellung-column-hide-css';
	style.type = 'text/css';
	style.innerHTML = css;
	document.head.appendChild(style);
	
	console.log("Permanente CSS-Regeln zum Verstecken der Spalten hinzugefügt");
}

// SUMMEN-ANZEIGE FUNKTIONEN
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

function updateAllSummenAnzeigen(frm) {
	for (let i = 1; i <= 15; i++) {
		let tableName = `produktauswahl_für_kunde_${i}`;
		let sumFieldName = `summe_kunde_${i}`;
		updateSummeForTable(frm, tableName, sumFieldName);
	}
}

