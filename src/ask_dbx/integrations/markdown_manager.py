import os


class MarkdownManager:
    def __init__(self, config):
        """
        Initialize the Markdown Manager with configuration.

        Args:
            config: The global settings object containing configuration values.
        """
        self.config = config
        self.file_path = config.markdown_path

        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def write_update(self, task):
        """
        Append task details and state update information in markdown format.

        Args:
            task: An object with attributes 'id', 'details', and 'state'.
        """
        try:
            with open(self.file_path, "a") as f:
                f.write(f"## Task {task.id}\n")
                f.write(f"- **Details:** {task.details}\n")
                f.write(f"- **State:** {task.state}\n")
                f.write("\n")
            print(
                f"MarkdownManager: Updated markdown file at {self.file_path} for task {task.id}"
            )
        except Exception as e:
            print(
                f"MarkdownManager: Failed to write update for task {task.id} due to: {e}"
            )
