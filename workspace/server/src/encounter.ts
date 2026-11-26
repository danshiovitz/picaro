import { randomUUID } from "node:crypto";

import {
  EncounterSkillCheck,
  EncounterTemplate,
  Hex,
  PlayerEntity,
  Region,
  TableauCard,
  ValueType,
} from "./types.js";
import {
  elementTypes,
  generalPenaltyTypes,
  generalRewardTypes,
  getApiState,
  skillNames,
} from "./data.js";
import { hexDistance } from "@common/hexmap.js";
import { getField } from "./entity.js";
import { computeEffectiveValue } from "./rule.js";
import { getRng } from "@common/random.js";

function pickTemplateOrGeneral<T>(items: T[], generalItems: T[]) {
  return items.length > 0 && getRng().next() < 0.8
    ? [...items]
    : [getRng().pick(generalItems)];
}

function difficultySwing() {
  return getRng().pick([0, 0, 0, 0, 0, 0, 1, 1, -1, -1, 2, -2]);
}

function hexesNearPlayer(player: PlayerEntity) {
  const state = getApiState();
  const origin = state.hexes.find(
    (hex) => hex.name === getField(player, "location"),
  );
  if (!origin) return [...state.hexes];
  const speed = computeEffectiveValue(player, ValueType.speed);
  const nearby = state.hexes.filter((hex) => hexDistance(origin, hex) <= speed);
  return nearby.length > 0 ? nearby : [...state.hexes];
}

function regionDifficultyForHex(hex: Hex | undefined) {
  const state = getApiState();
  if (!hex) return 0;
  return (
    state.regions.find((region) => region.id === hex.region_id)
      ?.base_difficulty ?? 0
  );
}

export function rollEncounterSkillChecks(
  skillSource: string[],
  difficulty: number,
): EncounterSkillCheck[] {
  return [0, 1, 2].map(() => {
    const skillPool = getRng().next() < 0.9 ? skillSource : skillNames;
    const target = 4 + difficulty + difficultySwing();
    return {
      name: getRng().pick(skillPool),
      target,
    };
  });
}

export function instantiateEncounterTemplate(
  template: EncounterTemplate,
  player: PlayerEntity,
  qualityModOverride: number | undefined = undefined,
): TableauCard {
  const state = getApiState();
  const nearbyHexes = hexesNearPlayer(player);
  const skillSource = template.skills.length > 0 ? template.skills : skillNames;

  const locationCandidates = nearbyHexes.length > 0 ? nearbyHexes : state.hexes;
  const location =
    locationCandidates.length > 0
      ? getRng().pick(locationCandidates).name
      : getField(player, "location");
  const locationHex = state.hexes.find((hex) => hex.name === location);
  const difficulty =
    regionDifficultyForHex(locationHex) +
    template.difficulty_mod +
    difficultySwing();
  const qualityMod = qualityModOverride ?? difficultySwing();
  const successThreshold = 2;
  const criticalThreshold = 3;
  const failureThreshold = 3;
  return {
    id: randomUUID(),
    title: template.title,
    element:
      getRng().next() < 0.9 ? template.element : getRng().pick(elementTypes),
    location,
    difficulty,
    qualityMod,
    successThreshold,
    criticalThreshold,
    failureThreshold,
    rewards: pickTemplateOrGeneral(template.rewards, generalRewardTypes),
    criticalRewards: pickTemplateOrGeneral(
      template.criticalRewards,
      generalRewardTypes,
    ),
    penalties: pickTemplateOrGeneral(template.penalties, generalPenaltyTypes),
    skillSource: [...skillSource],
    skillChecks: rollEncounterSkillChecks(skillSource, difficulty),
  };
}
