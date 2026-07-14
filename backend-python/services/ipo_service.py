"""
IPO Service — Fetches real live IPO data, Grey Market Premium (GMP), and subscription details.
"""
import requests
import re
import datetime
from bs4 import BeautifulSoup
import database

# Heuristic to find numbers in price ranges
PRICE_REGEX = re.compile(r'Rs\.?\s*(\d+)\s+to\s+Rs\.?\s*(\d+)', re.IGNORECASE)
PRICE_NUMBERS = re.compile(r'(\d+)')

def parse_price_range(price_str):
    """Extracts min and max price, and estimates lot size."""
    if not price_str:
        return 0, 0, 50
    
    # Try Rs. 203 to Rs. 214 style
    match = PRICE_REGEX.search(price_str)
    if match:
        min_price = int(match.group(1))
        max_price = int(match.group(2))
    else:
        # Try simple numbers
        nums = PRICE_NUMBERS.findall(price_str)
        if len(nums) >= 2:
            min_price = int(nums[0])
            max_price = int(nums[1])
        elif len(nums) == 1:
            min_price = max_price = int(nums[0])
        else:
            min_price = max_price = 0
            
    # SEBI retail lot size heuristic (approx. Rs 14000 to Rs 15000 per lot)
    if max_price > 0:
        lot_size = max(1, 15000 // max_price)
    else:
        lot_size = 50
        
    return min_price, max_price, lot_size


def format_issue_size(size_str, price_range_str):
    """Formats issue size in shares or estimates in Crores (INR)."""
    if not size_str:
        return "N/A"
    
    try:
        shares = float(size_str)
        _, max_price, _ = parse_price_range(price_range_str)
        if max_price > 0:
            crores = (shares * max_price) / 10000000.0
            return f"₹{crores:.2f} Cr"
        else:
            return f"{shares:,.0f} Shares"
    except ValueError:
        return size_str


def parse_date(date_str):
    """Converts DD-MMM-YYYY (e.g. 09-Jul-2026) to YYYY-MM-DD."""
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str.strip(), "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str


def fetch_gmp_data():
    """
    Fetches GMP data from ipowatch.in.
    Returns a dictionary mapping: cleaned_company_name -> (gmp_value, status, date_str, price_band_str)
    """
    gmp_map = {}
    url = "https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                headers_row = [th.get_text(strip=True).lower() for th in rows[0].find_all(['td', 'th'])]
                
                # Identify index mappings
                name_idx = -1
                gmp_idx = -1
                status_idx = -1
                date_idx = -1
                price_idx = -1
                
                for idx, h in enumerate(headers_row):
                    if "name" in h:
                        name_idx = idx
                    elif "gmp" in h:
                        gmp_idx = idx
                    elif "status" in h:
                        status_idx = idx
                    elif "date" in h:
                        date_idx = idx
                    elif "price" in h or "band" in h:
                        price_idx = idx
                        
                if name_idx == -1 or gmp_idx == -1:
                    continue
                
                # Detect if this is the historical listing table
                is_history = any("listing" in h for h in headers_row) or "listing price" in headers_row
                default_status = "Closed" if is_history else "Active"
                
                for row in rows[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    if len(cols) > max(name_idx, gmp_idx):
                        raw_name = cols[name_idx]
                        gmp_val = cols[gmp_idx]
                        status = cols[status_idx] if (status_idx != -1 and len(cols) > status_idx) else default_status
                        date_val = cols[date_idx] if (date_idx != -1 and len(cols) > date_idx) else "N/A"
                        price_val = cols[price_idx] if (price_idx != -1 and len(cols) > price_idx) else "N/A"
                        
                        # Clean name to match easily
                        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', raw_name).strip().lower()
                        clean_name = re.sub(r'\b(ipo|limited|ltd|sme)\b', '', clean_name).strip()
                        clean_name = " ".join(clean_name.split())
                        
                        if clean_name:
                            gmp_map[clean_name] = {
                                "raw_name": raw_name,
                                "gmp": gmp_val,
                                "status": status,
                                "date": date_val,
                                "price": price_val
                            }
    except Exception as e:
        print(f"[IPO Fetcher] Error fetching GMP: {e}")
    return gmp_map


def fetch_upcoming_ipo_details():
    """
    Fetches detailed upcoming IPO list from ipowatch.in containing size and dates.
    Returns a dictionary mapping: cleaned_company_name -> {date, size, price_band}
    """
    details_map = {}
    url = "https://ipowatch.in/upcoming-ipo-list/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table')
            
            # Scrape mainboard and SME tables (usually Table 0 and 1)
            for idx in [0, 1]:
                if len(tables) > idx:
                    table = tables[idx]
                    rows = table.find_all('tr')
                    if len(rows) < 2:
                        continue
                    
                    headers_row = [th.get_text(strip=True).lower() for th in rows[0].find_all(['td', 'th'])]
                    
                    # Columns
                    name_idx = -1
                    date_idx = -1
                    size_idx = -1
                    price_idx = -1
                    
                    for i, h in enumerate(headers_row):
                        if "company" in h or "ipo" == h:
                            name_idx = i
                        elif "date" in h:
                            date_idx = i
                        elif "size" in h:
                            size_idx = i
                        elif "price" in h or "band" in h:
                            price_idx = i
                            
                    if name_idx == -1:
                        continue
                        
                    for row in rows[1:]:
                        cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                        if len(cols) > name_idx:
                            name = cols[name_idx]
                            date_val = cols[date_idx] if (date_idx != -1 and len(cols) > date_idx) else "N/A"
                            size_val = cols[size_idx] if (size_idx != -1 and len(cols) > size_idx) else "N/A"
                            price_val = cols[price_idx] if (price_idx != -1 and len(cols) > price_idx) else "N/A"
                            
                            clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', name).strip().lower()
                            clean_name = re.sub(r'\b(ipo|limited|ltd|sme)\b', '', clean_name).strip()
                            clean_name = " ".join(clean_name.split())
                            
                            if clean_name:
                                details_map[clean_name] = {
                                    "date": date_val,
                                    "size": size_val,
                                    "price_band": price_val
                                }
    except Exception as e:
        print(f"[IPO Fetcher] Error fetching upcoming IPO details: {e}")
    return details_map


def fetch_live_ipos():
    """
    Fetches active/current IPOs from NSE, aggregates GMP and metadata details from ipowatch.in,
    and updates the database.
    """
    print("[IPO Fetcher] Starting live IPO fetch and aggregation...")
    
    # 1. Fetch GMP and Calendar details
    gmp_map = fetch_gmp_data()
    upcoming_details = fetch_upcoming_ipo_details()
    
    print(f"[IPO Fetcher] Retrieved {len(gmp_map)} GMP records and {len(upcoming_details)} details from grey market portal.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/"
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    # 2. Query NSE India active/current issues
    active_issues = []
    try:
        session.get("https://www.nseindia.com", timeout=10)
        r_list = session.get("https://www.nseindia.com/api/ipo-current-issue", timeout=10)
        if r_list.status_code == 200:
            active_issues = r_list.json()
    except Exception as e:
        print(f"[IPO Fetcher] Error connecting to NSE: {e}")
        
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    try:
        # Delete legacy non-deterministic IPO symbols to clear duplicates
        cur.execute("DELETE FROM ipos WHERE symbol LIKE 'IPO%'")
        # Also clean up duplicate company name entries to keep database clean
        cur.execute('''
            DELETE FROM ipos 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM ipos 
                GROUP BY company_name
            )
        ''')
        conn.commit()
    except Exception as clean_err:
        print(f"[IPO Fetcher] Error clearing legacy duplicate symbols: {clean_err}")
        
    # Track symbols processed via NSE to avoid double inserting from GMP list
    processed_symbols = set()
    success_count = 0
    
    for issue in active_issues:
        symbol = issue.get("symbol")
        if not symbol:
            continue
            
        company_name = issue.get("companyName") or symbol
        start_date = parse_date(issue.get("issueStartDate"))
        end_date = parse_date(issue.get("issueEndDate"))
        price_range = issue.get("issuePrice", "N/A")
        raw_size = issue.get("issueSize")
        
        _, _, lot_size = parse_price_range(price_range)
        issue_size = format_issue_size(raw_size, price_range)
        
        retail_x = 0.0
        hni_x = 0.0
        qib_x = 0.0
        total_x = 0.0
        
        # Query details for subscription
        url_detail = f"https://www.nseindia.com/api/ipo-detail?symbol={symbol}"
        try:
            r_detail = session.get(url_detail, timeout=10)
            if r_detail.status_code == 200:
                detail_data = r_detail.json()
                bid_details = detail_data.get("bidDetails", [])
                for bid in bid_details:
                    cat = bid.get("category", "")
                    try:
                        multiplier = float(bid.get("noOfTime", "0.0") or "0.0")
                    except ValueError:
                        multiplier = 0.0
                        
                    if "Qualified Institutional Buyers" in cat:
                        qib_x = multiplier
                    elif cat == "Non Institutional Investors":
                        hni_x = multiplier
                    elif "Retail Individual Investors" in cat:
                        retail_x = multiplier
                
                graph_all = detail_data.get("demandGraphALL", {})
                if graph_all:
                    try:
                        total_x = float(graph_all.get("noOfTimesIssueSubscribed", "0.0") or "0.0")
                    except ValueError:
                        total_x = 0.0
                if total_x == 0.0:
                    total_x = round((retail_x * 0.35) + (hni_x * 0.15) + (qib_x * 0.50), 2)
        except Exception as e:
            print(f"[IPO Fetcher] Error details for {symbol}: {e}")
            
        # Match GMP
        gmp_val = "N/A"
        clean_issue_name = re.sub(r'[^a-zA-Z0-9\s]', '', company_name).strip().lower()
        clean_issue_name = re.sub(r'\b(ipo|limited|ltd|sme)\b', '', clean_issue_name).strip()
        clean_issue_name = " ".join(clean_issue_name.split())
        
        # Enrich from upcoming_details if missing
        if clean_issue_name in upcoming_details:
            up_info = upcoming_details[clean_issue_name]
            if not price_range or price_range == "N/A":
                price_range = up_info["price_band"]
            if not issue_size or issue_size == "N/A":
                issue_size = up_info["size"]
        
        if clean_issue_name in gmp_map:
            gmp_val = gmp_map[clean_issue_name]["gmp"]
            gmp_map.pop(clean_issue_name)
        else:
            matched_key = None
            for k, v in gmp_map.items():
                if k in clean_issue_name or clean_issue_name in k:
                    gmp_val = v["gmp"]
                    matched_key = k
                    break
            if matched_key:
                gmp_map.pop(matched_key)
                
        # Determine status dynamically based on current date vs start/end dates
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        if end_date and end_date < today_str:
            status = "Closed"
        elif start_date and start_date > today_str:
            status = "Upcoming"
        else:
            status = "Active"
        
        try:
            cur.execute('''
                INSERT INTO ipos (
                    company_name, symbol, issue_start_date, issue_end_date, 
                    price_range, issue_size, lot_size, status, 
                    retail_x, hni_x, qib_x, total_x, gmp, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    company_name=excluded.company_name,
                    issue_start_date=excluded.issue_start_date,
                    issue_end_date=excluded.issue_end_date,
                    price_range=excluded.price_range,
                    issue_size=excluded.issue_size,
                    lot_size=excluded.lot_size,
                    status=excluded.status,
                    retail_x=excluded.retail_x,
                    hni_x=excluded.hni_x,
                    qib_x=excluded.qib_x,
                    total_x=excluded.total_x,
                    gmp=excluded.gmp,
                    updated_at=excluded.updated_at
            ''', (
                company_name, symbol, start_date, end_date,
                price_range, issue_size, lot_size, status,
                retail_x, hni_x, qib_x, total_x, gmp_val,
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            processed_symbols.add(symbol)
            success_count += 1
        except Exception as db_err:
            print(f"[IPO Fetcher] Database error for {symbol}: {db_err}")
            
    # 3. For any remaining GMP listings (e.g. upcoming/closed ones not returned by NSE active API),
    # insert them as well so the user gets the complete set of grey market trends.
    for clean_name, info in gmp_map.items():
        company_name = info["raw_name"]
        
        # Generate clean symbol deterministically
        import hashlib
        words = [re.sub(r'[^A-Z]', '', w.upper()) for w in company_name.split()]
        words = [w for w in words if w]
        if words:
            # Combine first two words if first is short
            first = words[0]
            if len(first) < 3 and len(words) > 1:
                first_word = (first + words[1])[:6]
            else:
                first_word = first[:6]
        else:
            first_word = ""
            
        if len(first_word) < 3:
            h = hashlib.md5(clean_name.encode('utf-8')).hexdigest()
            first_word = f"IPO{h[:4].upper()}"
            
        symbol = first_word
        
        # Avoid duplicate symbols
        idx = 1
        while symbol in processed_symbols:
            symbol = f"{first_word}{idx}"
            idx += 1
            
        gmp_val = info["gmp"]
        price_range = info["price"]
        issue_size = "N/A"
        
        # Enrich from upcoming details if available
        start_date = "N/A"
        end_date = "N/A"
        date_str = info["date"]
        
        if clean_name in upcoming_details:
            up_info = upcoming_details[clean_name]
            if up_info["price_band"] != "N/A":
                price_range = up_info["price_band"]
            if up_info["size"] != "N/A":
                issue_size = up_info["size"]
            if up_info["date"] != "N/A":
                date_str = up_info["date"]
                
        # Parse start & end dates from the Date string (e.g. "14-16 July" or "9-13 July")
        date_match = re.search(r'(\d+)-(\d+)\s+([A-Za-z]+)', date_str)
        if date_match:
            start_date = f"{date_match.group(1)} {date_match.group(3)}"
            end_date = f"{date_match.group(2)} {date_match.group(3)}"
            
        # Set status
        raw_status = info["status"].lower()
        if "open" in raw_status or "active" in raw_status:
            status = "Active"
        elif "close" in raw_status:
            status = "Closed"
        else:
            status = "Upcoming"
            
        # Refine status based on dates if available
        today_str = datetime.date.today().strftime("%d %B") # e.g. "09 July"
        # If dates are in standard YYYY-MM-DD format (or we compare year-wise)
        # But since dates are e.g. "14 July", let's do a simple comparison:
        # We can try parsing them into standard dates
        try:
            current_year = datetime.datetime.now().year
            if start_date != "N/A" and end_date != "N/A":
                start_dt = datetime.datetime.strptime(f"{start_date} {current_year}", "%d %B %Y")
                end_dt = datetime.datetime.strptime(f"{end_date} {current_year}", "%d %B %Y")
                today_dt = datetime.datetime.now()
                
                # Format to standard YYYY-MM-DD for database consistency!
                start_db = start_dt.strftime("%Y-%m-%d")
                end_db = end_dt.strftime("%Y-%m-%d")
                
                start_date = start_db
                end_date = end_db
                
                if end_dt.date() < today_dt.date():
                    status = "Closed"
                elif start_dt.date() > today_dt.date():
                    status = "Upcoming"
                else:
                    status = "Active"
        except Exception:
            pass
            
        _, _, lot_size = parse_price_range(price_range)
        
        try:
            cur.execute('''
                INSERT INTO ipos (
                    company_name, symbol, issue_start_date, issue_end_date, 
                    price_range, issue_size, lot_size, status, 
                    retail_x, hni_x, qib_x, total_x, gmp, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    company_name=excluded.company_name,
                    issue_start_date=excluded.issue_start_date,
                    issue_end_date=excluded.issue_end_date,
                    price_range=excluded.price_range,
                    issue_size=excluded.issue_size,
                    lot_size=excluded.lot_size,
                    status=excluded.status,
                    gmp=excluded.gmp,
                    updated_at=excluded.updated_at
            ''', (
                company_name, symbol, start_date, end_date,
                price_range, issue_size, lot_size, status,
                0.0, 0.0, 0.0, 0.0, gmp_val,
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            processed_symbols.add(symbol)
            success_count += 1
        except Exception as db_err:
            print(f"[IPO Fetcher] Database error for GMP seed {symbol}: {db_err}")
            
    conn.commit()
    conn.close()
    print(f"[IPO Fetcher] Finished live fetch. persited {success_count} IPO records in database.")
    return True
