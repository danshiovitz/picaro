import {
  ActivityNextActive,
  ActivityResult,
  ActiveEncounter,
  ActiveEncounterSkillCheck,
  ApiState,
  Condition,
  Effect,
  EffectType,
  EncounterTemplate,
  Hex,
  Item,
  PenaltyType,
  PendingActivity,
  PlayerEntity,
  RewardType,
  SectionType,
  Selection,
  SelectionChoice,
  SpecialAction,
  SpecialActionRequest,
  TableauCard,
  TableauData,
} from "./types.js";
import { hexDistance } from "./hexmap.js";
import {
  terrainSpecs,
  claims,
  cityTokens,
  encounterTemplates,
  resourceTypes,
  skillNames,
  terrainEncounterTemplates,
  specialActions,
} from "./data.js";
import {
  instantiateEncounterTemplate,
  rollEncounterSkillChecks,
} from "./encounter.js";
import { computeEffectiveValue } from "./rule.js";
import { RNG } from "./random.js";
import { selectionDto } from "./selection.js";

export class RulesViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RulesViolation";
  }
}

export type TravelRequest = { route: string[] };
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

function getPlayerTableau(state: ApiState, player: PlayerEntity) {
  const tableau = state.tableau.get(player.id);
  if (!tableau) throw new RulesViolation("Tableau not found");
  return tableau;
}

function pendingWorkFor(state: ApiState, player: PlayerEntity) {
  return state.pendingWork.get(player.id) ?? [];
}

function assertNoPendingWork(state: ApiState, player: PlayerEntity) {
  if (
    pendingWorkFor(state, player).length > 0 ||
    state.currentActivities.has(player.id)
  ) {
    throw new RulesViolation("You must finish pending items first.");
  }
}

export function queuePendingWork(
  state: ApiState,
  player: PlayerEntity,
  work: PendingActivity,
  front = false,
) {
  const queue = pendingWorkFor(state, player);
  if (front) queue.unshift(work);
  else queue.push(work);
  state.pendingWork.set(player.id, queue);
}

function takePendingWork(
  state: ApiState,
  player: PlayerEntity,
): PendingActivity | undefined {
  const queue = pendingWorkFor(state, player);
  const work = queue.shift();
  if (queue.length > 0) state.pendingWork.set(player.id, queue);
  else state.pendingWork.delete(player.id);
  return work;
}

