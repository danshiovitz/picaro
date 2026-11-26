import {
  ActivityNextActive,
  ActiveEncounter,
  Notification,
  ActiveEncounterSkillCheck,
  ApiState,
  AnnotatedValue,
  Condition,
  Effect,
  EffectType,
  EncounterTemplate,
  Hex,
  Item,
  PenaltyType,
  PendingActivity,
  PlayerEntity,
  PlayerEntityDto,
  RewardType,
  Selection,
  SelectionChoice,
  AvailableSpecialAction,
  SpecialAction,
  SpecialActionDefinition,
  SpecialActionRequest,
  SpecialActionType,
  TableauCard,
  TableauData,
  CityEntity,
  Entity,
  HexEntity,
  Token,
  GameData,
  ValueType,
  FunctionType,
  TriggerType,
} from "./types.js";
import { createEntity, getField, serializeEntity, setField } from "./entity.js";
import { randomUUID } from "node:crypto";

import { hexDistance } from "@common/hexmap.js";
import {
  terrainSpecs,
  claims,
  encounterTemplates,
  resourceTypes,
  elementTypes,
  skillNames,
  terrainEncounterTemplates,
  specialActions,
  getApiState,
  invoke,
  registerFunction,
  moveToken,
} from "./data.js";
import {
  instantiateEncounterTemplate,
  rollEncounterSkillChecks,
} from "./encounter.js";
import {
  computeAnnotatedEffectiveValue,
  computeEffectiveValue,
  evalTriggers,
} from "./rule.js";
import { getRng } from "@common/random.js";
import { selectionDto } from "./selection.js";

const TABLEAU_LENGTH: number = 3;

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

function specialActionBase(action: SpecialActionDefinition) {
  const { availability: _availability, ...rest } = action;
  return rest;
}

function nearbyEntitiesForPlayer(player: PlayerEntity) {
  const state = getApiState();
  const location = getField(player, "location");
  return (state.hexTokens.get(location) ?? [])
    .filter((entId) => entId !== player.id)
    .map((entId) => state.entities.getById<Entity>(entId))
    .filter((entity): entity is Entity => Boolean(entity));
}

export function addPlayer(
  location: string,
  initialData: Record<string, unknown>,
) {
  const state = getApiState();

  initialData.location = location;
  let player = createEntity<PlayerEntity>("player", initialData);
  state.entities.add(player);

  const playerTableau: TableauCard[] = [];
  fillTableau(playerTableau, encounterTemplates, player);
  state.tableau.set(player.id, playerTableau);

  moveToken(player.id, "", location);
}

function getPlayerTableau(player: PlayerEntity) {
  const state = getApiState();
  const tableau = state.tableau.get(player.id);
  if (!tableau) throw new RulesViolation("Tableau not found");
  return tableau;
}

function assertNoActivities(player: PlayerEntity) {
  const state = getApiState();
  shiftActivityIfNeeded(player, state);
  if (state.curActivity.has(player.id)) {
    throw new RulesViolation("You must finish pending items first.");
  }
}

function shiftActivityIfNeeded(player: PlayerEntity, state: ApiState) {
  // nothing to do if there's already an active activity
  if (state.curActivity.has(player.id)) {
    return;
  }
  let queue = state.activitiesQueue.get(player.id);
  if (queue && queue.length > 0) {
    let cur = queue.shift()!;
    // TODO apply effects
    state.curActivity.set(player.id, cur);

    if (cur.type === "placeholder") {
      handlePlaceholder(player, cur.value);
      state.curActivity.delete(player.id);
      // then go on to the next one
      shiftActivityIfNeeded(player, state);
    }
  } else {
    return; // no pending either
  }
}

function handlePlaceholder(player: PlayerEntity, placeholderType: string) {
  if (placeholderType === "endturn") {
    endTurn(player);
  } else {
    throw new RulesViolation("Unknown placeholder: " + placeholderType);
  }
}

function dbgact(activity: PendingActivity) {
  return (
    "[" +
    activity.type +
    "/" +
    (activity.phase ?? 0) +
    (activity.type === "notification"
      ? "/" + activity.notification.title
      : "") +
    "]"
  );
}
export function queueActivity(
  player: PlayerEntity,
  activity: PendingActivity,
  phaseMod: number,
) {
  const state = getApiState();
  shiftActivityIfNeeded(player, state);

  let cur = state.curActivity.get(player.id);
  activity.phase = (cur?.phase ?? 0) + phaseMod;
  let queue = state.activitiesQueue.get(player.id);
  if (!queue || queue.length == 0) {
    queue = [activity];
    state.activitiesQueue.set(player.id, queue);
    console.log("queue single activity", dbgact(activity));
  } else {
    const index = queue.findLastIndex(
      (existing) => (existing.phase ?? 0) <= (activity.phase ?? 0),
    );
    if (index === -1) queue.unshift(activity);
    else queue.splice(index + 1, 0, activity);
    console.log("queue now", queue.map((a) => dbgact(a)).join(", "));
  }
}

export function makeNotification(
  title: string,
  flavorText?: string,
): Notification {
  return {
    id: `notification-${randomUUID()}`,
    title,
    flavorText,
    effects: [],
    implicitEffects: [],
  };
}

