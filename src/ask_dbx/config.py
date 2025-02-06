from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    databricks_token: str = Field(..., env="DATABRICKS_TOKEN")
    databricks_host: str = Field(..., env="DATABRICKS_HOST")

    # Agents Specific Settings
    default_agent_timeout: int = Field(60, env="AGENT_TIMEOUT")
    agent_logging_level: str = Field("INFO", env="AGENT_LOG_LEVEL")

    # Tools Specific Settings (for example, for the Databricks SDK)
    sdk_timeout: int = Field(30, env="SDK_TIMEOUT")
    sdk_retry_count: int = Field(3, env="SDK_RETRY_COUNT")

    # Integrations Specific Settings
    retriever_endpoint: str = Field(
        "https://default-databricks-vector-search.example.com", env="RETRIEVER_ENDPOINT"
    )
    state_db_path: str = Field("data/state.db", env="STATE_DB_PATH")
    markdown_path: str = Field("data/tasks.md", env="MARKDOWN_PATH")


# Instantiate a single settings object that all modules can import
settings = Settings(_env_file=".env")
