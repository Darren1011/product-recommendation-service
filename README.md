# Product Recommendation

Personal monorepo for the JSON-backed product recommendation prototype.

## Demo

<video src="docs/demo/product-recommendation-demo.mp4" controls width="100%"></video>

[Open the MP4 demo](docs/demo/product-recommendation-demo.mp4)

## Structure

- `services/` - FastAPI and LangGraph backend using local JSON files
- `web/` - Next.js recommendation workspace UI

## Constraints

- No company data
- No OpenAI API requirement
- No Databricks dependency
- No real database
- JSON files as the data source

## Run Locally

Install backend dependencies:

```powershell
npm run install:services
```

Install web dependencies:

```powershell
npm run install:web
```

Start the backend:

```powershell
npm run dev:services
```

Start the web app in another terminal:

```powershell
npm run dev:web
```

Open `http://127.0.0.1:3000`. The web app calls the backend on port `8123`.
