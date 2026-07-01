import os
import re
import sqlite3
import datetime
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from database import get_db_connection, init_db

# Reputed stock market RSS feeds
FEEDS = {
    'Yahoo Finance': 'https://finance.yahoo.com/news/rss',
    'Economic Times': 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
    'Moneycontrol': 'https://www.moneycontrol.com/rss/marketedge.xml',
    'MarketWatch': 'https://feeds.content.dowjones.io/public/rss/mw_topstories',
    'CNBC': 'https://www.cnbc.com/id/10000664/device/rss/rss.html'
}

# Positive and Negative financial sentiment keywords
POSITIVE_WORDS = {
    'surge', 'jump', 'gain', 'rise', 'rally', 'bullish', 'upbeat', 'profit', 
    'record', 'outperform', 'growth', 'buy', 'acquisition', 'expand', 'beat', 
    'upgrade', 'higher', 'positive', 'breakout', 'spike', 'recovery', 'bounce', 
    'green', 'success', 'strengthen', 'growth', 'stellar', 'positive'
}

NEGATIVE_WORDS = {
    'slump', 'fall', 'drop', 'plunge', 'loss', 'bearish', 'miss', 'debt', 
    'deficit', 'decline', 'warning', 'sell', 'layoff', 'probe', 'scam', 
    'regulatory', 'investigation', 'cut', 'downgrade', 'lower', 'negative', 
    'crash', 'slashed', 'red', 'worry', 'fear', 'inflation', 'recession', 
    'hit', 'weak', 'sluggish', 'plummets'
}

# Fallback top tickers in case DB tables are empty
DEFAULT_TICKERS = {
    'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'HUL', 'ITC', 'SBIN', 
    'BHARTIARTL', 'LICI', 'ZOMATO', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 
    'GOOGL', 'TATAMOTORS', 'AXISBANK', 'KOTAKBANK', 'WIPRO', 'HCLTECH'
}

def parse_rss_date(date_str):
    """Parses RFC 822/2822 RSS date strings to standard ISO UTC format."""
    if not date_str:
        return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    try:
        dt = parsedate_to_datetime(date_str)
        # Convert to UTC timezone-naive standard representation
        return dt.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        # Fallback to now on failure
        return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def analyze_sentiment(title, summary):
    """Calculates financial sentiment based on custom weighted keyword lists."""
    combined = f"{title} {summary}".lower()
    # Find all alphabetic words
    words = re.findall(r'\b[a-z]{3,20}\b', combined)
    
    pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
    
    if pos_count > neg_count:
        return 'Positive'
    elif neg_count > pos_count:
        return 'Negative'
    else:
        return 'Neutral'

def get_known_tickers():
    """Queries all database tables to compile a list of known stock tickers."""
    tickers = set(DEFAULT_TICKERS)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Select from bulk_deals, block_deals, consistent_compounders, fundamentals
        queries = [
            "SELECT DISTINCT symbol FROM bulk_deals",
            "SELECT DISTINCT symbol FROM block_deals",
            "SELECT DISTINCT symbol FROM consistent_compounders",
            "SELECT DISTINCT symbol FROM fundamentals"
        ]
        
        for q in queries:
            try:
                cursor.execute(q)
                for row in cursor.fetchall():
                    if row[0] and isinstance(row[0], str):
                        # clean symbol
                        clean_sym = row[0].upper().strip()
                        if clean_sym:
                            tickers.add(clean_sym)
            except sqlite3.OperationalError:
                # Table might not exist yet during first boot
                pass
                
        conn.close()
    except Exception as e:
        print(f"[News Crawler] Warning querying database tickers: {e}")
        
    return tickers

