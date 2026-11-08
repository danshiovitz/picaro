import { EffectType } from "./types";
import type { ActivityResult, Effect } from "./types";

export type ActivityKind =
  "Selection" | "Action" | "Encounter" | "Camp" | "Scout" | "Travel";

export function activityErrorTitle(kind: ActivityKind) {
  return `${kind} Error`;
}

export function activityResultTitle(
  kind: ActivityKind,
  result: ActivityResult,
) {
  return result.title ?? `${kind} Results`;
}

type ItemNameResolver = (
  itemId: string,
) => Promise<string | undefined> | string | undefined;

export async function renderEffectText(
  effect: Effect,
  resolveItemName?: ItemNameResolver,
) {
  if (effect.type === EffectType.Resource)
    return `${effect.amount >= 0 ? "+" : "-"}${Math.abs(effect.amount)} ${labelForType(effect.type)} (${effect.resourceType})`;
  if (effect.type === EffectType.FreeXp)
    return `${effect.amount >= 0 ? "+" : "-"}${Math.abs(effect.amount)} ${labelForType(effect.type)}`;
  if (effect.type === EffectType.ControlledTeleport)
    return `${labelForType(effect.type)} (radius ${effect.radius})`;
  if (effect.type === EffectType.SkillXp)
    return `${effect.amount >= 0 ? "+" : "-"}${Math.abs(effect.amount)} xp for ${effect.skill}${effect.newLevel ? ` (now level ${effect.newLevel})` : ""}`;
  if (effect.type === EffectType.RemoveItems) {
    const names = await Promise.all(
      effect.itemIds.map(
        async (itemId) => (await resolveItemName?.(itemId)) ?? itemId,
      ),
    );
    return `Removed: ${names.join(", ") || "none"}`;
  }
  if (effect.type === EffectType.GainRandomItem) {
    const name =
      (await resolveItemName?.(effect.itemId ?? "no id")) ?? "a random item";
    return `Gained: ${name}`;
  }
  if (effect.type === EffectType.RemoveRandomItem) {
    const name =
      (await resolveItemName?.(effect.itemId ?? "no id")) ?? "a random item";
    return `Removed: ${name}`;
  }
  return `${effect.amount >= 0 ? "+" : "-"}${Math.abs(effect.amount)} ${labelForType(effect.type)}`;
}

export async function renderActivityLines(
  result: ActivityResult,
  resolveItemName?: ItemNameResolver,
) {
  const lines: string[] = [];
  if (result.flavorText)
    lines.push(
      ...result.flavorText.split(/\n+/).filter((line) => line.length > 0),
    );
  if (result.effects.length)
    lines.push(
      ...(await Promise.all(
        result.effects.map((effect) =>
          renderEffectText(effect, resolveItemName),
        ),
      )),
    );
  if (!result.flavorText && result.effects.length === 0 && !result.nextActive)
    lines.push("Action Complete");
  return lines;
}

function labelForType(type: string) {
  if (type === EffectType.FreeXp) return "Free XP";
  if (type === EffectType.ControlledTeleport) return "Teleport";
  if (type === EffectType.GainRandomItem) return "Item";
  if (type === EffectType.RemoveRandomItem) return "Item";
  return type[0].toUpperCase() + type.slice(1);
}
