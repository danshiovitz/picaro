import http from "node:http";

import {
  ActiveEncounter,
  ApiState,
  Condition,
  HexEntity,
  Item,
  PendingActivity,
  PlayerEntity,
  Selection,
  TableauCard,
  FunctionParamType,
  FunctionType,
} from "./types.js";
import { createEntity } from "./entity.js";
import {
  entityStore,
  makeEmptyResources,
  makeEmptySkills,
  encounterTemplates,
  setApiState,
} from "./data.js";
import { loadOrGenerateWorld, MapGeneratorName } from "./map_generator.js";
import { getRng } from "@common/random.js";
import {
  RulesViolation,
  addPlayer,
  campEntity,
  fillTableau,
  continueEncounter,
  finishEncounter,
  ackNotification,
  getClaims,
  getEntity,
  getGame,
  getHexes,
  getRegions,
  getSpecialActions,
  getTableau,
  getTerrain,
  getItem,
  initSystemFunctions,
  performSpecialAction,
  runEncounter,
  scoutEntity,
  travelEntity,
  viewNextActivityForClient,
} from "./commands.js";
import { makeSelection } from "./selection.js";

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
const regions = world.regions;
for (const entity of world.entities) entityStore.add(entity);

function startingInventory(): Item[] {
  const createItem = (
    name: string,
    extra: {
      name?: string;
      speed_boost?: number;
      is_artifact?: boolean;
      use_function?: string;
    },
  ) => {
    let fields = extra;
    fields.name = name;
    const item = createEntity<Item>("item", fields);
    entityStore.add(item);
    return item;
  };
  return [
    createItem("Excalibur", { is_artifact: true }),
    createItem("shield", { speed_boost: -1 }),
    createItem("can of coke", {
      speed_boost: 2,
      use_function: "coke-use-execute",
    }),
  ];
}

function startingConditions() {
  return [
    createEntity<Condition>("condition", {
      name: "Flatulent",
      duration: 5,
      speed_boost: 1,
    }),
  ];
}

function startingResources() {
  const resources = makeEmptyResources();
  resources.Silk = 1;
  resources.Steel = 1;
  resources.Jewels = 1;
  return resources;
}

function startingSkills() {
  const skill_xp = makeEmptySkills();
  const skillKeys = Object.keys(skill_xp) as Array<string>;
  for (let i = 0; i < 30; i++) {
    const randomIndex = Math.floor(Math.random() * skillKeys.length);
    skill_xp[skillKeys[randomIndex]] += 20;
  }
  return skill_xp;
}

function addPlayers() {
  const rng = getRng();
  const used = new Set<number>();
  const getUnused = (index: number | undefined) => {
    let idx = index ?? rng.int(hexes.length);
    while (used.has(idx)) idx = rng.int(hexes.length);
    used.add(idx);
    return hexes[idx].name;
  };

  const playerVals = [1, 2, 3, 4].map((i) => ({
    name: `Player ${i}`,
    icon: `player${i}`,
    location: getUnused(i == 1 ? 42 : undefined),
  }));

  for (const pv of playerVals) {
    addPlayer(pv.location, {
      name: pv.name,
      icon: pv.icon,
      curHealth: 10,
      maxHealth: 10,
      curLuck: 3,
      maxLuck: 3,
      speed: 3,
      gold: 0,
      reputation: 10,
      turns: 20,
      resources: startingResources(),
      inventory: startingInventory(),
      conditions: startingConditions(),
      skill_xp: startingSkills(),
    });
  }
}

