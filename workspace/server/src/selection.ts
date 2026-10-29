import type { ApiState } from "./commands.js";
import {
  Selection,
  PlayerEntity,
  SectionType,
  SelectionChoice,
  ActionResponse,
  SelectionView,
} from "./types.js";
import { skillNames } from "./data.js";
import { computeEffectiveValue } from "./rule.js";
import { RulesViolation } from "./commands.js";

export type SelectionRequest = {
  selectionId: string;
  selectedIndexes: number[];
};

function cloneInventory(inventory: PlayerEntity["inventory"]) {
  return inventory.map((item) => ({ ...item }));
}

function cloneConditions(conditions: PlayerEntity["conditions"]) {
  return conditions.map((condition) => ({ ...condition }));
}

function cloneResources(resources: PlayerEntity["resources"]) {
  return { ...resources };
}

function effectiveSkills(player: PlayerEntity) {
  return Object.fromEntries(
    skillNames.map(
      (skill) =>
        [
          skill,
          computeEffectiveValue(player, SectionType.skill, skill),
        ] as const,
    ),
  );
}

function playerUpdates(player: PlayerEntity) {
  return {
    curHealth: player.curHealth,
    curLuck: player.curLuck,
    maxLuck: player.maxLuck,
    gold: player.gold,
    reputation: player.reputation,
    turns: player.turns,
    maxHealth: computeEffectiveValue(player, SectionType.maxHealth),
    speed: computeEffectiveValue(player, SectionType.speed),
    location: player.location,
    skills: effectiveSkills(player),
    resources: cloneResources(player.resources),
    inventory: cloneInventory(player.inventory),
    conditions: cloneConditions(player.conditions),
  } satisfies Partial<PlayerEntity>;
}

function selectionChoiceDto(choice: SelectionChoice) {
  const { data: _data, ...dto } = choice;
  return dto;
}

function selectionDto(selection: Selection): SelectionView {
  const { callback: _callback, ...dto } = selection;
  return {
    ...dto,
    choices: selection.choices.map(selectionChoiceDto),
  };
}

function validateSelectionIndexes(
  selection: Selection,
  selectedIndexes: number[],
) {
  if (!selectedIndexes.every(Number.isInteger)) {
    throw new RulesViolation("Selection indexes must be integers");
  }
  const minChoices = selection.minChoices ?? 1;
  const maxChoices = selection.maxChoices ?? 1;
  if (
    selectedIndexes.length < minChoices ||
    selectedIndexes.length > maxChoices
  ) {
    throw new RulesViolation(
      `Select between ${minChoices} and ${maxChoices} choices.`,
    );
  }
  const knownIndexes = new Set(selection.choices.map((choice) => choice.index));
  const seen = new Set<number>();
  for (const index of selectedIndexes) {
    if (seen.has(index)) {
      throw new RulesViolation("Selection contains duplicate choices");
    }
    seen.add(index);
    if (!knownIndexes.has(index)) {
      throw new RulesViolation("Selection choice not found");
    }
  }
}

function selectedChoices(selection: Selection, selectedIndexes: number[]) {
  const byIndex = new Map(
    selection.choices.map((choice) => [choice.index, choice] as const),
  );
  return selectedIndexes
    .map((index) => byIndex.get(index))
    .filter((choice): choice is SelectionChoice => Boolean(choice));
}

export function presentSelection(
  state: ApiState,
  player: PlayerEntity,
  selection: Selection,
) {
  state.activeSelections.set(player.name, selection);
  return selectionDto(selection);
}

export function getActiveSelection(
  state: ApiState,
  player: PlayerEntity,
): SelectionView | undefined {
  return state.activeSelections.has(player.name)
    ? selectionDto(state.activeSelections.get(player.name)!)
    : undefined;
}

export function makeSelection(
  state: ApiState,
  player: PlayerEntity,
  request: SelectionRequest,
): ActionResponse {
  const selection = state.activeSelections.get(player.name);
  if (!selection || selection.id !== request.selectionId) {
    throw new RulesViolation("Selection not found");
  }
  validateSelectionIndexes(selection, request.selectedIndexes);
  state.activeSelections.delete(player.name);
  selection.callback([...request.selectedIndexes]);
  const choices = selectedChoices(selection, request.selectedIndexes);
  return {
    updates: playerUpdates(player),
    card: {
      title: "Selection Results",
      lines:
        choices.length > 0
          ? choices.map((choice) => choice.description)
          : ["No selection made."],
    },
    tableauChanged: false,
  };
}
