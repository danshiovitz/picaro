import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { RNG } from './random.js';
import { PerlinNoise, noiseValue } from './noise.js';
import { hexName, hexDirs, pickRandomWallPath } from './hexmap.js';
import { claims, regions, cityTokens, setCityTokens } from './data.js';
const allRandomTerrains = ['Forest', 'Deep Forest', 'Desert', 'Water', 'Plains', 'Mountain', 'Hills', 'Swamp', 'Tundra', 'Jungle', 'Badlands', 'Marsh'];
const mapFilePath = resolve(process.cwd(), process.env['MAP_FILE'] ?? 'data/map.json');
async function fileExists(filePath) {
    try {
        await access(filePath);
        return true;
    }
    catch {
        return false;
    }
}
export async function saveMap(filePath, state) {
    await mkdir(dirname(filePath), { recursive: true });
    await writeFile(filePath, JSON.stringify(state, null, 2), 'utf8');
}
export async function loadMap(filePath) {
    const raw = await readFile(filePath, 'utf8');
    const state = JSON.parse(raw);
    if (!Array.isArray(state.hexes) || !Array.isArray(state.entities))
        throw new Error('Invalid map save file');
    setCityTokens(state.entities);
    return { hexes: state.hexes, hexByName: new Map(state.hexes.map(hex => [hex.name, hex])), entities: state.entities };
}
function buildHexes(width, height) {
    const hexes = [];
    for (let y = 0; y < height; y++)
        for (let x = 0; x < width; x++)
            hexes.push({ name: hexName(x, y), x, y, q: x - Math.floor(y / 2), r: y, terrain: 'Plains', region: 'Valley of Aardia', claims: [], tokens: [] });
    return hexes;
}
function placeToken(hexes, used, token, index, rng) {
    let idx = index ?? rng.int(hexes.length);
    while (used.has(idx))
        idx = rng.int(hexes.length);
    used.add(idx);
    hexes[idx].tokens.push(token.id);
}
function applyRandomClaims(hexes, rng) {
    for (const hex of hexes) {
        const n = rng.int(4);
        hex.claims = [...claims].sort(() => rng.next() - .5).slice(0, n).map(claim => claim.name);
    }
}
function placeCities(hexes, rng) {
    const used = new Set();
    placeToken(hexes, used, cityTokens[0], 42, rng);
    for (const token of cityTokens.slice(1))
        placeToken(hexes, used, token, undefined, rng);
}
function spreadHexes(hexes, indexByCoord, rng, startIndexes, tries, canFunc, spreadFunc) {
    let curArray = [];
    let curSet = new Set(startIndexes);
    let nextArray = [...startIndexes];
    for (let i = 0; i < tries; i++) {
        if (curArray.length === 0) {
            curArray = rng.shuffle(nextArray);
            nextArray = [];
            if (curArray.length === 0)
                break;
        }
        const curIdx = curArray.pop();
        if (curIdx === undefined)
            continue;
        const hex = hexes[curIdx];
        const nghs = [];
        for (const [dq, dr] of hexDirs()) {
            const neighborIndex = indexByCoord.get(`${hex.q + dq},${hex.r + dr}`);
            if (neighborIndex !== undefined && !curSet.has(neighborIndex) && canFunc(hexes[neighborIndex]))
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
function pickRandomWallPointIndex(hexes, rng) {
    const walls = ['top', 'right', 'bottom', 'left'];
    const minX = Math.min(...hexes.map(h => h.x));
    const maxX = Math.max(...hexes.map(h => h.x));
    const minY = Math.min(...hexes.map(h => h.y));
    const maxY = Math.max(...hexes.map(h => h.y));
    function wallFor(hex) {
        const result = [];
        if (hex.y === minY)
            result.push('top');
        if (hex.x === maxX)
            result.push('right');
        if (hex.y === maxY)
            result.push('bottom');
        if (hex.x === minX)
            result.push('left');
        return result;
    }
    const wallToIndexes = new Map();
    for (const wall of walls)
        wallToIndexes.set(wall, []);
    for (let i = 0; i < hexes.length; i++)
        for (const wall of wallFor(hexes[i]))
            wallToIndexes.get(wall).push(i);
    const availableWalls = walls.filter(w => (wallToIndexes.get(w) ?? []).length > 0);
    if (availableWalls.length < 2)
        return 0;
    const wall = rng.pick(availableWalls);
    return rng.pick(wallToIndexes.get(wall));
}
function buildAllRandom(seed) {
    const rng = new RNG(`${seed}:allRandom`);
    const hexes = buildHexes(20, 20);
    const hexByName = new Map(hexes.map(hex => [hex.name, hex]));
    for (const hex of hexes) {
        hex.terrain = rng.pick(allRandomTerrains);
        hex.region = rng.pick(regions).name;
    }
    applyRandomClaims(hexes, rng);
    placeCities(hexes, rng);
    return { hexes, hexByName, entities: [...cityTokens] };
}
function buildEmpire(seed) {
    const rng = new RNG(`${seed}:empire`);
    const width = 28;
    const height = 30;
    const hexes = buildHexes(width, height);
    const hexByName = new Map(hexes.map(hex => [hex.name, hex]));
    const heightNoise = new PerlinNoise(`${seed}:empire:height`);
    const temperatureMap = new Map();
    const arcticTransitions = new Array();
    const tropicalTransitions = new Array();
    for (let i = 0; i < width; i++) {
        arcticTransitions.push(rng.next());
        tropicalTransitions.push(rng.next());
    }
    const arcticEnd = Math.floor(height * 0.20);
    const temperateStart = Math.floor(height * 0.30);
    const temperateEnd = Math.floor(height * 0.60);
    const tropicalStart = Math.floor(height * 0.70);
    const tropicalEnd = height;
    for (const hex of hexes) {
        const heightValue = noiseValue(heightNoise, hex.q, hex.r, .12, 4);
        if (hex.y <= arcticEnd)
            temperatureMap.set(hex.name, 'arctic');
        else if (hex.y < temperateStart)
            temperatureMap.set(hex.name, (hex.y - arcticEnd) / (temperateStart - arcticEnd) < arcticTransitions[hex.x] ? 'arctic' : 'temperate');
        else if (hex.y <= temperateEnd)
            temperatureMap.set(hex.name, 'temperate');
        else if (hex.y < tropicalStart)
            temperatureMap.set(hex.name, (hex.y - temperateEnd) / (tropicalStart - temperateEnd) < tropicalTransitions[hex.x] ? 'temperate' : 'tropical');
        else
            temperatureMap.set(hex.name, 'tropical');
        if (heightValue >= 0.77)
            hex.terrain = 'Mountain';
        else if (heightValue >= 0.65)
            hex.terrain = 'Hills';
        else if (temperatureMap.get(hex.name) === 'arctic')
            hex.terrain = 'Tundra';
        else if (temperatureMap.get(hex.name) === 'temperate')
            hex.terrain = 'Plains';
        else
            hex.terrain = 'Savannah';
    }
    const indexByCoord = new Map();
    for (let i = 0; i < hexes.length; i++)
        indexByCoord.set(`${hexes[i].q},${hexes[i].r}`, i);
    const curSeaArray = pickRandomWallPath(hexes, indexByCoord, rng).slice(0, Math.floor(Math.min(width, height) / 2));
    curSeaArray.push(pickRandomWallPointIndex(hexes, rng));
    for (const idx of curSeaArray)
        hexes[idx].terrain = 'Water';
    spreadHexes(hexes, indexByCoord, rng, curSeaArray, Math.floor(hexes.length * .2), (h) => h.terrain !== 'Water', (h) => h.terrain = 'Water');
    const numForestSeeds = Math.floor(hexes.length * .05);
    function canForest(hex) { return hex.terrain === 'Hills' || hex.terrain === 'Plains' || hex.terrain === 'Savannah'; }
    const curForestArray = [];
    for (let i = 0; i < numForestSeeds; i++) {
        const idx = rng.int(hexes.length);
        if (!canForest(hexes[idx])) {
            if (hexes[idx].terrain === 'Water' || hexes[idx].terrain === 'Tundra')
                hexes[idx].terrain = 'Forest';
            continue;
        }
        curForestArray.push(idx);
        hexes[idx].terrain = 'Forest';
    }
    spreadHexes(hexes, indexByCoord, rng, curForestArray, Math.floor(hexes.length * .20), canForest, (h) => h.terrain = 'Forest');
    for (const hex of hexes)
        if (temperatureMap.get(hex.name) === 'tropical' && hex.terrain === 'Forest')
            hex.terrain = 'Jungle';
    const numGlacierSeeds = 6 + rng.int(4);
    function canGlacier(hex) { return hex.y >= 0 && hex.y <= arcticEnd; }
    const curGlacierArray = [];
    for (let i = 0; i < numGlacierSeeds; i++) {
        let idx = rng.int(hexes.length);
        while (!canGlacier(hexes[idx]))
            idx = rng.int(hexes.length);
        curGlacierArray.push(idx);
        hexes[idx].terrain = 'Glacier';
    }
    spreadHexes(hexes, indexByCoord, rng, curGlacierArray, 6, canGlacier, (h) => h.terrain = 'Glacier');
    const numSwampSeeds = 4;
    function canSwamp(hex) { return hex.terrain === 'Jungle'; }
    const curSwampArray = [];
    for (let i = 0; i < numSwampSeeds; i++) {
        let idx = rng.int(hexes.length);
        while (!canSwamp(hexes[idx]))
            idx = rng.int(hexes.length);
        curSwampArray.push(idx);
        hexes[idx].terrain = 'Swamp';
    }
    spreadHexes(hexes, indexByCoord, rng, curSwampArray, 8, canSwamp, (h) => h.terrain = 'Swamp');
    const numDesertSeeds = 6 + rng.int(4);
    function canDesert(hex) { return (hex.terrain === 'Savannah' || hex.terrain === 'Jungle') && hex.y >= temperateStart && hex.y <= tropicalEnd; }
    const curDesertArray = [];
    for (let i = 0; i < numDesertSeeds; i++) {
        let idx = rng.int(hexes.length);
        while (!canDesert(hexes[idx]))
            idx = rng.int(hexes.length);
        curDesertArray.push(idx);
        hexes[idx].terrain = 'Desert';
    }
    spreadHexes(hexes, indexByCoord, rng, curDesertArray, 40, canDesert, (h) => h.terrain = 'Desert');
    for (const hex of hexes)
        hex.region = rng.pick(regions).name;
    applyRandomClaims(hexes, rng);
    placeCities(hexes, rng);
    return { hexes, hexByName, entities: [...cityTokens] };
}
export function buildWorld(options) {
    return options.generator === 'empire' ? buildEmpire(options.seed) : buildAllRandom(options.seed);
}
export async function loadOrGenerateWorld(options) {
    if (await fileExists(mapFilePath)) {
        try {
            return await loadMap(mapFilePath);
        }
        catch (error) {
            console.warn('Failed to load saved map, regenerating it', error);
        }
    }
    const generated = buildWorld(options);
    await saveMap(mapFilePath, { hexes: generated.hexes, entities: generated.entities });
    return generated;
}
