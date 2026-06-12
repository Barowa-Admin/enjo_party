import calendar
from datetime import date, datetime
from typing import Any, Optional

import frappe
from frappe.utils import flt, getdate


MONTH_NAMES = [
	"Januar", "Februar", "März", "April", "Mai", "Juni",
	"Juli", "August", "September", "Oktober", "November", "Dezember",
]


_NO_SALES_PARTNER_WARNING = (
	"Ihr Benutzerkonto ist keinem Vertriebspartner zugeordnet. "
	"Bitte wenden Sie sich an die Geschäftsstelle."
)


def _normalize_name(value: Optional[str]) -> str:
	if not value:
		return ""
	return " ".join(value.split()).strip().casefold()


def _find_sales_partner_by_partner_name(partner_name: Optional[str]) -> Optional[str]:
	if not partner_name:
		return None
	exact = frappe.db.get_value("Sales Partner", {"partner_name": partner_name}, "name")
	if exact:
		return exact
	normalized = _normalize_name(partner_name)
	if not normalized:
		return None
	for row in frappe.get_all("Sales Partner", fields=["name", "partner_name"]):
		if _normalize_name(row.partner_name) == normalized:
			return row.name
	return None


def _get_sales_partner_for_user(user: str) -> Optional[str]:
	try:
		sales_partner_meta = frappe.get_meta("Sales Partner")
		if sales_partner_meta.has_field("custom_user"):
			sales_partner = frappe.db.get_value("Sales Partner", {"custom_user": user}, "name")
			if sales_partner:
				return sales_partner
	except Exception:
		pass

	try:
		user_full_name = frappe.db.get_value("User", user, "full_name")
		sales_partner = _find_sales_partner_by_partner_name(user_full_name)
		if sales_partner:
			return sales_partner
		return _find_sales_partner_by_partner_name(user)
	except Exception:
		pass
	return None


def _si_base_conditions(sales_partner: str) -> tuple[str, dict]:
	return "si.sales_partner = %(sales_partner)s", {"sales_partner": sales_partner}


def _no_sales_partner_response(user: str) -> dict[str, Any]:
	user_full_name = frappe.db.get_value("User", user, "full_name")
	frappe.log_error(
		title="Meine Provision: Kein Sales Partner",
		message=f"User: {user!r}, full_name: {user_full_name!r}",
	)
	return _empty_response(
		can_print=False,
		sales_partner_found=False,
		warning=_NO_SALES_PARTNER_WARNING,
	)


def _storno_clause() -> str:
	return """si.docstatus = 1
		AND si.is_return = 0
		AND NOT EXISTS (
			SELECT 1 FROM `tabSales Invoice` storno
			WHERE storno.return_against = si.name
			AND storno.docstatus = 1
		)"""


def _fetch_payment_rows(sales_invoice_names: list[str]) -> list[dict[str, Any]]:
	if not sales_invoice_names:
		return []
	placeholders = ", ".join(["%s"] * len(sales_invoice_names))
	return frappe.db.sql(
		f"""
		SELECT
			per.reference_name AS sales_invoice,
			per.allocated_amount AS allocated_amount,
			pe.posting_date AS posting_date,
			pe.creation AS pe_creation,
			per.idx AS per_idx
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name AND pe.docstatus = 1
		WHERE per.reference_doctype = 'Sales Invoice'
		AND per.reference_name IN ({placeholders})
		ORDER BY per.reference_name, pe.posting_date, pe.creation, per.idx
		""",
		tuple(sales_invoice_names),
		as_dict=True,
	)


def _paid_cum_up_to(allocations: list[dict], as_of: date) -> float:
	total = 0.0
	for row in allocations:
		pd = getdate(row.posting_date)
		if pd <= as_of:
			total = flt(total + flt(row.allocated_amount))
	return total


def _completion_info(
	allocations: list[dict],
	grand_total: float,
) -> tuple[Optional[date], Optional[date]]:
	"""Erster Zeitpunkt, an dem kumulierte Zuordnungen grand_total erreichen."""
	if flt(grand_total) <= 0:
		return None, None
	cum = 0.0
	comp_date = None
	comp_pay_display = None
	for row in allocations:
		cum = flt(cum + flt(row.allocated_amount))
		if comp_date is None and cum >= flt(grand_total) - 1e-6:
			comp_date = getdate(row.posting_date)
			comp_pay_display = comp_date
	return comp_date, comp_pay_display


def _month_bounds(year: int, month_num: int) -> tuple[date, date]:
	first = date(year, month_num, 1)
	last = date(year, month_num, calendar.monthrange(year, month_num)[1])
	return first, last


def _is_current_calendar_month(year: int, month_num: int) -> bool:
	t = date.today()
	return t.year == year and t.month == month_num


