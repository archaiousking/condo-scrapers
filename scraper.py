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

# Exact URLs confirmed working
SOURCES = [
    {"name": "acmo", "url": "https://acmo.org/acmo-2000-certification/corporate-companies", "province": "ON"},
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

TEAM_KEYWORDS = ["team", "staff", "people", "our-team", "meet-us", "who-we-are", "about-us"]
PORTFOLIO_KEYWORDS = ["properties", "portfolio", "buildings", "communities", "our-properties", "managed-properties"]

ACMO_DOMAIN = "acmo.org"
CCI_DOMAINS = [
    "ccitoronto.ca", "cci-ghc.ca", "ccilondon.ca", "cci-easternontario.ca",
    "cci-windsor.ca", "cci-grc.ca", "ccihuronia.com", "ccibcchapter.ca",
    "ccinorthalberta.com", "ccisouthalberta.com", "cci-manitoba.ca",
    "cci-northsaskatchewan.ca", "cci-southsaskatchewan.ca", "ccinovascotia.ca",
    "condogenie.com", "cci-newfoundland.ca", "cci.ca"
]

SKIP_DOMAINS = [
    "facebook.com", "twitter.com", "linkedin.com", "instagram.com",
    "youtube.com", "google.com", "apple.com", "microsoft.com",
    "list-manage.com", "mailchimp.com", "avanan.click"
]

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

def get_domain(url):
    return urlparse(url).netloc.lower().replace("www.", "")

def is_skip_domain(url):
    domain = get_domain(url)
    for skip in SKIP_DOMAINS + CCI_DOMAINS + [ACMO_DOMAIN]:
        if skip in domain:
            return True
    return False

def find_subpage(base_url, keywords):
    soup = get_soup(base_url)
    if not soup:
        return None
    base_domain = get_domain(base_url)
    links = soup.find_all("a", href=True)
    for link in links:
        href = link["href"].lower()
        text = link.get_text().lower().strip()
        for kw in keywords:
            if kw in href or kw in text:
                full_url = urljoin(base_url, link["href"])
                if get_domain(full_url) == base_domain:
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
    cards = soup.find_all(["div", "article", "li"], class_=re.compile(r'team|staff|person|member|card|employee', re.I))
    for card in cards:
        text = card.get_text(separator=" ", strip=True)
        name_tag = card.find(["h2", "h3", "h4", "strong", "b"])
        name = name_tag.get_text(strip=True) if name_tag else None
        if name and len(name.split()) >= 2 and len(name) < 60:
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
        if name and len(name) < 100:
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
        print(f"Error saving: {e}")

def extract_acmo_companies(soup):
    """ACMO page has a clean ul list of company name -> external website links"""
    companies = []
    main_content = soup.find("div", class_=re.compile(r'content|main|body|field', re.I))
    if not main_content:
        main_content = soup
    list_items = main_content.find_all("li")
    for li in list_items:
        link = li.find("a", href=True)
        if link:
            href = link["href"]
            name = link.get_text(strip=True)
            if not href.startswith("http"):
                continue
            if is_skip_domain(href):
                continue
            if name and len(name) > 3:
                companies.append({"name": name, "website": href})
    return companies

def extract_cci_companies(soup, source_url):
    """CCI pages vary — try to find external company links"""
    companies = []
    seen = set()
    links = soup.find_all("a", href=True)
    for link in links:
        href = link["href"]
        name = link.get_text(strip=True)
        if not href.startswith("http"):
            full_url = urljoin(source_url, href)
        else:
            full_url = href
        if is_skip_domain(full_url):
            continue
        if get_domain(full_url) == get_domain(source_url):
            continue
        if not name or len(name) < 4 or len(name) > 80:
            continue
        if name in seen:
            continue
        seen.add(name)
        companies.append({"name": name, "website": full_url})
    return companies

def scrape_source(source):
    print(f"\n--- Scraping {source['name']} ---")
    soup = get_soup(source["url"])
    if not soup:
        print(f"Could not fetch {source['url']}")
        return

    if source["name"] == "acmo":
        companies = extract_acmo_companies(soup)
    else:
        companies = extract_cci_companies(soup, source["url"])

    print(f"Found {len(companies)} companies")

    for company in companies[:100]:
        name = company["name"]
        website = company["website"]

        if record_exists(name, source["name"]):
            print(f"Skipping {name} — exists")
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
