import type {
  ActiveEncounter as CommonActiveEncounter,
  ActiveEncounterSkillCheck as CommonActiveEncounterSkillCheck,
  ActivityNextActive as CommonActivityNextActive,
  ActivityResult as CommonActivityResult,
  Notification as CommonNotification,
  Trigger as CommonTrigger,
  AxialPoint as CommonAxialPoint,
  Claim as CommonClaim,
  Condition as CommonCondition,
  EncounterSkillCheck,
  EncounterTemplate,
  Effect,
  GameData as CommonGameData,
  Hex as CommonHex,
  Item as CommonItem,
  AnnotatedValue as CommonAnnotatedValue,
  PlayerEntity as CommonPlayerEntity,
  PlayerEntityDto as CommonPlayerEntityDto,
  PlayerSummary as CommonPlayerSummary,
  SingleValueEntry as CommonSingleValueEntry,
  Region as CommonRegion,
  FunctionParamType,
  FunctionType,
  SelectionBase,
  SelectionChoice as CommonSelectionChoice,
  AvailableSpecialAction as CommonAvailableSpecialAction,
  SpecialAction as CommonSpecialAction,
  SpecialActionRequest as CommonSpecialActionRequest,
  SpecialActionType as CommonSpecialActionType,
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
export {
  RewardType,
  PenaltyType,
  EffectType,
  FunctionType,
  FunctionParamType,
} from "@common/types.js";
export type { EncounterSkillCheck, EncounterTemplate, Effect };

export type PlayerEntity = CommonPlayerEntity;
export type PlayerEntityDto = CommonPlayerEntityDto;
export type AnnotatedValue = CommonAnnotatedValue;
export type SingleValueEntry = CommonSingleValueEntry;
export type RegionEntity = EntityOf<"region">;
export type CityEntity = EntityOf<"city">;
export type HexEntity = EntityOf<"hex">;
export type AxialPoint = CommonAxialPoint;

export enum ValueType {
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
};
export enum ValueRuleType {
  General = "General",
  Item = "Item",
}
export type Rule =
  | (RuleBase & {
      valueType: ValueType;
      valueSubtype?: string;
      type: RuleType.BaseValue;
      subtype: ValueRuleType.General;
      condition: string;
      value: string;
    })
  | (RuleBase & {
      valueType: ValueType;
      valueSubtype?: string;
      type: RuleType.BaseValue;
      subtype: ValueRuleType.Item;
      condition: string;
      value: string;
    })
  | (RuleBase & {
      valueType: ValueType;
      valueSubtype?: string;
      type: RuleType.ModifierValue;
      subtype: ValueRuleType.General;
      condition: string;
      value: string;
    })
  | (RuleBase & {
      valueType: ValueType;
      valueSubtype?: string;
      type: RuleType.ModifierValue;
      subtype: ValueRuleType.Item;
      condition: string;
      value: string;
    });

export type ActiveEncounterSkillCheck = CommonActiveEncounterSkillCheck;
export type TableauCard = CommonTableauCard;
export type TableauData = CommonTableauData;
export type SpecialAction = CommonSpecialAction;
export type AvailableSpecialAction = CommonAvailableSpecialAction;
export { SpecialActionType } from "@common/types.js";
export type SelectionChoice = CommonSelectionChoice;
export type SelectionViewChoice = CommonSelectionChoice;
export type SelectionView = SelectionBase;
export type Selection = SelectionBase & {
  callback: string;
};
export type Notification = CommonNotification;
export type Trigger = CommonTrigger;
export { TriggerType } from "@common/types.js";
export type PendingActivity =
  | { type: "encounter"; encounter: ActiveEncounter }
  | { type: "selection"; selection: Selection }
  | { type: "notification"; notification: Notification };
export type PlayCard = { title: string; lines: string[] };
export type SpecialActionDefinition = SpecialAction & {
  availability: string;
  execute: string;
};
export type SpecialActionRequest = CommonSpecialActionRequest;
export type ApiState = {
  hexes: Hex[];
  hexByName: Map<string, Hex>;
  regions: Region[];
  tokens: { id: string; entityName: string; icon: string }[];
  entities: EntityStore;
  activitiesQueue: Map<string, PendingActivity[]>;
  tableau: Map<string, TableauCard[]>;
};
export type ActivityNextActive = CommonActivityNextActive<SelectionView>;
export type ActivityResult = CommonActivityResult<SelectionView>;
export type ActiveEncounter = CommonActiveEncounter;
