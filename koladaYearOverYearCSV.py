#!/usr/bin/env python3
import requests
import csv

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

def compare_years(municipality_id, year1, year2, threshold_percent, whole_threshold=0):
    """
    Compare KPI values for two years and return a list of tuples:
    (KPI id, value in year1, value in year2, percentage change, numeric change)
    
    KPIs are included if they satisfy one of the following:
      - The percentage change is non-zero and within the threshold, OR
      - Both year values are whole numbers, less than or equal to whole_threshold,
        and they differ (i.e. they change by a whole number).
    """
    data_year1 = fetch_municipality_year_data(municipality_id, year1)
    data_year2 = fetch_municipality_year_data(municipality_id, year2)
    
    kpi_year1 = parse_kpi_values(data_year1)
    kpi_year2 = parse_kpi_values(data_year2)
    
    common_kpis = set(kpi_year1.keys()) & set(kpi_year2.keys())
    results_dict = {}
    
    for kpi in common_kpis:
        v1 = kpi_year1[kpi]
        v2 = kpi_year2[kpi]
        if v1 is None or v2 is None:
            continue
        
        try:
            v1_val = float(v1)
            v2_val = float(v2)
        except (ValueError, TypeError):
            continue
        
        numeric_change = v2_val - v1_val
        percentage_change = compute_percentage_change(v1_val, v2_val)
        
        qualifies = False
        # Condition 1: KPI qualifies if the percentage change is defined, non-zero, and within the threshold.
        if percentage_change is not None and abs(percentage_change) > 0 and abs(percentage_change) <= threshold_percent:
            qualifies = True
        
        # Condition 2: If whole_threshold is specified, only include if both values are whole numbers ≤ whole_threshold and they differ.
        if whole_threshold > 0:
            if (v1_val.is_integer() and v2_val.is_integer() and 
                v1_val <= whole_threshold and v2_val <= whole_threshold and 
                v1_val != v2_val):
                qualifies = True
        
        if qualifies:
            # If percentage_change is undefined, we default it to 0 for output purposes.
            results_dict[kpi] = (kpi, v1, v2, percentage_change if percentage_change is not None else 0, numeric_change)
    
    return list(results_dict.values())

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

    whole_threshold_input = input("Enter whole number threshold to include (e.g., 2, leave blank or 0 to skip): ").strip()
    try:
        whole_threshold = int(whole_threshold_input) if whole_threshold_input else 0
    except ValueError:
        whole_threshold = 0

    results = compare_years(municipality_id, year1, year2, threshold_percent, whole_threshold)
    
    if not results:
        print(f"No KPIs found with a percentage change within ±{threshold_percent}% between {year1} and {year2} "
              f"or with both values as whole numbers ≤ {whole_threshold} that change by a whole number.")
    else:
        # Sort results by absolute percentage change (or numeric change if percentage is undefined)
        sorted_results = sorted(results, key=lambda x: abs(x[3]) if x[3] is not None else abs(x[4]))
        
        # Prepare data for CSV output
        rows = []
        for kpi, val1, val2, pct_change, num_change in sorted_results:
            metadata = get_kpi_metadata(kpi)
            if metadata:
                kpi_title = metadata.get("title", "Unknown KPI Title")
                description = metadata.get("description", "No description available.")
            else:
                kpi_title = "Unknown KPI Title"
                description = "No description available."
            rows.append({
                "KPI": kpi,
                "Title": kpi_title,
                f"Value {year1}": val1,
                f"Value {year2}": val2,
                "Change (%)": f"{pct_change:.2f}" if pct_change is not None else "N/A",
                "Change (Number)": num_change
                #"Description": description
            })
        
        filename = "kpi_comparison.csv"
        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["KPI", "Title", f"Value {year1}", f"Value {year2}", "Change (%)", "Change (Number)", "Description"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"Results written to {filename}")

