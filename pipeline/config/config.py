from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # Directories
    data_directory: Optional[str] = None
    output_directory: str = "./Results"

    # Pipeline run control
    resume: bool = False
    start_from_step: int = 1

    # OpenAI models
    openai_api_key: Optional[str] = None
    openai_model_vision: str = "gpt-4o-mini"
    openai_model_text: str = "gpt-4o-mini"

    # Dolphin inference
    dolphin_max_batch_size: int = 16

    # Limits
    max_context_length: int = 5000
    max_description_length: int = 1000

    # Logging
    default_log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