setApiState(hexes, regions, entityStore);
initSystemFunctions();
addPlayers();

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
      return sendJson(res, 200, getHexes());
    if (req.method === "GET" && path === "/api/terrain")
      return sendJson(res, 200, getTerrain());
    if (req.method === "GET" && path === "/api/regions")
      return sendJson(res, 200, getRegions());
    if (req.method === "GET" && path === "/api/claims")
      return sendJson(res, 200, getClaims());
    if (req.method === "GET" && path === "/api/tableau") {
      const playerId = url.searchParams.get("player");
      if (!playerId) return sendJson(res, 400, { error: "Player id required" });
      const player = entityStore.getById<PlayerEntity>(playerId);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      return sendJson(res, 200, getTableau(player));
    }
    if (req.method === "GET" && path === "/api/game")
      return sendJson(res, 200, getGame());

    const itemMatch = path.match(/^\/api\/items\/([^/]+)$/);
    if (itemMatch && req.method === "GET") {
      const item = getItem(itemMatch[1]);
      if (!item) return sendJson(res, 404, { error: "Item not found" });
      return sendJson(res, 200, item);
    }

    const specialActionsMatch = path.match(
      /^\/api\/entities\/([^/]+)\/special_actions$/,
    );
    if (specialActionsMatch) {
      const playerId = url.searchParams.get("player") ?? specialActionsMatch[1];
      const player = entityStore.getById<PlayerEntity>(playerId);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      if (req.method === "GET")
        return sendJson(res, 200, getSpecialActions(player));
    }

    const entityMatch = path.match(
      /^\/api\/entities\/([^/]+)(?:\/actions\/(camp|travel|scout|run_encounter|continue_encounter|finish_encounter|special_action|make_selection|ack_notification))?$/,
    );
    if (entityMatch) {
      const playerId = url.searchParams.get("player") ?? entityMatch[1];
      const player = entityStore.getById<PlayerEntity>(playerId);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      const action = entityMatch[2];

      if (req.method === "GET" && !action)
        return sendJson(res, 200, getEntity(player));

      if (req.method === "POST" && action === "camp") campEntity(player);
      else if (req.method === "POST" && action === "travel") {
        const body = await readJson(req);
        const request = { route: Array.isArray(body?.route) ? body.route : [] };
        travelEntity(player, request);
      } else if (req.method === "POST" && action === "scout")
        scoutEntity(player);
      else if (req.method === "POST" && action === "run_encounter") {
        const body = await readJson(req);
        const request = {
          encounterId: String(body?.encounterId ?? ""),
          tableauId:
            typeof body?.tableauId === "string" ? body.tableauId : undefined,
        };
        runEncounter(player, request);
      } else if (req.method === "POST" && action === "continue_encounter") {
        const body = await readJson(req);
        const request = {
          encounterId: String(body?.encounterId ?? ""),
          tableauId:
            typeof body?.tableauId === "string" ? body.tableauId : undefined,
        };
        continueEncounter(player, request);
      } else if (req.method === "POST" && action === "finish_encounter") {
        const body = await readJson(req);
        const request = {
          encounterId: String(body?.encounterId ?? ""),
          tableauId:
            typeof body?.tableauId === "string" ? body.tableauId : undefined,
          conceding: Boolean(body?.conceding),
        };
        finishEncounter(player, request);
      } else if (req.method === "POST" && action === "special_action") {
        const body = await readJson(req);
        const request = {
          specialActionId: String(body?.specialActionId ?? ""),
          entityId: body?.entityId ? String(body?.entityId!) : undefined,
        };
        performSpecialAction(player, request);
      } else if (req.method === "POST" && action === "make_selection") {
        const body = await readJson(req);
        const request = {
          selectionId: String(body?.selectionId ?? ""),
          selectedIndexes: Array.isArray(body?.selectedIndexes)
            ? body.selectedIndexes.map((value: unknown) => Number(value))
            : [],
        };
        makeSelection(player, request);
      } else if (req.method === "POST" && action === "ack_notification") {
        const body = await readJson(req);
        ackNotification(player, String(body?.notificationId ?? ""));
      }

      return sendJson(res, 200, viewNextActivityForClient(player) ?? null);
    }

    sendJson(res, 404, { error: "Not found" });
  } catch (error) {
    if (error instanceof RulesViolation) {
      return sendJson(res, 400, {
        errorType: "rule violation",
        message: error.message,
      });
    }
    console.error(
      error instanceof Error ? (error.stack ?? error.message) : error,
    );
    sendJson(res, 500, { error: "Internal server error" });
  }
});
const port = Number(process.env.PORT) || 3001;
server.listen(port, () => console.log(`Picaro server on ${port}`));
