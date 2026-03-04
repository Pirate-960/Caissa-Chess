"""
core/model_discovery.py

Model discovery for all supported LLM providers.
Queries each provider's API to list available models, optionally including
preview / experimental variants.  Results are categorised and sorted so the
interactive CLI can present them in a user-friendly way.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# MODEL CATEGORISATION
# =============================================================================

class ModelTier(str, Enum):
    """Stability tier for a model."""
    STABLE      = "stable"        # Generally Available (GA)
    PREVIEW     = "preview"       # Preview / beta
    EXPERIMENTAL = "experimental"  # Experimental / snapshot
    DEPRECATED  = "deprecated"    # End-of-life / sunset
    UNKNOWN     = "unknown"       # Cannot determine


@dataclass
class ModelInfo:
    """Metadata for a single model."""
    id: str                         # e.g. "gpt-4o", "claude-3-5-sonnet-20241022"
    provider: str                   # e.g. "openai", "anthropic", "gemini"
    tier: ModelTier = ModelTier.UNKNOWN
    display_name: str = ""          # friendly label (falls back to id)
    description: str = ""           # one-line description
    context_window: Optional[int] = None  # max input tokens
    owned_by: str = ""              # owner / org string from the API
    tags: List[str] = field(default_factory=list)  # extra tags
    # ── verbose / extended fields ──
    output_tokens: Optional[int] = None   # max output tokens
    version: str = ""               # model version string
    temperature: Optional[float] = None   # default temperature
    top_p: Optional[float] = None         # default top_p
    top_k: Optional[int] = None           # default top_k
    supported_methods: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.id

    @property
    def tier_badge(self) -> str:
        """Short coloured badge string for the tier (plain-text fallback)."""
        return {
            ModelTier.STABLE:       "[GA]",
            ModelTier.PREVIEW:      "[Preview]",
            ModelTier.EXPERIMENTAL: "[Exp]",
            ModelTier.DEPRECATED:   "[Deprecated]",
            ModelTier.UNKNOWN:      "",
        }.get(self.tier, "")


# =============================================================================
# TIER CLASSIFICATION HELPERS
# =============================================================================

# Keywords in model IDs that signal non-GA status.
_PREVIEW_KEYWORDS  = ("preview", "beta", "canary")
_EXP_KEYWORDS      = ("exp", "experimental", "snapshot", "thinking", "search",
                       "realtime", "audio", "transcribe", "tts")
_DEPRECATED_KEYWORDS = ("0301", "0314", "instruct", "vision", "1106")


def _classify_openai(model_id: str, owned_by: str = "") -> ModelTier:
    """Classify an OpenAI model into a tier."""
    mid = model_id.lower()

    if any(k in mid for k in _DEPRECATED_KEYWORDS):
        return ModelTier.DEPRECATED
    if any(k in mid for k in _PREVIEW_KEYWORDS):
        return ModelTier.PREVIEW
    if any(k in mid for k in _EXP_KEYWORDS):
        return ModelTier.EXPERIMENTAL

    # Chat-oriented GA models
    ga_patterns = ("gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
                   "o1", "o3", "o4")
    if any(mid.startswith(p) for p in ga_patterns):
        return ModelTier.STABLE

    # Everything else (embeddings, dall-e, whisper, fine-tunes, etc.)
    return ModelTier.UNKNOWN


def _classify_gemini(model_name: str) -> ModelTier:
    """Classify a Gemini model into a tier."""
    mn = model_name.lower()
    if "exp" in mn or "thinking" in mn:
        return ModelTier.EXPERIMENTAL
    if "preview" in mn or "beta" in mn:
        return ModelTier.PREVIEW
    if "1.0" in mn or "deprecated" in mn:
        return ModelTier.DEPRECATED
    return ModelTier.STABLE


def _classify_anthropic(model_id: str) -> ModelTier:
    """Classify an Anthropic model into a tier."""
    mid = model_id.lower()
    if "preview" in mid or "beta" in mid:
        return ModelTier.PREVIEW
    return ModelTier.STABLE


def _classify_deepseek(model_id: str) -> ModelTier:
    """Classify a DeepSeek model into a tier."""
    mid = model_id.lower()
    if "beta" in mid or "preview" in mid:
        return ModelTier.PREVIEW
    return ModelTier.STABLE


# =============================================================================
# PROVIDER-SPECIFIC DISCOVERY
# =============================================================================

def _discover_openai(
    api_key: str,
    include_preview: bool = False,
    base_url: Optional[str] = None,
    provider_label: str = "openai",
) -> List[ModelInfo]:
    """List models via the OpenAI-compatible /v1/models endpoint."""
    from openai import OpenAI

    kwargs: Dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)
    raw = client.models.list()

    models: List[ModelInfo] = []
    for m in raw.data:
        mid = m.id
        owned = getattr(m, "owned_by", "")

        if provider_label == "deepseek":
            tier = _classify_deepseek(mid)
        else:
            tier = _classify_openai(mid, owned)

        # Skip non-chat models unless preview mode is on
        if not include_preview:
            if tier in (ModelTier.EXPERIMENTAL, ModelTier.DEPRECATED,
                        ModelTier.UNKNOWN):
                continue

        models.append(ModelInfo(
            id=mid,
            provider=provider_label,
            tier=tier,
            owned_by=owned,
        ))

    models.sort(key=lambda m: (m.tier.value, m.id))
    return models


def _discover_anthropic(
    api_key: str,
    include_preview: bool = False,
) -> List[ModelInfo]:
    """
    Discover Anthropic models.

    Anthropic's API has a /v1/models endpoint (added 2024-07).
    We try the SDK method first and fall back to a curated list.
    """
    models: List[ModelInfo] = []

    # --- Try SDK list_models first (anthropic>=0.35) -------------------------
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        # The SDK exposes client.models.list() since v0.35
        page = client.models.list(limit=100)
        for m in page.data:
            mid = m.id
            tier = _classify_anthropic(mid)
            if not include_preview and tier != ModelTier.STABLE:
                continue
            display = getattr(m, "display_name", mid)
            models.append(ModelInfo(
                id=mid,
                provider="anthropic",
                tier=tier,
                display_name=display,
            ))
        if models:
            models.sort(key=lambda m: (m.tier.value, m.id))
            return models
    except Exception:
        logger.debug("Anthropic SDK models.list() unavailable — using curated list")

    # --- Fallback: curated list ---------------------------------------------
    _KNOWN = [
        # Claude 4 family
        ("claude-sonnet-4-20250514", ModelTier.STABLE, "Claude Sonnet 4"),
        ("claude-opus-4-20250514", ModelTier.STABLE, "Claude Opus 4"),
        # Claude 3.7 family
        ("claude-3-7-sonnet-20250219", ModelTier.STABLE, "Claude 3.7 Sonnet"),
        # Claude 3.5 family
        ("claude-3-5-sonnet-20241022", ModelTier.STABLE, "Claude 3.5 Sonnet v2"),
        ("claude-3-5-sonnet-20240620", ModelTier.STABLE, "Claude 3.5 Sonnet v1"),
        ("claude-3-5-haiku-20241022", ModelTier.STABLE, "Claude 3.5 Haiku"),
        # Claude 3 family
        ("claude-3-opus-20240229", ModelTier.STABLE, "Claude 3 Opus"),
        ("claude-3-sonnet-20240229", ModelTier.STABLE, "Claude 3 Sonnet"),
        ("claude-3-haiku-20240307", ModelTier.STABLE, "Claude 3 Haiku"),
    ]

    for mid, tier, name in _KNOWN:
        if not include_preview and tier != ModelTier.STABLE:
            continue
        models.append(ModelInfo(
            id=mid,
            provider="anthropic",
            tier=tier,
            display_name=name,
        ))

    return models


def _discover_gemini_new_sdk(
    api_key: str,
    include_preview: bool = False,
) -> List[ModelInfo]:
    """List models using the new ``google-genai`` SDK (``google.genai``)."""
    from google import genai

    client = genai.Client(api_key=api_key)

    models: List[ModelInfo] = []
    for m in client.models.list():
        name = getattr(m, "name", "") or ""
        short = name.replace("models/", "") if name.startswith("models/") else name

        # New SDK uses 'supported_actions' instead of 'supported_generation_methods'
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" not in actions:
            continue

        tier = _classify_gemini(short)
        if not include_preview and tier in (ModelTier.EXPERIMENTAL,
                                            ModelTier.DEPRECATED,
                                            ModelTier.UNKNOWN):
            continue

        ctx = getattr(m, "input_token_limit", None)
        desc = getattr(m, "description", "") or ""
        display = getattr(m, "display_name", short) or short

        models.append(ModelInfo(
            id=short,
            provider="gemini",
            tier=tier,
            display_name=display,
            description=desc[:120] if desc else "",
            context_window=ctx,
            output_tokens=getattr(m, "output_token_limit", None),
            version=getattr(m, "version", "") or "",
            # New SDK Model objects don't expose temperature/top_p/top_k
            supported_methods=list(actions),
        ))

    models.sort(key=lambda m: (m.tier.value, m.id))
    return models


def _discover_gemini_old_sdk(
    api_key: str,
    include_preview: bool = False,
) -> List[ModelInfo]:
    """List models using the deprecated ``google-generativeai`` SDK."""
    import google.generativeai as genai
    genai.configure(api_key=api_key)

    models: List[ModelInfo] = []
    for m in genai.list_models():
        name = m.name  # e.g. "models/gemini-2.5-pro"
        short = name.replace("models/", "") if name.startswith("models/") else name

        methods = getattr(m, "supported_generation_methods", [])
        if "generateContent" not in methods:
            continue

        tier = _classify_gemini(short)
        if not include_preview and tier in (ModelTier.EXPERIMENTAL,
                                            ModelTier.DEPRECATED,
                                            ModelTier.UNKNOWN):
            continue

        ctx = getattr(m, "input_token_limit", None)
        desc = getattr(m, "description", "")
        display = getattr(m, "display_name", short)

        models.append(ModelInfo(
            id=short,
            provider="gemini",
            tier=tier,
            display_name=display,
            description=desc[:120] if desc else "",
            context_window=ctx,
            output_tokens=getattr(m, "output_token_limit", None),
            version=getattr(m, "version", "") or "",
            temperature=getattr(m, "temperature", None),
            top_p=getattr(m, "top_p", None),
            top_k=getattr(m, "top_k", None),
            supported_methods=list(methods),
        ))

    models.sort(key=lambda m: (m.tier.value, m.id))
    return models


def _discover_gemini_rest(
    api_key: str,
    include_preview: bool = False,
) -> List[ModelInfo]:
    """List models via the Google Generative AI REST API.

    Avoids SDK deserialization issues (e.g. unexpected ``max_temperature``
    field) by calling the REST endpoint directly.
    """
    import requests as _req

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    resp = _req.get(url, params={"key": api_key}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    models: List[ModelInfo] = []
    for entry in data.get("models", []):
        name = entry.get("name", "")
        short = name.replace("models/", "") if name.startswith("models/") else name

        methods = entry.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue

        tier = _classify_gemini(short)
        if not include_preview and tier in (ModelTier.EXPERIMENTAL,
                                            ModelTier.DEPRECATED,
                                            ModelTier.UNKNOWN):
            continue

        ctx = entry.get("inputTokenLimit")
        desc = entry.get("description", "")
        display = entry.get("displayName", short)

        models.append(ModelInfo(
            id=short,
            provider="gemini",
            tier=tier,
            display_name=display,
            description=desc[:120] if desc else "",
            context_window=ctx,
            output_tokens=entry.get("outputTokenLimit"),
            version=entry.get("version", "") or "",
            temperature=entry.get("temperature"),
            top_p=entry.get("topP"),
            top_k=entry.get("topK"),
            supported_methods=list(methods),
        ))

    models.sort(key=lambda m: (m.tier.value, m.id))
    return models


# Possible SDK-check statuses returned alongside Gemini results.
GEMINI_NEW_SDK_OK         = "new_sdk_ok"      # google.genai worked
GEMINI_OLD_SDK_OK         = "old_sdk_ok"      # google.generativeai (deprecated) worked
GEMINI_SDK_OK             = "sdk_ok"          # alias — kept for backward compat
GEMINI_SDK_NOT_INSTALLED  = "sdk_not_installed"
GEMINI_SDK_ERROR          = "sdk_error"
GEMINI_REST_FALLBACK      = "rest_fallback"


def _discover_gemini(
    api_key: str,
    include_preview: bool = False,
) -> tuple:
    """Discover Gemini models — 3-tier: new SDK → old SDK → REST.

    Returns:
        ``(models_list, sdk_status, sdk_error_detail)``

    *sdk_status* is one of ``GEMINI_NEW_SDK_OK``, ``GEMINI_OLD_SDK_OK``,
    ``GEMINI_SDK_NOT_INSTALLED``, or ``GEMINI_SDK_ERROR``.
    """
    errors_collected: List[str] = []

    # 1. Try new SDK (google.genai)
    try:
        from google import genai  # noqa: F401
        new_sdk_installed = True
    except ImportError:
        new_sdk_installed = False

    if new_sdk_installed:
        try:
            models = _discover_gemini_new_sdk(api_key, include_preview)
            return models, GEMINI_NEW_SDK_OK, None
        except Exception as exc:
            logger.debug("New Gemini SDK (google.genai) failed: %s", exc)
            errors_collected.append(f"google.genai: {exc}")

    # 2. Try old/deprecated SDK (google.generativeai)
    try:
        import google.generativeai  # noqa: F401
        old_sdk_installed = True
    except ImportError:
        old_sdk_installed = False

    if old_sdk_installed:
        try:
            models = _discover_gemini_old_sdk(api_key, include_preview)
            return models, GEMINI_OLD_SDK_OK, None
        except Exception as exc:
            logger.debug("Old Gemini SDK (google.generativeai) failed: %s", exc)
            errors_collected.append(f"google.generativeai: {exc}")

    # 3. REST fallback
    models = _discover_gemini_rest(api_key, include_preview)

    if not new_sdk_installed and not old_sdk_installed:
        return models, GEMINI_SDK_NOT_INSTALLED, None
    else:
        detail = "; ".join(errors_collected) if errors_collected else None
        return models, GEMINI_SDK_ERROR, detail


def _discover_ollama(
    base_url: str = "http://localhost:11434",
) -> List[ModelInfo]:
    """List locally-pulled Ollama models via ``/api/tags``."""
    import requests

    resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    models: List[ModelInfo] = []
    for entry in data.get("models", []):
        name = entry.get("name", "")
        size = entry.get("size", 0)
        desc = f"{size / 1e9:.1f} GB" if size else ""

        models.append(ModelInfo(
            id=name,
            provider="ollama",
            tier=ModelTier.STABLE,
            display_name=name,
            description=desc,
        ))

    models.sort(key=lambda m: m.id)
    return models


def _discover_azure(
    api_key: str,
    endpoint: str,
    api_version: str = "2024-02-15-preview",
    include_preview: bool = False,
) -> List[ModelInfo]:
    """List models available in an Azure OpenAI resource."""
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=endpoint,
    )
    raw = client.models.list()

    models: List[ModelInfo] = []
    for m in raw.data:
        mid = m.id
        tier = _classify_openai(mid)
        if not include_preview and tier in (ModelTier.EXPERIMENTAL,
                                            ModelTier.DEPRECATED,
                                            ModelTier.UNKNOWN):
            continue
        models.append(ModelInfo(
            id=mid,
            provider="azure",
            tier=tier,
            owned_by=getattr(m, "owned_by", ""),
        ))

    models.sort(key=lambda m: (m.tier.value, m.id))
    return models


# =============================================================================
# UNIFIED ENTRY POINT
# =============================================================================

@dataclass
class DiscoveryResult:
    """Result of a model discovery call."""
    models: List[ModelInfo]
    error: Optional[str] = None
    sdk_status: Optional[str] = None   # Gemini-specific: sdk_ok / sdk_not_installed / sdk_error
    sdk_detail: Optional[str] = None   # e.g. the SDK exception message


def discover_models(
    provider_name: str,
    *,
    include_preview: bool = False,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    azure_api_version: str = "2024-02-15-preview",
    cfg=None,
) -> DiscoveryResult:
    """
    Discover models available for a given provider.

    Returns:
        A ``DiscoveryResult`` with models, optional error, and SDK status
        metadata (currently only populated for the Gemini provider).
    """
    provider_name = provider_name.lower().strip()

    # ── Resolve credentials from env / config ────────────────────────────
    if provider_name == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY")
        if cfg:
            key = key or getattr(cfg.llm, "openai_api_key", None)
        if not key:
            return DiscoveryResult([], error="OPENAI_API_KEY not set.")
        try:
            return DiscoveryResult(_discover_openai(key, include_preview))
        except Exception as exc:
            return DiscoveryResult([], error=f"OpenAI discovery failed: {exc}")

    elif provider_name == "anthropic":
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if cfg:
            key = key or getattr(cfg.llm, "anthropic_api_key", None)
        if not key:
            return DiscoveryResult([], error="ANTHROPIC_API_KEY not set.")
        try:
            return DiscoveryResult(_discover_anthropic(key, include_preview))
        except Exception as exc:
            return DiscoveryResult([], error=f"Anthropic discovery failed: {exc}")

    elif provider_name == "gemini":
        key = api_key or os.getenv("GOOGLE_API_KEY")
        if cfg:
            key = key or getattr(cfg.llm, "google_api_key", None)
        if not key:
            return DiscoveryResult([], error="GOOGLE_API_KEY not set.")
        try:
            models, sdk_status, sdk_detail = _discover_gemini(key, include_preview)
            return DiscoveryResult(
                models, sdk_status=sdk_status, sdk_detail=sdk_detail,
            )
        except Exception as exc:
            return DiscoveryResult([], error=f"Gemini discovery failed: {exc}")

    elif provider_name == "deepseek":
        key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if cfg:
            key = key or getattr(cfg.llm, "deepseek_api_key", None)
        if not key:
            return DiscoveryResult([], error="DEEPSEEK_API_KEY not set.")
        try:
            return DiscoveryResult(_discover_openai(
                key,
                include_preview,
                base_url="https://api.deepseek.com",
                provider_label="deepseek",
            ))
        except Exception as exc:
            return DiscoveryResult([], error=f"DeepSeek discovery failed: {exc}")

    elif provider_name == "ollama":
        url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if cfg:
            url = getattr(cfg.llm, "ollama_base_url", None) or url
        try:
            return DiscoveryResult(_discover_ollama(url))
        except Exception as exc:
            return DiscoveryResult([], error=f"Ollama discovery failed (is Ollama running?): {exc}")

    elif provider_name == "azure":
        key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        ver = azure_api_version
        if cfg:
            key = key or getattr(cfg.llm, "openai_api_key", None)
            endpoint = endpoint or getattr(cfg.llm, "azure_endpoint", None)
            ver = getattr(cfg.llm, "azure_api_version", None) or ver
        if not key:
            return DiscoveryResult([], error="AZURE_OPENAI_API_KEY not set.")
        if not endpoint:
            return DiscoveryResult([], error="AZURE_OPENAI_ENDPOINT not set.")
        try:
            return DiscoveryResult(_discover_azure(key, endpoint, ver, include_preview))
        except Exception as exc:
            return DiscoveryResult([], error=f"Azure discovery failed: {exc}")

    else:
        return DiscoveryResult([], error=f"Unknown provider: '{provider_name}'.")



# =============================================================================
# FORMATTING HELPERS (for CLI display)
# =============================================================================

def format_model_table(
    models: List[ModelInfo],
    *,
    show_tier: bool = True,
    show_context: bool = False,
    show_description: bool = False,
    number_start: int = 1,
) -> str:
    """
    Format a list of ``ModelInfo`` into a human-readable numbered table.

    Returns a multi-line string ready for ``print()``.
    """
    if not models:
        return "  (no models found)"

    lines: List[str] = []
    current_tier: Optional[ModelTier] = None

    for idx, m in enumerate(models):
        # Section header when tier changes
        if show_tier and m.tier != current_tier:
            current_tier = m.tier
            label = {
                ModelTier.STABLE:       "Stable / GA",
                ModelTier.PREVIEW:      "Preview / Beta",
                ModelTier.EXPERIMENTAL: "Experimental",
                ModelTier.DEPRECATED:   "Deprecated",
                ModelTier.UNKNOWN:      "Other",
            }.get(m.tier, "Other")
            lines.append(f"\n    --- {label} ---")

        num = number_start + idx
        parts = [f"    {num:>3}. {m.id}"]

        if show_tier and m.tier_badge:
            parts.append(f"  {m.tier_badge}")

        if show_context and m.context_window:
            ctx_k = m.context_window // 1000
            parts.append(f"  [{ctx_k}k ctx]")

        if show_description and m.description:
            parts.append(f"  - {m.description}")

        lines.append("".join(parts))

    return "\n".join(lines)


def format_model_verbose(models: List[ModelInfo], *, number_start: int = 1) -> str:
    """Format models with full detail cards, one per model.

    Shows all available metadata: version, token limits, generation
    parameters, supported methods — matching the level of detail from
    a raw API verbose listing.
    """
    if not models:
        return "  (no models found)"

    separator = "  " + "-" * 60
    lines: List[str] = []

    for idx, m in enumerate(models):
        num = number_start + idx
        lines.append(separator)
        lines.append(f"  {num:>3}. {m.id}  {m.tier_badge}")
        if m.display_name and m.display_name != m.id:
            lines.append(f"       Display Name : {m.display_name}")
        if m.version:
            lines.append(f"       Version      : {m.version}")
        if m.description:
            lines.append(f"       Description  : {m.description}")
        if m.context_window is not None:
            lines.append(f"       Input Tokens : {m.context_window:,}")
        if m.output_tokens is not None:
            lines.append(f"       Output Tokens: {m.output_tokens:,}")
        if m.temperature is not None:
            lines.append(f"       Temperature  : {m.temperature}")
        if m.top_p is not None:
            lines.append(f"       Top-P        : {m.top_p}")
        if m.top_k is not None:
            lines.append(f"       Top-K        : {m.top_k}")
        if m.supported_methods:
            lines.append(f"       Methods      : {', '.join(m.supported_methods)}")
        if m.owned_by:
            lines.append(f"       Owned By     : {m.owned_by}")

    lines.append(separator)
    return "\n".join(lines)
