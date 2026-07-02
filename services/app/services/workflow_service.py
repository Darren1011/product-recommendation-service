from datetime import UTC, datetime
from time import sleep
from threading import Lock, Thread
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
SIMULATED_STAGE_SECONDS = 2.5


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
    simulate_delay: bool
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
        self.lock = Lock()
        self.graph = self._build_graph()

    def start(
        self,
        query: str,
        products: list[Product],
        account: Account | None,
        opportunity: Opportunity | None,
        simulate_delay: bool = True,
    ) -> str:
        """Start a recommendation workflow in the background."""
        # Create a workflow id and publish pending steps before work begins.
        workflow_id = str(uuid4())
        self._set_status(
            WorkflowStatus(
                workflow_id=workflow_id,
                status="running",
                steps=_build_steps("pending", "Waiting to start."),
                terminal=False,
            )
        )

        # Run graph execution outside the request path so the UI can poll stages.
        thread = Thread(
            target=self.execute,
            args=(workflow_id, query, products, account, opportunity, simulate_delay),
            daemon=True,
        )
        thread.start()
        return workflow_id

    def run(
        self,
        query: str,
        products: list[Product],
        account: Account | None,
        opportunity: Opportunity | None,
    ) -> WorkflowResult:
        """Run the local recommendation workflow to completion."""
        # Keep a synchronous no-delay path for tests and local scripts.
        workflow_id = str(uuid4())
        self._set_status(
            WorkflowStatus(
                workflow_id=workflow_id,
                status="running",
                steps=_build_steps("pending", "Waiting to start."),
                terminal=False,
            )
        )
        self.execute(workflow_id, query, products, account, opportunity, False)
        result = self.get_result(workflow_id)
        if result is None:
            raise RuntimeError("Recommendation workflow did not produce a result")
        return result

    def execute(
        self,
        workflow_id: str,
        query: str,
        products: list[Product],
        account: Account | None,
        opportunity: Opportunity | None,
        simulate_delay: bool,
    ) -> None:
        """Execute a workflow and update in-memory status after each stage."""
        # Execute the deterministic LangGraph pipeline over local JSON data.
        graph_state = self.graph.invoke(
            {
                "workflow_id": workflow_id,
                "query": query,
                "products": products,
                "account": account,
                "opportunity": opportunity,
                "simulate_delay": simulate_delay,
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
        with self.lock:
            self.result_by_id[workflow_id] = result
            self.status_by_id[workflow_id] = WorkflowStatus(
                workflow_id=workflow_id,
                status="completed",
                steps=completed_steps,
                terminal=True,
            )
        return None

    def _set_status(self, status: WorkflowStatus) -> None:
        # Write status updates under a lock because the graph runs in a thread.
        with self.lock:
            self.status_by_id[status.workflow_id] = status

    def _mark_step(
        self,
        workflow_id: str,
        step_id: str,
        status: str,
        detail: str,
    ) -> None:
        # Update one step while preserving all other visible workflow rows.
        with self.lock:
            current_status = self.status_by_id.get(workflow_id)
            if current_status is None:
                return
            updated_steps = [
                _update_step(step, step_id, status, detail)
                for step in current_status.steps
            ]
            self.status_by_id[workflow_id] = WorkflowStatus(
                workflow_id=workflow_id,
                status="running",
                steps=updated_steps,
                terminal=False,
            )

    def _run_visible_stage(
        self,
        state: RecommendationGraphState,
        step_id: str,
        running_detail: str,
    ) -> None:
        # Publish a running state and pause so the UI can show this stage.
        self._mark_step(state["workflow_id"], step_id, "running", running_detail)
        if state.get("simulate_delay"):
            sleep(SIMULATED_STAGE_SECONDS)

    def _complete_visible_stage(
        self,
        state: RecommendationGraphState,
        step_id: str,
        completed_detail: str,
    ) -> None:
        # Publish a completed state after the graph node finishes its work.
        self._mark_step(state["workflow_id"], step_id, "completed", completed_detail)

    def get_status(self, workflow_id: str) -> WorkflowStatus | None:
        """Return the current status for a workflow."""
        with self.lock:
            return self.status_by_id.get(workflow_id)

    def get_result(self, workflow_id: str) -> WorkflowResult | None:
        """Return the completed workflow result."""
        with self.lock:
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
        # Show the input analysis stage before calculating context details.
        self._run_visible_stage(
            state,
            "analyze_request",
            "Reading request and selected context.",
        )

        # Summarize the context that will influence scoring.
        context_bits = _describe_context(state.get("account"), state.get("opportunity"))
        query_detail = _describe_query_source(state.get("query", ""))
        detail = f"Parsed {query_detail}; using {context_bits}."
        self._complete_visible_stage(state, "analyze_request", detail)
        return {"step_details": _merge_detail(state, "analyze_request", detail)}

    def _match_catalog(
        self,
        state: RecommendationGraphState,
    ) -> dict[str, object]:
        # Show catalog matching while local JSON candidates are filtered.
        self._run_visible_stage(
            state,
            "match_catalog",
            "Filtering local JSON catalog candidates.",
        )

        # Keep candidates available in the selected country when context exists.
        account = state.get("account")
        products = state.get("products", [])
        candidates = _filter_country_products(products, account)
        detail = f"Matched {len(candidates)} local JSON catalog candidates."
        self._complete_visible_stage(state, "match_catalog", detail)
        return {
            "candidate_products": candidates,
            "step_details": _merge_detail(state, "match_catalog", detail),
        }

    def _score_options(
        self,
        state: RecommendationGraphState,
    ) -> dict[str, object]:
        # Show scoring while the deterministic recommender ranks products.
        self._run_visible_stage(
            state,
            "score_options",
            "Scoring product fit for Good, Better, Best.",
        )

        # Rank candidates with deterministic scoring, not an external LLM.
        candidates = state.get("candidate_products") or state.get("products", [])
        recommendations = self.recommender.recommend(
            state["query"],
            candidates,
            state.get("account"),
            state.get("opportunity"),
        )
        detail = f"Scored candidates and selected {len(recommendations)} ranked cards."
        self._complete_visible_stage(state, "score_options", detail)
        return {
            "recommendations": recommendations,
            "step_details": _merge_detail(state, "score_options", detail),
        }

    def _prepare_response(
        self,
        state: RecommendationGraphState,
    ) -> dict[str, object]:
        # Show response preparation before final cards are made available.
        self._run_visible_stage(
            state,
            "prepare_response",
            "Preparing recommendation cards and receipts.",
        )

        # Prepare final copy for the chat response and result payload.
        recommendations = state.get("recommendations", [])
        summary = _build_summary(state["query"], len(recommendations))
        detail = "Prepared Good, Better, Best recommendation response."
        self._complete_visible_stage(state, "prepare_response", detail)
        return {
            "summary": summary,
            "step_details": _merge_detail(
                state,
                "prepare_response",
                detail,
            ),
        }


# Build initial workflow steps before scoring completes.
def _build_steps(status: str, detail: str) -> list[WorkflowStep]:
    return [
        WorkflowStep(id=step_id, label=label, status=status, detail=detail)
        for step_id, label in STEP_TEMPLATE
    ]


# Replace one step in the visible status list.
def _update_step(
    step: WorkflowStep,
    target_step_id: str,
    status: str,
    detail: str,
) -> WorkflowStep:
    if step.id != target_step_id:
        return step
    return WorkflowStep(
        id=step.id,
        label=step.label,
        status=status,
        detail=detail,
    )


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
    query_text = query.strip() or "selected context"
    return (
        f"Generated {recommendations_count} JSON-backed recommendations for "
        f"'{query_text}' at {timestamp}."
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


# Explain whether recommendations came from text or selected context.
def _describe_query_source(query: str) -> str:
    if query.strip():
        return "typed request"
    return "selected context only"
