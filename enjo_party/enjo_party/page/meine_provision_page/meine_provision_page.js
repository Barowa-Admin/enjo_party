frappe.pages['meine-provision-page'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Meine Provision',
		single_column: true
	});

	page._provision_allow_print = false;
	page._provision_print_block_reason = '';

	function syncProvisionPrintUI(freePeriod, canPrint, reason) {
		var allow = !!canPrint && !freePeriod;
		page._provision_allow_print = allow;
		page._provision_print_block_reason = reason || '';
		var text = (!allow && reason) ? reason : '';
		var $hint = $('#provision-print-hint');
		if ($hint.length) {
			$hint.text(text);
		}
		var $btn = page.btn_primary;
		if ($btn && $btn.length) {
			$btn.prop('disabled', !allow);
			$btn.toggleClass('disabled', !allow);
		}
	}

	page.set_primary_action('Drucken', function() {
		if (!page._provision_allow_print) {
			frappe.msgprint(
				page._provision_print_block_reason ||
					__('Druck ist für diesen Zeitraum nicht möglich.')
			);
			return;
		}
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

	$(page.body).append(
		'<p id="provision-print-hint" class="text-muted small" style="margin-bottom: 8px;"></p>' +
			'<div id="provision-table" style="margin-top: 20px;"></div>'
	);

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
				var msg = response.message;
				var rows = [];
				var canPrint = false;
				var reason = '';
				if (msg && msg.rows) {
					rows = msg.rows;
					canPrint = msg.can_print === true;
					reason = msg.print_block_reason || '';
				} else if ($.isArray(msg)) {
					rows = msg;
					canPrint = false;
					reason = '';
				}
				showTable(rows);
				syncProvisionPrintUI(freePeriod, canPrint, reason);
			}
		});
	}

	// Button Funktion global verfügbar machen
	window.printProvision = function() {
		if (!page._provision_allow_print) {
			frappe.msgprint(
				page._provision_print_block_reason ||
					__('Druck ist für diesen Zeitraum nicht möglich.')
			);
			return;
		}

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
		if (!data) {
			data = [];
		}
		var html = '<table class="table table-bordered table-striped">';
		html += '<thead><tr>';
		html += '<th style="width: 80px;">Bezahlt am</th>';
		html += '<th style="width: 150px;">Rechnung</th>';
		html += '<th style="width: 88px;">Status</th>';
		html += '<th style="width: 230px;">Kundenname</th>';
		html += '<th style="width: 80px;">Umsatz</th>';
		html += '<th style="width: 160px;">Provisionsfähiger Betrag</th>';
		html += '<th style="width: 80px;">Provision</th>';
		html += '<th style="width: 60px;">Punkte</th>';
		html += '</tr></thead><tbody>';

		var total = 0;
		data.forEach(function(row) {
			var isTotalRow = row[1] === 'GESAMT';
			if (isTotalRow) {
				html += '<tr style="font-weight: bold; background-color: #f8f9fa;">';
			} else {
				html += '<tr>';
			}
			
			html += '<td>' + (row[0] || '') + '</td>';
			
			html += '<td>' + (isTotalRow ? '' : (row[1] || '')) + '</td>';

			// Status (row[2]) als Badge wie in Ausgangsrechnung
			html += '<td>' + getStatusBadgeHtml(row[2], isTotalRow) + '</td>';
			
			// Kundenname mit Link (row[3] = customer_name, row[4] = customer_id)
			if (isTotalRow) {
				html += '<td style="text-align: right;">GESAMT</td>';
			} else if (row[4]) {
				html += '<td><a href="/app/customer/' + row[4] + '" target="_blank">' + (row[3] || '') + '</a></td>';
			} else {
				html += '<td>' + (row[3] || '') + '</td>';
			}
			html += '<td style="text-align: right;">' + (row[5] ? format_currency(row[5]) : '') + '</td>';
			html += '<td style="text-align: right;">' + (row[6] ? format_currency(row[6]) : '') + '</td>';
			html += '<td style="text-align: right;">' + (row[7] ? format_currency(row[7]) : '') + '</td>';
			html += '<td style="text-align: right;">' + ((row[8] !== null && row[8] !== undefined) ? row[8] : '') + '</td>';
			html += '</tr>';
			
			if (!isTotalRow) {
				total += (row[7] || 0);  // Commission ist jetzt row[7]
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

function getStatusBadgeHtml(status, isTotalRow) {
	if (isTotalRow || !status) {
		return '';
	}

	var statusColorMap = {
		'Bezahlt': 'green',
		'Paid': 'green',
		'Unbezahlt': 'red',
		'Unpaid': 'red',
		'Überfällig': 'red',
		'Overdue': 'red',
		'Teilbezahlt': 'orange',
		'Partly Paid': 'orange',
		'Entwurf': 'blue',
		'Draft': 'blue',
		'Gebucht': 'blue',
		'Submitted': 'blue',
		'Gutschrift': 'orange',
		'Return': 'orange',
		'Gutschrift ausgelöst': 'orange',
		'Credit Note Issued': 'orange',
		'Storniert': 'gray',
		'Cancelled': 'gray'
	};

	var colorClass = statusColorMap[status] || 'gray';
	return '<span class="indicator-pill ' + colorClass + '">' + frappe.utils.escape_html(status) + '</span>';
}