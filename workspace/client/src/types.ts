import type { Entity, EntityOf } from "./schemas";

export type Terrain = { name: string; color: string; icon: string };
export type Region = EntityOf<"region">;
export type Claim = { name: string; icon: string };
export type Token = EntityOf<"city">;
export type Item = EntityOf<"item">;
export type Condition = EntityOf<"condition">;
export type Hex = EntityOf<"hex">;
export type PlayerEntity = EntityOf<"player">;
export type PlayerSummary = { id: string; name: string };
export type GameData = {
  hexes: Hex[];
  terrains: Terrain[];
  regions: Region[];
  claims: Claim[];
  tokens: Token[];
  players: PlayerSummary[];
  resourceTypes: string[];
  entities?: Entity[];
};
export enum RewardType {
  Gold = "gold",
  Reputation = "reputation",
  Luck = "luck",
  Resource = "resource",
  FreeXp = "free_xp",
  ControlledTeleport = "controlled_teleport",
  GainItem = "gain_item",
  QualityEncounter = "quality_encounter",
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
  AddTableauCard = "add_tableau_card",
}

export type EncounterSkillCheck = { name: string; target: number };
export type EncounterTemplate = {
  title: string;
  difficulty_mod: number;
  qualityMod?: number;
  rewards: RewardType[];
  criticalRewards: RewardType[];
  penalties: PenaltyType[];
  skills: string[];
};

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
  | { type: EffectType.RemoveRandomItem; itemId?: string }
  | {
      type: EffectType.AddTableauCard;
      encounterTemplate?: EncounterTemplate;
      qualityMod?: number;
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
  qualityMod: number;
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
export type SpecialAction = {
  id: string;
  name: string;
  locations?: string[];
  cost: Effect[];
};
export type SelectionChoice = {
  description: string;
  data: string;
  index: number;
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
};
export type ActivityNextActive =
  | { type: "encounter"; encounter: ActiveEncounter }
  | { type: "selection"; selection: Selection };
export type ActivityResult = {
  title?: string;
  flavorText?: string;
  effects: Effect[];
  implicitEffects?: Effect[];
  nextActive?: ActivityNextActive;
};
export type ActiveEncounter = {
  id: string;
  tableauId?: string;
  title: string;
  state: EncounterState;
  successThreshold: number;
  criticalThreshold?: number;
  failureThreshold: number;
  difficulty: number;
  qualityMod: number;
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
