import http from "node:http";

import { PlayerEntity, TableauCard } from "./types.js";
import { makeTokenId, encounterTemplates } from "./data.js";
import { loadOrGenerateWorld, MapGeneratorName } from "./map_generator.js";
import { RNG } from "./random.js";
import {
  ApiState,
  RulesViolation,
  campEntity,
  fillTableau,
  continueEncounter,
  finishEncounter,
  getClaims,
  getEntity,
  getGame,
  getHexes,
  getRegions,
  getSpecialActionCatalog,
  getSpecialActions,
  getTableau,
  getTerrain,
  getTokens,
  performSpecialAction,
  runEncounter,
  travelEntity,
} from "./commands.js";
import { setEncounterContext } from "./encounter.js";

const defaultGenerator: MapGeneratorName =
  process.env["MAP_GENERATOR"] === "allRandom" ||
  process.env["MAP_GENERATOR"] === "empire"
    ? process.env["MAP_GENERATOR"]
    : "empire";
const defaultSeed =
  process.env["MAP_SEED"] ?? Math.random().toString(36).slice(2, 18);
const world = await loadOrGenerateWorld({
  generator: defaultGenerator,
  seed: defaultSeed,
});
const hexes = world.hexes;
const hexByName = world.hexByName;

const playerTokens = [1, 2, 3, 4].map((i) => ({
  id: makeTokenId(),
  entityName: `Player ${i}`,
  icon: `player${i}`,
}));
const playerPlacementRng = new RNG(`${defaultSeed}:players`);

function clearPlayerTokens() {
  for (const hex of hexes)
    hex.tokens = hex.tokens.filter(
      (id) => !playerTokens.some((player) => player.id === id),
    );
}

function placePlayersAfterLoad() {
  clearPlayerTokens();
  const used = new Set<number>();
  const place = (tokenId: string, index: number | undefined) => {
    let idx = index ?? playerPlacementRng.int(hexes.length);
    while (used.has(idx)) idx = playerPlacementRng.int(hexes.length);
    used.add(idx);
    hexes[idx].tokens.push(tokenId);
  };
  place(playerTokens[0].id, 42);
  for (const token of playerTokens.slice(1)) place(token.id, undefined);
}
placePlayersAfterLoad();

function locationForToken(tokenId: string) {
  return hexes.find((hex) => hex.tokens.includes(tokenId))?.name ?? "Unknown";
}

const players = new Map<string, PlayerEntity>();
for (const token of playerTokens) {
  players.set(token.entityName, {
    name: token.entityName,
    tokenId: token.id,
    curHealth: 6 + Number(token.id.split("-")[1]) - 1,
    maxHealth: 10,
    curLuck: 1,
    maxLuck: 3,
    speed: 3,
    gold: 0,
    reputation: 10,
    turns: 20,
    location: locationForToken(token.id),
  });
}
const activeEncounters = new Map<
  string,
  import("./types.js").ActiveEncounter
>();
const tableau: TableauCard[] = [];
const encounterRng = new RNG(`${defaultSeed}:encounters`);
setEncounterContext({ hexes, rng: encounterRng });
const firstPlayer = players.values().next().value as PlayerEntity | undefined;
if (firstPlayer)
  fillTableau(tableau, encounterTemplates, firstPlayer, encounterRng);

const apiState: ApiState = {
  hexes,
  hexByName,
  tokens: playerTokens,
  players,
  activeEncounters,
  tableau,
  rng: encounterRng,
};

function sendJson(res: http.ServerResponse, status: number, data: unknown) {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body),
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  });
  res.end(body);
}

async function readJson(req: http.IncomingMessage): Promise<any> {
  let body = "";
  for await (const chunk of req) body += chunk;
  if (!body) return undefined;
  return JSON.parse(body);
}

const server = http.createServer(async (req, res) => {
  try {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    const url = new URL(
      req.url ?? "/",
      `http://${req.headers.host ?? "localhost"}`,
    );
    const path = decodeURIComponent(url.pathname);

    if (req.method === "GET" && path === "/api/hexes")
      return sendJson(res, 200, getHexes(apiState));
    if (req.method === "GET" && path === "/api/terrain")
      return sendJson(res, 200, getTerrain());
    if (req.method === "GET" && path === "/api/regions")
      return sendJson(res, 200, getRegions());
    if (req.method === "GET" && path === "/api/claims")
      return sendJson(res, 200, getClaims());
    if (req.method === "GET" && path === "/api/tokens")
      return sendJson(res, 200, getTokens(apiState));
    if (req.method === "GET" && path === "/api/tableau")
      return sendJson(res, 200, getTableau(apiState));
    if (req.method === "GET" && path === "/api/game")
      return sendJson(res, 200, getGame(apiState));
    if (req.method === "GET" && path === "/api/special_actions")
      return sendJson(res, 200, getSpecialActionCatalog());

    const specialActionsMatch = path.match(
      /^\/api\/entities\/([^/]+)\/special_actions$/,
    );
    if (specialActionsMatch) {
      const player = players.get(specialActionsMatch[1]);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      if (req.method === "GET")
        return sendJson(res, 200, getSpecialActions(apiState, player));
    }

    const entityMatch = path.match(
      /^\/api\/entities\/([^/]+)(?:\/actions\/(camp|travel|run_encounter|continue_encounter|finish_encounter|special_action))?$/,
    );
    if (entityMatch) {
      const player = players.get(entityMatch[1]);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      const action = entityMatch[2];

      if (req.method === "GET" && !action)
        return sendJson(res, 200, getEntity(apiState, player));

      if (req.method === "POST" && action === "camp")
        return sendJson(res, 200, campEntity(apiState, player));

      if (req.method === "POST" && action === "travel") {
        const body = await readJson(req);
        const request = { route: Array.isArray(body?.route) ? body.route : [] };
        return sendJson(res, 200, travelEntity(apiState, player, request));
      }

      if (req.method === "POST" && action === "run_encounter") {
        const body = await readJson(req);
        const request = {
          encounterId: String(body?.encounterId ?? ""),
          tableauId:
            typeof body?.tableauId === "string" ? body.tableauId : undefined,
        };
        return sendJson(res, 200, runEncounter(apiState, player, request));
      }

      if (req.method === "POST" && action === "continue_encounter") {
        const body = await readJson(req);
        const request = {
          encounterId: String(body?.encounterId ?? ""),
          tableauId:
            typeof body?.tableauId === "string" ? body.tableauId : undefined,
        };
        return sendJson(res, 200, continueEncounter(apiState, player, request));
      }

      if (req.method === "POST" && action === "finish_encounter") {
        const body = await readJson(req);
        const request = {
          encounterId: String(body?.encounterId ?? ""),
          tableauId:
            typeof body?.tableauId === "string" ? body.tableauId : undefined,
          conceding: Boolean(body?.conceding),
        };
        return sendJson(res, 200, finishEncounter(apiState, player, request));
      }

      if (req.method === "POST" && action === "special_action") {
        const body = await readJson(req);
        const request = {
          specialActionId: String(body?.specialActionId ?? ""),
        };
        return sendJson(
          res,
          200,
          performSpecialAction(apiState, player, request),
        );
      }
    }

    sendJson(res, 404, { error: "Not found" });
  } catch (error) {
    if (error instanceof RulesViolation) {
      return sendJson(res, 400, {
        errorType: "rule violation",
        message: error.message,
      });
    }
    console.error(error);
    sendJson(res, 500, { error: "Internal server error" });
  }
});
const port = Number(process.env.PORT) || 3001;
server.listen(port, () => console.log(`Picaro server on ${port}`));
