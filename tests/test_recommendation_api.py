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


def test_chat_message_returns_workflow_result() -> None:
    # Send the same request shape the frontend uses.
    response = client.post(
        "/chat/message",
        json={
            "input_text": "Recommend a secure lightweight laptop with long battery",
            "account_id": "acct-northstar-health",
            "opportunity_id": "opp-clinician-refresh",
        },
    )

    # Fetch the workflow result using the returned id.
    payload = response.json()
    result_response = client.get(
        "/workflow/result",
        params={"workflow_id": payload["workflow_id"]},
    )

    # Verify the chat and workflow contracts are connected.
    assert response.status_code == 200
    assert payload["intent"] == "search_auto"
    assert result_response.status_code == 200
    assert len(result_response.json()["result"]["recommendations"]) == 3
