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
						
						// WICHTIG: Rufe Stripe-Kündigung VOR dem Cancel auf, damit die Subscription noch aktiv ist
						// Fange den Click-Handler ab und rufe zuerst Stripe-Kündigung auf
						let originalClickHandler = cancelMenuItem[0].onclick;
						let originalHref = cancelMenuItem[0].getAttribute('href');
						
						// Überschreibe den Click-Handler temporär
						cancelMenuItem.off('click').on('click', function(e) {
							e.preventDefault();
							e.stopPropagation();
							
							// Rufe zuerst Stripe-Kündigung auf (BEVOR der Standard-Handler läuft)
							frappe.call({
								method: "enjo_party.enjo_party.utils.stripe_subscription.cancel_subscription_in_stripe",
								args: {
									subscription_name: subscriptionName
								},
								callback: function(r) {
									console.log('Stripe-Kündigung Antwort (vor Cancel):', r);
									if (r.message && r.message.success) {
										console.log('Stripe Subscription erfolgreich gekündigt');
									} else {
										console.error('Stripe Kündigung fehlgeschlagen:', r.message);
									}
									
									// Rufe dann den originalen Handler auf
									if (originalClickHandler) {
										originalClickHandler.call(cancelMenuItem[0], e);
									} else if (originalHref) {
										// Fallback: Navigiere zum Link
										window.location.href = originalHref;
									} else {
										// Letzter Fallback: Trigger den originalen Click-Event
										cancelMenuItem[0].dispatchEvent(new MouseEvent('click', { bubbles: true }));
									}
								}
							});
						});
						
						// Klicke auf den Menüpunkt (dieser zeigt dann seinen eigenen Bestätigungsdialog)
						cancelMenuItem[0].click();
						
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

