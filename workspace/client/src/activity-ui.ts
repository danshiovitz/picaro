import { EffectType } from "./types";
import type { AnnotatedValue, Notification, Effect } from "./types";

type ItemNameResolver = (
  itemId: string,
) => Promise<string | undefined> | string | undefined;

function esc(value: unknown) {
  return String(value).replace(
    /[&<>"']/g,
    (ch) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[ch]!,
  );
}

function renderAnnotatedValue(value: AnnotatedValue, showSign = false) {
  const display =
    showSign && value.finalValue >= 0
      ? `+${value.finalValue}`
      : value.finalValue;
  return `<span class="annotated-value" title="${esc(
    [
      `${value.baseValue.value} base value from ${value.baseValue.text}`,
      ...value.modifierValues.map(
        (modifier) =>
          `${modifier.value >= 0 ? "+" : ""}${modifier.value} ${modifier.text}`,
      ),
      `=${value.finalValue} final`,
    ].join("\n"),
  )}">${esc(display)}</span>`;
}

export async function renderEffectText(
  effect: Effect,
  resolveItemName?: ItemNameResolver,
) {
  if (
    effect.annotatedValue &&
    (effect.type === EffectType.Gold ||
      effect.type === EffectType.Reputation ||
      effect.type === EffectType.Health ||
      effect.type === EffectType.Luck ||
      effect.type === EffectType.Resource)
  ) {
    const suffix =
      effect.type === EffectType.Resource ? ` (${effect.resourceType})` : "";
    return `${renderAnnotatedValue(effect.annotatedValue, true)} ${labelForType(effect.type)}${suffix}`;
  }
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
    return `Gained: ${name ? `${name}` : "a random item"}`;
  }
  if (effect.type === EffectType.RemoveRandomItem) {
    const name = effect.itemId
      ? ((await resolveItemName?.(effect.itemId)) ?? effect.itemId)
      : undefined;
    return `Removed: ${name ? `${name}` : "a random item"}`;
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
  if (effect.annotatedValue) {
    return `${renderAnnotatedValue(effect.annotatedValue, true)} ${labelForType(effect.type)}`;
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
      ...result.flavorText
        .split(/\n+/)
        .filter((line) => line.length > 0)
        .map((line) => esc(line)),
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
