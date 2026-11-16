import {
  ApiState,
  Claim,
  EffectType,
  EncounterTemplate,
  CityEntity,
  Item,
  PenaltyType,
  PlayerEntity,
  RewardType,
  Rule,
  RuleType,
  Selection,
  SelectionChoice,
  SpecialActionDefinition,
  SpecialActionType,
  ValueRuleType,
  ValueType,
  FunctionType,
  FunctionParamType,
} from "./types.js";
import {
  createEntity,
  EntityStore,
  getField,
  registerEntitySchema,
  setField,
} from "./entity.js";
import { SCHEMAS } from "./schemas.js";
import { computeEffectiveValue } from "./rule.js";
import { appendActivity, RulesViolation } from "./commands.js";

export const terrainSpecs = [
  ["Forest", "#1a531e", "forest"],
  ["Deep Forest", "#14552a", "deep-forest"],
  ["Desert", "#d8b45f", "desert"],
  ["Water", "#3182bd", "water"],
  ["Plains", "#9fca62", "plains"],
  ["Mountain", "#8a8178", "mountain"],
  ["Hills", "#a68b55", "hills"],
  ["Swamp", "#a42d8e", "swamp"],
  ["Tundra", "#81cbe8", "tundra"],
  ["Jungle", "#15de4a", "jungle"],
  ["Badlands", "#b86945", "badlands"],
  ["Marsh", "#6c9272", "marsh"],
  ["Glacier", "#e9f6ff", "glacier"],
  ["Savannah", "#d7ae7f", "savannah"],
].map(([name, color, icon]) => ({ name, color, icon }));

export const terrainByName = new Map(
  terrainSpecs.map((terrain) => [terrain.name, terrain] as const),
);

export const claimColors = [
  "red",
  "yellow",
  "blue",
  "green",
  "purple",
  "orange",
];

export const resourceTypes = [
  "Silk",
  "Jewels",
  "Steel",
  "Bricks",
  "Spices",
  "Wood",
  "Wine",
];
export let claims: Claim[] = claimColors.map((icon, i) => ({
  name: `Faction ${i + 1}`,
  icon,
}));

export const skillNames = [
  "Acrobatics",
  "Animal Training",
  "Appraisal",
  "Architecture",
  "Arctic Lore",
  "Brutal Fighting",
  "Carousing",
  "Charm",
  "Climb",
  "Command",
  "Debate",
  "Desert Lore",
  "Doctor",
  "Dueling",
  "Endurance",
  "Forest Lore",
  "Formation Fighting",
  "Hills Lore",
  "Jungle Lore",
  "Mechanisms",
  "Mesmerism",
  "Might",
  "Mountain Lore",
  "Navigation",
  "Observation",
  "Pickpocket",
  "Plains Lore",
  "Research",
  "Ride",
  "Sea Lore",
  "Shoot",
  "Skill X",
  "Skill Y",
  "Speed",
  "Spirit Binding",
  "Stealth",
  "Swamp Lore",
  "Thaumaturgy",
  "Throw",
];

const terrainLoreSkills: Record<string, string[]> = {
  Forest: ["Forest Lore", "Stealth", "Observation"],
  "Deep Forest": ["Forest Lore", "Stealth", "Observation"],
  Desert: ["Desert Lore", "Endurance", "Navigation"],
  Water: ["Sea Lore", "Navigation", "Observation"],
  Plains: ["Plains Lore", "Ride", "Observation"],
  Mountain: ["Mountain Lore", "Climb", "Endurance"],
  Hills: ["Hills Lore", "Ride", "Observation"],
  Swamp: ["Swamp Lore", "Stealth", "Endurance"],
  Tundra: ["Arctic Lore", "Endurance", "Navigation"],
  Jungle: ["Jungle Lore", "Stealth", "Observation"],
  Badlands: ["Desert Lore", "Throw", "Might"],
  Marsh: ["Swamp Lore", "Stealth", "Observation"],
  Glacier: ["Arctic Lore", "Endurance", "Observation"],
  Savannah: ["Plains Lore", "Ride", "Observation"],
};

export const terrainEncounterTemplates: Record<string, EncounterTemplate[]> =
  Object.fromEntries(
    terrainSpecs.map((terrain) => [
      terrain.name,
      [
        {
          title: `Beast of the ${terrain.name}`,
          difficulty_mod: 2,
          rewards: [RewardType.Gold],
          criticalRewards: [RewardType.Gold],
          penalties: [PenaltyType.Health],
          skills: terrainLoreSkills[terrain.name] ?? [
            "Observation",
            "Speed",
            "Might",
          ],
        },
      ],
    ]),
  );

