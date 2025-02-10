import inspect
import json
import re
from typing import *
from typing import get_type_hints
from itertools import islice

from databricks.sdk import WorkspaceClient, WorkspaceAPI
from databricks.sdk.service.jobs import *
from databricks.sdk.service.jobs import JobsAPI
from databricks.sdk.service.serving import ServingEndpointsAPI
from databricks.sdk.service.compute import ClustersAPI
from langchain_core.callbacks import (
    CallbackManagerForToolRun,
    AsyncCallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, Field

import os
import textwrap

from ask_dbx.config import settings

# Import the Unity Catalog registration helpers.
from unitycatalog.ai.core.base import set_uc_function_client
from unitycatalog.ai.core.databricks import DatabricksFunctionClient


class DatabricksSDKRegistrar:
    """
    Encapsulates Unity Catalog function registration using the DatabricksFunctionClient.

    When registering a Python function, instead of inlining its source code,
    a SQL DDL statement is generated that creates a PYTHON function. This SQL function
    instantiates a WorkspaceClient using a secret token passed in from the SQL wrapper,
    calls an SDK method based on the function's API group, and returns a JSON‑serialized result.

    For example, if a function named `list_jobs` (defined as part of JobsAPI) is registered, the generated code will look like:

        from databricks.sdk import WorkspaceClient
        import json
        client = WorkspaceClient(host="https://...", token=secret)
        result = client.jobs.list_jobs(<parameters>)
        def default_serializer(o):
            if hasattr(o, "to_dict"):
                return o.to_dict()
            elif hasattr(o, "__dict__"):
                return o.__dict__
            else:
                return str(o)
        return json.dumps(result, default=default_serializer)
    """

    def __init__(self):
        # Initialize the Unity Catalog function client and set it as the default.
        self.client = DatabricksFunctionClient()
        set_uc_function_client(self.client)

    def safe_get_type_hints(self, func):
        """
        Safely retrieve type hints for a function. If resolution of any type fails
        (for example, due to forward reference issues), fall back to the raw __annotations__.
        """
        try:
            return get_type_hints(func, func.__globals__)
        except Exception as e:
            print(f"Warning: get_type_hints failed for {func.__name__}: {e}")
            return func.__annotations__

    def safe_stringify_annotation(self, value) -> str:
        """
        Converts a type annotation to a string.
        If the value is a type, returns its qualified name;
        otherwise, falls back to converting it via str().
        """
        try:
            if isinstance(value, type):
                return f"{value.__module__}.{value.__qualname__}"
            return str(value)
        except Exception:
            return str(value)

    def _is_serializable_type(self, typ) -> bool:
        """
        Checks if the given type is considered JSON serializable.
        We consider basic types (int, float, bool, str, dict) as serializable.
        Also, if the type is a generic list or dict, we consider it serializable.
        """
        allowed = {int, float, bool, str, dict}
        if typ in allowed:
            return True
        origin = getattr(typ, "__origin__", None)
        if origin in (list, dict):
            return True
        if typ is type(None):
            return True
        return False

    def _append_deserialize_hint(self, func):
        """
        Looks at the function's return type annotation; if that type isn't among the basic
        JSON-serializable types, appends a "DeserializeAs: ..." line to the function's docstring.
        """
        type_hints = self.safe_get_type_hints(func)
        return_type = type_hints.get("return", None)
        if return_type is not None and not self._is_serializable_type(return_type):
            deserialization_hint = f"DeserializeAs: {return_type!r}"
            if func.__doc__:
                func.__doc__ += "\n" + deserialization_hint
            else:
                func.__doc__ = deserialization_hint
            print(
                f"Warning: Function '{func.__name__}' has return type {return_type} which is not "
                f"automatically serializable. {deserialization_hint}"
            )

    def map_python_type_to_sql(self, python_type) -> str:
        """
        Map a Python type to a SQL-compatible type for use in a SQL function definition.
        Only basic types are supported.
        """
        mapping = {
            int: "INT",
            float: "DOUBLE",
            bool: "BOOLEAN",
            str: "STRING",
        }
        return mapping.get(python_type, "STRING")

    def get_sql_parameters(self, func) -> (str, str):
        """
        Extract the SQL parameter definitions and the call list from the Python function's signature.
        Returns a tuple:
            (parameter_definitions, parameter_call_list)
        where:
            parameter_definitions is a comma-separated string like "x INT, y DOUBLE"
            parameter_call_list is a comma-separated string like "x, y"
        Note: 'self' and 'secret' are excluded here since we'll add secret explicitly.
        """
        sig = inspect.signature(func)
        param_declarations = []
        param_calls = []
        for param in sig.parameters.values():
            if param.name in ("self", "secret"):
                continue
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue
            sql_type = "STRING"
            if param.annotation is not inspect.Parameter.empty:
                sql_type = self.map_python_type_to_sql(param.annotation)
            param_declarations.append(f"{param.name} {sql_type}")
            param_calls.append(param.name)
        return ", ".join(param_declarations), ", ".join(param_calls)

    def get_api_group(self, func) -> str:
        """
        Deduce the API group (used to access the appropriate method on WorkspaceClient)
        from the function's qualified name.
        For instance, if the function's qualname begins with 'JobsAPI.', this returns 'jobs';
        if it begins with 'ClustersAPI.', returns 'clusters'; and if it begins with 'WorkspaceAPI.', returns 'workspace'.
        Otherwise, fallback to the last part of the module name.
        """
        qualname = func.__qualname__
        if qualname.startswith("JobsAPI."):
            return "jobs"
        elif qualname.startswith("ClustersAPI."):
            return "clusters"
        elif qualname.startswith("WorkspaceAPI."):
            return "workspace"
        else:
            module_parts = func.__module__.split(".")
            return module_parts[-1]

    def register_function(
        self, func, secret_scope: str = "default_scope", secret_key: str = "default_key"
    ):
        """
        Register a Python function using a SQL DDL statement. The generated PYTHON function,
        when executed, creates a WorkspaceClient using a secret passed in as a parameter,
        calls the corresponding API method, and returns a JSON-serialized result.

        Args:
            func (callable): The function to register.
            secret_scope (str): The secret's scope.
            secret_key (str): The secret's key.
        """
        # Append deserialization hint if needed.
        self._append_deserialize_hint(func)

        # Extract SQL parameter definitions and call list from the original function.
        # (The list excludes 'self' and 'secret'.)
        param_decls, param_calls = self.get_sql_parameters(func)
        # Add the extra secret parameter to the SQL DDL.
        full_param_decls = (
            f"{param_decls}, secret STRING" if param_decls else "secret STRING"
        )
        api_group = self.get_api_group(func)

        # Build the call string for the underlying client API (do not pass secret to the API call).
        if param_calls:
            call_str = f"result = client.{api_group}.{func.__name__}({param_calls})"
        else:
            call_str = f"result = client.{api_group}.{func.__name__}()"

        # Construct the SQL DDL for a PYTHON function.
        sql_body = f"""CREATE OR REPLACE FUNCTION {settings.uc_catalog}.{settings.uc_schema}.{func.__name__}({full_param_decls})
RETURNS STRING
LANGUAGE PYTHON
COMMENT {repr(func.__doc__ or '')}
AS $$
import json
from databricks.sdk import WorkspaceClient
# The secret parameter is passed in from the SQL wrapper.
client = WorkspaceClient(host={repr(settings.databricks_host)}, token=secret)
{call_str}
def default_serializer(o):
    if hasattr(o, "to_dict"):
        return o.to_dict()
    elif hasattr(o, "__dict__"):
        return o.__dict__
    else:
        return str(o)
return json.dumps(result, default=default_serializer)
$$;
"""
        try:
            function_info = self.client.create_function(sql_function_body=sql_body)
            print(f"Registered Python function '{func.__name__}': {function_info}")
        except Exception as e:
            print(f"Error registering Python function '{func.__name__}': {e}")

    def register_with_sql_wrapper(self, func, secret_scope: str, secret_key: str):
        """
        Registers both the Python function and its SQL-based wrapper.
        The SQL wrapper is defined using a SQL DDL statement that maps the Python function's parameters
        (with the extra secret parameter) and calls the Python function.

        Args:
            func (callable): The original Python function.
            secret_scope (str): The secret's scope.
            secret_key (str): The secret's key.
        """
        # First, register the Python function.
        self.register_function(func, secret_scope, secret_key)

        # Build SQL parameter definitions and call list.
        param_decls, param_calls = self.get_sql_parameters(func)
        # full_param_decls = (
        #     f"{param_decls}, secret STRING" if param_decls else "secret STRING"
        # )
        # # For the SQL wrapper call, we append the secret literal.
        if param_calls:
            call_arguments = f"{param_calls}, {self.get_sql_secret_placeholder(secret_scope, secret_key)}"
        else:
            call_arguments = self.get_sql_secret_placeholder(secret_scope, secret_key)

        func_name = f"{settings.uc_catalog}.{settings.uc_schema}.{func.__name__}_sql"
        comment = func.__doc__ or "No description available."
        sql_body = f"""CREATE OR REPLACE FUNCTION {func_name}({param_decls})
RETURNS STRING
LANGUAGE SQL
COMMENT {repr(comment)}
RETURN SELECT {settings.uc_catalog}.{settings.uc_schema}.{func.__name__}({call_arguments});
"""
        try:
            self.client.create_function(sql_function_body=sql_body)
            print(f"Registered SQL wrapper function '{func_name}'.")
        except Exception as e:
            print(f"Error registering SQL wrapper function '{func_name}': {e}")

    def register_functions_from_module(
        self,
        module,
        prefixes,
        secret_scope: str = "default_scope",
        secret_key: str = "default_key",
    ):
        """
        Iterate over the attributes of a module and register any callable that starts with one of the provided prefixes.
        This method now registers the SQL wrapper for each function.

        Args:
            module: The module to inspect.
            prefixes (list[str]): List of name prefixes to filter functions.
            secret_scope (str): The secret's scope.
            secret_key (str): The secret's key.
        """
        for name, member in module.__dict__.items():
            if callable(member) and any(name.startswith(prefix) for prefix in prefixes):
                print(f"Found function '{name}' in module '{module.__name__}'")
                self.register_with_sql_wrapper(
                    member, settings.secret_scope, settings.secret_key
                )

    def register_all_uc_functions(self):
        """
        Iterate over selected Databricks SDK modules and register functions in Unity Catalog.
        Both the Python function and its SQL wrapper are registered.
        """
        from databricks.sdk.service.jobs import JobsAPI
        from databricks.sdk import WorkspaceAPI
        from databricks.sdk.service.compute import ClustersAPI

        modules_to_register = [
            (JobsAPI, ["get", "list"]),
            (WorkspaceAPI, ["list"]),
            (ClustersAPI, ["get", "list", "events"]),
        ]

        for module, prefixes in modules_to_register:
            self.register_functions_from_module(module, prefixes)

    def get_sql_secret_placeholder(self, secret_scope: str, secret_key: str) -> str:
        """
        Returns a placeholder string for use in SQL wrappers.
        (Not used in Python function registration anymore since the secret is passed in as a parameter.)
        """
        return f"secret('{secret_scope}', '{secret_key}')"


if __name__ == "__main__":
    registrar = DatabricksSDKRegistrar()

    # Example: Register all default UC functions from Databricks SDK.
    registrar.register_all_uc_functions()

    # Example: To register a specific function with a SQL wrapper and pass a secret,
    # you can define your function and then call:
    #
    # def my_function(x: int) -> int:
    #     """Doubles the value of x."""
    #     return x * 2
    #
    # registrar.register_with_sql_wrapper(my_function,
    #                                     secret_scope="my_secret_scope",
    #                                     secret_key="my_secret_key")
