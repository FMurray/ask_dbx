from ask_dbx.models import Task


class TechLead:
    def __init__(self, retriever, config):
        self.retriever = retriever
        self.config = config

    def analyze_job_requirements(self) -> Task:
        print("TechLead: Analyzing job requirements...")
        # In an agentic multi-agent system, the TechLead first gathers context.
        # Here we use the retriever to fetch documentation related to job creation.
        documentation = self.retriever.fetch_docs("job creation")
        task_details = (
            "Automate Databricks job creation based on requirements and documentation."
        )
        task = Task(
            id=1, details=task_details, documentation=documentation, state="PENDING"
        )
        print(f"TechLead: Created task with details: {task.details}")
        return task
