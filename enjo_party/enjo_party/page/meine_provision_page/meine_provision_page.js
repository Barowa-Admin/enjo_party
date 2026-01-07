frappe.pages['meine-provision-page'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Meine Provision',
		single_column: true
	});

	// Drucken Button direkt im Header hinzufügen
	page.set_primary_action('Drucken', function() {
		console.log('Drucken Button geklickt!');
		window.printProvision();
	});

	// Setze automatisch den letzten abgeschlossenen Monat
	var heute = new Date();
	var letzterMonat = new Date(heute.getFullYear(), heute.getMonth() - 1, 1);
	
	var monthNames = [
		"Januar", "Februar", "März", "April", "Mai", "Juni",
		"Juli", "August", "September", "Oktober", "November", "Dezember"
	];
	
	var defaultMonth = monthNames[letzterMonat.getMonth()];
	var defaultYear = letzterMonat.getFullYear();
	
	// Von Datum: 1. des aktuellen Monats (Format: YYYY-MM-DD)
	var firstDayCurrentMonth = new Date(heute.getFullYear(), heute.getMonth(), 1);
	var year = firstDayCurrentMonth.getFullYear();
	var month = String(firstDayCurrentMonth.getMonth() + 1).padStart(2, '0');
	var day = String(firstDayCurrentMonth.getDate()).padStart(2, '0');
	var defaultDateFrom = year + '-' + month + '-' + day;
	
	// Bis Datum: Heutiges Datum (Format: YYYY-MM-DD)
	var todayYear = heute.getFullYear();
	var todayMonth = String(heute.getMonth() + 1).padStart(2, '0');
	var todayDay = String(heute.getDate()).padStart(2, '0');
	var defaultDateTo = todayYear + '-' + todayMonth + '-' + todayDay;

	// Filter erstellen
	page.add_field({
		label: 'Monat',
		fieldtype: 'Select',
		fieldname: 'month',
		options: monthNames,
		default: defaultMonth,
		change: function() {
			loadData();
		}
	});

	page.add_field({
		label: 'Jahr',
		fieldtype: 'Int',
		fieldname: 'year',
		default: defaultYear,
		change: function() {
			loadData();
		}
	});

	// Datum-Felder für freien Zeitraum
	page.add_field({
		label: 'Von Datum',
		fieldtype: 'Date',
		fieldname: 'date_from',
		change: function() {
			loadData();
		}
	});

	page.add_field({
		label: 'Bis Datum',
		fieldtype: 'Date',
		fieldname: 'date_to',
		change: function() {
			loadData();
		}
	});

	// Checkbox für Freier Zeitraum (als letztes Feld ganz rechts)
	page.add_field({
		label: 'Freien Zeitraum auswählen',
		fieldtype: 'Check',
		fieldname: 'free_period',
		default: 0,
		change: function() {
			togglePeriodFields();
			loadData();
		}
	});
	
	// Checkbox-Label breiter machen damit kein Zeilenumbruch
	setTimeout(function() {
		if (page.fields_dict.free_period && page.fields_dict.free_period.$wrapper) {
			var label = page.fields_dict.free_period.$wrapper.find('label');
			if (label.length) {
				label.css('white-space', 'nowrap');
				label.css('min-width', '200px');
			}
		}
	}, 100);
	
	// Toggle-Funktion für Felder ein-/ausblenden (nur visuell, technisch bleibt alles gleich)
	function togglePeriodFields() {
		var freePeriod = page.fields_dict.free_period ? page.fields_dict.free_period.get_value() : 0;
		
		if (freePeriod) {
			// Freier Zeitraum aktiviert: Monat/Jahr ausblenden, Datum-Felder anzeigen
			if (page.fields_dict.month && page.fields_dict.month.$wrapper) {
				page.fields_dict.month.$wrapper.hide();
			}
			if (page.fields_dict.year && page.fields_dict.year.$wrapper) {
				page.fields_dict.year.$wrapper.hide();
			}
			if (page.fields_dict.date_from && page.fields_dict.date_from.$wrapper) {
				page.fields_dict.date_from.$wrapper.show();
			}
			if (page.fields_dict.date_to && page.fields_dict.date_to.$wrapper) {
				page.fields_dict.date_to.$wrapper.show();
			}
		} else {
			// Freier Zeitraum deaktiviert: Datum-Felder ausblenden, Monat/Jahr anzeigen
			if (page.fields_dict.date_from && page.fields_dict.date_from.$wrapper) {
				page.fields_dict.date_from.$wrapper.hide();
			}
			if (page.fields_dict.date_to && page.fields_dict.date_to.$wrapper) {
				page.fields_dict.date_to.$wrapper.hide();
			}
			if (page.fields_dict.month && page.fields_dict.month.$wrapper) {
				page.fields_dict.month.$wrapper.show();
			}
			if (page.fields_dict.year && page.fields_dict.year.$wrapper) {
				page.fields_dict.year.$wrapper.show();
			}
		}
	}
	
	// Initial: Datum-Felder ausblenden, Monat/Jahr sichtbar lassen
	// Warten bis alle Felder initialisiert sind
	setTimeout(function() {
		togglePeriodFields();
	}, 150);

	// Datatable Container
	$(page.body).append('<div id="provision-table" style="margin-top: 20px;"></div>');

	function loadData() {
		var freePeriod = page.fields_dict.free_period ? page.fields_dict.free_period.get_value() : 0;
		var args = {};
		
		if (freePeriod) {
			// Freier Zeitraum: date_from und date_to verwenden
			// Wichtig: Werte auch abrufen wenn Felder ausgeblendet sind
			var dateFrom = null;
			var dateTo = null;
			
			if (page.fields_dict.date_from) {
				dateFrom = page.fields_dict.date_from.get_value();
			}
			if (page.fields_dict.date_to) {
				dateTo = page.fields_dict.date_to.get_value();
			}
			
			// Falls keine Werte vorhanden, Standardwerte verwenden
			if (!dateFrom) {
				dateFrom = defaultDateFrom;
			}
			if (!dateTo) {
				dateTo = defaultDateTo;
			}
			
			if (dateFrom && dateTo) {
				args.date_from = dateFrom;
				args.date_to = dateTo;
			} else {
				// Wenn keine Daten ausgewählt, nichts laden
				return;
			}
		} else {
			// Monat/Jahr Modus: month und year verwenden
			// Wichtig: Werte auch abrufen wenn Felder ausgeblendet sind
			var month = null;
			var year = null;
			
			if (page.fields_dict.month) {
				month = page.fields_dict.month.get_value();
			}
			if (page.fields_dict.year) {
				year = page.fields_dict.year.get_value();
			}
			
			if (!month || !year) {
				// Wenn keine Werte vorhanden, nichts laden
				return;
			}
			
			args.month = month;
			args.year = year;
		}
		
		frappe.call({
			method: 'enjo_party.enjo_party.page.meine_provision_page.meine_provision_page.get_provision_data',
			args: args,
			callback: function(response) {
				if (response.message) {
					showTable(response.message);
				}
			}
		});
	}

	// Button Funktion global verfügbar machen
	window.printProvision = function() {
		console.log('Print function called!');
		
		// Hole aktuelle Tabellendaten
		var tableHtml = $('#provision-table').html();
		
		if (!tableHtml || tableHtml.trim() === '') {
			frappe.msgprint('Keine Daten zum Drucken vorhanden!');
			return;
		}
		
		// Hole aktuellen Benutzernamen
		var userName = frappe.session.user_fullname || frappe.session.user || 'Unbekannt';
		
		// Bestimme Zeitraum-Text je nach Checkbox-Status
		var freePeriod = page.fields_dict.free_period ? page.fields_dict.free_period.get_value() : 0;
		var periodText = '';
		
		if (freePeriod) {
			// Freier Zeitraum: Von/Bis Datum verwenden
			var dateFrom = page.fields_dict.date_from ? page.fields_dict.date_from.get_value() : null;
			var dateTo = page.fields_dict.date_to ? page.fields_dict.date_to.get_value() : null;
			
			if (dateFrom && dateTo) {
				// Datum formatieren (von YYYY-MM-DD zu DD.MM.YYYY)
				var formatDate = function(dateStr) {
					if (!dateStr) return '';
					var parts = dateStr.split('-');
					if (parts.length === 3) {
						return parts[2] + '.' + parts[1] + '.' + parts[0];
					}
					return dateStr;
				};
				periodText = formatDate(dateFrom) + ' - ' + formatDate(dateTo);
			} else {
				periodText = 'Freier Zeitraum';
			}
		} else {
			// Monat/Jahr Modus
			var month = page.fields_dict.month ? page.fields_dict.month.get_value() : '';
			var year = page.fields_dict.year ? page.fields_dict.year.get_value() : '';
			periodText = month + ' ' + year;
		}
		
		// Erstelle CSS für sauberes Drucken
		var printStyles = `
			<style id="print-styles">
				@media print {
					* { 
						-webkit-print-color-adjust: exact !important;
						color-adjust: exact !important;
					}
					
					body { 
						font-family: Arial, sans-serif !important;
						margin: 0 !important;
						padding: 20px !important;
						background: white !important;
						color: black !important;
						font-size: 12px !important;
					}
					
					/* Verstecke alles außer unserer Tabelle */
					.layout-main, .navbar, .sidebar, .page-head,
					.form-control, .btn, .filter-section, #provision-table {
						display: none !important;
					}
					
					/* Zeige nur Print Content */
					.print-only {
						display: block !important;
					}
					
					.print-only h1 { 
						color: #333 !important;
						margin-bottom: 10px !important;
						text-align: center !important;
						font-size: 24px !important;
					}
					
					.print-only h2 {
						text-align: center !important;
						margin-bottom: 5px !important;
						font-size: 16px !important;
						color: #666 !important;
					}
					
					.print-only h3 {
						text-align: center !important;
						margin-bottom: 30px !important;
						font-size: 14px !important;
						color: #666 !important;
					}
					
					.print-only table { 
						width: 100% !important;
						border-collapse: collapse !important;
						margin-top: 20px !important;
						background: white !important;
					}
					
					.print-only th, .print-only td { 
						border: 1px solid #333 !important;
						padding: 8px !important;
						text-align: left !important;
						font-size: 12px !important;
					}
					
					.print-only th { 
						background-color: #f0f0f0 !important;
						font-weight: bold !important;
					}
					
					.print-only p {
						text-align: center !important;
						font-size: 10px !important;
						margin-top: 30px !important;
					}
				}
			</style>
		`;
		
		// Erstelle Print Content
		var printContent = `
			<div class="print-only" style="display: none;">
				<h1>Meine Provision</h1>
				<h2>Benutzer: ${userName}</h2>
				<h3>Zeitraum: ${periodText}</h3>
				${tableHtml}
				<p><small>Erstellt am: ${new Date().toLocaleDateString('de-DE')}</small></p>
			</div>
		`;
		
		// Füge Styles und Content hinzu
		$('head').append(printStyles);
		$('body').append(printContent);
		
		// Drucken
		window.print();
		
		// Cleanup nach dem Drucken
		setTimeout(function() {
			$('#print-styles').remove();
			$('.print-only').remove();
		}, 1000);
	};

	function showTable(data) {
		var html = '<table class="table table-bordered table-striped">';
		html += '<thead><tr>';
		html += '<th style="width: 80px;">Bezahlt am</th>';
		html += '<th style="width: 150px;">Rechnung</th>';
		html += '<th style="width: 230px;">Kundenname</th>';
		html += '<th style="width: 80px;">Umsatz</th>';
		html += '<th style="width: 160px;">Provisionsfähiger Betrag</th>';
		html += '<th style="width: 80px;">Provision</th>';
		html += '<th style="width: 60px;">Punkte</th>';
		html += '</tr></thead><tbody>';

		var total = 0;
		data.forEach(function(row) {
			if (row[1] === 'GESAMT') {
				html += '<tr style="font-weight: bold; background-color: #f8f9fa;">';
			} else {
				html += '<tr>';
			}
			
			html += '<td>' + (row[0] || '') + '</td>';
			
			html += '<td>' + (row[1] || '') + '</td>';
			
			// Kundenname mit Link (row[2] = customer_name, row[3] = customer_id)
			if (row[3] && row[1] !== 'GESAMT') {
				html += '<td><a href="/app/customer/' + row[3] + '" target="_blank">' + (row[2] || '') + '</a></td>';
			} else {
				html += '<td>' + (row[2] || '') + '</td>';
			}
			html += '<td style="text-align: right;">' + (row[4] ? format_currency(row[4]) : '') + '</td>';
			html += '<td style="text-align: right;">' + (row[5] ? format_currency(row[5]) : '') + '</td>';
			html += '<td style="text-align: right;">' + (row[6] ? format_currency(row[6]) : '') + '</td>';
			html += '<td style="text-align: right;">' + (row[7] || '0') + '</td>';
			html += '</tr>';
			
			if (row[1] !== 'GESAMT') {
				total += (row[6] || 0);  // Commission ist jetzt row[6]
			}
		});
		
		html += '</tbody></table>';
		
		$('#provision-table').html(html);
	}

	// Initial laden - Daten für Monat/Jahr laden (Checkbox ist nicht aktiviert)
	// Datum-Felder befüllen, Felder ausblenden und dann Daten laden
	setTimeout(function() {
		// Datum-Felder befüllen (auch wenn sie ausgeblendet werden)
		if (page.fields_dict.date_from) {
			page.fields_dict.date_from.set_value(defaultDateFrom);
		}
		if (page.fields_dict.date_to) {
			page.fields_dict.date_to.set_value(defaultDateTo);
		}
		// Felder korrekt anzeigen/ausblenden (Monat/Jahr sichtbar, Datum-Felder ausgeblendet)
		togglePeriodFields();
		// Daten laden
		loadData();
	}, 250);
};

