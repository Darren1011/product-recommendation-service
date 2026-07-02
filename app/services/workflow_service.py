from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.models import (
    Account,
    Opportunity,
    Product,
    RecommendationOption,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStep,
)
from app.services.recommender import RecommendationEngine


STEP_TEMPLATE = [
    ("analyze_request", "Analyze request"),
    ("match_catalog", "Match JSON catalog"),
    ("score_options", "Score product fit"),
    ("prepare_response", "Prepare recommendation"),
]


# Define the state passed between deterministic LangGraph nodes.
class RecommendationGraphState(TypedDict, total=False):
    """State carried through the local recommendation graph."""

    workflow_id: str
    query: str
    products: list[Product]
    account: Account | None
    opportunity: Opportunity | None
    candidate_products: list[Product]
    recommendations: list[RecommendationOption]
    step_details: dict[str, str]
    summary: str


# Keep workflow execution local and deterministic for the prototype.
class WorkflowService:
    """In-memory workflow runner that mimics the production API shape."""

    def __init__(self, recommender: RecommendationEngine) -> None:
        """Create empty workflow state for the current process."""
        # Store workflow status and results only for the running process.
        self.recommender = recommender
        self.status_by_id: dict[str, WorkflowStatus] = {}
        self.result_by_id: dict[str, WorkflowResult] = {}
        self.graph = self._build_graph()

    def run(
        self,
        query: str,
        products: list[Product],
        account: Account | None,
        opportunity: Opportunity | None,
    ) -> WorkflowResult:
        """Run the local recommendation workflow to completion."""
        # Create a workflow id that can be tracked by the frontend.
        workflow_id = str(uuid4())
        started_steps = _build_steps("running", "Workflow started")
        self.status_by_id[workflow_id] = WorkflowStatus(
            workflow_id=workflow_id,
            status="running",
            steps=started_steps,
            terminal=False,
        )

        # Execute the deterministic LangGraph pipeline over local JSON data.
        graph_state = self.graph.invoke(
            {
                "workflow_id": workflow_id,
                "query": query,
                "products": products,
                "account": account,
                "opportunity": opportunity,
                "step_details": {},
            }
        )

        # Convert graph output into the public workflow payload.
        recommendations = graph_state.get("recommendations", [])
        completed_steps = _build_completed_steps(graph_state.get("step_details", {}))
        result = WorkflowResult(
            workflow_id=workflow_id,
            query=query,
            account=account,
            opportunity=opportunity,
            steps=completed_steps,
            recommendations=recommendations,
            summary=graph_state.get("summary") or _build_summary(query, len(recommendations)),
        )

        # Store the completed state for status and result endpoints.
        self.result_by_id[workflow_id] = result
        self.status_by_id[workflow_id] = WorkflowStatus(
            workflow_id=workflow_id,
            status="completed",
            steps=completed_steps,
            terminal=True,
        )
        return result

    def get_status(self, workflow_id: str) -> WorkflowStatus | None:
        """Return the current status for a workflow."""
        return self.status_by_id.get(workflow_id)

    def get_result(self, workflow_id: str) -> WorkflowResult | None:
        """Return the completed workflow result."""
        return self.result_by_id.get(workflow_id)

    def _build_graph(self) -> Any:
        # Wire the prototype workflow with the same graph shape as the real service.
        workflow = StateGraph(RecommendationGraphState)
        workflow.add_node("analyze_request", self._analyze_request)
        workflow.add_node("match_catalog", self._match_catalog)
        workflow.add_node("score_options", self._score_options)
        workflow.add_node("prepare_response", self._prepare_response)
        workflow.add_edge(START, "analyze_request")
        workflow.add_edge("analyze_request", "match_catalog")
        workflow.add_edge("match_catalog", "score_options")
        workflow.add_edge("score_options", "prepare_response")
        workflow.add_edge("prepare_response", END)
        return workflow.compile()

    def _analyze_request(
        self,
        state: RecommendationGraphState,
    ) -> dict[str, dict[str, str]]:
        # Summarize the context that will influence scoring.
        context_bits = _describe_context(state.get("account"), state.get("opportunity"))
        detail = f"Parsed request and context: {context_bits}."
        return {"step_details": _merge_detail(state, "analyze_request", detail)}

    def _match_catalog(
        self,
        state: RecommendationGraphState,
    ) -> dict[str, object]:
        # Keep candidates available in the selected country when context exists.
        account = state.get("account")
        products = state.get("products", [])
        candidates = _filter_country_products(products, account)
        detail = f"Matched {len(candidates)} local JSON catalog candidates."
        return {
            "candidate_products": candidates,
            "step_details": _merge_detail(state, "match_catalog", detail),
        }

    def _score_options(
        self,
        state: RecommendationGraphState,
    ) -> dict[str, object]:
        # Rank candidates with deterministic scoring, not an external LLM.
        candidates = state.get("candidate_products") or state.get("products", [])
        recommendations = self.recommender.recommend(
            state["query"],
            candidates,
            state.get("account"),
            state.get("opportunity"),
        )
        detail = f"Scored candidates and selected {len(recommendations)} ranked cards."
        return {
            "recommendations": recommendations,
            "step_details": _merge_detail(state, "score_options", detail),
        }

    def _prepare_response(
        self,
        state: RecommendationGraphState,
    ) -> dict[str, object]:
        # Prepare final copy for the chat response and result payload.
        recommendations = state.get("recommendations", [])
        summary = _build_summary(state["query"], len(recommendations))
        return {
            "summary": summary,
            "step_details": _merge_detail(
                state,
                "prepare_response",
                "Prepared Good, Better, Best recommendation response.",
            ),
        }


# Build initial workflow steps before scoring completes.
def _build_steps(status: str, detail: str) -> list[WorkflowStep]:
    return [
        WorkflowStep(id=step_id, label=label, status=status, detail=detail)
        for step_id, label in STEP_TEMPLATE
    ]


# Build finished steps with simple receipt-style details.
def _build_completed_steps(details: dict[str, str]) -> list[WorkflowStep]:
    return [
        WorkflowStep(
            id=step_id,
            label=label,
            status="completed",
            detail=details.get(step_id, "Completed."),
        )
        for step_id, label in STEP_TEMPLATE
    ]


# Keep result summary deterministic and short.
def _build_summary(query: str, recommendations_count: int) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Generated {recommendations_count} JSON-backed recommendations for "
        f"'{query}' at {timestamp}."
    )


# Merge one graph receipt into the current detail map.
def _merge_detail(
    state: RecommendationGraphState,
    step_id: str,
    detail: str,
) -> dict[str, str]:
    step_details = dict(state.get("step_details", {}))
    step_details[step_id] = detail
    return step_details


# Use selected account geography as a lightweight availability filter.
def _filter_country_products(
    products: list[Product],
    account: Account | None,
) -> list[Product]:
    if account is None:
        return products
    return [
        product
        for product in products
        if account.country in product.inventory.countries
    ]


# Explain the context without exposing private or external data.
def _describe_context(account: Account | None, opportunity: Opportunity | None) -> str:
    details = []
    if account:
        details.append(f"{account.industry} account in {account.country}")
    if opportunity:
        details.append(f"opportunity '{opportunity.name}'")
    return ", ".join(details) if details else "no selected account or opportunity"
