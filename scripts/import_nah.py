import json
import re
import psycopg2
from psycopg2.extras import execute_values
import os

# Database connection details (assuming standard from project)
DB_CONFIG = "dbname=emergency_db user=emergency_admin password=emergency_pass host=100.64.0.1"

MONTHS_MAP = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

def parse_opening_hours(oh_string):
    """
    Parses OSM opening_hours string into structured data.
    Returns: (op_type, fixed_start, fixed_end, months_active, is_night_ready)
    """
    if not oh_string:
        # Default for Air Rescue if missing
        return 'daylight', None, None, list(range(1, 13)), False

    oh_string = oh_string.lower()
    op_type = 'daylight'
    fixed_start = None
    fixed_end = None
    months_active = list(range(1, 13))
    is_night_ready = False

    # 1. Check for 24/7
    if '24/7' in oh_string:
        return '24/7', None, None, list(range(1, 13)), True

    # 2. Check for fixed times (e.g., 06:00-22:00)
    time_match = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2})', oh_string)
    if time_match:
        op_type = 'fixed'
        fixed_start = time_match.group(1)
        fixed_end = time_match.group(2)
        # If it spans late night, might be night ready
        # Simplified: if it ends after 22:00 or is 24h
        if int(fixed_end[:2]) >= 22 or int(fixed_end[:2]) < 4:
            is_night_ready = True

    # 3. Check for sunrise-sunset
    if 'sunrise-sunset' in oh_string:
        op_type = 'daylight'

    # 4. Check for seasons (e.g. Jan-Apr)
    # This is a bit complex for a regex, we look for month names
    found_months = []
    # Pattern for "Jan-Apr"
    range_matches = re.finditer(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)-(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', oh_string)
    for rm in range_matches:
        start_m = MONTHS_MAP[rm.group(1).capitalize()]
        end_m = MONTHS_MAP[rm.group(2).capitalize()]
        if start_m <= end_m:
            found_months.extend(range(start_m, end_m + 1))
        else: # Over year wrap (Dec-Apr)
            found_months.extend(range(start_m, 13))
            found_months.extend(range(1, end_m + 1))
            
    # Single months (e.g. Dec)
    single_matches = re.finditer(r'(?<!-)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?!-)', oh_string)
    for sm in single_matches:
        found_months.append(MONTHS_MAP[sm.group(1).capitalize()])

    if found_months:
        months_active = sorted(list(set(found_months)))

    return op_type, fixed_start, fixed_end, months_active, is_night_ready

def import_geojson(file_path, region):
    print(f"Processing {file_path} for region {region}...")
    with open(file_path, 'r') as f:
        data = json.load(f)

    records = []
    for feature in data['features']:
        props = feature['properties']
        geom = feature['geometry']
        
        # Extract basic fields
        osm_id = props.get('id')
        name = props.get('name')
        callsign = props.get('alt_name') or props.get('description')
        short_name = props.get('short_name')
        icao = props.get('icao')
        operator = props.get('operator')
        
        # Extract address
        address = {
            'city': props.get('addr:city'),
            'street': props.get('addr:street'),
            'housenumber': props.get('addr:housenumber'),
            'postcode': props.get('addr:postcode')
        }
        
        # Parse opening hours
        raw_oh = props.get('opening_hours')
        op_type, fixed_start, fixed_end, months_active, is_night_ready = parse_opening_hours(raw_oh)
        
        # Point coordinates [lon, lat]
        lon, lat = geom['coordinates']
        wkt_geom = f'SRID=4326;POINT({lon} {lat})'

        records.append((
            osm_id, region, name, callsign, short_name, icao, operator,
            json.dumps(address), wkt_geom,
            raw_oh, op_type, fixed_start, fixed_end, months_active, is_night_ready
        ))

    # DB Operations
    conn = psycopg2.connect(DB_CONFIG)
    cur = conn.cursor()
    
    # Create Table if not exists
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS emergency;
        CREATE TABLE IF NOT EXISTS emergency.nah_stations (
            id SERIAL PRIMARY KEY,
            osm_id TEXT UNIQUE,
            region TEXT,
            name TEXT,
            callsign TEXT,
            short_name TEXT,
            icao TEXT,
            operator TEXT,
            address JSONB,
            geom GEOMETRY(Point, 4326),
            raw_opening_hours TEXT,
            op_type TEXT,
            fixed_start TIME,
            fixed_end TIME,
            months_active INTEGER[],
            is_night_ready BOOLEAN
        );
        CREATE INDEX IF NOT EXISTS nah_stations_geom_idx ON emergency.nah_stations USING GIST (geom);
    """)
    
    # Upsert data
    sql = """
        INSERT INTO emergency.nah_stations (
            osm_id, region, name, callsign, short_name, icao, operator,
            address, geom,
            raw_opening_hours, op_type, fixed_start, fixed_end, months_active, is_night_ready
        ) VALUES %s
        ON CONFLICT (osm_id) DO UPDATE SET
            region = EXCLUDED.region,
            name = EXCLUDED.name,
            callsign = EXCLUDED.callsign,
            short_name = EXCLUDED.short_name,
            icao = EXCLUDED.icao,
            operator = EXCLUDED.operator,
            address = EXCLUDED.address,
            geom = EXCLUDED.geom,
            raw_opening_hours = EXCLUDED.raw_opening_hours,
            op_type = EXCLUDED.op_type,
            fixed_start = EXCLUDED.fixed_start,
            fixed_end = EXCLUDED.fixed_end,
            months_active = EXCLUDED.months_active,
            is_night_ready = EXCLUDED.is_night_ready;
    """
    
    execute_values(cur, sql, records)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Imported {len(records)} stations.")

if __name__ == "__main__":
    # Define files to import
    base_path = "/root/git/geojson/NAH-Stützpunkte/"
    
    # Importing Bavaria
    bayern_file = os.path.join(base_path, "NAH-Bayern.geojson")
    if os.path.exists(bayern_file):
        import_geojson(bayern_file, "Bayern")
    
    # Importing Austria (Winter as baseline, can be merged or updated)
    at_file = os.path.join(base_path, "NAH-Österreich-Winter.geojson")
    if os.path.exists(at_file):
        import_geojson(at_file, "Österreich")
