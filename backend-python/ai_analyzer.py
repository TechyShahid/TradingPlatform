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


def predict_growth_stocks():
    """Calls local Llama 3 to predict the top 10 growth stocks"""
    market_data = get_market_data_summary()

    prompt = f"""
You are an expert quantitative financial analyst. I am providing you with two sets of recent data from the Indian Stock Market (NSE):
1. Institutional Buying Activity: Stocks that large institutions are buying in bulk/block deals.
2. Fundamental Growth Data: Stocks showing strong Year-over-Year (YoY) revenue and profit growth.

Based ONLY on the data below, select EXACTLY 10 stocks that have the highest probability of returning 15% or more growth in the next year.
If a stock is in both lists, prioritize it. Otherwise, fill the remaining spots with stocks from the Institutional Buying list that have massive volume. YOU MUST OUTPUT 10 STOCKS.

Here is the data:
{market_data}

Output your response as a JSON array containing exactly 10 objects.

Example format:
[
  {{
    "symbol": "TCS",
    "company_name": "Tata Consultancy Services",
    "predicted_growth_pct": 16,
    "reasoning": "Consistent revenue growth and strong institutional buying."
  }},
  {{
    "symbol": "RELIANCE",
    "company_name": "Reliance Industries",
    "predicted_growth_pct": 18,
    "reasoning": "High overlap in bulk deals and solid profit margins."
  }}
]

JSON Output:
[
"""

    data = {
        "model": "llama3:latest",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.4
        }
    }

    req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')

    try:
        response = urllib.request.urlopen(req, timeout=300)
        result = json.loads(response.read().decode('utf-8'))
        
        import re
        
        # Extract all JSON-like objects using regex
        # This prevents crashing if Llama 3 forgets closing brackets or adds extra text
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
            # Fallback if regex failed but it might be valid JSON
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
        return predictions
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        raise e

if __name__ == '__main__':
    print("Testing AI Analyzer...")
    res = predict_growth_stocks()
    print(json.dumps(res, indent=2))
