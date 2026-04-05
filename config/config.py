from typing import List, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Directories
    data_directory: str = Field("./Data", env="DATA_DIRECTORY")
    output_directory: str = Field("./Results", env="OUTPUT_DIRECTORY")

    # Pipeline run control
    resume: bool = Field(False, env="RESUME")
    start_from_step: int = Field(1, env="START_FROM_STEP")

    # Flags
    process_code_using_llm: bool = Field(False, env="PROCESS_CODE_USING_LLM")
    process_figures_using_llm: bool = Field(False, env="PROCESS_FIGURES_USING_LLM")
    segments_to_refine: List[str] = Field(
        default_factory=lambda: ["code", "fig", "tab"], env="SEGMENTS_TO_REFINE"
    )

    # OpenAI models
    openai_api_key: Optional[SecretStr] = Field(None, env="OPENAI_API_KEY")
    openai_model_vision: str = Field("gpt-4o-mini", env="OPENAI_MODEL_VISION")
    openai_model_text: str = Field("gpt-4o-mini", env="OPENAI_MODEL_TEXT")

    # Limits
    max_context_length: int = Field(5000, env="MAX_CONTEXT_LENGTH")
    max_description_length: int = Field(1000, env="MAX_DESCRIPTION_LENGTH")

    # Logging
    default_log_level: str = Field("INFO", env="DEFAULT_LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
