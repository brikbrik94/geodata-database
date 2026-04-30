import json
import os
import psycopg2
from psycopg2.extras import execute_values

# Database connection details
DB_CONFIG = "dbname=emergency_db user=emergency_admin password=emergency_pass host=100.64.0.1"

def import_geojson_file(file_path):
    filename = os.path.basename(file_path)
    print(f"Processing {filename}...")
    with open(file_path, 'r') as f:
        data = json.load(f)

    records = []
    for feature in data['features']:
        props = feature['properties']
        geom = feature['geometry']
        
        # Ensure unique osm_id by prefixing with filename if it's a simple numeric ID
        raw_id = props.get('id') or feature.get('id')
        if not raw_id:
            continue
            
        osm_id = str(raw_id)
        if not osm_id.startswith(('node/', 'way/', 'relation/')):
            osm_id = f"{filename}:{osm_id}"
        
        name = props.get('name')
        short_name = props.get('short_name') or props.get('brand:short')
        alt_name = props.get('alt_name')
        type_val = props.get('emergency') or 'ambulance_station'
        organization = props.get('operator') or props.get('brand')
        
        has_doctor = props.get('ambulance_station:emergency_doctor') or 'no'
        has_transport = props.get('ambulance_station:patient_transport') or 'no'
        description = props.get('description')
        
        city = props.get('addr:city')
        postcode = props.get('addr:postcode')
        street = props.get('addr:street')
        housenumber = props.get('addr:housenumber')
        
        # Point coordinates [lon, lat]
        lon, lat = geom['coordinates']
        wkt_geom = f'SRID=4326;POINT({lon} {lat})'

        records.append((
            osm_id, name, short_name, alt_name, type_val, organization,
            has_doctor, has_transport, description,
            city, postcode, street, housenumber,
            json.dumps(props), wkt_geom
        ))

    conn = psycopg2.connect(DB_CONFIG)
    cur = conn.cursor()
    
    sql = """
        INSERT INTO emergency.stations (
            osm_id, name, short_name, alt_name, type, organization,
            has_doctor, has_transport, description,
            city, postcode, street, housenumber,
            properties, geom
        ) VALUES %s
        ON CONFLICT (osm_id) DO UPDATE SET
            name = EXCLUDED.name,
            short_name = EXCLUDED.short_name,
            alt_name = EXCLUDED.alt_name,
            type = EXCLUDED.type,
            organization = EXCLUDED.organization,
            has_doctor = EXCLUDED.has_doctor,
            has_transport = EXCLUDED.has_transport,
            description = EXCLUDED.description,
            city = EXCLUDED.city,
            postcode = EXCLUDED.postcode,
            street = EXCLUDED.street,
            housenumber = EXCLUDED.housenumber,
            properties = EXCLUDED.properties,
            geom = EXCLUDED.geom;
    """
    
    execute_values(cur, sql, records)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Imported {len(records)} stations.")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rd_dir = os.path.join(script_dir, "..", "data", "geojson", "RD-Dienststellen")
    
    if os.path.exists(rd_dir):
        for filename in os.listdir(rd_dir):
            if filename.endswith(".geojson"):
                import_geojson_file(os.path.join(rd_dir, filename))
    else:
        print(f"Directory not found: {rd_dir}")