def _candidate_invoice_names_month(
	base_sql: str,
	base_vals: dict,
	first_day: date,
	last_day: date,
	period_end: date,
	is_current: bool,
) -> set[str]:
	def q(extra: str, vals: dict) -> list[str]:
		sql = f"""
			SELECT DISTINCT si.name
			FROM `tabSales Invoice` si
			WHERE {_storno_clause()}
			AND {base_sql}
			AND {extra}
		"""
		return frappe.db.sql(sql, vals, pluck=True)

	if is_current:
		posting_end = min(last_day, period_end)
		part1 = q(
			f"si.posting_date >= %(fd)s AND si.posting_date <= %(ped)s",
			{**base_vals, "fd": first_day, "ped": posting_end},
		)
		part2 = q(
			f"""EXISTS (
				SELECT 1 FROM `tabPayment Entry Reference` per
				INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name AND pe.docstatus = 1
				WHERE per.reference_doctype = 'Sales Invoice'
				AND per.reference_name = si.name
				AND pe.posting_date >= %(fd)s AND pe.posting_date <= %(ped)s
			)""",
			{**base_vals, "fd": first_day, "ped": min(last_day, period_end)},
		)
	else:
		part1 = q(
			f"si.posting_date >= %(fd)s AND si.posting_date <= %(ld)s",
			{**base_vals, "fd": first_day, "ld": last_day},
		)
		part2 = q(
			f"""EXISTS (
				SELECT 1 FROM `tabPayment Entry Reference` per
				INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name AND pe.docstatus = 1
				WHERE per.reference_doctype = 'Sales Invoice'
				AND per.reference_name = si.name
				AND pe.posting_date >= %(fd)s AND pe.posting_date <= %(ld)s
			)""",
			{**base_vals, "fd": first_day, "ld": last_day},
		)
	return set(part1) | set(part2)


def _candidate_invoice_names_free_range(
	base_sql: str,
	base_vals: dict,
	d_from: date,
	d_to: date,
) -> set[str]:
	part1 = frappe.db.sql(
		f"""
		SELECT DISTINCT si.name
		FROM `tabSales Invoice` si
		WHERE {_storno_clause()}
		AND {base_sql}
		AND si.posting_date >= %(df)s AND si.posting_date <= %(dt)s
		""",
		{**base_vals, "df": d_from, "dt": d_to},
		pluck=True,
	)
	part2 = frappe.db.sql(
		f"""
		SELECT DISTINCT si.name
		FROM `tabSales Invoice` si
		WHERE {_storno_clause()}
		AND {base_sql}
		AND EXISTS (
			SELECT 1 FROM `tabPayment Entry Reference` per
			INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name AND pe.docstatus = 1
			WHERE per.reference_doctype = 'Sales Invoice'
			AND per.reference_name = si.name
			AND pe.posting_date >= %(df)s AND pe.posting_date <= %(dt)s
		)
		""",
		{**base_vals, "df": d_from, "dt": d_to},
		pluck=True,
	)
	return set(part1) | set(part2)


def _load_invoice_rows(names: list[str]) -> dict[str, Any]:
	if not names:
		return {}
	placeholders = ", ".join(["%s"] * len(names))
	rows = frappe.db.sql(
		f"""
		SELECT
			si.name,
			si.posting_date,
			si.status AS invoice_status,
			si.docstatus AS invoice_docstatus,
			c.customer_name,
			si.customer,
			si.grand_total,
			si.amount_eligible_for_commission,
			si.total_commission
		FROM `tabSales Invoice` si
		LEFT JOIN `tabCustomer` c ON si.customer = c.name
		WHERE si.name IN ({placeholders})
		""",
		tuple(names),
		as_dict=True,
	)
	return {r.name: r for r in rows}


def _load_punkte_map(names: list[str]) -> dict[str, float]:
	if not names:
		return {}
	placeholders = ", ".join(["%s"] * len(names))
	rows = frappe.db.sql(
		f"""
		SELECT sales_invoice, SUM(punkte_gesamt) AS punkte_gesamt
		FROM `tabENJO Punkte Transaktion`
		WHERE is_cancelled = 0
		AND sales_invoice IN ({placeholders})
		GROUP BY sales_invoice
		""",
		tuple(names),
		as_dict=True,
	)
	return {r.sales_invoice: flt(r.punkte_gesamt) for r in rows}


def _format_invoice_status(invoice_status: Optional[str], invoice_docstatus: int) -> str:
	if invoice_docstatus == 0:
		return "Entwurf"
	if invoice_docstatus == 2:
		return "Storniert"
	status_map = {
		"Paid": "Bezahlt",
		"Unpaid": "Unbezahlt",
		"Overdue": "Überfällig",
		"Partly Paid": "Teilbezahlt",
		"Return": "Gutschrift",
		"Credit Note Issued": "Gutschrift ausgelöst",
		"Cancelled": "Storniert",
		"Draft": "Entwurf",
		"Submitted": "Gebucht",
	}
	return status_map.get(invoice_status, invoice_status or "")


