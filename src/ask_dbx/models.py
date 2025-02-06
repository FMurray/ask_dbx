class Task:
    def __init__(self, id, details, documentation, state="PENDING"):
        self.id = id
        self.details = details
        self.documentation = documentation
        self.state = state

    def __repr__(self):
        return f"<Task {self.id}: {self.details} ({self.state})>"
