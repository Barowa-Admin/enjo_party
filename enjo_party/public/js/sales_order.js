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
                    
                    // Prüfe, ob bereits ein Aktionsartikel vorhanden ist
                    let hasAktionsartikel = frm.doc.items.some(item => allAktionsCodes.includes(item.item_code));
                    
                    if (!hasAktionsartikel) {
                        // Prüfe alle Items auf ihre Berücksichtigung für Aktionen
                        checkItemsForAction(frm.doc.items, 0, [], 0);
                    } else {
                        frappe.validated = true;
                    }
                    
                    function checkItemsForAction(items, index, actionItems, total) {
                        if (index >= items.length) {
                            console.log("Alle Items wurden geprüft. Aktionsberechtigte Items:", actionItems.length);
                            console.log("Berechnete Aktionssumme:", total);
                            
                            if (actionItems.length > 0) {
                                if (total > STAGE_1_MAX) {
                                    showStage2Dialog(total);
                                } else if (total > STAGE_1_MIN) {
                                    showStage1Dialog(total);
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
                                checkItemsForAction(items, index + 1, actionItems, total);
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
                                
                                addAktionsartikelToOrder(itemCode, selectedItem, d);
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
                                
                                addAktionsartikelToOrder(itemCode, selectedItem, d);
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
                    
                    function addAktionsartikelToOrder(itemCode, selectedItem, dialog) {
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
                                    
                                    // Warehouse vom ersten Item übernehmen
                                    if (frm.doc.items && frm.doc.items.length > 0) {
                                        warehouse = frm.doc.items[0].warehouse || warehouse;
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
                                                item_name: item.item_name || selectedItem,
                                                description: item.description || selectedItem,
                                                qty: 1,
                                                rate: price,
                                                amount: price,
                                                uom: item.stock_uom || "Stk",
                                                stock_uom: item.stock_uom || "Stk",
                                                conversion_factor: 1,
                                                warehouse: warehouse,
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
                            cur_frm.save();
                            
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
    }
}); 