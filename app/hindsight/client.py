import time
import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("codemind.hindsight")

class HindsightClient:
    def __init__(self, base_url: str = None, api_key: str = None, bank_id: str = None):
        self.base_url = (base_url or settings.HINDSIGHT_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.HINDSIGHT_API_KEY
        self.bank_id = bank_id or settings.HINDSIGHT_BANK_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CodeMind/1.0"
        }
        self._memories_cache: List[Dict[str, Any]] = []
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 60.0 # 60 seconds memory cache

    async def recall(self, query: str, budget: str = "mid") -> List[Dict[str, Any]]:
        """
        Recall memories matching a query from the Hindsight bank.
        """
        if not self.api_key:
            logger.warning("HINDSIGHT_API_KEY not set. Skipping recall.")
            return []

        url = f"{self.base_url}/v1/default/banks/{self.bank_id}/memories/recall"
        payload = {
            "query": query,
            "budget": budget
        }

        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                res = await client.post(url, json=payload, headers=self.headers)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    logger.info(f"Hindsight recall returned {len(results)} items for query: '{query[:50]}'")
                    return results
                else:
                    logger.error(f"Hindsight recall failed: {res.status_code} - {res.text}")
                    return []
        except Exception as e:
            logger.error(f"Exception during Hindsight recall: {e}")
            return []

    async def retain(self, items: List[Dict[str, str]]) -> bool:
        """
        Retain new learnings into the Hindsight bank.
        items: List of dicts e.g. [{"content": "...", "context": "code_review"}]
        """
        if not self.api_key:
            logger.warning("HINDSIGHT_API_KEY not set. Skipping retain.")
            return False

        if not items:
            return True

        # Invalidate memories list cache on new retain
        self._cache_timestamp = 0.0

        url = f"{self.base_url}/v1/default/banks/{self.bank_id}/memories"
        payload = {
            "items": items
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, json=payload, headers=self.headers)
                if res.status_code == 200:
                    data = res.json()
                    logger.info(f"Hindsight retained {len(items)} items into bank '{self.bank_id}'. Success: {data.get('success')}")
                    return True
                else:
                    logger.error(f"Hindsight retain failed: {res.status_code} - {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Exception during Hindsight retain: {e}")
            return False

    async def list_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List recent memories stored in the Hindsight bank with fast local caching.
        """
        now = time.time()
        if self._memories_cache and (now - self._cache_timestamp) < self._cache_ttl:
            logger.info("Serving Hindsight list_memories from fast memory cache.")
            return self._memories_cache[:limit]

        if not self.api_key:
            return []

        url = f"{self.base_url}/v1/default/banks/{self.bank_id}/memories/list"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(url, headers=self.headers)
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    self._memories_cache = items
                    self._cache_timestamp = now
                    return items[:limit]
                return self._memories_cache[:limit]
        except Exception as e:
            logger.error(f"Exception listing Hindsight memories: {e}")
            return self._memories_cache[:limit]

hindsight_client = HindsightClient()

