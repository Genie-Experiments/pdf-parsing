from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr
from typing import List, Optional


class Settings(BaseSettings):
    # Directories
    data_directory: str = Field("./Data", env="DATA_DIRECTORY")
    output_directory: str = Field("./Results", env="OUTPUT_DIRECTORY")
    processed_images_dir: str = Field("./processed_images_by_dolphin", env="PROCESSED_IMAGES_DIR")
    raw_pdf_text_dir: str = Field("./pdfs_raw_text", env="RAW_PDF_TEXT_DIR")
    hierarchy_json_directory: str = Field("./section_hierarchy_pdfs", env="HIERARCHY_JSON_DIRECTORY")

    # Internal paths
    dolphin_script: str = Field("./Dolphin/demo_page.py", env="DOLPHIN_SCRIPT")
    model_path: str = Field("./Dolphin/hf_model", env="MODEL_PATH")
    html_to_markdown_dir: str = Field("./html-to-markdown", env="HTML_TO_MARKDOWN_DIR")

    # Flags
    process_code_using_llm: bool = Field(False, env="PROCESS_CODE_USING_LLM")
    process_figures_using_llm: bool = Field(False, env="PROCESS_FIGURES_USING_LLM")
    segments_to_refine: List[str] = Field(default_factory=lambda: ["code", "fig", "tab"], env="SEGMENTS_TO_REFINE")

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
