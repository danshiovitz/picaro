import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import {
  CityEntity,
  Entity,
  Hex,
  HexEntity,
  Region,
  RegionEntity,
} from "./types.js";
import { createEntity, hydrateEntity, serializeEntity } from "./entity.js";
import { RNG } from "./random.js";
import { PerlinNoise, noiseValue } from "./noise.js";
import {
  hexName,
  hexDirs,
  pickRandomWallPoint,
  pickRandomWallPath,
  shortestHexPath,
  getNeighborIndexes,
  hexDistance,
} from "./hexmap.js";
import { claims, makeCityEntities } from "./data.js";

export type MapGeneratorName = "allRandom" | "empire";
export type GeneratedWorld = {
  hexes: Hex[];
  hexByName: Map<string, Hex>;
  regions: Region[];
  entities: Entity[];
};
export type SavedMapState = {
  hexes: Hex[];
  entities: Entity[];
  regions: Region[];
};
export type MapOptions = { generator: MapGeneratorName; seed: string };

type Wall = "top" | "right" | "bottom" | "left";

const allRandomTerrains = [
  "Forest",
  "Deep Forest",
  "Desert",
  "Water",
  "Plains",
  "Mountain",
  "Hills",
  "Swamp",
  "Tundra",
  "Jungle",
  "Badlands",
  "Marsh",
];
const mapFilePath = resolve(
  process.cwd(),
  process.env["MAP_FILE"] ?? "data/map.json",
);

const regionNames = [
  "Valley of Aardia",
  "Domain of the Elves",
  "Iron Marches",
  "Sunspire Coast",
  "Gloaming Fens",
  "Kingdom of Roses",
  "Storm Peaks",
  "Amber Wastes",
  "Silverwood",
  "Riverlands",
  "Crown Basin",
  "Ashen Reach",
  "Sapphire Isles",
  "Old Empire",
  "Whispering Downs",
  "Dragonmere",
  "Golden Steppe",
  "Umbral Vale",
  "Free Cities",
];

const terrainRegionNames: Record<string, string[]> = {
  Forest: [
    "Silverwood",
    "Domain of the Elves",
    "Whispering Grove",
    "Greenbough Vale",
    "Oakshade Wilds",
    "Moonpine Thicket",
    "Oldwood Reach",
    "Emerald Canopy",
  ],
  "Deep Forest": [
    "Silverwood",
    "Domain of the Elves",
    "Blackbark Thicket",
    "Deepwood Expanse",
    "Moonshadow Grove",
    "Elderbough Wilds",
    "Greenbough Vale",
    "Ironleaf Vale",
  ],
  Desert: [
    "Amber Wastes",
    "Iron Marches",
    "Sunspire Dunes",
    "Glass Desert",
    "Searing Expanse",
    "Red Wastes",
    "Dune Sea",
    "Cinder Marches",
  ],
  Water: [
    "Sapphire Isles",
    "Sunspire Coast",
    "Riverlands",
    "Azure Reaches",
    "Tidebound Sea",
    "Coral Expanse",
    "Stormwater Gulf",
    "Glasswater Bay",
  ],
  Plains: [
    "Whispering Downs",
    "Golden Steppe",
    "Riverlands",
    "Crown Basin",
    "Sunlit Meadows",
    "Greenward Fields",
    "Open Crown",
    "Broadmead Vale",
  ],
  Mountain: [
    "Storm Peaks",
    "Ashen Reach",
    "Iron Marches",
    "Thunder Spires",
    "Granite Crown",
    "Frostpeak Range",
    "Highwatch Mountains",
    "Blackcrag Hold",
  ],
  Hills: [
    "Crown Basin",
    "Whispering Downs",
    "Rolling Downs",
    "Amber Knolls",
    "Greencrest Rise",
    "Silver Knolls",
    "Hartholm Slopes",
    "Oldridge Vale",
  ],
  Swamp: [
    "Gloaming Fens",
    "Umbral Vale",
    "Blackwater Fen",
    "Sable Mire",
    "Reedshadow Mire",
    "Bog of Whispers",
    "Nightmarsh",
    "Murkfen Reaches",
  ],
  Tundra: [
    "Frostveil Tundra",
    "White Wastes",
    "Icewind Reach",
    "Glacier Marches",
    "Winter Crown",
    "Northwind Vale",
    "Snowmelt Expanse",
    "Arctic Steppe",
  ],
  Jungle: [
    "Emerald Wilds",
    "Jade Canopy",
    "Vinecoil Reach",
    "Serpent Thicket",
    "Rainshadow Wilds",
    "Sunleaf Expanse",
    "Greenfire Basin",
    "Verdant Labyrinth",
  ],
  Badlands: [
    "Ashen Reach",
    "Iron Marches",
    "Red Badlands",
    "Cinder Vale",
    "Shatterstone Wastes",
    "Rust Marches",
    "Broken Crown",
    "Scorched Reach",
  ],
  Marsh: [
    "Gloaming Fens",
    "Umbral Vale",
    "Reedshadow Fen",
    "Blackwater Marsh",
    "Muddrowned Reach",
    "Siltfen Basin",
    "Nightmarsh",
    "Whisperbog",
  ],
  Glacier: [
    "White Wastes",
    "Frostveil Tundra",
    "Crystal Glacier",
    "Northwind Crown",
    "Icefall Reach",
    "Snowbound Expanse",
    "Shardmere",
    "Blueglass Ice",
  ],
  Savannah: [
    "Amber Wastes",
    "Golden Steppe",
    "Sunspire Savanna",
    "Lion's Reach",
    "Saffron Plains",
    "Warmwind Downs",
    "Dustflower Vale",
    "Ochre Marches",
  ],
};

const allRandomRegions: Region[] = regionNames.map((name, index) => ({
  id: `region-${index + 1}`,
  name,
  base_difficulty: 1,
}));

async function fileExists(filePath: string) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function saveMap(filePath: string, state: SavedMapState) {
  await mkdir(dirname(filePath), { recursive: true });
  await writeFile(
    filePath,
    JSON.stringify(
      {
        ...state,
        entities: state.entities.map((entity) => serializeEntity(entity)),
      },
      null,
      2,
    ),
    "utf8",
  );
}

export async function loadMap(filePath: string): Promise<GeneratedWorld> {
  const raw = await readFile(filePath, "utf8");
  const state = JSON.parse(raw) as SavedMapState;
  if (
    !Array.isArray(state.hexes) ||
    !Array.isArray(state.entities) ||
    !Array.isArray(state.regions)
  )
    throw new Error("Invalid map save file");
  if (state.hexes.some((hex) => typeof hex.region_id !== "string"))
    throw new Error("Invalid map save file");
  return {
    hexes: state.hexes,
    hexByName: new Map(state.hexes.map((hex) => [hex.name, hex] as const)),
    regions: state.regions,
    entities: state.entities.map((entity) => hydrateEntity(entity)),
  };
}

function buildHexes(width: number, height: number): Hex[] {
  const hexes: Hex[] = [];
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++)
      hexes.push({
        name: hexName(x, y),
        x,
        y,
        q: x - Math.floor(y / 2),
        r: y,
        terrain: "Plains",
        region_id: "",
        claims: [],
        tokens: [],
      });
  return hexes;
}

function placeToken(
  hexes: Hex[],
  used: Set<number>,
  token: Pick<Entity, "id">,
  index: number | undefined,
  rng: RNG,
) {
  let idx = index ?? rng.int(hexes.length);
  while (used.has(idx)) idx = rng.int(hexes.length);
  used.add(idx);
  hexes[idx].tokens.push(token.id);
}

function applyRandomClaims(hexes: Hex[], rng: RNG) {
  for (const hex of hexes) {
    const n = rng.int(4);
    hex.claims = [...claims]
      .sort(() => rng.next() - 0.5)
      .slice(0, n)
      .map((claim) => claim.name);
  }
}

function placeCities(hexes: Hex[], cityTokens: CityEntity[], rng: RNG) {
  const used = new Set<number>();
  placeToken(hexes, used, cityTokens[0], 42, rng);
  for (const token of cityTokens.slice(1))
    placeToken(hexes, used, token, undefined, rng);
}

function spreadHexes(
  hexes: Hex[],
  indexByCoord: Map<string, number>,
  rng: RNG,
  startIndexes: number[],
  tries: number,
  canFunc: (h: Hex) => boolean,
  spreadFunc: (h: Hex) => void,
): void {
  let curArray: number[] = [];
  let curSet = new Set<number>(startIndexes);
  let nextArray = [...startIndexes];
  for (let i = 0; i < tries; i++) {
    if (curArray.length === 0) {
      curArray = rng.shuffle(nextArray);
      nextArray = [];
      if (curArray.length === 0) break;
    }
    const curIdx = curArray.pop();
    if (curIdx === undefined) continue;
    const hex = hexes[curIdx];
    const nghs: number[] = [];
    for (const [dq, dr] of hexDirs()) {
      const neighborIndex = indexByCoord.get(`${hex.q + dq},${hex.r + dr}`);
      if (
        neighborIndex !== undefined &&
        !curSet.has(neighborIndex) &&
        canFunc(hexes[neighborIndex])
      )
        nghs.push(neighborIndex);
    }
    if (nghs.length > 0) {
      const nidx = rng.pick(nghs);
      curSet.add(nidx);
      nextArray.push(nidx);
      spreadFunc(hexes[nidx]);
    }
  }
}

function assignEmpireRegions(
  hexes: Hex[],
  indexByCoord: Map<string, number>,
  rng: RNG,
): Region[] {
  const totalHexes = hexes.length;
  const minSize = Math.max(1, Math.ceil(totalHexes * 0.01));
  const maxSize = Math.max(minSize, Math.floor(totalHexes * 0.05));
  const idealSize = Math.max(1, Math.round(totalHexes * 0.03));
  const strongIterations = 3;
  const promotedNeighborCount = 4;

  let placeholderIndex = 1;
  function nextPlaceholderRegion(): Region {
    const index = placeholderIndex++;
    return {
      id: "region-" + index,
      name: "Region " + index,
      base_difficulty: 1,
    };
  }

  type RegionGroup = {
    region: Region;
    indexes: number[];
  };

  function createGroup(indexes: number[]): RegionGroup {
    const region = nextPlaceholderRegion();
    for (const index of indexes) hexes[index].region_id = region.id;
    return { region, indexes: [...indexes] };
  }

  function collectTerrainComponent(
    startIndex: number,
    visited: Set<number>,
  ): number[] {
    const terrain = hexes[startIndex].terrain;
    const queue = [startIndex];
    const indexes = [startIndex];
    visited.add(startIndex);
    for (let i = 0; i < queue.length; i++) {
      const current = queue[i];
      for (const neighborIndex of getNeighborIndexes(
        hexes,
        indexByCoord,
        current,
      )) {
        if (visited.has(neighborIndex)) continue;
        if (hexes[neighborIndex].terrain !== terrain) continue;
        visited.add(neighborIndex);
        queue.push(neighborIndex);
        indexes.push(neighborIndex);
      }
    }
    return indexes;
  }

  function bfsDistances(
    startIndex: number,
    allowed: Set<number>,
  ): Map<number, number> {
    const distances = new Map<number, number>([[startIndex, 0]]);
    const queue = [startIndex];
    for (let i = 0; i < queue.length; i++) {
      const current = queue[i];
      const currentDistance = distances.get(current)!;
      for (const neighborIndex of getNeighborIndexes(
        hexes,
        indexByCoord,
        current,
      )) {
        if (!allowed.has(neighborIndex) || distances.has(neighborIndex))
          continue;
        distances.set(neighborIndex, currentDistance + 1);
        queue.push(neighborIndex);
      }
    }
    return distances;
  }

  function splitOversizedComponent(indexes: number[]): RegionGroup[] {
    if (indexes.length <= maxSize) return [createGroup(indexes)];

    const componentSet = new Set(indexes);
    const seedCount = Math.min(
      indexes.length,
      Math.max(
        2,
        Math.floor(indexes.length / idealSize),
        Math.ceil(indexes.length / maxSize),
      ),
    );

    const shuffledIndexes = rng.shuffle([...indexes]);
    const seeds: number[] = [shuffledIndexes[0]];
    while (seeds.length < seedCount) {
      let bestDistance = -1;
      const bestIndexes: number[] = [];
      for (const index of indexes) {
        if (seeds.includes(index)) continue;
        let minDistance = Infinity;
        for (const seed of seeds)
          minDistance = Math.min(
            minDistance,
            hexDistance(hexes[index], hexes[seed]),
          );
        if (minDistance > bestDistance) {
          bestDistance = minDistance;
          bestIndexes.length = 0;
          bestIndexes.push(index);
        } else if (minDistance === bestDistance) {
          bestIndexes.push(index);
        }
      }
      if (bestIndexes.length === 0) break;
      seeds.push(rng.pick(bestIndexes));
    }

    const distanceMaps = new Map<number, Map<number, number>>();
    for (const seed of seeds)
      distanceMaps.set(seed, bfsDistances(seed, componentSet));
    const seedBias = new Map<number, number>(
      seeds.map((seed) => [seed, rng.next()] as const),
    );

    const buckets = new Map<number, number[]>();
    for (const seed of seeds) buckets.set(seed, []);
    for (const index of indexes) {
      let bestSeed = seeds[0];
      let bestDistance = Infinity;
      let bestBias = -Infinity;
      for (const seed of seeds) {
        const distance = distanceMaps.get(seed)!.get(index) ?? Infinity;
        const bias = seedBias.get(seed) ?? 0;
        if (
          distance < bestDistance ||
          (distance === bestDistance && bias > bestBias)
        ) {
          bestSeed = seed;
          bestDistance = distance;
          bestBias = bias;
        }
      }
      buckets.get(bestSeed)!.push(index);
    }

    const groups: RegionGroup[] = [];
    for (const bucket of buckets.values()) {
      if (bucket.length === 0) continue;
      if (bucket.length > maxSize)
        groups.push(...splitOversizedComponent(bucket));
      else groups.push(createGroup(bucket));
    }
    return groups;
  }

  const terrainVisited = new Set<number>();
  const groups: RegionGroup[] = [];
  for (let i = 0; i < hexes.length; i++) {
    if (terrainVisited.has(i)) continue;
    const component = collectTerrainComponent(i, terrainVisited);
    if (component.length > maxSize)
      groups.push(...splitOversizedComponent(component));
    else groups.push(createGroup(component));
  }

  const groupsById = new Map<string, RegionGroup>(
    groups.map((group) => [group.region.id, group] as const),
  );

  function dominantTerrain(indexes: number[]): string {
    const counts = new Map<string, number>();
    for (const index of indexes)
      counts.set(
        hexes[index].terrain,
        (counts.get(hexes[index].terrain) ?? 0) + 1,
      );
    const winners = [...counts.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      return a[0].localeCompare(b[0]);
    });
    return winners[0]?.[0] ?? hexes[indexes[0]]?.terrain ?? "";
  }

  const terrainNamePools = new Map(
    Object.entries(terrainRegionNames).map(
      ([terrain, names]) => [terrain, rng.shuffle([...names])] as const,
    ),
  );
  const fallbackNames = rng.shuffle([...regionNames]);
  const usedFinalNames = new Set<string>();

  function pickFinalRegionName(terrain: string) {
    const pool = terrainNamePools.get(terrain) ?? [];
    while (pool.length > 0) {
      const candidate = pool.shift()!;
      if (!usedFinalNames.has(candidate)) {
        usedFinalNames.add(candidate);
        return candidate;
      }
    }
    while (fallbackNames.length > 0) {
      const candidate = fallbackNames.shift()!;
      if (!usedFinalNames.has(candidate)) {
        usedFinalNames.add(candidate);
        return candidate;
      }
    }
    const baseName = terrain + " Region";
    let suffix = 2;
    let candidate = baseName;
    while (usedFinalNames.has(candidate)) candidate = baseName + " " + suffix++;
    usedFinalNames.add(candidate);
    return candidate;
  }

  while (true) {
    const undersized = [...groupsById.values()]
      .filter((group) => group.indexes.length < minSize)
      .sort((a, b) => a.indexes.length - b.indexes.length);
    if (undersized.length === 0) break;

    let merged = false;
    for (const source of undersized) {
      if (!groupsById.has(source.region.id)) continue;
      const sourceTerrain = dominantTerrain(source.indexes);
      const sharedBorders = new Map<string, number>();
      for (const index of source.indexes) {
        for (const neighborIndex of getNeighborIndexes(
          hexes,
          indexByCoord,
          index,
        )) {
          const neighborId = hexes[neighborIndex].region_id;
          if (!neighborId || neighborId === source.region.id) continue;
          sharedBorders.set(
            neighborId,
            (sharedBorders.get(neighborId) ?? 0) + 1,
          );
        }
      }
      const candidates = [...sharedBorders.entries()]
        .map(([id, sharedBorderLength]) => {
          const target = groupsById.get(id);
          if (!target) return null;
          const wouldBeSize = target.indexes.length + source.indexes.length;
          return {
            target,
            sharedBorderLength,
            sameTerrain: dominantTerrain(target.indexes) === sourceTerrain,
            wouldBeSize,
          };
        })
        .filter((value): value is NonNullable<typeof value> => Boolean(value));
      if (candidates.length === 0) continue;

      const validCandidates = candidates.filter(
        (candidate) => candidate.wouldBeSize <= maxSize,
      );
      const pool = validCandidates.length > 0 ? validCandidates : candidates;
      pool.sort(
        (a, b) =>
          Number(b.sameTerrain) - Number(a.sameTerrain) ||
          b.sharedBorderLength - a.sharedBorderLength ||
          a.wouldBeSize - b.wouldBeSize ||
          a.target.indexes.length - b.target.indexes.length ||
          a.target.region.name.localeCompare(b.target.region.name),
      );
      const chosen = pool[0];
      for (const index of source.indexes)
        hexes[index].region_id = chosen.target.region.id;
      chosen.target.indexes.push(...source.indexes);
      groupsById.delete(source.region.id);
      merged = true;
      break;
    }

    if (!merged) break;
  }

  for (const group of groupsById.values()) {
    const finalName = pickFinalRegionName(dominantTerrain(group.indexes));
    group.region.name = finalName;
    group.region.base_difficulty = 1;
  }

  const regionGraph = new Map<string, Set<string>>();
  for (const region of groupsById.values())
    regionGraph.set(region.region.id, new Set());
  for (let i = 0; i < hexes.length; i++) {
    const regionId = hexes[i].region_id;
    const neighbors = regionGraph.get(regionId);
    if (!neighbors) continue;
    for (const neighborIndex of getNeighborIndexes(hexes, indexByCoord, i)) {
      const neighborId = hexes[neighborIndex].region_id;
      if (neighborId && neighborId !== regionId) neighbors.add(neighborId);
    }
  }

  const regions = [...groupsById.values()].map((group) => group.region);
  const regionById = new Map(
    regions.map((region) => [region.id, region] as const),
  );
  const promotedRandomCount = Math.max(0, Math.floor(regions.length * 0.25));

  const strongCandidates = () =>
    regions.filter((region) => {
      if (region.base_difficulty !== 1) return false;
      for (const neighborId of regionGraph.get(region.id) ?? []) {
        if ((regionById.get(neighborId)?.base_difficulty ?? 0) > 1)
          return false;
      }
      return true;
    });

  function isPromotableNeighbor(
    neighbor: Region | undefined,
  ): neighbor is Region {
    if (!neighbor) return false;
    return neighbor.base_difficulty === 1;
  }

  for (let iteration = 0; iteration < strongIterations; iteration++) {
    const candidates = strongCandidates();
    if (candidates.length === 0) break;
    const region = rng.pick(candidates);
    region.base_difficulty = 3;
    const neighbors = [...(regionGraph.get(region.id) ?? [])]
      .map((id) => regionById.get(id))
      .filter(isPromotableNeighbor);
    const pickedNeighbors = rng
      .shuffle(neighbors)
      .slice(0, Math.min(promotedNeighborCount, neighbors.length));
    for (const neighbor of pickedNeighbors) neighbor.base_difficulty = 2;
  }

  const easyRegions = regions.filter((region) => region.base_difficulty === 1);
  const pickedEasyRegions = rng
    .shuffle(easyRegions)
    .slice(0, Math.min(promotedRandomCount, easyRegions.length));
  for (const region of pickedEasyRegions) region.base_difficulty = 2;

  return regions;
}

