frappe.query_reports["Meine Provision"] = {
	"onload": function(report) {
		// Setze automatisch den letzten abgeschlossenen Monat
		var heute = new Date();
		var letzterMonat = new Date(heute.getFullYear(), heute.getMonth() - 1, 1);
		
		var monthNames = [
			"Januar", "Februar", "März", "April", "Mai", "Juni",
			"Juli", "August", "September", "Oktober", "November", "Dezember"
		];
		
		var defaultMonth = monthNames[letzterMonat.getMonth()];
		var defaultYear = letzterMonat.getFullYear();
		
		// Setze die Filter nur wenn sie noch nicht gesetzt sind
		if (!report.get_filter_value('month')) {
			report.set_filter_value('month', defaultMonth);
		}
		if (!report.get_filter_value('year')) {
			report.set_filter_value('year', defaultYear);
		}
		

	}
};