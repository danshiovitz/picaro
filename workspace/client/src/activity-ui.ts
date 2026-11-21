import { EffectType } from "./types";
import type { Notification, Effect } from "./types";

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
    const name = effect.itemId
      ? ((await resolveItemName?.(effect.itemId)) ?? effect.itemId)
      : undefined;
    return `Gained: ${name ? `a ${name}` : "a random item"}`;
  }
  if (effect.type === EffectType.RemoveRandomItem) {
    const name = effect.itemId
      ? ((await resolveItemName?.(effect.itemId)) ?? effect.itemId)
      : undefined;
    return `Removed: ${name ? `a ${name}` : "a random item"}`;
  }
  if (effect.type === EffectType.AddTableauCard) {
    return "Added tableau card";
  }
  if (effect.type === EffectType.RefreshTableau) {
    return "Refreshed tableau";
  }
  if (effect.type === EffectType.Teleport) {
    return `Teleported to: ${effect.centerHex}`;
  }
  return `${effect.amount >= 0 ? "+" : "-"}${Math.abs(effect.amount)} ${labelForType(effect.type)}`;
}

export async function renderActivityLines(
  result: Notification,
  resolveItemName?: ItemNameResolver,
) {
  const lines: string[] = [];
  if (result.flavorText)
    lines.push(
      ...result.flavorText.split(/\n+/).filter((line) => line.length > 0),
    );
  if (result.effects?.length)
    lines.push(
      ...(await Promise.all(
        result.effects.map((effect) =>
          renderEffectText(effect, resolveItemName),
        ),
      )),
    );
  if (!result.flavorText && (result.effects?.length ?? 0) === 0)
    lines.push("Action Complete");
  return lines;
}

function labelForType(type: string) {
  if (type === EffectType.FreeXp) return "Free XP";
  if (type === EffectType.ControlledTeleport || type === EffectType.Teleport)
    return "Teleport";
  if (type === EffectType.GainRandomItem || type == EffectType.RemoveRandomItem)
    return "Item";
  if (type === EffectType.AddTableauCard) return "Tableau Card";
  if (type === EffectType.RefreshTableau) return "Tableau Refresh";
  return type[0].toUpperCase() + type.slice(1);
}
