import {
  ActionResponse,
  ActiveEncounter,
  ActiveEncounterSkillCheck,
  Effect,
  EffectType,
  EncounterTemplate,
  Hex,
  Item,
  PenaltyType,
  PlayerEntity,
  RewardType,
  SpecialAction,
  SpecialActionRequest,
  TableauCard,
  TableauData,
} from "./types.js";
import {
  terrainSpecs,
  regions,
  claims,
  cityTokens,
  encounterTemplates,
  resourceTypes,
  terrainEncounterTemplates,
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

type SpecialActionDefinition = SpecialAction & {
  availability: (player: PlayerEntity) => boolean;
  execute: (state: ApiState, player: PlayerEntity) => Effect[];
};

const specialActions: SpecialActionDefinition[] = [
  {
    id: "medical-visit",
    name: "Medical Visit",
    locations: ["C10"],
    cost: [{ type: EffectType.Gold, amount: 2 }],
    availability: (player) => player.curHealth < player.maxHealth,
    execute: (_state, _player) => [{ type: EffectType.Health, amount: 2 }],
  },
];

export type ApiState = {
  hexes: Hex[];
  hexByName: Map<string, Hex>;
  tokens: { id: string; entityName: string; icon: string }[];
  players: Map<string, PlayerEntity>;
  activeEncounters: Map<string, ActiveEncounter>;
  travelContinuation: Map<string, boolean>;
  travelContinuationRoute: Map<string, string[]>;
  tableau: TableauCard[];
  rng: RNG;
};

export type TravelRequest = { route: string[]; continuing?: boolean };
export type EncounterRequest = {
  encounterId: string;
  tableauId?: string;
  conceding?: boolean;
};

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

function encounterState(
  numSuccesses: number,
  numFailures: number,
  successThreshold: number,
  criticalThreshold: number | undefined,
  failureThreshold: number,
) {
  if (numFailures >= failureThreshold) return "lost" as const;
  if (
    typeof criticalThreshold === "number" &&
    numSuccesses >= criticalThreshold
  )
    return "critical" as const;
  if (numSuccesses >= successThreshold) return "succeeded" as const;
  return "active" as const;
}

function randomPenalty(card: TableauCard, rng: RNG) {
  return card.penalties.length > 0 ? rng.pick(card.penalties) : undefined;
}

function rollSkillChecks(
  cards: { name: string; target: number }[],
  rng: RNG,
  old = false,
) {
  return cards.map((check): ActiveEncounterSkillCheck => {
    const roll = rng.d6();
    const modifier = 3;
    const total = roll + modifier;
    return {
      name: check.name,
      target: check.target,
      roll,
      modifier,
      total,
      success: total >= check.target,
      old,
    };
  });
}

function activeEncounterFor(card: TableauCard, rng: RNG): ActiveEncounter {
  const skillChecks = rollSkillChecks(card.skillChecks, rng);
  const numSuccesses = skillChecks.filter((check) => check.success).length;
  const numFailures = skillChecks.length - numSuccesses;
  const state = encounterState(
    numSuccesses,
    numFailures,
    card.successThreshold,
    card.criticalThreshold,
    card.failureThreshold,
  );
  return {
    id: card.id,
    tableauId: card.id,
    title: card.title,
    state,
    successThreshold: card.successThreshold,
    criticalThreshold: card.criticalThreshold,
    failureThreshold: card.failureThreshold,
    numSuccesses,
    numFailures,
    nextPenalty:
      state === "active" || state === "succeeded"
        ? randomPenalty(card, rng)
        : undefined,
    rewards: card.rewards,
    criticalRewards: card.criticalRewards,
    penalties: card.penalties,
    skillChecks,
    skillCheckTemplate: card.skillChecks,
  };
}

function cloneInventory(inventory: Item[]) {
  return inventory.map((item) => ({ ...item }));
}

function cloneResources(resources: Record<string, number>) {
  return { ...resources };
}

function resourceEffect(resourceType: string, amount: number): Effect {
  return { type: EffectType.Resource, resourceType, amount };
}

function randomResourceType(rng: RNG) {
  return rng.pick(resourceTypes);
}

function playerDto(hexes: Hex[], player: PlayerEntity) {
  player.location = locationForToken(hexes, player.tokenId);
  return {
    ...player,
    resources: cloneResources(player.resources),
    inventory: cloneInventory(player.inventory),
  };
}

function playerUpdates(player: PlayerEntity) {
  return {
    curHealth: player.curHealth,
    curLuck: player.curLuck,
    maxLuck: player.maxLuck,
    gold: player.gold,
    reputation: player.reputation,
    turns: player.turns,
    speed: player.speed,
    location: player.location,
    resources: cloneResources(player.resources),
    inventory: cloneInventory(player.inventory),
  } satisfies Partial<PlayerEntity>;
}

function resolveEncounterEffects(
  player: PlayerEntity,
  active: ActiveEncounter,
  rng: RNG,
  conceding = false,
) {
  if (conceding) {
    active.state = "lost";
    active.nextPenalty = undefined;
  }
  const effects: Effect[] = [];
  const meetsFailureThreshold = active.numFailures >= active.failureThreshold;
  if (
    !meetsFailureThreshold &&
    active.numSuccesses >= active.successThreshold
  ) {
    for (const reward of active.rewards)
      effects.push(...computeReward(reward, rng));
    if (
      typeof active.criticalThreshold === "number" &&
      active.numSuccesses >= active.criticalThreshold
    ) {
      for (const reward of active.criticalRewards)
        effects.push(...computeCriticalReward(reward, rng));
    }
  }
  for (const penalty of active.penalties)
    effects.push(...computePenalty(penalty, active.numFailures, rng));
  applyEffects(player, effects);
  return effects;
}

function labelForReward(type: RewardType | PenaltyType) {
  return type[0].toUpperCase() + type.slice(1);
}

function labelForEffect(type: EffectType) {
  return type[0].toUpperCase() + type.slice(1);
}

function adjustGold(player: PlayerEntity, amount: number) {
  player.gold = Math.max(0, player.gold + amount);
}

function adjustReputation(player: PlayerEntity, amount: number) {
  player.reputation = Math.max(0, player.reputation + amount);
}

function adjustHealth(player: PlayerEntity, amount: number) {
  player.curHealth = Math.max(
    0,
    Math.min(player.maxHealth, player.curHealth + amount),
  );
}

function adjustResource(
  player: PlayerEntity,
  resourceType: string,
  amount: number,
) {
  const current = player.resources[resourceType] ?? 0;
  player.resources[resourceType] = Math.max(0, current + amount);
}

function adjustLuck(player: PlayerEntity, amount: number) {
  player.curLuck = Math.max(
    0,
    Math.min(player.maxLuck, player.curLuck + amount),
  );
}

function canAfford(player: PlayerEntity, cost: Effect[]) {
  return cost.every((effect) => {
    switch (effect.type) {
      case EffectType.Gold:
        return player.gold >= effect.amount;
      case EffectType.Reputation:
        return player.reputation >= effect.amount;
      case EffectType.Health:
        return player.curHealth >= effect.amount;
      case EffectType.Turns:
        return player.turns >= effect.amount;
      case EffectType.Luck:
        return player.curLuck >= effect.amount;
      case EffectType.Resource:
        return (player.resources[effect.resourceType] ?? 0) >= effect.amount;
    }
  });
}

function applyEffects(player: PlayerEntity, effects: Effect[]) {
  for (const effect of effects) {
    switch (effect.type) {
      case EffectType.Gold:
        adjustGold(player, effect.amount);
        break;
      case EffectType.Reputation:
        adjustReputation(player, effect.amount);
        break;
      case EffectType.Health:
        adjustHealth(player, effect.amount);
        break;
      case EffectType.Turns:
        player.turns = Math.max(0, player.turns + effect.amount);
        break;
      case EffectType.Luck:
        adjustLuck(player, effect.amount);
        break;
      case EffectType.Resource:
        adjustResource(player, effect.resourceType, effect.amount);
        break;
    }
  }
}

function payCost(player: PlayerEntity, cost: Effect[]) {
  applyEffects(
    player,
    cost.map((effect) => ({ ...effect, amount: -effect.amount })),
  );
}

function effectLabelLine(effect: Effect) {
  return `${effect.amount >= 0 ? "+" : "-"}${Math.abs(effect.amount)} ${labelForEffect(effect.type)}`;
}

function effectsToLines(effects: Effect[]) {
  return effects.map(effectLabelLine);
}

function computeReward(rewardType: RewardType, rng: RNG): Effect[] {
  switch (rewardType) {
    case RewardType.Gold:
      return [{ type: EffectType.Gold, amount: 3 }];
    case RewardType.Reputation:
      return [{ type: EffectType.Reputation, amount: 1 }];
    case RewardType.Luck:
      return [{ type: EffectType.Luck, amount: 1 }];
    case RewardType.Resource:
      return [resourceEffect(randomResourceType(rng), 1)];
  }
}

function computeCriticalReward(rewardType: RewardType, rng: RNG): Effect[] {
  switch (rewardType) {
    case RewardType.Gold:
      return [{ type: EffectType.Gold, amount: 4 }];
    case RewardType.Reputation:
      return [{ type: EffectType.Reputation, amount: 1 }];
    case RewardType.Luck:
      return [{ type: EffectType.Luck, amount: 1 }];
    case RewardType.Resource:
      return [resourceEffect(randomResourceType(rng), 2)];
  }
}

function computePenalty(
  penaltyType: PenaltyType,
  numFailures: number,
  rng: RNG,
): Effect[] {
  switch (penaltyType) {
    case PenaltyType.Gold:
      return numFailures > 0 ? [{ type: EffectType.Gold, amount: -1 }] : [];
    case PenaltyType.Health:
      return numFailures > 0
        ? [{ type: EffectType.Health, amount: -numFailures }]
        : [];
    case PenaltyType.Turns:
      return [{ type: EffectType.Turns, amount: -1 }];
    case PenaltyType.Luck:
      return [{ type: EffectType.Luck, amount: -1 }];
    case PenaltyType.Resource:
      return numFailures > 0
        ? [resourceEffect(randomResourceType(rng), -numFailures)]
        : [];
  }
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

export function getSpecialActionCatalog(): SpecialAction[] {
  return specialActions.map(
    ({ availability: _availability, execute: _execute, ...action }) => action,
  );
}

export function getSpecialActions(
  state: ApiState,
  player: PlayerEntity,
): SpecialAction[] {
  return specialActions
    .filter((action) => action.availability(player))
    .map(
      ({ availability: _availability, execute: _execute, ...action }) => action,
    );
}

export function performSpecialAction(
  state: ApiState,
  player: PlayerEntity,
  request: SpecialActionRequest,
): ActionResponse {
  const action = specialActions.find(
    (item) => item.id === request.specialActionId,
  );
  if (!action) throw new RulesViolation("Special action not found");
  state.travelContinuation.delete(player.name);
  state.travelContinuationRoute.delete(player.name);
  if (!action.availability(player))
    throw new RulesViolation("Special action is unavailable");
  if (action.locations?.length && !action.locations.includes(player.location))
    throw new RulesViolation("Special action cannot be performed here");
  if (!canAfford(player, action.cost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(player, action.cost);
  const lines = effectsToLines(action.execute(state, player));
  player.location = locationForToken(state.hexes, player.tokenId);
  return {
    updates: playerUpdates(player),
    card: { title: "Action Results", lines },
    tableauChanged: false,
  };
}

export function getGame(state: ApiState) {
  return {
    hexes: state.hexes,
    terrains: terrainSpecs,
    regions,
    claims,
    tokens: allTokens(state.tokens),
    resourceTypes,
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
      return hex ? hexDistance(currentHex, hex) <= 2 * player.speed : true;
    });
    if (state.tableau.length !== before) changed = true;
  }
  const beforeFill = state.tableau.length;
  fillTableau(state.tableau, encounterTemplates, player, state.rng);
  if (state.tableau.length !== beforeFill) changed = true;
  return changed;
}

export function campEntity(state: ApiState, player: PlayerEntity) {
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  state.travelContinuation.delete(player.name);
  state.travelContinuationRoute.delete(player.name);
  if (!canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(player, turnCost);
  player.curHealth = Math.min(player.maxHealth, player.curHealth + 1);
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
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  const canContinueWithoutCost =
    state.travelContinuation.get(player.name) ?? false;
  if (!canContinueWithoutCost && !canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  const route = request.route;
  const storedContinuation = state.travelContinuationRoute.get(player.name);
  if (storedContinuation) {
    const sameRoute =
      storedContinuation.length === route.length &&
      storedContinuation.every((hex, i) => hex === route[i]);
    if (!sameRoute) throw new RulesViolation("There are gaps in the route");
  }
  const current = locationForToken(state.hexes, player.tokenId);
  if (route.length < 1 || route[0] !== current)
    throw new RulesViolation("There are gaps in the route");
  const travelPath = route.slice(0, player.speed + 1);
  for (let i = 0; i < travelPath.length; i++) {
    if (
      typeof travelPath[i] !== "string" ||
      !state.hexByName.has(travelPath[i])
    ) {
      throw new RulesViolation("There are gaps in the route");
    }
  }
  for (let i = 1; i < travelPath.length; i++) {
    const a = state.hexByName.get(travelPath[i - 1])!,
      b = state.hexByName.get(travelPath[i])!;
    if (hexDistance(a, b) !== 1)
      throw new RulesViolation("There are gaps in the route");
  }
  const destination = travelPath[travelPath.length - 1];
  const encounterRoute = travelPath.slice(1);
  const encounterHexName =
    encounterRoute.length > 0 && state.rng.next() < 0.5
      ? state.rng.pick(encounterRoute)
      : undefined;
  if (encounterHexName) {
    const encounterHex = state.hexByName.get(encounterHexName);
    if (encounterHex) {
      moveToken(state.hexes, state.hexByName, player.tokenId, encounterHexName);
      player.location = encounterHexName;
    }
    const templates = encounterHex
      ? (terrainEncounterTemplates[encounterHex.terrain] ?? encounterTemplates)
      : encounterTemplates;
    const template = state.rng.pick(templates);
    const encounterCard = instantiateEncounterTemplate(template, player);
    encounterCard.location = encounterHexName;
    const active = {
      ...activeEncounterFor(encounterCard, state.rng),
      tableauId: undefined,
    };
    state.activeEncounters.set(player.name, active);
    const resumeRoute = route.slice(route.indexOf(encounterHexName));
    state.travelContinuation.set(player.name, true);
    state.travelContinuationRoute.set(player.name, resumeRoute);
    if (!canContinueWithoutCost) payCost(player, turnCost);
    return {
      updates: playerUpdates(player),
      encounter: active,
      travelRoute: resumeRoute,
      tableauChanged: false,
    };
  }
  moveToken(state.hexes, state.hexByName, player.tokenId, destination);
  player.location = destination;
  if (!canContinueWithoutCost) payCost(player, turnCost);
  const remainingRoute =
    route.length > travelPath.length
      ? route.slice(travelPath.length - 1)
      : undefined;
  if (remainingRoute) {
    state.travelContinuation.set(player.name, true);
    state.travelContinuationRoute.set(player.name, remainingRoute);
  } else {
    state.travelContinuation.delete(player.name);
    state.travelContinuationRoute.delete(player.name);
  }
  const tableauChanged = endTurn(state, player);
  return {
    updates: playerUpdates(player),
    travelRoute: remainingRoute,
    tableauChanged,
    tableau: tableauChanged ? getTableau(state) : undefined,
  };
}

export function runEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest,
) {
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  if (!canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  state.travelContinuation.delete(player.name);
  state.travelContinuationRoute.delete(player.name);
  const encounter = state.tableau.find(
    (card) => card.id === request.encounterId,
  );
  if (!encounter) throw new RulesViolation("Encounter not found");
  payCost(player, turnCost);
  const active = activeEncounterFor(encounter, state.rng);
  state.activeEncounters.set(player.name, active);
  return { encounter: active, updates: playerUpdates(player) };
}

export function continueEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest,
) {
  const active = state.activeEncounters.get(player.name);
  if (!active || active.id !== request.encounterId)
    throw new RulesViolation("No active encounter to continue");
  if (active.state !== "active" && active.state !== "succeeded")
    throw new RulesViolation("Encounter cannot be continued");
  const encounter = active.tableauId
    ? state.tableau.find((card) => card.id === request.encounterId)
    : undefined;
  if (active.tableauId && !encounter)
    throw new RulesViolation("Encounter not found");
  const encounterSkillChecks =
    encounter?.skillChecks ?? active.skillCheckTemplate;
  if (active.nextPenalty) {
    active.penalties = [...active.penalties, active.nextPenalty];
    active.nextPenalty = undefined;
  }
  active.skillChecks = active.skillChecks.map((check) => ({
    ...check,
    old: true,
  }));
  active.skillChecks.push(...rollSkillChecks(encounterSkillChecks, state.rng));
  active.numSuccesses = active.skillChecks.filter(
    (check) => check.success,
  ).length;
  active.numFailures = active.skillChecks.length - active.numSuccesses;
  active.state = encounterState(
    active.numSuccesses,
    active.numFailures,
    active.successThreshold,
    active.criticalThreshold,
    active.failureThreshold,
  );
  if (active.state === "active" || active.state === "succeeded") {
    active.nextPenalty = encounter
      ? randomPenalty(encounter, state.rng)
      : randomPenalty(
          { penalties: active.penalties } as TableauCard,
          state.rng,
        );
  }
  return { encounter: active, updates: playerUpdates(player) };
}

export function finishEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest & { conceding?: boolean },
) {
  const active = state.activeEncounters.get(player.name);
  const encounterId = request.tableauId ?? request.encounterId;
  if (!active || active.id !== request.encounterId)
    throw new RulesViolation("No active encounter to finish");
  const encounter = active.tableauId
    ? state.tableau.find((card) => card.id === request.encounterId)
    : undefined;
  if (active.tableauId && !encounter)
    throw new RulesViolation("Encounter not found");
  if (request.conceding) {
    active.state = "lost";
    active.nextPenalty = undefined;
  }
  const effects = resolveEncounterEffects(
    player,
    active,
    state.rng,
    request.conceding,
  );
  state.activeEncounters.delete(player.name);
  const removedEncounterId = encounter
    ? removeEncounterFromTableau(state, encounterId)
      ? encounterId
      : undefined
    : undefined;
  const travelRoute = state.travelContinuationRoute.get(player.name);
  const tableauChanged = encounter
    ? endTurn(state, player) || Boolean(removedEncounterId)
    : false;
  return {
    updates: playerUpdates(player),
    card: { title: "Encounter Results", lines: effectsToLines(effects) },
    travelRoute,
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
