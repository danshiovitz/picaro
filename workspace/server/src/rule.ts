import { rulesBySection } from "./data.js";
import { PlayerEntity, RuleType, SectionType } from "./types.js";

export function getFieldValue(player: PlayerEntity, section: SectionType) {
  switch (section) {
    case SectionType.speed:
      return player.speed;
    case SectionType.maxHealth:
      return player.maxHealth;
    case SectionType.skill:
      return 0;
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
  let retval = getFieldValue(player, section);

  if (section === SectionType.skill) {
    retval = player.skills[subsection ?? ""] ?? 0;
  }

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
