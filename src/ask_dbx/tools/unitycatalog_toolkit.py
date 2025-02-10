import json
from typing import Any, Optional, List

from databricks.sdk.service.catalog import FunctionInfo
from unitycatalog.ai.langchain.toolkit import (
    UCFunctionToolkit,
    UnityCatalogTool,
    get_tool_name,
    generate_function_input_params_schema,
)
from unitycatalog.ai.core.utils.client_utils import validate_or_set_default_client
from unitycatalog.ai.core.base import (
    set_uc_function_client,
    BaseFunctionClient,
    PagedList,
)
from unitycatalog.ai.core.databricks import DatabricksFunctionClient


def custom_deserializer(result: dict, deserialize_hint: str):
    """
    Given a result (as a dict) and a deserialize hint (a string representing a Python type),
    try to convert the result into an instance of that type.
    The hint is expected to be something like:
        "<class 'databricks.sdk.service.compute.ClusterDetails'>"
    or simply a valid Python expression for a type.

    If the hint is in the form "<class '...'>", the inner quoted portion is extracted,
    then imported to obtain the actual type. This enables the use of the class's from_dict method.
    """
    try:
        # Check if the hint is in the form "<class '...'>"
        if deserialize_hint.startswith("<class") and deserialize_hint.endswith(">"):
            # Extract inner part. e.g. "<class 'databricks.sdk.service.compute.ListAvailableZonesResponse'>"
            # becomes "'databricks.sdk.service.compute.ListAvailableZonesResponse'"
            inner = deserialize_hint[6:-1].strip()
            if inner.startswith("'") and inner.endswith("'"):
                # Remove the quotes to get the fully-qualified class path.
                class_path = inner.strip("'")
            else:
                class_path = inner  # fallback if not quoted

            # Dynamically import the module and get the target class.
            module_name, class_name = class_path.rsplit(".", 1)
            module = __import__(module_name, fromlist=[class_name])
            target_type = getattr(module, class_name)
        else:
            # If the hint isn't in the "<class '...'>" format, attempt to eval it directly.
            target_type = eval(deserialize_hint)

        # Prefer a from_dict class method if available; otherwise try classic instantiation.
        if hasattr(target_type, "from_dict") and callable(target_type.from_dict):
            return target_type.from_dict(result)
        else:
            return target_type(**result)
    except Exception as e:
        print(f"Deserialization error: {e}")
        return result


