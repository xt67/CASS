import json

import httpx
from typing import AsyncIterator

from cass.core.llm import LlmProvider, LlmMessage, LlmResponse, Role


class OllamaProvider(LlmProvider):
    """LLM provider using local Ollama installation."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def _format_messages(self, messages: list[LlmMessage]) -> list[dict]:
        """Convert LlmMessage objects to Ollama format."""
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]

    async def chat(self, messages: list[LlmMessage]) -> LlmResponse:
        """Send messages to Ollama and get a response."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "options": {"num_predict": 2048},
                    "messages": self._format_messages(messages),
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return LlmResponse(
                content=data["message"]["content"],
                model=self.model,
                tokens_used=data.get("eval_count", 0)
            )

    async def chat_stream(self, messages: list[LlmMessage]) -> AsyncIterator[str]:
        """Stream response from Ollama token by token."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "options": {"num_predict": 2048},
                    "messages": self._format_messages(messages),
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data:
                            yield data["message"]["content"]
