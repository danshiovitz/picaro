export type Terrain = { name: string; color: string; icon: string };
export type Region = { name: string };
export type Claim = { name: string; icon: string };
export type Token = { id: string; entityName: string; icon: string };
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
export type GameData = {
  hexes: Hex[];
  terrains: Terrain[];
  regions: Region[];
  claims: Claim[];
  tokens: Token[];
};
export enum RewardType {
  Gold = "gold",
  Reputation = "reputation",
}
export enum PenaltyType {
  Gold = "gold",
  Health = "health",
}
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
export type PlayerEntity = {
  name: string;
  tokenId: string;
  curHealth: number;
  maxHealth: number;
  curLuck: number;
  maxLuck: number;
  gold: number;
  reputation: number;
  turns: number;
  location: string;
};
export type PlayCard = { title: string; lines: string[] };
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
};
export type ActionResponse = {
  updates: Partial<PlayerEntity>;
  card?: PlayCard;
  tableauChanged: boolean;
  tableau?: TableauData;
};
export type RunEncounterResponse = { encounter: ActiveEncounter };
export type ContinueEncounterResponse = { encounter: ActiveEncounter };
export type FinishEncounterResponse = {
  updates?: Partial<PlayerEntity>;
  card?: PlayCard;
  encounter?: ActiveEncounter;
  removedEncounterId?: string;
  tableauChanged: boolean;
  tableau?: TableauData;
};
