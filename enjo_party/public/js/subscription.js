// Zusätzlicher Button „Abonnement beenden“ (gleiche Logik wie ERPNext „Cancel Subscription“ unter Aktionen).
// Früher: DOM-Hack (Dropdown öffnen + Menüpunkt klicken) — bricht bei neuen Frappe-Toolbars.
// Jetzt: offizielle API + gleicher Server-Call wie subscription.js (ERPNext), zuvor Stripe-Kündigung.

frappe.ui.form.on("Subscription", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Cancelled") return;

		const label = __("Cancel Subscription");
		frm.page.remove_inner_button(label);

		const $btn = frm.page.add_inner_button(
			label,
			() => cancel_subscription_with_stripe(frm),
			null,
			"default"
		);

		// Links neben der „Aktionen“-Dropdown-Gruppe (wie bisher gewünscht)
		if ($btn && $btn.length && frm.page.inner_toolbar && frm.page.inner_toolbar.length) {
			const $first_group = frm.page.inner_toolbar.children(".btn-group").first();
			if ($first_group.length) {
				$first_group.before($btn);
			} else {
				$btn.prependTo(frm.page.inner_toolbar);
			}
		}
	},
});

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
