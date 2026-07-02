from datetime import UTC, datetime
from uuid import uuid4

from app.models import (
    Account,
    Opportunity,
    Product,
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


# Keep workflow execution local and deterministic for the prototype.
class WorkflowService:
    """In-memory workflow runner that mimics the production API shape."""

    def __init__(self, recommender: RecommendationEngine) -> None:
        """Create empty workflow state for the current process."""
        # Store workflow status and results only for the running process.
        self.recommender = recommender
        self.status_by_id: dict[str, WorkflowStatus] = {}
        self.result_by_id: dict[str, WorkflowResult] = {}

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

        # Generate ranked recommendations synchronously from JSON data.
        recommendations = self.recommender.recommend(query, products, account, opportunity)
        completed_steps = _build_completed_steps(recommendations_count=len(recommendations))
        result = WorkflowResult(
            workflow_id=workflow_id,
            query=query,
            account=account,
            opportunity=opportunity,
            steps=completed_steps,
            recommendations=recommendations,
            summary=_build_summary(query, recommendations_count=len(recommendations)),
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


# Build initial workflow steps before scoring completes.
def _build_steps(status: str, detail: str) -> list[WorkflowStep]:
    return [
        WorkflowStep(id=step_id, label=label, status=status, detail=detail)
        for step_id, label in STEP_TEMPLATE
    ]


# Build finished steps with simple receipt-style details.
def _build_completed_steps(recommendations_count: int) -> list[WorkflowStep]:
    details = {
        "analyze_request": "Parsed request, account, and opportunity context.",
        "match_catalog": "Loaded product candidates from local JSON files.",
        "score_options": f"Ranked candidates and selected {recommendations_count} options.",
        "prepare_response": "Prepared card explanations and workflow payload.",
    }
    return [
        WorkflowStep(id=step_id, label=label, status="completed", detail=details[step_id])
        for step_id, label in STEP_TEMPLATE
    ]


# Keep result summary deterministic and short.
def _build_summary(query: str, recommendations_count: int) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Generated {recommendations_count} JSON-backed recommendations for "
        f"'{query}' at {timestamp}."
    )
