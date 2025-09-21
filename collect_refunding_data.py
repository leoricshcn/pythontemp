import argparse
import csv
import io
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import pdfplumber
import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://home.treasury.gov"
RECOMMENDED_TABLES_URL = (
    "https://home.treasury.gov/policy-issues/financing-the-government/"
    "quarterly-refunding/quarterly-refunding-archives/tbac-recommended-financing-tables-by-calendar-year"
)
OFFICIAL_REMARKS_URL = (
    "https://home.treasury.gov/policy-issues/financing-the-government/"
    "quarterly-refunding/quarterly-refunding-archives/official-remarks-on-quarterly-refunding-by-calendar-year"
)
DEFAULT_MAX_QUARTERS = 23


def ordinal_to_int(text: str) -> Optional[int]:
    match = re.search(r"(\d+)(?:st|nd|rd|th)", text)
    return int(match.group(1)) if match else None


def quarter_key(year: int, quarter: int) -> Tuple[int, int]:
    return year, quarter


def format_quarter(year: int, quarter: int) -> str:
    return f"Q{quarter} {year}"


def absolute_url(href: str) -> str:
    return href if href.startswith("http") else f"{BASE_URL}{href}"


def extract_quarter_links(page_url: str) -> Dict[Tuple[int, int], str]:
    response = requests.get(page_url, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    tables = soup.find_all("table", attrs={"aria-label": re.compile(r"Quarter", re.I)})
    if not tables:
        raise RuntimeError("Could not locate the quarter link table on the page.")
    links: Dict[Tuple[int, int], str] = {}
    for table in tables:
        table_links = _parse_quarter_link_table(table)
        for key, url in table_links.items():
            links[key] = url
    return links


def extract_official_links() -> Dict[Tuple[int, int], str]:
    return extract_quarter_links(OFFICIAL_REMARKS_URL)


def extract_recommended_links() -> Dict[Tuple[int, int], str]:
    return extract_quarter_links(RECOMMENDED_TABLES_URL)


def _quarter_from_label(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"Q([1-4])\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    value = ordinal_to_int(text)
    if value is not None and 1 <= value <= 4:
        return value
    return None


def _determine_quarter_mapping(table: Tag) -> List[Optional[int]]:
    quarters: List[Optional[int]] = []
    candidate_rows: List[Tag] = []
    if table.find("thead"):
        candidate_rows.extend(table.find("thead").find_all("tr"))
    if table.find("tbody"):
        candidate_rows.extend(table.find("tbody").find_all("tr"))
    else:
        candidate_rows.extend(table.find_all("tr"))
    for row in candidate_rows:
        extracted: List[Optional[int]] = []
        for cell in row.find_all(["th", "td"]):
            extracted.append(_quarter_from_label(cell.get_text(" ", strip=True)))
        extracted = [value for value in extracted if value is not None]
        if extracted:
            quarters.extend(extracted)
            break
    return quarters


def _parse_quarter_link_table(table: Tag) -> Dict[Tuple[int, int], str]:
    quarter_mapping = _determine_quarter_mapping(table)
    rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
    links: Dict[Tuple[int, int], str] = {}
    current_year: Optional[int] = None
    is_calendar_table = "calendar quarter" in (table.get("aria-label") or "").lower()
    for row in rows:
        header_cells = row.find_all("th")
        for cell in header_cells:
            year_match = re.search(r"(19|20)\d{2}", cell.get_text())
            if year_match:
                current_year = int(year_match.group(0))
                break
        if current_year is None:
            continue
        data_cells = row.find_all("td")
        if not data_cells:
            data_cells = [cell for cell in header_cells if cell.find("a")]
        if not data_cells:
            continue
        for idx, cell in enumerate(data_cells):
            if idx >= len(quarter_mapping):
                continue
            quarter = quarter_mapping[idx]
            if quarter is None:
                continue
            anchors = [a for a in cell.find_all("a") if a.has_attr("href")]
            if not anchors:
                continue
            if is_calendar_table:
                for anchor in anchors:
                    anchor_quarter = _quarter_from_label(anchor.get("aria-label") or anchor.get_text(strip=True))
                    if anchor_quarter is None:
                        continue
                    target_year = current_year
                    if anchor_quarter < quarter:
                        target_year += 1
                    links[quarter_key(target_year, anchor_quarter)] = absolute_url(anchor["href"])
            else:
                selected_anchor = None
                for anchor in anchors:
                    anchor_quarter = _quarter_from_label(anchor.get("aria-label") or anchor.get_text(strip=True))
                    if anchor_quarter == quarter:
                        selected_anchor = anchor
                        break
                if not selected_anchor and len(anchors) == 1:
                    selected_anchor = anchors[0]
                if not selected_anchor:
                    continue
                links[quarter_key(current_year, quarter)] = absolute_url(selected_anchor["href"])
    return links


def parse_maturity(security: str) -> Tuple[Optional[float], str]:
    maturity_match = re.search(r"(\d+)(?:\s*-?\s*)(Year|Month|Week|Day)", security, re.IGNORECASE)
    if maturity_match:
        maturity = float(maturity_match.group(1))
        unit_text = maturity_match.group(2).upper()
        if "YEAR" in unit_text:
            unit = "YEARS"
        elif "MONTH" in unit_text:
            unit = "MONTHS"
        elif "WEEK" in unit_text:
            unit = "WEEKS"
        else:
            unit = "DAYS"
        return maturity, unit
    return None, ""


def categorize_security(security: str) -> str:
    s_lower = security.lower()
    if "bill" in s_lower:
        return "BILL"
    if "tips" in s_lower:
        return "TIPS"
    if "frn" in s_lower:
        return "FRN"
    if "bond" in s_lower:
        return "BOND"
    if "note" in s_lower:
        return "NOTE"
    if "savings" in s_lower:
        return "SAVINGS"
    return "OTHER"


def parse_recommended_pdf(pdf_bytes: bytes, quarter: int, year: int, announcement_date: str) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = list(pdf.pages)
        matrix_entries = _parse_matrix_recommended_pages(
            pages, format_quarter(year, quarter), announcement_date
        )
        if matrix_entries:
            results.extend(matrix_entries)
            return results
        text = "\n".join(page.extract_text(layout=True) or "" for page in pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pattern = re.compile(
        r"^(?P<security>[A-Za-z0-9/\-\(\)\s]+?)\s+"
        r"(?P<date>\d{1,2}/\d{1,2})\s+"
        r"(?P<offered>\d+\.\d{2})\s+"
        r"(?P<maturing>\d+\.\d{2})"
        r"(?:\s+(?P<new_money>\d+\.\d{2}))?"
        r"(?:\s+(?P<change>\d+\.\d{2}))?"
        r"$"
    )
    quarter_label = format_quarter(year, quarter)
    for line in lines:
        if line.lower().startswith("net bills issuance"):
            amount = float(line.split()[-1])
            results.append(
                {
                    "Quarter_year": quarter_label,
                    "Date": announcement_date,
                    "Security_type": "BILL",
                    "Maturity": "",
                    "Units": "",
                    "Auction_month": "",
                    "Auction_date": "",
                    "Offered_amount": amount,
                    "Data_type": "RECOMMENDATION_FOR_THIS_REFUNDING",
                    "Notes": "Net bills issuance for the quarter (recommended table)",
                }
            )
            continue
        match = pattern.match(line)
        if not match:
            continue
        data = match.groupdict()
        security = data["security"].strip()
        security_clean = security.replace("(r)", "").strip()
        maturity_value, unit = parse_maturity(security_clean)
        offered_amount = float(data["offered"])
        month, day = map(int, data["date"].split("/"))
        year_for_date = year
        auction_date = datetime(year_for_date, month, day)
        entry = {
            "Quarter_year": quarter_label,
            "Date": announcement_date,
            "Security_type": categorize_security(security_clean),
            "Maturity": maturity_value if maturity_value is not None else "",
            "Units": unit,
            "Auction_month": auction_date.strftime("%Y-%m"),
            "Auction_date": auction_date.strftime("%Y-%m-%d"),
            "Offered_amount": offered_amount,
            "Data_type": "RECOMMENDATION_FOR_THIS_REFUNDING",
            "Notes": "Reopening" if "(r)" in security else "Recommended financing schedule",
        }
        results.append(entry)
    return results


def _parse_matrix_recommended_pages(
    pages: List[pdfplumber.page.Page], quarter_label: str, announcement_date: str
) -> List[Dict[str, object]]:
    column_map = {
        5: ("2-Year Note", "NOTE", 2.0),
        8: ("3-Year Note", "NOTE", 3.0),
        11: ("5-Year Note", "NOTE", 5.0),
        14: ("7-Year Note", "NOTE", 7.0),
        17: ("10-Year Note", "NOTE", 10.0),
        20: ("20-Year Bond", "BOND", 20.0),
        23: ("30-Year Bond", "BOND", 30.0),
        26: ("5-Year TIPS", "TIPS", 5.0),
        29: ("10-Year TIPS", "TIPS", 10.0),
        32: ("30-Year TIPS", "TIPS", 30.0),
        35: ("2-Year FRN", "FRN", 2.0),
    }
    entries: List[Dict[str, object]] = []
    section: Optional[str] = None
    for page in pages:
        for table in page.extract_tables() or []:
            for raw_row in table:
                row = [cell.strip() if cell else "" for cell in raw_row]
                if not any(row):
                    continue
                joined = " ".join(row)
                if "Recommendations" in joined and "Refunding" in joined:
                    section = "RECOMMENDATION_FOR_THIS_REFUNDING"
                    continue
                if "Provisional" in joined and "Next Refunding" in joined:
                    section = "INDICATIONS_FOR_NEXT_REFUNDING"
                    continue
                if "Historical" in joined and "Reference" in joined:
                    section = "HISTORICAL_REFERENCE"
                    continue
                month = next(
                    (value for value in row if value and re.match(r"[A-Za-z]{3}-\d{2}$", value)),
                    None,
                )
                if not month or section != "RECOMMENDATION_FOR_THIS_REFUNDING":
                    continue
                month_date = datetime.strptime(month, "%b-%y")
                auction_month = month_date.strftime("%Y-%m")
                for idx, (name, security_type, maturity) in column_map.items():
                    if idx >= len(row):
                        continue
                    value = row[idx]
                    if not value or not re.match(r"^\d+(?:\.\d+)?$", value):
                        continue
                    amount = float(value)
                    entries.append(
                        {
                            "Quarter_year": quarter_label,
                            "Date": announcement_date,
                            "Security_type": security_type,
                            "Maturity": maturity,
                            "Units": "YEARS",
                            "Auction_month": auction_month,
                            "Auction_date": "",
                            "Offered_amount": amount,
                            "Data_type": "RECOMMENDATION_FOR_THIS_REFUNDING",
                            "Notes": "TBAC recommended financing table (matrix format)",
                        }
                    )
    return entries


def parse_official_article(article_html: str, year: int, quarter: int) -> Tuple[str, List[Dict[str, object]]]:
    soup = BeautifulSoup(article_html, "lxml")
    date_element = soup.select_one("div.field--name-field-news-publication-date time")
    if not date_element or not date_element.has_attr("datetime"):
        raise RuntimeError("Announcement date not found in official remarks article.")
    announcement_date = datetime.fromisoformat(date_element["datetime"].replace("Z", "+00:00")).date()
    quarter_label = format_quarter(year, quarter)

    table = soup.select_one("div.field--name-field-news-body table")
    table_entries: List[Dict[str, object]] = []
    if table and table.find("thead") and table.find("tbody"):
        headers = [cell.get_text(strip=True) for cell in table.find("thead").find_all("th")][1:]
        for row in table.find("tbody").find_all("tr"):
            month_header = row.find("th")
            if not month_header:
                continue
            month_label = month_header.get_text(strip=True)
            month_text = month_label.replace("\u00a0", " ")
            try:
                auction_month_date = datetime.strptime(month_text, "%b-%y")
            except ValueError:
                continue
            auction_month = auction_month_date.strftime("%Y-%m")
            is_projection_row = bool(month_header.find("strong"))
            for header, cell in zip(headers, row.find_all("td")):
                cell_text = cell.get_text(strip=True)
                if not cell_text:
                    continue
                try:
                    amount = float(cell_text)
                except ValueError:
                    continue
                is_projection = is_projection_row or bool(cell.find("strong"))
                maturity_value, unit = parse_maturity(header)
                security_type = categorize_security(header)
                if security_type == "OTHER" and "year" in header.lower():
                    if maturity_value is not None and maturity_value >= 20:
                        security_type = "BOND"
                    else:
                        security_type = "NOTE"
                note = (
                    "Projected auction size from official remarks table"
                    if is_projection
                    else "Actual auction size from prior quarter"
                )
                table_entries.append(
                    {
                        "Quarter_year": quarter_label,
                        "Date": announcement_date.strftime("%Y-%m-%d"),
                        "Security_type": security_type,
                        "Maturity": maturity_value if maturity_value is not None else "",
                        "Units": unit,
                        "Auction_month": auction_month,
                        "Auction_date": "",
                        "Offered_amount": amount,
                        "Data_type": "INDICATIONS_FOR_NEXT_REFUNDING"
                        if is_projection
                        else "HISTORICAL_REFERENCE",
                        "Notes": note,
                    }
                )
    return announcement_date.strftime("%Y-%m-%d"), table_entries


def collect_data(max_quarters: int = DEFAULT_MAX_QUARTERS) -> List[Dict[str, object]]:
    official_links = extract_official_links()
    recommended_links = extract_recommended_links()
    available_quarters = sorted(
        set(official_links.keys()) & set(recommended_links.keys()),
        reverse=True,
    )
    selected_quarters = available_quarters[:max_quarters]
    session = requests.Session()
    all_entries: List[Dict[str, object]] = []
    for year, quarter in selected_quarters:
        quarter_label = format_quarter(year, quarter)
        print(f"Fetching data for {quarter_label}...")
        official_url = official_links[(year, quarter)]
        recommended_url = recommended_links[(year, quarter)]
        official_resp = session.get(official_url, timeout=60)
        official_resp.raise_for_status()
        announcement_date, table_entries = parse_official_article(official_resp.text, year, quarter)
        all_entries.extend(table_entries)

        recommended_resp = session.get(recommended_url, timeout=60)
        recommended_resp.raise_for_status()
        pdf_entries = parse_recommended_pdf(recommended_resp.content, quarter, year, announcement_date)
        all_entries.extend(pdf_entries)
    return all_entries


def write_csv(entries: Iterable[Dict[str, object]], path: str) -> None:
    fieldnames = [
        "Quarter_year",
        "Date",
        "Security_type",
        "Maturity",
        "Units",
        "Auction_month",
        "Auction_date",
        "Offered_amount",
        "Data_type",
        "Notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Treasury refunding data")
    parser.add_argument(
        "--max-quarters",
        type=int,
        default=DEFAULT_MAX_QUARTERS,
        help=(
            "Number of most recent quarters to retrieve that have both official remarks "
            "and TBAC recommended tables"
        ),
    )
    parser.add_argument(
        "--output",
        default="refunding_data.csv",
        help="Destination CSV file path",
    )
    args = parser.parse_args()

    entries = collect_data(max_quarters=args.max_quarters)
    write_csv(entries, args.output)
    print(f"Wrote {len(entries)} rows to {args.output}")


if __name__ == "__main__":
    main()
