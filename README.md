# Enjo Party App

Eine umfassende Frappe/ERPNext-Erweiterung für die professionelle Verwaltung von ENJO Produktpräsentationen und automatisierte Auftragserstellung mit intelligenter Versandkostenberechnung und Provisionsmanagement.

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Kernfunktionen](#kernfunktionen)
- [Architektur & Technische Details](#architektur--technische-details)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
- [Verwendung](#verwendung)
- [API-Referenz](#api-referenz)
- [Hooks & Automatisierung](#hooks--automatisierung)
- [Benutzeroberfläche](#benutzeroberfläche)
- [Berichte & Übersichten](#berichte--übersichten)
- [Entwicklung](#entwicklung)
- [Troubleshooting](#troubleshooting)
- [Versionsverlauf](#versionsverlauf)

## Überblick

Die **Enjo Party App** ist eine spezialisierte Frappe-Anwendung, die für ENJO Direktvertrieb entwickelt wurde. Sie ermöglicht die komplette Abwicklung von ENJO Produktpräsentationen - von der Teilnehmerverwaltung über die Produktauswahl bis hin zur automatischen Auftragserstellung und Versandabwicklung.

### Hauptanwendungsfälle

- **Präsentations-Management**: Verwaltung von ENJO Produktpräsentationen mit bis zu 15 Teilnehmern
- **Provisionsberechnung**: Automatische Berechnung von Gastgeber-Gutscheinen basierend auf Umsätzen
- **Versandoptimierung**: Intelligente Gruppierung und Kostenaufteilung nach Versandzielen
- **Auftragserstellung**: Vollautomatische Generierung von Sales Orders und Invoices
- **Punktesystem**: Integriertes Belohnungssystem für Kunden

## Kernfunktionen

### Präsentations-Verwaltung

#### Teilnehmer-Management
- **Gastgeberin**: Zentrale Koordinatorin der ENJO Präsentation
- **Sales Partner**: Zugewiesene ENJO Beraterin für Provisionsabrechnung  
- **Bis zu 15 Gäste**: Flexible Teilnehmeranzahl mit individueller Produktauswahl
- **Dynamische Validierung**: Minimum 3 Gäste + Gastgeberin erforderlich

#### Intelligente Produktauswahl
```python
# Separate Produkttabellen für jeden Teilnehmer
produktauswahl_für_gastgeberin    # Sales Order Items für Gastgeberin
produktauswahl_für_gast_{1-15}    # Sales Order Items für Gäste 1-15
```

#### Status-Management
- **Gäste**: Teilnehmer werden erfasst
- **Produkte**: Produktauswahl läuft
- **Abgeschlossen**: Aufträge wurden erstellt und Präsentation ist eingereicht

### Automatische Provisionsberechnung

#### Gastgeber-Gutschein-System
```python
# Staffelung basierend auf Gesamtumsatz
gutschein_stufen = [
    (0, 0),      # Unter 350€: 0€ Gutschein
    (350, 30),   # Ab 350€: 30€ Gutschein  
    (600, 60),   # Ab 600€: 60€ Gutschein
    (850, 95),   # Ab 850€: 95€ Gutschein
    (1100, 130), # Ab 1100€: 130€ Gutschein
]
```

#### Gutschein-Anwendung
- **Automatische Preisreduktion**: Gutschein wird proportional auf aktionsberechtigte Artikel angewendet
- **Validierung**: Warnung bei nicht vollständiger Gutscheinnutzung
- **Transparenz**: Berechnungsgrundlage wird dokumentiert

### Intelligente Versandkostenberechnung

#### Versandartikel-System
```python
# 7 verschiedene Versandartikel für optimale Kostenaufteilung
shipping_items = {
    1: "shipping-7",      # 7€ für 1 Person
    2: "shipping-3.5",    # 3,5€ für 2 Personen  
    3: "shipping-2.33",   # 2,33€ für 3 Personen
    4: "shipping-1.75",   # 1,75€ für 4 Personen
    5: "shipping-1.4",    # 1,4€ für 5 Personen
    6: "shipping-1.17",   # 1,17€ für 6 Personen
    7: "shipping-1"       # 1€ für 7+ Personen
}
```

#### Versandlogik
- **200€ Freigrenze**: Versandkostenfrei ab 200€ Gesamtwert pro Versandziel
- **Gruppierung**: Aufträge werden nach Versandziel gruppiert
- **Faire Aufteilung**: 7€ Versandkosten werden gleichmäßig auf alle Bestellungen aufgeteilt

### Aktionssystem

#### Dynamische Aktionsartikel
- **Zwei Aktionsstufen**: Verschiedene Artikel je nach Bestellwert
- **Konfigurierbare Schwellwerte**: Über `Enjo Aktionseinstellungen` DocType
- **Automatische Anzeige**: Dialog erscheint bei berechtigten Bestellungen
- **0€ Preise**: Aktionsartikel werden mit 0€ in Aufträge übernommen

### Punktesystem

#### Automatische Punktevergabe
- **Bei Rechnungsstellung**: Punkte werden bei Einreichung vergeben
- **Bei Stornierung**: Punkte werden automatisch zurückgenommen  
- **Konfigurierbare Regeln**: Anpassbare Punktewerte pro Produktgruppe

## Architektur & Technische Details

### Projektstruktur

```
enjo_party/
├── enjo_party/                 # Hauptmodul
│   ├── doctype/               # Benutzerdefinierte DocTypes
│   │   ├── party/            # Haupt-DocType für Partys
│   │   ├── enjo_aktionseinstellungen/  # Aktions-Konfiguration
│   │   ├── enjo_punkte_transaktion/    # Punktesystem  
│   │   ├── kunde/            # Basis-Kundenverwaltung
│   │   ├── partnerin/        # Partnerinnen-Verwaltung
│   │   ├── produkt/          # Produkterweiterungen
│   │   └── ...              
│   ├── utils/                # Hilfsfunktionen
│   │   ├── sales_order_hooks.py      # Sales Order Automatisierung
│   │   ├── sales_invoice_hooks.py    # Rechnungs-Hooks
│   │   ├── address_hooks.py          # Adress-Management
│   │   └── shipping.py              # Versandkostenkonstanten
│   ├── server_scripts/       # Server-seitige Logik
│   │   └── enjo_punkte_vergabe.py   # Punktevergabe-System
│   ├── report/              # Berichte
│   │   └── enjo_punkte_uebersicht/  # Punkte-Report  
│   ├── page/                # Custom Pages
│   │   └── meine_provision_page/    # Provisions-Dashboard
│   └── print_format/        # Druckvorlagen
│       └── enjo_sales_invoice/      # Rechnungsformat
├── public/                  # Frontend-Assets
│   └── js/                 # JavaScript-Erweiterungen
│       ├── sales_order.js          # Aktionssystem für Aufträge
│       ├── sales_invoice.js        # Rechnungserweiterungen
│       └── customer_quick_entry.js # Schnelle Kundenerstellung
├── fixtures/               # Datenvorlagen
│   └── custom_field.json   # Custom Fields Definition
├── templates/              # Web-Templates
├── translations/           # Übersetzungen
│   └── de.csv             # Deutsche Übersetzungen
└── hooks.py               # Framework-Integration
```

### Wichtige DocTypes

#### Party (Haupt-DocType)
```json
{
  "autoname": "format:P{YY}{####}",
  "is_submittable": 1,
  "fields": [
    "party_name",           // Auto-generierter Name
    "party_date",          // Datum der Veranstaltung  
    "partnerin",           // Sales Partner (Beraterin)
    "gastgeberin",         // Customer (Gastgeberin)
    "gesamtumsatz",        // Berechneter Gesamtumsatz
    "gastgeber_gutschein_wert",  // Gutscheinwert
    "status",              // Gäste|Produkte|Abgeschlossen
    "kunden[]",            // Child Table: Party Kunde
    "produktauswahl_für_gast_{1-15}[]",    // Sales Order Items
    "produktauswahl_für_gastgeberin[]"     // Sales Order Items
  ]
}
```

## Installation

### Voraussetzungen

```bash
# Frappe Framework >= 14.0
# ERPNext >= 14.0  
# Python >= 3.8
# Node.js >= 14.0
```

### 1. App zum Bench hinzufügen

```bash
# Aus Git-Repository
bench get-app https://github.com/your-repo/enjo_party.git

# Lokaler Entwicklungspfad  
bench get-app /path/to/local/enjo_party
```

### 2. App installieren

```bash
# Auf spezifischer Site
bench --site your-site.local install-app enjo_party

# Oder auf allen Sites
bench install-app enjo_party
```

### 3. Datenbank-Migration

```bash
# Migration durchführen
bench --site your-site.local migrate

# Cache leeren
bench --site your-site.local clear-cache
```

### 4. Fixtures importieren

```bash
# Custom Fields werden automatisch importiert
# Alternativ manuell:
bench --site your-site.local import-doc fixtures/custom_field.json
```

## Konfiguration

### Custom Fields Setup

Die App erstellt automatisch Custom Fields für Sales Orders und Pick Lists:

#### Sales Order Erweiterungen
```python
custom_fields = [
    {
        'fieldname': 'custom_party_reference',
        'fieldtype': 'Link',
        'label': 'Party Referenz',
        'options': 'Party',
        'read_only': 1
    },
    {
        'fieldname': 'custom_shipping_target',
        'fieldtype': 'Link',
        'label': 'Versandziel',
        'options': 'Customer',
        'read_only': 1
    },
    {
        'fieldname': 'custom_calculated_shipping_cost',
        'fieldtype': 'Currency',
        'label': 'Berechnete Versandkosten',
        'read_only': 1
    },
    {
        'fieldname': 'custom_shipping_note',
        'fieldtype': 'Small Text',
        'label': 'Versandkosten Berechnung',
        'read_only': 1
    }
]
```

## Verwendung

### Präsentation erstellen und verwalten

#### 1. Neue Präsentation anlegen
```python
# Über UI: Neues Party-Dokument erstellen
# Oder via API:
party = frappe.new_doc("Party")
party.partnerin = "Partnerin-ID"     # ENJO Beraterin auswählen
party.gastgeberin = "Customer-ID"    # Gastgeberin auswählen  
party.party_date = "2025-02-15"     # Präsentationsdatum eintragen
party.save()
```

#### 2. Gäste hinzufügen
```python
# Minimum 3 Gäste erforderlich
for customer_id in ["CUST001", "CUST002", "CUST003"]:
    guest = party.append("kunden")
    guest.kunde = customer_id
    
party.save()  # Status wechselt zu "Gäste"
```

#### 3. ENJO Produkte auswählen
```python
# Für jeden Teilnehmer (Gastgeberin + Gäste)
# Gastgeberin
host_product = party.append("produktauswahl_für_gastgeberin")
host_product.item_code = "ENJO-001"
host_product.qty = 1
host_product.rate = 49.90

# Gast 1
guest_product = party.append("produktauswahl_für_gast_1")  
guest_product.item_code = "ENJO-002"
guest_product.qty = 2
guest_product.rate = 29.90

party.save()  # Status wechselt zu "Produkte"
                # Gesamtumsatz und Gutscheinwert werden berechnet
```

#### 4. Aufträge erstellen
```python
# Automatisch beim Submit
party.submit()  # Erstellt alle Sales Orders und Invoices

# Oder manuell über Button  
frappe.call({
    method: "enjo_party.enjo_party.doctype.party.party.create_invoices",
    args: {
        party: party.name,
        from_button: true
    }
})
```

## Entwicklung

Für lokale Entwicklung:

```bash
bench get-app /path/to/local/enjo_party
bench --site development.localhost install-app enjo_party
bench --site development.localhost migrate
```

## Support

**Entwickler:** Barowa
**E-Mail:** Service@Barowa.com
**Lizenz:** MIT License

Bei Problemen oder Fragen, bitte ein Issue erstellen oder den Entwickler kontaktieren.

---

*Diese App wurde speziell für ENJO Direktvertrieb entwickelt und bietet eine vollständige Lösung für Produktpräsentations-Management und automatisierte Auftragsprozesse.*
