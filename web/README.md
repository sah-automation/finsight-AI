# FinSight AI web app

Server-rendered Next.js application and the Backend-for-Frontend (BFF) for FinSight AI. The browser never talks to the Python API directly and never receives Cognito tokens.

## Commands

```bash
npm ci
npm run dev
npm run typecheck
npm run lint
npm run test
npm run build
npm run api:check
```

## Environment

Copy `.env.example` to `.env.local` and fill in the values. `SESSION_COOKIE_SECURE` should be `false` only for local HTTP development; production fails startup when it is false.

## Security model

- Cognito sign-in runs server-side using USER_SRP_AUTH.
- Access and ID tokens are stored in the server-side session record only.
- The browser receives an opaque session cookie: `HttpOnly`, `Secure`, `SameSite=Lax`.
- Every Python API request flows through `/api/backend/[...path]`, which attaches the access token from the resolved server session.
- Navigation and page access come from `/me` permissions, not role-name checks.

## Session storage

- `SESSION_STORE=memory` is the default and is suitable for local development and tests.
- `SESSION_STORE=dynamodb` uses `SESSION_TABLE_NAME` and the shared DynamoDB session table.

## Dependencies

- `next` and `react`: App Router server components and route handlers.
- `amazon-cognito-identity-js`: official Cognito SRP implementation for embedded sign-in.
- `@aws-sdk/client-dynamodb` and `@aws-sdk/lib-dynamodb`: DynamoDB session store.
- `openapi-fetch` and `openapi-typescript`: typed client and contract drift check against `docs/openapi.json`.
- `tailwindcss`, `@tailwindcss/postcss`, `postcss`: design token driven styling.
- `lucide-react`: outline icons at 1.5px stroke.
- `server-only`: prevents server-only modules from being imported into client components.
- `vitest`, `@testing-library/react`, `jsdom`, `vitest-axe`: component and unit tests.
- Inter fonts are self-hosted; no runtime font network requests are made.
EOF
