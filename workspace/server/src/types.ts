export type Terrain = { name: string; color: string; icon: string };
export type Region = { name: string };
export type Claim = { name: string; icon: string };
export type Token = { id: string; entityName: string; icon: string };
export type Item = { id: string; name: string };
export type Condition = { id: string; name: string; duration: number };
export type AxialPoint = { q: number; r: number };
export type Hex = {
  name: string;
  x: number;
  y: number;
  q: number;
  r: number;
  terrain: string;
  region: string;
  claims: string[];
  tokens: string[];
};
export type PlayerEntity = {
  id: string;
  name: string;
  tokenId: string;
  curHealth: number;
  maxHealth: number;
  curLuck: number;
  maxLuck: number;
  speed: number;
  gold: number;
  reputation: number;
  turns: number;
  location: string;
  resources: Record<string, number>;
  inventory: Item[];
  conditions: Condition[];
  skills: Record<string, number>;
};
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
}
export enum PenaltyType {
  Gold = "gold",
  Health = "health",
  Turns = "turns",
  Luck = "luck",
  Resource = "resource",
}
export enum EffectType {
  Gold = "gold",
  Reputation = "reputation",
  Health = "health",
  Turns = "turns",
  Luck = "luck",
  Resource = "resource",
  RemoveItems = "remove_items",
}
export type Effect =
  | { type: EffectType.Gold; amount: number }
  | { type: EffectType.Reputation; amount: number }
  | { type: EffectType.Health; amount: number }
  | { type: EffectType.Turns; amount: number }
  | { type: EffectType.Luck; amount: number }
  | { type: EffectType.Resource; resourceType: string; amount: number }
  | { type: EffectType.RemoveItems; itemIds: string[] };
export type EncounterSkillCheck = { name: string; target: number };
export type EncounterTemplate = {
  title: string;
  base_difficulty: number;
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
  old?: boolean;
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
  skillChecks: EncounterSkillCheck[];
};
export type TableauData = { encounters: TableauCard[] };
export type SpecialAction = {
  id: string;
  name: string;
  locations?: string[];
  cost: Effect[];
};
export type SpecialActionState = {
  activeSelections: Map<string, Selection>;
};
export type SpecialActionDefinition<
  TState extends SpecialActionState = SpecialActionState,
> = SpecialAction & {
  availability: (player: PlayerEntity) => boolean;
  execute: (state: TState, player: PlayerEntity) => Effect[];
};
export type SelectionChoice = {
  description: string;
  data: string;
  index: number;
};
export type SelectionViewChoice = {
  description: string;
  index: number;
};
export type SelectionView = {
  id: string;
  title: string;
  description?: string;
  choices: SelectionViewChoice[];
  minChoices?: number;
  maxChoices?: number;
};
export type Selection = {
  id: string;
  title: string;
  description?: string;
  choices: SelectionChoice[];
  minChoices?: number;
  maxChoices?: number;
  callback: (indexes: number[]) => ActivityResult | void;
};
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
  numSuccesses: number;
  numFailures: number;
  nextPenalty?: PenaltyType;
  rewards: RewardType[];
  criticalRewards: RewardType[];
  penalties: PenaltyType[];
  skillChecks: ActiveEncounterSkillCheck[];
  skillCheckTemplate: EncounterSkillCheck[];
};
