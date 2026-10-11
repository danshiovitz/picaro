# Picaro Implementation Plan

1. Create a TypeScript monorepo-style project under `/workspace` with:
   - `server/` Node + Express backend in TypeScript.
   - `client/` Vite web client in TypeScript.
   - shared API type definitions where practical.

2. Backend:
   - Define models for hexes, terrain, regions, claims, and tokens.
   - Generate startup data for a roughly 20x20 axial-backed hex grid.
   - Assign cartesian display names (`A1`, `A2`, etc.), terrain, regions, 0-3 claims, and scattered tokens.
   - Ensure one hex contains both a city token and a player token.
   - Expose REST endpoints to fetch hexes and reference objects.

3. Client data layer:
   - Fetch backend game data on startup.
   - Store hexes, terrain, regions, claims, and tokens in indexed maps.
   - Provide helpers for axial distance, token lookup, hex token lookup, and full enriched hex data.

4. Client UI:
   - Build a main layout with a central hex map, right panel, and bottom panel containing placeholder text.
   - Render a scrollable/zoomable SVG hex map.
   - Draw terrain-colored hexes with tiled terrain icon patterns.
   - Display hex names, token icons, and claim icons with visibility adjusted by zoom level.
   - Add mouse wheel zoom plus +/- controls.

5. Interaction:
   - Add click and delayed hover tooltip for hexes.
   - Tooltip shows name, terrain, region, claims, tokens, and a dummy `Move here` action.
   - Support close button and outside-click dismissal.

6. Assets:
   - Generate simple placeholder image assets for terrain, claims, and tokens under the client public folder.

7. Developer scripts and documentation:
   - Add package scripts for installing, developing, building, and running both client and server.
   - Include a README with usage instructions.
