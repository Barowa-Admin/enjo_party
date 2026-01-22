app_name = "enjo_party"
app_title = "Enjo Party"
app_publisher = "Elia"
app_description = "Enjo Party"
app_email = "elia@enjo.at"
app_license = "mit"

# Apps
# ------------------

required_apps = ["frappe", "erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "enjo_party",
# 		"logo": "/assets/enjo_party/logo.png",
# 		"title": "Enjo Präsentation",
# 		"route": "/enjo_party",
# 		"has_permission": "enjo_party.enjo_party.api.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/enjo_party/css/enjo_party.css"
app_include_js = "/assets/enjo_party/js/customer_quick_entry.js"

# include js, css files in header of web template
# web_include_css = "/assets/enjo_party/css/enjo_party.css"
# web_include_js = "/assets/enjo_party/js/enjo_party.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "enjo_party/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Party": "enjo_party/doctype/party/party.js",
    "Sammelbestellung": "enjo_party/doctype/sammelbestellung/sammelbestellung.js",
    "Sales Invoice": "public/js/sales_invoice.js",
    "Sales Order": "public/js/sales_order.js",
    "Subscription": "public/js/subscription.js"
}
doctype_list_js = {
    "Party": "enjo_party/doctype/party/party_list.js",
    "Sammelbestellung": "enjo_party/doctype/sammelbestellung/sammelbestellung_list.js",
    "Subscription": "public/js/subscription_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "enjo_party/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "enjo_party.utils.jinja_methods",
# 	"filters": "enjo_party.utils.jinja_filters"
# }

# Fixtures
# --------

fixtures = ["Custom Field"]

# Installation
# ------------

# before_install = "enjo_party.install.before_install"
# after_install = "enjo_party.utils.fix_erpnext_compatibility"

# Uninstallation
# ------------

# before_uninstall = "enjo_party.uninstall.before_uninstall"
# after_uninstall = "enjo_party.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "enjo_party.utils.before_app_install"
# after_app_install = "enjo_party.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "enjo_party.utils.before_app_uninstall"
# after_app_uninstall = "enjo_party.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "enjo_party.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Address": {
		"before_insert": "enjo_party.enjo_party.utils.address_hooks.copy_email_from_customer",
		"on_update": "enjo_party.enjo_party.utils.address_hooks.notify_draft_invoices_on_address_change",
		"after_insert": "enjo_party.enjo_party.utils.address_hooks.notify_draft_invoices_on_address_change"
	},
	"Sales Invoice": {
		"onload": "enjo_party.enjo_party.utils.sales_invoice_hooks.onload_sales_invoice",
		"before_validate": [
			"enjo_party.enjo_party.utils.sales_invoice_hooks.before_validate_sales_invoice",
			"enjo_party.enjo_party.utils.subscription_hooks.ensure_subscription_invoice_taxes_before_validate"
		],
		"before_save": "enjo_party.enjo_party.utils.sales_invoice_hooks.add_shipping_to_sales_invoice",
		"before_submit": "enjo_party.enjo_party.utils.subscription_hooks.ensure_subscription_invoice_taxes",
		"after_save": "enjo_party.enjo_party.utils.sales_invoice_hooks.after_save_sales_invoice",
		"on_submit": [
			"enjo_party.enjo_party.server_scripts.enjo_punkte_vergabe.award_points_on_invoice_submit",
			"enjo_party.enjo_party.utils.subscription_hooks.create_payment_request_for_subscription_invoice"
			# "enjo_party.enjo_party.utils.sales_invoice_hooks.auto_create_picklist_from_invoice"  # DEAKTIVIERT - wird jetzt in Sammelbestellung gesteuert
		],
		"on_cancel": "enjo_party.enjo_party.server_scripts.enjo_punkte_vergabe.cancel_points_on_invoice_cancel",
		# Sammelbestellungs-Status: Prüfe ob alle Rechnungen bezahlt sind
		# Subscription-Status: Prüfe ob Subscription-Rechnungen bezahlt sind
		"on_update_after_submit": [
			"enjo_party.enjo_party.utils.sammelbestellung_status.update_sammelbestellung_status_on_invoice_payment",
			"enjo_party.enjo_party.utils.subscription_status.update_subscription_status_on_invoice_payment"
		]
	},
	"Sales Order": {
		"on_submit": "enjo_party.enjo_party.utils.sales_order_hooks.auto_create_and_submit_sales_invoice"
	},
	# Sammelbestellungs-Status: Update bei Zahlungseingang
	# Subscription-Status: Update bei Zahlungseingang
	"Payment Entry": {
		"on_submit": [
			"enjo_party.enjo_party.utils.sammelbestellung_status.update_sammelbestellung_status_on_payment",
			"enjo_party.enjo_party.utils.subscription_status.update_subscription_status_on_payment"
		]
	},
	# ===================================================================================
	# DELIVERY NOTE & PICK LIST HOOKS - LAGER-VALIDIERUNG DEAKTIVIERT
	# ===================================================================================
	# Diese Hooks machen Lieferscheine und Packlisten IMMER buchbar, auch wenn:
	# - Der Lagerbestand nicht ausreicht
	# - Die Bewertungsrate fehlt
	# - Keine Buchhaltungseinträge erstellt werden können
	#
	# ZUM DEAKTIVIEREN: Kommentiere die entsprechenden Zeilen aus
	# (Kommentiere die gesamten "Delivery Note" und "Pick List" Blöcke aus)
	#
	# HINWEIS: Wenn diese Hooks deaktiviert werden, müssen die Funktionen in
	#          delivery_note_hooks.py und pick_list_hooks.py NICHT gelöscht werden,
	#          sondern nur die Registrierung hier entfernt werden.
	# ===================================================================================
	"Delivery Note": {
		"before_insert": "enjo_party.enjo_party.utils.delivery_note_hooks.before_insert_delivery_note",
		"before_validate": "enjo_party.enjo_party.utils.delivery_note_hooks.before_validate_delivery_note",
		"before_submit": "enjo_party.enjo_party.utils.delivery_note_hooks.before_submit_delivery_note",
		# Sammelbestellungs-Status: Update wenn Gruppenversand-Lieferschein gebucht wird
		# Subscription-Status: Update wenn Subscription-Lieferschein gebucht wird
		# Webhook-Trigger: Explizit für Gruppenversand-Lieferscheine, da Frappe's Standard-System diese nicht triggert
		"on_submit": [
			"enjo_party.enjo_party.utils.sammelbestellung_status.update_sammelbestellung_status_on_delivery",
			"enjo_party.enjo_party.utils.subscription_status.update_subscription_status_on_delivery",
			"enjo_party.enjo_party.utils.delivery_note_hooks.on_submit_delivery_note"
		]
	},
	"Pick List": {
		"before_validate": "enjo_party.enjo_party.utils.pick_list_hooks.before_validate_pick_list",
		"before_save": "enjo_party.enjo_party.utils.pick_list_hooks.before_save_pick_list",
		"before_submit": "enjo_party.enjo_party.utils.pick_list_hooks.before_submit_pick_list"
	},
	"Subscription": {
		"before_validate": "enjo_party.enjo_party.utils.subscription_hooks.validate_subscription_end_date",
		"after_insert": "enjo_party.enjo_party.utils.subscription_hooks.force_subscription_update",
		"after_save": "enjo_party.enjo_party.utils.subscription_hooks.force_subscription_update",
		"on_cancel": "enjo_party.enjo_party.utils.subscription_hooks.handle_subscription_cancel"
	},
	"Subscription Plan": {
		"before_save": [
			"enjo_party.enjo_party.utils.subscription_hooks.set_default_payment_gateway",
			"enjo_party.enjo_party.utils.subscription_hooks.validate_subscription_plan_interval"
		],
		"validate": [
			"enjo_party.enjo_party.utils.subscription_hooks.set_default_payment_gateway",
			"enjo_party.enjo_party.utils.subscription_hooks.validate_subscription_plan_interval"
		]
	},
	"Payment Request": {
		"before_validate": "enjo_party.enjo_party.utils.payment_request_hooks.validate_payment_request_subscription",
		"on_update": "enjo_party.enjo_party.utils.payment_request_hooks.create_payment_entry_on_paid"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"enjo_party.enjo_party.utils.status_scheduler.update_overdue_status"
	]
}

# Testing
# -------

# before_tests = "enjo_party.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "enjo_party.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "enjo_party.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["enjo_party.utils.fix_erpnext_compatibility"]
# after_request = ["enjo_party.utils.after_request"]

# Job Events
# ----------
# before_job = ["enjo_party.utils.before_job"]
# after_job = ["enjo_party.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"enjo_party.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

