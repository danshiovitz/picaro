import http from 'node:http';
import { URL } from 'node:url';
const terrains = [['Forest', '#3f8f45', 'forest'], ['Deep Forest', '#14552a', 'deep-forest'], ['Desert', '#d8b45f', 'desert'], ['Water', '#3182bd', 'water'], ['Plains', '#9fca62', 'plains'], ['Mountain', '#8a8178', 'mountain'], ['Hills', '#a68b55', 'hills'], ['Swamp', '#55775a', 'swamp'], ['Tundra', '#cbd5d9', 'tundra'], ['Jungle', '#247a3b', 'jungle'], ['Badlands', '#b86945', 'badlands'], ['Marsh', '#6c9272', 'marsh']].map(([name, color, icon]) => ({ name, color, icon }));
const regionNames = ['Valley of Aardia', 'Domain of the Elves', 'Iron Marches', 'Sunspire Coast', 'Gloaming Fens', 'Kingdom of Roses', 'Storm Peaks', 'Amber Wastes', 'Silverwood', 'Riverlands', 'Crown Basin', 'Ashen Reach', 'Sapphire Isles', 'Old Empire', 'Whispering Downs', 'Dragonmere', 'Golden Steppe', 'Umbral Vale', 'Free Cities'];
const regions = regionNames.map(name => ({ name }));
const claimColors = ['red', 'yellow', 'blue', 'green', 'purple', 'orange'];
const claims = claimColors.map((icon, i) => ({ name: `Faction ${i + 1}`, icon }));
let nextTokenId = 1;
const makeTokenId = () => `token-${nextTokenId++}`;
const tokens = [1, 2, 3, 4].map(i => ({ id: makeTokenId(), entityName: `Player ${i}`, icon: `player${i}` }));
['Waterdeep', 'Underhaven', 'Dawnport', 'Ironford', 'Moonfall', 'Highspire', 'Blackwell', 'Greengate'].forEach(n => tokens.push({ id: makeTokenId(), entityName: `City of ${n}`, icon: 'city' }));
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const hexes = [];
for (let y = 0; y < 20; y++)
    for (let x = 0; x < 20; x++) {
        const n = Math.floor(Math.random() * 4);
        hexes.push({ name: `${String.fromCharCode(65 + y)}${x + 1}`, x, y, q: x - Math.floor(y / 2), r: y, terrain: pick(terrains).name, region: pick(regions).name, claims: [...claims].sort(() => Math.random() - .5).slice(0, n).map(c => c.name), tokens: [] });
    }
const hexByName = new Map(hexes.map(h => [h.name, h]));
const used = new Set();
function place(t, i) { let idx = i ?? Math.floor(Math.random() * hexes.length); while (used.has(idx))
    idx = Math.floor(Math.random() * hexes.length); used.add(idx); hexes[idx].tokens.push(t.id); }