def _filter_closed_month_names(
	inv_by_name: dict[str, Any],
	allocs_by_si: dict[str, list[dict]],
	first_day: date,
	last_day: date,
) -> set[str]:
	selected: set[str] = set()
	for name, inv in inv_by_name.items():
		pd = getdate(inv.posting_date)
		if not (first_day <= pd <= last_day):
			continue
		gt = flt(inv.grand_total)
		allocs = allocs_by_si.get(name, [])
		paid_end = _paid_cum_up_to(allocs, last_day)
		comp, _ = _completion_info(allocs, gt)
		in_a = flt(paid_end) < flt(gt) - 1e-6 and (comp is None or comp <= last_day)
		if in_a:
			selected.add(name)
	# B: completion in month
	for name, inv in inv_by_name.items():
		gt = flt(inv.grand_total)
		allocs = allocs_by_si.get(name, [])
		comp, _ = _completion_info(allocs, gt)
		if comp is not None and first_day <= comp <= last_day:
			selected.add(name)
	return selected


def _filter_current_month_names(
	candidates: set[str],
	inv_by_name: dict[str, Any],
	allocs_by_si: dict[str, list[dict]],
	first_day: date,
	last_day: date,
	period_end: date,
) -> set[str]:
	selected: set[str] = set()
	posting_end = min(last_day, period_end)
	for name in candidates:
		inv = inv_by_name.get(name)
		if not inv:
			continue
		pd = getdate(inv.posting_date)
		if first_day <= pd <= posting_end:
			selected.add(name)
			continue
		gt = flt(inv.grand_total)
		allocs = allocs_by_si.get(name, [])
		comp, _ = _completion_info(allocs, gt)
		if comp is not None and first_day <= comp <= last_day and comp <= period_end:
			selected.add(name)
	return selected


def _filter_free_range_names(
	inv_by_name: dict[str, Any],
	allocs_by_si: dict[str, list[dict]],
	d_from: date,
	d_to: date,
) -> set[str]:
	selected: set[str] = set()
	for name, inv in inv_by_name.items():
		pd = getdate(inv.posting_date)
		if d_from <= pd <= d_to:
			selected.add(name)
	for name, inv in inv_by_name.items():
		gt = flt(inv.grand_total)
		allocs = allocs_by_si.get(name, [])
		comp, _ = _completion_info(allocs, gt)
		if comp is not None and d_from <= comp <= d_to:
			selected.add(name)
	return selected


