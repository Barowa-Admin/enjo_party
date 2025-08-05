frappe.pages['meine_provision'] = {
    onload: function(wrapper) {
        let page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __('Meine Provision'),
            single_column: true
        });

        // UI-Elemente
        let $container = $(wrapper).find('.layout-main-section');
        $container.append(`
            <div class="meine-provision-filter" style="margin-bottom: 20px; display: flex; align-items: center; gap: 16px;">
                <input type="month" id="monat" class="form-control" style="width: 180px;" />
                <button class="btn btn-primary" id="provision-refresh">Anzeigen</button>
            </div>
            <div id="provision-tabelle"></div>
        `);

        // Standardwert: aktueller Monat
        let now = new Date();
        let monatStr = now.toISOString().slice(0,7);
        $('#monat').val(monatStr);

        function ladeProvisionen() {
            let monat = $('#monat').val();
            frappe.call({
                method: 'enjo_party.enjo_party.doctype.meine_provision.meine_provision.get_data',
                args: { month: monat },
                callback: function(r) {
                    if(r.message && r.message.data) {
                        renderTabelle(r.message);
                    } else {
                        $('#provision-tabelle').html('<div class="alert alert-warning">Keine Daten gefunden.</div>');
                    }
                }
            });
        }

        function renderTabelle(data) {
            let rows = data.data.map(row => `
                <tr>
                    <td>${frappe.datetime.str_to_user(row.datum)}</td>
                    <td>${row.rechnung}</td>
                    <td>${row.kundenname || ''}</td>
                    <td style="text-align:right">${format_currency(row.betrag, 'EUR')}</td>
                    <td style="text-align:right">${format_currency(row.provision, 'EUR')}</td>
                </tr>
            `).join('');
            let html = `
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Datum</th>
                            <th>Rechnung</th>
                            <th>Kundenname</th>
                            <th>Betrag</th>
                            <th>Provision</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                    <tfoot>
                        <tr style="font-weight:bold;">
                            <td colspan="3" style="text-align:right">Summe</td>
                            <td style="text-align:right">${format_currency(data.sum_betrag, 'EUR')}</td>
                            <td style="text-align:right">${format_currency(data.sum_provision, 'EUR')}</td>
                        </tr>
                    </tfoot>
                </table>
            `;
            $('#provision-tabelle').html(html);
        }

        // Event-Handler
        $('#provision-refresh').on('click', ladeProvisionen);
        $('#monat').on('change', ladeProvisionen);

        // Initial laden
        ladeProvisionen();
    }
};