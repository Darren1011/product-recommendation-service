from fastapi.testclient import TestClient

from app.main import app
from app.services.data_store import CatalogStore
from app.services.recommender import RecommendationEngine


# Create shared fixtures from the local JSON catalog.
client = TestClient(app)
catalog_store = CatalogStore()


def test_recommender_prioritizes_workstation_request() -> None:
    # Score a workstation-heavy request without external model calls.
    engine = RecommendationEngine()
    results = engine.recommend(
        query="Need a workstation for CAD rendering with 64GB memory",
        products=catalog_store.products,
        account=catalog_store.find_account("acct-vertex-design"),
        opportunity=catalog_store.find_opportunity("opp-render-farm-edge"),
    )

    # Verify the top result is from the synthetic workstation family.
    assert results
    assert "ForgeStation" in results[0].product.family
    assert "graphics" in results[0].matched_requirements


def test_chat_message_starts_workflow_status() -> None:
    # Send the same request shape the frontend uses.
    response = client.post(
        "/chat/message",
        json={
            "input_text": "Recommend a secure lightweight laptop with long battery",
            "account_id": "acct-northstar-health",
            "opportunity_id": "opp-clinician-refresh",
        },
    )

    # Fetch the workflow status using the returned id.
    payload = response.json()
    status_response = client.get(
        "/workflow/status",
        params={"workflow_id": payload["workflow_id"]},
    )

    # Verify the chat endpoint starts an observable workflow.
    assert response.status_code == 200
    assert payload["intent"] == "search_auto"
    assert status_response.status_code == 200
    assert len(status_response.json()["steps"]) == 4


def test_context_only_request_can_recommend() -> None:
    # Verify empty input is accepted by the API contract.
    response = client.post(
        "/chat/message",
        json={
            "input_text": "",
            "account_id": "acct-northstar-health",
            "opportunity_id": "opp-clinician-refresh",
        },
    )

    # Confirm a workflow is still started from account and opportunity context.
    payload = response.json()
    assert response.status_code == 200
    assert payload["workflow_id"]
    assert "selected context" in payload["content"]
