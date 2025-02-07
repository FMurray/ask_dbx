import os
import requests
import json

from langchain_core.tools import BaseTool
from mlflow.deployments import get_deploy_client
from databricks_langchain import DatabricksVectorSearch


def get_retriever(config):
    retriver = DatabricksVectorSearch(
        index_name=config.retriever_index,
        client_args={"personal_access_token": config.databricks_token},
    ).as_retriever()
    return retriver

    def __init__(self, config):
        """
        Initialize the Remote Retriever using a serving endpoint.

        Args:
            config: The global settings object containing configuration values,
                    including retriever_endpoint and databricks_token.
        """
        self.config = config
        self.endpoint_url = (
            config.retriever_endpoint
        )  # e.g., "https://<workspace>/serving-endpoints/<endpoint_name>/invocations"

        self.deployment_client = get_deploy_client("databricks")

        print(
            f"Remote Retriever initialized with serving endpoint: {self.endpoint_url}"
        )

    def fetch_docs(self, query: str) -> str:
        """
        Retrieve documentation content relevant to the given query by calling a remote agent
        served via a Databricks serving endpoint.

        This method:
          1. Constructs a query payload.
          2. Sends a POST request to the remote agent using the provided serving endpoint.
          3. Processes the returned JSON result to extract the "text_column" from each document.

        Args:
            query (str): The search query or keyword.

        Returns:
            str: A combined string of document excerpts retrieved by the remote agent.
        """
        # Build the payload. Adjust the keys and values as required by your remote agent.
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": query,
                }
            ]
        }
        print(
            f"Remote Retriever: Querying serving endpoint at '{self.endpoint_url}' for query: '{query}'"
        )
        results = self.deployment_client.predict(
            endpoint="agents_robert-dbdemos_rag_chatbot-rag_agent",
            inputs=payload,
        )

        print(results)

        docs = self._convert_results_to_docs(results)
        combined_doc = "\n\n".join(docs)
        return combined_doc

    def _convert_results_to_docs(self, results) -> list:
        """
        Convert the returned results from the remote agent into a list of document texts.

        The expected response is aligned with the MLflow retriever schema and contains:
          - A "manifest" key with column metadata.
          - A "result" key that includes a "data_array" of the search results.

        Args:
            results: The JSON response from the remote agent.

        Returns:
            list: A list of strings representing the text content from each document.
        """
        docs = []
        try:
            manifest = results.get("manifest", {})
            data_array = results.get("result", {}).get("data_array", [])
            column_names = [col["name"] for col in manifest.get("columns", [])]
            # Identify the column containing the text; if not found, fallback to the second column.
            text_index = (
                column_names.index("text_column")
                if "text_column" in column_names
                else 1
            )

            for row in data_array:
                if len(row) > text_index:
                    docs.append(row[text_index])
        except Exception as e:
            print("Error converting remote agent results to documents:", e)
        return docs
