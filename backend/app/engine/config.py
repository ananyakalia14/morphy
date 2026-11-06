import base64
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    control_dsn: str
    encryption_key: bytes
    target_hosts: frozenset[str]
    ollama_url: str
    ollama_model: str

    @classmethod
    def load(cls):
        required = [
            "MORPHY_SUPABASE_URL",
            "MORPHY_SUPABASE_PUBLIC_KEY",
            "MORPHY_CONTROL_DSN",
            "MORPHY_ENCRYPTION_KEY",
            "MORPHY_TARGET_HOSTS",
        ]
        if any(not os.getenv(k) for k in required):
            raise ValueError(
                "The live engine requires its server environment settings."
            )
        key = base64.urlsafe_b64decode(os.environ["MORPHY_ENCRYPTION_KEY"])
        if len(key) != 32:
            raise ValueError("The engine encryption key must decode to 32 bytes.")
        url = os.environ["MORPHY_SUPABASE_URL"].rstrip("/")
        if not url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
            raise ValueError("Supabase requires HTTPS outside local development.")
        return cls(
            url,
            os.environ["MORPHY_SUPABASE_PUBLIC_KEY"],
            os.environ["MORPHY_CONTROL_DSN"],
            key,
            frozenset(
                h.strip().lower()
                for h in os.environ["MORPHY_TARGET_HOSTS"].split(",")
                if h.strip()
            ),
            os.getenv("MORPHY_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            os.getenv("MORPHY_OLLAMA_MODEL", "qwen2.5-coder:7b"),
        )
