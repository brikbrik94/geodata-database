# Dokumentation: Emergency-Datenbank

Diese Dokumentation beschreibt die Struktur, den Importprozess und die Abfragemöglichkeiten der `emergency_db` (Schema: `emergency`).

---

## Tabellenübersicht

### 1. Notarzthubschrauber-Stützpunkte (`emergency.nah_stations`)
Speichert spezialisierte Daten für die Luftrettung (NAH). Besonders wichtig sind hier die dynamischen Betriebszeiten.

| Spalte | Typ | Beschreibung |
| :--- | :--- | :--- |
| `osm_id` | `TEXT` | Eindeutige ID aus OpenStreetMap (z. B. `node/123`). |
| `region` | `TEXT` | Einsatzregion (z. B. `Bayern`, `Österreich`). |
| `name` | `TEXT` | Voller Name des Stützpunktes. |
| `callsign` | `TEXT` | Funkrufname (z. B. "Christophorus 10"). |
| `op_type` | `TEXT` | Typ der Betriebszeit: `24/7`, `daylight` (Sonnenstand), `fixed` (feste Zeiten). |
| `months_active` | `INT[]` | Array der Monate (1-12), in denen der Stützpunkt aktiv ist (saisonale Betriebe). |
| `is_night_ready`| `BOOL` | Kennzeichnet, ob der Stützpunkt für Nachtflugbetrieb ausgestattet ist. |
| `geom` | `GEOMETRY` | Geografische Position (Point, SRID 4326). |

### 2. Rettungsdienst-Dienststellen (`emergency.stations`)
Zentrale Tabelle für bodengebundene Rettungsmittel (Rettungswachen, NEF-Stützpunkte, SEW-Standorte).

| Spalte | Typ | Beschreibung |
| :--- | :--- | :--- |
| `osm_id` | `TEXT` | Eindeutige ID (OSM-ID oder `Dateiname:ID` bei internen Quellen). |
| `has_doctor` | `TEXT` | `yes`, wenn ein Notarzt am Standort stationiert ist (NEF-Basis). |
| `has_transport`| `TEXT` | `yes`, wenn Krankentransportmittel vorhanden sind (SEW-Standort). |
| `organization` | `TEXT` | Betreiberorganisation (z. B. "Rotes Kreuz", "Samariterbund"). |
| `properties` | `JSONB` | Vollständiger Satz aller Original-Attribute aus der GeoJSON-Quelle. |

---

## Abfrage-Logik & PostGIS-Funktionen

### 1. Suche im Umkreis (Räumliche Abfrage)
Um die nächstgelegenen Stützpunkte zu einer Koordinate zu finden, nutzt man den `<->` Operator (Nearest Neighbor) oder `ST_DWithin` für einen festen Radius.

```sql
-- Die 5 nächsten Dienststellen zu einem Punkt (Linz)
SELECT name, organization, 
       ST_Distance(geom, ST_SetSRID(ST_Point(14.28, 48.30), 4326)::geography) / 1000 as dist_km
FROM emergency.stations
ORDER BY geom <-> ST_SetSRID(ST_Point(14.28, 48.30), 4326)
LIMIT 5;
```

### 2. Filtern nach Rettungstyp
Durch die Spalten `has_doctor` und `has_transport` können gezielt NEF oder SEW Standorte abgefragt werden.

```sql
-- Alle NEF-Standorte in Oberösterreich
SELECT name, city FROM emergency.stations 
WHERE has_doctor = 'yes' AND osm_id LIKE 'RD-OO%';
```

---

## Speziallogik: Betriebszeiten (NAH)

Die Verfügbarkeit von Hubschraubern ist oft an den Sonnenstand gebunden.

### Saisonale Filterung
Hubschrauber, die z. B. nur im Winter aktiv sind, werden über das Array `months_active` gefiltert.
```sql
-- Alle aktuell (diesen Monat) aktiven Hubschrauber
SELECT name, callsign FROM emergency.nah_stations 
WHERE extract(month from now()) = ANY(months_active);
```

### Sonnenstand-Berechnung (`daylight`)
Wenn `op_type = 'daylight'`, ist der Stützpunkt von Sonnenaufgang bis Sonnenuntergang aktiv. Dies kann im Backend (z. B. mit Python `suntime`) oder direkt in PostgreSQL berechnet werden, sofern die `pg_suncalc` Extension installiert ist:

```sql
-- Beispiel-Logik für daylight (Pseudocode / pg_suncalc)
SELECT name FROM emergency.nah_stations 
WHERE op_type = 'daylight' 
  AND now() BETWEEN sun_rise(geom, now()) AND sun_set(geom, now());
```

---

## Daten-Import & Synchronisierung
Die Daten werden über Python-Skripte aus dem `geojson` Submodul geladen:
1. `scripts/import_nah.py`: Importiert NAH-Daten inkl. komplexem Parsing der `opening_hours`.
2. `scripts/import_rd.py`: Importiert Dienststellen und stellt sicher, dass IDs über Regionen hinweg eindeutig bleiben.

Beide Skripte nutzen **Upsert-Logik** (`ON CONFLICT`), sodass bestehende Daten aktualisiert und neue hinzugefügt werden, ohne Dubletten zu erzeugen.
