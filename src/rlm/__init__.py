from .config import settings
# Lazy import of llm to avoid dependency error when litellm not installed
try:
    from .llm import get_llm_client, call_llm
except ImportError:
    get_llm_client = None
    call_llm = None

from .processor import process_scene

__version__ = "0.2.0"
