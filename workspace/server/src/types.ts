import { RNG } from "./random.js";
import type {
  Entity as BaseEntity,
  EntityOf,
  EntitySchema,
  FieldType,
  SchemaField,
  SchemaId,
} from "./schemas.js";

export type Terrain = { name: string; color: string; icon: string };
export type Region = { id: string; name: string; base_difficulty: number };
export type RegionEntity = EntityOf<"region">;
export type Claim = { name: string; icon: string };
export type Token = { id: string; entityName: string; icon: string };
export type AxialPoint = { q: number; r: number };
export type Entity = BaseEntity;
export type CityEntity = EntityOf<"city">;
export type Item = EntityOf<"item">;
export type Condition = EntityOf<"condition">;
export type PlayerEntity = EntityOf<"player">;
export type Hex = {
  name: string;
  x: number;
  y: number;
  q: number;
  r: number;
  terrain: string;
  region_id: string;
  claims: string[];
  tokens: string[];
};
export type HexEntity = EntityOf<"hex">;
export enum SectionType {
  speed = "speed",
  maxHealth = "max_health",
  skill = "skill",
}
export enum RuleType {
  BaseValue = "BaseValue",
  ModifierValue = "ModifierValue",
}
export type RuleBase = {
  id: string;
  name: string;
  priority?: number;
  section: SectionType;
  subsection?: string;
  condition: (player: PlayerEntity) => boolean;
};
export type BaseValueRule = RuleBase & {
  type: RuleType.BaseValue;
  value: (player: PlayerEntity) => number;
};
export type ModifierValueRule = RuleBase & {
  type: RuleType.ModifierValue;
  value: (player: PlayerEntity) => number;
};
export type Rule = BaseValueRule | ModifierValueRule;
export enum RewardType {
  Gold = "gold",
  Reputation = "reputation",
  Luck = "luck",
  Resource = "resource",
  FreeXp = "free_xp",
  ControlledTeleport = "controlled_teleport",
  GainItem = "gain_item",
}
export enum PenaltyType {
  Gold = "gold",
  Health = "health",
  Turns = "turns",
  Luck = "luck",
  Resource = "resource",
  RemoveItem = "remove_item",
}
export enum EffectType {
  Gold = "gold",
  Reputation = "reputation",
  Health = "health",
  Turns = "turns",
  Luck = "luck",
  Resource = "resource",
  FreeXp = "free_xp",
  ControlledTeleport = "controlled_teleport",
  SkillXp = "skill_xp",
  RemoveItems = "remove_items",
  GainRandomItem = "gain_random_item",
  RemoveRandomItem = "remove_random_item",
}
export type Effect =
  | { type: EffectType.Gold; amount: number }
  | { type: EffectType.Reputation; amount: number }
  | { type: EffectType.Health; amount: number }
  | { type: EffectType.Turns; amount: number }
  | { type: EffectType.Luck; amount: number }
  | { type: EffectType.Resource; resourceType: string; amount: number }
  | { type: EffectType.FreeXp; amount: number }
  | { type: EffectType.ControlledTeleport; radius: number }
  | {
      type: EffectType.SkillXp;
      skill: string;
      amount: number;
      newLevel?: number;
    }
  | { type: EffectType.RemoveItems; itemIds: string[] }
  | {
      type: EffectType.GainRandomItem;
      quality: number;
      itemId?: string;
    }
  | { type: EffectType.RemoveRandomItem; itemId?: string };
export type EncounterSkillCheck = { name: string; target: number };
export type EncounterTemplate = {
  title: string;
  difficulty_mod: number;
  rewards: RewardType[];
  criticalRewards: RewardType[];
  penalties: PenaltyType[];
  skills: string[];
};
export type EncounterState = "active" | "lost" | "succeeded" | "critical";
export type ActiveEncounterSkillCheck = {
  name: string;
  target: number;
  roll: number;
  modifier: number;
  total: number;
  success: boolean;
};
export type TableauCard = {
  id: string;
  title: string;
  location: string;
  difficulty: number;
  successThreshold: number;
  criticalThreshold?: number;
  failureThreshold: number;
  rewards: RewardType[];
  criticalRewards: RewardType[];
  penalties: PenaltyType[];
  skillSource: string[];
  skillChecks: EncounterSkillCheck[];
};
export type TableauData = { encounters: TableauCard[] };

import type { EntityStore } from "./entity.js";

export type ApiState = {
  hexes: Hex[];
  hexByName: Map<string, Hex>;
  regions: Region[];
  tokens: { id: string; entityName: string; icon: string }[];
  entities: EntityStore;
  currentActivities: Map<string, PendingActivity>;
  pendingWork: Map<string, PendingActivity[]>;
  tableau: Map<string, TableauCard[]>;
};

export type SpecialAction = {
  id: string;
  name: string;
  locations?: string[];
  cost: Effect[];
};
export type SpecialActionDefinition = SpecialAction & {
  availability: (player: PlayerEntity) => boolean;
  execute: (state: ApiState, player: PlayerEntity) => Effect[];
};
export type SelectionChoice = {
  description: string;
  data: string;
  index: number;
};
export type SelectionViewChoice = {
  description: string;
  data: string;
  index: number;
};
export type SelectionView = {
  id: string;
  title: string;
  description?: string;
  choices: SelectionViewChoice[];
  minChoices?: number;
  maxChoices?: number;
  useDropdown?: boolean;
  hexSelection?: { originHex: string; radius: number };
};
export type Selection = {
  id: string;
  title: string;
  description?: string;
  choices: SelectionChoice[];
  minChoices?: number;
  maxChoices?: number;
  useDropdown?: boolean;
  hexSelection?: { originHex: string; radius: number };
  callback: (indexes: number[]) => ActivityResult | void;
};

export type PendingActivity =
  | { type: "encounter"; encounter: ActiveEncounter }
  | { type: "selection"; selection: Selection };

export type PlayCard = { title: string; lines: string[] };
export type ActivityNextActive =
  | { type: "encounter"; encounter: ActiveEncounter }
  | { type: "selection"; selection: SelectionView };
export type ActivityResult = {
  title?: string;
  flavorText?: string;
  effects: Effect[];
  implicitEffects?: Effect[];
  nextActive?: ActivityNextActive;
};
export type SpecialActionRequest = { specialActionId: string };
export type ActiveEncounter = {
  id: string;
  tableauId?: string;
  title: string;
  state: EncounterState;
  successThreshold: number;
  criticalThreshold?: number;
  failureThreshold: number;
  difficulty: number;
  numSuccesses: number;
  numFailures: number;
  nextPenalty?: PenaltyType;
  rewards: RewardType[];
  criticalRewards: RewardType[];
  penalties: PenaltyType[];
  skillChecks: ActiveEncounterSkillCheck[];
  skillSource: string[];
  currentSkillChecks: ActiveEncounterSkillCheck[];
};
