import type {
  ActiveEncounter as CommonActiveEncounter,
  ActiveEncounterSkillCheck as CommonActiveEncounterSkillCheck,
  ActivityNextActive as CommonActivityNextActive,
  ActivityResult as CommonActivityResult,
  AxialPoint as CommonAxialPoint,
  Claim as CommonClaim,
  Condition as CommonCondition,
  EncounterSkillCheck,
  EncounterTemplate,
  Effect,
  GameData as CommonGameData,
  Hex as CommonHex,
  Item as CommonItem,
  PlayerEntity as CommonPlayerEntity,
  PlayerSummary as CommonPlayerSummary,
  Region as CommonRegion,
  SelectionBase,
  SelectionChoice as CommonSelectionChoice,
  SpecialAction as CommonSpecialAction,
  TableauCard as CommonTableauCard,
  TableauData as CommonTableauData,
  Terrain as CommonTerrain,
  Token as CommonToken,
} from "@common/types.js";
import type { Entity as CommonEntity, EntityOf } from "@common/schemas.js";
import type { EntityStore } from "./entity.js";

export type Entity = CommonEntity;
export type Terrain = CommonTerrain;
export type Region = { id: string; name: string; base_difficulty: number };
export type Claim = { name: string; icon: string };
export type Token = { id: string; entityName: string; icon: string };
export type Item = CommonItem;
export type Condition = CommonCondition;
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
export type PlayerSummary = CommonPlayerSummary;
export { RewardType, PenaltyType, EffectType } from "@common/types.js";
export type { EncounterSkillCheck, EncounterTemplate, Effect };

export type PlayerEntity = CommonPlayerEntity;
export type RegionEntity = EntityOf<"region">;
export type CityEntity = EntityOf<"city">;
export type HexEntity = EntityOf<"hex">;
export type AxialPoint = CommonAxialPoint;

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

export type ActiveEncounterSkillCheck = CommonActiveEncounterSkillCheck;
export type TableauCard = CommonTableauCard;
export type TableauData = CommonTableauData;
export type SpecialAction = CommonSpecialAction;
export type SelectionChoice = CommonSelectionChoice;
export type SelectionViewChoice = CommonSelectionChoice;
export type SelectionView = SelectionBase;
export type Selection = SelectionBase & {
  callback: (indexes: number[]) => ActivityResult | void;
};
export type PendingActivity =
  | { type: "encounter"; encounter: ActiveEncounter }
  | { type: "selection"; selection: Selection };
export type PlayCard = { title: string; lines: string[] };
export type SpecialActionDefinition = SpecialAction & {
  availability: (player: PlayerEntity) => boolean;
  execute: (state: ApiState, player: PlayerEntity) => Effect[];
};
export type SpecialActionRequest = { specialActionId: string };
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
export type ActivityNextActive = CommonActivityNextActive<SelectionView>;
export type ActivityResult = CommonActivityResult<SelectionView>;
export type ActiveEncounter = CommonActiveEncounter;
