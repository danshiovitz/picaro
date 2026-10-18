import http from 'node:http';
import {URL} from 'node:url';
import crypto from 'node:crypto';

type Terrain={name:string;color:string;icon:string};
type Region={name:string};
type Claim={name:string;icon:string};
type Token={id:string;entityName:string;icon:string};
type AxialPoint = { q: number; r: number };
type Hex={name:string;x:number;y:number;q:number;r:number;terrain:string;region:string;claims:string[];tokens:string[]};
type PlayerEntity={name:string;tokenId:string;curHealth:number;maxHealth:number;curLuck:number;maxLuck:number;gold:number;reputation:number;turns:number;location:string};
type EncounterSkillCheck={name:string;target:number};
type ActiveEncounterSkillCheck={name:string;target:number;roll:number;modifier:number;total:number;success:boolean};
type TableauCard={id:string;title:string;location:string;difficulty:number;rewards:string[];penalties:string[];skillChecks:EncounterSkillCheck[]};
type ActiveEncounter={id:string;title:string;rewards:string[];penalties:string[];skillChecks:ActiveEncounterSkillCheck[]};
type MapGeneratorName='allRandom'|'empire';

type GeneratedWorld={hexes:Hex[];hexByName:Map<string,Hex>;tokens:Token[]};

type MapOptions={generator:MapGeneratorName;seed:string};

class RNG {
 private state:number;
 constructor(seed:string){this.state=hashSeed(seed)||0x1a2b3c4d;}
 next(){
  let t=this.state+=0x6D2B79F5;
  t=Math.imul(t^(t>>>15),t|1);
  t^=t+Math.imul(t^(t>>>7),t|61);
  return ((t^(t>>>14))>>>0)/4294967296;
 }
 int(max:number){return Math.floor(this.next()*max);}
 range(min:number,max:number){return min+this.int(max-min+1);}
 pick<T>(items:T[]){return items[this.int(items.length)];}
 shuffle<T>(items:T[]){
  const copy=[...items];
  for(let i=copy.length-1;i>0;i--){
   const j=this.int(i+1);
   [copy[i],copy[j]]=[copy[j],copy[i]];
  }
  return copy;
 }
 d6(){return this.range(1,6);}
}

class PerlinNoise {
 private perm:number[];
 constructor(seed:string){
  const rng=new RNG(seed);
  const p=[...Array(256).keys()];
  for(let i=p.length-1;i>0;i--){
   const j=rng.int(i+1);
   [p[i],p[j]]=[p[j],p[i]];
  }
  this.perm=[...p,...p];
 }
 private fade(t:number){return t*t*t*(t*(t*6-15)+10);}
 private lerp(a:number,b:number,t:number){return a+t*(b-a);}
 private grad(hash:number,x:number,y:number){
  switch(hash&3){
   case 0:return x+y;
   case 1:return -x+y;
   case 2:return x-y;
   default:return -x-y;
  }
 }
 noise(x:number,y:number){
  const xi=Math.floor(x)&255;
  const yi=Math.floor(y)&255;
  const xf=x-Math.floor(x);
  const yf=y-Math.floor(y);
  const u=this.fade(xf);
  const v=this.fade(yf);
  const aa=this.perm[this.perm[xi]+yi];
  const ab=this.perm[this.perm[xi]+yi+1];
  const ba=this.perm[this.perm[xi+1]+yi];
  const bb=this.perm[this.perm[xi+1]+yi+1];
  const x1=this.lerp(this.grad(aa,xf,yf),this.grad(ba,xf-1,yf),u);
  const x2=this.lerp(this.grad(ab,xf,yf-1),this.grad(bb,xf-1,yf-1),u);
  return (this.lerp(x1,x2,v)+1)/2;
 }
}

