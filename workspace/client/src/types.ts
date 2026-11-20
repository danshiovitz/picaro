import type {
  ActiveEncounter as CommonActiveEncounter,
  ActiveEncounterSkillCheck as CommonActiveEncounterSkillCheck,
  ActivityNextActive as CommonActivityNextActive,
  Notification as CommonNotification,
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
  SelectionBase,
  SelectionChoice as CommonSelectionChoice,
  AvailableSpecialAction as CommonAvailableSpecialAction,
  SpecialAction as CommonSpecialAction,
  SpecialActionType as CommonSpecialActionType,
  TableauCard as CommonTableauCard,
  TableauData as CommonTableauData,
  Terrain as CommonTerrain,
  Token as CommonToken,
} from "../../common/src/types.js";
import type { Entity as CommonEntity } from "../../common/src/schemas.js";

export type Entity = CommonEntity;
export type Terrain = CommonTerrain;
export type Region = CommonRegion;
export type Claim = CommonClaim;
export type Token = CommonToken;
export type Item = CommonItem;
export type Condition = CommonCondition;
export type Hex = CommonHex;
export type PlayerEntityDto = CommonPlayerEntityDto;
export type PlayerEntity = PlayerEntityDto & {
  skills: Record<string, number>;
};
export type AnnotatedValue = CommonAnnotatedValue;
export type SingleValueEntry = CommonSingleValueEntry;
export type PlayerSummary = CommonPlayerSummary;
export type GameData = CommonGameData;
export { RewardType, PenaltyType, EffectType } from "../../common/src/types.js";
export type { EncounterSkillCheck, EncounterTemplate, Effect };

export type EncounterState = "active" | "lost" | "succeeded" | "critical";
export type ActiveEncounterSkillCheck = CommonActiveEncounterSkillCheck;
export type TableauCard = CommonTableauCard;
export type TableauData = CommonTableauData;
export type SpecialAction = CommonSpecialAction;
export type AvailableSpecialAction = CommonAvailableSpecialAction;
export { SpecialActionType } from "../../common/src/types.js";
export type SelectionChoice = CommonSelectionChoice;
export type Selection = SelectionBase;
export type Notification = CommonNotification;
export type ActivityNextActive = CommonActivityNextActive<Selection>;
export type ActiveEncounter = CommonActiveEncounter;
