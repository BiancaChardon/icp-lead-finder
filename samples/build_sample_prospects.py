"""Write samples/sample-prospects.xlsx. Every person and company is fictional."""

from pathlib import Path

from openpyxl import Workbook

HEADERS = [
    "Company Name",
    "First Name",
    "Last Name",
    "Job Title",
    "Email Address",
    "Phone Number",
    "Website",
    "Industry",
    "Employees",
    "City",
    "State",
    "Country",
    "Data Source",
]

ROWS = [
    ["Harborline Health", "Avery", "Lang", "Chief Information Officer (CIO)", "avery.lang@harborline-health.example", "410-555-0101", "www.harborline-health.example", "Healthcare", 420, "Baltimore", "MD", "United States", "Sample spreadsheet (fictional)"],
    ["Cedarline Clinics", "Riley", "Quinn", "IT Director", "riley.quinn@cedarline-clinics.example", "410-555-0102", "www.cedarline-clinics.example", "Healthcare", 180, "Columbia", "MD", "United States", "Sample spreadsheet (fictional)"],
    ["Ironbridge Medical", "Casey", "Moore", "Chief Technology Officer (CTO)", "casey.moore@ironbridge-medical.example", "703-555-0103", "www.ironbridge-medical.example", "Healthcare", 1200, "Arlington", "VA", "United States", "Sample spreadsheet (fictional)"],
    ["Northgate Health, LLC", "Drew", "Shaw", "VP of Information Technology", "drew.shaw@northgate-health.example", "202-555-0104", "www.northgate-health.example", "Healthcare", 860, "Washington", "DC", "United States", "Sample spreadsheet (fictional)"],
    ["Oakridge Financial", "Quinn", "Ellis", "Chief Information Security Officer (CISO)", "quinn.ellis@oakridge-financial.example", "410-555-0105", "www.oakridge-financial.example", "Financial Services", 640, "Bethesda", "MD", "United States", "Sample spreadsheet (fictional)"],
    ["Pinecrest Manufacturing", "Skyler", "Brooks", "Director of Infrastructure", "skyler.brooks@pinecrest-manufacturing.example", "804-555-0106", "www.pinecrest-manufacturing.example", "Manufacturing", 2500, "Richmond", "VA", "United States", "Sample spreadsheet (fictional)"],
    ["Redwater Logistics", "Hayden", "Cole", "VP of Operations", "hayden.cole@redwater-logistics.example", "410-555-0107", "www.redwater-logistics.example", "Logistics", 540, "Rockville", "MD", "United States", "Sample spreadsheet (fictional)"],
    ["Silverbrook University", "Rowan", "Price", "Chief Information Officer (CIO)", "rowan.price@silverbrook-university.example", "919-555-0108", "www.silverbrook-university.example", "Education", 3100, "Raleigh", "NC", "United States", "Sample spreadsheet (fictional)"],
    ["Stonefield Systems", "Emerson", "Ward", "IT Manager", "emerson.ward@stonefield-systems.example", "512-555-0109", "www.stonefield-systems.example", "Software", 95, "Austin", "TX", "United States", "Sample spreadsheet (fictional)"],
    ["Westhaven Care Partners", "Parker", "Nguyen", "Head of Procurement", None, "410-555-0110", "www.westhaven-care.example", "Healthcare", 260, "Annapolis", "MD", "United States", "Sample spreadsheet (fictional)"],
    ["Brightwell Credit Union", "Logan", "Bennett", "Chief Financial Officer (CFO)", "logan.bennett@brightwell-credit.example", "703-555-0111", "www.brightwell-credit.example", "Financial Services", 410, "Reston", "VA", "United States", "Sample spreadsheet (fictional)"],
    ["Clearpath Retail Group", "Sage", "Peterson", "IT Director", "sage.peterson@clearpath-retail.example", "404-555-0112", "www.clearpath-retail.example", "Retail", 1750, "Atlanta", "GA", "United States", "Sample spreadsheet (fictional)"],
]


def main() -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Sample prospects"
    sheet.append(HEADERS)
    for row in ROWS:
        sheet.append(row)
    sheet.auto_filter.ref = sheet.dimensions
    destination = Path(__file__).with_name("sample-prospects.xlsx")
    book.save(destination)
    book.close()
    print(f"Wrote {destination} ({len(ROWS)} fictional prospects)")


if __name__ == "__main__":
    main()
