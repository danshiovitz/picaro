import {
  ActivityResult,
  ActiveEncounter,
  ActiveEncounterSkillCheck,
  Condition,
  Effect,
  EffectType,
  EncounterTemplate,
  Hex,
  Item,
  PenaltyType,
  PlayerEntity,
  RewardType,
  SectionType,
  Selection,
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
  skillNames,
  terrainEncounterTemplates,
  specialActions,
} from "./data.js";
import { hexDistance } from "./hexmap.js";
import { instantiateEncounterTemplate } from "./encounter.js";
import { computeEffectiveValue } from "./rule.js";
import { RNG } from "./random.js";
import { getActiveSelection } from "./selection.js";

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
  items: Map<string, Item>;
  players: Map<string, PlayerEntity>;
  activeEncounters: Map<string, ActiveEncounter>;
  activeSelections: Map<string, Selection>;
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
  player: PlayerEntity,
  cards: { name: string; target: number }[],
  rng: RNG,
  old = false,
) {
  return cards.map((check): ActiveEncounterSkillCheck => {
    const roll = rng.d10();
    const modifier = computeEffectiveValue(
      player,
      SectionType.skill,
      check.name,
    );
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

function activeEncounterFor(
  player: PlayerEntity,
  card: TableauCard,
  rng: RNG,
): ActiveEncounter {
  const skillChecks = rollSkillChecks(player, card.skillChecks, rng);
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

function cloneConditions(conditions: Condition[]) {
  return conditions.map((condition) => ({ ...condition }));
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

function effectiveSkills(player: PlayerEntity) {
  return Object.fromEntries(
    skillNames.map(
      (skill) =>
        [
          skill,
          computeEffectiveValue(player, SectionType.skill, skill),
        ] as const,
    ),
  );
}

function playerDto(hexes: Hex[], player: PlayerEntity) {
  player.location = locationForToken(hexes, player.tokenId);
  return {
    ...player,
    maxHealth: computeEffectiveValue(player, SectionType.maxHealth),
    speed: computeEffectiveValue(player, SectionType.speed),
    skills: effectiveSkills(player),
    resources: cloneResources(player.resources),
    inventory: cloneInventory(player.inventory),
    conditions: cloneConditions(player.conditions),
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
    maxHealth: computeEffectiveValue(player, SectionType.maxHealth),
    speed: computeEffectiveValue(player, SectionType.speed),
    location: player.location,
    skills: effectiveSkills(player),
    resources: cloneResources(player.resources),
    inventory: cloneInventory(player.inventory),
    conditions: cloneConditions(player.conditions),
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
    effects.push(...computePenalty(penalty, active.numFailures, player, rng));
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
  const maxHealth = computeEffectiveValue(player, SectionType.maxHealth);
  player.curHealth = Math.max(
    0,
    Math.min(maxHealth, player.curHealth + amount),
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

function removeItems(player: PlayerEntity, itemIds: string[]) {
  const ids = new Set(itemIds);
  player.inventory = player.inventory.filter((item) => !ids.has(item.id));
}

function adjustTurns(player: PlayerEntity, amount: number) {
  player.turns = Math.max(0, player.turns + amount);
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
      case EffectType.RemoveItems: {
        const inventoryIds = new Set(player.inventory.map((item) => item.id));
        return effect.itemIds.every((itemId) => inventoryIds.has(itemId));
      }
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
        adjustTurns(player, effect.amount);
        break;
      case EffectType.Luck:
        adjustLuck(player, effect.amount);
        break;
      case EffectType.Resource:
        adjustResource(player, effect.resourceType, effect.amount);
        break;
      case EffectType.RemoveItems:
        removeItems(player, effect.itemIds);
        break;
    }
  }
}

function payCost(player: PlayerEntity, cost: Effect[]) {
  applyEffects(
    player,
    cost.map((effect) =>
      effect.type === EffectType.RemoveItems
        ? effect
        : { ...effect, amount: -effect.amount },
    ),
  );
}

function effectLabelLine(effect: Effect) {
  if (effect.type === EffectType.RemoveItems) {
    return `Remove items: ${effect.itemIds.join(", ") || "none"}`;
  }
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
  player: PlayerEntity,
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
    case PenaltyType.Resource: {
      const removals = Math.ceil(numFailures / 2);
      if (removals <= 0) return [];
      const pool = Object.entries(player.resources).flatMap(
        ([resourceType, amount]) =>
          Array.from({ length: Math.max(0, amount) }, () => resourceType),
      );
      if (pool.length === 0) return [];
      const remaining = new Map(Object.entries(player.resources));
      const removed = new Map<string, number>();
      let available = pool.length;
      const chooseResource = () => {
        let pick = rng.int(available);
        for (const [resourceType, amount] of remaining) {
          if (amount <= 0) continue;
          if (pick < amount) return resourceType;
          pick -= amount;
        }
        return undefined;
      };
      for (let i = 0; i < Math.min(removals, pool.length); i++) {
        const resourceType = chooseResource();
        if (!resourceType) break;
        remaining.set(resourceType, (remaining.get(resourceType) ?? 0) - 1);
        removed.set(resourceType, (removed.get(resourceType) ?? 0) + 1);
        available -= 1;
      }
      return [...removed.entries()].map(([resourceType, amount]) =>
        resourceEffect(resourceType, -amount),
      );
    }
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

export function getItem(state: ApiState, itemId: string) {
  return state.items.get(itemId);
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
): ActivityResult {
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
  const effects = action.execute(state, player);
  player.location = locationForToken(state.hexes, player.tokenId);
  const selection = getActiveSelection(state, player);
  return {
    effects,
    nextActive: selection ? { type: "selection", selection } : undefined,
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

function endTurn(state: ApiState, player: PlayerEntity, reason: string) {
  console.log(`[endTurn] ${reason} for ${player.name} @ ${player.location}`);
  for (const condition of player.conditions) condition.duration -= 1;
  player.conditions = player.conditions.filter(
    (condition) => condition.duration > 0,
  );
  const currentHex = state.hexByName.get(player.location);
  let changed = false;
  if (currentHex) {
    const speed = computeEffectiveValue(player, SectionType.speed);
    const before = state.tableau.length;
    state.tableau = state.tableau.filter((card) => {
      const hex = state.hexByName.get(card.location);
      return hex ? hexDistance(currentHex, hex) <= 2 * speed : true;
    });
    if (state.tableau.length !== before) changed = true;
  }
  const beforeFill = state.tableau.length;
  fillTableau(state.tableau, encounterTemplates, player, state.rng);
  if (state.tableau.length !== beforeFill) changed = true;
  return changed;
}

export function campEntity(
  state: ApiState,
  player: PlayerEntity,
): ActivityResult {
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  state.travelContinuation.delete(player.name);
  state.travelContinuationRoute.delete(player.name);
  if (!canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(player, turnCost);
  adjustHealth(player, 1);
  player.location = locationForToken(state.hexes, player.tokenId);
  endTurn(state, player, "camp");
  const selection = getActiveSelection(state, player);
  return {
    title: "A Restful Night",
    effects: [{ type: EffectType.Health, amount: 1 }],
    implicitEffects: [{ type: EffectType.Turns, amount: -1 }],
    nextActive: selection ? { type: "selection", selection } : undefined,
  };
}

export function travelEntity(
  state: ApiState,
  player: PlayerEntity,
  request: TravelRequest,
): ActivityResult {
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  const canContinueWithoutCost =
    state.travelContinuation.get(player.name) ?? false;
  if (!canContinueWithoutCost && !canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  if (!canContinueWithoutCost) payCost(player, turnCost);
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
  const speed = computeEffectiveValue(player, SectionType.speed);
  const travelPath = route.slice(0, speed + 1);
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
      ...activeEncounterFor(player, encounterCard, state.rng),
      tableauId: undefined,
    };
    state.activeEncounters.set(player.name, active);
    const tripDestination = route[route.length - 1];
    const completesTrip = encounterHexName === tripDestination;
    if (completesTrip) {
      state.travelContinuation.delete(player.name);
      state.travelContinuationRoute.delete(player.name);
    } else {
      const resumeRoute = route.slice(route.indexOf(encounterHexName));
      state.travelContinuation.set(player.name, true);
      state.travelContinuationRoute.set(player.name, resumeRoute);
    }
    if (completesTrip) {
      endTurn(state, player, "travel-encounter-destination");
      state.travelContinuation.delete(player.name);
      state.travelContinuationRoute.delete(player.name);
    }
    return {
      effects: [],
      implicitEffects: canContinueWithoutCost
        ? []
        : [{ type: EffectType.Turns, amount: -1 }],
      nextActive: { type: "encounter", encounter: active },
    };
  }
  moveToken(state.hexes, state.hexByName, player.tokenId, destination);
  player.location = destination;
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
  if (!remainingRoute) {
    endTurn(state, player, "travel-complete");
  }
  const selection = getActiveSelection(state, player);
  return {
    effects: [],
    implicitEffects: canContinueWithoutCost
      ? []
      : [{ type: EffectType.Turns, amount: -1 }],
    nextActive: selection ? { type: "selection", selection } : undefined,
  };
}

export function runEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest,
): ActivityResult {
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  if (!canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(player, turnCost);
  state.travelContinuation.delete(player.name);
  state.travelContinuationRoute.delete(player.name);
  const encounter = state.tableau.find(
    (card) => card.id === request.encounterId,
  );
  if (!encounter) throw new RulesViolation("Encounter not found");
  const active = activeEncounterFor(player, encounter, state.rng);
  state.activeEncounters.set(player.name, active);
  return {
    effects: [],
    implicitEffects: [{ type: EffectType.Turns, amount: -1 }],
    nextActive: { type: "encounter", encounter: active },
  };
}

export function continueEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest,
): ActivityResult {
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
  active.skillChecks.push(
    ...rollSkillChecks(player, encounterSkillChecks, state.rng),
  );
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
  return {
    effects: [],
    nextActive: { type: "encounter", encounter: active },
  };
}

export function finishEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest & { conceding?: boolean },
): ActivityResult {
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
  if (encounter) {
    removeEncounterFromTableau(state, encounterId);
    endTurn(state, player, "finish-encounter");
  }
  const selection = getActiveSelection(state, player);
  return {
    effects,
    nextActive: selection ? { type: "selection", selection } : undefined,
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
