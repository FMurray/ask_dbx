# Databricks Job Automation Agent

## Overview

The Databricks Job Automation Agent is an AI-powered tool designed to streamline the creation and management of jobs on Databricks. By leveraging a multi-persona architecture and a structured workflow, it automates tasks that traditionally require manual intervention.

### Key Capabilities

- **Multi-Persona Workflow:**  
  - **Tech Lead:** Reviews job requirements, interprets details, and assigns actionable tasks.
  - **Worker:** Executes tasks through a streamlined process: **Validate → Plan → Apply**.

- **Tool Integrations:**  
  1. **Retriever:** Queries and retrieves relevant sections of the Databricks documentation.
  2. **Databricks Python SDK:** Communicates directly with Databricks APIs for job creation and management.
  3. **Local Markdown File Manager:** Handles markdown file operations to record high-level task progress.
  4. **State Database:** Monitors and tracks the status of tasks (e.g., IN_PROGRESS, COMPLETE, FAILED).

## Architecture

The system is composed of two primary processes:

1. **Tech Lead Process:**  
   - Analyzes incoming job requirements.
   - Breaks down complex tasks into detailed steps.
   - Delegates tasks to the Worker based on priority and current processing state.

2. **Worker Process:**  
   - **Validate:** Ensures that tasks are in the correct state to be executed.
   - **Plan:** Outlines a sequence of steps needed to complete the task.
   - **Apply:** Executes the proposed steps, interacting with the Databricks APIs via the Python SDK and updating the task state accordingly.

These processes work together to ensure job creation and management are performed efficiently, accurately, and with clear audit trails.

## Getting Started

### Prerequisites

- [uv Package Manager](https://example.com/uv) installed globally.
- Access credentials to your Databricks workspace.
- A properly configured local environment for managing markdown files.
- A database setup for tracking task states (see setup documentation for details).

### Installation

To set up the project with **uv**, follow these steps:

1. **Install the project using uv:**
   ```bash
   uv install databricks-job-automation-agent
   ```

2. **Navigate to the newly created project directory:**
   ```bash
   cd databricks-job-automation-agent
   ```

3. **Configure Your Environment:**
   - Update any necessary environment variables.
   - Ensure that your Databricks workspace credentials are properly configured.

### Running the Project

To start the application, run:
