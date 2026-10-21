import http from "node:http";

import { PlayerEntity, TableauCard } from "./types.js";
import { makeTokenId } from "./data.js";
import { loadOrGenerateWorld, MapGeneratorName } from "./map_generator.js";
import { RNG } from "./random.js";
import { createApiCommands } from "./commands.js";

const defaultGenerator: MapGeneratorName =
  process.env["MAP_GENERATOR"] === "allRandom" ||
  process.env["MAP_GENERATOR"] === "empire"
    ? process.env["MAP_GENERATOR"]
    : "empire";
const defaultSeed =
  process.env["MAP_SEED"] ?? Math.random().toString(36).slice(2, 18);
const world = await loadOrGenerateWorld({
  generator: defaultGenerator,
  seed: defaultSeed,
});
const hexes = world.hexes;
const hexByName = world.hexByName;

const playerTokens = [1, 2, 3, 4].map((i) => ({
  id: makeTokenId(),
  entityName: `Player ${i}`,
  icon: `player${i}`,
}));
const playerPlacementRng = new RNG(`${defaultSeed}:players`);

function clearPlayerTokens() {
  for (const hex of hexes)
    hex.tokens = hex.tokens.filter(
      (id) => !playerTokens.some((player) => player.id === id),
    );
}

function placePlayersAfterLoad() {
  clearPlayerTokens();
  const used = new Set<number>();
  const place = (tokenId: string, index: number | undefined) => {
    let idx = index ?? playerPlacementRng.int(hexes.length);
    while (used.has(idx)) idx = playerPlacementRng.int(hexes.length);
    used.add(idx);
    hexes[idx].tokens.push(tokenId);
  };
  place(playerTokens[0].id, 42);
  for (const token of playerTokens.slice(1)) place(token.id, undefined);
}
placePlayersAfterLoad();

function locationForToken(tokenId: string) {
  return hexes.find((hex) => hex.tokens.includes(tokenId))?.name ?? "Unknown";
}

const players = new Map<string, PlayerEntity>();
for (const token of playerTokens) {
  players.set(token.entityName, {
    name: token.entityName,
    tokenId: token.id,
    curHealth: 6 + Number(token.id.split("-")[1]) - 1,
    maxHealth: 10,
    curLuck: 1,
    maxLuck: 3,
    gold: 0,
    reputation: 10,
    turns: 20,
    location: locationForToken(token.id),
  });
}
const activeEncounters = new Map<string, string>();

const encounters: TableauCard[] = [
  {
    id: "dungeon-raid",
    title: "Dungeon Raid",
    location: "B17",
    difficulty: 0,
    rewards: ["Gold"],
    penalties: ["Health"],
    skillChecks: [
      { name: "Stealth", target: 5 },
      { name: "Athletics", target: 4 },
      { name: "Blades", target: 6 },
    ],
  },
  {
    id: "parley",
    title: "Parley",
    location: "H8",
    difficulty: 4,
    rewards: ["Gold"],
    penalties: ["Health"],
    skillChecks: [
      { name: "Persuasion", target: 6 },
      { name: "Deception", target: 5 },
    ],
  },
  {
    id: "wandering-sage",
    title: "Wandering Sage",
    location: "M12",
    difficulty: 2,
    rewards: ["Gold"],
    penalties: ["Health"],
    skillChecks: [
      { name: "Lore", target: 4 },
      { name: "Insight", target: 7 },
    ],
  },
];

const api = createApiCommands({
  hexes,
  hexByName,
  tokens: playerTokens,
  players,
  activeEncounters,
  encounters,
});

const server = http.createServer(api.handle);
const port = Number(process.env.PORT) || 3001;
server.listen(port, () => console.log(`Picaro server on ${port}`));