const terrainSpecs:Terrain[]=[
 ['Forest','#1a531e','forest'],
 ['Deep Forest','#14552a','deep-forest'],
 ['Desert','#d8b45f','desert'],
 ['Water','#3182bd','water'],
 ['Plains','#9fca62','plains'],
 ['Mountain','#8a8178','mountain'],
 ['Hills','#a68b55','hills'],
 ['Swamp','#a42d8e','swamp'],
 ['Tundra','#81cbe8','tundra'],
 ['Jungle','#15de4a','jungle'],
 ['Badlands','#b86945','badlands'],
 ['Marsh','#6c9272','marsh'],
 ['Glacier','#e9f6ff','glacier'],
 ['Savannah','#d7ae7f','savannah'],
].map(([name,color,icon])=>({name,color,icon}));
const terrainByName=new Map(terrainSpecs.map(terrain=>[terrain.name,terrain] as const));
const allRandomTerrains=['Forest','Deep Forest','Desert','Water','Plains','Mountain','Hills','Swamp','Tundra','Jungle','Badlands','Marsh'];
const regionNames=['Valley of Aardia','Domain of the Elves','Iron Marches','Sunspire Coast','Gloaming Fens','Kingdom of Roses','Storm Peaks','Amber Wastes','Silverwood','Riverlands','Crown Basin','Ashen Reach','Sapphire Isles','Old Empire','Whispering Downs','Dragonmere','Golden Steppe','Umbral Vale','Free Cities'];
const regions:Region[]=regionNames.map(name=>({name}));
const claimColors=['red','yellow','blue','green','purple','orange'];
const claims:Claim[]=claimColors.map((icon,i)=>({name:`Faction ${i+1}`,icon}));

let nextTokenId=1;
const makeTokenId=()=>`token-${nextTokenId++}`;
const playerTokens:Token[]=[1,2,3,4].map(i=>({id:makeTokenId(),entityName:`Player ${i}`,icon:`player${i}`}));
const cityTokens:Token[]=['Waterdeep','Underhaven','Dawnport','Ironford','Moonfall','Highspire','Blackwell','Greengate'].map(n=>({id:makeTokenId(),entityName:`City of ${n}`,icon:'city'}));
const tokens=[...playerTokens,...cityTokens];

function hashSeed(seed:string){
 let h=2166136261;
 for(let i=0;i<seed.length;i++){
  h^=seed.charCodeAt(i);
  h=Math.imul(h,16777619);
 }
 return h>>>0;
}

function rowLabel(index:number): string{
 if(index<0)return "-"+rowLabel(26+index);
 if(index<26)return String.fromCharCode(65+index);
 const letter=String.fromCharCode(65+((index-26)%26));
 return `${letter}${letter}`;
}

