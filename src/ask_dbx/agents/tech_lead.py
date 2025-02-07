from ask_dbx.models import Task
from langgraph.graph import StateGraph, END
from databricks_langchain import ChatDatabricks
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.schema.output_parser import StrOutputParser
from typing import Literal
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


class TechLead:
    def __init__(self, retriever, config):
        self.retriever = retriever
        self.config = config
        self.llm = ChatDatabricks(endpoint=config.gpt_model)
        self._setup_chains()

    def _setup_chains(self):
        """Set up the LangChain chains used by the agent with structured output support."""
        # Summarization chain: no structured output needed here.
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

        # Decision chain: using structured output.
        decision_template = (
            "Question: {job_requirements}\n\n"
            "Current plan (if any): {plan}\n\n"
            "Based on the above, should I retrieve additional documentation?\n"
        )
        decision_prompt = PromptTemplate.from_template(decision_template)
        self.decision_chain = decision_prompt | self.llm.with_structured_output(
            RetrieveDecision
        )

        # Filter docs chain now uses the FilterResponse model with Literal output.
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

        # Plan generation chain remains free-form.
        plan_template = (
            "Based on the following job requirements:\n{job_requirements}\n\n"
            "and the following relevant documentation:\n{docs}\n\n"
            "Generate a detailed plan as a numbered list of actionable tasks to automate Databricks job creation."
        )
        self.plan_chain = (
            PromptTemplate.from_template(plan_template) | self.llm | StrOutputParser()
        )

        # Verification chain: structured output.
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

        # Rating chain: structured output.
        rating_template = (
            "Question: {job_requirements}\n\n"
            "Plan: {plan}\n\n"
            "On a scale from 1 to 5 (where 5 is excellent), how useful is the plan in addressing the question?\n"
            "Return just a single integer between 1 and 5."
        )
        rating_prompt = PromptTemplate.from_template(rating_template)
        self.rating_chain = rating_prompt | self.llm.with_structured_output(PlanRating)

    def analyze_job_requirements(self) -> Task:
        """
        Builds a LangGraph-based agent that:
          - Summarizes the job requirements and current plan to generate a focused query
          - Retrieves and filters documentation (with parallel filtering)
          - Generates a plan
          - Verifies the plan's support from the documentation
          - Rates the plan's usefulness
          - Decides whether additional retrieval is necessary
        """
        with open(self.config.job_requirements_path, "r") as f:
            markdown_requirements = f.read()

        MAX_ITERATIONS = 5
        initial_state = {
            "job_requirements": markdown_requirements,
            "docs": {},  # will be a dict mapping doc.metadata.id -> {doc, filter_score, verify_score}
            "plan": "",
            "verification": "",
            "rating": 0,
            "retrieve_decision": "",
            "iteration": 0,
            "done": False,
            "search_query": "",  # Generated search query
        }

        def summarize_question(state: dict) -> dict:
            """Generates a focused search query based on the job requirements and current plan."""
            query = self.summarize_chain.invoke(
                {"job_requirements": state["job_requirements"], "plan": state["plan"]}
            )
            state["search_query"] = query
            print(f"Summarized query: {query}")
            return state

        def retrieve_docs(state: dict) -> dict:
            iteration = state.get("iteration", 0) + 1
            state["iteration"] = iteration

            # Use the current search query generated by the summarization.
            base_query = state["search_query"]
            if iteration > 1:
                query = f"{base_query} | Additional info needed to refine plan: {state['plan']}"
            else:
                query = base_query

            doc_chunks = self.retriever.get_relevant_documents(
                query, k=10, query_type="hybrid", columns=["content", "chunk_id"]
            )
            for d in doc_chunks:
                # Store the full document and initialize scoring flags.
                state["docs"][d.metadata["id"]] = {
                    "doc": d,
                    "filter_score": None,
                    "verify_score": None,
                }
            print(
                f"Retrieve Docs: Retrieved {len(doc_chunks)} chunks using query: {query}"
            )
            return state

        def filter_docs(state: dict) -> dict:
            """Parallelizes filtering of document chunks using structured output."""
            docs = state["docs"]
            job_requirements = state["job_requirements"]

            # Prepare to filter only those docs that haven't been scored.
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

            # Remove docs that are scored as irrelevant.
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
            # Prepare inputs for docs that haven't been verified.
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
            # Batch call to the verify chain for all unscored docs.
            if unscored_inputs:
                responses = self.verify_chain.batch(unscored_inputs)
                for doc_id, response in zip(unscored_ids, responses):
                    docs[doc_id]["verify_score"] = response.verification.lower().strip()

            # Accumulate all verification scores.
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
            if state["iteration"] >= MAX_ITERATIONS:
                print("Maximum iterations reached; finalizing plan.")
                return END
            if ("fully supported" in state["verification"]) and (state["rating"] >= 4):
                state["done"] = True
                print(
                    f"Plan accepted with rating {state['rating']} and verification: {state['verification']}"
                )
                return END
            # Update the search query based on the current plan before new retrieval.
            return "summarize_question" if "yes" in state["retrieve_decision"] else END

        # Build the LangGraph with the new flow.
        graph = StateGraph(dict)
        graph.add_node("summarize_question", summarize_question)
        graph.add_node("retrieve_docs", retrieve_docs)
        graph.add_node("filter_docs", filter_docs)
        graph.add_node("generate_plan", generate_plan)
        graph.add_node("verify_plan_support", verify_plan_support)
        graph.add_node("rate_plan", rate_plan)
        graph.add_node("decide_retrieve", decide_retrieve)

        # Set up execution order:
        graph.set_entry_point("summarize_question")
        graph.add_edge("summarize_question", "retrieve_docs")
        graph.add_edge("retrieve_docs", "filter_docs")
        graph.add_edge("filter_docs", "generate_plan")
        graph.add_edge("generate_plan", "verify_plan_support")
        graph.add_edge("verify_plan_support", "rate_plan")
        graph.add_edge("rate_plan", "decide_retrieve")
        graph.add_conditional_edges("decide_retrieve", branch_decide)

        # Execute the graph.
        compiled_graph = graph.compile()
        final_state = compiled_graph.invoke(initial_state)

        # Build the final Task.
        task = Task(
            id=1,
            details=final_state.get("plan", "No plan generated."),
            documentation="\n".join(
                info["doc"].page_content
                for info in final_state.get("docs", {}).values()
            ),
            state="PENDING",
        )
        print("TechLead: Finalized task details:")
        print(task.details)
        return task
