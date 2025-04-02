#!/usr/bin/env python3
import requests

def fetch_municipality_year_data(municipality_id, year, per_page=5000):
    """
    Fetch all KPI data for a given municipality and year.
    Returns a list of records.
    """
    url = f"http://api.kolada.se/v2/data/municipality/{municipality_id}/year/{year}"
    params = {"per_page": per_page}
    data = []
    
    while url:
        print(f"Fetching data from: {url}")
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
    Parse the list of records into a dictionary mapping KPI id to a value.
    Tries to use the overall (gender 'T') value when available.
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
    If v1 is zero:
      - return 0 if v2 is also zero,
      - otherwise return None (indicating an undefined percentage change).
    """
    if v1 == 0:
        return 0 if v2 == 0 else None
    return ((v2 - v1) / abs(v1)) * 100

def compare_years(municipality_id, year1, year2, threshold_percent):
    """
    Compare KPI values for two years and return a list of tuples:
    (KPI id, value in year1, value in year2, percentage change)
    Only includes KPIs where the absolute percentage change is greater than zero
    and within the threshold.
    """
    data_year1 = fetch_municipality_year_data(municipality_id, year1)
    data_year2 = fetch_municipality_year_data(municipality_id, year2)
    
    kpi_year1 = parse_kpi_values(data_year1)
    kpi_year2 = parse_kpi_values(data_year2)
    
    common_kpis = set(kpi_year1.keys()) & set(kpi_year2.keys())
    small_changes = []
    
    for kpi in common_kpis:
        v1 = kpi_year1[kpi]
        v2 = kpi_year2[kpi]
        if v1 is None or v2 is None:
            continue
        change = compute_percentage_change(v1, v2)
        # Skip if percentage change is undefined (v1==0 and v2 != 0)
        if change is None:
            continue
        # Only include if change is non-zero and within the threshold.
        if abs(change) > 0 and abs(change) <= threshold_percent:
            small_changes.append((kpi, v1, v2, change))
    return small_changes

def get_kpi_metadata(kpi_id):
    """
    Fetch metadata for a given KPI id from the Kolada API.
    Returns a dictionary with KPI details (title, description, etc.) extracted
    from the first element in the 'values' list.
    """
    url = f"http://api.kolada.se/v2/kpi/{kpi_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "values" in data and len(data["values"]) > 0:
            return data["values"][0]
        else:
            return None
    else:
        print(f"Metadata for KPI {kpi_id} could not be fetched (status code: {response.status_code})")
        return None

if __name__ == '__main__':
    municipality_id = input("Enter municipality id (e.g., 1860): ").strip()
    year1 = input("Enter first year (e.g., 2009): ").strip()
    year2 = input("Enter second year (e.g., 2010): ").strip()
    threshold_input = input("Enter threshold percentage for 'small change' (default is 5): ").strip()
    
    try:
        threshold_percent = float(threshold_input) if threshold_input else 5.0
    except ValueError:
        threshold_percent = 5.0

    results = compare_years(municipality_id, year1, year2, threshold_percent)
    
    if not results:
        print(f"No KPIs found with a percentage change within ±{threshold_percent}% between {year1} and {year2}.")
    else:
        # Sort results by absolute percentage change (smallest change first)
        sorted_results = sorted(results, key=lambda x: abs(x[3]))
        print(f"\nKPIs with a percentage change within ±{threshold_percent}% between {year1} and {year2} (sorted by smallest change):\n")
        for kpi, val1, val2, change in sorted_results:
            metadata = get_kpi_metadata(kpi)
            if metadata:
                kpi_title = metadata.get("title", "Unknown KPI Title")
                description = metadata.get("description", "No description available.")
            else:
                kpi_title = "Unknown KPI Title"
                description = "No description available."
            print(f"KPI: {kpi} - {kpi_title}")
            print(f"  {year1}: {val1} | {year2}: {val2} | Change: {change:.2f}%\n")
            #print(f"  Description: {description}\n")

