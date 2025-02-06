# Product Requirements Document (PRD): Databricks Job Automation Agent

## 1. Introduction

### 1.1 Purpose

The purpose of this document is to outline the requirements, features, and design for the Databricks Job Automation Agent. This agent aims to automate the creation and management of jobs on Databricks by reducing manual intervention, minimizing errors, and streamlining the workflow using AI-powered components.

### 1.2 Scope

The project will deliver an AI agent that:
- Integrates with the Databricks ecosystem via the Databricks Python SDK.
- Retrieves relevant documentation through a built-in retriever.
- Tracks high-level tasks using local markdown files.
- Manages task state via a dedicated database.
- Operates with two core components: a Tech Lead and a Worker.

### 1.3 Definitions, Acronyms, and Abbreviations

- **Databricks:** A unified analytics platform.
- **Tech Lead:** The persona responsible for task analysis and assignment.
- **Worker:** The persona executing the tasks following a validate-plan-apply workflow.
- **SDK:** Software Development Kit.
- **ASK:** Agent Software Kit.
- **Retriever:** A tool for fetching relevant documentation content.
- **State Database:** A storage system for task statuses (e.g., IN_PROGRESS, COMPLETE, FAILED).

## 2. System Overview

The Databricks Job Automation Agent is designed to simplify and automate job creation on the Databricks platform. It operates by dividing responsibilities between two specialized personas:
- **Tech Lead:** Reviews and decomposes job requirements.
- **Worker:** Executes the job creation process in three phases (Validate, Plan, Apply).

The agent also integrates several external tools to enhance its capabilities and ensure robust state tracking and documentation.

## 3. Functional Requirements

### 3.1 Multi-Persona Architecture

- **Tech Lead Component:**
  - Interpret job requirements.
  - Use the retriever tool to obtain relevant documentation.
  - Assign tasks with detailed specifications to the Worker.

- **Worker Component:**
  - **Validate Phase:** Verify that the task is in the correct state and meets all prerequisites.
  - **Plan Phase:** Generate a sequence of actionable steps to execute the task.
  - **Apply Phase:** Execute the steps by interfacing with the Databricks Python SDK and updating the state database.

### 3.2 Tool Integrations

- **Retriever:**
  - Must allow keyword-based retrieval of documentation content from Databricks docs.
  - Ensure that the retrieved information is relevant to the current job/task.

- **Databricks Python SDK:**
  - Must support all necessary operations for job creation and management.
  - Provide error handling and logging for API interactions.

- **Local Markdown Files:**
  - Must support read/write operations to track task progress and decisions.
  - Serve as an audit trail for high-level task management.

- **State Database:**
  - Must record task states (e.g., IN_PROGRESS, COMPLETE, FAILED).
  - Enable efficient querying and updating of task statuses.

