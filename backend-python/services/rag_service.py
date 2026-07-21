"""
Token-Efficient RAG Service.
Implements fast document chunking, lightweight TF-IDF / vector search,
sentence-level context compression, and query-response caching to minimize LLM token usage.
"""
import re
import math
import hashlib
import time
import numpy as np
from services.rag_prompt_templates import (
    SYSTEM_PROMPT_CONCISE,
    SYSTEM_PROMPT_JSON,
    compress_context,
    build_rag_user_prompt
)


class TokenEfficientRAGEngine:
    def __init__(self, chunk_size=350, chunk_overlap=40):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.documents = []  # List of dicts: {"id": str, "content": str, "metadata": dict}
        self.chunks = []     # List of dicts: {"id": str, "text": str, "doc_id": str}
        self.vocab = {}      # Term -> index
        self.idf = np.array([])
        self.tfidf_matrix = None
        self.query_cache = {} # MD5 hash -> {"response": str, "timestamp": float}

    def _tokenize(self, text):
        return re.findall(r'\b[a-zA-Z0-9_]{2,}\b', text.lower())

    def add_documents(self, docs):
        """
        Ingests documents, chunks them, and builds a TF-IDF vector index.
        docs: List of dicts with keys 'id', 'content', and optional 'metadata'.
        """
        for doc in docs:
            doc_id = doc.get("id", str(len(self.documents)))
            content = doc.get("content", "")
            self.documents.append({"id": doc_id, "content": content, "metadata": doc.get("metadata", {})})
            
            # Chunking logic
            words = content.split()
            step = max(1, self.chunk_size - self.chunk_overlap)
            for i in range(0, len(words), step):
                chunk_text = " ".join(words[i:i + self.chunk_size])
                if len(chunk_text.strip()) > 20:
                    self.chunks.append({
                        "id": f"{doc_id}_chunk_{len(self.chunks)}",
                        "text": chunk_text,
                        "doc_id": doc_id
                    })
                    
        self._build_index()

    def _build_index(self):
        """Builds TF-IDF matrix for all chunks."""
        if not self.chunks:
            return

        doc_freq = {}
        total_chunks = len(self.chunks)
        
        chunk_tokens_list = []
        for chunk in self.chunks:
            tokens = set(self._tokenize(chunk["text"]))
            chunk_tokens_list.append(tokens)
            for t in tokens:
                doc_freq[t] = doc_freq.get(t, 0) + 1
                
        # Build vocabulary
        self.vocab = {term: idx for idx, term in enumerate(sorted(doc_freq.keys()))}
        vocab_size = len(self.vocab)
        
        # Calculate IDF
        self.idf = np.zeros(vocab_size)
        for term, idx in self.vocab.items():
            self.idf[idx] = math.log((total_chunks + 1) / (doc_freq[term] + 1)) + 1.0

        # Calculate TF-IDF matrix
        self.tfidf_matrix = np.zeros((total_chunks, vocab_size))
        for i, tokens in enumerate(chunk_tokens_list):
            token_counts = {}
            raw_tokens = self._tokenize(self.chunks[i]["text"])
            for t in raw_tokens:
                if t in self.vocab:
                    token_counts[t] = token_counts.get(t, 0) + 1
                    
            for term, count in token_counts.items():
                idx = self.vocab[term]
                tf = count / max(1, len(raw_tokens))
                self.tfidf_matrix[i, idx] = tf * self.idf[idx]

        # Normalize TF-IDF vectors
        norms = np.linalg.norm(self.tfidf_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.tfidf_matrix = self.tfidf_matrix / norms

    def retrieve_chunks(self, query, top_k=3):
        """Retrieves the top_k most relevant chunks using Cosine Similarity."""
        if self.tfidf_matrix is None or len(self.chunks) == 0:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return self.chunks[:top_k]

        vocab_size = len(self.vocab)
        query_vec = np.zeros(vocab_size)
        
        token_counts = {}
        for t in query_tokens:
            if t in self.vocab:
                token_counts[t] = token_counts.get(t, 0) + 1

        for term, count in token_counts.items():
            idx = self.vocab[term]
            tf = count / max(1, len(query_tokens))
            query_vec[idx] = tf * self.idf[idx]

        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm

        scores = np.dot(self.tfidf_matrix, query_vec)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0.01:
                results.append({
                    "chunk": self.chunks[idx],
                    "score": float(scores[idx])
                })
        return results

    def get_cached_response(self, query, cache_ttl=3600):
        """Checks for cached query response."""
        query_hash = hashlib.md5(query.strip().lower().encode('utf-8')).hexdigest()
        if query_hash in self.query_cache:
            entry = self.query_cache[query_hash]
            if time.time() - entry["timestamp"] < cache_ttl:
                return entry["response"]
        return None

    def cache_response(self, query, response):
        """Caches query response."""
        query_hash = hashlib.md5(query.strip().lower().encode('utf-8')).hexdigest()
        self.query_cache[query_hash] = {
            "response": response,
            "timestamp": time.time()
        }

    def prepare_rag_prompt(self, query, top_k=3, max_context_tokens=300, output_format="bullet"):
        """
        Retrieves relevant chunks, compresses context to max_context_tokens,
        and constructs the token-optimized system and user prompt pair.
        """
        # 1. Retrieve top chunks
        retrieved = self.retrieve_chunks(query, top_k=top_k)
        raw_chunks = [r["chunk"]["text"] for r in retrieved]

        # 2. Compress context (sentence extraction)
        compressed = compress_context(raw_chunks, query, max_tokens=max_context_tokens)

        # 3. Choose System Prompt
        system_prompt = SYSTEM_PROMPT_JSON if output_format == "json" else SYSTEM_PROMPT_CONCISE

        # 4. Build User Prompt
        user_prompt = build_rag_user_prompt(compressed, query, output_format=output_format)

        # Estimate Tokens (approx 4 chars per token)
        est_input_tokens = len(system_prompt.split()) + len(user_prompt.split())

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "compressed_context": compressed,
            "retrieved_count": len(retrieved),
            "estimated_input_tokens": est_input_tokens
        }


# Singleton instance for quick application usage
rag_engine = TokenEfficientRAGEngine()
