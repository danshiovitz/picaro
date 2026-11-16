import {
  Selection,
  PlayerEntity,
  SelectionChoice,
  ActivityResult,
  SelectionView,
  FunctionType,
} from "./types.js";
import {
  fetchNextActivityExpectingSelection,
  RulesViolation,
} from "./commands.js";
import { getApiState, skillNames, invoke } from "./data.js";

export type SelectionRequest = {
  selectionId: string;
  selectedIndexes: number[];
};

function selectionChoiceDto(choice: SelectionChoice) {
  return { ...choice };
}

export function selectionDto(selection: Selection): SelectionView {
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

export function makeSelection(
  player: PlayerEntity,
  request: SelectionRequest,
): ActivityResult {
  const selection = fetchNextActivityExpectingSelection(
    player,
    request.selectionId,
  );
  if (!selection) {
    throw new RulesViolation("Selection not found");
  }
  validateSelectionIndexes(selection, request.selectedIndexes);
  const choices = selectedChoices(selection, request.selectedIndexes);
  return invoke<ActivityResult>(
    selection.callback,
    FunctionType.SelectionCallback,
    [selection, player, choices],
  );
}