- **Unity Catalog Integration:**
  - Integrate with the Unity Catalog AI package to leverage UC functions as agile automation tools.
  - Use the `UnitycatalogFunctionClient` for initializing and managing UC functions.
  - For Databricks-managed Unity Catalog setups, support configuration with the `DatabricksFunctionClient`.
  - Provide functionality to create UC functions using Python callables or SQL definitions.
  - Expose UC functions as native Langchain tools via the `UCFunctionToolkit` for dynamic function invocation within the automation workflow.
  - Ensure robust error handling, logging, and secure management of function definitions.
  - **Reference:** [Unity Catalog Integration with Langchain](https://github.com/unitycatalog/unitycatalog/tree/main/ai/integrations/langchain)

### 3.3 Workflow Execution

- **Validation:**  
  Confirm prerequisites and current task state before proceeding.

- **Planning:**  
  Break down the task into a detailed list of steps, similar to Terraform's plan phase.

- **Application:**  
  Execute the planned steps by interfacing with external tools and update the task state accordingly.

### 3.4 Error Handling and Logging

- Implement robust error handling for failures in any phase of the workflow.
- Log critical events, decisions, and state changes to aid in troubleshooting and auditing.

### 3.5 Evaluation and Feedback for GenAI Agents

- **Automated Performance Evaluation:**
  - Integrate Databricks capabilities for evaluating GenAI agents through a custom metrics framework.
  - Implement a custom metrics system that allows developers to define evaluation metrics in Python (e.g., using the `@metric` decorator).
  - Leverage MLflow's evaluation method to pass these custom metrics via the `extra_metrics` field in `mlflow.evaluate()`.

- **Custom Metrics Requirements:**
  - Must allow developers to write custom evaluation metrics that can return pass/fail (e.g., `"yes"` or `"no"`), numeric (integers or floats), or boolean values.
  - Custom metrics should have full access to the evaluation data, including input requests, expected outputs, retrieved context, and detailed execution traces.
  - Enable the use of custom fields (e.g., a `custom_expected` field) to supply additional context for metric computations.
  - Ensure that the custom metrics framework is flexible enough to evaluate key performance indicators—such as response accuracy, retrieval precision, and compliance with guidelines—tailored to specific business use cases.
  - Integrate the output of custom metrics with dashboards, logs, and automated alerts to enable continuous monitoring and rapid troubleshooting.
  - **Reference:** [Custom Metrics Documentation](https://docs.databricks.com/en/generative-ai/agent-evaluation/custom-metrics.html)

- **User Feedback Incorporation:**
  - Provide mechanisms to capture end-user feedback through Databricks-supported interfaces.
  - Leverage this feedback in combination with custom metrics results to iteratively improve the AI agent's performance.

- **Continuous Monitoring and Iterative Improvement:**
  - Implement dashboards and logging integrations (e.g., via MLflow) for real-time monitoring of evaluation metrics.
  - Set up automated alerts using Databricks monitoring solutions to quickly identify and address performance degradations.
  - Define processes for periodically reviewing the custom metric evaluations and feedback, ensuring that insights are used to update the agent configuration and improve external integrations.

## 4. Non-functional Requirements

### 4.1 Performance

- The system should minimize latency in task processing.
- Efficient interaction with the Databricks APIs to ensure rapid job creation.

### 4.2 Reliability and Availability

- Ensure high reliability through error recovery and fallback mechanisms.
- Provide graceful degradation in case of integration failures.

### 4.3 Scalability

- Design the architecture to scale with increasing numbers of tasks and integrations.
- Allow for future expansion of supported Databricks operations.

### 4.4 Security

- Securely manage Databricks credentials and sensitive configuration data.
- Implement access controls for both local file operations and database interactions.

## 5. System Architecture

### 5.1 High-Level Architecture Diagram

*Diagram placeholder: Include a diagram illustrating the interaction between the Tech Lead, Worker, and integrated tools (Retriever, Databricks SDK, Markdown Manager, and State Database).*

### 5.2 Data Flow

1. **User Input:**  
   Job requirements are provided by the user.
2. **Tech Lead Processing:**  
   - Requirements are analyzed.
   - Relevant documentation is retrieved.
   - Tasks are formulated and assigned.
3. **Worker Execution:**  
   - Validation of prerequisites.
   - Planning of detailed execution steps.
   - Application of steps through Databricks API calls.
4. **State Management:**  
   The database is updated with the current task state.
5. **Documentation:**  
   Local markdown files are updated with task details and progress.

## 6. Use Cases

### 6.1 Create Job Use Case

- **Actors:**  
  User, Tech Lead, Worker.
- **Description:**  
  A user provides job requirements. The Tech Lead processes these requirements and assigns a task to the Worker. The Worker then validates, plans, and applies the necessary steps to create a new job on Databricks.
- **Preconditions:**  
  Databricks workspace credentials are configured, and the state database is initialized.
- **Postconditions:**  
  A new job is created, and the state is updated to reflect the job's progress.

### 6.2 Update Job Use Case

- **Actors:**  
  User, Tech Lead, Worker.
- **Description:**  
  The system updates an existing job based on revised requirements. The Tech Lead reassesses the job details, and the Worker re-executes the validate-plan-apply process.
- **Preconditions:**  
  The job exists and is accessible.
- **Postconditions:**  
  The job is updated, and changes are tracked via the state database and markdown documentation.

## 7. Milestones and Timeline

- **Phase 1: Design and Integration Setup**  
  - Define architecture and component interactions.
  - Set up initial integrations (retriever, markdown file manager, state database).

- **Phase 2: Core Functionality Implementation**  
  - Develop the Tech Lead process.
  - Implement the Worker's validate-plan-apply workflow.

- **Phase 3: Full Integration & Testing**  
  - Integrate with the Databricks Python SDK.
  - Conduct comprehensive testing and error handling improvements.

- **Phase 4: Documentation & Deployment**  
  - Finalize user and developer documentation.
  - Deploy the solution and gather user feedback.

## 8. Risks and Mitigations

- **Integration Complexity:**  
  - *Risk:* Challenges integrating with the Databricks API and documentation systems.  
  - *Mitigation:* Early prototyping and iterative testing; fallback mechanisms in case of API failures.

- **State Management:**  
  - *Risk:* Inconsistent state updates or race conditions.  
  - *Mitigation:* Use transactional database operations and robust error handling.

- **Documentation Accuracy:**  
  - *Risk:* The retriever may not always return the most relevant documentation.  
  - *Mitigation:* Allow manual overrides and maintain logs for review.

## 9. Future Enhancements

- Expand support to additional Databricks operations beyond job creation.
- Integrate advanced AI features for improved task prioritization and dynamic workflow adjustments.
- Enhance collaboration features for multi-user environments.

## 10. Appendices

- **Appendix A:** Glossary of Terms.
- **Appendix B:** List of External Dependencies and Libraries.
- **Appendix C:** Detailed Architecture Diagrams (if available).
