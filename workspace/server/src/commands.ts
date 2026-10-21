import http from "node:http";
import { URL } from "node:url";

import {
  Hex,
  PlayerEntity,
  TableauCard,
  ActiveEncounter,
  ActiveEncounterSkillCheck,
} from "./types.js";
import { terrainSpecs, regions, claims, cityTokens } from "./data.js";
import { hexDistance } from "./hexmap.js";

export type ApiState = {
  hexes: Hex[];
  hexByName: Map<string, Hex>;
  tokens: { id: string; entityName: string; icon: string }[];
  players: Map<string, PlayerEntity>;
  activeEncounters: Map<string, string>;
  encounters: TableauCard[];
};

export type ApiCommands = {
  handle: (req: http.IncomingMessage, res: http.ServerResponse) => Promise<void>;
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

function ruleViolation(res: http.ServerResponse, message: string) {
  sendJson(res, 400, { errorType: "rule violation", message });
}

async function readJson(req: http.IncomingMessage) {
  let body = "";
  for await (const chunk of req) body += chunk;
  if (!body) return undefined;
  return JSON.parse(body);
}

function allTokens(tokens: ApiState["tokens"]) {
  return [...tokens, ...cityTokens];
}

function locationForToken(hexes: Hex[], tokenId: string) {
  return hexes.find((hex) => hex.tokens.includes(tokenId))?.name ?? "Unknown";
}

function moveToken(hexes: Hex[], hexByName: Map<string, Hex>, tokenId: string, to: string) {
  const fromHex = hexes.find((hex) => hex.tokens.includes(tokenId));
  if (fromHex) fromHex.tokens = fromHex.tokens.filter((id) => id !== tokenId);
  hexByName.get(to)?.tokens.push(tokenId);
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

function playerDto(hexes: Hex[], player: PlayerEntity) {
  player.location = locationForToken(hexes, player.tokenId);
  return { ...player };
}

export function createApiCommands(state: ApiState): ApiCommands {
  const { hexes, hexByName, players, activeEncounters, encounters } = state;
  const encounterById = new Map(
    encounters.map((encounter) => [encounter.id, encounter] as const),
  );

  return {
    handle: async (req, res) => {
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
          return sendJson(res, 200, allTokens(state.tokens));
        if (req.method === "GET" && path === "/api/tableau")
          return sendJson(res, 200, { encounters });
        if (req.method === "GET" && path === "/api/game")
          return sendJson(res, 200, {
            hexes,
            terrains: terrainSpecs,
            regions,
            claims,
            tokens: allTokens(state.tokens),
          });

        const entityMatch = path.match(
          /^\/api\/entities\/([^/]+)(?:\/actions\/(camp|travel|run_encounter|finish_encounter))?$/,
        );
        if (entityMatch) {
          const player = players.get(entityMatch[1]);
          if (!player) return sendJson(res, 404, { error: "Entity not found" });
          const action = entityMatch[2];
          if (req.method === "GET" && !action)
            return sendJson(res, 200, playerDto(hexes, player));
          if (req.method === "POST" && action === "camp") {
            player.curHealth = Math.min(player.maxHealth, player.curHealth + 1);
            player.turns = Math.max(0, player.turns - 1);
            player.location = locationForToken(hexes, player.tokenId);
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
            const current = locationForToken(hexes, player.tokenId);
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
            moveToken(hexes, hexByName, player.tokenId, destination);
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
    },
  };
}