function pickRandomWallPointIndex(hexes: Hex[], rng: RNG): number {
  const walls: Wall[] = ["top", "right", "bottom", "left"];
  const minX = Math.min(...hexes.map((h) => h.x));
  const maxX = Math.max(...hexes.map((h) => h.x));
  const minY = Math.min(...hexes.map((h) => h.y));
  const maxY = Math.max(...hexes.map((h) => h.y));
  function wallFor(hex: Hex): Wall[] {
    const result: Wall[] = [];
    if (hex.y === minY) result.push("top");
    if (hex.x === maxX) result.push("right");
    if (hex.y === maxY) result.push("bottom");
    if (hex.x === minX) result.push("left");
    return result;
  }
  const wallToIndexes = new Map<Wall, number[]>();
  for (const wall of walls) wallToIndexes.set(wall, []);
  for (let i = 0; i < hexes.length; i++)
    for (const wall of wallFor(hexes[i])) wallToIndexes.get(wall)!.push(i);
  const availableWalls = walls.filter(
    (w) => (wallToIndexes.get(w) ?? []).length > 0,
  );
  if (availableWalls.length < 2) return 0;
  const wall = rng.pick(availableWalls);
  return rng.pick(wallToIndexes.get(wall)!);
}

function makeWorldEntities(
  hexes: Hex[],
  regions: Region[],
  cityTokens: CityEntity[],
) {
  return [
    ...regions.map((region) =>
      createEntity<RegionEntity>("region", region.id, region),
    ),
    ...hexes.map((hex) => createEntity<HexEntity>("hex", hex.name, hex)),
    ...cityTokens,
  ];
}

