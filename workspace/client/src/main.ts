import { entityEntries, getField, hydrateEntity, setField } from "./entity";
import { SCHEMAS, resolveSchemaFields } from "./schemas";
import { GameStore } from "./store";
import { EffectType, PenaltyType, RewardType, RuleScope } from "./types";
import { renderActivityLines } from "./activity-ui";
import type {
  ActivityNextActive,
  Notification,
  AnnotatedValue,
  ActiveEncounter,
  Effect,
  EncounterSkillCheck,
  GameData,
  Hex,
  Condition,
  Item,
  Token,
  PlayerEntity,
  Selection,
  AvailableSpecialAction,
  SpecialAction,
  TableauCard,
  TableauData,
} from "./types";
import { hexDistance } from "@common/hexmap.js";

const API = import.meta.env.VITE_API_URL ?? "";
const url = new URL(window.location.href);
let playerId = url.searchParams.get("player") ?? "";
const app = document.querySelector("#app")!;
let activeEncounterId: string | null = null;

window.addEventListener("error", (event) => {
  console.error("[client error]", event.error ?? event.message);
  if (event.error instanceof Error && event.error.stack)
    console.error(event.error.stack);
});
window.addEventListener("unhandledrejection", (event) => {
  console.error("[client unhandledrejection]", event.reason);
  if (event.reason instanceof Error && event.reason.stack)
    console.error(event.reason.stack);
});

type Point = { x: number; y: number };

function withPlayerParam(path: string) {
  const hashIndex = path.indexOf("#");
  const hash = hashIndex >= 0 ? path.slice(hashIndex) : "";
  const base = hashIndex >= 0 ? path.slice(0, hashIndex) : path;
  const queryIndex = base.indexOf("?");
  const pathname = queryIndex >= 0 ? base.slice(0, queryIndex) : base;
  const search = queryIndex >= 0 ? base.slice(queryIndex + 1) : "";
  const params = new URLSearchParams(search);
  if (playerId) params.set("player", playerId);
  const query = params.toString();
  return `${pathname}${query ? `?${query}` : ""}${hash}`;
}

async function apiJson<T>(
  path: string,
  init?: RequestInit,
  attempts = 1,
): Promise<T> {
  let lastError: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      const r = await fetch(`${API}${withPlayerParam(path)}`, init);
      if (!r.ok) {
        let message = `API request failed: ${r.status}`;
        try {
          const body = await r.json();
          message = body?.message ?? body?.error ?? message;
        } catch {}
        throw new Error(message);
      }
      return r.json();
    } catch (err) {
      lastError = err;
      if (i < attempts - 1)
        await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw lastError;
}

(async () => {
  try {
    const game = await apiJson<GameData>("/api/game", undefined, 20);
    const store = new GameStore(game);
    if (!playerId || !store.playerIds.some((pid) => pid === playerId)) {
      playerId = store.playerIds.length > 0 ? store.playerIds[0] : "";
      if (!playerId) throw new Error("No players available");
      url.searchParams.set("player", playerId);
      history.replaceState(null, "", url);
    }
    const [playerRaw, tableau, specialActions] = await Promise.all([
      apiJson<PlayerEntity>(
        `/api/entities/${encodeURIComponent(playerId)}`,
        undefined,
        20,
      ),
      apiJson<TableauData>("/api/tableau", undefined, 20),
      apiJson<AvailableSpecialAction[]>(
        `/api/entities/${encodeURIComponent(playerId)}/special_actions`,
        undefined,
        20,
      ),
    ]);
    render(store, hydrateEntity(playerRaw), tableau, specialActions);
  } catch (err) {
    console.error("[client bootstrap] Failed to load game data");
    console.error(err instanceof Error ? (err.stack ?? err) : err);
    app.innerHTML = `<main style="padding:24px"><h2>Unable to load game data</h2><p>${err instanceof Error ? err.message : String(err)}</p><p>Check that the API server is running on port 3001.</p></main>`;
  }
})();

function esc(value: unknown) {
  return String(value).replace(
    /[&<>"]/g,
    (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]!,
  );
}

function isAnnotatedValue(value: unknown): value is AnnotatedValue {
  return (
    Boolean(value) &&
    typeof value === "object" &&
    value !== null &&
    "finalValue" in value &&
    "baseValue" in value &&
    "modifierValues" in value
  );
}

function finalValue(value: number | AnnotatedValue) {
  return typeof value === "number" ? value : value.finalValue;
}

function annotatedValueTooltip(value: AnnotatedValue) {
  const lines = [
    `${value.baseValue.value} base value from ${value.baseValue.text}`,
  ];
  for (const modifier of value.modifierValues) {
    const prefix = modifier.value >= 0 ? "+" : "";
    lines.push(`${prefix}${modifier.value} ${modifier.text}`);
  }
  lines.push(`=${value.finalValue} final`);
  return lines.join("\n");
}

function renderAnnotatedValue(value: AnnotatedValue, showSign = false) {
  const display =
    showSign && value.finalValue >= 0
      ? `+${value.finalValue}`
      : value.finalValue;
  return `<span class="annotated-value" title="${esc(annotatedValueTooltip(value))}">${esc(display)}</span>`;
}

function renderEntityValue(value: unknown) {
  if (isAnnotatedValue(value)) return renderAnnotatedValue(value);
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  )
    return esc(value);
  if (value == null) return "";
  return esc(JSON.stringify(value));
}

function labelForType(type: string) {
  if (type === RewardType.FreeXp) return "Free XP";
  if (
    type === RewardType.ControlledTeleport ||
    type == PenaltyType.RandomTeleport
  )
    return "Teleport";
  if (type === RewardType.GainItem || type === PenaltyType.RemoveItem)
    return "Item";
  if (type === RewardType.QualityEncounter) return "Encounter";
  return type[0].toUpperCase() + type.slice(1);
}

function skillXpThresholds() {
  return [0, 10, 30, 50, 75, 100, 130];
}

function skillLevelFromXp(xp: number) {
  let level = 0;
  for (const threshold of skillXpThresholds()) {
    if (xp >= threshold) level += 1;
  }
  return Math.max(0, level - 1);
}

function skillXpDisplay(xp: number) {
  const thresholds = skillXpThresholds();
  const level = skillLevelFromXp(xp);
  const current = thresholds[level] ?? thresholds[thresholds.length - 1];
  const next = thresholds[level + 1];
  return {
    level,
    current,
    next: next ?? current,
    text: next ? `${xp}/${next}` : `${xp}/${current}+`,
    fill: next && next > current ? (xp - current) / (next - current) : 1,
  };
}

// Used for displaying costs, so random picks aren't resolved yet
function effectLabel(effect: Effect) {
  if (effect.type === EffectType.Resource)
    return `${labelForType(effect.type)} (${effect.resourceType})`;
  if (effect.type === EffectType.FreeXp) return labelForType(effect.type);
  if (effect.type === EffectType.ControlledTeleport)
    return `${labelForType(effect.type)} (radius ${effect.radius})`;
  if (effect.type === EffectType.Teleport)
    return `${labelForType(effect.type)} (radius ${effect.radius} of ${effect.centerHex})`;
  if (effect.type === EffectType.SkillXp)
    return `xp for ${effect.skill}${effect.newLevel ? ` (now level ${effect.newLevel})` : ""}`;
  if (effect.type === EffectType.RemoveItems)
    return `Remove items (${effect.itemIds.join(", ") || "none"})`;
  if (effect.type === EffectType.GainRandomItem) return `Gain a random item`;
  if (effect.type === EffectType.RemoveRandomItem)
    return `Remove a random item`;
  if (effect.type === EffectType.AddTableauCard) return "Add a tableau card";
  if (effect.type === EffectType.RefreshTableau) return "Refresh the tableau";
  return labelForType(effect.type);
}

function formatEffects(effects: Effect[]) {
  return effects.length
    ? effects
        .map((effect) =>
          effect.type === EffectType.RemoveItems ||
          effect.type === EffectType.ControlledTeleport ||
          effect.type === EffectType.Teleport ||
          effect.type === EffectType.RemoveRandomItem ||
          effect.type === EffectType.GainRandomItem ||
          effect.type === EffectType.AddTableauCard ||
          effect.type === EffectType.RefreshTableau
            ? effectLabel(effect)
            : `${effect.annotatedValue?.finalValue ?? effect.amount} ${effectLabel(effect)}`,
        )
        .join(", ")
    : "none";
}

function canAffordEffects(player: PlayerEntity, effects: Effect[]) {
  return effects.every((effect) => {
    switch (effect.type) {
      case EffectType.FreeXp:
      case EffectType.GainRandomItem:
        return false;
      case EffectType.Gold:
        return player.gold + effect.amount >= 0;
      case EffectType.Reputation:
        return player.reputation + effect.amount >= 0;
      case EffectType.Health:
        return player.curHealth + effect.amount >= 0;
      case EffectType.Turns:
        return player.turns + effect.amount >= 0;
      case EffectType.Luck:
        return player.curLuck + effect.amount >= 0;
      case EffectType.Resource:
        return (
          (player.resources[effect.resourceType] ?? 0) + effect.amount >= 0
        );
      case EffectType.SkillXp:
        return (player.skill_xp[effect.skill] ?? 0) + effect.amount >= 0;
      case EffectType.RemoveItems: {
        const inventoryIds = new Set(
          (player.inventory as Item[]).map((item) => item.id),
        );
        return effect.itemIds.every((itemId) => inventoryIds.has(itemId));
      }
      case EffectType.RemoveRandomItem:
        return player.inventory.length > 0;
      case EffectType.AddTableauCard:
      case EffectType.RefreshTableau:
      case EffectType.ControlledTeleport:
      case EffectType.Teleport:
        return true;
    }
  });
}

