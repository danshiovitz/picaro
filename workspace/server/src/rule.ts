import { rulesByTypeKey } from "./data.js";
import { getField } from "./entity.js";
import {
  AnnotatedValue,
  PlayerEntity,
  RuleType,
  ValueRuleType,
  ValueType,
} from "./types.js";

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
  valueType: ValueType,
  valueSubtype?: string,
) {
  switch (valueType) {
    case ValueType.speed:
      return getField(player, "speed");
    case ValueType.maxHealth:
      return getField(player, "maxHealth");
    case ValueType.skill:
      return skillLevelFromXp(
        getField(player, "skill_xp")[valueSubtype ?? ""] ?? 0,
      );
    default: {
      const exhaustiveCheck: never = valueType;
      throw new Error(`Unsupported value type: ${exhaustiveCheck}`);
    }
  }
}

function valueKey(valueType: ValueType, valueSubtype?: string) {
  if (valueSubtype) {
    return `${valueType}/${valueSubtype}`;
  } else {
    return valueType;
  }
}

export function computeAnnotatedEffectiveValue(
  player: PlayerEntity,
  valueType: ValueType,
  valueSubtype?: string,
): AnnotatedValue {
  const key = valueKey(valueType, valueSubtype);
  const baseRules = rulesByTypeKey.get(RuleType.BaseValue)?.get(key) ?? [];
  const modRules = rulesByTypeKey.get(RuleType.ModifierValue)?.get(key) ?? [];

  let baseValue = getFieldValue(player, valueType, valueSubtype);
  let baseText = "default";

  for (const rule of baseRules) {
    if (rule.subtype == ValueRuleType.Item) {
      for (const item of getField(player, "inventory")) {
        if (rule.condition(player, item)) {
          baseValue = rule.value(player, item);
          baseText = getField(item, "name");
          break;
        }
      }
    } else {
      if (rule.condition(player)) {
        baseValue = rule.value(player);
        baseText = rule.name;
        break;
      }
    }
  }

  const modifierValues = [] as AnnotatedValue["modifierValues"];
  let finalValue = baseValue;
  for (const rule of modRules) {
    if (rule.subtype == ValueRuleType.Item) {
      for (const item of getField(player, "inventory")) {
        if (rule.condition(player, item)) {
          const value = rule.value(player, item);
          modifierValues.push({ value, text: getField(item, "name") });
          finalValue += value;
        }
      }
    } else {
      if (rule.condition(player)) {
        const value = rule.value(player);
        modifierValues.push({ value, text: rule.name });
        finalValue += value;
      }
    }
  }

  return {
    finalValue,
    baseValue: { value: baseValue, text: baseText },
    modifierValues,
  };
}

export function computeEffectiveValue(
  player: PlayerEntity,
  valueType: ValueType,
  valueSubtype?: string,
) {
  return computeAnnotatedEffectiveValue(player, valueType, valueSubtype)
    .finalValue;
}