place(tokens[0], 42);
hexes[42].tokens.push(tokens[4].id);
used.add(42);
tokens.slice(1, 4).forEach(t => place(t));
tokens.slice(5).forEach(t => place(t));
function locationForToken(tokenId) { return hexes.find(h => h.tokens.includes(tokenId))?.name ?? 'Unknown'; }
function hexDistance(a, b) { return (Math.abs(a.q - b.q) + Math.abs(a.q + a.r - b.q - b.r) + Math.abs(a.r - b.r)) / 2; }
function moveToken(tokenId, to) {
    const fromHex = hexes.find(h => h.tokens.includes(tokenId));
    if (fromHex)
        fromHex.tokens = fromHex.tokens.filter(id => id !== tokenId);
    hexByName.get(to)?.tokens.push(tokenId);
}
const encounters = [
    { id: 'dungeon-raid', title: 'Dungeon Raid', location: 'B17', difficulty: 0, rewards: ['Gold'], penalties: ['Health'], skillChecks: [{ name: 'Stealth', target: 5 }, { name: 'Athletics', target: 4 }, { name: 'Blades', target: 6 }] },
    { id: 'parley', title: 'Parley', location: 'H8', difficulty: 4, rewards: ['Gold'], penalties: ['Health'], skillChecks: [{ name: 'Persuasion', target: 6 }, { name: 'Deception', target: 5 }] },
    { id: 'wandering-sage', title: 'Wandering Sage', location: 'M12', difficulty: 2, rewards: ['Gold'], penalties: ['Health'], skillChecks: [{ name: 'Lore', target: 4 }, { name: 'Insight', target: 7 }] },
];
const encounterById = new Map(encounters.map(encounter => [encounter.id, encounter]));
const players = new Map();
tokens.filter(t => t.icon.startsWith('player')).forEach((t, i) => players.set(t.entityName, { name: t.entityName, tokenId: t.id, curHealth: 6 + i, maxHealth: 10, curLuck: 1, maxLuck: 3, gold: 0, reputation: 10, turns: 20, location: locationForToken(t.id) }));
const activeEncounters = new Map();
const tableau = encounters;
function playerDto(player) { player.location = locationForToken(player.tokenId); return { ...player }; }
function sendJson(res, status, data) {
    const body = JSON.stringify(data);
    res.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body), 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' });
    res.end(body);
}
function ruleViolation(res, message) { sendJson(res, 400, { errorType: 'rule violation', message }); }
async function readJson(req) {
    let body = '';
    for await (const chunk of req)
        body += chunk;
    if (!body)
        return undefined;
    return JSON.parse(body);
}
function activeEncounterFor(card) {
    const skillChecks = {
        'dungeon-raid': [
            { name: 'Stealth', target: 5, roll: 4, modifier: 3, total: 7, success: true },
            { name: 'Athletics', target: 4, roll: 1, modifier: 2, total: 3, success: false },
            { name: 'Blades', target: 6, roll: 6, modifier: 0, total: 6, success: true },
        ],
        'parley': [
            { name: 'Persuasion', target: 6, roll: 2, modifier: 1, total: 3, success: false },
            { name: 'Deception', target: 5, roll: 5, modifier: 1, total: 6, success: true },
        ],
        'wandering-sage': [
            { name: 'Lore', target: 4, roll: 7, modifier: 0, total: 7, success: true },
            { name: 'Insight', target: 7, roll: 3, modifier: 2, total: 5, success: false },
        ],
    };
    return { id: card.id, title: card.title, rewards: card.rewards, penalties: card.penalties, skillChecks: skillChecks[card.id] ?? card.skillChecks.map(check => ({ name: check.name, target: check.target, roll: 4, modifier: 0, total: 4, success: false })) };
}
const server = http.createServer(async (req, res) => {
    try {
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
        if (req.method === 'OPTIONS') {
            res.writeHead(204);
            res.end();
            return;
        }
        const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`);
        const path = decodeURIComponent(url.pathname);
        if (req.method === 'GET' && path === '/api/hexes')
            return sendJson(res, 200, hexes);
        if (req.method === 'GET' && path === '/api/terrain')
            return sendJson(res, 200, terrains);
        if (req.method === 'GET' && path === '/api/regions')
            return sendJson(res, 200, regions);
        if (req.method === 'GET' && path === '/api/claims')
            return sendJson(res, 200, claims);
        if (req.method === 'GET' && path === '/api/tokens')
            return sendJson(res, 200, tokens);
        if (req.method === 'GET' && path === '/api/tableau')
            return sendJson(res, 200, { encounters: tableau });
        if (req.method === 'GET' && path === '/api/game')
            return sendJson(res, 200, { hexes, terrains, regions, claims, tokens });
        const entityMatch = path.match(/^\/api\/entities\/([^/]+)(?:\/actions\/(camp|travel|run_encounter|finish_encounter))?$/);
        if (entityMatch) {
            const player = players.get(entityMatch[1]);
            if (!player)
                return sendJson(res, 404, { error: 'Entity not found' });
            const action = entityMatch[2];
            if (req.method === 'GET' && !action)
                return sendJson(res, 200, playerDto(player));
            if (req.method === 'POST' && action === 'camp') {
                player.curHealth = Math.min(player.maxHealth, player.curHealth + 1);
                player.turns = Math.max(0, player.turns - 1);
                player.location = locationForToken(player.tokenId);
                return sendJson(res, 200, { updates: { curHealth: player.curHealth, turns: player.turns, location: player.location }, card: { title: 'A Restful Night', lines: ['+1 Health', '-1 Turn'] } });
            }
            if (req.method === 'POST' && action === 'travel') {
                const body = await readJson(req);
                const route = Array.isArray(body?.route) ? body.route : [];
                if (route.length > 4)
                    return ruleViolation(res, 'The travel route is too long');
                const current = locationForToken(player.tokenId);
                if (route.length < 1 || route[0] !== current)
                    return ruleViolation(res, 'There are gaps in the route');
                for (let i = 0; i < route.length; i++)
                    if (typeof route[i] !== 'string' || !hexByName.has(route[i]))
                        return ruleViolation(res, 'There are gaps in the route');
                for (let i = 1; i < route.length; i++) {
                    const a = hexByName.get(route[i - 1]), b = hexByName.get(route[i]);
                    if (hexDistance(a, b) !== 1)
                        return ruleViolation(res, 'There are gaps in the route');
                }
                const destination = route[route.length - 1];
                moveToken(player.tokenId, destination);
                player.location = destination;
                player.turns = Math.max(0, player.turns - 1);
                return sendJson(res, 200, { updates: { location: player.location, turns: player.turns } });
            }
            if (req.method === 'POST' && action === 'run_encounter') {
                const body = await readJson(req);
                const encounterId = String(body?.encounterId ?? '');
                const encounter = encounterById.get(encounterId);
                if (!encounter)
                    return ruleViolation(res, 'Encounter not found');
                activeEncounters.set(player.name, encounterId);
                return sendJson(res, 200, { encounter: activeEncounterFor(encounter) });
            }
            if (req.method === 'POST' && action === 'finish_encounter') {
                const body = await readJson(req);
                const encounterId = String(body?.encounterId ?? '');
                const activeEncounterId = activeEncounters.get(player.name);
                if (!activeEncounterId || activeEncounterId !== encounterId)
                    return ruleViolation(res, 'No active encounter to finish');
                const encounter = encounterById.get(encounterId);
                if (!encounter)
                    return ruleViolation(res, 'Encounter not found');
                player.gold += 1;
                player.curHealth = Math.max(0, player.curHealth - 1);
                activeEncounters.delete(player.name);
                return sendJson(res, 200, { updates: { gold: player.gold, curHealth: player.curHealth }, card: { title: 'Encounter Results', lines: ['Gold +1', 'Health -1'] } });
            }
        }
        sendJson(res, 404, { error: 'Not found' });
    }
    catch (error) {
        console.error(error);
        sendJson(res, 500, { error: 'Internal server error' });
    }
});
const port = Number(process.env.PORT) || 3001;
server.listen(port, () => console.log(`Picaro server on ${port}`));
