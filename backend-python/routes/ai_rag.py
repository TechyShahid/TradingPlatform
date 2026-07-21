"""
RAG API Routes — Token-Efficient AI Assistant Endpoint.
Exposes /api/ai/ask endpoint powered by TokenEfficientRAGEngine.
"""
import config
from flask import Blueprint, request, jsonify
import database
from services.rag_service import rag_engine
import ai_analyzer

ai_rag_bp = Blueprint('ai_rag', __name__)


def sync_platform_data_to_rag():
    """Syncs live database data (IPOs, Mutual Funds, Bulk/Block Deals, Consistent Compounders) into RAG engine with item-level granularity."""
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        docs = []

        # 1. Fetch & Index IPOs
        cur.execute("SELECT company_name, symbol, status, retail_x, hni_x, qib_x, total_x, issue_start_date, issue_end_date FROM ipos LIMIT 50")
        ipos = cur.fetchall()
        for idx, ipo in enumerate(ipos):
            docs.append({
                "id": f"ipo_{ipo['symbol']}_{idx}",
                "content": f"IPO Offering: {ipo['company_name']} ({ipo['symbol']}) | Status: {ipo['status']} | Retail Subscription: {ipo['retail_x']}x | HNI Subscription: {ipo['hni_x']}x | QIB Subscription: {ipo['qib_x']}x | Total Subscription Demand: {ipo['total_x']}x | Issue Start Date: {ipo['issue_start_date']} | Issue End Date: {ipo['issue_end_date']}"
            })

        # 2. Fetch & Index Mutual Funds
        cur.execute("SELECT amfi_code, scheme_name, category, sub_category, return_1y, return_3y, return_5y, expense_ratio FROM funds LIMIT 60")
        funds = cur.fetchall()
        for idx, f in enumerate(funds):
            docs.append({
                "id": f"fund_{f['amfi_code']}_{idx}",
                "content": f"Mutual Fund Scheme: {f['scheme_name']} (AMFI: {f['amfi_code']}) | Category: {f['category']} ({f['sub_category']}) | 1-Year Return: {f['return_1y']}% | 3-Year Return (3Y Return): {f['return_3y']}% | 5-Year Return (5Y Return): {f['return_5y']}% | Expense Ratio: {f['expense_ratio']}%"
            })

        # 3. Fetch & Index Bulk & Block Deals
        cur.execute("SELECT deal_date, symbol, security_name, client_name, buy_sell, quantity_traded, trade_price, 'Bulk Deal' as deal_type FROM bulk_deals ORDER BY deal_date DESC LIMIT 40")
        bulk_deals = cur.fetchall()
        
        cur.execute("SELECT deal_date, symbol, security_name, client_name, buy_sell, quantity_traded, trade_price, 'Block Deal' as deal_type FROM block_deals ORDER BY deal_date DESC LIMIT 40")
        block_deals = cur.fetchall()

        for idx, d in enumerate(bulk_deals + block_deals):
            sec = d.get('security_name', d['symbol'])
            docs.append({
                "id": f"deal_{d['symbol']}_{idx}",
                "content": f"NSE {d['deal_type']} Transaction: {d['symbol']} ({sec}) | Deal Date: {d['deal_date']} | Client Investor: {d['client_name']} | Action: {d['buy_sell']} | Shares Traded: {d['quantity_traded']:,} shares @ Rs.{d['trade_price']}"
            })

        # 4. Fetch & Index Consistent Compounder Stocks (Short/Long term stock investment picks)
        cur.execute("SELECT symbol, avg_3yr_growth_pct, ai_driving_factor FROM consistent_compounders ORDER BY avg_3yr_growth_pct DESC LIMIT 20")
        compounders = cur.fetchall()
        for idx, c in enumerate(compounders):
            docs.append({
                "id": f"compounder_{c['symbol']}_{idx}",
                "content": f"Top Stock Pick / High Return Stock to Invest In: {c['symbol']} | 3-Year CAGR Growth: {c['avg_3yr_growth_pct']}% | Growth Driver: {c['ai_driving_factor']}"
            })

        conn.close()

        # Reset, clear cache and re-index
        rag_engine.query_cache.clear()
        rag_engine.documents = []
        rag_engine.chunks = []
        rag_engine.add_documents(docs)
    except Exception as e:
        print(f"[RAG Route] Error syncing platform data to RAG: {e}")


