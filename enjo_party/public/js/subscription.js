// Zusätzlicher Button „Abonnement beenden“ (gleiche Logik wie ERPNext „Cancel Subscription“ unter Aktionen).
// Früher: DOM-Hack (Dropdown öffnen + Menüpunkt klicken) — bricht bei neuen Frappe-Toolbars.
// Jetzt: offizielle API + gleicher Server-Call wie subscription.js (ERPNext), zuvor Stripe-Kündigung.

frappe.ui.form.on("Subscription", {
	refresh(frm) {
		if (frm.is_new()) return;

		add_recalculate_period_button(frm);

		if (frm.doc.status === "Cancelled") return;

		const label = __("Cancel Subscription");
		frm.page.remove_inner_button(label);

		const $btn = frm.page.add_inner_button(
			label,
			() => cancel_subscription_with_stripe(frm),
			null,
			"default"
		);

		prepend_inner_button(frm, $btn);
	},
});

function add_recalculate_period_button(frm) {
	const label = __("Periode neu berechnen");
	frm.page.remove_inner_button(label);

	const $btn = frm.page.add_inner_button(
		label,
		() => recalculate_subscription_period(frm),
		null,
		"default"
	);

	prepend_inner_button(frm, $btn);
}

function prepend_inner_button(frm, $btn) {
	if ($btn && $btn.length && frm.page.inner_toolbar && frm.page.inner_toolbar.length) {
		const $first_group = frm.page.inner_toolbar.children(".btn-group").first();
		if ($first_group.length) {
			$first_group.before($btn);
		} else {
			$btn.prependTo(frm.page.inner_toolbar);
		}
	}
}

function recalculate_subscription_period(frm) {
	frappe.confirm(
		__(
			"Die Abo-Periode wird anhand des aktuellen Plans neu berechnet: bei bestehenden Rechnungen ab der letzten Auslösung, sonst ab dem Abo-Start. Stripe bitte separat anpassen. Fortfahren?"
		),
		() => {
			frappe.call({
				method: "enjo_party.enjo_party.utils.subscription_hooks.recalculate_subscription_period",
				args: { subscription_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Bitte warten …"),
				callback(r) {
					const msg = r.message;
					if (!msg || !msg.success) {
						frappe.msgprint({
							message: (msg && msg.message) || __("Periode konnte nicht neu berechnet werden."),
							indicator: "red",
						});
						return;
					}
					frappe.msgprint({
						title: __("Periode aktualisiert"),
						message:
							msg.old_period +
							"<br>→ " +
							msg.new_period +
							"<br><br>" +
							msg.message,
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		}
	);
}

function cancel_subscription_with_stripe(frm) {
	frappe.confirm(
		__(
			"This action will stop future billing. Are you sure you want to cancel this subscription?"
		),
		() => {
			frappe.call({
				method: "enjo_party.enjo_party.utils.stripe_subscription.cancel_subscription_in_stripe",
				args: { subscription_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Bitte warten …"),
				callback(r) {
					if (r.message && r.message.success === false) {
						frappe.msgprint({
							message:
								r.message.message ||
								__("Stripe meldet ein Problem; Abo wird trotzdem in ERPNext gekündigt."),
							indicator: "orange",
						});
					}
					frm.call("cancel_subscription").then((res) => {
						if (!res.exec) {
							frm.reload_doc();
						}
					});
				},
				error() {
					frm.call("cancel_subscription").then((res) => {
						if (!res.exec) {
							frm.reload_doc();
						}
					});
				},
			});
		}
	);
}
