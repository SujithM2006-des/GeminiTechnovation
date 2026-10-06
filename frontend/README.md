# AthleteGuard Frontend
React + Vite + TypeScript + Tailwind v4 + React Router + TanStack Query + react-hook-form/zod.

    npm install
    npm run dev          # http://localhost:5173  (the backend only accepts this port)
    npm run build        # type-check + production build

Talks to the FastAPI backend at `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`).
Start the backend first: `cd backend` then `uvicorn main:app --reload`.