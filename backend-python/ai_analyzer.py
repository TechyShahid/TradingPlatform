import json
import urllib.request
import database
import analyze_fundamentals

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_market_data_summary():
    """Aggregates data from deals and fundamentals to feed to the LLM"""
    conn = database.get_db_connection()
    conn.row_factory = dict_factory
    cur = conn.cursor()

    # Get Deals Data (Stocks with high institutional buying)
    query_deals = """
        SELECT symbol, security_name, COUNT(*) as buy_count, SUM(quantity_traded) as total_bought
        FROM (
            SELECT symbol, security_name, quantity_traded FROM bulk_deals WHERE buy_sell LIKE 'BUY%'
            UNION ALL
            SELECT symbol, security_name, quantity_traded FROM block_deals WHERE buy_sell LIKE 'BUY%'
        )
        GROUP BY symbol, security_name
        HAVING buy_count > 0
        ORDER BY total_bought DESC
        LIMIT 20
    """
    cur.execute(query_deals)
    deals_data = cur.fetchall()

    # Get Fundamentals Data
    fundamentals_data = analyze_fundamentals.find_growth_stocks()
    conn.close()

    # Merge them into a structured text prompt
    summary = "--- INSTITUTIONAL BUYING ACTIVITY (Top 20 by Volume) ---\n"
    for d in deals_data:
        summary += f"Symbol: {d['symbol']} ({d['security_name']}) | Institutional Buy Deals: {d['buy_count']} | Total Volume Bought: {d['total_bought']}\n"

    summary += "\n--- FUNDAMENTAL GROWTH DATA (YoY > 10% Revenue Growth) ---\n"
    for f in fundamentals_data:
        summary += f"Symbol: {f['symbol']} | Revenue Growth: {f['revenue_growth_pct']}% | Net Profit Growth: {f['profit_growth_pct']}%\n"

    return summary


def call_groq_api(prompt):
    """Call Groq Cloud API which runs Llama 3 with ultra-fast inference (free tier)"""
    import os
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found")

    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert quantitative financial analyst. Respond ONLY with valid JSON arrays. No markdown, no explanation, no code fences."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.6,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {api_key}')
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    response = urllib.request.urlopen(req, timeout=60)
    res_data = json.loads(response.read().decode('utf-8'))

    text = res_data['choices'][0]['message']['content'].strip()
    parsed = json.loads(text)

    # Handle both {"predictions": [...]} wrapper and direct [...] array
    if isinstance(parsed, dict):
        for key in ['predictions', 'stocks', 'results', 'data']:
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        # If dict has symbol key, it's a single prediction
        if 'symbol' in parsed:
            return [parsed]
    return parsed


def call_gemini_api(prompt):
    import os
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    
    response = urllib.request.urlopen(req, timeout=30)
    res_data = json.loads(response.read().decode('utf-8'))
    
    text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
    return json.loads(text)

