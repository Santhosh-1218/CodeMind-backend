import logging
import httpx
from typing import List, Dict, Any
from app.core.config import settings
from app.llm.prompts import SYSTEM_PROMPT, build_review_prompt
from app.llm.parser import parse_and_validate_llm_json

logger = logging.getLogger("codemind.llm.groq")

class GroqClient:
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CodeMind/1.0"
        }

    async def analyze_code(
        self,
        files_data: List[Dict[str, str]],
        static_analysis_findings: List[Dict[str, Any]],
        recalled_memories: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute Groq LLM reasoning on source files, static analysis results, and recalled Hindsight memories.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY not set. Returning fallback review report.")
            return parse_and_validate_llm_json("{}")

        user_content = build_review_prompt(files_data, static_analysis_findings, recalled_memories)

        models_to_try = ["llama-3.3-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"]
        if self.model and self.model not in models_to_try and "gpt-oss" not in self.model:
            models_to_try.insert(0, self.model)

        for model_name in models_to_try:
            logger.info(f"Attempting Groq LLM completion with model: {model_name}")
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2,
                "max_tokens": 2048
            }

            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    res = await client.post(self.base_url, json=payload, headers=self.headers)
                    if res.status_code == 200:
                        res_data = res.json()
                        choices = res_data.get("choices", [])
                        if choices:
                            raw_content = choices[0].get("message", {}).get("content", "")
                            logger.info(f"Groq reasoning successful with model {model_name}.")
                            parsed_report = parse_and_validate_llm_json(raw_content)
                            return parsed_report
                    else:
                        logger.error(f"Groq API error on model {model_name}: {res.status_code} - {res.text}")
            except Exception as e:
                logger.error(f"Groq client exception on model {model_name}: {e}")

        logger.error("All Groq model attempts failed. Returning safe fallback response.")
        return parse_and_validate_llm_json("{}")

groq_client = GroqClient()