function format_currency(amount) {
	return '€ ' + parseFloat(amount).toFixed(2).replace('.', ',');
}

function printProvision() {
	// Hole aktuelle Tabellendaten
	var tableHtml = $('#provision-table').html();
	
	if (!tableHtml || tableHtml.trim() === '') {
		frappe.msgprint('Keine Daten zum Drucken vorhanden!');
		return;
	}
	
	// Bestimme Zeitraum-Text je nach Checkbox-Status
	var freePeriod = page.fields_dict.free_period ? page.fields_dict.free_period.get_value() : 0;
	var periodText = '';
	
	if (freePeriod) {
		// Freier Zeitraum: Von/Bis Datum verwenden
		var dateFrom = page.fields_dict.date_from ? page.fields_dict.date_from.get_value() : null;
		var dateTo = page.fields_dict.date_to ? page.fields_dict.date_to.get_value() : null;
		
		if (dateFrom && dateTo) {
			// Datum formatieren (von YYYY-MM-DD zu DD.MM.YYYY)
			var formatDate = function(dateStr) {
				if (!dateStr) return '';
				var parts = dateStr.split('-');
				if (parts.length === 3) {
					return parts[2] + '.' + parts[1] + '.' + parts[0];
				}
				return dateStr;
			};
			periodText = formatDate(dateFrom) + ' - ' + formatDate(dateTo);
		} else {
			periodText = 'Freier Zeitraum';
		}
	} else {
		// Monat/Jahr Modus
		var month = page.fields_dict.month ? page.fields_dict.month.get_value() : '';
		var year = page.fields_dict.year ? page.fields_dict.year.get_value() : '';
		periodText = month + ' ' + year;
	}
	
	// Erstelle Druckfenster wie am Anfang
	var printHtml = `
		<!DOCTYPE html>
		<html>
		<head>
			<title>Meine Provision - ${periodText}</title>
			<meta charset="utf-8">
			<style>
				body { 
					font-family: Arial, sans-serif; 
					margin: 20px;
					background: white;
				}
				h1 { 
					color: #333; 
					margin-bottom: 20px; 
					text-align: center;
				}
				table { 
					width: 100%; 
					border-collapse: collapse; 
					margin-top: 20px;
					background: white;
				}
				th, td { 
					border: 1px solid #333; 
					padding: 8px; 
					text-align: left; 
				}
				th { 
					background-color: #f0f0f0; 
					font-weight: bold; 
				}
				.header { 
					margin-bottom: 30px; 
					text-align: center;
				}
				@media print {
					body { margin: 0; }
				}
			</style>
		</head>
		<body>
			<div class="header">
				<h1>Meine Provision</h1>
				<h3>Zeitraum: ${periodText}</h3>
			</div>
			${tableHtml}
			<br>
			<p style="text-align: center;"><small>Erstellt am: ${new Date().toLocaleDateString('de-DE')}</small></p>
		</body>
		</html>
	`;
	
	// Neues Fenster für Druck öffnen
	var printWindow = window.open('', '_blank');
	printWindow.document.write(printHtml);
	printWindow.document.close();
	
	// Automatisch Druck-Dialog öffnen
	setTimeout(function() {
		printWindow.print();
	}, 500);
}