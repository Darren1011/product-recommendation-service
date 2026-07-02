from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    Account,
    ChatRequest,
    ChatResponse,
    ChatThreadDetail,
    ChatThreadSummary,
    FavoriteThreadRequest,
    HealthResponse,
    Opportunity,
    Product,
    RenameThreadRequest,
    WorkflowResult,
    WorkflowResultEnvelope,
    WorkflowStatus,
)
from app.services.chat_service import ChatService
from app.services.data_store import CatalogStore
from app.services.recommender import RecommendationEngine
from app.services.workflow_service import WorkflowService


# Initialize local services over JSON files and in-memory state.
catalog_store = CatalogStore()
chat_service = ChatService()
workflow_service = WorkflowService(RecommendationEngine())

# Create the FastAPI app with a neutral personal-project identity.
app = FastAPI(
    title="Product Recommendation Service",
    version="0.1.0",
    description="JSON-backed enterprise product recommendation prototype.",
)

# Allow local frontend development without any platform proxy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Return service health."""
    # Report the explicit local data source to make constraints visible.
    return HealthResponse(status="ok", data_source="local JSON files")


@app.get("/api/products", response_model=list[Product])
def list_products() -> list[Product]:
    """Return the synthetic product catalog."""
    # Expose catalog rows for frontend filters and debugging.
    return catalog_store.products


@app.get("/api/recommendation-context/accounts", response_model=list[Account])
@app.get("/a2a/recommendation-context/accounts", response_model=list[Account])
def list_accounts(q: str | None = Query(default=None)) -> list[Account]:
    """Return selectable account context."""
    # Filter accounts locally for selector search.
    return catalog_store.list_accounts(q)


@app.get("/api/recommendation-context/opportunities", response_model=list[Opportunity])
@app.get("/a2a/recommendation-context/opportunities", response_model=list[Opportunity])
def list_opportunities(account_id: str | None = Query(default=None)) -> list[Opportunity]:
    """Return selectable opportunities."""
    # Scope opportunities to the selected account when provided.
    return catalog_store.list_opportunities(account_id)


@app.post("/chat/message", response_model=ChatResponse)
def send_chat_message(request: ChatRequest) -> ChatResponse:
    """Run a recommendation workflow and store the chat exchange."""
    # Resolve optional account and opportunity context before scoring.
    account = _resolve_account(request.account_id)
    opportunity = _resolve_opportunity(request.opportunity_id, account)

    # Run the deterministic JSON-backed workflow synchronously.
    workflow_result = workflow_service.run(
        query=request.input_text,
        products=catalog_store.products,
        account=account,
        opportunity=opportunity,
    )

    # Store a chat exchange that references the completed workflow.
    assistant_text = _build_assistant_text(workflow_result)
    chat_id, message_id, chat_name = chat_service.add_exchange(
        request.chat_id,
        request.input_text,
        assistant_text,
        workflow_result.workflow_id,
    )

    # Return the compact response expected by the frontend chat surface.
    return ChatResponse(
        chat_id=chat_id,
        message_id=message_id,
        content=assistant_text,
        intent="search_auto",
        chat_name=chat_name,
        workflow_id=workflow_result.workflow_id,
    )


@app.get("/workflow/status", response_model=WorkflowStatus)
def get_workflow_status(workflow_id: str) -> WorkflowStatus:
    """Return the current workflow status."""
    # Fail clearly when the frontend asks for an unknown workflow id.
    status = workflow_service.get_status(workflow_id)
    if status is None:
        raise HTTPException(status_code=404, detail="workflow_id not found")
    return status


@app.get("/workflow/thinking", response_model=WorkflowStatus)
def get_workflow_thinking(workflow_id: str) -> WorkflowStatus:
    """Return workflow steps for the status panel."""
    # Reuse status because every prototype step is already receipt-ready.
    return get_workflow_status(workflow_id)


@app.get("/workflow/result", response_model=WorkflowResultEnvelope)
def get_workflow_result(workflow_id: str) -> WorkflowResultEnvelope:
    """Return the completed workflow result."""
    # Return 404 until a known workflow has a completed result.
    result = workflow_service.get_result(workflow_id)
    if result is None:
        raise HTTPException(status_code=404, detail="workflow result not found")
    return WorkflowResultEnvelope(workflow_id=workflow_id, result=result)


@app.get("/api/chat-history/list", response_model=list[ChatThreadSummary])
def list_chat_history() -> list[ChatThreadSummary]:
    """Return chat thread summaries."""
    # The prototype history is in-memory and resets when the server restarts.
    return chat_service.list_threads()


@app.get("/api/chat-history/{chat_id}", response_model=ChatThreadDetail)
def get_chat_history(chat_id: str) -> ChatThreadDetail:
    """Return one chat thread."""
    # Keep missing thread handling explicit for the frontend.
    thread = chat_service.get_thread(chat_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="chat_id not found")
    return thread


@app.put("/api/chat-history/{chat_id}/rename", response_model=ChatThreadDetail)
def rename_chat_history(
    chat_id: str,
    request: RenameThreadRequest,
) -> ChatThreadDetail:
    """Rename one chat thread."""
    # Apply a metadata-only change to the in-memory thread.
    thread = chat_service.rename_thread(chat_id, request.name)
    if thread is None:
        raise HTTPException(status_code=404, detail="chat_id not found")
    return thread


@app.put("/api/chat-history/{chat_id}/favorite", response_model=ChatThreadDetail)
def favorite_chat_history(
    chat_id: str,
    request: FavoriteThreadRequest,
) -> ChatThreadDetail:
    """Favorite or unfavorite one chat thread."""
    # Apply a metadata-only change to the in-memory thread.
    thread = chat_service.set_favorite(chat_id, request.is_favorite)
    if thread is None:
        raise HTTPException(status_code=404, detail="chat_id not found")
    return thread


# Resolve account context and reject invalid ids early.
def _resolve_account(account_id: str | None) -> Account | None:
    account = catalog_store.find_account(account_id)
    if account_id and account is None:
        raise HTTPException(status_code=404, detail="account_id not found")
    return account


# Resolve opportunity context and keep it aligned to the selected account.
def _resolve_opportunity(
    opportunity_id: str | None,
    account: Account | None,
) -> Opportunity | None:
    opportunity = catalog_store.find_opportunity(opportunity_id)
    if opportunity_id and opportunity is None:
        raise HTTPException(status_code=404, detail="opportunity_id not found")
    if opportunity and account and opportunity.account_id != account.id:
        raise HTTPException(status_code=400, detail="opportunity does not belong to account")
    return opportunity


# Create a conversational assistant message from the completed result.
def _build_assistant_text(result: WorkflowResult) -> str:
    count = len(result.recommendations)
    top_name = result.recommendations[0].product.name if result.recommendations else "no product"
    return (
        f"I found {count} recommendation options. "
        f"The strongest match is {top_name}. "
        f"Open the recommendation panel for scoring details."
    )
