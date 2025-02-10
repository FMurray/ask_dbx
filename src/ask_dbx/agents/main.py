from ask_dbx.config import settings
from ask_dbx.integrations import state_db, markdown_manager, retriever

from ask_dbx.tools.databricks_sdk import DatabricksSDKRegistrar
from ask_dbx.agents.tech_lead import TechLead
from ask_dbx.agents.worker import Worker
from ask_dbx.tools.unitycatalog_toolkit import UnityCatalogToolkit
import mlflow
import os
import io


def main():
    # registrar = DatabricksSDKRegistrar()
    # registrar.register_all_uc_functions()

    toolkit = UnityCatalogToolkit(settings)

    result = toolkit.invoke_tool("forrest_murray.rag_demo.list_zones_sql")
    print("Deserialized result:", result)
    # # Set up MLflow tracking to Databricks
    # os.environ["MLFLOW_TRACKING_URI"] = "databricks"
    # # Set the experiment name
    # mlflow.set_experiment(settings.mlflow_experiment)

    # # Enable MLflow tracing for LangChain (if you're using it)
    # mlflow.langchain.autolog()

    # retriever_client = retriever.get_retriever(settings)

    # # Initialize the Databricks client
    # databricks_client = DatabricksClient(settings)
    # markdown_mgr = markdown_manager.MarkdownManager(settings)
    # state_database = state_db.StateDatabase(settings)

    # # Initialize the core agent processes
    # tech_lead = TechLead(retriever_client, settings)
    # worker = Worker(databricks_client, markdown_mgr, state_database, settings)

    # # Start an MLflow run to track the tech lead analysis
    # with mlflow.start_run(run_name="tech_lead_analysis"):
    #     # 1. Tech Lead analyzes the job requirements and creates a task.
    #     task = tech_lead.analyze_job_requirements()

    #     # Log the task output
    #     mlflow.log_text(str(task), "task_output.txt")

    # print(task)

    # 2. Worker processes the task using the validate-plan-apply workflow.
    # worker.process_task(task)


def tech_lead() -> None:
    from PIL import Image

    retriever_client = retriever.get_retriever(settings)

    # Initialize the Databricks client
    databricks_client = DatabricksClient(settings)
    markdown_mgr = markdown_manager.MarkdownManager(settings)
    state_database = state_db.StateDatabase(settings)

    # Initialize the core agent processes
    tech_lead = TechLead(retriever_client, settings)

    os.environ["MLFLOW_TRACKING_URI"] = "databricks"
    # Set the experiment name
    mlflow.set_experiment(settings.mlflow_experiment)
    mlflow.langchain.autolog()

    with mlflow.start_run(run_name="tech_lead_analysis"):
        # 1. Tech Lead analyzes the job requirements and creates a task.
        task = tech_lead.analyze_job_requirements()

        # # Log the task output
        mlflow.log_text(str(task), "task_output.txt")
        mlflow.log_image(
            Image.open(
                io.BytesIO(
                    tech_lead.g_analyze_job_requirements.get_graph().draw_mermaid_png()
                )
            ),
            "tech_lead.png",
        )
