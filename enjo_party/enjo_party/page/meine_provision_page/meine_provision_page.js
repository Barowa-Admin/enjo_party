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

	// Datatable Container
	$(page.body).append('<div id="provision-table" style="margin-top: 20px;"></div>');

	function loadData() {
		var month = page.fields_dict.month.get_value();
		var year = page.fields_dict.year.get_value();
		
		frappe.call({
			method: 'enjo_party.enjo_party.page.meine_provision_page.meine_provision_page.get_provision_data',
			args: {
				month: month,
				year: year
			},
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
		var month = page.fields_dict.month.get_value();
		var year = page.fields_dict.year.get_value();
		
		// Hole aktuelle Tabellendaten
		var tableHtml = $('#provision-table').html();
		
		if (!tableHtml || tableHtml.trim() === '') {
			frappe.msgprint('Keine Daten zum Drucken vorhanden!');
			return;
		}
		
		// Hole aktuellen Benutzernamen
		var userName = frappe.session.user_fullname || frappe.session.user || 'Unbekannt';
		
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
				<h3>Zeitraum: ${month} ${year}</h3>
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
		html += '<th style="width: 130px;">Bezahlt am</th>';
		html += '<th style="width: 200px;">Rechnung</th>';
		html += '<th style="width: 230px;">Kundenname</th>';
		html += '<th style="width: 160px;">Provisionsfähiger Betrag</th>';
		html += '<th style="width: 100px;">Provision</th>';
		html += '<th style="width: 80px;">Punkte</th>';
		html += '</tr></thead><tbody>';

		var total = 0;
		data.forEach(function(row) {
			if (row[1] === 'GESAMT') {
				html += '<tr style="font-weight: bold; background-color: #f8f9fa;">';
			} else {
				html += '<tr>';
			}
			
			html += '<td>' + (row[0] || '') + '</td>';
			
			if (row[1] && row[1] !== 'GESAMT' && row[1].startsWith('ACC-')) {
				html += '<td><a href="/app/sales-invoice/' + row[1] + '" target="_blank">' + row[1] + '</a></td>';
			} else {
				html += '<td>' + (row[1] || '') + '</td>';
			}
			
			html += '<td>' + (row[2] || '') + '</td>';
			html += '<td>' + (row[3] ? format_currency(row[3]) : '') + '</td>';
			html += '<td>' + (row[4] ? format_currency(row[4]) : '') + '</td>';
			html += '<td>' + (row[5] || '0') + '</td>';
			html += '</tr>';
			
			if (row[1] !== 'GESAMT') {
				total += (row[4] || 0);
			}
		});
		
		html += '</tbody></table>';
		
		$('#provision-table').html(html);
	}

	// Initial laden
	loadData();
};

function format_currency(amount) {
	return '€ ' + parseFloat(amount).toFixed(2).replace('.', ',');
}

function printProvision() {
	var month = page.fields_dict.month.get_value();
	var year = page.fields_dict.year.get_value();
	
	// Hole aktuelle Tabellendaten
	var tableHtml = $('#provision-table').html();
	
	if (!tableHtml || tableHtml.trim() === '') {
		frappe.msgprint('Keine Daten zum Drucken vorhanden!');
		return;
	}
	
	// Erstelle Druckfenster wie am Anfang
	var printHtml = `
		<!DOCTYPE html>
		<html>
		<head>
			<title>Meine Provision - ${month} ${year}</title>
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
				<h3>Zeitraum: ${month} ${year}</h3>
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