frappe.ui.form.on('Subscription', {
	refresh: function(frm) {
		// Entferne zuerst alle vorhandenen Buttons (verhindere Duplikate)
		$(frm.wrapper).find('.btn-cancel-subscription').remove();
		
		// Prüfe ob das Abonnement aktiv ist
		if (frm.doc.status === "Active") {
			setTimeout(() => {
				addCancelButton(frm);
			}, 300);
			
			setTimeout(() => {
				addCancelButton(frm);
			}, 800);
		}
	}
});

function addCancelButton(frm) {
	// Prüfe ob der Button bereits existiert
	if ($(frm.wrapper).find('.btn-cancel-subscription').length > 0) {
		return;
	}
	
	// Finde den Aktionen-Button
	let actionsButton = $(frm.wrapper).find('button.btn-default.ellipsis[data-toggle="dropdown"]');
	
	if (actionsButton.length === 0) {
		actionsButton = $(frm.wrapper).find('button:contains("Aktionen")');
	}
	
	if (actionsButton.length > 0) {
		// Erstelle einen Standard-Frappe-Button (wie der Aktionen-Button)
		let cancelButton = $('<button>')
			.addClass('btn btn-default btn-cancel-subscription')
			.attr('type', 'button')
			.text('Abonnement beenden')
			.css('margin-right', '5px')
			.on('click', function(e) {
				e.preventDefault();
				e.stopPropagation();
				
				// Öffne das Dropdown und verstecke es sofort visuell
				actionsButton.trigger('click');
				
				// Verstecke das Dropdown-Menü sofort, damit es nicht sichtbar ist
				setTimeout(() => {
					$('.dropdown-menu').css('display', 'none');
				}, 10);
				
				setTimeout(() => {
					// Suche nach dem Cancel-Menüpunkt (nehme den ersten, der "Abonnement beenden" oder "Cancel" enthält)
					let cancelMenuItem = $('.dropdown-menu a:contains("Abonnement beenden")').first();
					
					if (cancelMenuItem.length === 0) {
						cancelMenuItem = $('.dropdown-menu a:contains("Cancel Subscription")').first();
					}
					
					if (cancelMenuItem.length === 0) {
						cancelMenuItem = $('.dropdown-menu a[data-label*="Cancel"]').first();
					}
					
					if (cancelMenuItem.length > 0) {
						// Speichere Subscription Name für späteren Aufruf
						let subscriptionName = frm.doc.name;
						console.log('Abonnement beenden Button: Subscription Name gespeichert:', subscriptionName);
						
						// Klicke auf den Menüpunkt (dieser zeigt dann seinen eigenen Bestätigungsdialog)
						cancelMenuItem[0].click();
						
						// Warte auf Bestätigung und rufe dann zusätzlich die Stripe-Kündigung auf
						// Verwende einen Observer auf das refresh-Event, um zu erkennen, wenn das Dokument neu geladen wird (nach Cancel)
						let refreshHandler = frm.refresh;
						let stripeCancelCalled = false;
						
						// Überschreibe refresh-Handler temporär
						frm.refresh = function() {
							refreshHandler.apply(this, arguments);
							
							// Prüfe ob Status auf "Cancelled" gesetzt wurde und Stripe-Kündigung noch nicht aufgerufen wurde
							if (!stripeCancelCalled && this.doc.status === "Cancelled") {
								stripeCancelCalled = true;
								console.log('Status ist Cancelled, rufe Stripe-Kündigung auf für:', subscriptionName);
								
								// Rufe Server-Funktion auf, um Stripe Subscription zu kündigen
								frappe.call({
									method: "enjo_party.enjo_party.utils.stripe_subscription.cancel_subscription_in_stripe",
									args: {
										subscription_name: subscriptionName
									},
									callback: function(r) {
										console.log('Stripe-Kündigung Antwort:', r);
										if (r.message && r.message.success) {
											frappe.show_alert({
												message: __('Stripe Subscription wurde erfolgreich gekündigt'),
												indicator: 'green'
											}, 5);
										} else {
											console.error('Stripe Kündigung fehlgeschlagen:', r.message);
											frappe.show_alert({
												message: __('Stripe Kündigung fehlgeschlagen: ' + (r.message ? r.message.message : 'Unbekannter Fehler')),
												indicator: 'red'
											}, 5);
										}
									}
								});
							}
						};
						
						// Fallback: Prüfe auch nach 2 Sekunden, falls refresh nicht aufgerufen wird
						setTimeout(() => {
							if (!stripeCancelCalled && frm.doc.status === "Cancelled") {
								stripeCancelCalled = true;
								console.log('Fallback: Status ist Cancelled, rufe Stripe-Kündigung auf für:', subscriptionName);
								
								frappe.call({
									method: "enjo_party.enjo_party.utils.stripe_subscription.cancel_subscription_in_stripe",
									args: {
										subscription_name: subscriptionName
									},
									callback: function(r) {
										console.log('Stripe-Kündigung Antwort (Fallback):', r);
										if (r.message && r.message.success) {
											frappe.show_alert({
												message: __('Stripe Subscription wurde erfolgreich gekündigt'),
												indicator: 'green'
											}, 5);
										} else {
											console.error('Stripe Kündigung fehlgeschlagen:', r.message);
											frappe.show_alert({
												message: __('Stripe Kündigung fehlgeschlagen: ' + (r.message ? r.message.message : 'Unbekannter Fehler')),
												indicator: 'red'
											}, 5);
										}
									}
								});
							}
						}, 2000);
					} else {
						// Fallback: Versuche alle Menüpunkte zu durchsuchen
						let allMenuItems = $('.dropdown-menu a');
						let found = false;
						allMenuItems.each(function() {
							let text = $(this).text().toLowerCase();
							if ((text.includes('cancel') || text.includes('beenden') || text.includes('kündigen')) && !found) {
								$(this)[0].click();
								found = true;
								return false;
							}
						});
						
						if (!found) {
							frappe.msgprint(__('Fehler: Cancel-Funktion nicht gefunden.'));
							actionsButton.trigger('click'); // Schließe Dropdown
						}
					}
				}, 50); // Sehr kurze Verzögerung, damit es kaum sichtbar ist
			});
		
		// Füge den Button links neben dem Aktionen-Button ein
		actionsButton.before(cancelButton);
	}
}