function outcomeLine(
  rewards: RewardType[],
  criticalRewards: RewardType[],
  penalties: PenaltyType[],
) {
  const rewardText = (item: RewardType) => `+${labelForType(item)}`;
  const criticalRewardText = (item: RewardType) => `++${labelForType(item)}`;
  const penaltyText = (item: PenaltyType) => `-${labelForType(item)}`;
  const parts = [
    ...rewards.map(rewardText),
    ...criticalRewards.map(criticalRewardText),
    ...penalties.map(penaltyText),
  ];
  return `${parts.join(", ")}`;
}

function skillLine(
  check: EncounterSkillCheck,
  skills: Record<string, number | AnnotatedValue> | undefined,
  showTarget = true,
) {
  const skillValue = skills?.[check.name];
  const skillLabel =
    skillValue !== undefined
      ? `${esc(check.name)} ${renderEntityValue(skillValue)}`
      : esc(check.name);
  return showTarget ? `${skillLabel} vs ${esc(check.target)}` : skillLabel;
}

type EncounterCard = TableauCard;

function renderEncounterPips(difficulty: number, qualityMod = 0) {
  const blackCount = Math.max(0, difficulty - Math.abs(qualityMod));
  const coloredCount = Math.abs(qualityMod);
  const emptyCount = Math.max(0, 5 - difficulty);
  const colorClass =
    qualityMod > 0 ? " positive" : qualityMod < 0 ? " negative" : "";
  return [
    ...Array.from(
      { length: blackCount },
      () => `<span class="encounter-pip filled" aria-hidden="true"></span>`,
    ),
    ...Array.from(
      { length: coloredCount },
      () =>
        `<span class="encounter-pip filled${colorClass}" aria-hidden="true"></span>`,
    ),
    ...Array.from(
      { length: emptyCount },
      () => `<span class="encounter-pip" aria-hidden="true"></span>`,
    ),
  ].join("");
}

function renderEncounterCard(
  card: EncounterCard,
  skills: Record<string, number | AnnotatedValue> | undefined,
) {
  const circles = renderEncounterPips(card.difficulty, card.qualityMod ?? 0);
  const activeClass =
    card.id === activeEncounterId ? " active-tableau-encounter" : "";
  const elementSuffix = card.element ? ` (${card.element[0]})` : "";
  return `<article class="play-card encounter-card tableau-encounter${activeClass}" data-encounter-id="${esc(card.id)}">
  <div class="encounter-header">
   <div class="encounter-title-row">
    <span class="encounter-title">${esc(card.title + elementSuffix)}</span>
   </div>
   <div class="encounter-meta-row">
    <span class="encounter-location">${esc(card.location)}</span>
    <span class="encounter-ranks">${circles}</span>
   </div>
  </div>
  <div class="play-card-body encounter-body">
   <p>${esc(outcomeLine(card.rewards, card.criticalRewards, card.penalties))}</p>
   <div class="encounter-spacer"></div>
   ${card.skillChecks
     .slice(0, 1)
     .map(
       (check) =>
         `<p class="encounter-check">${skillLine(check, skills, false)}</p>`,
     )
     .join("")}
  </div>
 </article>`;
}

function renderActiveEncounterCard(
  card: ActiveEncounter,
  skills: Record<string, number | AnnotatedValue> | undefined,
) {
  const nextPenalty = card.nextPenalty
    ? `<p class="encounter-next-penalty">Next penalty: -${esc(labelForType(card.nextPenalty))}</p>`
    : "";
  const skillChecks = card.currentSkillChecks;
  const elementSuffix = card.element ? ` (${card.element[0]})` : "";
  return `<article class="play-card encounter-card active-encounter-card" data-encounter-id="${esc(card.id)}">
  <div class="encounter-header">
   <div class="encounter-title-row">
    <span class="encounter-title">${esc(card.title + elementSuffix)}</span>
   </div>
  </div>
  <div class="play-card-body encounter-body">
   <p>${esc(outcomeLine(card.rewards, card.criticalRewards, card.penalties))}</p>
   <div class="encounter-spacer"></div>
   ${skillChecks
     .map(
       (check) => `<p class="encounter-check">${skillLine(check, skills)}</p>`,
     )
     .join("")}
   ${nextPenalty}
  </div>
 </article>`;
}

function renderEncounterSummary(card: ActiveEncounter) {
  const successes =
    typeof card.numSuccesses === "number"
      ? card.numSuccesses
      : card.skillChecks.filter((check) => check.success).length;
  const failures =
    typeof card.numFailures === "number"
      ? card.numFailures
      : card.skillChecks.length - successes;
  const successThreshold =
    typeof card.successThreshold === "number"
      ? card.successThreshold
      : successes;
  const hasCriticalThreshold = typeof card.criticalThreshold === "number";
  const criticalThreshold = card.criticalThreshold ?? successThreshold;
  const failureThreshold =
    typeof card.failureThreshold === "number"
      ? card.failureThreshold
      : failures;
  const placeholder = "◦";
  const renderSegment = (filled: number, threshold: number) =>
    `${"✅".repeat(filled)}${placeholder.repeat(Math.max(0, threshold - filled))}`;
  const successSegments = [
    renderSegment(Math.min(successes, successThreshold), successThreshold),
  ];
  if (hasCriticalThreshold) {
    const criticalSpan = Math.max(0, criticalThreshold - successThreshold);
    if (criticalSpan > 0) {
      successSegments.push(
        renderSegment(
          Math.min(Math.max(successes - successThreshold, 0), criticalSpan),
          criticalSpan,
        ),
      );
    }
    if (successes > criticalThreshold)
      successSegments.push(`✅`.repeat(successes - criticalThreshold));
  } else if (successes > successThreshold) {
    successSegments.push(`✅`.repeat(successes - successThreshold));
  }
  const failureSegments = [
    `${"☠️".repeat(Math.min(failures, failureThreshold))}${placeholder.repeat(Math.max(0, failureThreshold - failures))}`,
  ];
  if (failures > failureThreshold)
    failureSegments.push(`☠️`.repeat(failures - failureThreshold));
  return `<dl class="encounter-summary"><div><dt>Successes</dt><dd>${esc(successSegments.join(" / "))}</dd></div><div><dt>Failures</dt><dd>${esc(failureSegments.join(" / "))}</dd></div></dl>`;
}

function renderEncounterResults(card: ActiveEncounter) {
  const skillChecks = card.currentSkillChecks;
  return `<div class="encounter-results">${skillChecks
    .map((check) => {
      const modifier = renderEntityValue(check.modifier);
      return `<p class="encounter-result-line">1d10 (${esc(check.roll)}) + ${modifier} = ${esc(check.total)} .. ${esc(check.success ? "Success!" : "Failure!")}</p>`;
    })
    .join("")}</div>`;
}

function renderSelectionCard(selection: Selection, error = "") {
  const maxChoices = selection.maxChoices ?? 1;
  const instruction =
    selection.minChoices === 0
      ? maxChoices === 1
        ? "Choose one option or cancel."
        : `Choose up to ${maxChoices} options.`
      : selection.minChoices === maxChoices
        ? `Choose ${maxChoices} option${maxChoices === 1 ? "" : "s"}.`
        : `Choose between ${selection.minChoices ?? 1} and ${maxChoices} options.`;
  const choices = selection.useDropdown
    ? `<label class="selection-choice selection-dropdown"><select id="selection-dropdown-${esc(selection.id)}" name="selection-${esc(selection.id)}">${selection.minChoices === 0 ? '<option value="">Choose an option</option>' : ""}${selection.choices
        .map(
          (choice) =>
            `<option value="${esc(choice.index)}">${esc(choice.description)}</option>`,
        )
        .join("")}</select></label>`
    : selection.choices
        .map((choice) => {
          const inputType = maxChoices === 1 ? "radio" : "checkbox";
          return `
        <label class="selection-choice">
          <input type="${inputType}" name="selection-${esc(selection.id)}" value="${esc(choice.index)}" data-choice-index="${esc(choice.index)}" />
          <span>${esc(choice.description)}</span>
        </label>`;
        })
        .join("");
  const description = selection.description
    ? `<p class="selection-description">${esc(selection.description)}</p>`
    : "";
  const errorHtml = error
    ? `<div class="selection-error" role="alert">${esc(error)}</div>`
    : `<div class="selection-error" role="alert"></div>`;
  return `<article class="play-card selection-card"><h3>${esc(selection.title)}</h3><div class="play-card-body selection-body">${description}<p class="selection-instruction">${esc(instruction)}</p><div class="selection-choice-list">${choices}</div></div></article>${errorHtml}<div class="selection-controls"><button id="selection-select" class="card-ok" type="button">Select</button>${selection.minChoices === 0 ? '<button id="selection-cancel" class="card-ok" type="button">Cancel</button>' : ""}</div>`;
}

