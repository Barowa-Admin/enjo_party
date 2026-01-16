// Customer Quick Entry Override
// Korrigiert E-Mail Problem für Adresserstellung

console.log('Customer Quick Entry Override wird geladen...');

console.log('=== ENJO PARTY CUSTOMER QUICK ENTRY WIRD GELADEN 57 (sauberer Stand mit E-Mail Mapping) ===');
frappe.provide("frappe.ui.form");

// Erstmal den frappe.client.save Override entfernt um zu testen
// ob unser Formular wieder funktioniert

// Customer Quick Entry Override - komplett eigene Implementierung
frappe.ui.form.CustomerQuickEntryForm = class CustomerQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	constructor(doctype, after_insert, init_callback, doc, force) {
		console.log('ENJO CUSTOMER QUICK ENTRY CONSTRUCTOR AUFGERUFEN!');
		super(doctype, after_insert, init_callback, doc, force);
		this.skip_redirect_on_error = true;
	}

	render_dialog() {
		console.log('ENJO RENDER_DIALOG AUFGERUFEN!');
		this.mandatory = this.get_variant_fields();
		super.render_dialog();
		
		// "Vollständiges Formular bearbeiten" Button verstecken (DE + EN)
		setTimeout(() => {
			if (this.dialog && this.dialog.$wrapper) {
				// Alle möglichen Selektoren für den Button
				const buttonSelectors = [
					'.edit-full',                                      // CSS Klasse
					'[data-label="Edit Full Form"]',                   // Data Attribut (EN)
					'button:contains("Edit Full Form")',               // Button Text (EN)
					'button:contains("Vollständiges Formular")',       // Button Text (DE)
					'button:contains("Vollständiges Formular bearbeiten")', // Button Text (DE - alt)
					'a:contains("Edit Full Form")',                    // Link Text (EN)
					'a:contains("Vollständiges Formular")',            // Link Text (DE)
					'a:contains("Vollständiges Formular bearbeiten")'  // Link Text (DE - alt)
				];

				// Jeden Selektor durchgehen und Element ausblenden falls gefunden
				buttonSelectors.forEach(selector => {
					const elements = this.dialog.$wrapper.find(selector);
					if (elements.length) {
						elements.hide();
					}
				});
			}
			
			// Event-Handler für Kundentyp-Änderung
			this.setup_customer_type_handler();
			
			// Explizit "Einzelperson" setzen und sichtbar machen
			this.dialog.set_value('customer_type_selection', 'Einzelperson');
			
			// Initial den korrekten customer_type setzen
			this.update_customer_name_label();
			
			// Standard-Feld auch direkt verstecken
			this.hide_standard_customer_type_field();
			
			// Vertriebspartner automatisch setzen
			this.set_sales_partner_from_user();
		}, 100);
		
		// Nochmal nach längerem Delay für sicheres Verstecken
		setTimeout(() => {
			this.hide_standard_customer_type_field();
		}, 300);
	}

	setup_customer_type_handler() {
		if (this.dialog.fields_dict.customer_type_selection) {
			this.dialog.fields_dict.customer_type_selection.$input.on('change', () => {
				this.update_customer_name_label();
			});
		}
	}

	update_customer_name_label() {
		const customer_type = this.dialog.get_value('customer_type_selection');
		
		if (customer_type === 'Unternehmen') {
			this.dialog.set_df_property('customer_name', 'label', 'Unternehmensname');
			// Setze auch den ERPNext customer_type
			this.dialog.set_value('customer_type', 'Company');
			
			// Adressfelder für Unternehmen umschalten
			this.switch_to_company_address_fields();
		} else {
			this.dialog.set_df_property('customer_name', 'label', 'Kundenname');
			// Setze auch den ERPNext customer_type
			this.dialog.set_value('customer_type', 'Individual');
			
			// Adressfelder für Einzelperson umschalten
			this.switch_to_individual_address_fields();
		}
		
		// Standard ERPNext Kundentyp-Feld verstecken (falls vorhanden)
		this.hide_standard_customer_type_field();
	}

	switch_to_company_address_fields() {
		// Rechnungsadresse für Unternehmen
		this.dialog.set_df_property('address_line1', 'label', 'Name des Ansprechpartners');
		this.dialog.set_df_property('address_line1', 'reqd', 0);  // Nicht mehr Pflicht
		this.dialog.set_df_property('address_line2', 'label', 'Straße & Hausnummer');
		this.dialog.set_df_property('address_line2', 'hidden', 0);  // Sichtbar machen
		this.dialog.set_df_property('address_line2', 'reqd', 1);   // Pflichtfeld
		
		// Lieferadresse für Unternehmen
		this.dialog.set_df_property('shipping_address_line1', 'label', 'Name des Ansprechpartners');
		this.dialog.set_df_property('shipping_address_line2', 'label', 'Straße & Hausnummer');
		this.dialog.set_df_property('shipping_address_line2', 'hidden', 0);  // Sichtbar machen
		
		this.dialog.refresh();
	}

	switch_to_individual_address_fields() {
		// Rechnungsadresse für Einzelperson  
		this.dialog.set_df_property('address_line1', 'label', 'Straße & Hausnummer');
		this.dialog.set_df_property('address_line1', 'reqd', 1);   // Pflichtfeld
		this.dialog.set_df_property('address_line2', 'label', 'Namen');  // Zurück zu "Namen"
		this.dialog.set_df_property('address_line2', 'hidden', 1); // Verstecken
		this.dialog.set_df_property('address_line2', 'reqd', 0);   // Nicht mehr Pflicht
		
		// Lieferadresse für Einzelperson
		this.dialog.set_df_property('shipping_address_line1', 'label', 'Straße & Hausnummer');
		this.dialog.set_df_property('shipping_address_line2', 'hidden', 1); // Verstecken
		
		this.dialog.refresh();
	}

	hide_standard_customer_type_field() {
		// Verstecke das Standard ERPNext Kundentyp-Feld
		setTimeout(() => {
			if (this.dialog && this.dialog.$wrapper) {
				// Verschiedene mögliche Selektoren für das Standard-Feld
				this.dialog.$wrapper.find('[data-fieldname="customer_type"]:not([data-fieldname="customer_type_selection"])').hide();
				this.dialog.$wrapper.find('select[data-fieldname="customer_type"]').closest('.frappe-control').hide();
				this.dialog.$wrapper.find('label:contains("Kundentyp")').not(':first').closest('.frappe-control').hide();
				
				// Zusätzliche Selektoren für besseres Verstecken
				this.dialog.$wrapper.find('.frappe-control').each(function() {
					const $control = $(this);
					const $select = $control.find('select');
					if ($select.length && $select.attr('data-fieldname') === 'customer_type') {
						$control.hide();
					}
				});
			}
		}, 50);
		
		// Nochmal nach längerem Timeout versuchen
		setTimeout(() => {
			if (this.dialog && this.dialog.$wrapper) {
				this.dialog.$wrapper.find('[data-fieldname="customer_type"]:not([data-fieldname="customer_type_selection"])').closest('.frappe-control').hide();
			}
		}, 200);
	}

	set_sales_partner_from_user() {
		// Nur wenn noch kein Vertriebspartner gesetzt ist
		if (!this.dialog.get_value('sales_partner')) {
			var user_fullname = frappe.session.user_fullname;
			
			if (user_fullname) {
				// Prüfen, ob der Benutzer als Vertriebspartner existiert
				frappe.db.exists('Sales Partner', user_fullname)
					.then(exists => {
						if (exists) {
							this.dialog.set_value('sales_partner', user_fullname);
							console.log("Sales Partner gesetzt auf:", user_fullname);
						}
					});
			}
		}
	}

	insert() {
		console.log('ENJO INSERT AUFGERUFEN!');
		
		// ERPNext-kompatibles Field-Mapping (wie in ContactAddressQuickEntryForm)
		const map_field_names = {
			email_address: "email_id",
			mobile_number: "mobile_no",
		};

		Object.entries(map_field_names).forEach(([fieldname, new_fieldname]) => {
			if (this.dialog.doc[fieldname]) {
				this.dialog.doc[new_fieldname] = this.dialog.doc[fieldname];
				delete this.dialog.doc[fieldname];
			}
		});
		
		// E-Mail für Lieferadresse speichern  
		const email_address = this.dialog.doc.email_id; // Jetzt email_id nach Mapping
		const shipping_data = this.extract_shipping_data();
		
		// E-Mail für Lieferadresse mitgeben
		if (email_address) {
			shipping_data.email_address = email_address;
		}
		
		// Überschreibe die after_insert Callback für Lieferadresse
		const original_after_insert = this.after_insert;
		this.after_insert = (doc) => {
			// Originalen Callback ausführen
			if (original_after_insert) {
				original_after_insert.call(this, doc);
			}
			
			// Nur Lieferadresse erstellen falls Daten vorhanden
			if (shipping_data.has_shipping_data) {
				this.create_shipping_address(doc.name, shipping_data);
			}
		};

		// Standard QuickEntryForm Save
		return super.insert();
	}

	extract_shipping_data() {
		const shipping_fields = ['shipping_address_line1', 'shipping_address_line2', 'shipping_pincode', 
		                        'shipping_city', 'shipping_state', 'shipping_country'];
		
		const shipping_data = {};
		let has_data = false;
		
		shipping_fields.forEach(field => {
			if (this.dialog.doc[field]) {
				shipping_data[field] = this.dialog.doc[field];
				has_data = true;
				// Feld aus Customer-Doc entfernen (gehört nicht zum Customer)
				delete this.dialog.doc[field];
			}
		});
		
		return {
			has_shipping_data: has_data,
			...shipping_data
		};
	}

	create_shipping_address(customer_name, shipping_data) {
		// Neue Lieferadresse erstellen MIT E-Mail damit es funktioniert
		frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: {
					doctype: "Address",
					address_title: customer_name + " - Lieferadresse",
					address_type: "Shipping",
					address_line1: shipping_data.shipping_address_line1 || "",
					address_line2: shipping_data.shipping_address_line2 || "",
					pincode: shipping_data.shipping_pincode || "",
					city: shipping_data.shipping_city || "",
					state: shipping_data.shipping_state || "",
					country: shipping_data.shipping_country || "Deutschland",
					email_id: shipping_data.email_address || "",  // E-Mail hinzufügen
					links: [{
						link_doctype: "Customer",
						link_name: customer_name
					}]
				}
			},
			callback: function(r) {
				if (r.message) {
					console.log("Lieferadresse erstellt:", r.message.name);
				} else if (r.exc) {
					console.error("Fehler bei Lieferadresse:", r.exc);
				}
			}
		});
	}

	get_variant_fields() {
		const variantFields = [
			{
				label: 'Kundentyp',
				fieldname: 'customer_type_selection',
				fieldtype: 'Select',
				options: 'Einzelperson\nUnternehmen',
				default: 'Einzelperson',
			},
			{
				label: 'Kundenname',
				fieldname: 'customer_name',
				fieldtype: 'Data',
				reqd: 1,
			},
			{
				fieldname: 'customer_type',
				fieldtype: 'Select',
				options: 'Individual\nCompany',
				hidden: 1,
				default: 'Individual',
			},
			{
				fieldtype: 'Section Break',
			},
			{
				label: 'Mail',
				fieldname: 'email_address',
				fieldtype: 'Data',
				options: 'Email',
				reqd: 1,
			},
			{
				label: 'Steuernummer',
				fieldname: 'tax_id',
				fieldtype: 'Data',
			},
			{
				fieldtype: 'Column Break',
			},
			{
				label: 'Mobilfunknummer',
				fieldname: 'mobile_number',
				fieldtype: 'Data',
			},
			{
				label: 'Vertriebspartner',
				fieldname: 'sales_partner',
				fieldtype: 'Link',
				options: 'Sales Partner',
			},
			{
				fieldtype: 'Section Break',
				label: 'Rechnungsadresse',
			},
			{
				label: 'Straße & Hausnummer',
				fieldname: 'address_line1',
				fieldtype: 'Data',
				reqd: 1,
			},
			{
				label: 'Namen',
				fieldname: 'address_line2',
				fieldtype: 'Data',
				hidden: 1,
			},
			{
				fieldtype: 'Column Break',
			},
			{
				label: 'Stadt',
				fieldname: 'city',
				fieldtype: 'Data',
				reqd: 1,
			},
			{
				label: 'PLZ',
				fieldname: 'pincode',
				fieldtype: 'Data',
				reqd: 1,
			},
			{
				label: 'Land',
				fieldname: 'country',
				fieldtype: 'Link',
				options: 'Country',
				reqd: 1,
			},
			{
				fieldtype: 'Section Break',
				label: 'Lieferadresse <span style="font-size: 11px; color: #6c757d; font-style: italic; font-weight: normal;">(nur bei Abweichung ausfüllen)</span>',
				fieldname: 'shipping_section',
				collapsible: 1,
			},
			{
				label: 'Straße & Hausnummer',
				fieldname: 'shipping_address_line1',
				fieldtype: 'Data',
			},
			{
				label: 'Namen', 
				fieldname: 'shipping_address_line2',
				fieldtype: 'Data',
				hidden: 1,
			},
			{
				fieldtype: 'Column Break',
				fieldname: 'shipping_column_break',
			},
			{
				label: 'Stadt',
				fieldname: 'shipping_city',
				fieldtype: 'Data',
			},
			{
				label: 'PLZ',
				fieldname: 'shipping_pincode',
				fieldtype: 'Data',
			},
			{
				label: 'Land',
				fieldname: 'shipping_country',
				fieldtype: 'Link',
				options: 'Country',
			},
		];

		return variantFields;
	}
};

console.log('Customer Quick Entry Override installiert!'); 