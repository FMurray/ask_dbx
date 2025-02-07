from ask_dbx.models import Task
from langgraph.graph import StateGraph, END
from databricks_langchain import ChatDatabricks
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.schema.output_parser import StrOutputParser
from typing import Literal, List
from pydantic import BaseModel, Field
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from concurrent.futures import ThreadPoolExecutor, as_completed
# Define structured responses using Pydantic.


class RetrieveDecision(BaseModel):
    """Is the plan sufficiently supported by the documentation?"""

    decision: Literal["yes", "no"] = Field(
        ..., description="Answer must be one of 'yes', 'no'."
    )


class PlanRating(BaseModel):
    """How useful is the plan?"""

    rating: int = Field(
        ..., ge=1, le=5, description="Rating as an integer between 1 and 5."
    )


class PlanVerification(BaseModel):
    """Does the plan support the requirements?"""

    verification: Literal[
        "fully supported", "partially supported", "no support"
    ] = Field(
        ...,
        description="Answer must be one of 'fully supported', 'partially supported', or 'no support'.",
    )


class FilterResponse(BaseModel):
    """Is the document relevant to the requirements?"""

    verification: Literal["relevant", "irrelevant"] = Field(
        ..., description="Answer must be one of 'relevant' or 'irrelevant'."
    )


class TaskList(BaseModel):
    tasks: List[Task]


