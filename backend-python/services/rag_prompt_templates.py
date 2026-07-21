"""
Token-Optimized RAG Prompt Templates & Context Compression Utilities.
Designed to minimize LLM token consumption (input & output) while maximizing response accuracy.
"""
import re


SYSTEM_PROMPT_CONCISE = """You are an expert Indian stock market financial assistant.
Rules:
1. Provide a clear, direct, and actionable answer based on the provided context items (IPOs, Mutual Funds, Bulk/Block Deals, Compounder Stocks).
2. If the user asks for investment recommendations or stock picks, suggest top stocks or mutual funds from the provided context with key metrics.
3. Be direct and concise. Omit unnecessary intros and generic filler.
4. Output Markdown bullet points or clear structured text.
"""

SYSTEM_PROMPT_JSON = """You are a precise data extractor.
Rules:
1. Extract requested fields using ONLY the provided context.
2. Output valid JSON strictly adhering to the schema.
3. No conversational prose, commentary, or markdown formatting outside JSON.
"""


def compress_context(context_chunks, query, max_sentences=6, max_tokens=350):
    """
    Extracts the most relevant sentences from context chunks based on query term overlap,
    trimming context down to ~300-400 tokens max.
    """
    if not context_chunks:
        return ""

    if isinstance(context_chunks, str):
        context_chunks = [context_chunks]

    query_words = set(re.findall(r'\w+', query.lower()))
    # Remove common stop words
    stop_words = {'what', 'is', 'the', 'a', 'an', 'in', 'on', 'of', 'for', 'and', 'or', 'to', 'how', 'do', 'does', 'show', 'get'}
    query_terms = query_words - stop_words
    if not query_terms:
        query_terms = query_words

    scored_sentences = []
    
    for chunk in context_chunks:
        # Split chunk into sentences or lines
        sentences = re.split(r'[\n\r]+|(?<=[.!?])\s+', chunk)
        for sentence in sentences:
            sentence_clean = sentence.strip()
            if len(sentence_clean) < 10:
                continue
                
            sentence_words = set(re.findall(r'\w+', sentence_clean.lower()))
            overlap = len(query_terms.intersection(sentence_words))
            
            # Count matches
            scored_sentences.append((overlap, sentence_clean))
                
    # Sort by highest relevance score
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    
    selected_sentences = []
    current_length = 0
    
    for score, sentence in scored_sentences:
        words_count = len(sentence.split())
        if current_length + words_count > max_tokens:
            break
        selected_sentences.append(sentence)
        current_length += words_count
        if len(selected_sentences) >= max_sentences:
            break
            
    if not selected_sentences:
        # Fallback: return first chunk truncated to max_tokens
        first_chunk = context_chunks[0]
        words = first_chunk.split()[:max_tokens]
        return " ".join(words)
        
    return " ".join(selected_sentences)


def build_rag_user_prompt(compressed_context, user_query, output_format="bullet"):
    """
    Formats the final compact user prompt with compressed context.
    """
    if output_format == "json":
        format_spec = "Return JSON format: {\"answer\": \"...\", \"key_points\": [\"...\"]}"
    else:
        format_spec = "- Direct Answer: <1 sentence>\n- Details: <max 3 points>"

    return f"""[CONTEXT]
{compressed_context}

[QUERY]
{user_query}

[FORMAT]
{format_spec}"""