function hexDistance(a:Hex,b:Hex){return (Math.abs(a.q-b.q)+Math.abs(a.q+a.r-b.q-b.r)+Math.abs(a.r-b.r))/2}
function hexName(x:number,y:number){return `${rowLabel(y)}${x+1}`;}
function hexDirs(){return [[1,0],[1,-1],[0,-1],[-1,0],[-1,1],[0,1]] as const;}
function erf(x:number){
 const sign=x<0?-1:1;
 const abs=Math.abs(x);
 const a1=.254829592, a2=-.284496736, a3=1.421413741, a4=-1.453152027, a5=1.061405429, p=.3275911;
 const t=1/(1+p*abs);
 const y=1-((((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*Math.exp(-abs*abs));
 return sign*y;
}
function cdf01(value:number){
 const centered=(value-.5)/.18;
 return Math.max(0,Math.min(1,.5*(1+erf(centered/Math.SQRT2))));
}
function noiseValue(noise:PerlinNoise,x:number,y:number,scale:number,octaves=4){
 let value=0;
 let amplitude=.5;
 let frequency=2;
 let totalAmplitude=0;
 for(let i=0;i<octaves;i++){
  value+=noise.noise(x*scale*frequency,y*scale*frequency)*amplitude;
  totalAmplitude+=amplitude;
  amplitude*=.5;
  frequency*=2;
 }
 return cdf01(value/totalAmplitude);
}
function placeToken(hexes:Hex[],used:Set<number>,token:Token,index:number|undefined,rng:RNG){
 let idx=index??rng.int(hexes.length);
 while(used.has(idx))idx=rng.int(hexes.length);
 used.add(idx);
 hexes[idx].tokens.push(token.id);
}

type Wall = 'top' | 'right' | 'bottom' | 'left';

function getNeighborIndexes(
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

function shortestHexPath(
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

function pickRandomWallPoint(
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

function pickRandomWallPath(
    hexes: Hex[],
    indexByCoord: Map<string, number>,
    rng: RNG
): number[] {
    let startIndex = pickRandomWallPoint(hexes, rng);
    let endIndex = pickRandomWallPoint(hexes, rng);
    while (hexes[startIndex].x == hexes[endIndex].x || hexes[startIndex].y == hexes[endIndex].y) endIndex = pickRandomWallPoint(hexes, rng);

    return shortestHexPath(hexes, indexByCoord, startIndex, endIndex);
}

function spreadHexes(hexes: Hex[], indexByCoord: Map<string, number>, rng: RNG, startIndexes: number[], tries: number, canFunc: (h: Hex) => boolean, spreadFunc: (h: Hex) => void): void {
    let curArray = new Array<number>();
    let curSet = new Set<number>(startIndexes);
    let nextArray = startIndexes;
    for (let i = 0; i < tries; i++) {
        if (curArray.length == 0) {
            curArray = rng.shuffle(nextArray);
            nextArray = [];
            if (curArray.length == 0) {
                console.log("Ran out of neighbors!");
                break;
            }
        }
        const curIdx = curArray.pop();
        const hex = hexes[curIdx!];
        if (!hex) { continue; }
        
        let nghs = new Array<number>();
        for (const [dq, dr] of hexDirs()) {
            const neighborIndex = indexByCoord.get(`${hex.q + dq},${hex.r + dr}`);
            if (neighborIndex !== undefined && !curSet.has(neighborIndex) && canFunc(hexes[neighborIndex])) {
                nghs.push(neighborIndex);
            }
        }
        if (nghs.length > 0) {
            let nidx = rng.pick(nghs);
            curSet.add(nidx);
            nextArray.push(nidx);
            spreadFunc(hexes[nidx]);
        }
    }
}

function pickOutsidePoint(
    hexes: Hex[],
    distance: number,
    rng: RNG
): AxialPoint {
    const minX = Math.min(...hexes.map(h => h.x));
    const maxX = Math.max(...hexes.map(h => h.x));
    const minY = Math.min(...hexes.map(h => h.y));
    const maxY = Math.max(...hexes.map(h => h.y));

    const wall = rng.pick<Wall>(['top', 'right', 'bottom', 'left']);

    let x = 0;
    let y = 0;

    if (wall === 'top') {
    x = rng.range(minX, maxX);
    y = minY - distance;
    } else if (wall === 'bottom') {
    x = rng.range(minX, maxX);
    y = maxY + distance;
    } else if (wall === 'left') {
    x = minX - distance;
    y = rng.range(minY, maxY);
    } else {
    x = maxX + distance;
    y = rng.range(minY, maxY);
    }

    // Convert offset coords to axial coords the same way buildHexes() does.
    return {
        q: x - Math.floor(y / 2),
        r: y,
    };
}

function indexesWithinDistanceOfPoint(
    hexes: Hex[],
    point: AxialPoint,
    radius: number,
    callbackFunc: (h: Hex, distance: number) => void,
): void {
    const syntheticPoint = {
    name: 'outside-point',
    x: 0,
    y: 0,
    q: point.q,
    r: point.r,
    terrain: 'Plains',
    region: '',
    claims: [],
    tokens: [],
    } as Hex;

    const indexes: number[] = [];

    for (let i = 0; i < hexes.length; i++) {
        const hd = hexDistance(hexes[i], syntheticPoint);
        if (hd <= radius) {
            callbackFunc(hexes[i], hd);
        }
    }
}

function buildHexes(width:number,height:number):Hex[]{
 const hexes:Hex[]=[];
 for(let y=0;y<height;y++)for(let x=0;x<width;x++)hexes.push({name:hexName(x,y),x,y,q:x-Math.floor(y/2),r:y,terrain:'Plains',region:'Valley of Aardia',claims:[],tokens:[]});
 return hexes;
}
function applyRandomClaims(hexes:Hex[],rng:RNG){
 for(const hex of hexes){
  const n=rng.int(4);
  hex.claims=[...claims].sort(()=>rng.next()-.5).slice(0,n).map(claim=>claim.name);
 }
}
function placeCitiesLikeAllRandom(hexes:Hex[],rng:RNG){
 const used=new Set<number>();
 placeToken(hexes,used,cityTokens[0],42,rng);
 for(const token of cityTokens.slice(1))placeToken(hexes,used,token,undefined,rng);
}
function placePlayersAfterGeneration(hexes:Hex[],rng:RNG){
 const used=new Set<number>();
 // mirror the current overlap of Player 1 with the first city token.
 placeToken(hexes,used,playerTokens[0],42,rng);
 for(const token of playerTokens.slice(1))placeToken(hexes,used,token,undefined,rng);
}
function buildAllRandom(seed:string):GeneratedWorld{
 const rng=new RNG(`${seed}:allRandom`);
 const hexes=buildHexes(20,20);
 const hexByName=new Map(hexes.map(hex=>[hex.name,hex] as const));
 for(const hex of hexes){
  hex.terrain=rng.pick(allRandomTerrains);
  hex.region=rng.pick(regions).name;
 }
 applyRandomClaims(hexes,rng);
 placeCitiesLikeAllRandom(hexes,rng);
 placePlayersAfterGeneration(hexes,rng);
 return {hexes,hexByName,tokens:[...tokens]};
}
type Temperature = 'tropical' | 'arctic' | 'temperate';

function buildEmpire(seed:string):GeneratedWorld{
 const rng=new RNG(`${seed}:empire`);
 const width=28; //18+rng.d6()+rng.d6();
 const height=30; //18+rng.d6()+rng.d6();
 const hexes=buildHexes(width,height);
 const hexByName=new Map(hexes.map(hex=>[hex.name,hex] as const));
 const heightNoise=new PerlinNoise(`${seed}:empire:height`);
 const heightMap=new Map<string,number>();
 const temperatureMap=new Map<string,Temperature>();
 // temperature gradient is like:
 //   20% arctic, 10% transition, 30% temperate, 10% transition, 30% tropical
 const arcticTransitions = new Array<number>();
 const tropicalTransitions = new Array<number>();
 for (let i = 0; i < width; i++) {
    arcticTransitions.push(rng.next());
    tropicalTransitions.push(rng.next());
 }
 const arcticStart = 0;
 const arcticEnd = Math.floor(height * 0.20);
 const temperateStart = Math.floor(height * 0.30);
 const temperateEnd = Math.floor(height * 0.60);
 const tropicalStart = Math.floor(height * 0.70);
 const tropicalEnd = height;

 for(const hex of hexes){
  const heightValue=noiseValue(heightNoise,hex.q,hex.r,.12,4);
  heightMap.set(hex.name,heightValue);

  if (hex.y >= arcticStart && hex.y <= arcticEnd) {
    temperatureMap.set(hex.name, 'arctic');
  } else if (hex.y > arcticEnd && hex.y < temperateStart) {
    if ((hex.y - arcticEnd) / (temperateStart - arcticEnd) < arcticTransitions[hex.x]) {
        temperatureMap.set(hex.name, 'arctic');
    } else {
        temperatureMap.set(hex.name, 'temperate');
    }
  } else if (hex.y >= temperateStart && hex.y <= temperateEnd) {
    temperatureMap.set(hex.name, 'temperate');
  } else if (hex.y > temperateEnd && hex.y < tropicalStart) {
    if ((hex.y - temperateEnd) / (tropicalStart - temperateEnd) < tropicalTransitions[hex.x]) {
        temperatureMap.set(hex.name, 'temperate');
    } else {
        temperatureMap.set(hex.name, 'tropical');
    }
  } else if (hex.y >= tropicalStart && hex.y <= tropicalEnd) {
    temperatureMap.set(hex.name, 'tropical');
  } else {
    console.log("Unknown temperature zone ", hex.y);
    temperatureMap.set(hex.name, 'temperate');
  }

  if(heightValue>=0.77)hex.terrain='Mountain';
  else if (heightValue>=0.65)hex.terrain='Hills';
  else if (temperatureMap.get(hex.name) == 'arctic') {
    hex.terrain='Tundra';
  } else if (temperatureMap.get(hex.name) == 'temperate') {
    hex.terrain = 'Plains';
  } else {
    hex.terrain = 'Savannah';
  }
 } 

 
 /*
 const windDirection=hexDirs()[rng.int(6)];
 for(const hex of hexes){
  const heightValue=heightMap.get(hex.name)??0;
  let rainShadow=Math.floor((heightValue-0.65)/0.05);
  let q=hex.q;
  let r=hex.r;
  while(rainShadow>0){
   q+=windDirection[0];
   r+=windDirection[1];
   const target=hexes.find(candidate=>candidate.q===q&&candidate.r===r);
   if(target){
    moistureMap.set(target.name,(moistureMap.get(target.name)??0)-rainShadow*0.1);
   }
   rainShadow-=1;
  }
 }
  */
 
 const indexByCoord = new Map<string, number>();

 for (let i = 0; i < hexes.length; i++) {
   const hex = hexes[i];
   indexByCoord.set(`${hex.q},${hex.r}`, i);
 }

 const curSeaArray = pickRandomWallPath(hexes, indexByCoord, rng).slice(0, Math.floor(Math.min(width, height) / 2));
 // one more smaller sea somewhere:
 curSeaArray.push(pickRandomWallPoint(hexes, rng));
 for (const idx of curSeaArray) {
    hexes[idx].terrain = 'Water';
 }
 console.log("Spreading out sea ...");
 spreadHexes(hexes, indexByCoord, rng, curSeaArray, Math.floor(hexes.length * 0.2), (h: Hex) => h.terrain != 'Water', (h: Hex) => h.terrain = 'Water');

 const numForestSeeds = Math.floor(hexes.length * 0.05);
 function canForest(hex: Hex): boolean {
    return hex.terrain == 'Hills' || hex.terrain == 'Plains' || hex.terrain == 'Savannah';
 }
 let curForestArray = new Array<number>();
 for (let i = 0; i < numForestSeeds; i++) {
    const idx = rng.int(hexes.length);

    if (!canForest(hexes[idx])) {
        // If it's in water, make it a little island, but don't grow it
        // Ditto if it's up in the frozen north
        if (hexes[idx].terrain == 'Water' || hexes[idx].terrain == 'Tundra') {
            hexes[idx].terrain = 'Forest';
        }
        continue;
    }
    curForestArray.push(idx);
    hexes[idx].terrain = 'Forest';
 }

 const numForestTries = Math.floor(hexes.length * 0.20);
 console.log("Spreading out forest ...");
  spreadHexes(hexes, indexByCoord, rng, curForestArray, numForestTries, canForest, (h: Hex) => h.terrain = 'Forest');
 for(const hex of hexes) { if (temperatureMap.get(hex.name) == 'tropical' && hex.terrain == 'Forest') { hex.terrain = 'Jungle'; } }

 console.log("Putting down glaciers ...");
 const numGlacierSeeds = 6 + rng.int(4);
 function canGlacier(hex: Hex): boolean {
    // Can go anywhere, including on water, but can't leave the arctic zone
    return hex.y >= arcticStart && hex.y <= arcticEnd;
 }
 let curGlacierArray = new Array<number>();
 for (let i = 0; i < numGlacierSeeds; i++) {
    let idx = rng.int(hexes.length);
    while (!canGlacier(hexes[idx])) {
        idx = rng.int(hexes.length);
    }
    curGlacierArray.push(idx);
    hexes[idx].terrain = 'Glacier';
 }

spreadHexes(hexes, indexByCoord, rng, curGlacierArray, 6, canGlacier, (h: Hex) => h.terrain = 'Glacier');

 console.log("Putting down swamps ...");
 const numSwampSeeds = 4;
 function canSwamp(hex: Hex): boolean {
    return hex.terrain == 'Jungle';
 }
 let curSwampArray = new Array<number>();
 for (let i = 0; i < numSwampSeeds; i++) {
    let idx = rng.int(hexes.length);
    while (!canSwamp(hexes[idx])) {
        idx = rng.int(hexes.length);
    }
    curSwampArray.push(idx);
    hexes[idx].terrain = 'Swamp';
 }

spreadHexes(hexes, indexByCoord, rng, curSwampArray, 8, canSwamp, (h: Hex) => h.terrain = 'Swamp');

 console.log("Putting down deserts ...");
 const numDesertSeeds = 6 + rng.int(4);
 function canDesert(hex: Hex): boolean {
    // can go in transition zone
    return (hex.terrain == 'Savannah' || hex.terrain == 'Jungle') && hex.y >= temperateStart && hex.y <= tropicalEnd;
 }
 let curDesertArray = new Array<number>();
 for (let i = 0; i < numDesertSeeds; i++) {
    let idx = rng.int(hexes.length);
    while (!canDesert(hexes[idx])) {
        idx = rng.int(hexes.length);
    }
    curDesertArray.push(idx);
    hexes[idx].terrain = 'Desert';
 }

spreadHexes(hexes, indexByCoord, rng, curDesertArray, 40, canDesert, (h: Hex) => h.terrain = 'Desert');

//   if(heightValue>=0.8)hex.terrain='Mountain';
//   else if(tempValue<=0.30){
//    if(moistureValue<=0.4)hex.terrain='Tundra';
//    else if(moistureValue<=0.9)hex.terrain='Forest';
//    else hex.terrain='Glacier';
//   }else if(tempValue<=0.70){
//    if(moistureValue<=0.3)hex.terrain='Hills';
//    else if(moistureValue<=0.6)hex.terrain='Plains';
//    else if(moistureValue<=0.9)hex.terrain='Forest';
//    else hex.terrain='Swamp';
//   }else{
//    if(moistureValue<=0.3)hex.terrain='Desert';
//    else if(moistureValue<=0.6)hex.terrain='Savannah';
//    else if(moistureValue<=0.9)hex.terrain='Jungle';
//    else hex.terrain='Swamp';
//   }
 
 for(const hex of hexes)hex.region=rng.pick(regions).name;
 applyRandomClaims(hexes,rng);
 placeCitiesLikeAllRandom(hexes,rng);
 placePlayersAfterGeneration(hexes,rng);
 return {hexes,hexByName,tokens:[...tokens]};
}

function buildWorld(options:MapOptions){
 return options.generator==='empire'?buildEmpire(options.seed):buildAllRandom(options.seed);
}

const defaultGenerator:MapGeneratorName=process.env['MAP_GENERATOR']==='allRandom'||process.env['MAP_GENERATOR']==='empire'?process.env['MAP_GENERATOR']:'empire';
const defaultSeed=process.env['MAP_SEED']??crypto.randomBytes(8).toString().slice(0, 16);
const world=buildWorld({generator:defaultGenerator,seed:defaultSeed});
const hexes=world.hexes;
const hexByName=world.hexByName;

const encounters:TableauCard[]=[
 {id:'dungeon-raid',title:'Dungeon Raid',location:'B17',difficulty:0,rewards:['Gold'],penalties:['Health'],skillChecks:[{name:'Stealth',target:5},{name:'Athletics',target:4},{name:'Blades',target:6}]},
 {id:'parley',title:'Parley',location:'H8',difficulty:4,rewards:['Gold'],penalties:['Health'],skillChecks:[{name:'Persuasion',target:6},{name:'Deception',target:5}]},
 {id:'wandering-sage',title:'Wandering Sage',location:'M12',difficulty:2,rewards:['Gold'],penalties:['Health'],skillChecks:[{name:'Lore',target:4},{name:'Insight',target:7}]},
];
const encounterById=new Map(encounters.map(encounter=>[encounter.id, encounter] as const));
const tableau=encounters;

const players=new Map<string,PlayerEntity>();
for(const token of playerTokens){
 players.set(token.entityName,{name:token.entityName,tokenId:token.id,curHealth:6+Number(token.id.split('-')[1])-1,maxHealth:10,curLuck:1,maxLuck:3,gold:0,reputation:10,turns:20,location:locationForToken(token.id)});
}
const activeEncounters=new Map<string,string>();

function locationForToken(tokenId:string){return hexes.find(hex=>hex.tokens.includes(tokenId))?.name??'Unknown';}
function moveToken(tokenId:string,to:string){
 const fromHex=hexes.find(hex=>hex.tokens.includes(tokenId));
 if(fromHex)fromHex.tokens=fromHex.tokens.filter(id=>id!==tokenId);
 hexByName.get(to)?.tokens.push(tokenId);
}

function sendJson(res:http.ServerResponse,status:number,data:unknown){
 const body=JSON.stringify(data);
 res.writeHead(status,{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body),'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Access-Control-Allow-Headers':'Content-Type'});
 res.end(body);
}
function ruleViolation(res:http.ServerResponse,message:string){sendJson(res,400,{errorType:'rule violation',message});}
async function readJson(req:http.IncomingMessage){
 let body='';
 for await(const chunk of req)body+=chunk;
 if(!body)return undefined;
 return JSON.parse(body);
}

function activeEncounterFor(card:TableauCard):ActiveEncounter{
 const skillChecks:Record<string,ActiveEncounterSkillCheck[]>= {
  'dungeon-raid':[
   {name:'Stealth',target:5,roll:4,modifier:3,total:7,success:true},
   {name:'Athletics',target:4,roll:1,modifier:2,total:3,success:false},
   {name:'Blades',target:6,roll:6,modifier:0,total:6,success:true},
  ],
  'parley':[
   {name:'Persuasion',target:6,roll:2,modifier:1,total:3,success:false},
   {name:'Deception',target:5,roll:5,modifier:1,total:6,success:true},
  ],
  'wandering-sage':[
   {name:'Lore',target:4,roll:7,modifier:0,total:7,success:true},
   {name:'Insight',target:7,roll:3,modifier:2,total:5,success:false},
  ],
 };
 return {id:card.id,title:card.title,rewards:card.rewards,penalties:card.penalties,skillChecks:skillChecks[card.id]??card.skillChecks.map(check=>({name:check.name,target:check.target,roll:4,modifier:0,total:4,success:false}))};
}

function playerDto(player:PlayerEntity){player.location=locationForToken(player.tokenId); return {...player};}

const server=http.createServer(async(req,res)=>{
 try{
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers','Content-Type');
  if(req.method==='OPTIONS'){res.writeHead(204); res.end(); return;}
  const url=new URL(req.url??'/',`http://${req.headers.host??'localhost'}`);
  const path=decodeURIComponent(url.pathname);
  if(req.method==='GET'&&path==='/api/hexes')return sendJson(res,200,hexes);
  if(req.method==='GET'&&path==='/api/terrain')return sendJson(res,200,terrainSpecs);
  if(req.method==='GET'&&path==='/api/regions')return sendJson(res,200,regions);
  if(req.method==='GET'&&path==='/api/claims')return sendJson(res,200,claims);
  if(req.method==='GET'&&path==='/api/tokens')return sendJson(res,200,tokens);
  if(req.method==='GET'&&path==='/api/tableau')return sendJson(res,200,{encounters:tableau});
  if(req.method==='GET'&&path==='/api/game')return sendJson(res,200,{hexes,terrains:terrainSpecs,regions,claims,tokens});
  const entityMatch=path.match(/^\/api\/entities\/([^/]+)(?:\/actions\/(camp|travel|run_encounter|finish_encounter))?$/);
  if(entityMatch){
   const player=players.get(entityMatch[1]);
   if(!player)return sendJson(res,404,{error:'Entity not found'});
   const action=entityMatch[2];
   if(req.method==='GET'&&!action)return sendJson(res,200,playerDto(player));
   if(req.method==='POST'&&action==='camp'){
    player.curHealth=Math.min(player.maxHealth,player.curHealth+1);
    player.turns=Math.max(0,player.turns-1);
    player.location=locationForToken(player.tokenId);
    return sendJson(res,200,{updates:{curHealth:player.curHealth,turns:player.turns,location:player.location},card:{title:'A Restful Night',lines:['+1 Health','-1 Turn']}});
   }
   if(req.method==='POST'&&action==='travel'){
    const body=await readJson(req);
    const route=Array.isArray(body?.route)?body.route:[];
    if(route.length>4)return ruleViolation(res,'The travel route is too long');
    const current=locationForToken(player.tokenId);
    if(route.length<1||route[0]!==current)return ruleViolation(res,'There are gaps in the route');
    for(let i=0;i<route.length;i++)if(typeof route[i]!=='string'||!hexByName.has(route[i]))return ruleViolation(res,'There are gaps in the route');
    for(let i=1;i<route.length;i++){
     const a=hexByName.get(route[i-1])!,b=hexByName.get(route[i])!;
     if(hexDistance(a,b)!==1)return ruleViolation(res,'There are gaps in the route');
    }
    const destination=route[route.length-1];
    moveToken(player.tokenId,destination);
    player.location=destination;
    player.turns=Math.max(0,player.turns-1);
    return sendJson(res,200,{updates:{location:player.location,turns:player.turns}});
   }
   if(req.method==='POST'&&action==='run_encounter'){
    const body=await readJson(req);
    const encounterId=String(body?.encounterId??'');
    const encounter=encounterById.get(encounterId);
    if(!encounter)return ruleViolation(res,'Encounter not found');
    activeEncounters.set(player.name,encounterId);
    return sendJson(res,200,{encounter:activeEncounterFor(encounter)});
   }
   if(req.method==='POST'&&action==='finish_encounter'){
    const body=await readJson(req);
    const encounterId=String(body?.encounterId??'');
    const activeEncounterId=activeEncounters.get(player.name);
    if(!activeEncounterId||activeEncounterId!==encounterId)return ruleViolation(res,'No active encounter to finish');
    const encounter=encounterById.get(encounterId);
    if(!encounter)return ruleViolation(res,'Encounter not found');
    player.gold+=1;
    player.curHealth=Math.max(0,player.curHealth-1);
    activeEncounters.delete(player.name);
    return sendJson(res,200,{updates:{gold:player.gold,curHealth:player.curHealth},card:{title:'Encounter Results',lines:['Gold +1','Health -1']}});
   }
  }
  sendJson(res,404,{error:'Not found'});
 }catch(error){
  console.error(error);
  sendJson(res,500,{error:'Internal server error'});
 }
});
const port=Number(process.env.PORT)||3001;
server.listen(port,()=>console.log(`Picaro server on ${port}`));
