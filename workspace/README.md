# Picaro

TypeScript web client and Node/Express backend prototype.

## Run

```bash
npm install
npm run dev
```

Backend API: http://localhost:3001. Client: http://localhost:8080.

The client dev server proxies `/api` requests from port 8080 to the backend on port 3001, so only the client port needs to be opened externally. `npm run dev` logs both processes to the terminal with `[dev:server]` and `[dev:client]` prefixes.

## API

- `GET /api/game` returns hexes, terrain, regions, claims, and tokens.
- Individual endpoints: `/api/hexes`, `/api/terrain`, `/api/regions`, `/api/claims`, `/api/tokens`.