export const generalRewardTypes = Object.values(RewardType) as RewardType[];
export const generalPenaltyTypes = Object.values(PenaltyType) as PenaltyType[];

export const encounterTemplates: EncounterTemplate[] = [
  {
    title: "Dungeon Raid",
    difficulty_mod: 0,
    rewards: [RewardType.Gold],
    criticalRewards: [RewardType.Gold],
    penalties: [PenaltyType.Health],
    skills: [
      "Stealth",
      "Endurance",
      "Might",
      "Mechanisms",
      "Observation",
      "Acrobatics",
    ],
  },
  {
    title: "Parley",
    difficulty_mod: 2,
    rewards: [RewardType.Gold],
    criticalRewards: [],
    penalties: [PenaltyType.Health],
    skills: [
      "Charm",
      "Debate",
      "Command",
      "Observation",
      "Research",
      "Mesmerism",
    ],
  },
  {
    title: "Wandering Sage",
    difficulty_mod: 1,
    rewards: [RewardType.Gold],
    criticalRewards: [],
    penalties: [PenaltyType.Health],
    skills: [
      "Research",
      "Observation",
      "Arctic Lore",
      "Forest Lore",
      "Spirit Binding",
      "Thaumaturgy",
    ],
  },
  {
    title: "Bandit Ambush",
    difficulty_mod: 1,
    rewards: [RewardType.Gold],
    criticalRewards: [],
    penalties: [PenaltyType.Health],
    skills: [
      "Brutal Fighting",
      "Climb",
      "Pickpocket",
      "Speed",
      "Throw",
      "Ride",
    ],
  },
  {
    title: "Ancient Ruins",
    difficulty_mod: 2,
    rewards: [RewardType.FreeXp],
    criticalRewards: [RewardType.Gold],
    penalties: [PenaltyType.Health],
    skills: [
      "Architecture",
      "Appraisal",
      "Mechanisms",
      "Research",
      "Observation",
      "Navigation",
    ],
  },
  {
    title: "Court Intrigue",
    difficulty_mod: 1,
    rewards: [RewardType.ControlledTeleport],
    criticalRewards: [],
    penalties: [PenaltyType.Health],
    skills: [
      "Charm",
      "Carousing",
      "Debate",
      "Command",
      "Mesmerism",
      "Appraisal",
    ],
  },
];

let nextTokenId = 1;
export const makeTokenId = () => `token-${nextTokenId++}`;

let nextItemId = 1;
export const makeItemId = () => `item-${nextItemId++}`;

let nextConditionId = 1;
export const makeConditionId = () => `condition-${nextConditionId++}`;

export function makeEmptyResources(): Record<string, number> {
  return Object.fromEntries(resourceTypes.map((type) => [type, 0] as const));
}

export const entityStore = new EntityStore();
for (const schema of Object.values(SCHEMAS)) registerEntitySchema(schema);

type RegisteredFunction = {
  type: FunctionType;
  fn: (...params: any[]) => unknown;
  paramTypes?: FunctionParamType[];
};

export const functionRegistry = new Map<string, RegisteredFunction>();
export const functionParamTypesByType = new Map<
  FunctionType,
  FunctionParamType[]
>([
  [
    FunctionType.RuleCondition,
    [FunctionParamType.Player, FunctionParamType.RawData],
  ],
  [
    FunctionType.RuleValue,
    [FunctionParamType.Player, FunctionParamType.RawData],
  ],
  [
    FunctionType.SelectionCallback,
    [
      FunctionParamType.Selection,
      FunctionParamType.Player,
      FunctionParamType.SelectionChoices,
    ],
  ],
  [FunctionType.SpecialActionAvailability, [FunctionParamType.Player]],
  [FunctionType.SpecialActionExecute, [FunctionParamType.Player]],
]);

function isEntityWithSchema(value: unknown, schemaId: string) {
  return (
    !!value &&
    typeof value === "object" &&
    "schemaId" in value &&
    (value as { schemaId?: unknown }).schemaId === schemaId
  );
}

