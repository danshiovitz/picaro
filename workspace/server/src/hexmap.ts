import {Terrain,Region,Claim,Token,Hex,PlayerEntity,EncounterSkillCheck,ActiveEncounterSkillCheck,TableauCard,ActiveEncounter} from './types.js';
import {RNG} from './random.js';

function rowLabel(index:number): string{
 if(index<0)return "-"+rowLabel(26+index);
 if(index<26)return String.fromCharCode(65+index);
 const letter=String.fromCharCode(65+((index-26)%26));
 return `${letter}${letter}`;
}

export function hexDistance(a:Hex,b:Hex){return (Math.abs(a.q-b.q)+Math.abs(a.q+a.r-b.q-b.r)+Math.abs(a.r-b.r))/2}

export function hexName(x:number,y:number){return `${rowLabel(y)}${x+1}`;}

export function hexDirs(){return [[1,0],[1,-1],[0,-1],[-1,0],[-1,1],[0,1]] as const;}

export function getNeighborIndexes(
    hexes: Hex[],
    indexByCoord: Map<string, number>,
    index: number
): number[] {
    const hex = hexes[index];
    if (!hex) return [];

    const neighbors: number[] = [];
    for (const [dq, dr] of hexDirs()) {
    const neighborIndex = indexByCoord.get(`${hex.q + dq},${hex.r + dr}`);
    if (neighborIndex !== undefined) neighbors.push(neighborIndex);
    }
    return neighbors;
}

export function shortestHexPath(
    hexes: Hex[],
    indexByCoord: Map<string, number>,
    startIndex: number,
    endIndex: number
): number[] {
    if (startIndex === endIndex) return [startIndex];

    const queue: number[] = [startIndex];
    const cameFrom = new Map<number, number | null>();
    cameFrom.set(startIndex, null);

    while (queue.length > 0) {
    const current = queue.shift()!;
    for (const neighbor of getNeighborIndexes(hexes, indexByCoord, current)) {
        if (cameFrom.has(neighbor)) continue;
        cameFrom.set(neighbor, current);

        if (neighbor === endIndex) {
        const path: number[] = [];
        let cursor: number | null = endIndex;
        while (cursor !== null) {
            path.push(cursor);
            cursor = cameFrom.get(cursor) ?? null;
        }
        return path.reverse();
        }

        queue.push(neighbor);
    }
    }

    return [];
}

type Wall = 'top' | 'right' | 'bottom' | 'left';

export function pickRandomWallPoint(
    hexes: Hex[],
    rng: RNG
): number {
    const walls: Wall[] = ['top', 'right', 'bottom', 'left'];

    function wallFor(hex: Hex): Wall[] {
    const minX = Math.min(...hexes.map(h => h.x));
    const maxX = Math.max(...hexes.map(h => h.x));
    const minY = Math.min(...hexes.map(h => h.y));
    const maxY = Math.max(...hexes.map(h => h.y));

    const result: Wall[] = [];
    if (hex.y === minY) result.push('top');
    if (hex.x === maxX) result.push('right');
    if (hex.y === maxY) result.push('bottom');
    if (hex.x === minX) result.push('left');
    return result;
    }

    const wallToIndexes = new Map<Wall, number[]>();
    for (const wall of walls) wallToIndexes.set(wall, []);

    for (let i = 0; i < hexes.length; i++) {
    const hex = hexes[i];
    for (const wall of wallFor(hex)) {
        wallToIndexes.get(wall)!.push(i);
    }
    }

    const availableWalls = walls.filter(w => (wallToIndexes.get(w) ?? []).length > 0);
    if (availableWalls.length < 2) {
        console.log("Not enough walls?");
        return 0;
    };

    const wall = rng.pick(availableWalls);
    return rng.pick(wallToIndexes.get(wall)!);
}

export function pickRandomWallPath(
    hexes: Hex[],
    indexByCoord: Map<string, number>,
    rng: RNG
): number[] {
    let startIndex = pickRandomWallPoint(hexes, rng);
    let endIndex = pickRandomWallPoint(hexes, rng);
    while (hexes[startIndex].x == hexes[endIndex].x || hexes[startIndex].y == hexes[endIndex].y) endIndex = pickRandomWallPoint(hexes, rng);

    return shortestHexPath(hexes, indexByCoord, startIndex, endIndex);
}
