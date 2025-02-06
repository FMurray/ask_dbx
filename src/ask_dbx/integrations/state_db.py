import os
import sqlite3


class StateDatabase:
    def __init__(self, config):
        """
        Initialize the state database connection using SQLite.

        Args:
            config: The global settings object containing configuration values.
        """
        self.db_path = config.state_db_path

        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Connect to SQLite database (creates the file if it doesn't exist)
        self.conn = sqlite3.connect(self.db_path)
        self._initialize_database()

    def _initialize_database(self):
        """
        Create the tasks table if it does not exist.
        """
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL
                )
            """
            )
        print(f"StateDatabase: Database initialized at {self.db_path}")

    def update_task_state(self, task_id: int, state: str):
        """
        Update the state of a task in the database.
        If the task does not exist, it is inserted.

        Args:
            task_id (int): The ID of the task.
            state (str): The new state for the task.
        """
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
            result = cursor.fetchone()
            if result:
                cursor.execute(
                    "UPDATE tasks SET state = ? WHERE id = ?", (state, task_id)
                )
                print(f"StateDatabase: Updated task {task_id} to state '{state}'.")
            else:
                cursor.execute(
                    "INSERT INTO tasks (id, state) VALUES (?, ?)", (task_id, state)
                )
                print(f"StateDatabase: Inserted task {task_id} with state '{state}'.")
