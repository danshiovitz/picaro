import {
  ActiveEncounter,
  ActiveEncounterSkillCheck,
  EncounterTemplate,
  Hex,
  PlayerEntity,
  TableauCard,
  TableauData,
} from "./types.js";
import {
  terrainSpecs,
  regions,
  claims,
  cityTokens,
  encounterTemplates,
} from "./data.js";
import { hexDistance } from "./hexmap.js";
import { instantiateEncounterTemplate } from "./encounter.js";
import { RNG } from "./random.js";

export class RulesViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RulesViolation";
  }
}

export type ApiState = {
  hexes: Hex[];
  hexByName: Map<string, Hex>;
  tokens: { id: string; entityName: string; icon: string }[];
  players: Map<string, PlayerEntity>;
  activeEncounters: Map<string, string>;
  tableau: TableauCard[];
  rng: RNG;
};

export type TravelRequest = { route: string[] };
export type EncounterRequest = { encounterId: string; tableauId?: string };

function allTokens(tokens: ApiState["tokens"]) {
  return [...tokens, ...cityTokens];
}

function locationForToken(hexes: Hex[], tokenId: string) {
  return hexes.find((hex) => hex.tokens.includes(tokenId))?.name ?? "Unknown";
}

function moveToken(
  hexes: Hex[],
  hexByName: Map<string, Hex>,
  tokenId: string,
  to: string,
) {
  const fromHex = hexes.find((hex) => hex.tokens.includes(tokenId));
  if (fromHex) fromHex.tokens = fromHex.tokens.filter((id) => id !== tokenId);
  hexByName.get(to)?.tokens.push(tokenId);
}

function activeEncounterFor(card: TableauCard, rng: RNG): ActiveEncounter {
  return {
    id: card.id,
    tableauId: card.id,
    title: card.title,
    rewards: card.rewards,
    penalties: card.penalties,
    skillChecks: card.skillChecks.map((check): ActiveEncounterSkillCheck => {
      const roll = rng.d6();
      const modifier = 0;
      const total = roll + modifier;
      return {
        name: check.name,
        target: check.target,
        roll,
        modifier,
        total,
        success: total >= check.target,
      };
    }),
  };
}

function playerDto(hexes: Hex[], player: PlayerEntity) {
  player.location = locationForToken(hexes, player.tokenId);
  return { ...player };
}

export function getHexes(state: ApiState) {
  return state.hexes;
}

export function getTerrain() {
  return terrainSpecs;
}

export function getRegions() {
  return regions;
}

export function getClaims() {
  return claims;
}

export function getTokens(state: ApiState) {
  return allTokens(state.tokens);
}

export function getTableau(state: ApiState): TableauData {
  return { encounters: state.tableau };
}

export function getGame(state: ApiState) {
  return {
    hexes: state.hexes,
    terrains: terrainSpecs,
    regions,
    claims,
    tokens: allTokens(state.tokens),
  };
}

export function getEntity(state: ApiState, player: PlayerEntity) {
  return playerDto(state.hexes, player);
}

function removeEncounterFromTableau(state: ApiState, encounterId: string) {
  const index = state.tableau.findIndex((card) => card.id === encounterId);
  if (index === -1) return false;
  state.tableau.splice(index, 1);
  return true;
}

function endTurn(state: ApiState, player: PlayerEntity) {
  const currentHex = state.hexByName.get(player.location);
  let changed = false;
  if (currentHex) {
    const before = state.tableau.length;
    state.tableau = state.tableau.filter((card) => {
      const hex = state.hexByName.get(card.location);
      return hex ? hexDistance(currentHex, hex) <= 6 : true;
    });
    if (state.tableau.length !== before) changed = true;
  }
  const beforeFill = state.tableau.length;
  fillTableau(state.tableau, encounterTemplates, player, state.rng);
  if (state.tableau.length !== beforeFill) changed = true;
  return changed;
}

export function campEntity(state: ApiState, player: PlayerEntity) {
  player.curHealth = Math.min(player.maxHealth, player.curHealth + 1);
  player.turns = Math.max(0, player.turns - 1);
  player.location = locationForToken(state.hexes, player.tokenId);
  const tableauChanged = endTurn(state, player);
  return {
    updates: {
      curHealth: player.curHealth,
      turns: player.turns,
      location: player.location,
    },
    card: { title: "A Restful Night", lines: ["+1 Health", "-1 Turn"] },
    tableauChanged,
    tableau: tableauChanged ? getTableau(state) : undefined,
  };
}

export function travelEntity(
  state: ApiState,
  player: PlayerEntity,
  request: TravelRequest,
) {
  const route = request.route;
  if (route.length > 4)
    throw new RulesViolation("The travel route is too long");
  const current = locationForToken(state.hexes, player.tokenId);
  if (route.length < 1 || route[0] !== current)
    throw new RulesViolation("There are gaps in the route");
  for (let i = 0; i < route.length; i++) {
    if (typeof route[i] !== "string" || !state.hexByName.has(route[i])) {
      throw new RulesViolation("There are gaps in the route");
    }
  }
  for (let i = 1; i < route.length; i++) {
    const a = state.hexByName.get(route[i - 1])!,
      b = state.hexByName.get(route[i])!;
    if (hexDistance(a, b) !== 1)
      throw new RulesViolation("There are gaps in the route");
  }
  const destination = route[route.length - 1];
  moveToken(state.hexes, state.hexByName, player.tokenId, destination);
  player.location = destination;
  player.turns = Math.max(0, player.turns - 1);
  const tableauChanged = endTurn(state, player);
  return {
    updates: { location: player.location, turns: player.turns },
    tableauChanged,
    tableau: tableauChanged ? getTableau(state) : undefined,
  };
}

export function runEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest,
) {
  const encounter = state.tableau.find(
    (card) => card.id === request.encounterId,
  );
  if (!encounter) throw new RulesViolation("Encounter not found");
  state.activeEncounters.set(player.name, request.encounterId);
  return { encounter: activeEncounterFor(encounter, state.rng) };
}

export function finishEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest,
) {
  const activeEncounterId = state.activeEncounters.get(player.name);
  const encounterId = request.tableauId ?? request.encounterId;
  if (!activeEncounterId || activeEncounterId !== request.encounterId)
    throw new RulesViolation("No active encounter to finish");
  const encounter = state.tableau.find(
    (card) => card.id === request.encounterId,
  );
  if (!encounter) throw new RulesViolation("Encounter not found");
  player.gold += 1;
  player.curHealth = Math.max(0, player.curHealth - 1);
  state.activeEncounters.delete(player.name);
  const removedEncounterId = removeEncounterFromTableau(state, encounterId)
    ? encounterId
    : undefined;
  const tableauChanged = endTurn(state, player) || Boolean(removedEncounterId);
  return {
    updates: { gold: player.gold, curHealth: player.curHealth },
    card: { title: "Encounter Results", lines: ["Gold +1", "Health -1"] },
    removedEncounterId,
    tableauChanged,
    tableau: tableauChanged ? getTableau(state) : undefined,
  };
}

export function fillTableau(
  tableau: TableauCard[],
  templates: EncounterTemplate[],
  player: PlayerEntity,
  rng: RNG,
) {
  while (tableau.length < 3 && templates.length > 0) {
    const template = rng.pick(templates);
    tableau.push(instantiateEncounterTemplate(template, player));
  }
}
