import { EffectType } from "./types";
import type { ActivityResult, Effect } from "./types";

export type ActivityKind =
  "Selection" | "Action" | "Encounter" | "Camp" | "Travel";

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
  if (effect.type === EffectType.RemoveItems) {
    const names = await Promise.all(
      effect.itemIds.map(
        async (itemId) => (await resolveItemName?.(itemId)) ?? itemId,
      ),
    );
    return `Removed: ${names.join(", ") || "none"}`;
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
  return type[0].toUpperCase() + type.slice(1);
}