function render(
  store: GameStore,
  player: PlayerEntity,
  tableau: TableauData,
  initialSpecialActions: AvailableSpecialAction[],
) {
  let tableauData = tableau;
  let encounterById = new Map(
    tableauData.encounters.map(
      (encounter) => [encounter.id, encounter] as const,
    ),
  );
  let encounterByLocation = new Map(
    tableauData.encounters.map(
      (encounter) => [encounter.location, encounter] as const,
    ),
  );
  const itemNameCache = new Map<string, string>();
  for (const item of player.inventory) itemNameCache.set(item.id, item.name);
  app.innerHTML = `<div class="layout"><main><section class="top-strip"><div class="bar"><button id="minus">-</button><span id="z"></span><button id="plus">+</button><label class="map-toggle"><input type="checkbox" id="show-region-borders"/> show region borders</label><button id="fit">Fit</button><button id="snap">Snap</button></div></section><div class="map-shell"><div class="map-pane"><div id="map-scroll"><div id="map"></div><section class="tableau">${tableauData.encounters.map((encounter) => renderEncounterCard(encounter, player.skills)).join("")}</section></div></div></div><section class="character-panel"><section class="character-summary"><h2>Character</h2><div id="character-stats"></div></section><section class="action-section"><div class="action-buttons-row"><button id="travel" class="action-button" type="button"><img src="/images/actions/boots.svg" alt=""/><span>Travel</span></button><button id="camp" class="action-button" type="button"><img src="/images/actions/campfire.svg" alt=""/><span>Camp</span></button><button id="scout" class="action-button" type="button"><img src="/images/actions/telescope.svg" alt=""/><span>Scout</span></button></div><div id="special-actions" class="special-actions"></div></section></section></main><aside class="right-panel"><section class="activity-panel"><h2 id="activity-panel-title" hidden></h2><div id="activity-panel-content"></div></section></aside><footer><b>Log</b><p>Bogus bottom panel: marching orders, dice results, chat, and event feed will appear here.</p></footer></div><div id="tip"></div><div id="entity-popup" class="entity-popup" hidden><div class="entity-popup-backdrop" data-entity-popup-close></div><article class="play-card entity-popup-card"><button id="entity-popup-close" class="entity-popup-close" type="button" aria-label="Close">×</button><div id="entity-popup-content" class="entity-popup-content"></div></article></div>`;
  const map = document.querySelector("#map") as HTMLElement;
  const mapScroll = document.querySelector("#map-scroll") as HTMLElement;
  const tip = document.querySelector("#tip") as HTMLElement;
  const stats = document.querySelector("#character-stats") as HTMLElement;
  const activityPanelTitle = document.querySelector(
    "#activity-panel-title",
  ) as HTMLElement;
  const activityPanelContent = document.querySelector(
    "#activity-panel-content",
  ) as HTMLElement;
  const tableauEl = document.querySelector(".tableau") as HTMLElement;
  const zoomLabel = document.querySelector("#z") as HTMLElement | null;
  const actionButtons = [
    ...document.querySelectorAll(".action-button"),
  ] as HTMLButtonElement[];
  const specialActionsEl = document.querySelector(
    "#special-actions",
  ) as HTMLElement;
  const entityPopup = document.querySelector("#entity-popup") as HTMLElement;
  const entityPopupContent = document.querySelector(
    "#entity-popup-content",
  ) as HTMLElement;
  const entityPopupClose = document.querySelector(
    "#entity-popup-close",
  ) as HTMLButtonElement;
  let zoom = 0.72;
  const size = 44;
  const w = Math.sqrt(3) * size,
    h = 2 * size;
  const svgNS = "http://www.w3.org/2000/svg";
  let route: string[] | null = null;
  let busy = false;
  let manualZoom = false;
  let centerPlayerAfterDraw = false;
  let specialActions = initialSpecialActions;
  let activeEntityPopup: Item | Condition | null = null;

  type OngoingTravelData = {
    route: string[];
    specialActionId: string | null;
    entityId?: string;
    targetHex?: string;
    targetName?: string;
  };
  let ongoingTravel: OngoingTravelData | null = null;
  let activeSelection: Selection | null = null;
  let activityBlocksControls = false;

  function isHexSelectionActive() {
    return Boolean(activeSelection?.hexSelection);
  }

  function updateMapCursor() {
    map.classList.toggle(
      "travel-mode",
      Boolean(route) || isHexSelectionActive(),
    );
  }
  const indexByCoord = new Map(
    store.data.hexes.map((hex, index) => [`${hex.q},${hex.r}`, index] as const),
  );
  const mapBounds = store.data.hexes.reduce(
    (acc, hex) => {
      const { x, y } = hexCenter(hex);
      return {
        minX: Math.min(acc.minX, x - size),
        minY: Math.min(acc.minY, y - size),
        maxX: Math.max(acc.maxX, x + size),
        maxY: Math.max(acc.maxY, y + size),
      };
    },
    { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity },
  );

  function updateActionButtons() {
    const disabled = busy || activityBlocksControls;
    actionButtons.forEach((button) => (button.disabled = disabled));
    tableauEl.classList.toggle("disabled", disabled);
    document
      .querySelectorAll<HTMLButtonElement>(
        "#selection-select, #selection-cancel",
      )
      .forEach((button) => (button.disabled = busy));
    document
      .querySelectorAll<HTMLButtonElement>("[data-special-action-id]")
      .forEach((button) => (button.disabled = disabled));
    renderSpecialActionList();
  }
  function setActivityPanel(
    title: string | null,
    html: string,
    blocksControls = false,
  ) {
    activityBlocksControls = blocksControls;
    activityPanelTitle.hidden = !title;
    activityPanelTitle.textContent = title ?? "";
    activityPanelContent.innerHTML = html;
    updateActionButtons();
  }
  function setPlay(html: string, title: string, blocksControls = false) {
    setActivityPanel(title, html, blocksControls);
  }
  function clearPlay() {
    activeSelection = null;
    activityBlocksControls = false;
    updateMapCursor();
    setActivityPanel(null, "");
  }

  function clearOngoingTravel() {
    ongoingTravel = null;
  }

  function maybeContinueOngoingTravel() {
    if (!ongoingTravel) return false;
    // Find where on the path they are
    const ridx = ongoingTravel.route.findIndex((h) => h == player.location);
    if (ridx == -1) {
      ongoingTravel = null;
      return false;
    }

    // If arrived in destination hex
    if (ridx == ongoingTravel.route.length - 1) {
      if (ongoingTravel.specialActionId) {
        const action = specialActions.find(
          (item) => item.id === ongoingTravel?.specialActionId,
        );
        if (!action) return false;
        showSpecialActionPrompt(
          action,
          ongoingTravel.targetName ?? player.location,
          ongoingTravel.entityId,
        );
        ongoingTravel = null;
        return true;
      } else {
        ongoingTravel = null;
        return false;
      }
    }

    ongoingTravel.route = ongoingTravel.route.slice(
      ridx,
      ongoingTravel.route.length,
    );
    route = ongoingTravel.route;
    showTravelCard();
    return true;
  }

  function validateSelectionLocally(
    selection: Selection,
    selectedIndexes: number[],
  ) {
    const minChoices = selection.minChoices ?? 1;
    const maxChoices = selection.maxChoices ?? 1;
    if (
      selectedIndexes.length < minChoices ||
      selectedIndexes.length > maxChoices
    ) {
      return `Select between ${minChoices} and ${maxChoices} choices.`;
    }
    if (selection.hexSelection) {
      const origin = store.hexes.get(selection.hexSelection.originHex);
      if (!origin) return "Selected origin hex is not valid.";
      const choice = selection.choices.find(
        (item) => item.index === selectedIndexes[0],
      );
      if (!choice) return "Selection choice not found.";
      const target = store.hexes.get(choice.data);
      if (!target) return "Selected hex is not valid.";
      if (hexDistance(origin, target) > selection.hexSelection.radius) {
        return "Selected hex is out of range.";
      }
    }
    return null;
  }

  function selectedSelectionHexName() {
    if (!activeSelection?.hexSelection) return undefined;
    const dropdown = document.querySelector(
      `#selection-dropdown-${CSS.escape(activeSelection.id)}`,
    ) as HTMLSelectElement | null;
    const value = dropdown?.value ?? "";
    if (!value) return undefined;
    const choice = activeSelection.choices.find(
      (item) => String(item.index) === value,
    );
    return choice?.data;
  }

  function selectSelectionHex(hexName: string) {
    if (!activeSelection?.hexSelection) return;
    const choice = activeSelection.choices.find(
      (item) => item.data === hexName,
    );
    if (!choice) return;
    const dropdown = document.querySelector(
      `#selection-dropdown-${CSS.escape(activeSelection.id)}`,
    ) as HTMLSelectElement | null;
    if (dropdown) {
      dropdown.value = String(choice.index);
      dropdown.dispatchEvent(new Event("change", { bubbles: true }));
      draw();
    }
  }

  async function submitSelection(selectedIndexes: number[]) {
    if (!activeSelection) return;
    const selectionId = activeSelection.id;
    activeSelection = null;
    updateMapCursor();
    await executeActivity(() =>
      apiJson<ActivityNextActive>(
        `/api/entities/${encodeURIComponent(player.id)}/actions/make_selection`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            selectionId,
            selectedIndexes,
          }),
        },
      ),
    );
  }

  function showSelection(selection: Selection) {
    activeEncounterId = null;
    activeSelection = selection;
    setActivityPanel("Selection", renderSelectionCard(selection), true);
    updateMapCursor();
    const errorEl = document.querySelector(
      ".selection-error",
    ) as HTMLElement | null;
    const selectButton = document.querySelector(
      "#selection-select",
    ) as HTMLButtonElement | null;
    const cancelButton = document.querySelector(
      "#selection-cancel",
    ) as HTMLButtonElement | null;
    const dropdown = document.querySelector(
      `#selection-dropdown-${CSS.escape(selection.id)}`,
    ) as HTMLSelectElement | null;
    const clearError = () => {
      if (errorEl) errorEl.textContent = "";
    };
    if (selection.useDropdown) {
      dropdown?.addEventListener("change", () => {
        clearError();
        draw();
      });
    } else {
      document
        .querySelectorAll<HTMLInputElement>(
          `input[name="selection-${CSS.escape(selection.id)}"]`,
        )
        .forEach((input) => input.addEventListener("change", clearError));
    }
    cancelButton?.addEventListener("click", () => {
      void submitSelection([]);
    });
    selectButton?.addEventListener("click", () => {
      const selectedIndexes = selection.useDropdown
        ? (() => {
            const value = dropdown?.value ?? "";
            return value === "" ? [] : [Number(value)];
          })()
        : [
            ...document.querySelectorAll<HTMLInputElement>(
              `.selection-card input[name="selection-${CSS.escape(selection.id)}"]:checked`,
            ),
          ].map((input) => Number(input.value));
      const validationError = validateSelectionLocally(
        selection,
        selectedIndexes,
      );
      if (validationError) {
        if (errorEl) errorEl.textContent = validationError;
        return;
      }
      void submitSelection(selectedIndexes);
    });
  }

  function currentLocationHex() {
    return store.hexes.get(player.location);
  }

  function specialActionTarget(action: SpecialAction) {
    if (!action.locations?.length) return undefined;
    const origin = currentLocationHex();
    if (!origin) return action.locations[0];
    let best: { name: string; distance: number } | undefined;
    for (const location of action.locations) {
      const hex = store.hexes.get(location);
      if (!hex) continue;
      const distance = hexDistance(origin, hex);
      if (!best || distance < best.distance)
        best = { name: location, distance };
    }
    return best?.name;
  }

  function specialActionsForHex(hexName: string) {
    return specialActions.filter((action) =>
      action.locations?.includes(hexName),
    );
  }

  function nearbyEntityGroupsForHex(hexName: string) {
    const hex = store.hexes.get(hexName);
    if (!hex) return [];
    const groups = new Map<
      string,
      { entityId: string; name: string; actions: AvailableSpecialAction[] }
    >();
    for (const entity of store.tokensForHex(hex.name)) {
      const actions = specialActions.filter(
        (action) =>
          action.type === RuleScope.NearbyEntity &&
          action.entityId === entity.id,
      );
      if (!actions.length) continue;
      groups.set(entity.id, {
        entityId: entity.id,
        name: entity.name ?? entity.id,
        actions,
      });
    }
    return [...groups.values()];
  }

  function visibleGeneralSpecialActions() {
    const origin = currentLocationHex();
    return specialActions.filter((action) => {
      if (action.type !== RuleScope.General) return false;
      if (!action.locations?.length) return true;
      if (!origin) return false;
      return action.locations.some((location) => {
        const hex = store.hexes.get(location);
        return hex
          ? hexDistance(origin, hex) <= finalValue(player.speed)
          : false;
      });
    });
  }

  function specialActionLabel(action: AvailableSpecialAction) {
    return action.name;
  }

  function renderSpecialActionButton(
    action: AvailableSpecialAction,
    options: {
      targetHex?: string;
      targetName?: string;
      entityId?: string;
    } = {},
  ) {
    const disabled = busy || activityBlocksControls;
    const attrs = [
      `class="special-action-button special-action-link"`,
      `type="button"`,
      `data-special-action-id="${esc(action.id)}"`,
      (options.entityId ?? action.entityId)
        ? `data-special-action-entity-id="${esc(options.entityId ?? action.entityId)}"`
        : "",
      options.targetHex
        ? `data-special-action-target-hex="${esc(options.targetHex)}"`
        : "",
      options.targetName
        ? `data-special-action-target-name="${esc(options.targetName)}"`
        : "",
      disabled ? "disabled" : "",
    ]
      .filter(Boolean)
      .join(" ");
    return `<button ${attrs}>${esc(specialActionLabel(action))}</button>`;
  }

  function renderSpecialActionList() {
    const disabled = busy || activityBlocksControls;
    const generalActions = visibleGeneralSpecialActions();
    const nearbyEntityActions = specialActions.filter(
      (action) => action.type === RuleScope.NearbyEntity,
    );
    const nearbyGroups = new Map<string, AvailableSpecialAction[]>();
    for (const action of nearbyEntityActions) {
      if (!action.entityId) continue;
      const actions = nearbyGroups.get(action.entityId) ?? [];
      actions.push(action);
      nearbyGroups.set(action.entityId, actions);
    }
    const nearbyHtml = [...nearbyGroups.entries()]
      .map(([entityId, actions]) => {
        const entity = store.entity(entityId);
        const name = entity?.name ?? entityId;
        return `<div class="special-action-entity-group"><span class="special-action-entity-name">${esc(name)}</span> ${actions
          .map((action) =>
            renderSpecialActionButton(action, {
              targetHex: player.location,
              targetName: name,
              entityId,
            }),
          )
          .join(" ")}</div>`;
      })
      .join("");
    specialActionsEl.innerHTML =
      generalActions.length || nearbyHtml
        ? `<div class="special-actions-list">${generalActions
            .map((action) => renderSpecialActionButton(action))
            .join(" ")}</div>${nearbyHtml}`
        : "";
    specialActionsEl
      .querySelectorAll<HTMLButtonElement>("button[data-special-action-id]")
      .forEach((button) => {
        button.disabled = disabled;
      });
  }

  async function refreshSpecialActions() {
    try {
      specialActions = await apiJson<AvailableSpecialAction[]>(
        `/api/entities/${encodeURIComponent(player.id)}/special_actions`,
        undefined,
        20,
      );
      renderSpecialActionList();
    } catch (err) {
      console.error(err);
    }
  }

  function specialActionTitle(action: SpecialAction, targetName?: string) {
    if (!targetName) return `Perform ${action.name}?`;
    if (action.type === RuleScope.NearbyEntity) {
      return `Perform ${action.name} with ${targetName}?`;
    }
    if (action.type === RuleScope.Item) {
      return `Perform ${action.name} on ${targetName}?`;
    }
    if (action.locations?.length) {
      return `Perform ${action.name} in hex ${targetName}?`;
    }
    return `Perform ${action.name} on ${targetName}?`;
  }

  function specialActionTargetName(action: AvailableSpecialAction) {
    if (!action.entityId) return undefined;
    if (action.type === RuleScope.Item) {
      return (player.inventory as Item[]).find(
        (item) => item.id === action.entityId,
      )?.name;
    }
    if (action.type === RuleScope.NearbyEntity) {
      if (store.entities.has(action.entityId)) {
        const entity = store.entities.get(action.entityId)! as Token;
        return entity.name;
      }
      return action.entityId;
    }
    return undefined;
  }

  function showSpecialActionPrompt(
    action: SpecialAction,
    targetName?: string,
    entityId?: string,
  ) {
    const canAfford = canAffordEffects(player, action.cost ?? []);
    setPlay(
      `<article class="play-card special-action-card"><h3>${esc(action.name)}</h3><div class="play-card-body"><p>${esc(specialActionTitle(action, targetName))}</p><p class="special-action-cost">Cost: ${esc(formatEffects(action.cost ?? []))}</p></div></article><div class="special-action-controls"><button id="special-action-ok" class="card-ok" type="button"${canAfford ? "" : ' disabled title="You can\'t afford to perform this action." aria-disabled="true"'}>Do Action</button><button id="special-action-cancel" class="card-ok" type="button">Cancel</button></div>`,
      action.name,
      true,
    );
    document
      .querySelector("#special-action-cancel")!
      .addEventListener("click", clearPlay);
    const okButton = document.querySelector(
      "#special-action-ok",
    ) as HTMLButtonElement;
    if (canAfford)
      okButton.addEventListener(
        "click",
        () => void performSpecialAction(action.id, entityId),
      );
  }

  function startSpecialAction(
    action: SpecialAction,
    targetHex: string,
    entityId?: string,
    targetName?: string,
  ) {
    const currentHex = player.location;
    if (currentHex === targetHex) {
      showSpecialActionPrompt(action, targetName ?? targetHex, entityId);
      return;
    }
    ongoingTravel = {
      specialActionId: action.id,
      entityId,
      targetHex,
      targetName: targetName ?? targetHex,
      route: shortestPath(player.location, targetHex),
    };
    enterTravelMode();
    const hex = store.hexes.get(targetHex);
    if (hex) selectRouteHex(hex);
  }

  function specialActionLinkClick(
    actionId: string,
    targetHex?: string,
    entityId?: string,
    targetName?: string,
  ) {
    const action = specialActions.find((item) => item.id === actionId);
    if (!action) return;
    const hexName =
      targetHex ??
      (action?.locations?.length
        ? specialActionTarget(action)
        : player.location);
    if (!hexName) return;
    startSpecialAction(action, hexName, entityId, targetName);
  }

  async function performSpecialAction(
    specialActionId: string,
    entityId?: string,
  ) {
    await executeActivity(() =>
      apiJson<ActivityNextActive>(
        `/api/entities/${encodeURIComponent(player.id)}/actions/special_action`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ specialActionId, entityId }),
        },
      ),
    );
  }

  function handleSpecialActionClick(event: MouseEvent) {
    const button = (event.target as HTMLElement)?.closest(
      "button[data-special-action-id]",
    ) as HTMLButtonElement | null;
    if (!button || button.disabled) return;
    const actionId = button.dataset.specialActionId;
    if (!actionId) return;
    const action = specialActions.find((item) => item.id === actionId);
    if (!action) return;
    const entityId = button.dataset.specialActionEntityId;
    const targetHex = button.dataset.specialActionTargetHex;
    const targetName =
      button.dataset.specialActionTargetName ?? specialActionTargetName(action);
    if (action.type === RuleScope.Item) {
      showSpecialActionPrompt(action, targetName, entityId);
      return;
    }
    if (action.type === RuleScope.NearbyEntity) {
      if (!targetHex) {
        showSpecialActionPrompt(action, targetName, entityId);
        return;
      }
      startSpecialAction(action, targetHex, entityId, targetName);
      return;
    }
    if (targetHex) {
      specialActionLinkClick(actionId, targetHex, entityId, targetName);
      return;
    }
    showSpecialActionPrompt(action, targetName, entityId);
  }

  specialActionsEl.addEventListener("click", handleSpecialActionClick);
  stats.addEventListener("click", handleSpecialActionClick);

  function encounterButtons(card: ActiveEncounter) {
    if (card.state === "active")
      return `<div class="encounter-controls"><button id="encounter-continue" class="card-ok" type="button">Continue</button><button id="encounter-concede" class="card-ok" type="button">Concede</button></div>`;
    if (card.state === "succeeded")
      return `<div class="encounter-controls"><button id="encounter-continue" class="card-ok" type="button">Continue</button><button id="encounter-finish" class="card-ok" type="button">Finish</button></div>`;
    if (card.state === "lost" || card.state == "critical")
      return `<div class="encounter-controls"><button id="encounter-finish" class="card-ok" type="button">Finish</button></div>`;
    return "";
  }

  function setEncounterPanel(card: ActiveEncounter | null) {
    if (!card) {
      activeEncounterId = null;
      syncTableau(tableauData);
      clearPlay();
      return;
    }
    activeEncounterId = card.tableauId ?? card.id;
    syncTableau(tableauData);
    setActivityPanel(
      "Encounter",
      `${renderEncounterSummary(card)}${renderActiveEncounterCard(card, player.skills)}${renderEncounterResults(card)}${encounterButtons(card)}`,
      true,
    );
    document
      .querySelector("#encounter-continue")
      ?.addEventListener("click", () => void continueEncounter(card.id));
    document
      .querySelector("#encounter-concede")
      ?.addEventListener("click", () => void finishEncounter(card.id, true));
    document
      .querySelector("#encounter-finish")
      ?.addEventListener("click", () => void finishEncounter(card.id));
  }
  function hexCenter(hex: Hex): Point {
    return {
      x: Math.sqrt(3) * size * (hex.q + hex.r / 2) + 70,
      y: size * 1.5 * hex.r + 60,
    };
  }
  function hexCorner(center: Point, corner: number): Point {
    const angle = (Math.PI / 180) * (60 * corner - 30);
    return {
      x: center.x + size * Math.cos(angle),
      y: center.y + size * Math.sin(angle),
    };
  }
  function hexCorners(center: Point) {
    return [0, 1, 2, 3, 4, 5].map((corner) => hexCorner(center, corner));
  }
  function regionBorderSegment(a: Hex, b: Hex) {
    const aCorners = hexCorners(hexCenter(a));
    const bCorners = hexCorners(hexCenter(b));
    const matches: Point[] = [];
    const epsilon = 1e-6;
    for (const ac of aCorners) {
      for (const bc of bCorners) {
        if (
          Math.abs(ac.x - bc.x) < epsilon &&
          Math.abs(ac.y - bc.y) < epsilon
        ) {
          matches.push(ac);
        }
      }
    }
    if (matches.length < 2) return null;
    return [matches[0], matches[1]] as const;
  }
  function isAdjacent(a: Hex, b: Hex) {
    return hexDistance(a, b) === 1;
  }
  function clamp(value: number, min: number, max: number) {
    return Math.max(min, Math.min(max, value));
  }

  let collapsedSummarySections = {
    resources: false,
    inventory: false,
    conditions: false,
    skills: false,
    extraFields: false,
  };
  let hideZeroResources = false;
  let hideZeroSkills = false;
  let showRegionBorders = false;

  function renderResources(resources: Record<string, number>) {
    const visibleResources = store.data.resourceTypes.filter(
      (resourceType) =>
        !hideZeroResources || (resources[resourceType] ?? 0) > 0,
    );
    return visibleResources.length
      ? `<ul class="resource-list">${visibleResources
          .map(
            (resourceType) =>
              `<li>${esc(resourceType)}: ${esc(resources[resourceType])}</li>`,
          )
          .join("")}</ul>`
      : `<p class="resource-empty">None</p>`;
  }

  function renderInventory(items: Item[]) {
    const itemActionsById = new Map<string, AvailableSpecialAction[]>();
    for (const action of specialActions) {
      if (action.type !== RuleScope.Item || !action.entityId) continue;
      const actions = itemActionsById.get(action.entityId) ?? [];
      actions.push(action);
      itemActionsById.set(action.entityId, actions);
    }
    return items.length
      ? `<ul class="inventory-list">${items
          .map((item) => {
            const actions = itemActionsById.get(item.id) ?? [];
            const actionHtml = actions.length
              ? ` ${actions
                  .map((action) =>
                    renderSpecialActionButton(action, {
                      targetName: item.name,
                      entityId: item.id,
                    }),
                  )
                  .join(" ")}`
              : "";
            return `<li class="inventory-entry" data-inventory-entity-id="${esc(item.id)}"><span class="inventory-entry-name">${esc(item.name)}</span>${actionHtml}</li>`;
          })
          .join("")}</ul>`
      : `<p class="inventory-empty">None</p>`;
  }

  function renderConditions(conditions: Condition[]) {
    return conditions.length
      ? `<ul class="condition-list">${conditions
          .map((condition) =>
            condition.duration == 1
              ? `<li class="condition-entry" data-condition-entity-id="${esc(condition.id)}"><span class="condition-entry-name">${esc(condition.name)}</span> <span class="condition-entry-duration">(1 turn)</span></li>`
              : `<li class="condition-entry" data-condition-entity-id="${esc(condition.id)}"><span class="condition-entry-name">${esc(condition.name)}</span> <span class="condition-entry-duration">(${esc(condition.duration)} turns)</span></li>`,
          )
          .join("")}</ul>`
      : `<p class="condition-empty">None</p>`;
  }

  function renderSkills(
    skills: Record<string, number | AnnotatedValue> | undefined,
    skillXp: Record<string, number> | undefined,
  ) {
    const safeSkills = skills ?? {};
    const safeSkillXp = skillXp ?? {};
    const visibleSkills = Object.entries(safeSkills)
      .sort(([a], [b]) => a.localeCompare(b))
      .filter(([, value]) => !hideZeroSkills || finalValue(value) !== 0);
    return visibleSkills.length
      ? `<ul class="skill-list">${visibleSkills
          .map(([name, value]) => {
            const xp = safeSkillXp[name] ?? 0;
            const progress = skillXpDisplay(xp);
            const fill = Math.max(0, Math.min(1, progress.fill));
            return `<li class="skill-row"><div class="skill-top-row"><span class="skill-name">${esc(name)}</span><span class="skill-value">${renderEntityValue(value)}</span></div><div class="skill-bottom-row"><span class="skill-bar" aria-hidden="true"><span class="skill-bar-fill" style="width: ${Math.round(fill * 100)}%"></span></span><span class="skill-xp-text">${esc(progress.text)}</span></div></li>`;
          })
          .join("")}</ul>`
      : `<p class="skill-empty">None</p>`;
  }

  function renderSummarySection(
    key: keyof typeof collapsedSummarySections,
    title: string,
    body: string,
  ) {
    const collapsed = collapsedSummarySections[key];
    return `<section class="summary-section ${collapsed ? "collapsed" : "expanded"}" data-summary-section="${esc(key)}"><div class="summary-section-header"><span>${esc(title)}</span><button class="summary-toggle" type="button" data-summary-toggle="${esc(key)}" aria-label="${collapsed ? "Expand" : "Collapse"} ${esc(title)}">${collapsed ? "+" : "−"}</button></div><div class="summary-section-body">${body}</div></section>`;
  }

  function renderExtraFields(entity: PlayerEntity) {
    const known = new Set([
      "id",
      "schemaId",
      "data",
      "name",
      "icon",
      "curHealth",
      "maxHealth",
      "curLuck",
      "maxLuck",
      "speed",
      "gold",
      "reputation",
      "turns",
      "location",
      "resources",
      "inventory",
      "conditions",
      "skill_xp",
      "skills",
    ]);
    const extra = entityEntries(entity)
      .filter(([key]) => !known.has(key))
      .sort(([a], [b]) => a.localeCompare(b));
    return extra.length
      ? `<ul class="extra-fields-list">${extra
          .map(
            ([key, value]) =>
              `<li><span class="extra-field-name">${esc(key)}</span>: <span class="extra-field-value">${renderEntityValue(value)}</span></li>`,
          )
          .join("")}</ul>`
      : `<p class="extra-fields-empty">None</p>`;
  }

  function renderSummary() {
    stats.innerHTML = `<div class="summary-basic"><div><dd>${esc(player.name)}</dd></div><div><dt>Location</dt><dd>${esc(player.location)}</dd></div><div><dt>Health</dt><dd>${player.curHealth}/${renderEntityValue(player.maxHealth)}</dd></div><div><dt>Luck</dt><dd>${player.curLuck}/${renderEntityValue(player.maxLuck)}</dd></div><div><dt>Speed</dt><dd>${renderEntityValue(player.speed)}</dd></div><div><dt>Gold</dt><dd>${player.gold}</dd></div><div><dt>Reputation</dt><dd>${player.reputation}</dd></div><div><dt>Turns</dt><dd>${player.turns}</dd></div></div>${renderSummarySection("resources", "Resources", `<label class="skills-filter"><input type="checkbox" id="hide-zero-resources"${hideZeroResources ? " checked" : ""}/> hide 0 resources</label>${renderResources(player.resources)}`)}${renderSummarySection("inventory", "Inventory", renderInventory(player.inventory))}${renderSummarySection("conditions", "Conditions", renderConditions(player.conditions))}${renderSummarySection("skills", "Skills", `<label class="skills-filter"><input type="checkbox" id="hide-zero-skills"${hideZeroSkills ? " checked" : ""}/> hide 0 skills</label>${renderSkills(player.skills, player.skill_xp)}`)}${renderSummarySection("extraFields", "Additional Fields", renderExtraFields(player))}`;
    stats
      .querySelectorAll<HTMLButtonElement>("[data-summary-toggle]")
      .forEach((button) => {
        button.addEventListener("click", () => {
          const key = button.dataset.summaryToggle as
            keyof typeof collapsedSummarySections | undefined;
          if (!key) return;
          collapsedSummarySections = {
            ...collapsedSummarySections,
            [key]: !collapsedSummarySections[key],
          };
          renderSummary();
        });
      });
    stats
      .querySelector("#hide-zero-resources")
      ?.addEventListener("change", (event) => {
        hideZeroResources = (event.target as HTMLInputElement).checked;
        renderSummary();
      });
    stats
      .querySelector("#hide-zero-skills")
      ?.addEventListener("change", (event) => {
        hideZeroSkills = (event.target as HTMLInputElement).checked;
        renderSummary();
      });
  }

  function formatSignedNumber(value: number) {
    return `${value >= 0 ? "+" : ""}${value}`;
  }

  function hideEntityPopup() {
    activeEntityPopup = null;
    entityPopup.hidden = true;
    entityPopupContent.innerHTML = "";
  }

  function valueEquals(a: unknown, b: unknown) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  function showEntityPopup(entity: Item | Condition) {
    activeEntityPopup = entity;
    const schemaId =
      entity.schemaId ?? ("duration" in entity ? "condition" : "item");
    const schemaFields = resolveSchemaFields(SCHEMAS, schemaId);
    const title = getField(entity, "name") || "Entity";
    const headerLines: string[] = [];
    const bodyLines: string[] = [];

    if (schemaId === "item" && getField(entity as Item, "is_artifact")) {
      headerLines.push(`<div class="entity-popup-subtitle">Artifact</div>`);
    }
    if (schemaId === "condition") {
      const duration = Number(getField(entity as Condition, "duration"));
      if (duration !== 0) {
        headerLines.push(
          `<div class="entity-popup-subtitle">Duration: ${esc(duration)} turn${duration === 1 ? "" : "s"}</div>`,
        );
      }
    }

    bodyLines.push(`<p class="entity-popup-id">id ${esc(entity.id)}</p>`);
    for (const [fieldName, field] of Object.entries(schemaFields)) {
      if (fieldName === "name") continue;
      const value = (entity as Record<string, unknown>)[fieldName];
      if (value === undefined || valueEquals(value, field.defaultValue))
        continue;
      if (entity.schemaId === "item" && fieldName === "speed_boost") {
        bodyLines.push(
          `<p class="entity-popup-ability">Speed bonus: ${esc(formatSignedNumber(Number(value)))}</p>`,
        );
      } else if (entity.schemaId === "item" && fieldName === "is_artifact") {
        continue;
      } else if (entity.schemaId === "item" && fieldName === "use_function") {
        bodyLines.push(
          `<p class="entity-popup-ability">Use function: ${esc(value)}</p>`,
        );
      } else if (entity.schemaId === "condition" && fieldName === "duration") {
        continue;
      } else {
        const label = fieldName
          .split("_")
          .join(" ")
          .replace(/\b\w/g, (ch: string) => ch.toUpperCase());
        bodyLines.push(
          `<p class="entity-popup-ability">${esc(label)}: ${renderEntityValue(value)}</p>`,
        );
      }
    }

    entityPopupContent.innerHTML = `
      <div class="entity-popup-header">
        <h3 class="entity-popup-title">${esc(title)}</h3>
        ${headerLines.join("")}
      </div>
      <div class="entity-popup-body">
        ${bodyLines.join("")}
      </div>
    `;
    entityPopup.hidden = false;
  }

  function showActivityError(message: string) {
    const title = "Error";
    setPlay(
      `<article class="play-card error-card"><h3>${esc(title)}</h3><div class="play-card-body"><p>${esc(message)}</p></div></article><button id="card-ok" class="card-ok" type="button">OK</button>`,
      title,
      false,
    );
    document.querySelector("#card-ok")!.addEventListener("click", clearPlay);
  }

  async function showNotification(notification: Notification) {
    const title = notification.title ?? "Results";
    const lines = await renderActivityLines(notification, async (itemId) => {
      const cached = itemNameCache.get(itemId);
      if (cached) return cached;
      try {
        const item = await apiJson<Item>(
          `/api/items/${encodeURIComponent(itemId)}`,
          undefined,
          20,
        );
        itemNameCache.set(itemId, item.name);
        return item.name;
      } catch {
        return undefined;
      }
    });
    setPlay(
      `<article class="play-card"><h3>${esc(title)}</h3><div class="play-card-body">${lines
        .map((line) => `<p>${line}</p>`)
        .join(
          "",
        )}</div></article><button id="card-ok" class="card-ok" type="button">OK</button>`,
      title,
      true,
    );

    document
      .querySelector("#card-ok")!
      .addEventListener("click", () => void ackNotification(notification.id));
  }

  function syncTableau(next: TableauData) {
    tableauData = next;
    encounterById = new Map(
      tableauData.encounters.map(
        (encounter) => [encounter.id, encounter] as const,
      ),
    );
    encounterByLocation = new Map(
      tableauData.encounters.map(
        (encounter) => [encounter.location, encounter] as const,
      ),
    );
    tableauEl.innerHTML = tableauData.encounters
      .map((encounter) => renderEncounterCard(encounter, player.skills))
      .join("");
  }

  async function refreshActivityState(previousLocation = player.location) {
    const updatedPlayer = hydrateEntity(
      await apiJson<PlayerEntity>(
        `/api/entities/${encodeURIComponent(player.id)}`,
        undefined,
        20,
      ),
    );
    for (const [key, value] of entityEntries(updatedPlayer)) {
      setField(player, key as keyof PlayerEntity, value as never);
    }
    for (const item of getField(updatedPlayer, "inventory"))
      itemNameCache.set(item.id, item.name);
    if (getField(updatedPlayer, "location") !== previousLocation) {
      store.moveToken(
        player.id,
        previousLocation,
        getField(updatedPlayer, "location"),
      );
    }
    const updatedTableau = await apiJson<TableauData>(
      "/api/tableau",
      undefined,
      20,
    );
    syncTableau(updatedTableau);
    await refreshSpecialActions();
    renderSummary();
    draw();
  }

  async function executeActivity(
    request: () => Promise<ActivityNextActive>,
    onComplete: (result: ActivityNextActive) => void = () => {},
  ) {
    busy = true;
    updateActionButtons();
    try {
      const result = await request();
      await refreshActivityState();
      await onComplete(result);
      showNextActivity(result);
    } catch (err) {
      console.error(err);
      showActivityError(err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
      updateActionButtons();
    }
  }

  function showNextActivity(result: ActivityNextActive | undefined) {
    if (!result) {
      if (!maybeContinueOngoingTravel()) {
        clearPlay();
      }
    } else if (result.type === "selection") {
      showSelection(result.selection);
    } else if (result.type === "encounter") {
      showActiveEncounter(result.encounter);
    } else if (result.type === "notification") {
      showNotification(result.notification);
    } else {
      console.error("Unknown result type", result);
      clearPlay();
    }
  }

  function showEncounterPreview(card: EncounterCard) {
    const canAfford = canAffordEffects(player, [
      { type: EffectType.Turns, amount: 1 },
    ]);
    setPlay(
      `${renderEncounterCard(card, player.skills)}<div class="encounter-controls"><button id="encounter-ok" class="card-ok" type="button"${canAfford ? "" : ' disabled title="You\'re out of turns." aria-disabled="true"'}>OK</button><button id="encounter-cancel" class="card-ok" type="button">Cancel</button></div>`,
      "Encounter",
      true,
    );
    document
      .querySelector("#encounter-cancel")!
      .addEventListener("click", clearPlay);
    if (canAfford)
      document
        .querySelector("#encounter-ok")!
        .addEventListener("click", () => void runEncounter(card.id));
  }

  function showActiveEncounter(card: ActiveEncounter) {
    clearPlay();
    setEncounterPanel(card);
  }

  async function ackNotification(notificationId: string) {
    await executeActivity(() =>
      apiJson<ActivityNextActive>(
        `/api/entities/${encodeURIComponent(player.id)}/actions/ack_notification`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notificationId: notificationId }),
        },
      ),
    );
  }

  async function runEncounter(encounterId: string) {
    await executeActivity(() =>
      apiJson<ActivityNextActive>(
        `/api/entities/${encodeURIComponent(player.id)}/actions/run_encounter`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ encounterId, tableauId: encounterId }),
        },
      ),
    );
  }

  async function continueEncounter(encounterId: string) {
    await executeActivity(() =>
      apiJson<ActivityNextActive>(
        `/api/entities/${encodeURIComponent(player.id)}/actions/continue_encounter`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ encounterId, tableauId: encounterId }),
        },
      ),
    );
  }

  async function finishEncounter(encounterId: string, conceding = false) {
    await executeActivity(
      () =>
        apiJson<ActivityNextActive>(
          `/api/entities/${encodeURIComponent(player.id)}/actions/finish_encounter`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              encounterId,
              tableauId: encounterId,
              conceding,
            }),
          },
        ),
      (result) => {
        activeEncounterId = null;
        setEncounterPanel(null);
      },
    );
  }

  function enterTravelMode() {
    if (busy || activityBlocksControls) return;
    route = [player.location];
    updateMapCursor();
    tip.style.display = "none";
    showTravelCard();
    draw();
  }

  function showCampCard() {
    const canAfford = canAffordEffects(player, [
      { type: EffectType.Turns, amount: 1 },
    ]);
    setPlay(
      `<article class="play-card camp-card"><h3>Camp</h3><div class="play-card-body"><img src="/images/actions/campfire.svg" alt="Campfire" style="width:120px;height:120px;object-fit:contain"/></div></article><div class="travel-controls"><button id="camp-go" class="card-ok" type="button"${canAfford ? "" : ' disabled title="You\'re out of turns." aria-disabled="true"'}>OK</button><button id="camp-cancel" class="card-ok" type="button">Cancel</button></div>`,
      "Camp",
      true,
    );
    document
      .querySelector("#camp-cancel")!
      .addEventListener("click", clearPlay);
    if (canAfford)
      document.querySelector("#camp-go")!.addEventListener("click", goCamp);
  }

  function showScoutCard() {
    const canAfford = canAffordEffects(player, [
      { type: EffectType.Turns, amount: 1 },
    ]);
    setPlay(
      `<article class="play-card camp-card"><h3>Scout</h3><div class="play-card-body"><img src="/images/actions/telescope.svg" alt="Telescope" style="width:120px;height:120px;object-fit:contain"/></div></article><div class="travel-controls"><button id="scout-go" class="card-ok" type="button"${canAfford ? "" : ' disabled title="You\'re out of turns." aria-disabled="true"'}>OK</button><button id="scout-cancel" class="card-ok" type="button">Cancel</button></div>`,
      "Scout",
      true,
    );
    document
      .querySelector("#scout-cancel")!
      .addEventListener("click", clearPlay);
    if (canAfford)
      document.querySelector("#scout-go")!.addEventListener("click", goScout);
  }

  function travelRouteHtml() {
    const maxNodes = finalValue(player.speed) + 1;
    return route!
      .map((hexName, index) => {
        const cls = index >= maxNodes ? ' class="travel-route-future"' : "";
        return `<span${cls}>${esc(hexName)}</span>`;
      })
      .join(" - ");
  }

  function showTravelCard() {
    const canAfford = canAffordEffects(player, [
      { type: EffectType.Turns, amount: 1 },
    ]);
    setPlay(
      `<article class="play-card travel-card"><h3>Travel</h3><div class="play-card-body route-body"><p>${travelRouteHtml()}</p></div></article><div class="travel-controls"><button id="travel-go" class="card-ok" type="button"${canAfford ? "" : ' disabled title="You\'re out of turns." aria-disabled="true"'}>Go</button><button id="travel-cancel" class="card-ok" type="button">Cancel</button></div>`,
      "Travel",
      true,
    );
    document
      .querySelector("#travel-cancel")!
      .addEventListener("click", exitTravelMode);
    if (canAfford)
      document.querySelector("#travel-go")!.addEventListener("click", goTravel);
  }

  async function goCamp() {
    await executeActivity(() =>
      apiJson<ActivityNextActive>(
        `/api/entities/${encodeURIComponent(player.id)}/actions/camp`,
        { method: "POST" },
      ),
    );
  }

  async function goScout() {
    await executeActivity(() =>
      apiJson<ActivityNextActive>(
        `/api/entities/${encodeURIComponent(player.id)}/actions/scout`,
        { method: "POST" },
      ),
    );
  }

  function exitTravelMode() {
    route = null;
    clearOngoingTravel();
    updateMapCursor();
    clearPlay();
    draw();
  }

  function shortestPath(fromName: string, toName: string) {
    const start = store.hexes.get(fromName),
      target = store.hexes.get(toName);
    if (!start || !target) return [fromName];
    const queue = [start];
    const cameFrom = new Map<string, string | null>([[start.name, null]]);
    const dirs = [
      [1, 0],
      [1, -1],
      [0, -1],
      [-1, 0],
      [-1, 1],
      [0, 1],
    ];
    for (let qi = 0; qi < queue.length; qi++) {
      const current = queue[qi];
      if (current.name === target.name) break;
      for (const [dq, dr] of dirs) {
        const next = store.data.hexes.find(
          (h) => h.q === current.q + dq && h.r === current.r + dr,
        );
        if (next && !cameFrom.has(next.name)) {
          cameFrom.set(next.name, current.name);
          queue.push(next);
        }
      }
    }
    if (!cameFrom.has(target.name)) return [fromName];
    const path: string[] = [];
    for (
      let name: string | null = target.name;
      name;
      name = cameFrom.get(name) ?? null
    )
      path.push(name);
    return path.reverse();
  }

  function selectRouteHex(hex: Hex) {
    if (!route) return;
    const existing = route.indexOf(hex.name);
    if (existing >= 0) route = route.slice(0, existing + 1);
    else {
      const last = store.hexes.get(route[route.length - 1])!;
      if (isAdjacent(last, hex)) route.push(hex.name);
      else route.push(...shortestPath(last.name, hex.name).slice(1));
    }
    showTravelCard();
    draw();
  }

  async function goTravel() {
    if (!route) return;
    const submittedRoute = route.slice(0, finalValue(player.speed) + 1);
    const destination = route[route.length - 1];
    const remainingRoute =
      route.length > submittedRoute.length
        ? route.slice(submittedRoute.length - 1)
        : undefined;
    route = null;
    map.classList.remove("travel-mode");
    draw();
    await executeActivity(
      () =>
        apiJson<ActivityNextActive>(
          `/api/entities/${encodeURIComponent(player.id)}/actions/travel`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ route: submittedRoute }),
          },
        ),
      (result) => {
        const arrivedHex = player.location;
        if (remainingRoute?.length) {
          ongoingTravel = {
            route: remainingRoute,
            specialActionId: ongoingTravel
              ? ongoingTravel.specialActionId
              : null,
          };
        }
      },
    );
  }

  function fitInitialZoom() {
    const padding = 90;
    const boundsWidth = Math.max(
      1,
      mapBounds.maxX - mapBounds.minX + padding * 2,
    );
    const boundsHeight = Math.max(
      1,
      mapBounds.maxY - mapBounds.minY + padding * 2,
    );
    const availableWidth = Math.max(1, mapScroll.clientWidth - 24);
    const availableHeight = Math.max(
      1,
      mapScroll.clientHeight - tableauEl.offsetHeight - 24,
    );
    zoom = Math.max(
      0.05,
      Math.min(
        1.6,
        Math.min(availableWidth / boundsWidth, availableHeight / boundsHeight),
      ),
    );
  }

  function centerOnPlayer() {
    const padding = 90;
    const hex = store.hexes.get(player.location);
    if (!hex) return;
    const { x, y } = hexCenter(hex);
    const left = (x - (mapBounds.minX - padding)) * zoom;
    const top = (y - (mapBounds.minY - padding)) * zoom;
    const viewportWidth = Math.max(1, mapScroll.clientWidth);
    const viewportHeight = Math.max(
      1,
      mapScroll.clientHeight - tableauEl.offsetHeight,
    );
    const maxScrollLeft = Math.max(0, mapScroll.scrollWidth - viewportWidth);
    const maxScrollTop = Math.max(0, mapScroll.scrollHeight - viewportHeight);
    mapScroll.scrollLeft = clamp(left - viewportWidth / 2, 0, maxScrollLeft);
    mapScroll.scrollTop = clamp(top - viewportHeight / 2, 0, maxScrollTop);
  }

  function draw() {
    if (zoomLabel) zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
    const borderCheckbox = document.querySelector(
      "#show-region-borders",
    ) as HTMLInputElement | null;
    if (borderCheckbox) borderCheckbox.checked = showRegionBorders;
    map.innerHTML = "";
    const svg = document.createElementNS(svgNS, "svg");
    const padding = 90;
    const width = Math.max(1, mapBounds.maxX - mapBounds.minX + padding * 2);
    const height = Math.max(1, mapBounds.maxY - mapBounds.minY + padding * 2);
    svg.style.width = `${width * zoom}px`;
    svg.style.height = `${height * zoom}px`;
    svg.setAttribute(
      "viewBox",
      `${mapBounds.minX - padding} ${mapBounds.minY - padding} ${width} ${height}`,
    );
    const defs = document.createElementNS(svgNS, "defs");
    store.data.terrains.forEach((t) => {
      defs.innerHTML += `<pattern id="p-${t.icon}" width="12" height="12" patternUnits="userSpaceOnUse"><image href="/images/terrain/${t.icon}.svg" width="12" height="12"/></pattern>`;
    });
    svg.append(defs);
    const highlightedSelectionHex = selectedSelectionHexName();
    for (const [index, hex] of store.data.hexes.entries()) {
      const { x: cx, y: cy } = hexCenter(hex);
      const terr = store.terrains.get(hex.terrain)!;
      const g = document.createElementNS(svgNS, "g");
      g.classList.add("hex");
      if (highlightedSelectionHex === hex.name)
        g.classList.add("selected-selection-hex");
      g.dataset.name = hex.name;
      const pts = [0, 1, 2, 3, 4, 5]
        .map((i) => {
          const a = (Math.PI / 180) * (60 * i - 30);
          return `${cx + size * Math.cos(a)},${cy + size * Math.sin(a)}`;
        })
        .join(" ");
      g.innerHTML = `<polygon points="${pts}" fill="${terr.color}" stroke="#222"/><polygon points="${pts}" fill="url(#p-${terr.icon})" opacity=".35" stroke="#222"/>`;
      if (zoom > 0.45)
        g.innerHTML += `<text x="${cx}" y="${cy - 24}" text-anchor="middle" class="name">${hex.name}</text>`;
      const toks = store.tokensForHex(hex.name);
      toks.forEach((t, i) => {
        const separate = zoom > 0.38;
        g.innerHTML += `<image href="/images/tokens/${t.icon}.svg" x="${cx - 18 + (separate ? (i - (toks.length - 1) / 2) * 24 : 0)}" y="${cy - 18}" width="36" height="36"/>`;
      });
      if (zoom > 0.55)
        hex.claims.forEach((c, i) => {
          const cl = store.claims.get(c)!;
          g.innerHTML += `<image href="/images/claims/${cl.icon}.svg" x="${cx - 24 + i * 16}" y="${cy + 22}" width="14" height="14"/>`;
        });
      if (
        encounterByLocation.has(hex.name) ||
        specialActions.some((action) => action.locations?.includes(hex.name))
      )
        g.innerHTML += `<text x="${cx}" y="${cy + 10}" text-anchor="middle" class="encounter-star" aria-hidden="true">★</text>`;
      g.onclick = (e) => {
        e.stopPropagation();
        if (isHexSelectionActive()) {
          selectSelectionHex(hex.name);
          return;
        }
        if (activityBlocksControls || busy) return;
        route ? selectRouteHex(hex) : showTip(hex, g.getBoundingClientRect());
      };
      let timer: any;
      g.onmouseenter = () =>
        (timer = setTimeout(() => {
          if (!route && !isHexSelectionActive() && !activityBlocksControls)
            showTip(hex, g.getBoundingClientRect());
        }, 700));
      g.onmouseleave = () => clearTimeout(timer);
      svg.append(g);
    }
    if (showRegionBorders && zoom >= 0.45) {
      const borderOverlay = document.createElementNS(svgNS, "g");
      borderOverlay.classList.add("region-border-overlay");
      for (const [index, hex] of store.data.hexes.entries()) {
        for (const [dq, dr] of [
          [1, 0],
          [1, -1],
          [0, -1],
          [-1, 0],
          [-1, 1],
          [0, 1],
        ] as const) {
          const neighborIndex = indexByCoord.get(`${hex.q + dq},${hex.r + dr}`);
          if (neighborIndex === undefined || neighborIndex <= index) continue;
          const neighbor = store.data.hexes[neighborIndex];
          if (!neighbor || hex.region_id === neighbor.region_id) continue;
          const segment = regionBorderSegment(hex, neighbor);
          if (!segment) continue;
          const [start, end] = segment;
          const line = document.createElementNS(svgNS, "line");
          line.setAttribute("x1", String(start.x));
          line.setAttribute("y1", String(start.y));
          line.setAttribute("x2", String(end.x));
          line.setAttribute("y2", String(end.y));
          line.classList.add("region-border");
          borderOverlay.append(line);
        }
      }
      svg.append(borderOverlay);
    }
    if (route && route.length > 1) {
      const overlay = document.createElementNS(svgNS, "g");
      overlay.classList.add("route-overlay");
      for (let i = 1; i < route.length; i++) {
        const a = store.hexes.get(route[i - 1])!,
          b = store.hexes.get(route[i])!;
        const ac = hexCenter(a),
          bc = hexCenter(b);
        const line = document.createElementNS(svgNS, "line");
        line.setAttribute("x1", String(ac.x));
        line.setAttribute("y1", String(ac.y));
        line.setAttribute("x2", String(bc.x));
        line.setAttribute("y2", String(bc.y));
        overlay.append(line);
      }
      svg.append(overlay);
    }
    map.append(svg);
    if (centerPlayerAfterDraw) {
      centerPlayerAfterDraw = false;
      requestAnimationFrame(() => centerOnPlayer());
    }
  }

  function formatClaims(claims: string[]) {
    const counts = new Map<string, number>();
    for (const claim of claims) counts.set(claim, (counts.get(claim) ?? 0) + 1);
    return [...counts.entries()]
      .map(([name, count]) => (count > 1 ? `${name} (x${count})` : name))
      .join(", ");
  }

  function showTip(hex: Hex, anchor: DOMRect) {
    const f = store.fullHex(hex.name)!;
    const moveHereDisabled = busy || activityBlocksControls;
    const claimsText = formatClaims(
      f.claimObjs
        .filter((claim): claim is NonNullable<typeof claim> => Boolean(claim))
        .map((claim) => claim.name),
    );
    const entityText = f.tokenObjs.map((obj) => obj.name).join(", ");
    const encounter = encounterByLocation.get(hex.name);
    const specialActionsHere = specialActionsForHex(hex.name);
    const nearbyEntityGroups = nearbyEntityGroupsForHex(hex.name);
    const regionStars = f.regionObj
      ? "★".repeat(f.regionObj.base_difficulty)
      : "";
    const lines: [string, string][] = [
      ["Terrain", esc(f.terrain)],
      [
        "Region",
        esc(
          `${f.regionObj?.name ?? ""}${regionStars ? ` ${regionStars}` : ""}`,
        ),
      ],
    ];
    if (claimsText) lines.push(["Claims", esc(claimsText)]);
    if (entityText) lines.push(["Entities", esc(entityText)]);
    if (encounter)
      lines.push([
        "Encounter",
        `<a class="encounter-link" href="#" data-encounter-id="${esc(encounter.id)}">${esc(encounter.title)}</a>`,
      ]);
    if (specialActionsHere.length)
      lines.push([
        "Special Actions",
        specialActionsHere
          .map(
            (action) =>
              `<a class="special-action-popup-link" href="#" data-action-id="${esc(action.id)}" data-target-hex="${esc(hex.name)}">${esc(action.name)}</a>`,
          )
          .join("<br/>"),
      ]);
    if (nearbyEntityGroups.length)
      lines.push([
        "Nearby Actions",
        nearbyEntityGroups
          .map(
            (group) =>
              `<div>${esc(group.name)} ${group.actions
                .map(
                  (action) =>
                    `<a class="special-action-popup-link" href="#" data-action-id="${esc(action.id)}" data-target-hex="${esc(hex.name)}" data-target-name="${esc(group.name)}" data-entity-id="${esc(group.entityId)}">${esc(action.name)}</a>`,
                )
                .join(" ")}</div>`,
          )
          .join("<br/>"),
      ]);
    const details = lines
      .map(([label, value]) => `<p><b>${label}:</b> ${value}</p>`)
      .join("");
    tip.style.display = "block";
    tip.style.visibility = "hidden";
    tip.style.left = "0px";
    tip.style.top = "0px";
    tip.innerHTML = `<button id="close">×</button><h3>${f.name}</h3>${details}<a id="move-here" class="move-here-link" href="#">Move here</a>`;
    const bounds = tip.getBoundingClientRect();
    const gap = 12;
    let x = anchor.right + gap;
    let y = anchor.top;
    if (x + bounds.width > window.innerWidth)
      x = anchor.left - bounds.width - gap;
    if (y + bounds.height > window.innerHeight)
      y = window.innerHeight - bounds.height - gap;
    x = Math.max(gap, x);
    y = Math.max(gap, y);
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
    tip.style.visibility = "visible";
    document
      .querySelector("#close")!
      .addEventListener("click", () => (tip.style.display = "none"));
    const moveHereLink = document.querySelector(
      "#move-here",
    ) as HTMLAnchorElement;
    moveHereLink.classList.toggle("disabled", moveHereDisabled);
    moveHereLink.setAttribute("aria-disabled", String(moveHereDisabled));
    if (moveHereDisabled) moveHereLink.removeAttribute("href");
    else moveHereLink.href = "#";
    moveHereLink.addEventListener("click", (e) => {
      if (moveHereDisabled) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      enterTravelMode();
      if (route) selectRouteHex(hex);
    });
    const encounterLink = document.querySelector(
      ".encounter-link",
    ) as HTMLAnchorElement | null;
    if (encounterLink) {
      encounterLink.classList.toggle("disabled", moveHereDisabled);
      encounterLink.setAttribute("aria-disabled", String(moveHereDisabled));
      encounterLink.addEventListener("click", (e) => {
        if (moveHereDisabled) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        e.preventDefault();
        e.stopPropagation();
        const encounterId = (e.currentTarget as HTMLElement).dataset
          .encounterId;
        const encounter = encounterId
          ? encounterById.get(encounterId)
          : undefined;
        if (encounter) showEncounterPreview(encounter);
      });
    }
    tip.querySelectorAll(".special-action-popup-link").forEach((link) => {
      const specialActionLink = link as HTMLAnchorElement;
      specialActionLink.classList.toggle("disabled", moveHereDisabled);
      specialActionLink.setAttribute("aria-disabled", String(moveHereDisabled));
      specialActionLink.addEventListener("click", (e) => {
        if (moveHereDisabled) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        e.preventDefault();
        e.stopPropagation();
        const actionId = specialActionLink.dataset.actionId;
        const targetHex = specialActionLink.dataset.targetHex;
        const entityId = specialActionLink.dataset.entityId;
        const targetName = specialActionLink.dataset.targetName;
        if (actionId)
          specialActionLinkClick(actionId, targetHex, entityId, targetName);
      });
    });
    tip.querySelectorAll(".special-action-entity-link").forEach((link) => {
      const entityLink = link as HTMLAnchorElement;
      entityLink.classList.toggle("disabled", moveHereDisabled);
      entityLink.setAttribute("aria-disabled", String(moveHereDisabled));
      entityLink.addEventListener("click", (e) => {
        if (moveHereDisabled) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        e.preventDefault();
        e.stopPropagation();
        enterTravelMode();
        if (route) selectRouteHex(hex);
      });
    });
  }

  tableauEl.addEventListener("click", (e) => {
    if (busy || activityBlocksControls) return;
    const card = (e.target as HTMLElement).closest(
      ".tableau-encounter",
    ) as HTMLElement | null;
    if (!card) return;
    const encounterId = card.dataset.encounterId;
    const encounter = encounterId ? encounterById.get(encounterId) : undefined;
    if (encounter) showEncounterPreview(encounter);
  });

  document.addEventListener("click", (e) => {
    if (!(e.target as HTMLElement).closest("#tip")) tip.style.display = "none";
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !entityPopup.hidden) {
      hideEntityPopup();
    }
  });
  entityPopupClose.addEventListener("click", hideEntityPopup);
  entityPopup.addEventListener("click", (e) => {
    if ((e.target as HTMLElement).closest("[data-entity-popup-close]")) {
      hideEntityPopup();
    }
  });
  stats.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    if (target.closest("button[data-special-action-id]")) return;
    const itemEl = target.closest<HTMLElement>("[data-inventory-entity-id]");
    if (itemEl) {
      const item = (player.inventory as Item[]).find(
        (entry) => entry.id === itemEl.dataset.inventoryEntityId,
      );
      if (item) showEntityPopup(item);
      return;
    }
    const conditionEl = target.closest<HTMLElement>(
      "[data-condition-entity-id]",
    );
    if (conditionEl) {
      const condition = (player.conditions as Condition[]).find(
        (entry) => entry.id === conditionEl.dataset.conditionEntityId,
      );
      if (condition) showEntityPopup(condition);
    }
  });
  map.addEventListener("scroll", () => {
    tip.style.display = "none";
  });
  map.onwheel = (e) => {
    e.preventDefault();
    manualZoom = true;
    zoom = Math.max(0.22, Math.min(1.6, zoom + (e.deltaY < 0 ? 0.08 : -0.08)));
    draw();
  };
  document.querySelector("#plus")!.addEventListener("click", () => {
    manualZoom = true;
    zoom = Math.min(1.6, zoom + 0.1);
    draw();
  });
  document.querySelector("#minus")!.addEventListener("click", () => {
    manualZoom = true;
    zoom = Math.max(0.22, zoom - 0.1);
    draw();
  });
  document.querySelector("#fit")!.addEventListener("click", () => {
    manualZoom = false;
    fitInitialZoom();
    draw();
  });
  document
    .querySelector("#show-region-borders")!
    .addEventListener("change", (event) => {
      showRegionBorders = (event.target as HTMLInputElement).checked;
      draw();
    });
  document.querySelector("#snap")!.addEventListener("click", () => {
    manualZoom = true;
    zoom = 1;
    centerPlayerAfterDraw = true;
    draw();
  });
  document.querySelector("#travel")!.addEventListener("click", enterTravelMode);
  document.querySelector("#camp")!.addEventListener("click", showCampCard);
  document.querySelector("#scout")!.addEventListener("click", showScoutCard);
  window.addEventListener("resize", () => {
    if (!manualZoom) {
      fitInitialZoom();
      draw();
    }
  });
  renderSummary();
  updateActionButtons();
  fitInitialZoom();
  draw();
}
