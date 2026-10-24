import { randomUUID } from "node:crypto";

import { EncounterTemplate, Hex, PlayerEntity, TableauCard } from "./types.js";
import { skillNames } from "./data.js";
import { hexDistance } from "./hexmap.js";
import { RNG } from "./random.js";

let encounterHexes: Hex[] = [];
let encounterRng = new RNG("encounter");

export function setEncounterContext(context: { hexes: Hex[]; rng: RNG }) {
  encounterHexes = context.hexes;
  encounterRng = context.rng;
}

function randomPick<T>(items: T[]) {
  return encounterRng.pick(items);
}

function difficultySwing() {
  return randomPick([0, 0, 0, 0, 0, 0, 1, 1, -1, -1, 2, -2]);
}

function hexesNearPlayer(player: PlayerEntity) {
  const origin = encounterHexes.find((hex) => hex.name === player.location);
  if (!origin) return [...encounterHexes];
  const nearby = encounterHexes.filter((hex) => hexDistance(origin, hex) <= 3);
  return nearby.length > 0 ? nearby : [...encounterHexes];
}

export function instantiateEncounterTemplate(
  template: EncounterTemplate,
  player: PlayerEntity,
): TableauCard {
  const difficulty = template.base_difficulty + difficultySwing();
  const nearbyHexes = hexesNearPlayer(player);
  const skillSource = template.skills.length > 0 ? template.skills : skillNames;

  const locationCandidates =
    nearbyHexes.length > 0 ? nearbyHexes : encounterHexes;
  const successThreshold = 2;
  const criticalThreshold = 3;
  const failureThreshold = Math.max(0, successThreshold - 2);
  return {
    id: randomUUID(),
    title: template.title,
    location:
      locationCandidates.length > 0
        ? randomPick(locationCandidates).name
        : player.location,
    difficulty,
    successThreshold,
    criticalThreshold,
    failureThreshold,
    rewards: [...template.rewards],
    criticalRewards: [...template.criticalRewards],
    penalties: [...template.penalties],
    skillChecks: [0, 1, 2].map(() => {
      const skillPool = encounterRng.next() < 0.9 ? skillSource : skillNames;
      const target = 4 + difficulty + difficultySwing();
      return {
        name: randomPick(skillPool),
        target,
      };
    }),
  };
}
