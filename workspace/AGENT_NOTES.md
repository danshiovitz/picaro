# Project notes for future edits

## Repo structure

- `common/src/` holds shared types, schemas, and utilities used by both client and server.
- `server/src/` contains game logic, API command handlers, data definitions, rules, and entity/state helpers.
- `client/src/` contains UI rendering, store/view helpers, and browser interaction logic.
- `client/dist/` is build output; generally do not edit directly.

## Important conventions

- Shared runtime values that must exist in the browser must be imported as value imports, not `import type`.
- Shared TS types often live in `common/src/types.ts`; server/client `src/types.ts` files usually re-export or alias them.
- Use `server/src/entity.ts` helpers (`getField`, `setField`, `hydrateEntity`, `serializeEntity`) instead of direct property manipulation when possible.
- Prefer `read` for inspecting files and `edit` for targeted changes.

## Build/test commands

- Server build: `npm --workspace server run build`
- Client build: `npm --workspace client run build`
- Root build: `npm run build`

## Special actions architecture

- `common/src/types.ts` defines the shared special action shapes and enums.
- Server special action definitions live in `server/src/data.ts`.
- Server action execution/availability logic is implemented in `server/src/commands.ts` and registered through `server/src/data.ts` function registry.
- Client loads `/api/special_actions` for catalog data and `/api/entities/:id/special_actions` for available actions.

## Special action implementation details

- Special actions can be:
  - `General`
  - `Item`
  - `NearbyEntity`
- Available actions may repeat the same special action with different `entityId` values.
- For `Item` and `NearbyEntity` actions, availability and execute functions take the player plus the target item/entity.
- If a client request omits `entityId`, server-side logic may need to infer the target from the player state.

## Client UI patterns

- `client/src/main.ts` is a large single-file renderer/interaction controller.
- The character panel contains summary + action sections; special actions are rendered there and may also appear in hex hover popups.
- Inventory actions should render inline after item names.
- Nearby-entity actions should be grouped by entity and rendered in hover popups similarly to general hex-based actions.
- When wiring click handlers, check for event delegation and existing handlers before adding new ones.
- Hex/token state should be treated as a single source of truth in the client store. Avoid keeping separate raw and hydrated copies of hexes in sync.

## Pitfalls observed

- Importing enums/values with `import type` causes runtime `ReferenceError` in the browser.
- The client `renderInventory()` and hover popup logic are easy places to accidentally use stale action shapes.
- If a server action is missing an expected target id, it may still need fallback lookup by current player inventory or location.
- Some action labels were previously rendered with square brackets; avoid reintroducing that formatting.
- If player movement appears not to update visually, check whether rendering reads from a different hex copy than the one being mutated.
