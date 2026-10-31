import http from "node:http";

import {
  ActiveEncounter,
  Item,
  PlayerEntity,
  Selection,
  TableauCard,
} from "./types.js";
import {
  makeConditionId,
  makeEmptyResources,
  makeEmptySkills,
  makeItemId,
  makeTokenId,
  encounterTemplates,
} from "./data.js";
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
  getItem,
  performSpecialAction,
  runEncounter,
  travelEntity,
} from "./commands.js";
import { makeSelection } from "./selection.js";
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

const items = new Map<string, Item>();
const players = new Map<string, PlayerEntity>();
function createItem(name: string): Item {
  const item = { id: makeItemId(), name };
  items.set(item.id, item);
  return item;
}
function startingInventory(): Item[] {
  return ["sword", "shield", "can of coke"].map(createItem);
}

function startingConditions() {
  return [{ id: makeConditionId(), name: "Flatulent", duration: 5 }];
}

function startingResources() {
  const resources = makeEmptyResources();
  resources.Silk = 1;
  resources.Steel = 1;
  resources.Jewels = 1;
  return resources;
}

function startingSkills() {
  const skills = makeEmptySkills();
  const skillKeys = Object.keys(skills) as Array<string>;
  for (let i = 0; i < 30; i++) {
    const randomIndex = Math.floor(Math.random() * skillKeys.length);
    skills[skillKeys[randomIndex]]++;
  }
  return skills;
}

for (const [index, token] of playerTokens.entries()) {
  players.set(token.id, {
    id: token.id,
    name: token.entityName,
    tokenId: token.id,
    curHealth: 10,
    maxHealth: 10,
    curLuck: 3,
    maxLuck: 3,
    speed: 3,
    gold: 0,
    reputation: 10,
    turns: 20,
    location: locationForToken(token.id),
    resources: startingResources(),
    inventory: startingInventory(),
    conditions: startingConditions(),
    skills: startingSkills(),
  });
}
const activeEncounters = new Map<string, ActiveEncounter>();
const activeSelections = new Map<string, Selection>();
const travelContinuation = new Map<string, boolean>();
const travelContinuationRoute = new Map<string, string[]>();
const tableau = new Map<string, TableauCard[]>();
const encounterRng = new RNG(`${defaultSeed}:encounters`);
setEncounterContext({ hexes, rng: encounterRng });
for (const player of players.values()) {
  const playerTableau: TableauCard[] = [];
  fillTableau(playerTableau, encounterTemplates, player, encounterRng);
  tableau.set(player.id, playerTableau);
}

const apiState: ApiState = {
  hexes,
  hexByName,
  tokens: playerTokens,
  items,
  players,
  activeEncounters,
  activeSelections,
  travelContinuation,
  travelContinuationRoute,
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
    if (req.method === "GET" && path === "/api/tableau") {
      const playerId = url.searchParams.get("player");
      if (!playerId) return sendJson(res, 400, { error: "Player id required" });
      const player = players.get(playerId);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      return sendJson(res, 200, getTableau(apiState, player));
    }
    if (req.method === "GET" && path === "/api/game")
      return sendJson(res, 200, getGame(apiState));
    if (req.method === "GET" && path === "/api/special_actions")
      return sendJson(res, 200, getSpecialActionCatalog());

    const itemMatch = path.match(/^\/api\/items\/([^/]+)$/);
    if (itemMatch && req.method === "GET") {
      const item = getItem(apiState, itemMatch[1]);
      if (!item) return sendJson(res, 404, { error: "Item not found" });
      return sendJson(res, 200, item);
    }

    const specialActionsMatch = path.match(
      /^\/api\/entities\/([^/]+)\/special_actions$/,
    );
    if (specialActionsMatch) {
      const playerId = url.searchParams.get("player") ?? specialActionsMatch[1];
      const player = players.get(playerId);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      if (req.method === "GET")
        return sendJson(res, 200, getSpecialActions(apiState, player));
    }

    const entityMatch = path.match(
      /^\/api\/entities\/([^/]+)(?:\/actions\/(camp|travel|run_encounter|continue_encounter|finish_encounter|special_action|make_selection))?$/,
    );
    if (entityMatch) {
      const playerId = url.searchParams.get("player") ?? entityMatch[1];
      const player = players.get(playerId);
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

      if (req.method === "POST" && action === "make_selection") {
        const body = await readJson(req);
        const request = {
          selectionId: String(body?.selectionId ?? ""),
          selectedIndexes: Array.isArray(body?.selectedIndexes)
            ? body.selectedIndexes.map((value: unknown) => Number(value))
            : [],
        };
        return sendJson(res, 200, makeSelection(apiState, player, request));
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
