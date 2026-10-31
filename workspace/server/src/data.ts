import {
  Claim,
  EffectType,
  EncounterTemplate,
  Item,
  PenaltyType,
  PlayerEntity,
  Region,
  RewardType,
  Rule,
  RuleType,
  SectionType,
  Selection,
  SpecialActionDefinition,
  Token,
} from "./types.js";
import { computeEffectiveValue } from "./rule.js";

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

export const regionNames = [
  "Valley of Aardia",
  "Domain of the Elves",
  "Iron Marches",
  "Sunspire Coast",
  "Gloaming Fens",
  "Kingdom of Roses",
  "Storm Peaks",
  "Amber Wastes",
  "Silverwood",
  "Riverlands",
  "Crown Basin",
  "Ashen Reach",
  "Sapphire Isles",
  "Old Empire",
  "Whispering Downs",
  "Dragonmere",
  "Golden Steppe",
  "Umbral Vale",
  "Free Cities",
];
export let regions: Region[] = regionNames.map((name) => ({ name }));

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
          base_difficulty: 2,
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

export const encounterTemplates: EncounterTemplate[] = [
  {
    title: "Dungeon Raid",
    base_difficulty: 0,
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
    base_difficulty: 4,
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
    base_difficulty: 2,
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
    base_difficulty: 1,
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
    base_difficulty: 3,
    rewards: [RewardType.Gold],
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
    base_difficulty: 5,
    rewards: [RewardType.Gold],
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

export let cityTokens: Token[] = [
  "Waterdeep",
  "Underhaven",
  "Dawnport",
  "Ironford",
  "Moonfall",
  "Highspire",
  "Blackwell",
  "Greengate",
].map((n) => ({ id: makeTokenId(), entityName: `City of ${n}`, icon: "city" }));
export function setCityTokens(next: Token[]) {
  cityTokens = next;
}

export function makeEmptySkills() {
  return Object.fromEntries(skillNames.map((skill) => [skill, 0] as const));
}

export const rulesBySection = new Map<
  SectionType,
  Map<string | undefined, Map<RuleType, Rule[]>>
>();
const ruleNames = new Set<string>();

function resolvedPriority(rule: Rule) {
  return rule.priority ?? 10;
}

function insertRule(list: Rule[], rule: Rule) {
  const index = list.findIndex(
    (existing) => resolvedPriority(existing) < resolvedPriority(rule),
  );
  if (index === -1) list.push(rule);
  else list.splice(index, 0, rule);
}

export function addRule(rule: Rule) {
  if (ruleNames.has(rule.name)) {
    throw new Error(`Rule name must be unique: ${rule.name}`);
  }
  ruleNames.add(rule.name);
  const sectionRules =
    rulesBySection.get(rule.section) ??
    new Map<string | undefined, Map<RuleType, Rule[]>>();
  rulesBySection.set(rule.section, sectionRules);
  const subsectionRules =
    sectionRules.get(rule.subsection) ?? new Map<RuleType, Rule[]>();
  sectionRules.set(rule.subsection, subsectionRules);
  const ruleList = subsectionRules.get(rule.type) ?? [];
  subsectionRules.set(rule.type, ruleList);
  insertRule(ruleList, {
    ...rule,
    priority: resolvedPriority(rule),
  });
}

function hasItem(player: PlayerEntity, itemName: string) {
  return player.inventory.some((item) => item.name === itemName);
}

function hasItemNamed(player: PlayerEntity, itemName: string) {
  return hasItem(player, itemName);
}

addRule({
  id: "rule-speed-can-of-coke",
  name: "Can of Coke Speed Boost",
  section: SectionType.speed,
  type: RuleType.ModifierValue,
  condition: (player) => hasItem(player, "can of coke"),
  value: () => 2,
});

addRule({
  id: "rule-endurance-shield-base",
  name: "Shield Endurance Base",
  section: SectionType.skill,
  subsection: "Endurance",
  type: RuleType.BaseValue,
  condition: (player) => hasItem(player, "shield"),
  value: () => 4,
});

export const specialActions: SpecialActionDefinition[] = [
  {
    id: "medical-visit",
    name: "Medical Visit",
    locations: ["C10"],
    cost: [{ type: EffectType.Gold, amount: 2 }],
    availability: (player) =>
      player.curHealth < computeEffectiveValue(player, SectionType.maxHealth),
    execute: (_state, _player) => [{ type: EffectType.Health, amount: 2 }],
  },
  {
    id: "drink",
    name: "Drink",
    cost: [],
    availability: (player) => hasItemNamed(player, "can of coke"),
    execute: (_state, player) => {
      const item = player.inventory.find((item) => item.name === "can of coke");
      return item ? [{ type: EffectType.RemoveItems, itemIds: [item.id] }] : [];
    },
  },
  {
    id: "wish",
    name: "Wish",
    cost: [],
    availability: () => true,
    execute: (state, player) => {
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
        callback: (indexes) => {
          if (indexes.length === 0)
            return {
              title: "Wish Granted",
              effects: [],
              flavorText: "No selection made.",
            };
          const choice = selection.choices.find(
            (item) => item.index === indexes[0],
          );
          if (!choice)
            return {
              title: "Wish Granted",
              effects: [],
              flavorText: "No selection made.",
            };
          switch (choice.data) {
            case "gold":
              player.gold += 1;
              return {
                title: "Wish Granted",
                effects: [{ type: EffectType.Gold, amount: 1 }],
              };
            case "luck":
              player.curLuck = Math.min(player.maxLuck, player.curLuck + 1);
              return {
                title: "Wish Granted",
                effects: [{ type: EffectType.Luck, amount: 1 }],
              };
            default:
              player.resources[choice.data] =
                (player.resources[choice.data] ?? 0) + 1;
              return {
                title: "Wish Granted",
                effects: [
                  {
                    type: EffectType.Resource,
                    resourceType: choice.data,
                    amount: 1,
                  },
                ],
              };
          }
        },
      };
      state.activeSelections.set(player.id, selection);
      return [];
    },
  },
];
