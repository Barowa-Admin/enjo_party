frappe.ui.form.on('Sales Order', {
    before_save: function(frm) {
        console.log("Before Save wird ausgeführt");
        console.log("Dokument Status:", frm.doc.docstatus);
        
        // Wenn wir gerade aus dem Dialog speichern, speichere sofort
        if (frm.doc.__from_dialog) {
            frappe.validated = true;
            return;
        }
        
        if (frm.doc.docstatus === 0) {
            // Party-Referenz prüfen: falls aufgehoben (docstatus=2), Referenz entfernen
            if (frm.doc.custom_party_reference) {
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "Party",
                        filters: { name: frm.doc.custom_party_reference },
                        fieldname: "docstatus"
                    },
                    async: false,
                    callback: function(r) {
                        if (r.message && r.message.docstatus === 2) {
                            console.log("Entferne ungültige Party-Referenz (aufgehoben)");
                            frm.set_value("custom_party_reference", null);
                        }
                    }
                });
            }

            // Lade Aktionseinstellungen dynamisch
            frappe.call({
                method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
                async: false,
                callback: function(r) {
                    if (!r.message) {
                        console.log("Konnte Aktionseinstellungen nicht laden - überspringe Aktions-System");
                        frappe.validated = true;
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
                    
                    // Prüfe, ob bereits ein Aktionsartikel vorhanden ist und welcher Typ
                    let currentAktionsartikel = null;
                    let currentStage = 0;
                    
                    frm.doc.items.forEach(item => {
                        if (item._aktionsartikel === true || allAktionsCodes.includes(item.item_code)) {
                            currentAktionsartikel = item;
                            if (allStandardCodes.includes(item.item_code)) {
                                currentStage = 1;
                            } else if (allPremiumCodes.includes(item.item_code)) {
                                currentStage = 2;
                            }
                        }
                    });
                    
                    // Prüfe alle Items auf ihre Berücksichtigung für Aktionen
                    checkItemsForAction(frm.doc.items, 0, [], 0, currentAktionsartikel, currentStage);
                    
                    function checkItemsForAction(items, index, actionItems, total, currentAktionsartikel, currentStage) {
                        if (index >= items.length) {
                            console.log("Alle Items wurden geprüft. Aktionsberechtigte Items:", actionItems.length);
                            console.log("Berechnete Aktionssumme:", total);
                            console.log("Aktueller Aktionsartikel:", currentAktionsartikel ? currentAktionsartikel.item_code : "keiner");
                            console.log("Aktuelle Stage:", currentStage);
                            
                            if (actionItems.length > 0) {

                                if (total >= STAGE_1_MAX) {
                                    // Stage 2 berechtigt
                                    if (currentStage === 1) {
                                        // Upgrade von Stage 1 zu Stage 2 - entferne aktuellen Aktionsartikel
                                        showStage2UpgradeDialog(total, currentAktionsartikel);
                                    } else if (currentStage === 0) {
                                        // Kein Aktionsartikel vorhanden - zeige Stage 2
                                        showStage2Dialog(total);
                                    } else {
                                        // Bereits Stage 2 (und aktueller Aktionsartikel vorhanden): keine Abfrage
                                        frappe.validated = true;
                                    }
                                } else if (total >= STAGE_1_MIN) {
                                    // Stage 1 berechtigt
                                    if (currentStage === 0) {
                                        // Kein Aktionsartikel vorhanden - zeige Stage 1
                                        showStage1Dialog(total);
                                    } else if (currentStage === 2) {
                                        // Downgrade von Stage 2 zu Stage 1
                                        showStage1DowngradeDialog(total, currentAktionsartikel);
                                    } else {
                                        // Bereits Stage 1 Aktionsartikel vorhanden: keine Abfrage
                                        frappe.validated = true;
                                    }
                                } else {
                                    frappe.validated = true;
                                }
                            } else {
                                frappe.validated = true;
                            }
                            return;
                        }
                        
                        let item = items[index];
                        
                        frappe.call({
                            method: "frappe.client.get_value",
                            args: {
                                doctype: "Item",
                                filters: { item_code: item.item_code },
                                fieldname: "custom_considered_for_action"
                            },
                            async: false,
                            callback: function(r) {
                                if (r.message && r.message.custom_considered_for_action) {
                                    // Prüfe ob es ein Aktionsartikel ist (Flag ODER in der Aktionsartikel-Liste)
                                    const isAktionsartikel = item._aktionsartikel === true || 
                                                           allStandardCodes.includes(item.item_code) || 
                                                           allPremiumCodes.includes(item.item_code);
                                    
                                    if (!isAktionsartikel) {
                                        actionItems.push(item);
                                        total += item.amount;
                                        console.log(`Item ${item.item_code} wird für Aktion berücksichtigt (${item.amount} EUR)`);
                                    } else {
                                        console.log(`Item ${item.item_code} ist ein Aktionsartikel und wird NICHT zur Summe hinzugefügt`);
                                    }
                                }
                                checkItemsForAction(items, index + 1, actionItems, total, currentAktionsartikel, currentStage);
                            }
                        });
                    }
                    
                    function showStage1Dialog(total) {
                        frappe.validated = false;
                        
                        const options = standardVariants.map(v => v.name || v.code).filter(Boolean).join('\n');
                        
                        let d = new frappe.ui.Dialog({
                            title: 'Herzlichen Glückwunsch!',
                            fields: [
                                {
                                    fieldtype: 'Select',
                                    fieldname: 'aktion_artikel',
                                    label: 'Wähle deinen Aktionsartikel',
                                    options: options,
                                    reqd: 1
                                },
                                {
                                    fieldtype: 'HTML',
                                    fieldname: 'description',
                                    options: `
                                        <div style="margin-top: 10px; margin-bottom: 10px;">
                                            <p>Dein Einkauf berechtigt dich zur Teilnahme an unserer aktuellen Aktion.</p>
                                            <p>Bitte wähle einen der verfügbaren Aktionsartikel aus.</p>
                                            <br>
                                            <p>Mit der Auswahl "Nein, danke" verfällt die Aktion für diese Bestellung unwiderruflich.</p>
                                        </div>
                                    `
                                }
                            ],
                            primary_action_label: 'Auswählen',
                            primary_action: function() {
                                let values = d.get_values();
                                let selectedItem = values.aktion_artikel;
                                let itemCode = getItemCodeFromName(selectedItem);
                                
                                addAktionsartikelToInvoice(itemCode, selectedItem, d);
                            },
                            secondary_action_label: 'Nein, danke',
                            secondary_action: function() {
                                console.log("Keine Aktion gewünscht");
                                saveFromDialog(d);
                            },
                            onhide: function() {
                                if (!frm.doc.__from_dialog) {
                                    frappe.validated = false;
                                }
                            }
                        });
                        
                        d.show();
                    }
                    
                    function showStage2Dialog(total) {
                        frappe.validated = false;
                        
                        let d = new frappe.ui.Dialog({
                            title: 'Herzlichen Glückwunsch!',
                            fields: [
                                {
                                    fieldtype: 'Select',
                                    fieldname: 'aktion_artikel',
                                    label: 'Wähle deinen Aktionsartikel',
                                    options: premiumVariants.map(v => v.name || v.code).filter(Boolean).join('\n'),
                                    reqd: 1
                                },
                                {
                                    fieldtype: 'HTML',
                                    fieldname: 'description',
                                    options: `
                                        <div style="margin-top: 10px; margin-bottom: 10px;">
                                            <p>Dein Einkauf berechtigt dich zur Teilnahme an unserer Aktion.</p>
                                            <p>Bitte wähle einen der verfügbaren Aktionsartikel aus.</p>
                                            <br>
                                            <p>Mit der Auswahl "Nein, danke" verfällt die Aktion für diese Bestellung unwiderruflich.</p>
                                        </div>
                                    `
                                }
                            ],
                            primary_action_label: 'Auswählen',
                            primary_action: function() {
                                let values = d.get_values();
                                let selectedItem = values.aktion_artikel;
                                let itemCode = getItemCodeFromName(selectedItem);
                                
                                addAktionsartikelToInvoice(itemCode, selectedItem, d);
                            },
                            secondary_action_label: 'Nein, danke',
                            secondary_action: function() {
                                console.log("Keine Premium-Aktion gewünscht");
                                saveFromDialog(d);
                            },
                            onhide: function() {
                                if (!frm.doc.__from_dialog) {
                                    frappe.validated = false;
                                }
                            }
                        });
                        
                        d.show();
                    }
                    
                    function showStage1DowngradeDialog(total, currentAktionsartikel) {
                        frappe.validated = false;
                        
                        let d = new frappe.ui.Dialog({
                            title: 'Wechsel zu Standard-Aktion',
                            fields: [
                                {
                                    fieldtype: 'Select',
                                    fieldname: 'aktion_artikel',
                                    label: 'Wähle deinen Standard-Aktionsartikel',
                                    options: standardVariants.map(v => v.name).filter(Boolean),
                                    reqd: 1
                                },
                                {
                                    fieldtype: 'HTML',
                                    fieldname: 'description',
                                    options: `
                                        <div style="margin-top: 10px; margin-bottom: 10px;">
                                            <p>Dein Einkauf berechtigt dich zur Standard-Aktion.</p>
                                            <p>Dein aktueller Premium-Aktionsartikel "${currentAktionsartikel.item_name}" kann nicht behalten werden.</p>
                                            <p>Wähle einen Standard-Artikel oder klicke auf "Nein, danke".</p>
                                        </div>
                                    `
                                }
                            ],
                            primary_action_label: 'Wechseln',
                            primary_action: function() {
                                let values = d.get_values();
                                let selectedItem = values.aktion_artikel;
                                let itemCode = getItemCodeFromName(selectedItem);
                                
                                // Vor dem Hinzufügen: alle vorhandenen Aktionsartikel entfernen
                                removeExistingActionItems();
                                
                                addAktionsartikelToInvoice(itemCode, selectedItem, d);
                            },
                            secondary_action_label: 'Nein, danke',
                            secondary_action: function() {
                                console.log("Downgrade: Aktion abgelehnt – entferne Premium-Artikel");
                                removeExistingActionItems();
                                saveFromDialog(d);
                            },
                            onhide: function() {
                                if (!frm.doc.__from_dialog) {
                                    frappe.validated = false;
                                }
                            }
                        });
                        
                        d.show();
                    }
                    
                    function showStage2UpgradeDialog(total, currentAktionsartikel) {
                        frappe.validated = false;
                        
                        let d = new frappe.ui.Dialog({
                            title: 'Upgrade zu Premium-Aktion!',
                            fields: [
                                {
                                    fieldtype: 'Select',
                                    fieldname: 'aktion_artikel',
                                    label: 'Wähle deinen Premium-Aktionsartikel',
                                    options: premiumVariants.map(v => v.name || v.code).filter(Boolean).join('\n'),
                                    reqd: 1
                                },
                                {
                                    fieldtype: 'HTML',
                                    fieldname: 'description',
                                    options: `
                                        <div style="margin-top: 10px; margin-bottom: 10px;">
                                            <p><strong>Herzlichen Glückwunsch!</strong></p>
                                            <p>Dein Einkauf berechtigt dich jetzt zur Premium-Aktion!</p>
                                            <p>Dein aktueller Aktionsartikel "${currentAktionsartikel.item_name}" wird durch einen Premium-Artikel ersetzt.</p>
                                            <br>
                                            <p>Mit der Auswahl "Nein, danke" behältst du deinen aktuellen Aktionsartikel.</p>
                                        </div>
                                    `
                                }
                            ],
                            primary_action_label: 'Upgrade wählen',
                            primary_action: function() {
                                let values = d.get_values();
                                let selectedItem = values.aktion_artikel;
                                let itemCode = getItemCodeFromName(selectedItem);
                                
                                // Vor dem Hinzufügen: alle vorhandenen Aktionsartikel entfernen
                                removeExistingActionItems();
                                
                                addAktionsartikelToInvoice(itemCode, selectedItem, d);
                            },
                            secondary_action_label: 'Nein, danke',
                            secondary_action: function() {
                                console.log("Upgrade abgelehnt - behalte aktuellen Aktionsartikel");
                                saveFromDialog(d);
                            },
                            onhide: function() {
                                if (!frm.doc.__from_dialog) {
                                    frappe.validated = false;
                                }
                            }
                        });
                        
                        d.show();
                    }
                    
                    function getItemCodeFromName(itemName) {
                        let found = standardVariants.find(v => v.name === itemName) || premiumVariants.find(v => v.name === itemName);
                        return found ? found.code : null;
                    }
                    
                    function removeExistingActionItems() {
                        if (!frm.doc.items || !frm.doc.items.length) return;
                        for (let i = frm.doc.items.length - 1; i >= 0; i--) {
                            const it = frm.doc.items[i];
                            if (it._aktionsartikel === true || allAktionsCodes.includes(it.item_code)) {
                                frm.get_field("items").grid.grid_rows[i].remove();
                            }
                        }
                        frm.refresh_field("items");
                    }
                    
                    function addAktionsartikelToInvoice(itemCode, selectedItem, dialog) {
                        if (!itemCode) {
                            frappe.msgprint(`Aktionsartikel ${selectedItem} konnte nicht gefunden werden.`);
                            saveFromDialog(dialog);
                            return;
                        }
                        
                        // Vor dem Hinzufügen: alle vorhandenen Aktionsartikel entfernen
                        removeExistingActionItems();
                        
                        frappe.call({
                            method: "frappe.client.get_value",
                            args: {
                                doctype: "Item",
                                filters: { name: itemCode },
                                fieldname: ["item_name", "description", "stock_uom"]
                            },
                            callback: function(r) {
                                if (r.message) {
                                    let item = r.message;
                                    let warehouse = "Lagerräume - BM";
                                    let cost_center = "Haupt - BM";
                                    let income_account = "8200 - Erlöse - BM";
                                    
                                    // Werte vom ersten Item übernehmen
                                    if (frm.doc.items && frm.doc.items.length > 0) {
                                        warehouse = frm.doc.items[0].warehouse || warehouse;
                                        cost_center = frm.doc.items[0].cost_center || cost_center;
                                        income_account = frm.doc.items[0].income_account || income_account;
                                    }
                                    
                                    // Berechne Liefertermin (7 Tage ab heute)
                                    let deliveryDate = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
                                    
                                    // Preis laden
                                    frappe.call({
                                        method: "frappe.client.get_value",
                                        args: {
                                            doctype: "Item Price",
                                            filters: {
                                                item_code: itemCode,
                                                price_list: frm.doc.selling_price_list
                                            },
                                            fieldname: "price_list_rate"
                                        },
                                        callback: function(price_r) {
                                            let price = price_r.message ? price_r.message.price_list_rate : 0;
                                            
                                            // Item hinzufügen
                                            let child = frm.add_child("items", {
                                                item_code: itemCode,
                                                item_name: item.item_name,
                                                description: item.description,
                                                qty: 1,
                                                rate: price,
                                                amount: price,
                                                base_rate: price,
                                                base_amount: price,
                                                uom: item.stock_uom,
                                                conversion_factor: 1,
                                                warehouse: warehouse,
                                                cost_center: cost_center,
                                                income_account: income_account,
                                                delivery_date: deliveryDate
                                            });
                                            child._aktionsartikel = true;
                                            
                                            frm.refresh_field("items");
                                            frappe.show_alert(`Aktionsartikel "${selectedItem}" wurde hinzugefügt!`, 5);
                                            
                                            saveFromDialog(dialog);
                                        }
                                    });
                                } else {
                                    frappe.msgprint(`Aktionsartikel ${itemCode} konnte nicht gefunden werden.`);
                                    saveFromDialog(dialog);
                                }
                            }
                        });
                    }
                    
                    function saveFromDialog(dialog) {
                        dialog.hide();
                        frm.doc.__from_dialog = true;
                        
                        setTimeout(function() {
                            console.log("Speichere Dokument...");
                            frappe.validated = true;
                            frm.save();
                            
                            setTimeout(function() {
                                delete frm.doc.__from_dialog;
                            }, 1000);
                        }, 500);
                    }
                }
            });
        } else {
            frappe.validated = true;
        }
    },
    
    items_remove: function(frm, cdt, cdn) {
        // Neuberechnung bei Artikel-Entfernung
        setTimeout(function() {
            recalculateActionItemsOrder(frm);
        }, 100);
    }
});