export function viewNextActivityForClient(
  player: PlayerEntity,
): ActivityNextActive | undefined {
  const state = getApiState();
  shiftActivityIfNeeded(player, state);

  let cur = state.curActivity.get(player.id);
  if (!cur) {
    return undefined;
  }
  switch (cur.type) {
    case "selection":
      return { type: "selection", selection: selectionDto(cur.selection) };
    case "encounter":
    case "notification":
      return cur;
  }
}

export function clearCurrentActivity(player: PlayerEntity) {
  const state = getApiState();
  state.curActivity.delete(player.id);
}

export function fetchNextActivityExpectingSelection(
  player: PlayerEntity,
  selectionId: string,
): Selection | undefined {
  const state = getApiState();
  shiftActivityIfNeeded(player, state);

  let cur = state.curActivity.get(player.id);
  if (!cur || cur.type !== "selection" || cur.selection.id !== selectionId) {
    return undefined;
  }
  return cur.selection;
}

export function fetchNextActivityExpectingEncounter(
  player: PlayerEntity,
  encounterId: string,
): ActiveEncounter | undefined {
  const state = getApiState();
  shiftActivityIfNeeded(player, state);

  let cur = state.curActivity.get(player.id);
  if (!cur || cur.type !== "encounter" || cur.encounter.id !== encounterId) {
    return undefined;
  }
  return cur.encounter;
}

function fetchNextActivityExpectingNotification(
  player: PlayerEntity,
  notificationId: string,
): Notification | undefined {
  const state = getApiState();
  shiftActivityIfNeeded(player, state);

  let cur = state.curActivity.get(player.id);
  if (
    !cur ||
    cur.type !== "notification" ||
    cur.notification.id !== notificationId
  ) {
    return undefined;
  }
  return cur.notification;
}