GREETINGS_MAP = {
    ("hi", "hello", "hey", "kem cho", "kemcho", "hie", "namaste", "good morning", "good evening", "good afternoon"): 
        "Kem Cho! Majama? I am **Mota Bhai**, your AI Financial Copilot. Ask me anything about stocks, IPOs, mutual funds, or bulk/block deals!",
    
    ("how are you", "how r u", "how are u", "how do you do", "kem cho mota bhai", "how r u mota bhai", "how are you mota bhai"): 
        "Ekdam Majama! I am ready to help you analyze Indian stock markets, top IPOs, mutual funds, and large institutional deals. What would you like to explore today?",
    
    ("who are you", "what is your name", "who r u", "who is mota bhai", "tell me about yourself", "what are you"): 
        "I am **Mota Bhai** 👳‍♂️ — your smart, token-efficient AI Copilot for Indian stock markets! I analyze live data for IPOs, Mutual Funds, Bulk/Block Deals, and Compounder Stocks.",
    
    ("what can you do", "help", "features", "how to use", "what can u do"): 
        "Here is what I can do for you:\n- 📈 Recommend top compounder stocks to invest in\n- 🔥 Track active IPO subscription demand\n- 💼 Analyze Mutual Fund returns & expense ratios\n- 🤝 Track institutional Bulk & Block deals on NSE",
    
    ("thank you", "thanks", "dhanyawad", "shukriya", "great", "awesome", "nice"): 
        "You're welcome! Tamaro Aabhar! Feel free to ask if you have more questions about stocks or markets."
}


def detect_greeting_response(query):
    clean = query.strip().lower()
    clean_words = "".join([c for c in clean if c.isalnum() or c.isspace()]).strip()
    
    for keywords, response in GREETINGS_MAP.items():
        for kw in keywords:
            if clean_words == kw or clean_words == f"{kw} mota bhai" or clean_words == f"mota bhai {kw}":
                return response
    return None


@ai_rag_bp.route('/api/ai/ask', methods=['POST'])
def ask_ai_rag():
    """
    Token-Efficient RAG Endpoint.
    Receives JSON body: {"query": "..."}
    Returns: {"answer": "...", "tokens_estimated": int, "cached": bool}
    """
    try:
        data = request.get_json() or {}
        user_query = data.get("query", "").strip()
        
        if not user_query:
            return jsonify({"error": "Query parameter is required."}), 400

        # 1. Check 0-token Semantic Cache
        cached_response = rag_engine.get_cached_response(user_query)
        if cached_response:
            return jsonify({
                "answer": cached_response,
                "cached": True,
                "estimated_tokens_used": 0,
                "message": "Response returned from 0-token semantic cache."
            })

        # 2. Sync fresh platform data (IPOs, Funds, Bulk & Block Deals)
        sync_platform_data_to_rag()

        # 3. Prepare Token-Minimized Prompt
        rag_prompt = rag_engine.prepare_rag_prompt(user_query, top_k=5, max_context_tokens=600)

        # 4. Dynamic LLM Completion (Groq Llama 3 / Gemini / Heuristic Fallback)
        answer = ai_analyzer.call_llm_text_completion(rag_prompt['system_prompt'], rag_prompt['user_prompt'])
        
        if not answer:
            # Smart Fallback if LLM API is unreachable
            answer = f"Kem Cho! I analyzed the platform database for '{user_query}':\n\n{rag_prompt['compressed_context']}"

        # 5. Cache response for future identical queries
        rag_engine.cache_response(user_query, answer)

        return jsonify({
            "answer": answer,
            "cached": False,
            "estimated_tokens_used": rag_prompt["estimated_input_tokens"],
            "retrieved_documents_count": rag_prompt["retrieved_count"]
        })
    except Exception as e:
        print(f"[RAG Route] Exception in ask_ai_rag: {e}")
        return jsonify({"error": str(e)}), 500