def get_heuristic_predictions():
    """Fallback generator when AI APIs are unavailable"""
    print("[AI Analyzer] Generating heuristic recommendations...")
    conn = database.get_db_connection()
    conn.row_factory = dict_factory
    cur = conn.cursor()

    # Get Deals
    query_deals = """
        SELECT symbol, security_name, COUNT(*) as buy_count, SUM(quantity_traded) as total_bought
        FROM (
            SELECT symbol, security_name, quantity_traded FROM bulk_deals WHERE buy_sell LIKE 'BUY%'
            UNION ALL
            SELECT symbol, security_name, quantity_traded FROM block_deals WHERE buy_sell LIKE 'BUY%'
        )
        GROUP BY symbol, security_name
        HAVING buy_count > 0
        ORDER BY total_bought DESC
        LIMIT 30
    """
    cur.execute(query_deals)
    deals_data = cur.fetchall()

    fundamentals_data = analyze_fundamentals.find_growth_stocks()
    conn.close()

    deals_map = {d['symbol']: d for d in deals_data}
    fund_map = {f['symbol']: f for f in fundamentals_data}

    # Find overlap
    overlap_symbols = set(deals_map.keys()).intersection(set(fund_map.keys()))
    
    candidates = []
    
    # 1. Overlapping stocks first
    for sym in overlap_symbols:
        d = deals_map[sym]
        f = fund_map[sym]
        candidates.append({
            "symbol": sym,
            "company_name": d['security_name'] or sym,
            "predicted_growth_pct": int(15 + (f['revenue_growth_pct'] / 10)),
            "reasoning": f"Heuristic Pick: High overlap with {d['buy_count']} institutional buy deals and strong {f['revenue_growth_pct']}% YoY revenue growth."
        })

    # 2. Add remaining from deals (high volume)
    for sym, d in deals_map.items():
        if len(candidates) >= 10:
            break
        if sym not in overlap_symbols:
            candidates.append({
                "symbol": sym,
                "company_name": d['security_name'] or sym,
                "predicted_growth_pct": 15,
                "reasoning": f"Heuristic Pick: Substantial institutional buying with {d['buy_count']} block/bulk deals (Total volume: {d['total_bought']})."
            })

    # 3. Add from fundamentals if still short
    for sym, f in fund_map.items():
        if len(candidates) >= 10:
            break
        if sym not in [c['symbol'] for c in candidates]:
            candidates.append({
                "symbol": sym,
                "company_name": sym,
                "predicted_growth_pct": int(12 + (f['revenue_growth_pct'] / 12)),
                "reasoning": f"Heuristic Pick: Solid fundamental growth with {f['revenue_growth_pct']}% YoY revenue expansion."
            })

    # Ensure we return at least a default pick if the database is completely empty
    if not candidates:
        default_stocks = [
            ("RELIANCE", "Reliance Industries Ltd"),
            ("TCS", "Tata Consultancy Services Ltd"),
            ("INFY", "Infosys Ltd"),
            ("HDFCBANK", "HDFC Bank Ltd"),
            ("ICICIBANK", "ICICI Bank Ltd"),
            ("SBI", "State Bank of India"),
            ("BHARTIARTL", "Bharti Airtel Ltd"),
            ("L&T", "Larsen & Toubro Ltd"),
            ("ITC", "ITC Ltd"),
            ("KOTAKBANK", "Kotak Mahindra Bank Ltd")
        ]
        for idx, (sym, name) in enumerate(default_stocks):
            candidates.append({
                "symbol": sym,
                "company_name": name,
                "predicted_growth_pct": 12 + idx,
                "reasoning": f"Default market leader pick based on long-term compound performance statistics."
            })

    return candidates[:10]

_predictions_cache = {"data": None, "timestamp": 0}

