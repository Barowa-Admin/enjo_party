// Client Script für Aktions-System in Party App
// Dieses Script als separates Client Script in der Frappe UI einfügen

function discount_window_party(frm, callback) {
    console.log("discount_window_party gestartet");
    
    // Schwellwerte für die Aktion als Variablen
    const STAGE_1_MIN = 99;   // Mindestbetrag für Stage 1
    const STAGE_1_MAX = 199;  // Maximalbetrag für Stage 1 / Minimalbetrag für Stage 2
    
    // Artikelvariablen für Frühlingsaktion 2025
    // Diese Codes können bei Bedarf einfach angepasst werden
    const v1_code = "50238-Aktion";           // V1: Artikel-Code
    const v2_code = "52004-Aktion";    // V2: Artikel-Code
    const v3_code = "50320-Aktion";    // V3: Artikel-Code
    const v4_code = "15312a-Aktion";    // V4: Artikel-Code
    const v5_code = "15313-Aktion";    // V5: Artikel-Code
    const v6_code = "15308-Aktion";    // V6: Artikel-Code
    const v7_code = "15312b-Aktion";    // V7: Artikel-Code
    
    // Artikelnamen für die Auswahl
    const v1_name = "V1: Duo-Ministar";
    const v2_name = "V2: Lavendelbl. Waschmittel";
    const v3_name = "V3: ENJOfil Wohnen";
    const v4_name = "V4: Multi-Tool Platte & Faser Stark";
    const v5_name = "V5: Duo-Ministar & Lavendelbl.";
    const v6_name = "V6: Duo-Ministar & ENJOfil";
    const v7_name = "V7: Multi-Tool Platte & Faser Stark";
    
    // Array mit allen Aktionsartikeln
    const allAktionsCodes = [v1_code, v2_code, v3_code, v4_code, v5_code, v6_code, v7_code];
    
    // Sammle alle Teilnehmer und ihre Produkttabellen
    let teilnehmerMitProdukten = [];
    
    // Gastgeberin hinzufügen
    if (frm.doc.gastgeberin && frm.doc.produktauswahl_für_gastgeberin && frm.doc.produktauswahl_für_gastgeberin.length > 0) {
        teilnehmerMitProdukten.push({
            name: frm.doc.gastgeberin,
            typ: "Gastgeberin",
            produktfeld: "produktauswahl_für_gastgeberin",
            produkte: frm.doc.produktauswahl_für_gastgeberin
        });
    }
    
    // Alle Gäste hinzufügen
    for (let i = 0; i < frm.doc.kunden.length; i++) {
        let kunde = frm.doc.kunden[i];
        if (!kunde.kunde) continue;
        
        let field_name = `produktauswahl_für_gast_${i+1}`;
        if (frm.doc[field_name] && frm.doc[field_name].length > 0) {
            // Prüfe ob der Gast tatsächlich Produkte hat
            let hatProdukte = frm.doc[field_name].some(item => item.item_code && item.qty && item.qty > 0);
            if (hatProdukte) {
                teilnehmerMitProdukten.push({
                    name: kunde.kunde,
                    typ: "Gast",
                    gastNummer: i + 1,
                    produktfeld: field_name,
                    produkte: frm.doc[field_name]
                });
            }
        }
    }
    
    console.log("Gefundene Teilnehmer mit Produkten:", teilnehmerMitProdukten.length);
    
    if (teilnehmerMitProdukten.length === 0) {
        console.log("Keine Teilnehmer mit Produkten gefunden - überspringe Aktions-System");
        callback();
        return;
    }
    
    // Prüfe jeden Teilnehmer auf Aktionsberechtigung
    checkTeilnehmerForAction(teilnehmerMitProdukten, 0, []);
    
    function checkTeilnehmerForAction(teilnehmer, index, aktionsberechtigteTeilnehmer) {
        if (index >= teilnehmer.length) {
            // Alle Teilnehmer wurden geprüft
            console.log("Aktionsberechtigte Teilnehmer:", aktionsberechtigteTeilnehmer.length);
            
            if (aktionsberechtigteTeilnehmer.length > 0) {
                // Zeige Dialog für alle berechtigten Teilnehmer
                showAktionsDialog(aktionsberechtigteTeilnehmer);
            } else {
                // Keine aktionsberechtigten Teilnehmer
                console.log("Keine aktionsberechtigten Teilnehmer gefunden");
                callback();
            }
            return;
        }
        
        let teilnehmer_obj = teilnehmer[index];
        console.log(`Prüfe Teilnehmer: ${teilnehmer_obj.name} (${teilnehmer_obj.typ})`);
        
        // Prüfe alle Produkte dieses Teilnehmers auf Aktionsberechtigung
        checkItemsForAction(teilnehmer_obj.produkte, 0, [], 0, teilnehmer_obj);
        
        function checkItemsForAction(items, itemIndex, actionItems, total, teilnehmer_obj) {
            if (itemIndex >= items.length) {
                // Alle Items dieses Teilnehmers wurden geprüft
                console.log(`${teilnehmer_obj.name}: ${actionItems.length} aktionsfähige Items, Summe: ${total}`);
                
                // Prüfe ob bereits ein Aktionsartikel vorhanden ist
                let hasAktionsartikel = items.some(item => allAktionsCodes.includes(item.item_code));
                
                if (actionItems.length > 0 && !hasAktionsartikel) {
                    // Bestimme Stage basierend auf Summe
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
                
                // Nächsten Teilnehmer prüfen
                checkTeilnehmerForAction(teilnehmer, index + 1, aktionsberechtigteTeilnehmer);
                return;
            }
            
            // Aktuelles Item prüfen
            let item = items[itemIndex];
            
            if (!item.item_code || !item.qty || item.qty <= 0) {
                // Item überspringen
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
                        // Dieses Item wird für Aktionen berücksichtigt
                        actionItems.push(item);
                        total += item.amount || 0;
                        console.log(`${teilnehmer_obj.name}: Item ${item.item_code} aktionsfähig (${item.amount || 0} EUR)`);
                    }
                    
                    // Nächstes Item prüfen
                    checkItemsForAction(items, itemIndex + 1, actionItems, total, teilnehmer_obj);
                }
            });
        }
    }
    
    // Dialog für alle aktionsberechtigten Teilnehmer anzeigen
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
        
        // Für jeden berechtigten Teilnehmer ein Dropdown hinzufügen
        aktionsberechtigteTeilnehmer.forEach((teilnehmer, index) => {
            let optionen = [];
            let stageText = "";
            
            if (teilnehmer.stage === 1) {
                // Stage 1 (Standard)
                optionen = [
                    "",  // Leere Option für "Nein, danke"
                    v1_name,
                    v2_name,
                    v3_name,
                    v4_name
                ];
                stageText = "Standard";
            } else if (teilnehmer.stage === 2) {
                // Stage 2 (Premium)
                optionen = [
                    "",  // Leere Option für "Nein, danke"
                    v5_name,
                    v6_name,
                    v7_name
                ];
                stageText = "Premium";
            }
            
            dialogFields.push({
                fieldtype: 'HTML',
                fieldname: `teilnehmer_info_${index}`,
                options: `
                    <div style="margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
                        <strong>${teilnehmer.name}</strong> (${teilnehmer.typ})<br>
                        <small>Aktionssumme: ${teilnehmer.aktionssumme.toFixed(2)} EUR - ${stageText} Aktion</small>
                    </div>
                `
            });
            
            dialogFields.push({
                fieldtype: 'Select',
                fieldname: `aktion_artikel_${index}`,
                label: `Aktionsartikel für ${teilnehmer.name}`,
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
                
                // Verarbeite die Auswahl für jeden Teilnehmer
                let aktionsartikelHinzugefuegt = 0;
                let verarbeitungsPromises = [];
                
                aktionsberechtigteTeilnehmer.forEach((teilnehmer, index) => {
                    let selectedItem = values[`aktion_artikel_${index}`];
                    
                    if (selectedItem && selectedItem.trim() !== "") {
                        console.log(`${teilnehmer.name} hat gewählt: ${selectedItem}`);
                        
                        // Bestimme den richtigen Artikelcode
                        let itemCode = getItemCodeFromName(selectedItem);
                        
                        if (itemCode) {
                            let promise = addAktionsartikelToTeilnehmer(teilnehmer, itemCode, selectedItem);
                            verarbeitungsPromises.push(promise);
                            aktionsartikelHinzugefuegt++;
                        }
                    } else {
                        console.log(`${teilnehmer.name} hat "Nein, danke" gewählt`);
                    }
                });
                
                // Warte auf alle Verarbeitungen
                Promise.all(verarbeitungsPromises).then(() => {
                    console.log(`${aktionsartikelHinzugefuegt} Aktionsartikel wurden hinzugefügt`);
                    
                    if (aktionsartikelHinzugefuegt > 0) {
                        frm.refresh();
                        frappe.show_alert(`${aktionsartikelHinzugefuegt} Aktionsartikel wurden hinzugefügt!`, 5);
                    }
                    
                    d.hide();
                    
                    // Callback aufrufen um mit Phase 3 fortzufahren
                    callback();
                }).catch((error) => {
                    console.error("Fehler beim Hinzufügen der Aktionsartikel:", error);
                    frappe.msgprint("Fehler beim Hinzufügen der Aktionsartikel. Bitte versuchen Sie es erneut.");
                });
            },
            secondary_action_label: 'Alle ablehnen',
            secondary_action: function() {
                console.log("Alle Aktionen abgelehnt");
                d.hide();
                
                // Callback aufrufen um mit Phase 3 fortzufahren
                callback();
            }
        });
        
        d.show();
    }
    
    // Hilfsfunktion: Artikelcode basierend auf Namen ermitteln
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
    
    // Hilfsfunktion: Aktionsartikel zu einem Teilnehmer hinzufügen
    function addAktionsartikelToTeilnehmer(teilnehmer, itemCode, itemName) {
        return new Promise((resolve, reject) => {
            console.log(`Füge ${itemCode} zu ${teilnehmer.name} hinzu`);
            
            // Hole Item-Informationen
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Item",
                    filters: {
                        name: itemCode
                    },
                    fieldname: ["item_name", "description", "stock_uom"]
                },
                callback: function(r) {
                    if (r.message) {
                        let item = r.message;
                        
                        // Bestimme Warehouse (vom ersten Produkt des Teilnehmers)
                        let warehouse = "Lagerräume - BM"; // Default
                        if (teilnehmer.produkte && teilnehmer.produkte.length > 0) {
                            warehouse = teilnehmer.produkte[0].warehouse || warehouse;
                        }
                        
                        // Berechne Liefertermin (7 Tage ab heute)
                        let deliveryDate = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
                        
                        // Hole den Preis aus der Preisliste
                        frappe.call({
                            method: "frappe.client.get_value",
                            args: {
                                doctype: "Item Price",
                                filters: {
                                    item_code: itemCode,
                                    price_list: "Standard Selling" // Oder die entsprechende Preisliste
                                },
                                fieldname: "price_list_rate"
                            },
                            callback: function(price_r) {
                                // Preis (0 wenn nicht gefunden)
                                let price = price_r.message ? price_r.message.price_list_rate : 0;
                                
                                console.log(`Preis für ${itemCode}: ${price}`);
                                
                                // Füge das Item zur entsprechenden Produkttabelle hinzu
                                let produkttabelle = frm.doc[teilnehmer.produktfeld];
                                if (!produkttabelle) {
                                    produkttabelle = [];
                                    frm.doc[teilnehmer.produktfeld] = produkttabelle;
                                }
                                
                                // Neues Item hinzufügen
                                let newItem = {
                                    item_code: itemCode,
                                    item_name: item.item_name || itemName,
                                    description: item.description || itemName,
                                    qty: 1,
                                    rate: price,
                                    amount: price,
                                    uom: item.stock_uom || "Stk",
                                    stock_uom: item.stock_uom || "Stk",
                                    conversion_factor: 1,
                                    warehouse: warehouse,
                                    delivery_date: deliveryDate
                                };
                                
                                produkttabelle.push(newItem);
                                
                                // Refresh das entsprechende Feld
                                frm.refresh_field(teilnehmer.produktfeld);
                                
                                console.log(`Aktionsartikel ${itemName} zu ${teilnehmer.name} hinzugefügt`);
                                resolve();
                            }
                        });
                    } else {
                        console.error(`Aktionsartikel ${itemCode} konnte nicht gefunden werden`);
                        reject(new Error(`Item ${itemCode} nicht gefunden`));
                    }
                }
            });
        });
    }
} 