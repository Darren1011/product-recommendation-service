# Product Recommendation Web

Personal Next.js prototype for an enterprise-style product recommendation UI.

This repo is intentionally standalone and will connect to the JSON-backed service prototype.

## Run Locally

Start the backend service on port `8123`, then run:

```powershell
npm install
npm run dev
```

The web app opens at `http://localhost:3000` and reads `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8123`.