// Event Handler für Items Tabelle
frappe.ui.form.on('Sales Order Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row || !row.item_code) return;

        frappe.call({
            method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
            async: false,
            callback: function(r) {
                if (!r.message) return;
                const standardVariants = (r.message.variants && r.message.variants.standard) ? r.message.variants.standard : [];
                const premiumVariants = (r.message.variants && r.message.variants.premium) ? r.message.variants.premium : [];
                const allAktionsCodes = [...standardVariants, ...premiumVariants].map(v => v.code).filter(Boolean);

                // Manuelles Hinzufügen von Aktionsartikeln unterbinden
                if (allAktionsCodes.includes(row.item_code) && row._aktionsartikel !== true) {
                    frappe.show_alert('Aktionsartikel dürfen nur über das Auswahlfenster hinzugefügt werden.', 5);
                    try {
                        const grid = frm.get_field("items").grid;
                        const gr = grid.grid_rows_by_docname[cdn];
                        if (gr) {
                            gr.remove();
                            frm.refresh_field("items");
                            return;
                        }
                    } catch (e) { /* fallback unten */ }
                    frappe.model.set_value(cdt, cdn, 'item_code', '');
                    frappe.model.set_value(cdt, cdn, 'qty', 0);
                }
            }
        });
    },
    qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // Lade Aktionseinstellungen um zu prüfen ob es ein Aktionsartikel ist
        frappe.call({
            method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
            async: false,
            callback: function(r) {
                if (r.message) {
                    let settings = r.message;
                    const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
                    const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
                    const allAktionsCodes = [...standardVariants, ...premiumVariants].map(v => v.code).filter(Boolean);
                    
                    // Lock für Aktionsartikel: Flag ODER Code
                    if (row._aktionsartikel === true || allAktionsCodes.includes(row.item_code)) {
                        if (row.qty !== 1) {
                            frappe.model.set_value(cdt, cdn, 'qty', 1);
                            frappe.show_alert('Die Menge von Aktionsartikeln kann nicht geändert werden!', 3);
                        }
                    }
                    
                    // Defensive: Wenn Menge auf 0 gesetzt wird, Flag entfernen
                    if (row.qty === 0 && row._aktionsartikel === true) {
                        row._aktionsartikel = undefined;
                    }
                }
            }
        });
    }
});

