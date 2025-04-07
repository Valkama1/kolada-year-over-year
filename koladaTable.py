#!/usr/bin/env python3
import requests
import csv

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
        print(f"Fetching data for municipality {municipality_id} for year {year} from: {url}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        result = response.json()
        data.extend(result.get("values", []))
        url = result.get("next_page")
        params = None  # next_page URL already contains parameters
    return data

def parse_kpi_values(data):
    """
    Parse the list of records into a dictionary mapping KPI id to its value.
    Prefers the overall (gender 'T') value when available.
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
        if not found:
            for val in values_list:
                if val.get("value") is not None:
                    kpi_values[kpi_id] = val.get("value")
                    break
    return kpi_values

def count_changes_by_one(municipality_id, year1, year2):
    """
    Fetch KPI data for two years for a given municipality,
    and return the count of KPIs for which the numeric change (v2 - v1) is exactly 1 or -1.
    """
    data_year1 = fetch_municipality_year_data(municipality_id, year1)
    data_year2 = fetch_municipality_year_data(municipality_id, year2)
    
    kpi_year1 = parse_kpi_values(data_year1)
    kpi_year2 = parse_kpi_values(data_year2)
    
    common_kpis = set(kpi_year1.keys()) & set(kpi_year2.keys())
    count = 0
    for kpi in common_kpis:
        try:
            v1 = float(kpi_year1[kpi])
            v2 = float(kpi_year2[kpi])
        except (ValueError, TypeError):
            continue
        if abs(v2 - v1) == 1:
            count += 1
    return count

def get_population(municipality_id, year):
    """
    Retrieve the population for a municipality by looking up KPI 'N01951'
    for the given year. If not found, return "N/A".
    """
    data = fetch_municipality_year_data(municipality_id, year)
    kpi_values = parse_kpi_values(data)
    return kpi_values.get("N01951", "N/A")

def main():
    year1 = input("Enter first year (e.g., 2009): ").strip()
    year2 = input("Enter second year (e.g., 2010): ").strip()
    
    try:
        y1 = int(year1)
        y2 = int(year2)
    except ValueError:
        print("Invalid year input. Please enter integer values for years.")
        return

    municipalities = fetch_all_municipalities()
    print(f"Found {len(municipalities)} municipalities.")

    rows = []
    for municipality in municipalities:
        m_id = municipality.get("id")
        m_name = municipality.get("name", f"Municipality {m_id}")
        
        change_count = count_changes_by_one(m_id, y1, y2)
        # Retrieve population using KPI "N01951" for the second year
        population = get_population(m_id, y2)
        
        rows.append({
            "Municipality ID": m_id,
            "Municipality Name": m_name,
            "KPIs changed by 1": change_count,
            "Population": population
        })

    filename = "municipalities_changes.csv"
    fieldnames = ["Municipality ID", "Municipality Name", "KPIs changed by 1", "Population"]
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Results written to {filename}")

if __name__ == '__main__':
    main()

