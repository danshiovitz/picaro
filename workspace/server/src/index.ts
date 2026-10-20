import http from "node:http";
import { URL } from "node:url";

import {
  Hex,
  PlayerEntity,
  TableauCard,
  ActiveEncounter,
  ActiveEncounterSkillCheck,
} from "./types.js";
import {
  terrainSpecs,
  regions,
  claims,
  cityTokens,
  makeTokenId,
} from "./data.js";
import { loadOrGenerateWorld, MapGeneratorName } from "./map_generator.js";
import { hexDistance } from "./hexmap.js";
import { RNG } from "./random.js";

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

function allTokens() {
  return [...playerTokens, ...cityTokens];
}

function clearPlayerTokens() {
  for (const hex of hexes)
    hex.tokens = hex.tokens.filter(
      (id) => !playerTokens.some((player) => player.id === id),
    );
}

function placeToken(tokenId: string, to: string) {
  clearPlayerTokens();
  const destination = hexByName.get(to);
  if (destination) destination.tokens.push(tokenId);
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

const players = new Map<string, PlayerEntity>();
for (const token of playerTokens) {
  players.set(token.entityName, {
    name: token.entityName,
    tokenId: token.id,
    curHealth: 6 + Number(token.id.split("-")[1]) - 1,
    maxHealth: 10,
    curLuck: 1,
    maxLuck: 3,
    gold: 0,
    reputation: 10,
    turns: 20,
    location: locationForToken(token.id),
  });
}
const activeEncounters = new Map<string, string>();

function locationForToken(tokenId: string) {
  return hexes.find((hex) => hex.tokens.includes(tokenId))?.name ?? "Unknown";
}
function moveToken(tokenId: string, to: string) {
  const fromHex = hexes.find((hex) => hex.tokens.includes(tokenId));
  if (fromHex) fromHex.tokens = fromHex.tokens.filter((id) => id !== tokenId);
  hexByName.get(to)?.tokens.push(tokenId);
}

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
function ruleViolation(res: http.ServerResponse, message: string) {
  sendJson(res, 400, { errorType: "rule violation", message });
}
async function readJson(req: http.IncomingMessage) {
  let body = "";
  for await (const chunk of req) body += chunk;
  if (!body) return undefined;
  return JSON.parse(body);
}

function activeEncounterFor(card: TableauCard): ActiveEncounter {
  const skillChecks: Record<string, ActiveEncounterSkillCheck[]> = {
    "dungeon-raid": [
      {
        name: "Stealth",
        target: 5,
        roll: 4,
        modifier: 3,
        total: 7,
        success: true,
      },
      {
        name: "Athletics",
        target: 4,
        roll: 1,
        modifier: 2,
        total: 3,
        success: false,
      },
      {
        name: "Blades",
        target: 6,
        roll: 6,
        modifier: 0,
        total: 6,
        success: true,
      },
    ],
    parley: [
      {
        name: "Persuasion",
        target: 6,
        roll: 2,
        modifier: 1,
        total: 3,
        success: false,
      },
      {
        name: "Deception",
        target: 5,
        roll: 5,
        modifier: 1,
        total: 6,
        success: true,
      },
    ],
    "wandering-sage": [
      {
        name: "Lore",
        target: 4,
        roll: 7,
        modifier: 0,
        total: 7,
        success: true,
      },
      {
        name: "Insight",
        target: 7,
        roll: 3,
        modifier: 2,
        total: 5,
        success: false,
      },
    ],
  };
  return {
    id: card.id,
    title: card.title,
    rewards: card.rewards,
    penalties: card.penalties,
    skillChecks:
      skillChecks[card.id] ??
      card.skillChecks.map((check) => ({
        name: check.name,
        target: check.target,
        roll: 4,
        modifier: 0,
        total: 4,
        success: false,
      })),
  };
}

function playerDto(player: PlayerEntity) {
  player.location = locationForToken(player.tokenId);
  return { ...player };
}

const encounters: TableauCard[] = [
  {
    id: "dungeon-raid",
    title: "Dungeon Raid",
    location: "B17",
    difficulty: 0,
    rewards: ["Gold"],
    penalties: ["Health"],
    skillChecks: [
      { name: "Stealth", target: 5 },
      { name: "Athletics", target: 4 },
      { name: "Blades", target: 6 },
    ],
  },
  {
    id: "parley",
    title: "Parley",
    location: "H8",
    difficulty: 4,
    rewards: ["Gold"],
    penalties: ["Health"],
    skillChecks: [
      { name: "Persuasion", target: 6 },
      { name: "Deception", target: 5 },
    ],
  },
  {
    id: "wandering-sage",
    title: "Wandering Sage",
    location: "M12",
    difficulty: 2,
    rewards: ["Gold"],
    penalties: ["Health"],
    skillChecks: [
      { name: "Lore", target: 4 },
      { name: "Insight", target: 7 },
    ],
  },
];
const encounterById = new Map(
  encounters.map((encounter) => [encounter.id, encounter] as const),
);

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
      return sendJson(res, 200, hexes);
    if (req.method === "GET" && path === "/api/terrain")
      return sendJson(res, 200, terrainSpecs);
    if (req.method === "GET" && path === "/api/regions")
      return sendJson(res, 200, regions);
    if (req.method === "GET" && path === "/api/claims")
      return sendJson(res, 200, claims);
    if (req.method === "GET" && path === "/api/tokens")
      return sendJson(res, 200, allTokens());
    if (req.method === "GET" && path === "/api/tableau")
      return sendJson(res, 200, { encounters });
    if (req.method === "GET" && path === "/api/game")
      return sendJson(res, 200, {
        hexes,
        terrains: terrainSpecs,
        regions,
        claims,
        tokens: allTokens(),
      });
    const entityMatch = path.match(
      /^\/api\/entities\/([^/]+)(?:\/actions\/(camp|travel|run_encounter|finish_encounter))?$/,
    );
    if (entityMatch) {
      const player = players.get(entityMatch[1]);
      if (!player) return sendJson(res, 404, { error: "Entity not found" });
      const action = entityMatch[2];
      if (req.method === "GET" && !action)
        return sendJson(res, 200, playerDto(player));
      if (req.method === "POST" && action === "camp") {
        player.curHealth = Math.min(player.maxHealth, player.curHealth + 1);
        player.turns = Math.max(0, player.turns - 1);
        player.location = locationForToken(player.tokenId);
        return sendJson(res, 200, {
          updates: {
            curHealth: player.curHealth,
            turns: player.turns,
            location: player.location,
          },
          card: { title: "A Restful Night", lines: ["+1 Health", "-1 Turn"] },
        });
      }
      if (req.method === "POST" && action === "travel") {
        const body = await readJson(req);
        const route = Array.isArray(body?.route) ? body.route : [];
        if (route.length > 4)
          return ruleViolation(res, "The travel route is too long");
        const current = locationForToken(player.tokenId);
        if (route.length < 1 || route[0] !== current)
          return ruleViolation(res, "There are gaps in the route");
        for (let i = 0; i < route.length; i++)
          if (typeof route[i] !== "string" || !hexByName.has(route[i]))
            return ruleViolation(res, "There are gaps in the route");
        for (let i = 1; i < route.length; i++) {
          const a = hexByName.get(route[i - 1])!,
            b = hexByName.get(route[i])!;
          if (hexDistance(a, b) !== 1)
            return ruleViolation(res, "There are gaps in the route");
        }
        const destination = route[route.length - 1];
        moveToken(player.tokenId, destination);
        player.location = destination;
        player.turns = Math.max(0, player.turns - 1);
        return sendJson(res, 200, {
          updates: { location: player.location, turns: player.turns },
        });
      }
      if (req.method === "POST" && action === "run_encounter") {
        const body = await readJson(req);
        const encounterId = String(body?.encounterId ?? "");
        const encounter = encounterById.get(encounterId);
        if (!encounter) return ruleViolation(res, "Encounter not found");
        activeEncounters.set(player.name, encounterId);
        return sendJson(res, 200, { encounter: activeEncounterFor(encounter) });
      }
      if (req.method === "POST" && action === "finish_encounter") {
        const body = await readJson(req);
        const encounterId = String(body?.encounterId ?? "");
        const activeEncounterId = activeEncounters.get(player.name);
        if (!activeEncounterId || activeEncounterId !== encounterId)
          return ruleViolation(res, "No active encounter to finish");
        const encounter = encounterById.get(encounterId);
        if (!encounter) return ruleViolation(res, "Encounter not found");
        player.gold += 1;
        player.curHealth = Math.max(0, player.curHealth - 1);
        activeEncounters.delete(player.name);
        return sendJson(res, 200, {
          updates: { gold: player.gold, curHealth: player.curHealth },
          card: { title: "Encounter Results", lines: ["Gold +1", "Health -1"] },
        });
      }
    }
    sendJson(res, 404, { error: "Not found" });
  } catch (error) {
    console.error(error);
    sendJson(res, 500, { error: "Internal server error" });
  }
});
const port = Number(process.env.PORT) || 3001;
server.listen(port, () => console.log(`Picaro server on ${port}`));