def match_tickers(title, summary, known_tickers):
    """Matches known tickers from DB to the news text using word boundaries."""
    combined = f"{title} {summary}"
    
    # 1. Search for exact uppercase word matches (e.g. INFY, TCS, RELIANCE)
    uppercase_words = set(re.findall(r'\b[A-Z]{2,10}\b', combined))
    matched = uppercase_words.intersection(known_tickers)
    
    # 2. Check case-insensitive exact matches for NSE stock symbols in the title/summary
    if not matched:
        # Compile words from combined text (lowercased)
        lowercased_combined = combined.lower()
        matched_lowercase = []
        for ticker in known_tickers:
            # Avoid matching extremely short symbols like 'Y' or 'T' that could match common words
            if len(ticker) < 3:
                continue
            # Search for ticker with word boundaries
            pattern = r'\b' + re.escape(ticker.lower()) + r'\b'
            if re.search(pattern, lowercased_combined):
                matched_lowercase.append(ticker)
        if matched_lowercase:
            matched = set(matched_lowercase)
            
    if matched:
        return ",".join(sorted(list(matched)))
    return None

def fetch_feed(url):
    """Fetches feed XML with user-agent headers to bypass scraper blocks."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Accept': 'application/xml,text/xml,application/xhtml+xml'
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read()
    except Exception as e:
        print(f"[News Crawler] Failed to retrieve feed {url}: {e}")
        return None

def parse_feed_xml(xml_content, source_name):
    """Parses standard RSS 2.0 XML and returns list of news dictionary objects."""
    articles = []
    if not xml_content:
        return articles
        
    try:
        root = ET.fromstring(xml_content)
        # Find all <item> tags (RSS 2.0)
        channel = root.find('channel')
        items = channel.findall('item') if channel is not None else root.findall('.//item')
        
        for item in items:
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            description = item.findtext('description', '').strip()
            pub_date = item.findtext('pubDate', '').strip()
            
            # Clean HTML out of description
            description_cleaned = re.sub(r'<[^>]*>', '', description).strip()
            
            # Format link properly if it's nested or has queries
            if link:
                articles.append({
                    'title': title,
                    'url': link,
                    'summary': description_cleaned,
                    'published_at': parse_rss_date(pub_date),
                    'source': source_name
                })
    except Exception as e:
        print(f"[News Crawler] Error parsing XML for {source_name}: {e}")
        
    return articles

def crawl_all_news():
    """Runs crawling across all feeds, processes articles, and saves them to DB."""
    print(f"[News Crawler] Starting news aggregation crawl at {datetime.datetime.now()}")
    init_db()
    
    known_tickers = get_known_tickers()
    print(f"[News Crawler] Loaded {len(known_tickers)} known tickers for tagging.")
    
    total_scraped = 0
    total_new = 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for source_name, url in FEEDS.items():
        print(f"[News Crawler] Crawling source: {source_name}...")
        xml_data = fetch_feed(url)
        articles = parse_feed_xml(xml_data, source_name)
        
        source_new_count = 0
        for art in articles:
            total_scraped += 1
            sentiment = analyze_sentiment(art['title'], art['summary'])
            matched_ticker = match_tickers(art['title'], art['summary'], known_tickers)
            
            try:
                cursor.execute('''
                    INSERT INTO stock_news 
                    (title, source, url, summary, published_at, sentiment, ticker)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    art['title'],
                    art['source'],
                    art['url'],
                    art['summary'],
                    art['published_at'],
                    sentiment,
                    matched_ticker
                ))
                source_new_count += 1
                total_new += 1
            except sqlite3.IntegrityError:
                # Duplicate article (unique constraint on url matched)
                pass
                
        conn.commit()
        print(f"[News Crawler] Crawled {len(articles)} articles from {source_name} ({source_new_count} new).")
        
    conn.close()
    print(f"[News Crawler] Crawl complete. Processed {total_scraped} articles, inserted {total_new} new records.")
    return total_new

if __name__ == '__main__':
    # Allow running directly from command line for manual verification
    new_records = crawl_all_news()
    print(f"Crawled and stored {new_records} new articles.")
