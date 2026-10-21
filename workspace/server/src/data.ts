import { Claim, EncounterTemplate, Region, Token } from "./types.js";

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

export const encounterTemplates: EncounterTemplate[] = [
  {
    title: "Dungeon Raid",
    base_difficulty: 0,
    rewards: ["Gold"],
    penalties: ["Health"],
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
    rewards: ["Gold"],
    penalties: ["Health"],
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
    rewards: ["Gold"],
    penalties: ["Health"],
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
    rewards: ["Gold"],
    penalties: ["Health"],
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
    rewards: ["Gold"],
    penalties: ["Health"],
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
    rewards: ["Gold"],
    penalties: ["Reputation"],
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