function validateFunctionParam(
  paramType: FunctionParamType,
  value: unknown,
  index: number,
) {
  switch (paramType) {
    case FunctionParamType.Player:
      if (!isEntityWithSchema(value, "player")) {
        throw new RulesViolation(`Parameter ${index} must be a player entity`);
      }
      return;
    case FunctionParamType.Item:
      if (!isEntityWithSchema(value, "item")) {
        throw new RulesViolation(`Parameter ${index} must be an item entity`);
      }
      return;
    case FunctionParamType.Entity:
      if (
        !value ||
        typeof value !== "object" ||
        typeof (value as { schemaId?: unknown }).schemaId !== "string"
      ) {
        throw new RulesViolation(`Parameter ${index} must be an entity`);
      }
      return;
    case FunctionParamType.SelectionChoices:
      if (!Array.isArray(value) || !value.every((c) => "description" in c)) {
        throw new RulesViolation(
          `Parameter ${index} must be an array of selection choices`,
        );
      }
      return;
    case FunctionParamType.RawData:
      // can be whatever, is cast later
      return;
  }
}

export function registerFunction(
  name: string,
  type: FunctionType,
  fn: (...params: any[]) => unknown,
  paramTypes?: FunctionParamType[],
) {
  if (functionRegistry.has(name)) {
    throw new Error(`Function name must be unique: ${name}`);
  }
  functionRegistry.set(name, { type, fn, paramTypes });
}

export function invoke<T>(
  name: string,
  type: FunctionType,
  params: unknown[],
): T {
  const registered = functionRegistry.get(name);
  if (!registered) {
    throw new RulesViolation(`Function not found: ${name}`);
  }
  if (registered.type !== type) {
    throw new RulesViolation(
      `Function type mismatch for ${name}: expected ${type}, got ${registered.type}`,
    );
  }
  const expectedParams =
    registered.paramTypes ?? functionParamTypesByType.get(type) ?? [];
  if (expectedParams.length !== params.length) {
    throw new RulesViolation(
      `Function ${name} expected ${expectedParams.length} parameters, got ${params.length}`,
    );
  }
  params.forEach((param, index) =>
    validateFunctionParam(expectedParams[index], param, index),
  );
  return registered.fn(...params) as T;
}

let apiState: ApiState | undefined;
export function setApiState(state: ApiState) {
  apiState = state;
}
export function getApiState() {
  if (!apiState) throw new Error("ApiState has not been initialized");
  return apiState;
}

export function makeEmptySkills() {
  return Object.fromEntries(skillNames.map((skill) => [skill, 0] as const));
}

export const rulesByTypeKey = new Map<RuleType, Map<string, Rule[]>>();
const ruleNames = new Set<string>();

function insertRule(list: Rule[], rule: Rule) {
  const index = list.findIndex(
    (existing) => (existing.priority ?? 10) < (rule.priority ?? 10),
  );
  if (index === -1) list.push(rule);
  else list.splice(index, 0, rule);
}

function getRuleKey(rule: Rule) {
  if (rule.type == RuleType.BaseValue || rule.type == RuleType.ModifierValue) {
    if (rule.valueSubtype === undefined) {
      return rule.valueType;
    } else {
      return `${rule.valueType}/${rule.valueSubtype}`;
    }
  }
  return "UNKNOWN";
}

export function addRule(rule: Rule) {
  if (ruleNames.has(rule.name)) {
    throw new Error(`Rule name must be unique: ${rule.name}`);
  }
  ruleNames.add(rule.name);
  let key = getRuleKey(rule);
  const typeRules = rulesByTypeKey.get(rule.type) ?? new Map<string, Rule[]>();
  rulesByTypeKey.set(rule.type, typeRules);
  const ruleList = typeRules.get(key) ?? [];
  typeRules.set(key, ruleList);
  insertRule(ruleList, rule);
}

function hasItem(player: PlayerEntity, itemName: string) {
  return getField(player, "inventory").some((item) => item.name === itemName);
}

function hasItemNamed(player: PlayerEntity, itemName: string) {
  return hasItem(player, itemName);
}

registerFunction(
  "rule-item-speed-boost-condition",
  FunctionType.RuleCondition,
  (_player, item) => getField(item, "speed_boost") != 0,
);
registerFunction(
  "rule-item-speed-boost-value",
  FunctionType.RuleValue,
  (_player, item) => getField(item, "speed_boost"),
);
registerFunction(
  "rule-endurance-shield-base-condition",
  FunctionType.RuleCondition,
  (player) => hasItem(player, "shield"),
);
registerFunction(
  "rule-endurance-shield-base-value",
  FunctionType.RuleValue,
  () => 4,
);

addRule({
  id: "rule-item-speed-boost",
  name: "Item Speed Boost",
  valueType: ValueType.speed,
  type: RuleType.ModifierValue,
  subtype: ValueRuleType.Item,
  condition: "rule-item-speed-boost-condition",
  value: "rule-item-speed-boost-value",
});

