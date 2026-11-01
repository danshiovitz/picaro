import { rulesBySection } from "./data.js";
import { PlayerEntity, RuleType, SectionType } from "./types.js";

const skillXpThresholds = [0, 10, 30, 50, 75, 100, 130];

function skillLevelFromXp(xp: number) {
  let level = 0;
  for (let i = 0; i < skillXpThresholds.length; i++) {
    if (xp >= skillXpThresholds[i]) level = i;
  }
  return level;
}

export function getFieldValue(
  player: PlayerEntity,
  section: SectionType,
  subsection?: string,
) {
  switch (section) {
    case SectionType.speed:
      return player.speed;
    case SectionType.maxHealth:
      return player.maxHealth;
    case SectionType.skill:
      return skillLevelFromXp(player.skill_xp[subsection ?? ""] ?? 0);
    default: {
      const exhaustiveCheck: never = section;
      throw new Error(`Unsupported section: ${exhaustiveCheck}`);
    }
  }
}

function rulesForSection(
  section: SectionType,
  subsection: string | undefined,
  type: RuleType,
) {
  return rulesBySection.get(section)?.get(subsection)?.get(type) ?? [];
}

export function computeEffectiveValue(
  player: PlayerEntity,
  section: SectionType,
  subsection?: string,
) {
  let retval = getFieldValue(player, section, subsection);

  for (const rule of rulesForSection(section, subsection, RuleType.BaseValue)) {
    if (rule.condition(player)) {
      retval = rule.value(player);
      break;
    }
  }

  for (const rule of rulesForSection(
    section,
    subsection,
    RuleType.ModifierValue,
  )) {
    if (rule.condition(player)) retval += rule.value(player);
  }

  return retval;
}
