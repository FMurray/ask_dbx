# Databricks Job Automation Agent

## Overview

The Databricks Job Automation Agent is an AI-powered tool designed to streamline the creation and management of jobs on Databricks. It leverages a multi-persona architecture to automate tasks that would otherwise require manual intervention. The system is composed of two main components:

- **Tech Lead**:  
  Analyzes job requirements, interprets details, and creates detailed tasks.

- **Worker**:  
  Executes tasks through a streamlined process: **Validate → Plan → Apply**.

The Agent integrates several key tools:
- **Retriever**: Retrieves relevant sections of the Databricks documentation using vector search.
- **Databricks Python SDK**: Interacts with Databricks APIs for job management.
- **Local Markdown File Manager**: Logs high-level task updates to a markdown file.
- **State Database**: Tracks and manages the state of tasks (e.g., IN_PROGRESS, COMPLETE, FAILED).

## Project Structure

The project is organized as follows:

```
.
├── data/
│   ├── state.db             # SQLite database for tracking task states
│   └── tasks.md             # Markdown file for logging task updates
├── src/
│   └── ask_dbx/
│       ├── __init__.py
│       ├── config.py        # Global configuration using Pydantic
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── main.py      # Main orchestration script
│       │   ├── tech_lead.py # Tech Lead agent workflow
│       │   └── worker.py    # Worker agent workflow (validate-plan-apply)
│       ├── integrations/
│       │   ├── __init__.py
│       │   ├── markdown_manager.py  # Manages markdown logging
│       │   ├── retriever.py         # Retrieves documentation via vector search
│       │   └── state_db.py          # Manages task states using SQLite
│       └── tools/
│           └── databricks_sdk.py    # Wrapper for Databricks SDK operations
├── .env                       # Environment variables file
├── pyproject.toml             # Project configuration and dependencies
└── README.md                  # Project documentation
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv Package Manager](https://example.com/uv) (or alternatively, use pip)
- Valid credentials for your Databricks workspace
- A properly configured local environment for managing markdown files
- The necessary environment variables defined in a `.env` file

### Installation

1. **Install the project using uv:**
   ```bash
   uv install databricks-job-automation-agent
   ```

2. **Navigate to the project directory:**
   ```bash
   cd databricks-job-automation-agent
   ```

3. **Configure Your Environment:**
   Create or update the `.env` file in the project root with the required environment variables. For example:
   ```
   DATABRICKS_TOKEN=your-token-here
   DATABRICKS_HOST=https://your-databricks-host
   AGENT_TIMEOUT=60
   AGENT_LOG_LEVEL=INFO
   SDK_TIMEOUT=30
   SDK_RETRY_COUNT=3
   RETRIEVER_ENDPOINT=https://default-databricks-vector-search.example.com
   STATE_DB_PATH=data/state.db
   MARKDOWN_PATH=data/tasks.md
   ```

### Running the Project

Once installed and configured, start the application using the provided CLI command:

```bash
hello
```

This will initiate the following workflow:
- The **Tech Lead** analyzes the job requirements and creates a task.
- The **Worker** processes the task through the validate-plan-apply workflow.
- Task updates are logged to the `data/tasks.md` file.
- Task states are managed using the SQLite database at `data/state.db`.

## Extending the Project

- **Configuration**:  
  All configuration values are centralized in `src/ask_dbx/config.py` using Pydantic. This ensures type-safe, validated, and consistent configuration across the project.

- **Integrations**:  
  Update or extend the tool integrations (e.g., Markdown manager, state database, retriever) by modifying their respective modules in `src/ask_dbx/integrations/`.

- **Agents**:  
  Enhance the agent workflows in `src/ask_dbx/agents/` to add more detailed error handling, support additional job operations, or integrate with new services.

## Contributing

Contributions are welcome! Please ensure that your changes are well-tested and conform to the project's coding standards. When submitting pull requests, reference any corresponding updates in the design or requirements documentation.

## License

This project is licensed under the [Your License Name] license.
