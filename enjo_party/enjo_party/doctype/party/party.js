// Copyright (c) 2025, Elia and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Party", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Party', {
	refresh(frm) {
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

		// Für alle Versand-Select-Felder die Optionen setzen
		// Basierend auf der JSON-Definition gibt es 4 Versandfelder
		frm.set_df_property('versand_gast_1', 'options', optionen.join('\n'));
		frm.set_df_property('versand_gast_2', 'options', optionen.join('\n'));
		frm.set_df_property('versand_gast_3', 'options', optionen.join('\n'));
		frm.set_df_property('versand_gast_4', 'options', optionen.join('\n'));
	}
});
