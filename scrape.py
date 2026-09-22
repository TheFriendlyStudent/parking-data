import requests
import urllib3
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Suppress the warning that appears when you bypass SSL verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def scrape_utd_garages_to_csv(filename="utd_parking_data.csv"):
    url = "https://services.utdallas.edu/transit/garages/_code.php"
    
    print(f"Fetching raw table data from {url}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, verify=False)
    
    if response.status_code != 200:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table", class_="parking")
    
    if not tables:
        print("No tables found. Check if the network is blocking the request.")
        return

    # Check if file exists to determine if we need to write the header row
    file_exists = os.path.isfile(filename)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Open the CSV file in append mode ('a'). 
    # newline='' prevents blank lines between rows on Windows.
    with open(filename, mode="a", newline="", encoding="utf-8") as csv_file:
        fieldnames = ["Scrape Time", "Garage", "Last Checked", "Level", "Option", "Available Spaces"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        
        # Write headers only if the file is brand new or empty
        if not file_exists or os.path.getsize(filename) == 0:
            writer.writeheader()

        row_count = 0

        for table in tables:
            garage_id = table.get("id", "").upper()
            caption_elem = table.find("caption")
            garage_name = caption_elem.get_text(strip=True) if caption_elem else garage_id

            footer = table.find("tfoot")
            last_checked = "Unknown"
            if footer:
                time_p = footer.find("p", class_="centertight")
                if time_p:
                    last_checked = time_p.get_text(strip=True).replace("Last Checked ", "")

            tbody = table.find("tbody")
            if tbody:
                for row in tbody.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) == 3:
                        level = cols[0].get_text(strip=True)
                        option = " ".join(cols[1].get_text(strip=True).split())
                        
                        try:
                            available_spaces = int(cols[2].get_text(strip=True))
                        except ValueError:
                            available_spaces = 0

                        # Write a row to the CSV for every single level/option found
                        writer.writerow({
                            "Scrape Time": current_time,
                            "Garage": garage_name,
                            "Last Checked": last_checked,
                            "Level": level,
                            "Option": option,
                            "Available Spaces": available_spaces
                        })
                        row_count += 1

    print(f"Successfully appended {row_count} rows to {filename}")

if __name__ == "__main__":
    # You can change the filename here if you'd like it saved elsewhere
    scrape_utd_garages_to_csv("utd_parking_data.csv")