class TechLead:
    def __init__(self, retriever, config):
        self.retriever = retriever
        self.config = config
        self.llm = ChatDatabricks(endpoint=config.gpt_model)
        self._setup_chains()
        # Build and compile the analysis graph during initialization.
        self._build_analyze_graph()
        # The compiled graph is available as self.g_analyze_job_requirements.

    def _setup_chains(self):
        """Set up the LangChain chains used by the agent with structured output support."""
        summarize_template = (
            "Given the following job requirements and the current plan, generate a focused search query "
            "that will help retrieve documentation to address any gaps in our plan for Databricks job creation.\n"
            "If the current plan is empty, rely solely on the job requirements.\n"
            "Otherwise, consider what additional details are needed to improve or refine the plan.\n\n"
            "Job Requirements:\n{job_requirements}\n\n"
            "Current Plan:\n{plan}\n\n"
            "Provide a concise search query:"
        )
        self.summarize_chain = (
            PromptTemplate.from_template(summarize_template)
            | self.llm
            | StrOutputParser()
        )

        decision_template = (
            "Question: {job_requirements}\n\n"
            "Current plan (if any): {plan}\n\n"
            "Based on the above, should I retrieve additional documentation?\n"
        )
        decision_prompt = PromptTemplate.from_template(decision_template)
        self.decision_chain = decision_prompt | self.llm.with_structured_output(
            RetrieveDecision
        )

        filter_template = (
            "Question: {job_requirements}\n\n"
            "Document chunk: {doc}\n\n"
            "Does this document chunk provide useful information to solve the question?\n"
            "Answer with either 'relevant' or 'irrelevant'."
        )
        filter_prompt = PromptTemplate.from_template(filter_template)
        self.filter_chain = filter_prompt | self.llm.with_structured_output(
            FilterResponse
        )

        plan_template = (
            "Based on the following job requirements:\n{job_requirements}\n\n"
            "and the following relevant documentation:\n{docs}\n\n"
            "Generate a detailed plan as a numbered list of actionable tasks to automate Databricks job creation."
        )
        self.plan_chain = (
            PromptTemplate.from_template(plan_template) | self.llm | StrOutputParser()
        )

        verify_template = (
            "Question: {job_requirements}\n\n"
            "Document chunk: {doc}\n\n"
            "Plan: {plan}\n\n"
            "Evaluate whether the plan's statements are supported by the document chunk.\n"
            "Answer with 'fully supported', 'partially supported', or 'no support'."
        )
        verify_prompt = PromptTemplate.from_template(verify_template)
        self.verify_chain = verify_prompt | self.llm.with_structured_output(
            PlanVerification
        )

        rating_template = (
            "Question: {job_requirements}\n\n"
            "Plan: {plan}\n\n"
            "On a scale from 1 to 5 (where 5 is excellent), how useful is the plan in addressing the question?\n"
            "Return just a single integer between 1 and 5."
        )
        rating_prompt = PromptTemplate.from_template(rating_template)
        self.rating_chain = rating_prompt | self.llm.with_structured_output(PlanRating)

        split_plan_template = (
            "The final plan is as follows:\n{plan}\n\n"
            "Please split this plan into a list of individual tasks. Each task should include"
            " a 'details' field describing the task"
        )
        self.split_plan_chain = PromptTemplate.from_template(
            split_plan_template
        ) | self.llm.with_structured_output(TaskList)

    def _build_analyze_graph(self):
        """
        Constructs and compiles the LangGraph for analyzing job requirements.
        This is called during __init__ and assigns the compiled graph to the instance.
        """

        def summarize_question(state: dict) -> dict:
            query = self.summarize_chain.invoke(
                {"job_requirements": state["job_requirements"], "plan": state["plan"]}
            )
            state["search_query"] = query
            print(f"Summarized query: {query}")
            return state

        def retrieve_docs(state: dict) -> dict:
            iteration = state.get("iteration", 0) + 1
            state["iteration"] = iteration
            base_query = state["search_query"]
            query = (
                base_query
                if iteration == 1
                else f"{base_query} | Additional info needed to refine plan: {state['plan']}"
            )
            doc_chunks = self.retriever.get_relevant_documents(
                query, k=10, query_type="hybrid", columns=["content", "chunk_id"]
            )
            for d in doc_chunks:
                doc_id = d.metadata["id"]
                if doc_id not in state["docs"]:
                    state["docs"][doc_id] = {
                        "doc": d,
                        "filter_score": None,
                        "verify_score": None,
                    }
            print(
                f"Retrieve Docs: Retrieved {len(doc_chunks)} chunks using query: {query}"
            )
            return state

        def filter_docs(state: dict) -> dict:
            docs = state["docs"]
            job_requirements = state["job_requirements"]
            unscored_ids = []
            unscored_inputs = []
            for doc_id, doc_info in docs.items():
                if doc_info["filter_score"] is None:
                    unscored_inputs.append(
                        {
                            "job_requirements": job_requirements,
                            "doc": doc_info["doc"].page_content,
                        }
                    )
                    unscored_ids.append(doc_id)
            if unscored_inputs:
                responses = self.filter_chain.batch(unscored_inputs)
                for doc_id, response in zip(unscored_ids, responses):
                    docs[doc_id]["filter_score"] = response.verification.lower().strip()
            filtered_docs = {
                doc_id: info
                for doc_id, info in docs.items()
                if info["filter_score"] == "relevant"
            }
            state["docs"] = filtered_docs
            print(f"Filter Docs: Retained {len(filtered_docs)} relevant chunks.")
            return state

        def generate_plan(state: dict) -> dict:
            docs = state["docs"]
            docs_text = (
                "\n".join(info["doc"].page_content for info in docs.values())
                if docs
                else "No documentation available."
            )
            response = self.plan_chain.invoke(
                {"job_requirements": state["job_requirements"], "docs": docs_text}
            )
            state["plan"] = response
            print("Generate Plan: Generated plan:")
            print(response)
            return state

        def verify_plan_support(state: dict) -> dict:
            docs = state["docs"]
            unscored_ids = []
            unscored_inputs = []
            for doc_id, doc_info in docs.items():
                if doc_info["verify_score"] is None:
                    unscored_inputs.append(
                        {
                            "job_requirements": state["job_requirements"],
                            "doc": doc_info["doc"].page_content,
                            "plan": state["plan"],
                        }
                    )
                    unscored_ids.append(doc_id)
            if unscored_inputs:
                responses = self.verify_chain.batch(unscored_inputs)
                for doc_id, response in zip(unscored_ids, responses):
                    docs[doc_id]["verify_score"] = response.verification.lower().strip()
            verifications = [info["verify_score"] for info in docs.values()]
            if any("no support" in v for v in verifications):
                overall = "partially supported"
            elif verifications and all("fully supported" in v for v in verifications):
                overall = "fully supported"
            else:
                overall = "partially supported"
            state["verification"] = overall
            print("Verify Plan Support: Overall verification:", overall)
            return state

        def rate_plan(state: dict) -> dict:
            response = self.rating_chain.invoke(
                {
                    "job_requirements": state["job_requirements"],
                    "plan": state["plan"],
                }
            )
            state["rating"] = response.rating
            print("Rate Plan: Rated plan with a score of", response.rating)
            return state

        def decide_retrieve(state: dict) -> dict:
            response = self.decision_chain.invoke(
                {
                    "job_requirements": state["job_requirements"],
                    "plan": state["plan"],
                }
            )
            state["retrieve_decision"] = response.decision.lower().strip()
            print("Decide Retrieve:", state["retrieve_decision"])
            return state

        def branch_decide(state: dict) -> str:
            MAX_ITERATIONS = 5
            if state["iteration"] >= MAX_ITERATIONS:
                print("Maximum iterations reached; finalizing plan.")
                return END
            if ("fully supported" in state["verification"]) and (state["rating"] >= 4):
                state["done"] = True
                print(
                    f"Plan accepted with rating {state['rating']} and verification: {state['verification']}"
                )
                return END
            return "summarize_question" if "yes" in state["retrieve_decision"] else END

        graph = StateGraph(dict)
        graph.add_node("summarize_question", summarize_question)
        graph.add_node("retrieve_docs", retrieve_docs)
        graph.add_node("filter_docs", filter_docs)
        graph.add_node("generate_plan", generate_plan)
        graph.add_node("verify_plan_support", verify_plan_support)
        graph.add_node("rate_plan", rate_plan)
        graph.add_node("decide_retrieve", decide_retrieve)
        graph.set_entry_point("summarize_question")
        graph.add_edge("summarize_question", "retrieve_docs")
        graph.add_edge("retrieve_docs", "filter_docs")
        graph.add_edge("filter_docs", "generate_plan")
        graph.add_edge("generate_plan", "verify_plan_support")
        graph.add_edge("verify_plan_support", "rate_plan")
        graph.add_edge("rate_plan", "decide_retrieve")
        graph.add_conditional_edges("decide_retrieve", branch_decide)

        self.g_analyze_job_requirements = graph.compile()
        print(
            "TechLead: Compiled analysis graph stored in 'g_analyze_job_requirements'."
        )

    def _analyze_job_requirements(self) -> dict:
        """
        Private method to execute the analysis graph.
        Loads job requirements from file, constructs the initial state,
        and invokes the compiled graph.
        Returns:
            dict: The final state resulting from the graph flow.
        """
        with open(self.config.job_requirements_path, "r") as f:
            markdown_requirements = f.read()

        initial_state = {
            "job_requirements": markdown_requirements,
            "docs": {},
            "plan": "",
            "verification": "",
            "rating": 0,
            "retrieve_decision": "",
            "iteration": 0,
            "done": False,
            "search_query": "",
        }

        final_state = self.g_analyze_job_requirements.invoke(initial_state)
        return final_state

    def analyze_job_requirements(self) -> TaskList:
        """
        Public API method to analyze job requirements.
        Executes the analysis graph and then splits the final plan into a TaskList.

        Returns:
            TaskList: The parsed list of actionable tasks.
        """
        final_state = self._analyze_job_requirements()
        tasks: TaskList = self.split_plan_chain.invoke({"plan": final_state["plan"]})
        return tasks
