from ask_dbx.config import settings
from ask_dbx.integrations import state_db, markdown_manager, retriever
from ask_dbx.tools.databricks_sdk import DatabricksClient
from ask_dbx.agents.tech_lead import TechLead
from ask_dbx.agents.worker import Worker


def main():
    # Initialize integration components with the global settings
    retriever_client = retriever.Retriever(settings)
    databricks_client = DatabricksClient(settings)
    markdown_mgr = markdown_manager.MarkdownManager(settings)
    state_database = state_db.StateDatabase(settings)

    # Initialize the core agent processes
    tech_lead = TechLead(retriever_client, settings)
    worker = Worker(databricks_client, markdown_mgr, state_database, settings)

    # Orchestrate the process:
    # 1. Tech Lead analyzes the job requirements and creates a task.
    task = tech_lead.analyze_job_requirements()

    # 2. Worker processes the task using the validate-plan-apply workflow.
    worker.process_task(task)
