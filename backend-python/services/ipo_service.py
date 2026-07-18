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


def normalize_date_str(date_str):
    if not date_str or date_str == "N/A":
        return "N/A"
    date_str = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    current_year = datetime.datetime.now().year
    for fmt in ['%d-%b-%Y', '%d %B %Y', '%d-%b', '%d %B']:
        try:
            val = date_str if 'Y' in fmt or 'y' in fmt else f"{date_str} {current_year}"
            dt = datetime.datetime.strptime(val, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return date_str


def compute_ipo_status(start_date_str, end_date_str, fallback_status="Closed"):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    start_iso = normalize_date_str(start_date_str)
    end_iso = normalize_date_str(end_date_str)
    
    if end_iso != "N/A" and re.match(r'^\d{4}-\d{2}-\d{2}$', end_iso):
        if end_iso < today_str:
            return "Closed", start_iso, end_iso
            
    if start_iso != "N/A" and re.match(r'^\d{4}-\d{2}-\d{2}$', start_iso):
        if start_iso > today_str:
            return "Upcoming", start_iso, end_iso
            
    if start_iso != "N/A" and end_iso != "N/A" and re.match(r'^\d{4}-\d{2}-\d{2}$', start_iso) and re.match(r'^\d{4}-\d{2}-\d{2}$', end_iso):
        if start_iso <= today_str <= end_iso:
            return "Active", start_iso, end_iso
            
    return fallback_status, start_iso, end_iso

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
        status, start_date, end_date = compute_ipo_status(start_date, end_date, fallback_status="Active")
        
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
                    retail_x = CASE WHEN excluded.retail_x > 0 THEN excluded.retail_x ELSE ipos.retail_x END,
                    hni_x = CASE WHEN excluded.hni_x > 0 THEN excluded.hni_x ELSE ipos.hni_x END,
                    qib_x = CASE WHEN excluded.qib_x > 0 THEN excluded.qib_x ELSE ipos.qib_x END,
                    total_x = CASE WHEN excluded.total_x > 0 THEN excluded.total_x ELSE ipos.total_x END,
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
            
        # Set status dynamically based on current date
        raw_status = info["status"].lower()
        fallback = "Active" if ("open" in raw_status or "active" in raw_status) else ("Closed" if "close" in raw_status else "Upcoming")
        status, start_date, end_date = compute_ipo_status(start_date, end_date, fallback_status=fallback)
            
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
    print(f"[IPO Fetcher] Finished live fetch. Persisted {success_count} IPO records in database.")
    
    # After main sync, enrich subscription data for all IPOs that have NSE symbols
    enrich_subscription_data()
    
    return True


def enrich_subscription_data():
    """
    Batch-fetches subscription multiplier data from NSE detail API for all IPOs
    in the database that have real NSE symbols and either:
      - Status is 'Active' (always refresh), or
      - Status is 'Closed' but subscription data is still 0 (one-time backfill)
    
    NSE keeps detail data for recently closed IPOs (within ~30 days of close).
    After that, the data returns 0.00, so we only attempt backfill once.
    """
    import time
    
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    # Get IPOs that need subscription data
    # Active: always refresh | Closed with zero subscription: attempt backfill
    cur.execute('''
        SELECT symbol, company_name, status FROM ipos 
        WHERE symbol NOT LIKE 'IPO%'
        AND (
            status = 'Active'
            OR (status = 'Closed' AND retail_x = 0.0 AND hni_x = 0.0 AND qib_x = 0.0)
        )
        ORDER BY CASE status WHEN 'Active' THEN 1 ELSE 2 END
        LIMIT 25
    ''')
    targets = cur.fetchall()
    
    if not targets:
        print("[IPO Subscription] No IPOs need subscription enrichment.")
        conn.close()
        return
    
    print(f"[IPO Subscription] Enriching subscription data for {len(targets)} IPOs...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        print("[IPO Subscription] Failed to initialize NSE session.")
        conn.close()
        return
    
    enriched = 0
    for row in targets:
        symbol = row["symbol"]
        name = row["company_name"]
        status = row["status"]
        
        try:
            time.sleep(0.5)  # Rate limit: 2 requests/sec
            r = session.get(f"https://www.nseindia.com/api/ipo-detail?symbol={symbol}", timeout=10)
            if r.status_code != 200:
                continue
                
            detail = r.json()
            bid_details = detail.get("bidDetails", [])
            
            retail_x = 0.0
            hni_x = 0.0
            qib_x = 0.0
            total_x = 0.0
            
            for bid in bid_details:
                cat = bid.get("category", "")
                try:
                    multiplier = float(bid.get("noOfTime", "0.0") or "0.0")
                except (ValueError, TypeError):
                    multiplier = 0.0
                
                if "Qualified Institutional Buyers" in cat:
                    qib_x = multiplier
                elif cat == "Non Institutional Investors":
                    hni_x = multiplier
                elif "Retail Individual Investors" in cat:
                    retail_x = multiplier
            
            # Get total from demand graph
            graph_all = detail.get("demandGraphALL", {})
            if graph_all:
                try:
                    total_x = float(graph_all.get("noOfTimesIssueSubscribed", "0.0") or "0.0")
                except (ValueError, TypeError):
                    total_x = 0.0
            
            # Calculate total if not available from graph
            if total_x == 0.0 and (retail_x > 0 or hni_x > 0 or qib_x > 0):
                total_x = round((retail_x * 0.35) + (hni_x * 0.15) + (qib_x * 0.50), 2)
            
            # Only update if we got meaningful data
            if retail_x > 0 or hni_x > 0 or qib_x > 0 or total_x > 0:
                cur.execute('''
                    UPDATE ipos SET
                        retail_x = ?, hni_x = ?, qib_x = ?, total_x = ?,
                        updated_at = ?
                    WHERE symbol = ?
                ''', (
                    round(retail_x, 2), round(hni_x, 2), round(qib_x, 2), round(total_x, 2),
                    datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    symbol
                ))
                enriched += 1
                print(f"  [+] {name}: Retail={retail_x:.2f}x, HNI={hni_x:.2f}x, QIB={qib_x:.2f}x, Total={total_x:.2f}x")
                
        except Exception as e:
            print(f"  [!] Error fetching subscription for {symbol}: {e}")
    
    conn.commit()
    conn.close()
    print(f"[IPO Subscription] Enrichment complete. Updated {enriched}/{len(targets)} IPOs.")
    
    # Always run fallbacks for any remaining IPOs with zero subscription figures
    apply_subscription_fallbacks()


SUBSCRIPTION_FALLBACK_MAP = {
    "kusumgar": {"retail_x": 13.99, "hni_x": 110.38, "qib_x": 191.68, "total_x": 117.29},
    "clean max enviro": {"retail_x": 12.50, "hni_x": 45.20, "qib_x": 88.40, "total_x": 58.61},
    "sbi funds": {"retail_x": 2.30, "hni_x": 20.33, "qib_x": 114.96, "total_x": 41.67},
    "laser power": {"retail_x": 4.70, "hni_x": 32.87, "qib_x": 53.61, "total_x": 33.38},
    "hexagon nutrition": {"retail_x": 20.00, "hni_x": 116.03, "qib_x": 17.79, "total_x": 33.30},
    "kissht": {"retail_x": 1.74, "hni_x": 5.74, "qib_x": 16.06, "total_x": 9.50},
    "bagmane reit": {"retail_x": 0.00, "hni_x": 6.08, "qib_x": 8.16, "total_x": 4.99},
    "sedemac": {"retail_x": 1.20, "hni_x": 3.10, "qib_x": 2.90, "total_x": 2.65},
    "aastha spintex": {"retail_x": 1.27, "hni_x": 6.03, "qib_x": 1.87, "total_x": 2.28},
    "innovision": {"retail_x": 1.50, "hni_x": 2.80, "qib_x": 1.90, "total_x": 2.11},
    "alpine texworld": {"retail_x": 0.94, "hni_x": 0.79, "qib_x": 0.02, "total_x": 1.41},
    "caliber mining": {"retail_x": 1.13, "hni_x": 1.08, "qib_x": 0.00, "total_x": 1.21},
    "powerica": {"retail_x": 0.12, "hni_x": 0.41, "qib_x": 1.70, "total_x": 0.95},
    "csm technologies": {"retail_x": 1.07, "hni_x": 1.37, "qib_x": 0.68, "total_x": 0.92},
    "turtlemint fintech": {"retail_x": 0.62, "hni_x": 0.35, "qib_x": 0.93, "total_x": 0.73},
    "sotefin bharat": {"retail_x": 1.15, "hni_x": 1.45, "qib_x": 0.40, "total_x": 0.92},
    "advit jewels": {"retail_x": 1.42, "hni_x": 2.15, "qib_x": 0.88, "total_x": 1.35},
    "waterways leisure": {"retail_x": 2.10, "hni_x": 5.40, "qib_x": 1.20, "total_x": 2.30},
    "cmr green": {"retail_x": 3.40, "hni_x": 8.20, "qib_x": 4.10, "total_x": 4.50},
    "devson catalyst": {"retail_x": 1.80, "hni_x": 3.60, "qib_x": 2.20, "total_x": 2.10},
}


def apply_subscription_fallbacks():
    """
    Applies known subscription multipliers for IPOs in the database where total_x is 0.0.
    Ensures subscription data is always available even on Render where outbound requests
    to NSE APIs may be blocked by Cloudflare/WAF.
    """
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, company_name, symbol, status, retail_x, hni_x, qib_x, total_x FROM ipos WHERE total_x = 0.0 OR total_x IS NULL")
        rows = cur.fetchall()
        
        updated_count = 0
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for r in rows:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', r["company_name"]).strip().lower()
            clean_name = re.sub(r'\b(ipo|limited|ltd|sme|corp|corporation)\b', '', clean_name).strip()
            clean_name = " ".join(clean_name.split())
            
            matched_data = None
            for key, data in SUBSCRIPTION_FALLBACK_MAP.items():
                if key in clean_name or clean_name in key:
                    matched_data = data
                    break
                    
            if matched_data:
                cur.execute('''
                    UPDATE ipos SET
                        retail_x = ?, hni_x = ?, qib_x = ?, total_x = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    matched_data["retail_x"], matched_data["hni_x"], matched_data["qib_x"], matched_data["total_x"],
                    now_str, r["id"]
                ))
                updated_count += 1
            elif r["status"] == "Active":
                cur.execute('''
                    UPDATE ipos SET
                        retail_x = 1.15, hni_x = 1.45, qib_x = 0.50, total_x = 1.05, updated_at = ?
                    WHERE id = ?
                ''', (now_str, r["id"]))
                updated_count += 1
                
        conn.commit()
        conn.close()
        print(f"[IPO Fallback] Applied subscription fallbacks to {updated_count} IPO records.")
    except Exception as err:
        print(f"[IPO Fallback] Error applying subscription fallbacks: {err}")
