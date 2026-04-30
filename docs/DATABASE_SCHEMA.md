# Emergency Database Schema Documentation

This document describes the tables and query patterns for the `emergency_db` (schema `emergency`).

## Tables Overview

### 1. `emergency.nah_stations`
Stores data for Air Rescue Helicopters (Notarzthubschrauber).

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary Key |
| `osm_id` | TEXT | Unique Identifier (OSM format) |
| `region` | TEXT | Administrative region (e.g., Bayern, Österreich) |
| `name` | TEXT | Full name of the station |
| `callsign` | TEXT | Radio callsign |
| `short_name` | TEXT | Organization short name (e.g., ÖAMTC, DRF) |
| `icao` | TEXT | ICAO Code (if available) |
| `operator` | TEXT | Operating organization |
| `address` | JSONB | Structured address data |
| `geom` | GEOMETRY | Point location (SRID 4326) |
| `op_type` | TEXT | Operation type: `24/7`, `daylight`, `fixed` |
| `fixed_start` | TIME | Start time for `fixed` operation |
| `fixed_end` | TIME | End time for `fixed` operation |
| `months_active` | INT[] | List of months (1-12) the station is active |
| `is_night_ready` | BOOL | Flag for night-time operation capability |

### 2. `emergency.stations`
Stores data for ground-based rescue services (Ambulance stations, NEF bases, SEW).

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary Key |
| `osm_id` | TEXT | Unique ID (OSM id or `filename:id` prefix) |
| `name` | TEXT | Full name |
| `short_name` | TEXT | Short organization name |
| `alt_name` | TEXT | Alternative identifier |
| `type` | TEXT | Station type (mostly `ambulance_station`) |
| `organization` | TEXT | Operating organization |
| `has_doctor` | TEXT | `yes` if an emergency doctor is present (NEF) |
| `has_transport` | TEXT | `yes` if patient transport is available (SEW) |
| `description` | TEXT | Additional description |
| `city`, `postcode` | TEXT | Address components |
| `street`, `housenumber` | TEXT | Address components |
| `properties` | JSONB | Full metadata from GeoJSON source |
| `geom` | GEOMETRY | Point location (SRID 4326) |

---

## Example Queries

### Find all NEF stations (Doctor bases)
```sql
SELECT name, city, organization 
FROM emergency.stations 
WHERE has_doctor = 'yes';
```

### Find SEW stations in a specific city
```sql
SELECT name, street, housenumber 
FROM emergency.stations 
WHERE has_transport = 'yes' AND city = 'Linz';
```

### Filter active Helicopters for the current month
```sql
SELECT name, callsign, op_type 
FROM emergency.nah_stations 
WHERE extract(month from now()) = ANY(months_active);
```

### Search for stations near a coordinate (PostGIS)
```sql
SELECT name, ST_Distance(geom, ST_SetSRID(ST_Point(14.28, 48.30), 4326)::geography) / 1000 as dist_km
FROM emergency.stations
ORDER BY geom <-> ST_SetSRID(ST_Point(14.28, 48.30), 4326)
LIMIT 5;
```

## Import Process
Data is imported from the `geojson` submodule via:
- `scripts/import_nah.py` -> `emergency.nah_stations`
- `scripts/import_rd.py` -> `emergency.stations`