function buildAllRandom(seed: string): GeneratedWorld {
  const rng = new RNG(`${seed}:allRandom`);
  const hexes = buildHexes(20, 20);
  const hexByName = new Map(hexes.map((hex) => [hex.name, hex] as const));
  for (const hex of hexes) {
    hex.terrain = rng.pick(allRandomTerrains);
    hex.region_id = rng.pick(allRandomRegions).id;
  }
  applyRandomClaims(hexes, rng);
  const regions = allRandomRegions.map((region) => ({ ...region }));
  const cityTokens = makeCityEntities();
  placeCities(hexes, cityTokens, rng);
  return {
    hexes,
    hexByName,
    regions,
    entities: makeWorldEntities(hexes, regions, cityTokens),
  };
}

type Temperature = "tropical" | "arctic" | "temperate";

function buildEmpire(seed: string): GeneratedWorld {
  const rng = new RNG(`${seed}:empire`);
  const width = 28;
  const height = 30;
  const hexes = buildHexes(width, height);
  const hexByName = new Map(hexes.map((hex) => [hex.name, hex] as const));
  const heightNoise = new PerlinNoise(`${seed}:empire:height`);
  const temperatureMap = new Map<string, Temperature>();
  const arcticTransitions = new Array<number>();
  const tropicalTransitions = new Array<number>();
  for (let i = 0; i < width; i++) {
    arcticTransitions.push(rng.next());
    tropicalTransitions.push(rng.next());
  }
  const arcticEnd = Math.floor(height * 0.2);
  const temperateStart = Math.floor(height * 0.3);
  const temperateEnd = Math.floor(height * 0.6);
  const tropicalStart = Math.floor(height * 0.7);
  const tropicalEnd = height;
  for (const hex of hexes) {
    const heightValue = noiseValue(heightNoise, hex.q, hex.r, 0.12, 4);
    if (hex.y <= arcticEnd) temperatureMap.set(hex.name, "arctic");
    else if (hex.y < temperateStart)
      temperatureMap.set(
        hex.name,
        (hex.y - arcticEnd) / (temperateStart - arcticEnd) <
          arcticTransitions[hex.x]
          ? "arctic"
          : "temperate",
      );
    else if (hex.y <= temperateEnd) temperatureMap.set(hex.name, "temperate");
    else if (hex.y < tropicalStart)
      temperatureMap.set(
        hex.name,
        (hex.y - temperateEnd) / (tropicalStart - temperateEnd) <
          tropicalTransitions[hex.x]
          ? "temperate"
          : "tropical",
      );
    else temperatureMap.set(hex.name, "tropical");

    if (heightValue >= 0.65) hex.terrain = "Mountain";
    else if (heightValue >= 0.58) hex.terrain = "Hills";
    else if (temperatureMap.get(hex.name) === "arctic") hex.terrain = "Tundra";
    else if (temperatureMap.get(hex.name) === "temperate")
      hex.terrain = "Plains";
    else hex.terrain = "Savannah";
  }
  const indexByCoord = new Map<string, number>();
  for (let i = 0; i < hexes.length; i++)
    indexByCoord.set(`${hexes[i].q},${hexes[i].r}`, i);
  const curSeaArray = pickRandomWallPath(hexes, indexByCoord, rng).slice(
    0,
    Math.floor(Math.min(width, height) / 2),
  );
  curSeaArray.push(pickRandomWallPointIndex(hexes, rng));
  for (const idx of curSeaArray) hexes[idx].terrain = "Water";
  spreadHexes(
    hexes,
    indexByCoord,
    rng,
    curSeaArray,
    Math.floor(hexes.length * 0.2),
    (h: Hex) => h.terrain !== "Water",
    (h: Hex) => (h.terrain = "Water"),
  );

  const numForestSeeds = Math.floor(hexes.length * 0.05);
  function canForest(hex: Hex) {
    return (
      hex.terrain === "Hills" ||
      hex.terrain === "Plains" ||
      hex.terrain === "Savannah"
    );
  }
  const curForestArray: number[] = [];
  for (let i = 0; i < numForestSeeds; i++) {
    const idx = rng.int(hexes.length);
    if (!canForest(hexes[idx])) {
      if (hexes[idx].terrain === "Water" || hexes[idx].terrain === "Tundra")
        hexes[idx].terrain = "Forest";
      continue;
    }
    curForestArray.push(idx);
    hexes[idx].terrain = "Forest";
  }
  spreadHexes(
    hexes,
    indexByCoord,
    rng,
    curForestArray,
    Math.floor(hexes.length * 0.2),
    canForest,
    (h: Hex) => (h.terrain = "Forest"),
  );
  for (const hex of hexes)
    if (temperatureMap.get(hex.name) === "tropical" && hex.terrain === "Forest")
      hex.terrain = "Jungle";

  const numGlacierSeeds = 6 + rng.int(4);
  function canGlacier(hex: Hex) {
    return hex.y >= 0 && hex.y <= arcticEnd;
  }
  const curGlacierArray: number[] = [];
  for (let i = 0; i < numGlacierSeeds; i++) {
    let idx = rng.int(hexes.length);
    while (!canGlacier(hexes[idx])) idx = rng.int(hexes.length);
    curGlacierArray.push(idx);
    hexes[idx].terrain = "Glacier";
  }
  spreadHexes(
    hexes,
    indexByCoord,
    rng,
    curGlacierArray,
    6,
    canGlacier,
    (h: Hex) => (h.terrain = "Glacier"),
  );

  const numSwampSeeds = 4;
  function canSwamp(hex: Hex) {
    return hex.terrain === "Jungle";
  }
  const curSwampArray: number[] = [];
  for (let i = 0; i < numSwampSeeds; i++) {
    let idx = rng.int(hexes.length);
    while (!canSwamp(hexes[idx])) idx = rng.int(hexes.length);
    curSwampArray.push(idx);
    hexes[idx].terrain = "Swamp";
  }
  spreadHexes(
    hexes,
    indexByCoord,
    rng,
    curSwampArray,
    8,
    canSwamp,
    (h: Hex) => (h.terrain = "Swamp"),
  );

  const numDesertSeeds = 6 + rng.int(4);
  function canDesert(hex: Hex) {
    return (
      (hex.terrain === "Savannah" || hex.terrain === "Jungle") &&
      hex.y >= temperateStart &&
      hex.y <= tropicalEnd
    );
  }
  const curDesertArray: number[] = [];
  for (let i = 0; i < numDesertSeeds; i++) {
    let idx = rng.int(hexes.length);
    while (!canDesert(hexes[idx])) idx = rng.int(hexes.length);
    curDesertArray.push(idx);
    hexes[idx].terrain = "Desert";
  }
  spreadHexes(
    hexes,
    indexByCoord,
    rng,
    curDesertArray,
    40,
    canDesert,
    (h: Hex) => (h.terrain = "Desert"),
  );

  const regions = assignEmpireRegions(hexes, indexByCoord, rng);
  applyRandomClaims(hexes, rng);
  const cityTokens = makeCityEntities();
  placeCities(hexes, cityTokens, rng);
  return {
    hexes,
    hexByName,
    regions,
    entities: makeWorldEntities(hexes, regions, cityTokens),
  };
}

export function buildWorld(options: MapOptions) {
  return options.generator === "empire"
    ? buildEmpire(options.seed)
    : buildAllRandom(options.seed);
}

export async function loadOrGenerateWorld(options: MapOptions) {
  if (await fileExists(mapFilePath)) {
    try {
      return await loadMap(mapFilePath);
    } catch (error) {
      console.warn("Failed to load saved map, regenerating it", error);
    }
  }
  const generated = buildWorld(options);
  await saveMap(mapFilePath, {
    hexes: generated.hexes,
    entities: generated.entities,
    regions: generated.regions,
  });
  return generated;
}