@frappe.whitelist()
def get_provision_data(month=None, year=None, date_from=None, date_to=None):
	"""
	Holt Provisionsdaten für den angemeldeten User.
	Rückgabe: dict mit rows, can_print, print_block_reason, sales_partner_found, warning.
	"""
	user = frappe.session.user
	free_period = bool(date_from and date_to)

	if not free_period and (not month or not year):
		heute = datetime.now()
		import datetime as dt

		letzter_monat = heute.replace(day=1) - dt.timedelta(days=1)
		if not month:
			month = MONTH_NAMES[letzter_monat.month - 1]
		if not year:
			year = letzter_monat.year

	sales_partner = _get_sales_partner_for_user(user)
	if not sales_partner:
		return _no_sales_partner_response(user)
	base_sql, base_vals = _si_base_conditions(sales_partner)

	today = date.today()
	candidate_names: set[str] = set()
	period_end: date
	title_month: Optional[str] = None
	title_year: Optional[int] = None
	selected_year: Optional[int] = None
	selected_month_num: Optional[int] = None

	if free_period:
		d_from = getdate(date_from)
		d_to = getdate(date_to)
		period_end = d_to
		candidate_names = _candidate_invoice_names_free_range(base_sql, base_vals, d_from, d_to)
		name_list = list(candidate_names)
		inv_by_name = _load_invoice_rows(name_list)
		all_rows = _fetch_payment_rows(name_list)
		allocs_by_si: dict[str, list[dict]] = {}
		for row in all_rows:
			allocs_by_si.setdefault(row.sales_invoice, []).append(row)
		final_names = _filter_free_range_names(inv_by_name, allocs_by_si, d_from, d_to)
	elif month and year:
		if month not in MONTH_NAMES:
			return _empty_response(False)
		selected_month_num = MONTH_NAMES.index(month) + 1
		selected_year = int(year)
		first_day, last_day = _month_bounds(selected_year, selected_month_num)
		title_month, title_year = month, selected_year
		is_cur = _is_current_calendar_month(selected_year, selected_month_num)
		period_end = today if is_cur else last_day
		candidate_names = _candidate_invoice_names_month(
			base_sql, base_vals, first_day, last_day, period_end, is_cur
		)
		name_list = list(candidate_names)
		inv_by_name = _load_invoice_rows(name_list)
		all_rows = _fetch_payment_rows(name_list)
		allocs_by_si = {}
		for row in all_rows:
			allocs_by_si.setdefault(row.sales_invoice, []).append(row)
		if is_cur:
			final_names = _filter_current_month_names(
				candidate_names, inv_by_name, allocs_by_si, first_day, last_day, period_end
			)
		else:
			final_names = _filter_closed_month_names(inv_by_name, allocs_by_si, first_day, last_day)
	else:
		return _empty_response(False)

	name_list_final = sorted(final_names)
	inv_by_name = _load_invoice_rows(name_list_final)
	punkte_map = _load_punkte_map(name_list_final)
	allocs_by_si = {}
	for row in _fetch_payment_rows(name_list_final):
		allocs_by_si.setdefault(row.sales_invoice, []).append(row)

	data: list[list[Any]] = []
	total_provision = 0.0
	total_punkte = 0
	total_umsatz = 0.0
	total_amount_eligible = 0.0

	sort_keys: list[tuple] = []
	for si_name in name_list_final:
		inv = inv_by_name.get(si_name)
		if not inv:
			continue
		allocs = allocs_by_si.get(si_name, [])
		gt = flt(inv.grand_total)
		comp_date, pay_display = _completion_info(allocs, gt)
		paid_period = _paid_cum_up_to(allocs, period_end)
		fully_paid_now = flt(gt) > 0 and flt(paid_period) >= flt(gt) - 1e-6 and (
			comp_date is not None and comp_date <= period_end
		)
		if fully_paid_now:
			display_pay_date = pay_display or comp_date
			payment_cell = display_pay_date.strftime("%d.%m.%Y") if display_pay_date else ""
			is_paid_row = True
			status_label = "Bezahlt"
			umsatz = flt(inv.grand_total)
			amount_eligible = flt(inv.amount_eligible_for_commission)
			commission = flt(inv.total_commission)
			punkte = int(punkte_map.get(si_name, 0) or 0)
		else:
			payment_cell = ""
			is_paid_row = False
			status_label = _format_invoice_status(
				inv.get("invoice_status"), int(inv.get("invoice_docstatus") or 0)
			)
			umsatz = None
			amount_eligible = None
			commission = None
			punkte = None

		if is_paid_row:
			total_provision += commission
			total_punkte += punkte
			total_umsatz += umsatz
			total_amount_eligible += amount_eligible

		sort_dt = comp_date or getdate(inv.posting_date)
		sort_keys.append((sort_dt, si_name))
		data.append(
			[
				payment_cell,
				si_name,
				status_label,
				inv.customer_name,
				inv.customer if inv.customer else None,
				umsatz,
				amount_eligible,
				commission,
				punkte,
			]
		)

	# Sort descending by payment/completion or posting
	order = {t[1]: i for i, t in enumerate(sorted(sort_keys, key=lambda x: (-x[0].toordinal(), x[1])))}
	data.sort(key=lambda row: order.get(row[1], 0))

	if data and (free_period or (title_month and title_year)):
		if free_period:
			from frappe.utils import formatdate

			title = f"Provision {formatdate(date_from, 'dd.MM.yyyy')} - {formatdate(date_to, 'dd.MM.yyyy')}"
		else:
			title = f"Provision {title_month} {title_year}"
		data.append(
			[
				"",
				"GESAMT",
				title,
				"",
				None,
				total_umsatz,
				total_amount_eligible,
				total_provision,
				total_punkte,
			]
		)

	can_print = False
	print_block_reason = None
	if free_period:
		can_print = False
		print_block_reason = "Im freien Zeitraum ist kein Druck der Provisionsabrechnung möglich."
	elif selected_year is not None and selected_month_num is not None:
		req_idx = selected_year * 12 + selected_month_num
		cur_idx = today.year * 12 + today.month
		if req_idx >= cur_idx:
			can_print = False
			print_block_reason = (
				"Nur abgeschlossene Monate können als Provisionsabrechnung gedruckt werden."
			)
		else:
			can_print = True

	return {
		"rows": data,
		"can_print": can_print,
		"print_block_reason": print_block_reason,
		"sales_partner_found": True,
		"warning": None,
	}


def _empty_response(
	can_print: bool,
	sales_partner_found: bool = True,
	warning: Optional[str] = None,
) -> dict[str, Any]:
	return {
		"rows": [],
		"can_print": can_print,
		"print_block_reason": None,
		"sales_partner_found": sales_partner_found,
		"warning": warning,
	}