export function nextActiveForPlayer(
  state: ApiState,
  player: PlayerEntity,
): ActivityNextActive | undefined {
  if (!state.currentActivities.has(player.id)) {
    let pending = takePendingWork(state, player);
    if (pending) {
      state.currentActivities.set(player.id, pending);
    }
  }
  const activity = state.currentActivities.get(player.id);
  if (!activity) return undefined;
  switch (activity.type) {
    case "selection":
      return { type: "selection", selection: selectionDto(activity.selection) };
    case "encounter":
      return activity;
  }
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
  checks: { name: string; target: number }[],
  rng: RNG,
) {
  return checks.map((check): ActiveEncounterSkillCheck => {
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
    difficulty: card.difficulty,
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
    skillSource: [...card.skillSource],
    currentSkillChecks: skillChecks,
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

function cloneSkillXp(skill_xp: Record<string, number>) {
  return { ...skill_xp };
}

function resourceEffect(resourceType: string, amount: number): Effect {
  return { type: EffectType.Resource, resourceType, amount };
}

function controlledTeleportSelection(
  state: ApiState,
  player: PlayerEntity,
  radius: number,
): Selection {
  const originHex = state.hexByName.get(player.location);
  if (!originHex) throw new RulesViolation("Origin hex not found");
  const choices = state.hexes
    .filter((hex) => hexDistance(originHex, hex) <= radius)
    .map((hex, index) => ({
      description: hex.name,
      data: hex.name,
      index,
    }));
  const selection: Selection = {
    id: `selection-controlled-teleport-${Math.random().toString(36).slice(2)}`,
    title: "Controlled Teleport",
    description: `Choose a hex within ${radius} hexes of ${player.location}.`,
    choices,
    minChoices: 1,
    maxChoices: 1,
    useDropdown: true,
    hexSelection: { originHex: player.location, radius },
    callback: (indexes) => {
      const choice = selection.choices.find(
        (item: SelectionChoice) => item.index === indexes[0],
      );
      if (!choice) {
        return {
          title: "Controlled Teleport",
          flavorText: "No selection made.",
          effects: [],
        };
      }
      const origin = state.hexByName.get(selection.hexSelection!.originHex);
      if (!origin) throw new RulesViolation("Origin hex not found");
      const target = state.hexByName.get(choice.data);
      if (!target) throw new RulesViolation("Selected hex not found");
      if (hexDistance(origin, target) > selection.hexSelection!.radius) {
        throw new RulesViolation("Selected hex is out of range");
      }
      moveToken(state.hexes, state.hexByName, player.tokenId, target.name);
      player.location = target.name;
      return {
        title: "Controlled Teleport",
        flavorText: `Teleported to ${target.name}.`,
        effects: [],
      };
    },
  };
  return selection;
}

function freeXpSelection(
  state: ApiState,
  player: PlayerEntity,
  amount: number,
): Selection {
  const selection: Selection = {
    id: `selection-free-xp-${Math.random().toString(36).slice(2)}`,
    title: "Free XP",
    description: `Choose a skill to gain ${amount} xp in.`,
    choices: skillNames.map((skill, index) => ({
      description: skill,
      data: skill,
      index,
    })),
    minChoices: 1,
    maxChoices: 1,
    useDropdown: true,
    callback: (indexes) => {
      const choice = selection.choices.find(
        (item: SelectionChoice) => item.index === indexes[0],
      );
      if (!choice) {
        return {
          title: "Free XP",
          flavorText: "No selection made.",
          effects: [],
        };
      }
      const currentXp = player.skill_xp[choice.data] ?? 0;
      const nextXp = currentXp + amount;
      const effect =
        skillLevelFromXp(nextXp) > skillLevelFromXp(currentXp)
          ? ({
              type: EffectType.SkillXp,
              skill: choice.data,
              amount,
              newLevel: skillLevelFromXp(nextXp),
            } satisfies Effect)
          : ({
              type: EffectType.SkillXp,
              skill: choice.data,
              amount,
            } satisfies Effect);
      applyEffects(state, player, [effect]);
      return {
        title: "Free XP",
        effects: [effect],
      };
    },
  };
  return selection;
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

type PlayerDto = PlayerEntity & { skills: Record<string, number> };

function playerDto(hexes: Hex[], player: PlayerEntity) {
  player.location = locationForToken(hexes, player.tokenId);
  return {
    ...player,
    skill_xp: cloneSkillXp(player.skill_xp),
    maxHealth: computeEffectiveValue(player, SectionType.maxHealth),
    speed: computeEffectiveValue(player, SectionType.speed),
    skills: effectiveSkills(player),
    resources: cloneResources(player.resources),
    inventory: cloneInventory(player.inventory),
    conditions: cloneConditions(player.conditions),
  } satisfies PlayerDto;
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
    skill_xp: cloneSkillXp(player.skill_xp),
    skills: effectiveSkills(player),
    resources: cloneResources(player.resources),
    inventory: cloneInventory(player.inventory),
    conditions: cloneConditions(player.conditions),
  } satisfies Partial<PlayerEntity> & { skills: Record<string, number> };
}

const skillXpThresholds = [0, 10, 30, 50, 75, 100, 130];

function skillLevelFromXp(xp: number) {
  let level = 0;
  for (let i = 0; i < skillXpThresholds.length; i++) {
    if (xp >= skillXpThresholds[i]) level = i;
  }
  return level;
}

function resolveEncounterEffects(
  state: ApiState,
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

  const failedChecks = active.skillChecks.filter((check) => !check.success);
  const succeededChecks = active.skillChecks.filter((check) => check.success);
  const selectedFailedChecks =
    failedChecks.length >= 3
      ? failedChecks.length === 3
        ? failedChecks
        : rng.shuffle(failedChecks).slice(0, 3)
      : failedChecks;
  const selectedSucceededChecks =
    failedChecks.length >= 3
      ? []
      : rng.shuffle(succeededChecks).slice(0, 3 - failedChecks.length);

  const xpEffects: Effect[] = [];
  const runningSkillXp = { ...player.skill_xp };
  for (const check of [...selectedFailedChecks, ...selectedSucceededChecks]) {
    const amount = check.success ? 1 : 2;
    const currentXp = runningSkillXp[check.name] ?? 0;
    const currentLevel = skillLevelFromXp(currentXp);
    const nextXp = currentXp + amount;
    const nextLevel = skillLevelFromXp(nextXp);
    runningSkillXp[check.name] = nextXp;
    xpEffects.push(
      nextLevel > currentLevel
        ? {
            type: EffectType.SkillXp,
            skill: check.name,
            amount,
            newLevel: nextLevel,
          }
        : { type: EffectType.SkillXp, skill: check.name, amount },
    );
  }
  effects.push(...xpEffects);
  applyEffects(state, player, effects);
  return effects;
}

function labelForReward(type: RewardType | PenaltyType) {
  if (type === RewardType.FreeXp) return "Free XP";
  if (type === RewardType.ControlledTeleport) return "Controlled Teleport";
  return type[0].toUpperCase() + type.slice(1);
}

function labelForEffect(type: EffectType) {
  if (type === EffectType.FreeXp) return "Free XP";
  if (type === EffectType.ControlledTeleport) return "Controlled Teleport";
  if (type === EffectType.SkillXp) return "Skill XP";
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
  for (const effect of cost) {
    switch (effect.type) {
      case EffectType.FreeXp:
        throw new RulesViolation("Free XP cannot be used as a cost.");
      case EffectType.Gold:
        if (player.gold < effect.amount) return false;
        break;
      case EffectType.Reputation:
        if (player.reputation < effect.amount) return false;
        break;
      case EffectType.Health:
        if (player.curHealth < effect.amount) return false;
        break;
      case EffectType.Turns:
        if (player.turns < effect.amount) return false;
        break;
      case EffectType.Luck:
        if (player.curLuck < effect.amount) return false;
        break;
      case EffectType.Resource:
        if ((player.resources[effect.resourceType] ?? 0) < effect.amount)
          return false;
        break;
      case EffectType.SkillXp:
        if ((player.skill_xp[effect.skill] ?? 0) < effect.amount) return false;
        break;
      case EffectType.RemoveItems: {
        const inventoryIds = new Set(player.inventory.map((item) => item.id));
        if (!effect.itemIds.every((itemId) => inventoryIds.has(itemId)))
          return false;
        break;
      }
    }
  }
  return true;
}

function adjustSkillXp(player: PlayerEntity, skill: string, amount: number) {
  const current = player.skill_xp[skill] ?? 0;
  player.skill_xp[skill] = Math.max(0, current + amount);
}

function applyEffects(
  state: ApiState,
  player: PlayerEntity,
  effects: Effect[],
) {
  const frontQueue: PendingActivity[] = [];
  for (const effect of effects) {
    switch (effect.type) {
      case EffectType.FreeXp:
        frontQueue.push({
          type: "selection",
          selection: freeXpSelection(state, player, effect.amount),
        });
        break;
      case EffectType.ControlledTeleport:
        frontQueue.push({
          type: "selection",
          selection: controlledTeleportSelection(state, player, effect.radius),
        });
        break;
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
      case EffectType.SkillXp:
        adjustSkillXp(player, effect.skill, effect.amount);
        break;
      case EffectType.RemoveItems:
        removeItems(player, effect.itemIds);
        break;
    }
  }
  if (frontQueue.length > 0) {
    const queue = pendingWorkFor(state, player);
    queue.unshift(...frontQueue);
    state.pendingWork.set(player.id, queue);
  }
}

function payCost(state: ApiState, player: PlayerEntity, cost: Effect[]) {
  applyEffects(
    state,
    player,
    cost.map((effect) =>
      effect.type === EffectType.RemoveItems ||
      effect.type === EffectType.ControlledTeleport
        ? effect
        : { ...effect, amount: -effect.amount },
    ),
  );
}

function effectLabelLine(effect: Effect) {
  if (effect.type === EffectType.RemoveItems) {
    return `Remove items: ${effect.itemIds.join(", ") || "none"}`;
  }
  if (effect.type === EffectType.ControlledTeleport) {
    return `${labelForEffect(effect.type)} (radius ${effect.radius})`;
  }
  const label =
    effect.type === EffectType.SkillXp
      ? `${labelForEffect(effect.type)} (${effect.skill})`
      : labelForEffect(effect.type);
  return `${effect.amount >= 0 ? "+" : "-"}${Math.abs(effect.amount)} ${label}`;
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
    case RewardType.FreeXp:
      return [{ type: EffectType.FreeXp, amount: 5 }];
    case RewardType.ControlledTeleport:
      return [{ type: EffectType.ControlledTeleport, radius: 5 }];
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
    case RewardType.FreeXp:
      return [{ type: EffectType.FreeXp, amount: 5 }];
    case RewardType.ControlledTeleport:
      return [{ type: EffectType.ControlledTeleport, radius: 5 }];
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

export function getRegions(state: ApiState) {
  return state.regions;
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

export function getTableau(state: ApiState, player: PlayerEntity): TableauData {
  return { encounters: getPlayerTableau(state, player) };
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
  assertNoPendingWork(state, player);
  if (!action.availability(player))
    throw new RulesViolation("Special action is unavailable");
  if (action.locations?.length && !action.locations.includes(player.location))
    throw new RulesViolation("Special action cannot be performed here");
  if (!canAfford(player, action.cost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(state, player, action.cost);
  const effects = action.execute(state, player);
  applyEffects(state, player, effects);
  player.location = locationForToken(state.hexes, player.tokenId);
  return {
    effects,
    nextActive: nextActiveForPlayer(state, player),
  };
}

export function getGame(state: ApiState) {
  return {
    hexes: state.hexes,
    terrains: terrainSpecs,
    regions: state.regions,
    claims,
    tokens: allTokens(state.tokens),
    players: Array.from(state.players.values()).map(({ id, name }) => ({
      id,
      name,
    })),
    resourceTypes,
  };
}

export function getEntity(state: ApiState, player: PlayerEntity) {
  return playerDto(state.hexes, player);
}

function removeEncounterFromTableau(
  tableau: TableauCard[],
  encounterId: string,
) {
  const index = tableau.findIndex((card) => card.id === encounterId);
  if (index === -1) return false;
  tableau.splice(index, 1);
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
  const tableau = getPlayerTableau(state, player);
  if (currentHex) {
    const speed = computeEffectiveValue(player, SectionType.speed);
    const before = tableau.length;
    const filtered = tableau.filter((card) => {
      const hex = state.hexByName.get(card.location);
      return hex ? hexDistance(currentHex, hex) <= 2 * speed : true;
    });
    if (filtered.length !== before) {
      state.tableau.set(player.id, filtered);
      changed = true;
    }
  }
  const nextTableau = getPlayerTableau(state, player);
  const beforeFill = nextTableau.length;
  fillTableau(nextTableau, encounterTemplates, player, state.rng);
  if (nextTableau.length !== beforeFill) changed = true;
  return changed;
}

export function campEntity(
  state: ApiState,
  player: PlayerEntity,
): ActivityResult {
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  assertNoPendingWork(state, player);
  if (!canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(state, player, turnCost);
  adjustHealth(player, 1);
  player.location = locationForToken(state.hexes, player.tokenId);
  endTurn(state, player, "camp");
  return {
    title: "A Restful Night",
    effects: [{ type: EffectType.Health, amount: 1 }],
    implicitEffects: [{ type: EffectType.Turns, amount: -1 }],
    nextActive: nextActiveForPlayer(state, player),
  };
}

export function travelEntity(
  state: ApiState,
  player: PlayerEntity,
  request: TravelRequest,
): ActivityResult {
  assertNoPendingWork(state, player);
  const route = request.route;
  const current = locationForToken(state.hexes, player.tokenId);
  if (route.length < 1 || route[0] !== current)
    throw new RulesViolation("There are gaps in the route");
  const speed = computeEffectiveValue(player, SectionType.speed);
  if (route.length > speed + 1) throw new RulesViolation("Route is too long");
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

  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  if (!canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(state, player, turnCost);

  const destination = route[route.length - 1];
  const encounterRoute = route.slice(1);
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
    state.currentActivities.set(player.id, {
      type: "encounter",
      encounter: active,
    });

    // If they didn't stop in the last hex, then queue up a selection to
    // let them continue for free
    if (encounterHexName != encounterRoute[encounterRoute.length - 1]) {
      const travelContinueSelection: Selection = {
        id: `selection-travel-continue-${Math.random().toString(36).slice(2)}`,
        title: "Continue Travel",
        description:
          "You may continue the rest of this route without spending an additional turn.",
        choices: [
          {
            description: `Move to hex ${encounterRoute[encounterRoute.length - 1]}`,
            data: encounterHexName,
            index: 0,
          },
          { description: "Stay here", data: "", index: 1 },
        ],
        minChoices: 1,
        maxChoices: 1,
        callback: (indexes) => {
          const choice = travelContinueSelection.choices.find(
            (item: SelectionChoice) => item.index === indexes[0],
          );
          if (!choice || choice.data == "")
            return {
              title: "Travel Done",
              effects: [],
            };
          if (player.location !== choice.data)
            throw new RulesViolation("You can't continue since you've moved.");
          const destination = route[route.length - 1];
          moveToken(state.hexes, state.hexByName, player.tokenId, destination);
          player.location = destination;
          endTurn(state, player, "travel-continuation");
        },
      };
      queuePendingWork(state, player, {
        type: "selection",
        selection: travelContinueSelection,
      });
    }

    return {
      effects: [],
      implicitEffects: [{ type: EffectType.Turns, amount: -1 }],
      nextActive: { type: "encounter", encounter: active },
    };
  }

  moveToken(state.hexes, state.hexByName, player.tokenId, destination);
  player.location = destination;
  endTurn(state, player, "travel-complete");
  return {
    effects: [],
    implicitEffects: [{ type: EffectType.Turns, amount: -1 }],
    nextActive: nextActiveForPlayer(state, player),
  };
}

export function runEncounter(
  state: ApiState,
  player: PlayerEntity,
  request: EncounterRequest,
): ActivityResult {
  const turnCost: Effect[] = [{ type: EffectType.Turns, amount: 1 }];
  assertNoPendingWork(state, player);
  if (!canAfford(player, turnCost))
    throw new RulesViolation("You can't afford to perform this action.");
  payCost(state, player, turnCost);
  const tableau = getPlayerTableau(state, player);
  const encounter = tableau.find((card) => card.id === request.encounterId);
  if (!encounter) throw new RulesViolation("Encounter not found");
  const active = activeEncounterFor(player, encounter, state.rng);
  state.currentActivities.set(player.id, {
    type: "encounter",
    encounter: active,
  });
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
  const curActivity = state.currentActivities.get(player.id);
  const active =
    curActivity && curActivity.type == "encounter"
      ? curActivity.encounter
      : undefined;
  if (!active || active.id !== request.encounterId)
    throw new RulesViolation("No active encounter to continue");
  if (active.state !== "active" && active.state !== "succeeded")
    throw new RulesViolation("Encounter cannot be continued");
  const tableau = getPlayerTableau(state, player);
  const encounter = active.tableauId
    ? tableau.find((card) => card.id === request.encounterId)
    : undefined;
  if (active.tableauId && !encounter)
    throw new RulesViolation("Encounter not found");
  if (active.nextPenalty) {
    active.penalties = [...active.penalties, active.nextPenalty];
    active.nextPenalty = undefined;
  }
  const nextSkillTemplates = rollEncounterSkillChecks(
    active.skillSource,
    active.difficulty,
    state.rng,
  );
  const nextSkillChecks = rollSkillChecks(
    player,
    nextSkillTemplates,
    state.rng,
  );
  console.log(
    `[continueEncounter] ${player.name} ${active.id} new checks: ${nextSkillChecks
      .map(
        (check) =>
          `${check.name} vs ${check.target} (roll ${check.roll} + ${check.modifier} = ${check.total})`,
      )
      .join("; ")}`,
  );
  active.skillChecks.push(...nextSkillChecks);
  active.currentSkillChecks = nextSkillChecks;
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
  const curActivity = state.currentActivities.get(player.id);
  const active =
    curActivity && curActivity.type == "encounter"
      ? curActivity.encounter
      : undefined;
  const encounterId = request.tableauId ?? request.encounterId;
  if (!active || active.id !== request.encounterId)
    throw new RulesViolation("No active encounter to finish");
  const tableau = getPlayerTableau(state, player);
  const encounter = active.tableauId
    ? tableau.find((card) => card.id === request.encounterId)
    : undefined;
  if (active.tableauId && !encounter)
    throw new RulesViolation("Encounter not found");
  if (request.conceding) {
    active.state = "lost";
    active.nextPenalty = undefined;
  }
  const effects = resolveEncounterEffects(
    state,
    player,
    active,
    state.rng,
    request.conceding,
  );
  state.currentActivities.delete(player.id);
  if (encounter) {
    removeEncounterFromTableau(tableau, encounterId);
    endTurn(state, player, "finish-encounter");
  }
  return {
    effects,
    nextActive: nextActiveForPlayer(state, player),
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
