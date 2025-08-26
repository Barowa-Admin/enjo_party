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
                    const allAktionsCodes = [v1_code, v2_code, v3_code, v4_code, v5_code, v6_code, v7_code].filter(code => code);
                    
                    // Prüfe, ob bereits ein Aktionsartikel vorhanden ist und welcher Typ
                    let currentAktionsartikel = null;
                    let currentStage = 0;
                    
                    frm.doc.items.forEach(item => {
                        if (allAktionsCodes.includes(item.item_code)) {
                            currentAktionsartikel = item;
                            // Bestimme aktuelle Stage basierend auf dem Artikel
                            if ([v1_code, v2_code, v3_code, v4_code].includes(item.item_code)) {
                                currentStage = 1;
                            } else if ([v5_code, v6_code, v7_code].includes(item.item_code)) {
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
                                if (total > STAGE_1_MAX) {
                                    // Stage 2 berechtigt
                                    if (currentStage === 1) {
                                        // Upgrade von Stage 1 zu Stage 2 - entferne aktuellen Aktionsartikel
                                        showStage2UpgradeDialog(total, currentAktionsartikel);
                                    } else if (currentStage === 0) {
                                        // Kein Aktionsartikel vorhanden - zeige Stage 2
                                        showStage2Dialog(total);
                                    } else {
                                        // Bereits Stage 2
                                        frappe.validated = true;
                                    }
                                } else if (total > STAGE_1_MIN) {
                                    // Stage 1 berechtigt
                                    if (currentStage === 0) {
                                        // Kein Aktionsartikel vorhanden - zeige Stage 1
                                        showStage1Dialog(total);
                                    } else if (currentStage === 2) {
                                        // Downgrade von Stage 2 zu Stage 1
                                        showStage1DowngradeDialog(total, currentAktionsartikel);
                                    } else {
                                        // Bereits Stage 1 Aktionsartikel vorhanden
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
                            callback: function(r) {
                                if (r.message && r.message.custom_considered_for_action) {
                                    actionItems.push(item);
                                    total += item.amount;
                                    console.log(`Item ${item.item_code} wird für Aktion berücksichtigt (${item.amount} EUR)`);
                                }
                                checkItemsForAction(items, index + 1, actionItems, total, currentAktionsartikel, currentStage);
                            }
                        });
                    }
                    
                    function showStage1Dialog(total) {
                        frappe.validated = false;
                        
                        let d = new frappe.ui.Dialog({
                            title: 'Herzlichen Glückwunsch!',
                            fields: [
                                {
                                    fieldtype: 'Select',
                                    fieldname: 'aktion_artikel',
                                    label: 'Wähle deinen Aktionsartikel',
                                    options: [v1_name, v2_name, v3_name, v4_name].filter(name => name),
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
                                    options: [v5_name, v6_name, v7_name].filter(name => name),
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
                                    options: [v1_name, v2_name, v3_name, v4_name].filter(name => name),
                                    reqd: 1
                                },
                                {
                                    fieldtype: 'HTML',
                                    fieldname: 'description',
                                    options: `
                                        <div style="margin-top: 10px; margin-bottom: 10px;">
                                            <p>Dein Einkauf berechtigt dich zur Standard-Aktion.</p>
                                            <p>Dein aktueller Premium-Aktionsartikel "${currentAktionsartikel.item_name}" kann durch einen Standard-Artikel ersetzt werden.</p>
                                            <br>
                                            <p>Mit der Auswahl "Behalten" behältst du deinen Premium-Artikel.</p>
                                        </div>
                                    `
                                }
                            ],
                            primary_action_label: 'Wechseln',
                            primary_action: function() {
                                let values = d.get_values();
                                let selectedItem = values.aktion_artikel;
                                let itemCode = getItemCodeFromName(selectedItem);
                                
                                // Entferne aktuellen Premium-Aktionsartikel
                                let itemIndex = frm.doc.items.findIndex(item => item.item_code === currentAktionsartikel.item_code);
                                if (itemIndex !== -1) {
                                    frm.get_field("items").grid.grid_rows[itemIndex].remove();
                                    frm.refresh_field("items");
                                }
                                
                                addAktionsartikelToInvoice(itemCode, selectedItem, d);
                            },
                            secondary_action_label: 'Behalten',
                            secondary_action: function() {
                                console.log("Premium-Artikel wird beibehalten");
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
                                    options: [v5_name, v6_name, v7_name].filter(name => name),
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
                                
                                // Entferne aktuellen Aktionsartikel
                                let itemIndex = frm.doc.items.findIndex(item => item.item_code === currentAktionsartikel.item_code);
                                if (itemIndex !== -1) {
                                    frm.get_field("items").grid.grid_rows[itemIndex].remove();
                                    frm.refresh_field("items");
                                }
                                
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
                    
                    function addAktionsartikelToInvoice(itemCode, selectedItem, dialog) {
                        if (!itemCode) {
                            frappe.msgprint(`Aktionsartikel ${selectedItem} konnte nicht gefunden werden.`);
                            saveFromDialog(dialog);
                            return;
                        }
                        
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
    qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // Lade Aktionseinstellungen um zu prüfen ob es ein Aktionsartikel ist
        frappe.call({
            method: "enjo_party.enjo_party.doctype.enjo_aktionseinstellungen.enjo_aktionseinstellungen.get_aktionseinstellungen",
            async: false,
            callback: function(r) {
                if (r.message) {
                    let settings = r.message;
                    const allAktionsCodes = [
                        settings.v1_code, settings.v2_code, settings.v3_code, 
                        settings.v4_code, settings.v5_code, settings.v6_code, 
                        settings.v7_code
                    ].filter(code => code);
                    
                    // Prüfe ob es ein Aktionsartikel ist
                    if (allAktionsCodes.includes(row.item_code)) {
                        if (row.qty !== 1) {
                            frappe.model.set_value(cdt, cdn, 'qty', 1);
                            frappe.show_alert('Die Menge von Aktionsartikeln kann nicht geändert werden!', 3);
                        }
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
            const allAktionsCodes = [
                settings.v1_code, settings.v2_code, settings.v3_code, 
                settings.v4_code, settings.v5_code, settings.v6_code, 
                settings.v7_code
            ].filter(code => code);
            
            // Prüfe aktuelle Items auf Aktionsberechtigung
            let actionTotal = 0;
            let hasAktionsartikel = false;
            let aktionsartikelIndex = -1;
            
            frm.doc.items.forEach((item, index) => {
                if (allAktionsCodes.includes(item.item_code)) {
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