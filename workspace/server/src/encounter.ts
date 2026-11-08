import { randomUUID } from "node:crypto";

import {
  EncounterSkillCheck,
  EncounterTemplate,
  Hex,
  PlayerEntity,
  Region,
  SectionType,
  TableauCard,
} from "./types.js";
import { generalPenaltyTypes, generalRewardTypes, skillNames } from "./data.js";
import { hexDistance } from "./hexmap.js";
import { getField } from "./entity.js";
import { computeEffectiveValue } from "./rule.js";
import { RNG } from "./random.js";

let encounterHexes: Hex[] = [];
let encounterRegions: Region[] = [];
let encounterRng = new RNG("encounter");

export function setEncounterContext(context: {
  hexes: Hex[];
  regions: Region[];
  rng: RNG;
}) {
  encounterHexes = context.hexes;
  encounterRegions = context.regions;
  encounterRng = context.rng;
}

function randomPick<T>(items: T[], rng = encounterRng) {
  return rng.pick(items);
}

function pickTemplateOrGeneral<T>(
  items: T[],
  generalItems: T[],
  rng = encounterRng,
) {
  return items.length > 0 && rng.next() < 0.8
    ? [...items]
    : [rng.pick(generalItems)];
}

function difficultySwing(rng = encounterRng) {
  return randomPick([0, 0, 0, 0, 0, 0, 1, 1, -1, -1, 2, -2], rng);
}

function hexesNearPlayer(player: PlayerEntity) {
  const origin = encounterHexes.find(
    (hex) => hex.name === getField(player, "location"),
  );
  if (!origin) return [...encounterHexes];
  const speed = computeEffectiveValue(player, SectionType.speed);
  const nearby = encounterHexes.filter(
    (hex) => hexDistance(origin, hex) <= speed,
  );
  return nearby.length > 0 ? nearby : [...encounterHexes];
}

function regionDifficultyForHex(hex: Hex | undefined) {
  if (!hex) return 0;
  return (
    encounterRegions.find((region) => region.id === hex.region_id)
      ?.base_difficulty ?? 0
  );
}

export function rollEncounterSkillChecks(
  skillSource: string[],
  difficulty: number,
  rng = encounterRng,
): EncounterSkillCheck[] {
  return [0, 1, 2].map(() => {
    const skillPool = rng.next() < 0.9 ? skillSource : skillNames;
    const target = 4 + difficulty + difficultySwing(rng);
    return {
      name: randomPick(skillPool, rng),
      target,
    };
  });
}

export function instantiateEncounterTemplate(
  template: EncounterTemplate,
  player: PlayerEntity,
): TableauCard {
  const nearbyHexes = hexesNearPlayer(player);
  const skillSource = template.skills.length > 0 ? template.skills : skillNames;

  const locationCandidates =
    nearbyHexes.length > 0 ? nearbyHexes : encounterHexes;
  const location =
    locationCandidates.length > 0
      ? randomPick(locationCandidates).name
      : getField(player, "location");
  const locationHex = encounterHexes.find((hex) => hex.name === location);
  const difficulty =
    regionDifficultyForHex(locationHex) +
    template.difficulty_mod +
    difficultySwing();
  const successThreshold = 2;
  const criticalThreshold = 3;
  const failureThreshold = 3;
  return {
    id: randomUUID(),
    title: template.title,
    location,
    difficulty,
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
