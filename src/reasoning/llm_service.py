"""
src/reasoning/llm_service.py
LLMService: local inference backend abstraction.
Supports: llamacpp, ctransformers, mock (for testing without GPU).
No external API calls — all inference is local.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Generator, Optional

from loguru import logger

from config.settings import get_settings

settings = get_settings()


# ── Anti-hallucination system prompt ─────────────────────────────────────────

SYSTEM_PROMPT = """You are a Defence Procurement Policy Analyst for the Indian Navy.

STRICT RULES — NEVER VIOLATE:
1. Answer ONLY from the SOURCE PASSAGES provided below.
2. Every factual claim MUST be followed immediately by [SOURCE-N] where N is the source number.
3. If the answer is not present in the sources, respond EXACTLY:
   "INSUFFICIENT BASIS — the relevant policy document may not be ingested. Consult [relevant authority]."
4. Do NOT infer, extrapolate, combine, or assume rules not explicitly stated in sources.
5. Do NOT use your training knowledge about Indian defence procurement.
6. If sources contradict each other, note the contradiction explicitly.
7. Always quote the specific rule/clause/section number when available.

RESPONSE FORMAT:
- Begin with a direct answer to the question.
- Support each claim with [SOURCE-N].
- End with: "CONFIDENCE: [HIGH/MEDIUM/LOW] — [brief reason]"

You are providing information to procurement officers. Incorrect information has legal and operational consequences."""


# ── Abstract base ─────────────────────────────────────────────────────────────

class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = None) -> str:
        pass

    @abstractmethod
    def stream(self, prompt: str, max_tokens: int = None) -> Generator[str, None, None]:
        pass


# ── LlamaCPP backend ──────────────────────────────────────────────────────────

class LlamaCPPBackend(BaseLLM):
    def __init__(self):
        self._llm = None

    def _load(self):
        if self._llm is not None:
            return
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError("llama-cpp-python required: pip install llama-cpp-python")

        model_path = settings.llm_model_path
        if not model_path.exists():
            raise FileNotFoundError(
                f"LLM model not found at {model_path}. "
                f"Download a GGUF model and set LLM_MODEL_PATH in .env"
            )

        logger.info(f"Loading LlamaCPP model: {model_path}")
        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=settings.llm_n_ctx,
            n_gpu_layers=settings.llm_n_gpu_layers,
            verbose=False,
        )
        logger.info("LlamaCPP model loaded")

    def generate(self, prompt: str, max_tokens: int = None) -> str:
        self._load()
        output = self._llm(
            prompt,
            max_tokens=max_tokens or settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            stop=["</s>", "[INST]", "User:", "\n\nQuestion:"],
            echo=False,
        )
        return output["choices"][0]["text"].strip()

    def stream(self, prompt: str, max_tokens: int = None) -> Generator[str, None, None]:
        self._load()
        for chunk in self._llm(
            prompt,
            max_tokens=max_tokens or settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            stop=["</s>", "[INST]"],
            stream=True,
            echo=False,
        ):
            yield chunk["choices"][0]["text"]


# ── Mock backend (for testing without GPU/model) ──────────────────────────────

class MockLLMBackend(BaseLLM):
    """
    Deterministic mock for unit tests and development without a GPU.
    Returns a template response based on the query context.
    """

    def generate(self, prompt: str, max_tokens: int = None) -> str:
        # Extract question from prompt
        question = ""
        if "Question:" in prompt:
            question = prompt.split("Question:")[-1].strip()[:200]

        # Check if sources are present
        has_sources = "[SOURCE-1]" in prompt or "SOURCE 1:" in prompt

        if not has_sources:
            return (
                "INSUFFICIENT BASIS — the relevant policy document may not be ingested. "
                "Consult the relevant procurement authority.\n\n"
                "CONFIDENCE: LOW — No source documents available."
            )

        return (
            f"Based on the provided source documents, regarding: {question[:100]}\n\n"
            f"The applicable procurement rules specify the relevant conditions and requirements "
            f"as outlined in the policy documents [SOURCE-1]. "
            f"The Competent Financial Authority must approve procurement in accordance with "
            f"the prescribed financial limits [SOURCE-2].\n\n"
            f"Officers are advised to verify the current version of the policy document "
            f"and consult the relevant authority for case-specific guidance [SOURCE-1].\n\n"
            f"CONFIDENCE: MEDIUM — Mock response; replace with real LLM for production."
        )

    def stream(self, prompt: str, max_tokens: int = None) -> Generator[str, None, None]:
        response = self.generate(prompt)
        # Stream word by word
        for word in response.split():
            yield word + " "


# ── LLM Service ───────────────────────────────────────────────────────────────

class LLMService:
    """Facade that selects the correct backend based on settings."""

    _instance: Optional["LLMService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._backend = None
        return cls._instance

    def _get_backend(self) -> BaseLLM:
        if self._backend is not None:
            return self._backend
        backend_name = settings.llm_backend
        if backend_name == "llamacpp":
            self._backend = LlamaCPPBackend()
        elif backend_name == "mock":
            self._backend = MockLLMBackend()
            logger.warning("Using MockLLM — responses are synthetic. Set LLM_BACKEND=llamacpp for production.")
        else:
            raise ValueError(f"Unknown LLM backend: {backend_name}. Supported: llamacpp, mock")
        return self._backend

    def build_prompt(self, question: str, context_chunks: list[dict]) -> str:
        """Build the full prompt with system instructions and retrieved context."""
        sources_text = ""
        for i, chunk in enumerate(context_chunks, 1):
            sources_text += (
                f"\n--- SOURCE {i} ---\n"
                f"Document: {chunk.get('doc_filename', 'Unknown')}\n"
                f"Section: {chunk.get('section_id', '')} | Clause: {chunk.get('clause_id', '')}\n"
                f"Pages: {chunk.get('page_numbers', [])}\n"
                f"{'[OCR - LOW CONFIDENCE]' if chunk.get('ocr_uncertain') else ''}\n"
                f"Content:\n{chunk.get('text', '')}\n"
            )

        prompt = (
            f"[INST] <<SYS>>\n{SYSTEM_PROMPT}\n<</SYS>>\n\n"
            f"SOURCE PASSAGES:\n{sources_text}\n\n"
            f"Question: {question}\n"
            f"[/INST]\n"
            f"Answer:"
        )
        return prompt

    def generate(self, question: str, context_chunks: list[dict]) -> str:
        """Generate a response. Blocks until complete."""
        prompt = self.build_prompt(question, context_chunks)
        return self._get_backend().generate(prompt)

    def stream(self, question: str, context_chunks: list[dict]) -> Generator[str, None, None]:
        """Stream a response token by token."""
        prompt = self.build_prompt(question, context_chunks)
        yield from self._get_backend().stream(prompt)


def get_llm() -> LLMService:
    return LLMService()