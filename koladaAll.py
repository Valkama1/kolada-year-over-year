#!/usr/bin/env python3
import requests
import csv

# Global cache to store KPI metadata once it's fetched
kpi_metadata_cache = {}

def fetch_all_municipalities():
    """
    Fetch all municipalities from the Kolada API.
    Returns a list of municipality records.
    """
    url = "http://api.kolada.se/v2/municipality"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data.get("values", [])

def fetch_municipality_year_data(municipality_id, year, per_page=5000):
    """
    Fetch all KPI data for a given municipality and year.
    Follows pagination if necessary.
    """
    url = f"http://api.kolada.se/v2/data/municipality/{municipality_id}/year/{year}"
    params = {"per_page": per_page}
    data = []
    
    while url:
        print(f"Fetching data for municipality {municipality_id} year {year} from: {url}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        result = response.json()
        data.extend(result.get("values", []))
        # Follow pagination if there's a next_page URL
        url = result.get("next_page")
        params = None  # next_page URL already contains parameters
    return data

def parse_kpi_values(data):
    """
    Parse the list of records into a dictionary mapping KPI id to its value.
    Tries to use the overall value (gender 'T') when available.
    """
    kpi_values = {}
    for record in data:
        kpi_id = record.get("kpi")
        values_list = record.get("values", [])
        # Prefer overall value (gender 'T')
        found = False
        for val in values_list:
            if val.get("gender") == "T" and val.get("value") is not None:
                kpi_values[kpi_id] = val.get("value")
                found = True
                break
        # If not available, pick the first non-null value
        if not found:
            for val in values_list:
                if val.get("value") is not None:
                    kpi_values[kpi_id] = val.get("value")
                    break
    return kpi_values

def compute_percentage_change(v1, v2):
    """
    Compute percentage change from v1 to v2 using v1 as the base.
    Returns 0 if both are zero. Otherwise, if v1 is zero and v2 nonzero,
    returns None (undefined).
    """
    if v1 == 0:
        return 0 if v2 == 0 else None
    return ((v2 - v1) / abs(v1)) * 100

def get_kpi_metadata(kpi_id):
    """
    Fetch metadata for a given KPI id from the Kolada API.
    Uses a cache so that each KPI is looked up only once.
    Returns a dictionary with KPI details (title, description, etc.)
    extracted from the first element in the 'values' list.
    """
    if kpi_id in kpi_metadata_cache:
        return kpi_metadata_cache[kpi_id]

    url = f"http://api.kolada.se/v2/kpi/{kpi_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "values" in data and len(data["values"]) > 0:
            metadata = data["values"][0]
            kpi_metadata_cache[kpi_id] = metadata  # Cache the metadata
            return metadata
    else:
        print(f"Metadata for KPI {kpi_id} could not be fetched (status code: {response.status_code})")
    return None

def process_municipality(municipality, years):
    """
    For a given municipality and list of years:
      - Fetches KPI data for each year.
      - Combines the data by KPI id.
      - Computes percentage and numeric changes for each consecutive year.
      - Writes a CSV file (one per municipality) containing:
        KPI id, KPI Title, value per year, percentage change between each year, 
        numeric change between each year, and KPI description.
    """
    municipality_id = municipality.get("id")
    municipality_name = municipality.get("name", f"municipality_{municipality_id}")
    
    # Dictionary to store KPI data: { kpi_id: { year: value, ... } }
    municipality_kpis = {}
    
    for year in years:
        data_year = fetch_municipality_year_data(municipality_id, year)
        kpi_values = parse_kpi_values(data_year)
        for kpi, value in kpi_values.items():
            if kpi not in municipality_kpis:
                municipality_kpis[kpi] = {}
            municipality_kpis[kpi][year] = value
    
    # Build CSV rows
    rows = []
    for kpi, year_values in municipality_kpis.items():
        metadata = get_kpi_metadata(kpi)
        kpi_title = metadata.get("title") if metadata else f"KPI {kpi}"
        description = metadata.get("description", "No description available.") if metadata else "No description available."
        row = {
            "KPI": kpi,
            "Title": kpi_title,
            "Description": description
        }
        # Add values for each year
        for year in years:
            row[f"Value {year}"] = year_values.get(year, "")
        # Compute changes between consecutive years
        for i in range(len(years) - 1):
            y1 = years[i]
            y2 = years[i+1]
            v1 = year_values.get(y1)
            v2 = year_values.get(y2)
            if v1 is not None and v2 is not None:
                try:
                    v1_val = float(v1)
                    v2_val = float(v2)
                    pct_change = compute_percentage_change(v1_val, v2_val)
                    num_change = v2_val - v1_val
                    row[f"Change (%) {y1}-{y2}"] = f"{pct_change:.2f}" if pct_change is not None else "N/A"
                    row[f"Change (Number) {y1}-{y2}"] = num_change
                except (ValueError, TypeError):
                    row[f"Change (%) {y1}-{y2}"] = "N/A"
                    row[f"Change (Number) {y1}-{y2}"] = "N/A"
            else:
                row[f"Change (%) {y1}-{y2}"] = ""
                row[f"Change (Number) {y1}-{y2}"] = ""
        rows.append(row)
    
    # Define CSV columns dynamically:
    columns = ["KPI", "Title", "Description"]
    for year in years:
        columns.append(f"Value {year}")
    for i in range(len(years) - 1):
        y1 = years[i]
        y2 = years[i+1]
        columns.append(f"Change (%) {y1}-{y2}")
        columns.append(f"Change (Number) {y1}-{y2}")
    
    # Write CSV file for this municipality
    filename = f"{municipality_id}_{municipality_name.replace(' ', '_')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Written CSV for municipality {municipality_id} - {municipality_name}: {filename}")

if __name__ == '__main__':
    start_year_input = input("Enter the starting year (e.g., 2009): ").strip()
    end_year_input = input("Enter the ending year (e.g., 2012): ").strip()
    try:
        start_year = int(start_year_input)
        end_year = int(end_year_input)
    except ValueError:
        print("Invalid year input. Please enter integer values for years.")
        exit(1)
    
    if start_year > end_year:
        print("Starting year must be less than or equal to ending year.")
        exit(1)
    
    years = list(range(start_year, end_year + 1))
    print(f"Processing data for years: {years}")
    
    municipalities = fetch_all_municipalities()
    print(f"Found {len(municipalities)} municipalities.")
    
    for municipality in municipalities:
        process_municipality(municipality, years)
    
    print("All CSV files have been generated.")

