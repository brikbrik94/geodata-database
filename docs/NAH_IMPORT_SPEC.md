# NAH Stützpunkte Import Specification

## Overview
This document describes how air rescue stations (NAH - Notarzthubschrauber) from GeoJSON sources are imported into the `emergency_db` and how their operational hours are parsed for backend filtering.

## Database Structure
**Schema:** `emergency` (or `nah` if requested)
**Table:** `emergency.nah_stations`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `SERIAL PRIMARY KEY` | Internal ID |
| `osm_id` | `TEXT` | Original OSM ID (e.g., `way/123`) |
| `region` | `TEXT` | `Bayern` or `Österreich` |
| `name` | `TEXT` | Full name of the station |
| `callsign` | `TEXT` | Call sign (from `alt_name`) |
| `short_name`| `TEXT` | Short code (e.g., `C15`) |
| `icao` | `TEXT` | ICAO Code |
| `operator` | `TEXT` | Operator name |
| `address` | `JSONB` | Structured address (city, street, zip) |
| `geom` | `GEOMETRY(Point, 4326)` | Spatial location |
| **Operational Columns** | | |
| `raw_opening_hours` | `TEXT` | Original string from source |
| `op_type` | `TEXT` | `24/7`, `daylight`, `fixed` |
| `fixed_start` | `TIME` | For `fixed` type |
| `fixed_end` | `TIME` | For `fixed` type |
| `months_active` | `INTEGER[]` | Array of active months (1-12). Default `{1..12}` |
| `is_night_ready` | `BOOLEAN` | `true` if 24/7 or explicitly capable |

## Parsing Logic (`opening_hours`)

The import script uses a heuristic to convert OSM-style strings into structured data:

1.  **Seasonal Check**: 
    *   If months like `Jan`, `Dec`, `Jun-Sep` are found, `months_active` is populated.
    *   Example: `Jan-Apr; Dec` -> `{1,2,3,4,12}`.
2.  **Type Determination**:
    *   `24/7` -> `op_type = '24/7'`, `is_night_ready = true`.
    *   `sunrise-sunset` -> `op_type = 'daylight'`.
    *   `06:00-22:00` -> `op_type = 'fixed'`, `fixed_start = '06:00'`, `fixed_end = '22:00'`.
3.  **Defaults**:
    *   If `opening_hours` is empty (common in many Bayern nodes), it defaults to `daylight` (standard for air rescue).

## Backend Filtering Logic
To determine if a station is currently active, the backend should follow this logic:

```pseudo
function is_active(station, timestamp):
    # 1. Seasonal check
    if timestamp.month not in station.months_active:
        return false
        
    # 2. Daily time check
    if station.op_type == '24/7':
        return true
        
    if station.op_type == 'fixed':
        return station.fixed_start <= timestamp.time <= station.fixed_end
        
    if station.op_type == 'daylight':
        (sunrise, sunset) = calculate_sun(station.geom, timestamp.date)
        return sunrise <= timestamp.time <= sunset
```

## SQL View Example
A database view can simplify basic filtering:
```sql
CREATE VIEW emergency.active_nah_stations AS
SELECT * FROM emergency.nah_stations
WHERE extract(month from now()) = ANY(months_active);
-- Detailed time/daylight check usually done in backend or via PostGIS sun functions
```
