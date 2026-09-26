"""Configuration loaded from environment / .env file."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """All runtime configuration. Values come from the environment (.env)."""

    # --- GitHub ---
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USER: str = os.getenv("GITHUB_USER", "")

    # --- Google Docs (service account) ---
    GOOGLE_SA_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json")
    NEWS_DOC_ID: str = os.getenv("NEWS_DOC_ID", "")
    TRACKER_DOC_ID: str = os.getenv("TRACKER_DOC_ID", "")

    # --- Email (Gmail SMTP + app password) ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_APP_PASSWORD: str = os.getenv("EMAIL_APP_PASSWORD", "")
    EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "") or os.getenv("EMAIL_ADDRESS", "")

    # --- Optional LLM (OpenAI-compatible; defaults to Gemini) ---
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
    )
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    # --- Behaviour ---
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    STATE_FILE: str = os.getenv("STATE_FILE", "state/state.json")

    # Scanner limits (keep API usage sane)
    MAX_REPOS: int = int(os.getenv("MAX_REPOS", "40"))
    MAX_FILES_PER_REPO: int = int(os.getenv("MAX_FILES_PER_REPO", "250"))
    MAX_FILE_BYTES: int = int(os.getenv("MAX_FILE_BYTES", "200000"))

    @classmethod
    def validate(cls, need_email: bool = True, need_docs: bool = True) -> list:
        """Return a list of human-readable problems with the config."""
        problems = []
        if not cls.GITHUB_TOKEN:
            problems.append("GITHUB_TOKEN is not set (needed to scan your repos).")
        if need_docs:
            if not cls.GOOGLE_SA_FILE or not os.path.exists(cls.GOOGLE_SA_FILE):
                problems.append(
                    "GOOGLE_SERVICE_ACCOUNT_FILE not found — see .env.example "
                    "(create a service account key and share both docs with it)."
                )
            if not cls.NEWS_DOC_ID or not cls.TRACKER_DOC_ID:
                problems.append("NEWS_DOC_ID / TRACKER_DOC_ID are not set.")
        if need_email:
            if not cls.EMAIL_ADDRESS or not cls.EMAIL_APP_PASSWORD:
                problems.append(
                    "EMAIL_ADDRESS / EMAIL_APP_PASSWORD not set (Gmail app password)."
                )
        return problems