addRule({
  id: "rule-endurance-shield-base",
  name: "Shield Endurance Base",
  valueType: ValueType.skill,
  valueSubtype: "Endurance",
  type: RuleType.BaseValue,
  subtype: ValueRuleType.General,
  condition: "rule-endurance-shield-base-condition",
  value: "rule-endurance-shield-base-value",
});

registerFunction(
  "special-medical-visit-availability",
  FunctionType.SpecialActionAvailability,
  (player) =>
    getField(player, "curHealth") <
    computeEffectiveValue(player, ValueType.maxHealth),
  [FunctionParamType.Player],
);
registerFunction(
  "special-medical-visit-execute",
  FunctionType.SpecialActionExecute,
  (_player) => [{ type: EffectType.Health, amount: 2 }],
  [FunctionParamType.Player],
);
registerFunction(
  "special-drink-availability",
  FunctionType.SpecialActionAvailability,
  (_player, item) => getField(item, "name") === "can of coke",
  [FunctionParamType.Player, FunctionParamType.Item],
);
registerFunction(
  "special-drink-execute",
  FunctionType.SpecialActionExecute,
  (_player, item) => [
    { type: EffectType.RemoveItems, itemIds: [item.id] },
    { type: EffectType.Health, amount: 2 },
  ],
  [FunctionParamType.Player, FunctionParamType.Item],
);
registerFunction(
  "special-trade-availability",
  FunctionType.SpecialActionAvailability,
  (_player, entity) => entity.schemaId === "city",
  [FunctionParamType.Player, FunctionParamType.Entity],
);
registerFunction(
  "special-trade-execute",
  FunctionType.SpecialActionExecute,
  (_player) => [{ type: EffectType.Gold, amount: 2 }],
  [FunctionParamType.Player, FunctionParamType.Entity],
);
registerFunction(
  "special-wish-availability",
  FunctionType.SpecialActionAvailability,
  () => true,
  [FunctionParamType.Player],
);
registerFunction(
  "special-wish-execute",
  FunctionType.SpecialActionExecute,
  (player) => {
    const selection: Selection = {
      id: `selection-wish-${Math.random().toString(36).slice(2)}`,
      title: "You Get Your Wish",
      description: "What would you like?",
      choices: [
        { description: "1 gold", data: "gold", index: 0 },
        { description: "1 luck", data: "luck", index: 1 },
        { description: "1 Silk", data: "Silk", index: 2 },
      ],
      minChoices: 0,
      maxChoices: 1,
      callback: "selection-wish-callback",
    };
    appendActivity(player, {
      type: "selection",
      selection,
    });
    return [];
  },
  [FunctionParamType.Player],
);
registerFunction(
  "selection-wish-callback",
  FunctionType.SelectionCallback,
  (selection, player, choices) => {
    if (choices.length !== 1)
      return {
        title: "Wish Granted",
        effects: [],
        flavorText: "No selection made.",
      };
    const choice = choices[0];
    switch (choice.data) {
      case "gold":
        setField(player, "gold", getField(player, "gold") + 1);
        return {
          title: "Wish Granted",
          effects: [{ type: EffectType.Gold, amount: 1 }],
        };
      case "luck":
        setField(
          player,
          "curLuck",
          Math.min(
            getField(player, "maxLuck"),
            getField(player, "curLuck") + 1,
          ),
        );
        return {
          title: "Wish Granted",
          effects: [{ type: EffectType.Luck, amount: 1 }],
        };
      default: {
        throw new RulesViolation("Unknown wish type");
      }
    }
  },
);

export const specialActions: SpecialActionDefinition[] = [
  {
    id: "medical-visit",
    name: "Medical Visit",
    type: SpecialActionType.General,
    locations: ["C10"],
    cost: [{ type: EffectType.Gold, amount: 2 }],
    availability: "special-medical-visit-availability",
    execute: "special-medical-visit-execute",
  },
  {
    id: "drink",
    name: "Drink",
    type: SpecialActionType.Item,
    cost: [],
    availability: "special-drink-availability",
    execute: "special-drink-execute",
  },
  {
    id: "trade",
    name: "Trade",
    type: SpecialActionType.NearbyEntity,
    cost: [],
    availability: "special-trade-availability",
    execute: "special-trade-execute",
  },
  {
    id: "wish",
    name: "Wish",
    type: SpecialActionType.General,
    cost: [],
    availability: "special-wish-availability",
    execute: "special-wish-execute",
  },
];