class UnityCatalogToolkit(UCFunctionToolkit):
    """
    Extends the UCFunctionToolkit to:
      - Expose the correct tool version for agents:
          If both a base function (e.g. "my_func") and its `_sql` version exist,
          the `_sql` version is used (because that's the public API that receives the secret).
      - Deserialize results based on a 'DeserializeAs:' hint present in the function's description.
      - Support wildcard expansion for specifying all tools in a catalog and schema
        using the syntax "catalog.schema.*".

    Also provides a static method to convert a UC function (by name or info) into a LangChain StructuredTool.
    """

    class Config:
        # Allow extra attributes such as self.client
        extra = "allow"

    def __init__(self, config_or_function_names):
        """
        Accepts either:
          - A configuration object with attributes uc_catalog and uc_schema. In that case,
            we list all functions for that catalog/schema and expose the preferred version.
          - A string or list of strings representing function specifications.
            Wildcards in the form "catalog.schema.*" are supported.

        The provided specifications are converted to a unique list of function names and supplied to the parent.
        """
        client = DatabricksFunctionClient()
        set_uc_function_client(client)

        if hasattr(config_or_function_names, "uc_catalog"):
            # Use the config object's uc_catalog/uc_schema to list functions.
            catalog = config_or_function_names.uc_catalog
            schema = config_or_function_names.uc_schema
            functions = client.list_functions(catalog, schema)
            unique_names = self._choose_preferred_versions(functions)
        elif isinstance(config_or_function_names, str):
            unique_names = self._expand_function_names(
                [config_or_function_names], client
            )
        elif isinstance(config_or_function_names, list):
            unique_names = self._expand_function_names(config_or_function_names, client)
        else:
            raise ValueError(
                "Invalid input: must be a config object with uc_catalog/uc_schema, a string, or a list of strings."
            )

        super().__init__(function_names=unique_names)
        object.__setattr__(self, "client", client)

    def _choose_preferred_versions(self, functions: List[Any]) -> List[str]:
        """
        Given a list of FunctionInfo objects (each having a 'full_name'),
        group by the base name (removing a trailing '_sql' if present) and choose the _sql version
        if both exist. Returns a unique list of full names.
        """
        groups = {}
        for func in functions:
            name = func.full_name
            # Define the base name by stripping the trailing '_sql' if present.
            base = name[:-4] if name.endswith("_sql") else name
            # If we haven't seen this base, store it.
            if base not in groups:
                groups[base] = name
            else:
                # If the stored version is not _sql but this one is, override.
                if not groups[base].endswith("_sql") and name.endswith("_sql"):
                    groups[base] = name
        return list(groups.values())

    def _resolve_function_name(
        self, name: str, client: DatabricksFunctionClient
    ) -> str:
        """
        If the given function name does not end with '_sql' and if the _sql version exists,
        then return the version with '_sql' appended. Otherwise, return the original name.
        The lookup is performed using client.get_function(), catching exceptions if needed.
        """
        if name.endswith("_sql"):
            return name
        candidate = name + "_sql"
        try:
            # Attempt to retrieve the SQL version.
            client.get_function(candidate)
            return candidate
        except Exception:
            return name

    def _expand_function_names(
        self, function_names: List[str], client: DatabricksFunctionClient
    ) -> List[str]:
        """
        Processes a list of function name specifications. For entries in the form "catalog.schema.*",
        list and group all functions. For explicit function names, if they don't end with '_sql',
        attempt to resolve to the SQL version if it exists.
        """
        expanded = []
        for name in function_names:
            if "*" in name:
                # Expecting wildcard of the form "catalog.schema.*"
                if not name.endswith(".*"):
                    raise ValueError(
                        "Wildcard format not recognized. Expected format: 'catalog.schema.*'"
                    )
                parts = name.split(".")
                if len(parts) != 3:
                    raise ValueError("Wildcard must be in format 'catalog.schema.*'")
                catalog, schema, _ = parts
                functions = client.list_functions(catalog, schema)
                expanded.extend(self._choose_preferred_versions(functions))
            else:
                expanded.append(self._resolve_function_name(name, client))
        return list(dict.fromkeys(expanded))

    def get_tool(self, tool_name: str) -> UnityCatalogTool:
        """
        Retrieve a UnityCatalogTool by its name. This method lazily creates and caches the tool
        using the static method 'uc_function_to_langchain_tool', ensuring that each tool is only created once.
        """
        if not hasattr(self, "_tool_cache"):
            self._tool_cache = {}
        if tool_name not in self._tool_cache:
            self._tool_cache[
                tool_name
            ] = UnityCatalogToolkit.uc_function_to_langchain_tool(
                function_name=tool_name,
                client=self.client,
            )
        return self._tool_cache[tool_name]

    def invoke_tool(self, tool_name: str, inputs: Optional[dict] = None):
        """
        Invokes the tool with the given name and inputs.
        Deserializes the JSON result using the 'DeserializeAs:' hint, if present.
        The inputs parameter is optional and only used if the function definition requires inputs.
        """
        if inputs is None:
            inputs = {}
        tool = self.get_tool(tool_name)
        output_json = tool.invoke(inputs)
        raw_output = json.loads(output_json)

        # Attempt to unpack the nested 'value' field if present.
        if (
            isinstance(raw_output, dict)
            and "value" in raw_output
            and isinstance(raw_output["value"], str)
        ):
            try:
                output = json.loads(raw_output["value"])
            except Exception as e:
                print(f"Error unpacking value from output: {e}")
                output = raw_output
        else:
            output = raw_output

        deserialize_hint = None
        if tool.description and "DeserializeAs:" in tool.description:
            parts = tool.description.split("DeserializeAs:")
            if len(parts) > 1:
                deserialize_hint = parts[1].strip()
        if deserialize_hint:
            return custom_deserializer(output, deserialize_hint)
        return output

    @staticmethod
    def uc_function_to_langchain_tool(
        *,
        client: Optional[BaseFunctionClient] = None,
        function_name: Optional[str] = None,
        function_info: Optional[Any] = None,
    ) -> UnityCatalogTool:
        """
        Convert a UC function to a LangChain StructuredTool.

        Args:
            client: The client instance (a subclass of BaseFunctionClient).
            function_name: The full name of the function (e.g. "catalog.schema.function").
            function_info: The FunctionInfo object returned by client.get_function().

        Note:
            Only one of function_name or function_info should be provided.
        """
        if function_name and function_info:
            raise ValueError(
                "Only one of function_name or function_info should be provided."
            )
        client = validate_or_set_default_client(client)
        if function_name:
            function_info = client.get_function(function_name)
        elif function_info:
            function_name = function_info.full_name
        else:
            raise ValueError("Either function_name or function_info must be provided.")

        def func(*args: Any, **kwargs: Any) -> str:
            args_json = json.loads(json.dumps(kwargs, default=str))
            result = client.execute_function(
                function_name=function_name,
                parameters=args_json,
            )
            return result.to_json()

        return UnityCatalogTool(
            name=get_tool_name(function_name),
            description=function_info.comment or "",
            func=func,
            args_schema=generate_function_input_params_schema(
                function_info
            ).pydantic_model,
            uc_function_name=function_name,
            client_config=client.to_dict(),
        )


# Example Usage:
if __name__ == "__main__":
    from ask_dbx.config import settings

    # Instantiate the toolkit with a config object (with uc_catalog and uc_schema attributes)
    toolkit = UnityCatalogToolkit(settings)

    # Example: Invoke a tool. The secret is passed as a parameter.
    result = toolkit.invoke_tool(
        "my_catalog.my_schema.list_jobs_sql",
        {"some_parameter": "value", "secret": "your_secret_value"},
    )
    print("Deserialized result:", result)

    # Example: Convert a UC function to a LangChain tool.
    tool = UnityCatalogToolkit.uc_function_to_langchain_tool(
        function_name="my_catalog.my_schema.list_jobs_sql"
    )
    print("Tool created:", tool)
