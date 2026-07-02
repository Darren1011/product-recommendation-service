import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.models import Account, Opportunity, Product


ModelType = TypeVar("ModelType", bound=BaseModel)
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# Load a JSON array and validate each record with the supplied model.
def _load_records(path: Path, model_class: type[ModelType]) -> list[ModelType]:
    with path.open("r", encoding="utf-8") as file:
        raw_records = json.load(file)
    return [model_class.model_validate(record) for record in raw_records]


# Keep all sample data access behind one small service.
class CatalogStore:
    """Read-only repository over local JSON files."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        """Load JSON files once when the app starts."""
        # Load each dataset from the local data directory.
        self.accounts = _load_records(data_dir / "accounts.json", Account)
        self.opportunities = _load_records(data_dir / "opportunities.json", Opportunity)
        self.products = _load_records(data_dir / "products.json", Product)

    def list_accounts(self, search_text: str | None = None) -> list[Account]:
        """Return accounts, optionally filtered by name, industry, or country."""
        # Return all accounts when the UI has not entered search text.
        if not search_text:
            return self.accounts

        # Match the most visible account fields for selector filtering.
        normalized_query = search_text.lower()
        return [
            account
            for account in self.accounts
            if normalized_query in _account_search_text(account)
        ]

    def list_opportunities(self, account_id: str | None = None) -> list[Opportunity]:
        """Return opportunities, optionally scoped to one account."""
        # Preserve the release app pattern where opportunity depends on account.
        if not account_id:
            return self.opportunities
        return [
            opportunity
            for opportunity in self.opportunities
            if opportunity.account_id == account_id
        ]

    def find_account(self, account_id: str | None) -> Account | None:
        """Find one account by id."""
        # Skip lookup when the request has no account context.
        if not account_id:
            return None
        return next((account for account in self.accounts if account.id == account_id), None)

    def find_opportunity(self, opportunity_id: str | None) -> Opportunity | None:
        """Find one opportunity by id."""
        # Skip lookup when the request has no opportunity context.
        if not opportunity_id:
            return None
        return next(
            (
                opportunity
                for opportunity in self.opportunities
                if opportunity.id == opportunity_id
            ),
            None,
        )


# Combine account fields used by the account selector search box.
def _account_search_text(account: Account) -> str:
    return " ".join(
        [account.name, account.industry, account.country, account.segment]
    ).lower()
