# Enjo Party App

Eine Frappe/ERPNext App für erweiterte Party- und Versandkostenverwaltung.

## Features

- **Party Referenz**: Verknüpfung von Sales Orders mit Party-Datensätzen
- **Versandziel**: Separate Angabe des Versandziels (Customer)
- **Automatische Versandkostenberechnung**: Berechnung basierend auf Party und Versandziel
- **Versandkosten-Notizen**: Transparente Darstellung der Berechnungsgrundlage

## Installation

1. App zum Frappe Bench hinzufügen:
```bash
bench get-app https://github.com/your-repo/enjo_party.git
```

2. App auf der Site installieren:
```bash
bench --site your-site.local install-app enjo_party
```

3. Migration durchführen:
```bash
bench --site your-site.local migrate
```

## Custom Fields Setup

Falls die Custom Fields nicht automatisch erstellt werden, kann folgendes Skript in der Frappe Console ausgeführt werden:

```python
import frappe

# Custom Fields für Sales Order erstellen
custom_fields = [
    {
        'doctype': 'Custom Field',
        'name': 'Sales Order-custom_party_reference',
        'dt': 'Sales Order',
        'fieldname': 'custom_party_reference',
        'fieldtype': 'Link',
        'label': 'Party Referenz',
        'options': 'Party',
        'read_only': 1,
        'insert_after': 'po_no'
    },
    {
        'doctype': 'Custom Field',
        'name': 'Sales Order-custom_shipping_target',
        'dt': 'Sales Order',
        'fieldname': 'custom_shipping_target',
        'fieldtype': 'Link',
        'label': 'Versandziel',
        'options': 'Customer',
        'read_only': 1,
        'insert_after': 'custom_party_reference'
    },
    {
        'doctype': 'Custom Field',
        'name': 'Sales Order-custom_calculated_shipping_cost',
        'dt': 'Sales Order',
        'fieldname': 'custom_calculated_shipping_cost',
        'fieldtype': 'Currency',
        'label': 'Berechnete Versandkosten',
        'read_only': 1,
        'insert_after': 'custom_shipping_target'
    },
    {
        'doctype': 'Custom Field',
        'name': 'Sales Order-custom_shipping_note',
        'dt': 'Sales Order',
        'fieldname': 'custom_shipping_note',
        'fieldtype': 'Small Text',
        'label': 'Versandkosten Berechnung',
        'read_only': 1,
        'insert_after': 'custom_calculated_shipping_cost'
    }
]

for field_data in custom_fields:
    if not frappe.db.exists('Custom Field', {'dt': field_data['dt'], 'fieldname': field_data['fieldname']}):
        doc = frappe.get_doc(field_data)
        doc.insert()
        print(f'Custom Field {field_data["fieldname"]} erstellt')
    else:
        print(f'Custom Field {field_data["fieldname"]} existiert bereits')

frappe.db.commit()
print('Fertig!')
```

### Skript ausführen:

1. Frappe Console öffnen:
```bash
bench --site your-site.local console
```

2. Das obige Python-Skript einfügen und ausführen

## Verwendung

Nach der Installation sind in Sales Orders folgende neue Felder verfügbar:

- **Party Referenz**: Verknüpfung zu einem Party-Datensatz
- **Versandziel**: Auswahl des Versandkunden
- **Berechnete Versandkosten**: Automatisch berechnete Versandkosten
- **Versandkosten Berechnung**: Erklärung der Kostenberechnung

## Entwicklung

Für lokale Entwicklung:

```bash
bench get-app /path/to/local/enjo_party
bench --site development.localhost install-app enjo_party
bench --site development.localhost migrate
```

## Support

Bei Problemen oder Fragen, bitte ein Issue erstellen oder den Entwickler kontaktieren.
