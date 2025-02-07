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
        "https://e2-demo-field-eng.cloud.databricks.com/ml/endpoints/agents_robert-dbdemos_rag_chatbot-rag_agent/invocations",
        env="RETRIEVER_ENDPOINT",
    )
    retriever_index: str = Field("ask-dbx", env="RETRIEVER_INDEX")
    state_db_path: str = Field("data/state.db", env="STATE_DB_PATH")
    markdown_path: str = Field("data/tasks.md", env="MARKDOWN_PATH")
    job_requirements_path: str = Field(
        "data/requirements.md", env="JOB_REQUIREMENTS_PATH"
    )
    mlflow_experiment: str = Field(
        "/Users/forrest.murray@databricks.com/ask_dbx", env="MLFLOW_EXPERIMENT"
    )
    gpt_model: str = Field("agents-demo-gpt4o")


# Instantiate a single settings object that all modules can import
settings = Settings(_env_file=".env")
