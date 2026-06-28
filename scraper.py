import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from supabase import create_client
from urllib.parse import urljoin, urlparse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SOURCES = [
    {"name": "acmo", "url": "https://acmo.org/find-a-manager/management-firm-directory", "province": "ON"},
    {"name": "cci_toronto", "url": "https://ccitoronto.ca/directory", "province": "ON"},
    {"name": "cci_golden_horseshoe", "url": "https://www.cci-ghc.ca/directory", "province": "ON"},
    {"name": "cci_london", "url": "https://www.ccilondon.ca/directory", "province": "ON"},
    {"name": "cci_ottawa", "url": "https://cci-easternontario.ca/directory", "province": "ON"},
    {"name": "cci_windsor", "url": "https://cci-windsor.ca/directory", "province": "ON"},
    {"name": "cci_grand_river", "url": "https://cci-grc.ca/directory", "province": "ON"},
    {"name": "cci_huronia", "url": "https://www.ccihuronia.com/directory", "province": "ON"},
    {"name": "cci_bc", "url": "https://ccibcchapter.ca/directory", "province": "BC"},
    {"name": "cci_alberta_north", "url": "https://www.ccinorthalberta.com/directory", "province": "AB"},
    {"name": "cci_alberta_south", "url": "https://www.ccisouthalberta.com/directory", "province": "AB"},
    {"name": "cci_manitoba", "url": "https://cci-manitoba.ca/directory", "province": "MB"},
    {"name": "cci_saskatchewan_north", "url": "https://cci-northsaskatchewan.ca/directory", "province": "SK"},
    {"name": "cci_saskatchewan_south", "url": "https://cci-southsaskatchewan.ca/directory", "province": "SK"},
    {"name": "cci_nova_scotia", "url": "https://www.ccinovascotia.ca/directory", "province": "NS"},
    {"name": "cci_new_brunswick", "url": "https://ccinb.condogenie.com/directory", "province": "NB"},
    {"name": "cci_newfoundland", "url": "https://cci-newfoundland.ca/directory", "province": "NL"},
]

TEAM_KEYWORDS = ["team", "staff", "people", "about", "management", "our-team", "meet", "who-we-are"]
PORTFOLIO_KEYWORDS = ["properties", "portfolio", "buildings", "communities", "our-properties", "managed"]

def delay():
    time.sleep(random.uniform(3, 7))

def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

def extract_phone(text):
    phones = re.findall(r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]', text)
    return phones[0].strip() if phones else None

def extract_email(text):
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return emails[0].strip() if emails else None

def find_subpage(base_url, keywords):
    soup = get_soup(base_url)
    if not soup:
        return None
    links = soup.find_all("a", href=True)
    for link in links:
        href = link["href"].lower()
        text = link.get_text().lower()
        for kw in keywords:
            if kw in href or kw in text:
                full_url = urljoin(base_url, link["href"])
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    return full_url
    return None

def scrape_team_page(website):
    team_url = find_subpage(website, TEAM_KEYWORDS)
    if not team_url:
        return []
    delay()
    soup = get_soup(team_url)
    if not soup:
        return []
    managers = []
    cards = soup.find_all(["div", "article", "li"], class_=re.compile(r'team|staff|person|member|card', re.I))
    for card in cards:
        text = card.get_text(separator=" ", strip=True)
        name_tag = card.find(["h2", "h3", "h4", "strong", "b"])
        name = name_tag.get_text(strip=True) if name_tag else None
        if name and len(name.split()) >= 2:
            managers.append({
                "manager_name": name,
                "manager_email": extract_email(text),
                "manager_phone": extract_phone(text)
            })
    return managers

def scrape_portfolio_page(website):
    portfolio_url = find_subpage(website, PORTFOLIO_KEYWORDS)
    if not portfolio_url:
        return []
    delay()
    soup = get_soup(portfolio_url)
    if not soup:
        return []
    buildings = []
    items = soup.find_all(["div", "article", "li"], class_=re.compile(r'property|building|community|portfolio|card', re.I))
    for item in items:
        text = item.get_text(separator=" ", strip=True)
        name_tag = item.find(["h2", "h3", "h4", "strong"])
        name = name_tag.get_text(strip=True) if name_tag else None
        if name:
            buildings.append({
                "building_name": name,
                "building_address": text[:200] if text else None
            })
    return buildings[:50]

def scrape_company_details(website):
    soup = get_soup(website)
    if not soup:
        return None, None, None
    text = soup.get_text(separator=" ", strip=True)
    phone = extract_phone(text)
    email = extract_email(text)
    address = None
    address_tag = soup.find(["address", "p"], class_=re.compile(r'address|location|contact', re.I))
    if address_tag:
        address = address_tag.get_text(strip=True)[:200]
    return phone, email, address

def record_exists(company_name, source):
    result = supabase.table("property_managers").select("id").eq("company_name", company_name).eq("source", source).limit(1).execute()
    return len(result.data) > 0

def save_record(record):
    try:
        supabase.table("property_managers").insert(record).execute()
    except Exception as e:
        print(f"Error saving record: {e}")

def scrape_source(source):
    print(f"\n--- Scraping {source['name']} ---")
    soup = get_soup(source["url"])
    if not soup:
        print(f"Could not fetch {source['url']}")
        return
    links = soup.find_all("a", href=True)
    companies = []
    seen = set()
    for link in links:
        text = link.get_text(strip=True)
        href = link["href"]
        if text and len(text) > 3 and text not in seen:
            full_url = urljoin(source["url"], href)
            if urlparse(full_url).netloc != urlparse(source["url"]).netloc:
                companies.append({"name": text, "website": full_url})
                seen.add(text)
    print(f"Found {len(companies)} potential companies")
    for company in companies[:100]:
        name = company["name"]
        website = company["website"]
        if record_exists(name, source["name"]):
            print(f"Skipping {name} — already exists")
            continue
        print(f"Processing: {name} — {website}")
        delay()
        phone, email, address = scrape_company_details(website)
        delay()
        managers = scrape_team_page(website)
        delay()
        buildings = scrape_portfolio_page(website)
        if managers:
            for manager in managers:
                for building in buildings if buildings else [{}]:
                    record = {
                        "company_name": name,
                        "company_website": website,
                        "company_phone": phone,
                        "company_email": email,
                        "company_address": address,
                        "city": None,
                        "province": source["province"],
                        "manager_name": manager.get("manager_name"),
                        "manager_email": manager.get("manager_email"),
                        "manager_phone": manager.get("manager_phone"),
                        "building_name": building.get("building_name"),
                        "building_address": building.get("building_address"),
                        "source": source["name"]
                    }
                    save_record(record)
        else:
            record = {
                "company_name": name,
                "company_website": website,
                "company_phone": phone,
                "company_email": email,
                "company_address": address,
                "city": None,
                "province": source["province"],
                "manager_name": None,
                "manager_email": None,
                "manager_phone": None,
                "building_name": buildings[0]["building_name"] if buildings else None,
                "building_address": buildings[0]["building_address"] if buildings else None,
                "source": source["name"]
            }
            save_record(record)

if __name__ == "__main__":
    for source in SOURCES:
        scrape_source(source)
        delay()
