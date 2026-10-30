import { GameStore } from "./store";
import { EffectType } from "./types";
import {
  activityErrorTitle,
  activityResultTitle,
  renderActivityLines,
  type ActivityKind,
} from "./activity-ui";
import type {
  ActivityResult,
  ActivityNextActive,
  ActiveEncounter,
  Effect,
  EncounterSkillCheck,
  GameData,
  Hex,
  Condition,
  Item,
  PenaltyType,
  PlayerEntity,
  RewardType,
  Selection,
  SpecialAction,
  TableauCard,
  TableauData,
} from "./types";

const API = import.meta.env.VITE_API_URL ?? "";
const PLAYER_NAME = "Player 1";
const app = document.querySelector("#app")!;
let activeEncounterId: string | null = null;

type Point = { x: number; y: number };

async function apiJson<T>(
  path: string,
  init?: RequestInit,
  attempts = 1,
): Promise<T> {
  let lastError: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      const r = await fetch(`${API}${path}`, init);
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

Promise.all([
  apiJson<GameData>("/api/game", undefined, 20),
  apiJson<PlayerEntity>(
    `/api/entities/${encodeURIComponent(PLAYER_NAME)}`,
    undefined,
    20,
  ),
  apiJson<TableauData>("/api/tableau", undefined, 20),
  apiJson<SpecialAction[]>("/api/special_actions", undefined, 20),
  apiJson<SpecialAction[]>(
    `/api/entities/${encodeURIComponent(PLAYER_NAME)}/special_actions`,
    undefined,
    20,
  ),
])
  .then(([d, player, tableau, specialActionCatalog, specialActions]) =>
    render(
      new GameStore(d),
      player,
      tableau,
      specialActionCatalog,
      specialActions,
    ),
  )
  .catch((err) => {
    console.error(err);
    app.innerHTML = `<main style="padding:24px"><h2>Unable to load game data</h2><p>${err instanceof Error ? err.message : String(err)}</p><p>Check that the API server is running on port 3001.</p></main>`;
  });

function esc(value: unknown) {
  return String(value).replace(
    /[&<>"]/g,
    (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]!,
  );
}

function labelForType(type: string) {
  return type[0].toUpperCase() + type.slice(1);
}

function effectLabel(effect: Effect) {
  if (effect.type === EffectType.Resource)
    return `${labelForType(effect.type)} (${effect.resourceType})`;
  if (effect.type === EffectType.RemoveItems)
    return `Remove items (${effect.itemIds.join(", ") || "none"})`;
  return labelForType(effect.type);
}

function formatEffects(effects: Effect[]) {
  return effects.length
    ? effects
        .map((effect) =>
          effect.type === EffectType.RemoveItems
            ? effectLabel(effect)
            : `-${effect.amount} ${effectLabel(effect)}`,
        )
        .join(", ")
    : "none";
}

function canAffordEffects(player: PlayerEntity, effects: Effect[]) {
  return effects.every((effect) => {
    switch (effect.type) {
      case EffectType.Gold:
        return player.gold >= effect.amount;
      case EffectType.Reputation:
        return player.reputation >= effect.amount;
      case EffectType.Health:
        return player.curHealth >= effect.amount;
      case EffectType.Turns:
        return player.turns >= effect.amount;
      case EffectType.Luck:
        return player.curLuck >= effect.amount;
      case EffectType.Resource:
        return (player.resources[effect.resourceType] ?? 0) >= effect.amount;
      case EffectType.RemoveItems: {
        const inventoryIds = new Set(player.inventory.map((item) => item.id));
        return effect.itemIds.every((itemId) => inventoryIds.has(itemId));
      }
    }
  });
}

function outcomeLine(
  rewards: RewardType[],
  criticalRewards: RewardType[],
  penalties: PenaltyType[],
) {
  const parts = [
    ...rewards.map((item) => `+${labelForType(item)}`),
    ...criticalRewards.map((item) => `++${labelForType(item)}`),
    ...penalties.map((item) => `-${labelForType(item)}`),
  ];
  return `${parts.join(", ")}`;
}

function skillLine(check: EncounterSkillCheck, showTarget = true) {
  return showTarget ? `${check.name} vs ${check.target}` : check.name;
}

type EncounterCard = TableauCard;

function renderEncounterCard(card: EncounterCard) {
  const circles = Array.from(
    { length: 5 },
    (_, i) =>
      `<span class="encounter-pip ${i < card.difficulty ? "filled" : ""}" aria-hidden="true"></span>`,
  ).join("");
  const activeClass =
    card.id === activeEncounterId ? " active-tableau-encounter" : "";
  return `<article class="play-card encounter-card tableau-encounter${activeClass}" data-encounter-id="${esc(card.id)}">
  <div class="encounter-header">
   <div class="encounter-title-row">
    <span class="encounter-title">${esc(card.title)}</span>
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
         `<p class="encounter-check">${esc(skillLine(check, false))}</p>`,
     )
     .join("")}
  </div>
 </article>`;
}

function renderActiveEncounterCard(card: ActiveEncounter) {
  const nextPenalty = card.nextPenalty
    ? `<p class="encounter-next-penalty">Next penalty: -${esc(labelForType(card.nextPenalty))}</p>`
    : "";
  return `<article class="play-card encounter-card active-encounter-card" data-encounter-id="${esc(card.id)}">
  <div class="encounter-header">
   <div class="encounter-title-row">
    <span class="encounter-title">${esc(card.title)}</span>
   </div>
  </div>
  <div class="play-card-body encounter-body">
   <p>${esc(outcomeLine(card.rewards, card.criticalRewards, card.penalties))}</p>
   <div class="encounter-spacer"></div>
   ${card.skillChecks
     .filter((check) => !check.old)
     .map(
       (check) =>
         `<p class="encounter-check">${esc(`${check.name} vs ${check.target}`)}</p>`,
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
  return `<div class="encounter-results">${card.skillChecks
    .filter((check) => !check.old)
    .map(
      (check) =>
        `<p class="encounter-result-line">${esc(`1d10 (${check.roll}) + ${check.modifier} = ${check.total} .. ${check.success ? "Success!" : "Failure!"}`)}</p>`,
    )
    .join("")}</div>`;
}

function renderSelectionCard(selection: Selection, error = "") {
  const maxChoices = selection.maxChoices ?? 1;
  const inputType = maxChoices === 1 ? "radio" : "checkbox";
  const instruction =
    selection.minChoices === 0
      ? maxChoices === 1
        ? "Choose one option or cancel."
        : `Choose up to ${maxChoices} options.`
      : selection.minChoices === maxChoices
        ? `Choose ${maxChoices} option${maxChoices === 1 ? "" : "s"}.`
        : `Choose between ${selection.minChoices ?? 1} and ${maxChoices} options.`;
  const choices = selection.choices
    .map(
      (choice) => `
        <label class="selection-choice">
          <input type="${inputType}" name="selection-${esc(selection.id)}" value="${esc(choice.index)}" data-choice-index="${esc(choice.index)}" />
          <span>${esc(choice.description)}</span>
        </label>`,
    )
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
  initialSpecialActionCatalog: SpecialAction[],
  initialSpecialActions: SpecialAction[],
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
  app.innerHTML = `<div class="layout"><main><section class="top-strip"><div class="bar"><button id="minus">-</button><span id="z"></span><button id="plus">+</button><button id="fit">Fit</button><button id="snap">Snap</button></div></section><div class="map-shell"><div class="map-pane"><div id="map-scroll"><div id="map"></div><section class="tableau">${tableauData.encounters.map(renderEncounterCard).join("")}</section></div></div></div><section class="character-panel"><section class="character-summary"><h2>Character</h2><div id="character-stats"></div></section><section class="action-section"><div class="action-buttons-row"><button id="travel" class="action-button" type="button"><img src="/images/actions/boots.svg" alt=""/><span>Travel</span></button><button id="camp" class="action-button" type="button"><img src="/images/actions/campfire.svg" alt=""/><span>Camp</span></button><button id="attack" class="action-button" type="button"><img src="/images/actions/swords.svg" alt=""/><span>Attack</span></button></div><div id="special-actions" class="special-actions"></div></section></section></main><aside class="right-panel"><section class="activity-panel"><h2 id="activity-panel-title" hidden></h2><div id="activity-panel-content"></div></section></aside><footer><b>Log</b><p>Bogus bottom panel: marching orders, dice results, chat, and event feed will appear here.</p></footer></div><div id="tip"></div>`;
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
  const actionButtons = [
    ...document.querySelectorAll(".action-button"),
  ] as HTMLButtonElement[];
  const specialActionsEl = document.querySelector(
    "#special-actions",
  ) as HTMLElement;
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
  let specialActionCatalog = initialSpecialActionCatalog;
  let pendingSpecialAction: { actionId: string; targetHex: string } | null =
    null;
  let pendingTravelRoute: string[] | null = null;
  let travelContinuation = false;
  let travelSpecialAction: { actionId: string; targetHex: string } | null =
    null;
  let activeSelection: Selection | null = null;
  let activityBlocksControls = false;
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
    document
      .querySelectorAll<HTMLButtonElement>(
        "#selection-select, #selection-cancel",
      )
      .forEach((button) => (button.disabled = busy));
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
    setActivityPanel(null, "");
  }

  function clearPendingTravelState() {
    pendingSpecialAction = null;
    pendingTravelRoute = null;
    travelContinuation = false;
    travelSpecialAction = null;
  }

  function resumeTravelAfterActivity(
    destination: string,
    pendingAction: { actionId: string; targetHex: string } | null,
    remainingRoute: string[] | null = pendingTravelRoute,
  ) {
    if (pendingAction && destination === pendingAction.targetHex) {
      pendingTravelRoute = null;
      travelContinuation = false;
      const action = specialActionCatalog.find(
        (item) => item.id === pendingAction.actionId,
      );
      if (action) showSpecialActionPrompt(action, pendingAction.targetHex);
      return;
    }
    if (remainingRoute?.length) {
      route = remainingRoute;
      pendingSpecialAction = pendingAction;
      travelContinuation = true;
      map.classList.add("travel-mode");
      showTravelCard();
      draw();
      return;
    }
    clearPendingTravelState();
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
    return null;
  }

  async function submitSelection(selectedIndexes: number[]) {
    if (!activeSelection) return;
    const selectionId = activeSelection.id;
    activeSelection = null;
    const destination = player.location;
    const pendingAction = travelSpecialAction;
    const remainingRoute = pendingTravelRoute;
    await executeActivity(
      "Selection",
      () =>
        apiJson<ActivityResult>(
          `/api/entities/${encodeURIComponent(player.name)}/actions/make_selection`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              selectionId,
              selectedIndexes,
            }),
          },
        ),
      (result) => {
        return showActivityResult("Selection", result, () => {
          if (!launchResultNextActive(result))
            resumeTravelAfterActivity(
              destination,
              pendingAction,
              remainingRoute,
            );
        });
      },
    );
  }

  function showSelection(selection: Selection) {
    activeEncounterId = null;
    activeSelection = selection;
    setActivityPanel("Selection", renderSelectionCard(selection), true);
    const errorEl = document.querySelector(
      ".selection-error",
    ) as HTMLElement | null;
    const selectButton = document.querySelector(
      "#selection-select",
    ) as HTMLButtonElement | null;
    const cancelButton = document.querySelector(
      "#selection-cancel",
    ) as HTMLButtonElement | null;
    const clearError = () => {
      if (errorEl) errorEl.textContent = "";
    };
    document
      .querySelectorAll<HTMLInputElement>(
        `input[name="selection-${CSS.escape(selection.id)}"]`,
      )
      .forEach((input) => input.addEventListener("change", clearError));
    cancelButton?.addEventListener("click", () => {
      void submitSelection([]);
    });
    selectButton?.addEventListener("click", () => {
      const selectedIndexes = [
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
      const distance = store.distance(origin, hex);
      if (!best || distance < best.distance)
        best = { name: location, distance };
    }
    return best?.name;
  }

  function visibleSpecialActions() {
    const origin = currentLocationHex();
    return specialActions.filter((action) => {
      if (!action.locations?.length) return true;
      if (!origin) return false;
      return action.locations.some((location) => {
        const hex = store.hexes.get(location);
        return hex ? store.distance(origin, hex) <= player.speed : false;
      });
    });
  }

  function catalogSpecialActionsForHex(hexName: string) {
    return specialActionCatalog.filter((action) =>
      action.locations?.includes(hexName),
    );
  }

  function renderSpecialActionLabel(action: SpecialAction, target?: string) {
    return `${esc(action.name)}${target ? ` (${esc(target)})` : ""}`;
  }

  function renderSpecialActionList() {
    const actions = visibleSpecialActions();
    const disabled = busy || activityBlocksControls;
    specialActionsEl.innerHTML = actions.length
      ? `<div class="special-actions-list">${actions
          .map((action) => {
            const target = specialActionTarget(action);
            return `<button class="special-action-link" type="button" data-action-id="${esc(action.id)}"${target ? ` data-target-hex="${esc(target)}"` : ""} ${disabled ? "disabled" : ""}>${renderSpecialActionLabel(action, target)}</button>`;
          })
          .join("")}</div>`
      : "";
  }

  async function refreshSpecialActions() {
    try {
      specialActions = await apiJson<SpecialAction[]>(
        `/api/entities/${encodeURIComponent(player.name)}/special_actions`,
        undefined,
        20,
      );
      renderSpecialActionList();
    } catch (err) {
      console.error(err);
    }
  }

  function specialActionTitle(action: SpecialAction, hexName: string) {
    return `Perform ${action.name} in hex ${hexName}?`;
  }

  function showSpecialActionPrompt(action: SpecialAction, hexName: string) {
    const canAfford = canAffordEffects(player, action.cost ?? []);
    setPlay(
      `<article class="play-card special-action-card"><h3>${esc(action.name)}</h3><div class="play-card-body"><p>${esc(specialActionTitle(action, hexName))}</p><p class="special-action-cost">Cost: ${esc(formatEffects(action.cost ?? []))}</p></div></article><div class="special-action-controls"><button id="special-action-ok" class="card-ok" type="button"${canAfford ? "" : ' disabled title="You can\'t afford to perform this action." aria-disabled="true"'}>OK</button><button id="special-action-cancel" class="card-ok" type="button">Cancel</button></div>`,
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
        () => void performSpecialAction(action.id),
      );
  }

  function startSpecialAction(action: SpecialAction, targetHex: string) {
    const currentHex = player.location;
    if (currentHex === targetHex) {
      showSpecialActionPrompt(action, targetHex);
      return;
    }
    pendingSpecialAction = { actionId: action.id, targetHex };
    enterTravelMode();
    const hex = store.hexes.get(targetHex);
    if (hex) selectRouteHex(hex);
  }

  function specialActionLinkClick(actionId: string, targetHex?: string) {
    const action = specialActionCatalog.find((item) => item.id === actionId);
    const hexName =
      targetHex ??
      (action?.locations?.length
        ? specialActionTarget(action)
        : player.location);
    if (!action || !hexName) return;
    startSpecialAction(action, hexName);
  }

  async function performSpecialAction(specialActionId: string) {
    await executeActivity(
      "Action",
      () =>
        apiJson<ActivityResult>(
          `/api/entities/${encodeURIComponent(player.name)}/actions/special_action`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ specialActionId }),
          },
        ),
      (result) => {
        clearPendingTravelState();
        return showActivityResult("Action", result, () =>
          launchResultNextActive(result),
        );
      },
    );
  }

  specialActionsEl.addEventListener("click", (e) => {
    const button = (e.target as HTMLElement).closest(
      ".special-action-link",
    ) as HTMLButtonElement | null;
    if (!button || button.disabled) return;
    const actionId = button.dataset.actionId;
    if (!actionId) return;
    specialActionLinkClick(actionId, button.dataset.targetHex);
  });

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
      `${renderEncounterSummary(card)}${renderActiveEncounterCard(card)}${renderEncounterResults(card)}${encounterButtons(card)}`,
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
  function isAdjacent(a: Hex, b: Hex) {
    return store.distance(a, b) === 1;
  }
  function clamp(value: number, min: number, max: number) {
    return Math.max(min, Math.min(max, value));
  }

  let collapsedSummarySections = {
    resources: false,
    inventory: false,
    conditions: false,
    skills: false,
  };
  let hideZeroResources = false;
  let hideZeroSkills = false;

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
    return items.length
      ? `<ul class="inventory-list">${items
          .map((item) => `<li>${esc(item.name)}</li>`)
          .join("")}</ul>`
      : `<p class="inventory-empty">None</p>`;
  }

  function renderConditions(conditions: Condition[]) {
    return conditions.length
      ? `<ul class="condition-list">${conditions
          .map((condition) =>
            condition.duration == 1
              ? `<li>${esc(condition.name)} (1 turn)</li>`
              : `<li>${esc(condition.name)} (${esc(condition.duration)} turns)</li>`,
          )
          .join("")}</ul>`
      : `<p class="condition-empty">None</p>`;
  }

  function renderSkills(skills: Record<string, number>) {
    const visibleSkills = Object.entries(skills)
      .sort(([a], [b]) => a.localeCompare(b))
      .filter(([, value]) => !hideZeroSkills || value !== 0);
    return visibleSkills.length
      ? `<ul class="skill-list">${visibleSkills
          .map(([name, value]) => `<li>${esc(name)}: ${esc(value)}</li>`)
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

  function renderSummary() {
    stats.innerHTML = `<div class="summary-basic"><div><dd>${esc(player.name)}</dd></div><div><dt>Location</dt><dd>${esc(player.location)}</dd></div><div><dt>Health</dt><dd>${player.curHealth}/${player.maxHealth}</dd></div><div><dt>Luck</dt><dd>${player.curLuck}/${player.maxLuck}</dd></div><div><dt>Speed</dt><dd>${player.speed}</dd></div><div><dt>Gold</dt><dd>${player.gold}</dd></div><div><dt>Reputation</dt><dd>${player.reputation}</dd></div><div><dt>Turns</dt><dd>${player.turns}</dd></div></div>${renderSummarySection("resources", "Resources", `<label class="skills-filter"><input type="checkbox" id="hide-zero-resources"${hideZeroResources ? " checked" : ""}/> hide 0 resources</label>${renderResources(player.resources)}`)}${renderSummarySection("inventory", "Inventory", renderInventory(player.inventory))}${renderSummarySection("conditions", "Conditions", renderConditions(player.conditions))}${renderSummarySection("skills", "Skills", `<label class="skills-filter"><input type="checkbox" id="hide-zero-skills"${hideZeroSkills ? " checked" : ""}/> hide 0 skills</label>${renderSkills(player.skills)}`)}`;
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

  function showActivityError(kind: ActivityKind, message: string) {
    const title = activityErrorTitle(kind);
    setPlay(
      `<article class="play-card error-card"><h3>${esc(title)}</h3><div class="play-card-body"><p>${esc(message)}</p></div></article><button id="card-ok" class="card-ok" type="button">OK</button>`,
      title,
      false,
    );
    document.querySelector("#card-ok")!.addEventListener("click", clearPlay);
  }

  async function showActivityResult(
    kind: ActivityKind,
    result: ActivityResult,
    onClosed?: () => void,
  ) {
    const shouldRenderCard =
      Boolean(result.flavorText) ||
      result.effects.length > 0 ||
      !result.nextActive;
    const title = activityResultTitle(kind, result);
    if (!shouldRenderCard) {
      clearPlay();
      onClosed?.();
      return;
    }
    const lines = await renderActivityLines(result, async (itemId) => {
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
        .map((line) => `<p>${esc(line)}</p>`)
        .join(
          "",
        )}</div></article><button id="card-ok" class="card-ok" type="button">OK</button>`,
      title,
      Boolean(result.nextActive),
    );
    document.querySelector("#card-ok")!.addEventListener("click", () => {
      clearPlay();
      onClosed?.();
    });
  }

  function launchResultNextActive(result: ActivityResult) {
    if (result.nextActive) {
      launchNextActive(result.nextActive);
      return true;
    }
    return false;
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
      .map(renderEncounterCard)
      .join("");
  }

  async function refreshActivityState(previousLocation = player.location) {
    const updatedPlayer = await apiJson<PlayerEntity>(
      `/api/entities/${encodeURIComponent(player.name)}`,
      undefined,
      20,
    );
    Object.assign(player, updatedPlayer);
    for (const item of updatedPlayer.inventory)
      itemNameCache.set(item.id, item.name);
    if (updatedPlayer.location !== previousLocation)
      moveLocalPlayerToken(previousLocation, updatedPlayer.location);
    const updatedTableau = await apiJson<TableauData>(
      "/api/tableau",
      undefined,
      20,
    );
    syncTableau(updatedTableau);
    renderSummary();
    await refreshSpecialActions();
  }

  async function executeActivity(
    kind: string,
    request: () => Promise<ActivityResult>,
    onComplete: (result: ActivityResult) => void,
  ) {
    busy = true;
    updateActionButtons();
    try {
      const result = await request();
      await refreshActivityState();
      await onComplete(result);
    } catch (err) {
      console.error(err);
      showActivityError(kind, err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
      updateActionButtons();
    }
  }

  function showEncounterPreview(card: EncounterCard) {
    const canAfford = canAffordEffects(player, [
      { type: EffectType.Turns, amount: 1 },
    ]);
    setPlay(
      `${renderEncounterCard(card)}<div class="encounter-controls"><button id="encounter-ok" class="card-ok" type="button"${canAfford ? "" : ' disabled title="You\'re out of turns." aria-disabled="true"'}>OK</button><button id="encounter-cancel" class="card-ok" type="button">Cancel</button></div>`,
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

  function launchNextActive(nextActive: ActivityNextActive) {
    if (nextActive.type === "selection") showSelection(nextActive.selection);
    else showActiveEncounter(nextActive.encounter);
  }

  async function runEncounter(encounterId: string) {
    await executeActivity(
      "Encounter",
      () =>
        apiJson<ActivityResult>(
          `/api/entities/${encodeURIComponent(player.name)}/actions/run_encounter`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ encounterId, tableauId: encounterId }),
          },
        ),
      (result) => {
        return showActivityResult("Encounter", result, () =>
          launchResultNextActive(result),
        );
      },
    );
  }

  async function continueEncounter(encounterId: string) {
    await executeActivity(
      "Encounter",
      () =>
        apiJson<ActivityResult>(
          `/api/entities/${encodeURIComponent(player.name)}/actions/continue_encounter`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ encounterId, tableauId: encounterId }),
          },
        ),
      (result) => {
        return showActivityResult("Encounter", result, () =>
          launchResultNextActive(result),
        );
      },
    );
  }

  async function finishEncounter(encounterId: string, conceding = false) {
    const destination = player.location;
    const pendingAction = travelSpecialAction;
    const remainingRoute = pendingTravelRoute;
    await executeActivity(
      "Encounter",
      () =>
        apiJson<ActivityResult>(
          `/api/entities/${encodeURIComponent(player.name)}/actions/finish_encounter`,
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
        return showActivityResult("Encounter", result, () => {
          if (!launchResultNextActive(result))
            resumeTravelAfterActivity(
              destination,
              pendingAction,
              remainingRoute,
            );
        });
      },
    );
  }

  function enterTravelMode() {
    if (busy || activityBlocksControls) return;
    route = [player.location];
    pendingTravelRoute = null;
    travelContinuation = false;
    map.classList.add("travel-mode");
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

  function travelRouteHtml() {
    const maxNodes = player.speed + 1;
    return route!
      .map((hexName, index) => {
        const cls = index >= maxNodes ? ' class="travel-route-future"' : "";
        return `<span${cls}>${esc(hexName)}</span>`;
      })
      .join(" - ");
  }

  function showTravelCard() {
    const canAfford = travelContinuation
      ? true
      : canAffordEffects(player, [{ type: EffectType.Turns, amount: 1 }]);
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
    await executeActivity(
      "Camp",
      () =>
        apiJson<ActivityResult>(
          `/api/entities/${encodeURIComponent(player.name)}/actions/camp`,
          { method: "POST" },
        ),
      (result) => {
        clearPendingTravelState();
        return showActivityResult("Camp", result, () =>
          launchResultNextActive(result),
        );
      },
    );
  }

  function exitTravelMode() {
    route = null;
    pendingSpecialAction = null;
    pendingTravelRoute = null;
    travelContinuation = false;
    travelSpecialAction = null;
    map.classList.remove("travel-mode");
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
    const pendingAction = pendingSpecialAction;
    travelSpecialAction = pendingAction;
    const submittedRoute = [...route];
    route = null;
    pendingSpecialAction = null;
    map.classList.remove("travel-mode");
    draw();
    await executeActivity(
      "Travel",
      () =>
        apiJson<ActivityResult>(
          `/api/entities/${encodeURIComponent(player.name)}/actions/travel`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ route: submittedRoute }),
          },
        ),
      (result) => {
        const destination = player.location;
        const destinationIndex = submittedRoute.indexOf(destination);
        const remainingRoute =
          destinationIndex >= 0 && destinationIndex < submittedRoute.length - 1
            ? submittedRoute.slice(destinationIndex)
            : undefined;
        pendingTravelRoute = remainingRoute ?? null;
        travelContinuation = Boolean(remainingRoute?.length);
        return showActivityResult("Travel", result, () => {
          if (!launchResultNextActive(result))
            resumeTravelAfterActivity(
              destination,
              pendingAction,
              remainingRoute ?? null,
            );
        });
        draw();
      },
    );
  }

  function moveLocalPlayerToken(from: string, to: string) {
    const fromHex = store.hexes.get(from),
      toHex = store.hexes.get(to);
    if (!fromHex || !toHex) return;
    fromHex.tokens = fromHex.tokens.filter((id) => id !== player.tokenId);
    if (!toHex.tokens.includes(player.tokenId))
      toHex.tokens.push(player.tokenId);
    store.tokenHex.set(player.tokenId, toHex);
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
    document.querySelector("#z")!.textContent = `${Math.round(zoom * 100)}%`;
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
    for (const hex of store.data.hexes) {
      const { x: cx, y: cy } = hexCenter(hex);
      const terr = store.terrains.get(hex.terrain);
      const g = document.createElementNS(svgNS, "g");
      g.classList.add("hex");
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
      const toks = hex.tokens.map((id) => store.tokens.get(id)!);
      toks.forEach((t, i) => {
        const separate = zoom > 0.38;
        g.innerHTML += `<image href="/images/tokens/${t.icon}.svg" x="${cx - 18 + (separate ? (i - (toks.length - 1) / 2) * 24 : 0)}" y="${cy - 18}" width="36" height="36"/>`;
      });
      if (zoom > 0.55)
        hex.claims.forEach((c, i) => {
          const cl = store.claims.get(c);
          g.innerHTML += `<image href="/images/claims/${cl.icon}.svg" x="${cx - 24 + i * 16}" y="${cy + 22}" width="14" height="14"/>`;
        });
      if (
        encounterByLocation.has(hex.name) ||
        specialActionCatalog.some((action) =>
          action.locations?.includes(hex.name),
        )
      )
        g.innerHTML += `<text x="${cx}" y="${cy + 10}" text-anchor="middle" class="encounter-star" aria-hidden="true">★</text>`;
      g.onclick = (e) => {
        e.stopPropagation();
        route ? selectRouteHex(hex) : showTip(hex, g.getBoundingClientRect());
      };
      let timer: any;
      g.onmouseenter = () =>
        (timer = setTimeout(() => {
          if (!route) showTip(hex, g.getBoundingClientRect());
        }, 700));
      g.onmouseleave = () => clearTimeout(timer);
      svg.append(g);
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

  function formatTokens(tokens: { entityName: string }[]) {
    return tokens.map((token) => token.entityName).join(", ");
  }

  function showTip(hex: Hex, anchor: DOMRect) {
    const f = store.fullHex(hex.name)!;
    const moveHereDisabled = busy || activityBlocksControls;
    const claimsText = formatClaims(
      f.claimObjs
        .filter((claim): claim is NonNullable<typeof claim> => Boolean(claim))
        .map((claim) => claim.name),
    );
    const tokenText = formatTokens(
      f.tokenObjs.filter((token): token is NonNullable<typeof token> =>
        Boolean(token),
      ),
    );
    const encounter = encounterByLocation.get(hex.name);
    const specialActionsHere = catalogSpecialActionsForHex(hex.name);
    const lines: [string, string][] = [
      ["Terrain", esc(f.terrain)],
      ["Region", esc(f.region)],
    ];
    if (claimsText) lines.push(["Claims", esc(claimsText)]);
    if (tokenText) lines.push(["Tokens", esc(tokenText)]);
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
        if (actionId) specialActionLinkClick(actionId, targetHex);
      });
    });
  }

  tableauEl.addEventListener("click", (e) => {
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
  document.querySelector("#snap")!.addEventListener("click", () => {
    manualZoom = true;
    zoom = 1;
    centerPlayerAfterDraw = true;
    draw();
  });
  document.querySelector("#travel")!.addEventListener("click", enterTravelMode);
  document.querySelector("#camp")!.addEventListener("click", showCampCard);
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
