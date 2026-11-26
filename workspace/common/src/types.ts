import type { Entity, EntityOf } from "./schemas.js";

export type Terrain = { name: string; color: string; icon: string };
export type Region = EntityOf<"region">;
export type Claim = { name: string; icon: string };
export type AxialPoint = { q: number; r: number };
export type Item = EntityOf<"item">;
export type Condition = EntityOf<"condition">;
export type Hex = EntityOf<"hex">;
export type Token = EntityOf<"token">;
export type PlayerEntity = EntityOf<"player">;
export type PlayerSummary = { id: string; name: string };
export enum FunctionType {
  RuleCondition = "rule_condition",
  RuleValue = "rule_value",
  SelectionCallback = "selection_callback",
  SpecialActionAvailability = "special_action_availability",
  SpecialActionExecute = "special_action_execute",
  TriggerCallback = "trigger_callback",
}
export enum FunctionParamType {
  Player = "player",
  Item = "item",
  Entity = "entity",
  Selection = "selection",
  SelectionChoices = "choices",
  RawData = "rawData",
}
export type SingleValueEntry = { value: number; text: string };
export type AnnotatedValue = {
  finalValue: number;
  baseValue: SingleValueEntry;
  modifierValues: SingleValueEntry[];
};
export type PlayerEntityDto = Omit<
  PlayerEntity,
  "maxHealth" | "maxLuck" | "speed"
> & {
  maxHealth: AnnotatedValue;
  maxLuck: AnnotatedValue;
  speed: AnnotatedValue;
  skills: Record<string, AnnotatedValue>;
};
export type GameData = {
  hexes: Hex[];
  terrains: Terrain[];
  regions: Region[];
  claims: Claim[];
  resourceTypes: string[];
  entities: Entity[];
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
  RandomTeleport = "random_teleport",
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
  RefreshTableau = "refresh_tableau",
  Teleport = "teleport",
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
  | { type: EffectType.Gold; amount: number; annotatedValue?: AnnotatedValue }
  | {
      type: EffectType.Reputation;
      amount: number;
      annotatedValue?: AnnotatedValue;
    }
  | { type: EffectType.Health; amount: number; annotatedValue?: AnnotatedValue }
  | { type: EffectType.Turns; amount: number; annotatedValue?: AnnotatedValue }
  | { type: EffectType.Luck; amount: number; annotatedValue?: AnnotatedValue }
  | {
      type: EffectType.Resource;
      resourceType: string;
      amount: number;
      annotatedValue?: AnnotatedValue;
    }
  | { type: EffectType.FreeXp; amount: number; annotatedValue?: AnnotatedValue }
  | {
      type: EffectType.ControlledTeleport;
      radius: number;
      annotatedValue?: AnnotatedValue;
    }
  | {
      type: EffectType.SkillXp;
      skill: string;
      amount: number;
      newLevel?: number;
      annotatedValue?: AnnotatedValue;
    }
  | {
      type: EffectType.RemoveItems;
      itemIds: string[];
      annotatedValue?: AnnotatedValue;
    }
  | {
      type: EffectType.GainRandomItem;
      quality: number;
      itemId?: string;
      annotatedValue?: AnnotatedValue;
    }
  | {
      type: EffectType.RemoveRandomItem;
      itemId?: string;
      annotatedValue?: AnnotatedValue;
    }
  | {
      type: EffectType.AddTableauCard;
      encounterTemplate?: EncounterTemplate;
      qualityMod?: number;
      annotatedValue?: AnnotatedValue;
    }
  | {
      type: EffectType.RefreshTableau;
      qualityMods?: number[];
      annotatedValue?: AnnotatedValue;
    }
  | {
      type: EffectType.Teleport;
      radius: number;
      centerHex: string;
      annotatedValue?: AnnotatedValue;
    };

export enum TriggerType {
  EndOfTurn = "end_of_turn",
  Death = "death",
  HexEntered = "hex_entered",
}

export type Trigger = {
  id: string;
  name: string;
  priority: number;
  type: TriggerType;
  callback: string;
};

export type Notification = {
  id: string;
  title: string;
  flavorText?: string;
  effects: Effect[];
  implicitEffects: Effect[];
};

export type EncounterState = "active" | "lost" | "succeeded" | "critical";
export type ActiveEncounterSkillCheck = {
  name: string;
  target: number;
  roll: number;
  modifier: AnnotatedValue;
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
export enum SpecialActionType {
  General = "general",
  Item = "item",
  NearbyEntity = "nearby_entity",
}
export type SpecialAction = {
  id: string;
  name: string;
  type: SpecialActionType;
  locations?: string[];
  cost: Effect[];
};
export type AvailableSpecialAction = SpecialAction & {
  entityId?: string;
  execute?: string;
};
export type SelectionChoice = {
  description: string;
  data: string;
  index: number;
};
export type SelectionBase = {
  id: string;
  title: string;
  description?: string;
  choices: SelectionChoice[];
  minChoices?: number;
  maxChoices?: number;
  useDropdown?: boolean;
  hexSelection?: { originHex: string; radius: number };
  callbackData?: unknown;
  implicitEffects: Effect[];
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
  implicitEffects: Effect[];
};
export type ActivityNextActive<
  SelectionT extends SelectionBase = SelectionBase,
> =
  | { type: "encounter"; encounter: ActiveEncounter }
  | { type: "selection"; selection: SelectionT }
  | { type: "notification"; notification: Notification };

export type SpecialActionRequest = {
  specialActionId: string;
  entityId?: string;
};
export type ActivityResult<SelectionT extends SelectionBase = SelectionBase> =
  Notification;
