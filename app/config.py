import os

_here = os.path.dirname(os.path.abspath(__file__))

DATA_ROOT = os.environ.get("DATA_ROOT") or os.path.join(_here, "..", "data")  # env-first

DEFAULT_DOMAIN = os.environ.get("DOMAIN", "environment")

PROVIDER = os.environ.get("PROVIDER", "mock")
HOSTED_API_KEY = os.environ.get("HOSTED_API_KEY", "sk-REPLACE-ME")
HOSTED_MODEL = os.environ.get("HOSTED_MODEL", "gpt-4o-mini")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

CACHE_TTL = int(os.environ.get("CACHE_TTL", 3600))
IMAGE_TAG = os.environ.get("IMAGE_TAG", "dev")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