def predict_growth_stocks():
    """Predicts top 10 growth stocks using Groq (Llama 3), Gemini API, Ollama, or heuristic fallback with 1-hour cache."""
    import os, time
    global _predictions_cache

    now = time.time()
    if _predictions_cache["data"] and (now - _predictions_cache["timestamp"] < 3600):
        return _predictions_cache["data"]

    market_data = get_market_data_summary()

    prompt = f"""You are an expert quantitative financial analyst specializing in the Indian Stock Market (NSE).

I am providing you with two datasets:
1. **Institutional Buying Activity**: Stocks that large institutions (mutual funds, FIIs, DIIs) are actively buying in bulk/block deals. Higher buy_count and total_bought indicate stronger institutional conviction.
2. **Fundamental Growth Data**: Stocks showing strong Year-over-Year (YoY) revenue and profit growth.

Your task: Select EXACTLY 10 stocks with the highest growth potential for the next 12 months.

**CRITICAL RULES:**
- Each stock MUST have a DIFFERENT predicted_growth_pct value (no two stocks can have the same percentage)
- Range your predictions between 8% and 45% based on the strength of evidence
- Stocks appearing in BOTH lists deserve higher growth predictions (25-45%)
- Stocks with very high institutional buying volume but no fundamental data: predict 15-25%
- Stocks with good fundamentals but low institutional interest: predict 8-18%
- Your reasoning MUST cite specific numbers from the data (buy count, volume, revenue growth %)
- Do NOT give generic reasoning — be specific about WHY each stock differs

Here is the data:
{market_data}

Output a JSON object with a "predictions" key containing an array of exactly 10 objects sorted by predicted_growth_pct descending.

Required format:
{{{{
  "predictions": [
    {{{{
      "symbol": "STOCKNAME",
      "company_name": "Full Company Name",
      "predicted_growth_pct": 32,
      "reasoning": "Specific reason citing data numbers..."
    }}}}
  ]
}}}}
"""

    # 1. Try Groq Cloud API (Llama 3) — best quality, free tier
    if os.environ.get("GROQ_API_KEY"):
        print("[AI Analyzer] Requesting predictions from Groq Cloud (Llama 3)...")
        try:
            result = call_groq_api(prompt)
            if result and len(result) > 0:
                print(f"[AI Analyzer] Groq returned {len(result)} predictions successfully.")
                return result
        except Exception as e:
            print(f"[AI Analyzer] Groq API error: {e}. Trying fallback...")

    # 2. Try Google Gemini API as fallback
    if os.environ.get("GEMINI_API_KEY"):
        print("[AI Analyzer] Requesting predictions from Google Gemini API...")
        try:
            return call_gemini_api(prompt)
        except Exception as e:
            print(f"[AI Analyzer] Gemini API error: {e}. Trying fallback...")

    # 3. Try Local Ollama (Llama 3) — only works on local dev machine
    print("[AI Analyzer] Requesting predictions from local Ollama (Llama 3)...")
    data = {
        "model": "llama3:latest",
        "prompt": prompt + "[\n",
        "stream": False,
        "options": {
            "temperature": 0.4
        }
    }

    req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')

    try:
        response = urllib.request.urlopen(req, timeout=120)
        result = json.loads(response.read().decode('utf-8'))
        
        import re
        raw_response = result['response'].strip()
        predictions = []
        
        matches = re.finditer(r'\{[^{}]+\}', raw_response)
        for match in matches:
            try:
                obj = json.loads(match.group(0))
                if 'symbol' in obj and 'predicted_growth_pct' in obj:
                    predictions.append(obj)
            except json.JSONDecodeError:
                continue
                
        if not predictions:
            try:
                if not raw_response.startswith('['):
                    raw_response = '[' + raw_response
                if not raw_response.endswith(']'):
                    raw_response = raw_response + ']'
                predictions = json.loads(raw_response)
            except Exception as e:
                print(f"JSON Decode Error! Raw response was:\n{raw_response}")
                raise e
                
        if isinstance(predictions, dict):
            predictions = [predictions]
        _predictions_cache["data"] = predictions
        _predictions_cache["timestamp"] = time.time()
        return predictions
    except Exception as e:
        print(f"[AI Analyzer] Ollama error: {e}")
        # 4. Fall back to high-quality heuristic calculator
        fallback = get_heuristic_predictions()
        _predictions_cache["data"] = fallback
        _predictions_cache["timestamp"] = time.time()
        return fallback

if __name__ == '__main__':
    print("Testing AI Analyzer...")
    res = predict_growth_stocks()
    print(json.dumps(res, indent=2))


def call_llm_text_completion(system_prompt, user_prompt):
    """
    Calls LLM (Groq Llama 3 / Gemini) for free-form conversational text completion.
    Supports warm Mota Bhai persona responses, general chat, and RAG data answers.
    """
    import os
    
    # 1. Try Groq (Llama 3.3 70B Versatile)
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if groq_api_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1024
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Authorization', f'Bearer {groq_api_key}')
            req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)')
            response = urllib.request.urlopen(req, timeout=30)
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"[LLM Text Completion] Groq API call failed: {e}")

    # 2. Try Gemini API
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if gemini_api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
            req.add_header('Content-Type', 'application/json')
            response = urllib.request.urlopen(req, timeout=30)
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            print(f"[LLM Text Completion] Gemini API call failed: {e}")

    return None