export function ackNotification(
  player: PlayerEntity,
  notificationId: string,
): void {
  const notification = fetchNextActivityExpectingNotification(
    player,
    notificationId,
  );
  if (!notification) throw new RulesViolation("Notification not found");
  clearCurrentActivity(player);
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

function randomPenalty(card: TableauCard) {
  return card.penalties.length > 0 ? getRng().pick(card.penalties) : undefined;
}

function rollSkillChecks(
  player: PlayerEntity,
  checks: { name: string; target: number }[],
) {
  return checks.map((check): ActiveEncounterSkillCheck => {
    const roll = getRng().d10();
    const modifier = computeAnnotatedEffectiveValue(
      player,
      ValueType.skill,
      check.name,
    );
    const total = roll + modifier.finalValue;
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
): ActiveEncounter {
  const skillChecks = rollSkillChecks(player, card.skillChecks);
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
    element: card.element,
    state,
    successThreshold: card.successThreshold,
    criticalThreshold: card.criticalThreshold,
    failureThreshold: card.failureThreshold,
    difficulty: card.difficulty,
    qualityMod: card.qualityMod,
    numSuccesses,
    numFailures,
    nextPenalty:
      state === "active" || state === "succeeded"
        ? randomPenalty(card)
        : undefined,
    rewards: card.rewards,
    criticalRewards: card.criticalRewards,
    penalties: card.penalties,
    skillChecks,
    skillSource: [...card.skillSource],
    currentSkillChecks: skillChecks,
    implicitEffects: [],
  };
}

function cloneInventory(inventory: Item[]) {
  return inventory.map((item) => serializeEntity(item) as Item);
}

function cloneConditions(conditions: Condition[]) {
  return conditions.map((condition) => serializeEntity(condition) as Condition);
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

function randomResourceType() {
  return getRng().pick(resourceTypes);
}

function effectiveSkills(player: PlayerEntity) {
  return Object.fromEntries(
    skillNames.map(
      (skill) =>
        [
          skill,
          computeAnnotatedEffectiveValue(player, ValueType.skill, skill),
        ] as const,
    ),
  );
}

type PlayerDto = PlayerEntityDto;

function playerDto(hexes: Hex[], player: PlayerEntity) {
  return {
    ...(serializeEntity(player) as PlayerEntity),
    skill_xp: cloneSkillXp(getField(player, "skill_xp")),
    maxHealth: computeAnnotatedEffectiveValue(player, ValueType.maxHealth),
    maxLuck: computeAnnotatedEffectiveValue(player, ValueType.maxLuck),
    speed: computeAnnotatedEffectiveValue(player, ValueType.speed),
    skills: effectiveSkills(player),
    resources: cloneResources(getField(player, "resources")),
    inventory: cloneInventory(player.inventory as Item[]),
    conditions: cloneConditions(player.conditions as Condition[]),
  } satisfies PlayerDto;
}

function playerUpdates(player: PlayerEntity) {
  return {
    curHealth: getField(player, "curHealth"),
    curLuck: getField(player, "curLuck"),
    gold: getField(player, "gold"),
    reputation: getField(player, "reputation"),
    turns: getField(player, "turns"),
    maxHealth: computeAnnotatedEffectiveValue(player, ValueType.maxHealth),
    maxLuck: computeAnnotatedEffectiveValue(player, ValueType.maxLuck),
    speed: computeAnnotatedEffectiveValue(player, ValueType.speed),
    location: getField(player, "location"),
    skill_xp: cloneSkillXp(getField(player, "skill_xp")),
    skills: effectiveSkills(player),
    resources: cloneResources(getField(player, "resources")),
    inventory: cloneInventory(player.inventory as Item[]),
    conditions: cloneConditions(player.conditions as Condition[]),
  } satisfies Partial<PlayerEntityDto>;
}

const skillXpThresholds = [0, 10, 30, 50, 75, 100, 130];

function skillLevelFromXp(xp: number) {
  let level = 0;
  for (let i = 0; i < skillXpThresholds.length; i++) {
    if (xp >= skillXpThresholds[i]) level = i;
  }
  return level;
}

function computeEncounterEffects(
  player: PlayerEntity,
  active: ActiveEncounter,
) {
  const effects: Effect[] = [];
  const meetsFailureThreshold = active.numFailures >= active.failureThreshold;
  const clamp = (val: number, min: number, max: number) =>
    Math.min(Math.max(val, min), max);
  const quality = clamp(active.difficulty + active.qualityMod, 0, 8);
  if (
    !meetsFailureThreshold &&
    active.numSuccesses >= active.successThreshold
  ) {
    for (const reward of active.rewards)
      effects.push(...computeReward(reward, quality));
    if (
      typeof active.criticalThreshold === "number" &&
      active.numSuccesses >= active.criticalThreshold
    ) {
      for (const reward of active.criticalRewards)
        effects.push(...computeCriticalReward(reward, quality));
    }
  }
  for (const penalty of active.penalties)
    effects.push(...computePenalty(penalty, active.numFailures, player));

  const failedChecks = active.skillChecks.filter((check) => !check.success);
  const succeededChecks = active.skillChecks.filter((check) => check.success);
  const selectedFailedChecks =
    failedChecks.length >= 3
      ? failedChecks.length === 3
        ? failedChecks
        : getRng().shuffle(failedChecks).slice(0, 3)
      : failedChecks;
  const selectedSucceededChecks =
    failedChecks.length >= 3
      ? []
      : getRng()
          .shuffle(succeededChecks)
          .slice(0, 3 - failedChecks.length);

  const xpEffects: Effect[] = [];
  for (const check of [...selectedFailedChecks, ...selectedSucceededChecks]) {
    const amount = check.success ? 1 : 2;
    xpEffects.push({ type: EffectType.SkillXp, skill: check.name, amount });
  }
  effects.push(...xpEffects);
  return effects;
}

function annotatedAmount(value: number, text: string): AnnotatedValue {
  return {
    finalValue: value,
    baseValue: { value, text },
    modifierValues: [],
  };
}

function adjustGold(player: PlayerEntity, amount: number) {
  const annotated = annotatedAmount(amount, "gold change");
  setField(player, "gold", Math.max(0, getField(player, "gold") + amount));
  return annotated;
}

function adjustReputation(player: PlayerEntity, amount: number) {
  const annotated = annotatedAmount(amount, "reputation change");
  setField(
    player,
    "reputation",
    Math.max(0, getField(player, "reputation") + amount),
  );
  return annotated;
}

function adjustHealth(player: PlayerEntity, amount: number) {
  const maxHealth = computeEffectiveValue(player, ValueType.maxHealth);
  const valueType = amount < 0 ? ValueType.healthLoss : ValueType.healthGain;
  const annotated = computeAnnotatedEffectiveValue(
    player,
    valueType,
    undefined,
    amount,
  );
  const adjustedAmount =
    amount < 0
      ? Math.min(0, annotated.finalValue)
      : Math.max(0, annotated.finalValue);
  setField(
    player,
    "curHealth",
    Math.max(
      0,
      Math.min(maxHealth, getField(player, "curHealth") + adjustedAmount),
    ),
  );
  annotated.finalValue = adjustedAmount;
  return annotated;
}

function adjustResource(
  player: PlayerEntity,
  resourceType: string,
  amount: number,
) {
  const annotated = annotatedAmount(amount, `${resourceType} change`);
  const current = getField(player, "resources")[resourceType] ?? 0;
  getField(player, "resources")[resourceType] = Math.max(0, current + amount);
  return annotated;
}

function removeItems(player: PlayerEntity, itemIds: string[]) {
  const state = getApiState();
  const ids = new Set(itemIds);
  const inventory = player.inventory as Item[];
  for (const item of inventory) {
    if (ids.has(item.id) && getField(item, "is_artifact")) {
      if (!state.lostItems.some((lostItem) => lostItem.id === item.id)) {
        state.lostItems.push(item);
      }
    }
  }
  setField(
    player,
    "inventory",
    inventory.filter((item) => !ids.has(item.id)),
  );
}

function adjustTurns(player: PlayerEntity, amount: number) {
  setField(player, "turns", Math.max(0, getField(player, "turns") + amount));
}

function adjustLuck(player: PlayerEntity, amount: number) {
  const annotated = annotatedAmount(amount, "luck change");
  setField(
    player,
    "curLuck",
    Math.max(
      0,
      Math.min(
        getField(player, "maxLuck"),
        getField(player, "curLuck") + amount,
      ),
    ),
  );
  return annotated;
}

const randomItemTable = [
  "magic sword",
  "magic shield",
  "fast horse",
  "ring of invisibility",
];

function gainRandomItem(player: PlayerEntity, quality: number) {
  const state = getApiState();
  const shouldRecoverLostItem =
    state.lostItems.length > 0 && getRng().int(4) === 0;
  if (shouldRecoverLostItem) {
    const index = getRng().int(state.lostItems.length);
    const [item] = state.lostItems.splice(index, 1);
    if (item) {
      (player.inventory as Item[]).push(item);
      return item;
    }
  }
  if (randomItemTable.length === 0) return undefined;
  const roll = Math.min(
    randomItemTable.length,
    Math.max(1, getRng().int(randomItemTable.length) + 1 + quality),
  );
  const itemName = randomItemTable[roll - 1];
  const item = createEntity<Item>("item", { name: itemName });
  state.entities.add(item);
  (player.inventory as Item[]).push(item);
  return item;
}

function removeRandomItem(player: PlayerEntity) {
  const inventory = player.inventory as Item[];
  if (inventory.length === 0) return undefined;
  const index = getRng().int(inventory.length);
  const [item] = inventory.splice(index, 1);
  return item;
}

function canAfford(player: PlayerEntity, cost: Effect[]) {
  for (const effect of cost) {
    switch (effect.type) {
      case EffectType.FreeXp:
      case EffectType.GainRandomItem:
        throw new RulesViolation("This effect cannot be used as a cost.");
      case EffectType.Gold:
        if (getField(player, "gold") + effect.amount < 0) return false;
        break;
      case EffectType.Reputation:
        if (getField(player, "reputation") + effect.amount < 0) return false;
        break;
      case EffectType.Health:
        if (getField(player, "curHealth") + effect.amount < 0) return false;
        break;
      case EffectType.Turns:
        if (getField(player, "turns") + effect.amount < 0) return false;
        break;
      case EffectType.Luck:
        if (getField(player, "curLuck") + effect.amount < 0) return false;
        break;
      case EffectType.Resource:
        if (
          (getField(player, "resources")[effect.resourceType] ?? 0) +
            effect.amount <
          0
        )
          return false;
        break;
      case EffectType.SkillXp:
        if (
          (getField(player, "skill_xp")[effect.skill] ?? 0) + effect.amount <
          0
        )
          return false;
        break;
      case EffectType.RemoveItems: {
        const inventoryIds = new Set(
          (player.inventory as Item[]).map((item) => item.id),
        );
        if (!effect.itemIds.every((itemId) => inventoryIds.has(itemId)))
          return false;
        break;
      }
      case EffectType.RemoveRandomItem:
        if ((player.inventory as Item[]).length < 1) return false;
        break;
      case EffectType.AddTableauCard:
      case EffectType.RefreshTableau:
      case EffectType.ControlledTeleport:
      case EffectType.Teleport:
        return true;
    }
  }
  return true;
}

function adjustSkillXp(player: PlayerEntity, skill: string, amount: number) {
  const current = getField(player, "skill_xp")[skill] ?? 0;
  getField(player, "skill_xp")[skill] = Math.max(0, current + amount);
}

export function applyEffects(
  player: PlayerEntity,
  effects: Effect[],
  maybeNotif: Notification | undefined,
  implicitEffects: Effect[] = [],
  phaseMod: number = 0,
) {
  const frontQueue: PendingActivity[] = [];
  for (const effect of effects.concat(implicitEffects)) {
    switch (effect.type) {
      case EffectType.FreeXp:
        frontQueue.push({
          type: "selection",
          selection: freeXpSelection(effect.amount),
        });
        break;
      case EffectType.ControlledTeleport:
        frontQueue.push({
          type: "selection",
          selection: controlledTeleportSelection(player, effect.radius),
        });
        break;
      case EffectType.Teleport:
        let dest = effect.centerHex;
        if (effect.radius > 0) {
          const center = getApiState().hexByName.get(dest)!;
          const dests = getApiState().hexes.filter(
            (hex) => hexDistance(center, hex) <= effect.radius,
          );
          dest = getRng().pick(dests).name;
        }
        effect.centerHex = dest; // reuse center to log the name of the dest hex
        effect.radius = -1; // spoil the radius since we're overwriting the center
        moveToken(player.id, player.location, dest);
        break;
      case EffectType.Gold:
        effect.annotatedValue = adjustGold(player, effect.amount);
        break;
      case EffectType.Reputation:
        effect.annotatedValue = adjustReputation(player, effect.amount);
        break;
      case EffectType.Health:
        effect.annotatedValue = adjustHealth(player, effect.amount);
        break;
      case EffectType.Turns:
        adjustTurns(player, effect.amount);
        break;
      case EffectType.Luck:
        effect.annotatedValue = adjustLuck(player, effect.amount);
        break;
      case EffectType.Resource:
        effect.annotatedValue = adjustResource(
          player,
          effect.resourceType,
          effect.amount,
        );
        break;
      case EffectType.SkillXp:
        const currentXp = getField(player, "skill_xp")[effect.skill] ?? 0;
        const currentLevel = skillLevelFromXp(currentXp);
        adjustSkillXp(player, effect.skill, effect.amount);
        const nextXp = getField(player, "skill_xp")[effect.skill] ?? 0;
        const nextLevel = skillLevelFromXp(nextXp);
        if (nextLevel != currentLevel) {
          effect.newLevel = nextLevel;
        }
        break;
      case EffectType.RemoveItems:
        removeItems(player, effect.itemIds);
        break;
      case EffectType.GainRandomItem: {
        const item = gainRandomItem(player, effect.quality);
        if (item) effect.itemId = item.id;
        break;
      }
      case EffectType.RemoveRandomItem: {
        const item = removeRandomItem(player);
        if (item) effect.itemId = item.id;
        break;
      }
      case EffectType.AddTableauCard: {
        const tableau = getPlayerTableau(player);
        const template =
          effect.encounterTemplate ?? getRng().pick(encounterTemplates);
        tableau.push(
          instantiateEncounterTemplate(template, player, effect.qualityMod),
        );
        break;
      }
      case EffectType.RefreshTableau: {
        const tableau = getPlayerTableau(player);
        tableau.splice(0, tableau.length);
        let qmOverrides: (number | undefined)[] = effect.qualityMods ?? [];
        while (qmOverrides.length < TABLEAU_LENGTH) {
          qmOverrides.push(undefined);
        }
        qmOverrides = getRng().shuffle(qmOverrides);
        fillTableau(tableau, encounterTemplates, player, qmOverrides);
        break;
      }
    }
  }

  if (maybeNotif && (effects.length > 0 || implicitEffects.length > 0)) {
    maybeNotif.effects = effects;
    maybeNotif.implicitEffects = implicitEffects;
    frontQueue.unshift({
      type: "notification",
      notification: maybeNotif,
    });
  }

  for (const aty of frontQueue) {
    queueActivity(player, aty, phaseMod);
  }
}

type ControlledTeleportSelectionData = { radius: number };
type FreeXpSelectionData = { amount: number };
type TravelContinueSelectionData = {
  destination: string;
  encounterHexName: string;
};

export function controlledTeleportSelectionCallback(
  selection: Selection,
  player: PlayerEntity,
  choices: SelectionChoice[],
): void {
  const data = selection.callbackData as
    ControlledTeleportSelectionData | undefined;
  const radius = data?.radius ?? 0;
  const state = getApiState();
  if (choices.length != 1) {
    queueActivity(
      player,
      {
        type: "notification",
        notification: makeNotification(
          "Controlled Teleport",
          "No selection made.",
        ),
      },
      0,
    );
    return;
  }

  const choice = choices[0];
  const origin = state.hexByName.get(getField(player, "location"));
  if (!origin) throw new RulesViolation("Origin hex not found");
  const target = state.hexByName.get(choice.data);
  if (!target) throw new RulesViolation("Selected hex not found");
  if (hexDistance(origin, target) > radius) {
    throw new RulesViolation("Selected hex is out of range");
  }
  applyEffects(
    player,
    [{ type: EffectType.Teleport, radius: 0, centerHex: target.name }],
    makeNotification("Controlled Teleport"),
  );
}

export function freeXpSelectionCallback(
  selection: Selection,
  player: PlayerEntity,
  choices: SelectionChoice[],
): void {
  const data = selection.callbackData as FreeXpSelectionData | undefined;
  const amount = data?.amount ?? 0;
  if (choices.length != 1) {
    queueActivity(
      player,
      {
        type: "notification",
        notification: makeNotification("Free XP", "No selection made."),
      },
      0,
    );
    return;
  }
  const choice = choices[0];
  const effects: Effect[] = [
    { type: EffectType.SkillXp, skill: choice.data, amount },
  ];
  applyEffects(player, effects, makeNotification("Free XP"));
}

function queueEndTurn(player: PlayerEntity) {
  queueActivity(player, { type: "placeholder", value: "endturn" }, 2);
}

export function travelContinueSelectionCallback(
  selection: Selection,
  player: PlayerEntity,
  choices: SelectionChoice[],
): void {
  const data = selection.callbackData as
    TravelContinueSelectionData | undefined;
  let notification: Notification;
  if (choices.length != 1 || choices[0].data == "") {
    queueActivity(
      player,
      {
        type: "notification",
        notification: makeNotification(
          "Travel Done",
          "You remain in the current hex.",
        ),
      },
      0,
    );
    queueEndTurn(player);
    return;
  }

  const choice = choices[0];
  if (!data) throw new RulesViolation("Selection data missing");
  if (getField(player, "location") !== data.encounterHexName)
    throw new RulesViolation("You can't continue since you've moved.");
  applyEffects(
    player,
    [{ type: EffectType.Teleport, radius: 0, centerHex: data.destination }],
    makeNotification(
      "Continue Travel",
      "You complete your travel uneventfully.",
    ),
  );
  queueEndTurn(player);
}

function controlledTeleportSelection(
  player: PlayerEntity,
  radius: number,
): Selection {
  const state = getApiState();
  const originHex = state.hexByName.get(getField(player, "location"));
  if (!originHex) throw new RulesViolation("Origin hex not found");
  const selection: Selection = {
    id: `selection-controlled-teleport-${Math.random().toString(36).slice(2)}`,
    title: "Controlled Teleport",
    description: `Choose a hex within ${radius} hexes of ${getField(player, "location")}.`,
    choices: state.hexes
      .filter((hex) => hexDistance(originHex, hex) <= radius)
      .map((hex, index) => ({
        description: hex.name,
        data: hex.name,
        index,
      })),
    minChoices: 1,
    maxChoices: 1,
    useDropdown: true,
    hexSelection: { originHex: getField(player, "location"), radius },
    callback: "selection-controlled-teleport",
    callbackData: { radius },
    implicitEffects: [],
  };
  return selection;
}

function freeXpSelection(amount: number): Selection {
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
    callback: "selection-free-xp",
    callbackData: { amount },
    implicitEffects: [],
  };
  return selection;
}

function travelContinueSelection(
  currentHex: string,
  destinationHex: string,
): Selection {
  const selection: Selection = {
    id: `selection-travel-continue-${Math.random().toString(36).slice(2)}`,
    title: "Continue Travel",
    description:
      "You may continue the rest of this route without spending an additional turn.",
    choices: [
      {
        description: `Move to hex ${destinationHex}`,
        data: destinationHex,
        index: 0,
      },
      { description: "Stay here", data: "", index: 1 },
    ],
    minChoices: 1,
    maxChoices: 1,
    callback: "selection-travel-continue",
    callbackData: {
      destination: destinationHex,
      encounterHexName: currentHex,
    },
    implicitEffects: [],
  };
  return selection;
}

export function initSystemFunctions() {
  registerFunction(
    "selection-controlled-teleport",
    FunctionType.SelectionCallback,
    controlledTeleportSelectionCallback,
  );
  registerFunction(
    "selection-free-xp",
    FunctionType.SelectionCallback,
    freeXpSelectionCallback,
  );
  registerFunction(
    "selection-travel-continue",
    FunctionType.SelectionCallback,
    travelContinueSelectionCallback,
  );
}

function computeReward(rewardType: RewardType, quality: number): Effect[] {
  switch (rewardType) {
    case RewardType.Gold:
      return [{ type: EffectType.Gold, amount: 2 + Math.floor(quality / 2) }];
    case RewardType.Reputation:
      return [
        { type: EffectType.Reputation, amount: 1 + Math.floor(quality / 4) },
      ];
    case RewardType.Luck:
      return [{ type: EffectType.Luck, amount: 1 + Math.floor(quality / 4) }];
    case RewardType.Resource:
      return [
        resourceEffect(randomResourceType(), 1 + Math.floor(quality / 3)),
      ];
    case RewardType.FreeXp:
      return [{ type: EffectType.FreeXp, amount: 5 + Math.floor(quality / 3) }];
    case RewardType.ControlledTeleport:
      return [
        {
          type: EffectType.ControlledTeleport,
          radius: 5 + Math.floor(quality / 3),
        },
      ];
    case RewardType.GainItem:
      return [
        {
          type: EffectType.GainRandomItem,
          quality: 1 + Math.floor(quality / 3),
        },
      ];
    case RewardType.QualityEncounter:
      return [
        {
          type: EffectType.AddTableauCard,
          encounterTemplate: undefined, // will do a regular job card
          qualityMod: 3,
        },
      ];
  }
}

function computeCriticalReward(
  rewardType: RewardType,
  quality: number,
): Effect[] {
  return computeReward(rewardType, quality + 1);
}

function computePenalty(
  penaltyType: PenaltyType,
  numFailures: number,
  player: PlayerEntity,
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
      const pool = Object.entries(getField(player, "resources")).flatMap(
        ([resourceType, amount]) =>
          Array.from({ length: Math.max(0, amount) }, () => resourceType),
      );
      if (pool.length === 0) return [];
      const remaining = new Map(Object.entries(getField(player, "resources")));
      const removed = new Map<string, number>();
      let available = pool.length;
      const chooseResource = () => {
        let pick = getRng().int(available);
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
    case PenaltyType.RemoveItem:
      return [{ type: EffectType.RemoveRandomItem }];
    case PenaltyType.RandomTeleport:
      if (numFailures == 0) {
        return [];
      }
      return [
        {
          type: EffectType.Teleport,
          centerHex: getField(player, "location"),
          radius: numFailures * 2,
        },
      ];
  }
}

export function getHexes() {
  const state = getApiState();
  return state.hexes;
}

export function getTerrain() {
  return terrainSpecs;
}

export function getRegions() {
  const state = getApiState();
  return state.regions;
}

export function getClaims() {
  return claims;
}

export function getItem(itemId: string) {
  const state = getApiState();
  return state.entities.getById<Item>(itemId);
}

export function getTableau(player: PlayerEntity): TableauData {
  const state = getApiState();
  return { encounters: getPlayerTableau(player) };
}

export function getSpecialActions(
  player: PlayerEntity,
): AvailableSpecialAction[] {
  const state = getApiState();
  const available: AvailableSpecialAction[] = [];
  for (const action of specialActions) {
    if (action.type === SpecialActionType.General) {
      if (
        invoke<boolean>(
          action.availability,
          FunctionType.SpecialActionAvailability,
          [player],
        )
      ) {
        available.push(specialActionBase(action));
      }
      continue;
    }
    if (action.type === SpecialActionType.Item) {
      for (const item of player.inventory as Item[]) {
        if (
          invoke<boolean>(
            action.availability,
            FunctionType.SpecialActionAvailability,
            [player, item],
          )
        ) {
          available.push({ ...specialActionBase(action), entityId: item.id });
        }
      }
      continue;
    }
    if (action.type === SpecialActionType.NearbyEntity) {
      for (const entity of nearbyEntitiesForPlayer(player)) {
        if (
          invoke<boolean>(
            action.availability,
            FunctionType.SpecialActionAvailability,
            [player, entity],
          )
        ) {
          available.push({ ...specialActionBase(action), entityId: entity.id });
        }
      }
    }
  }
  return available;
}

export function performSpecialAction(
  player: PlayerEntity,
  request: SpecialActionRequest,
): void {
  const state = getApiState();
  const action = specialActions.find(
    (item) => item.id === request.specialActionId,
  );
  if (!action) throw new RulesViolation("Special action not found");
  assertNoActivities(player);
  let target: Item | Entity | undefined;
  let params: unknown[] = [player];
  switch (action.type) {
    case SpecialActionType.General:
      break;
    case SpecialActionType.Item: {
      target = (player.inventory as Item[]).find(
        (item) => item.id === request.entityId,
      );
      if (!target) throw new RulesViolation("Special action item not found");
      params = [player, target];
      break;
    }
    case SpecialActionType.NearbyEntity: {
      target = nearbyEntitiesForPlayer(player).find(
        (entity) => entity.id === request.entityId,
      );
      if (!target) throw new RulesViolation("Special action entity not found");
      params = [player, target];
      break;
    }
  }
  if (
    !invoke<boolean>(
      action.availability,
      FunctionType.SpecialActionAvailability,
      params,
    )
  )
    throw new RulesViolation("Special action is unavailable");
  if (
    action.locations?.length &&
    !action.locations.includes(getField(player, "location"))
  )
    throw new RulesViolation("Special action cannot be performed here");
  if (!canAfford(player, action.cost))
    throw new RulesViolation("You can't afford to perform this action.");
  const effects = invoke<Effect[]>(
    action.execute,
    FunctionType.SpecialActionExecute,
    params,
  );
  applyEffects(player, effects, makeNotification(action.name), action.cost);
}

export function getGame() {
  const state = getApiState();
  const ret: GameData = {
    hexes: state.hexes,
    terrains: terrainSpecs,
    regions: state.regions,
    claims,
    entities: state.entities.values().map(serializeEntity),
    resourceTypes,
    elementTypes,
  };
  return ret;
}

export function getEntity(player: PlayerEntity) {
  const state = getApiState();
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

function endTurn(player: PlayerEntity) {
  const state = getApiState();
  console.log(
    `[endTurn] for ${getField(player, "name")} @ ${getField(player, "location")}`,
  );
  for (const condition of player.conditions as Condition[])
    setField(condition, "duration", getField(condition, "duration") - 1);
  setField(
    player,
    "conditions",
    (player.conditions as Condition[]).filter(
      (condition) => getField(condition, "duration") > 0,
    ),
  );
  const currentHex = state.hexByName.get(getField(player, "location"));
  let changed = false;
  const tableau = getPlayerTableau(player);
  if (currentHex) {
    const speed = computeEffectiveValue(player, ValueType.speed);
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
  const nextTableau = getPlayerTableau(player);
  const beforeFill = nextTableau.length;
  fillTableau(nextTableau, encounterTemplates, player);
  if (nextTableau.length !== beforeFill) changed = true;
  evalTriggers(TriggerType.EndOfTurn, player);
  return changed;
}

export function scoutEntity(player: PlayerEntity): void {
  const state = getApiState();
  const cost: Effect[] = [{ type: EffectType.Turns, amount: -1 }];
  assertNoActivities(player);
  if (!canAfford(player, cost))
    throw new RulesViolation("You can't afford to perform this action.");
  // Make one encounter they scout guaranteed higher quality
  let effects: Effect[] = [
    { type: EffectType.RefreshTableau, qualityMods: [+2] },
  ];
  applyEffects(player, effects, makeNotification("Scout Results"), cost);
  queueEndTurn(player);
}

export function campEntity(player: PlayerEntity): void {
  const state = getApiState();
  const cost: Effect[] = [{ type: EffectType.Turns, amount: -1 }];
  assertNoActivities(player);
  if (!canAfford(player, cost))
    throw new RulesViolation("You can't afford to perform this action.");
  let effects: Effect[] = [{ type: EffectType.Health, amount: 1 }];
  applyEffects(player, effects, makeNotification("A Restful Night"), cost);
  queueEndTurn(player);
}

export function travelEntity(
  player: PlayerEntity,
  request: TravelRequest,
): void {
  const state = getApiState();
  assertNoActivities(player);
  const route = request.route;
  const current = getField(player, "location");
  if (route.length < 1 || route[0] !== current)
    throw new RulesViolation("There are gaps in the route");
  const speed = computeEffectiveValue(player, ValueType.speed);
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

  const cost: Effect[] = [{ type: EffectType.Turns, amount: -1 }];
  if (!canAfford(player, cost))
    throw new RulesViolation("You can't afford to perform this action.");

  const destination = route[route.length - 1];
  const encounterRoute = route.slice(1);
  const encounterHexName =
    encounterRoute.length > 0 && getRng().next() < 0.5
      ? getRng().pick(encounterRoute)
      : undefined;
  const encounterHex = encounterHexName
    ? state.hexByName.get(encounterHexName)
    : undefined;
  if (encounterHex) {
    const templates = encounterHex
      ? (terrainEncounterTemplates[encounterHex.terrain] ?? encounterTemplates)
      : encounterTemplates;
    const template = getRng().pick(templates);
    let effects: Effect[] = [];
    let implicitEffects = cost.concat([
      { type: EffectType.Teleport, radius: 0, centerHex: encounterHex.name },
    ]);
    applyEffects(
      player,
      effects,
      makeNotification(
        "Travel Interrupted",
        `You are interrupted at ${encounterHex.name}!`,
      ),
      implicitEffects,
    );

    const encounterCard = instantiateEncounterTemplate(template, player);
    encounterCard.location = encounterHex.name;
    const active = {
      ...activeEncounterFor(player, encounterCard),
      tableauId: undefined,
    };
    queueActivity(
      player,
      {
        type: "encounter",
        encounter: active,
      },
      0,
    );

    // If they didn't stop in the last hex, then queue up a selection to
    // let them continue for free
    if (encounterHex.name != encounterRoute[encounterRoute.length - 1]) {
      const selection = travelContinueSelection(
        encounterHex.name,
        encounterRoute[encounterRoute.length - 1],
      );
      queueActivity(
        player,
        {
          type: "selection",
          selection,
        },
        3,
      );
      // don't call endTurn() here, we'll do it in the continuation selection
      return;
    }
  }

  let effects: Effect[] = [];
  let implicitEffects: Effect[] = cost.concat([
    { type: EffectType.Teleport, radius: 0, centerHex: destination },
  ]);
  applyEffects(
    player,
    effects,
    makeNotification("Travel Complete", `You reach ${destination}.`),
    implicitEffects,
    1,
  );
  queueEndTurn(player);
}

export function runEncounter(
  player: PlayerEntity,
  request: EncounterRequest,
): void {
  const state = getApiState();
  const cost: Effect[] = [{ type: EffectType.Turns, amount: -1 }];
  assertNoActivities(player);
  if (!canAfford(player, cost))
    throw new RulesViolation("You can't afford to perform this action.");
  const tableau = getPlayerTableau(player);
  const encounter = tableau.find((card) => card.id === request.encounterId);
  if (!encounter) throw new RulesViolation("Encounter not found");
  const active = activeEncounterFor(player, encounter);
  active.implicitEffects = cost;
  // apply the cost here
  applyEffects(player, active.implicitEffects, undefined);
  queueActivity(
    player,
    {
      type: "encounter",
      encounter: active,
    },
    0,
  );
}

export function continueEncounter(
  player: PlayerEntity,
  request: EncounterRequest,
): void {
  const active = fetchNextActivityExpectingEncounter(
    player,
    request.encounterId,
  );
  if (!active) throw new RulesViolation("No active encounter to continue");
  if (active.state !== "active" && active.state !== "succeeded")
    throw new RulesViolation("Encounter cannot be continued");
  const tableau = getPlayerTableau(player);
  const tableauEncounter = active.tableauId
    ? tableau.find((card) => card.id === request.encounterId)
    : undefined;
  if (active.tableauId && !tableauEncounter)
    throw new RulesViolation("Encounter not found in tableau");
  if (active.nextPenalty) {
    active.penalties = [...active.penalties, active.nextPenalty];
    active.nextPenalty = undefined;
  }
  const nextSkillTemplates = rollEncounterSkillChecks(
    active.skillSource,
    active.difficulty,
  );
  const nextSkillChecks = rollSkillChecks(player, nextSkillTemplates);
  console.log(
    `[continueEncounter] ${getField(player, "name")} ${active.id} new checks: ${nextSkillChecks
      .map(
        (check) =>
          `${check.name} vs ${check.target} (roll ${check.roll} + ${check.modifier.finalValue} = ${check.total})`,
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
    active.nextPenalty = tableauEncounter
      ? randomPenalty(tableauEncounter)
      : randomPenalty({ penalties: active.penalties } as TableauCard);
  }
}

export function finishEncounter(
  player: PlayerEntity,
  request: EncounterRequest & { conceding?: boolean },
): void {
  const state = getApiState();
  const encounterId = request.tableauId ?? request.encounterId;
  const active = fetchNextActivityExpectingEncounter(player, encounterId);
  if (!active) throw new RulesViolation("Encounter not found");
  const tableau = getPlayerTableau(player);
  const tableauEncounter = active.tableauId
    ? tableau.find((card) => card.id === request.encounterId)
    : undefined;
  if (active.tableauId && !tableauEncounter)
    throw new RulesViolation("Encounter not found in tableau");
  if (request.conceding) {
    active.state = "lost";
    active.nextPenalty = undefined;
  }
  const effects = computeEncounterEffects(player, active);
  applyEffects(player, effects, makeNotification("Encounter Results"));
  clearCurrentActivity(player);
  if (tableauEncounter) {
    removeEncounterFromTableau(tableau, encounterId);
    queueEndTurn(player);
  }
}

export function fillTableau(
  tableau: TableauCard[],
  templates: EncounterTemplate[],
  player: PlayerEntity,
  qualityMods: (number | undefined)[] = [],
) {
  while (tableau.length < TABLEAU_LENGTH && templates.length > 0) {
    const template = getRng().pick(templates);
    const qm =
      tableau.length < qualityMods.length
        ? qualityMods[tableau.length]
        : undefined;
    tableau.push(instantiateEncounterTemplate(template, player, qm));
  }
}
