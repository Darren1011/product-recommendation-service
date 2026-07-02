from pydantic import BaseModel, Field


# Define account context supplied by the sample JSON data.
class Account(BaseModel):
    """Customer account context used to tailor recommendations."""

    id: str
    name: str
    industry: str
    country: str
    segment: str
    employee_count: int


# Define opportunity context supplied by the sample JSON data.
class Opportunity(BaseModel):
    """Sales opportunity context that adds priority requirements."""

    id: str
    account_id: str
    name: str
    stage: str
    summary: str
    priority_requirements: list[str]


# Capture normalized product hardware attributes for scoring and display.
class ProductSpecs(BaseModel):
    """Structured hardware attributes for a catalog product."""

    processor: str
    memory_gb: int
    storage_gb: int
    gpu: str
    display: str
    battery_hours: int
    weight_kg: float
    os: str


# Capture inventory as local sample data, not an external service result.
class ProductInventory(BaseModel):
    """Synthetic stock signal loaded from JSON."""

    status: str
    countries: list[str]
    quantity: int


# Define the recommendation catalog item.
class Product(BaseModel):
    """Product catalog record loaded from a JSON file."""

    id: str
    name: str
    category: str
    family: str
    form_factor: str
    summary: str
    personas: list[str]
    use_cases: list[str]
    tags: list[str]
    price_usd: int
    image_url: str
    specs: ProductSpecs
    inventory: ProductInventory


# Define the incoming chat contract used by the web app.
class ChatRequest(BaseModel):
    """User message and optional context for a recommendation request."""

    input_text: str = Field(..., min_length=1, max_length=2000)
    chat_id: str | None = None
    account_id: str | None = None
    opportunity_id: str | None = None


# Describe one visible workflow step in the prototype.
class WorkflowStep(BaseModel):
    """Status row for the enterprise-style workflow timeline."""

    id: str
    label: str
    status: str
    detail: str


# Describe a ranked product option returned to the frontend.
class RecommendationOption(BaseModel):
    """Ranked product recommendation with explanation metadata."""

    product: Product
    score: float
    badge: str
    matched_requirements: list[str]
    reasoning: str


# Package the completed workflow result.
class WorkflowResult(BaseModel):
    """Recommendation workflow payload returned by result endpoints."""

    workflow_id: str
    query: str
    account: Account | None
    opportunity: Opportunity | None
    steps: list[WorkflowStep]
    recommendations: list[RecommendationOption]
    summary: str


# Keep chat messages small and serializable for in-memory history.
class ChatMessage(BaseModel):
    """Single chat message stored in the prototype history."""

    id: str
    role: str
    content: str
    created_at: str
    workflow_id: str | None = None


# Return shape for the main chat endpoint.
class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    chat_id: str
    message_id: str
    content: str
    intent: str
    chat_name: str
    workflow_id: str | None = None


# Return shape for thread list views.
class ChatThreadSummary(BaseModel):
    """Collapsed chat history row for the frontend sidebar."""

    id: str
    name: str
    updated_at: str
    is_favorite: bool
    message_count: int
    latest_message: str


# Return shape for a full chat history lookup.
class ChatThreadDetail(BaseModel):
    """Full chat thread payload with messages."""

    id: str
    name: str
    updated_at: str
    is_favorite: bool
    messages: list[ChatMessage]


# Return shape for workflow status polling.
class WorkflowStatus(BaseModel):
    """Current workflow state used by the frontend status panel."""

    workflow_id: str
    status: str
    steps: list[WorkflowStep]
    terminal: bool


# Return shape for a completed workflow result lookup.
class WorkflowResultEnvelope(BaseModel):
    """Wrapper that mirrors the source service workflow result shape."""

    workflow_id: str
    result: WorkflowResult


# Request body for chat history rename.
class RenameThreadRequest(BaseModel):
    """Rename payload for a chat thread."""

    name: str = Field(..., min_length=1, max_length=100)


# Request body for chat history favorite changes.
class FavoriteThreadRequest(BaseModel):
    """Favorite toggle payload for a chat thread."""

    is_favorite: bool


# Simple health response for platform checks.
class HealthResponse(BaseModel):
    """Service health payload."""

    status: str
    data_source: str
