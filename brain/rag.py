"""
AI-INFLUENCER-OS — RAG Knowledge Base Layer
Retrieves product details, pricing, discount codes, and affiliate links from catalog.
"""

import os
import json
from typing import List, Dict, Optional


class ProductKnowledgeBase:
    """Lightweight local RAG retrieval for brand products and FAQs."""

    def __init__(self, brands_path: Optional[str] = None):
        if brands_path is None:
            brands_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "brands.json")
        self.brands_path = brands_path
        self.products = self._load_products()

    def _load_products(self) -> List[Dict]:
        if not os.path.exists(self.brands_path):
            return []
        try:
            with open(self.brands_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("brands", [])
        except Exception as e:
            print(f"Error loading brands catalog: {e}")
            return []

    def query(self, text: str, threshold: int = 1) -> Optional[Dict]:
        """Find the most relevant product from user's message."""
        lower = text.lower()
        best_match = None
        best_score = 0

        for p in self.products:
            score = 0
            name_words = p.get("name", "").lower().split()
            prod_words = p.get("product", "").lower().split()

            for w in name_words + prod_words:
                if len(w) > 2 and w in lower:
                    score += 2

            # Check keywords like price, cost, link, buy, discount
            if any(k in lower for k in ["price", "cost", "kitne", "paisa", "rupaye", "discount", "code", "link", "kareedna"]):
                score += 1

            if score > best_score and score >= threshold:
                best_score = score
                best_match = p

        return best_match

    def format_product_context(self, product: Dict) -> str:
        """Format product facts for LLM injection."""
        return (
            f"PRODUCT INFO: Brand: {product.get('name')}, Product: {product.get('product')}, "
            f"Price: {product.get('price')}, Pitch: {product.get('pitch')}, Link: {product.get('link')}"
        )
