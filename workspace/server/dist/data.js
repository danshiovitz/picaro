export const terrainSpecs = [
    ['Forest', '#1a531e', 'forest'],
    ['Deep Forest', '#14552a', 'deep-forest'],
    ['Desert', '#d8b45f', 'desert'],
    ['Water', '#3182bd', 'water'],
    ['Plains', '#9fca62', 'plains'],
    ['Mountain', '#8a8178', 'mountain'],
    ['Hills', '#a68b55', 'hills'],
    ['Swamp', '#a42d8e', 'swamp'],
    ['Tundra', '#81cbe8', 'tundra'],
    ['Jungle', '#15de4a', 'jungle'],
    ['Badlands', '#b86945', 'badlands'],
    ['Marsh', '#6c9272', 'marsh'],
    ['Glacier', '#e9f6ff', 'glacier'],
    ['Savannah', '#d7ae7f', 'savannah'],
].map(([name, color, icon]) => ({ name, color, icon }));
export const terrainByName = new Map(terrainSpecs.map(terrain => [terrain.name, terrain]));
export const regionNames = ['Valley of Aardia', 'Domain of the Elves', 'Iron Marches', 'Sunspire Coast', 'Gloaming Fens', 'Kingdom of Roses', 'Storm Peaks', 'Amber Wastes', 'Silverwood', 'Riverlands', 'Crown Basin', 'Ashen Reach', 'Sapphire Isles', 'Old Empire', 'Whispering Downs', 'Dragonmere', 'Golden Steppe', 'Umbral Vale', 'Free Cities'];
export let regions = regionNames.map(name => ({ name }));
export const claimColors = ['red', 'yellow', 'blue', 'green', 'purple', 'orange'];
export let claims = claimColors.map((icon, i) => ({ name: `Faction ${i + 1}`, icon }));
let nextTokenId = 1;
export const makeTokenId = () => `token-${nextTokenId++}`;
export let cityTokens = ['Waterdeep', 'Underhaven', 'Dawnport', 'Ironford', 'Moonfall', 'Highspire', 'Blackwell', 'Greengate'].map(n => ({ id: makeTokenId(), entityName: `City of ${n}`, icon: 'city' }));
export function setCityTokens(next) { cityTokens = next; }
