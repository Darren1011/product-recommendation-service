# Product Recommendation Service

Personal FastAPI and LangGraph prototype for enterprise-style product recommendations.

This repo is intentionally standalone:

- No company data
- No OpenAI API requirement
- No Databricks dependency
- No real database
- JSON files as the data source

## Run Locally

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8123 --reload
```

The API exposes `/chat/message`, `/workflow/status`, `/workflow/result`, and recommendation context endpoints over local JSON files.