function recalculateActionItemsOrder(frm) {
    // Lade Aktionseinstellungen
    frappe.call({
        method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
        async: false,
        callback: function(r) {
            if (!r.message) return;
            
            let settings = r.message;
            const STAGE_1_MIN = settings.stage_1_minimum;
            const standardVariants = (settings.variants && settings.variants.standard) ? settings.variants.standard : [];
            const premiumVariants = (settings.variants && settings.variants.premium) ? settings.variants.premium : [];
            const allAktionsCodes = [...standardVariants, ...premiumVariants].map(v => v.code).filter(Boolean);
            
            // Prüfe aktuelle Items auf Aktionsberechtigung
            let actionTotal = 0;
            let hasAktionsartikel = false;
            let aktionsartikelIndex = -1;
            
            frm.doc.items.forEach((item, index) => {
                if (item._aktionsartikel === true) {
                    hasAktionsartikel = true;
                    aktionsartikelIndex = index;
                } else {
                    // Prüfe ob Item für Aktion berücksichtigt wird
                    frappe.call({
                        method: "frappe.client.get_value",
                        args: {
                            doctype: "Item",
                            filters: { item_code: item.item_code },
                            fieldname: "custom_considered_for_action"
                        },
                        async: false,
                        callback: function(item_r) {
                            if (item_r.message && item_r.message.custom_considered_for_action) {
                                actionTotal += item.amount;
                            }
                        }
                    });
                }
            });
            
            // Wenn Aktionsartikel vorhanden aber Schwellwert nicht mehr erreicht
            if (hasAktionsartikel && actionTotal < STAGE_1_MIN) {
                // Entferne Aktionsartikel
                frm.get_field("items").grid.grid_rows[aktionsartikelIndex].remove();
                frm.refresh_field("items");
                frappe.show_alert('Aktionsartikel wurde entfernt, da der Schwellwert nicht mehr erreicht wird.', 5);
            }
        }
    });
}