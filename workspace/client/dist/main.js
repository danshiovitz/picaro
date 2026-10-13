// src/store.ts
var GameStore = class {
  constructor(data) {
    this.data = data;
    this.hexes = /* @__PURE__ */ new Map();
    this.tokens = /* @__PURE__ */ new Map();
    this.tokenHex = /* @__PURE__ */ new Map();
    this.terrains = /* @__PURE__ */ new Map();
    this.regions = /* @__PURE__ */ new Map();
    this.claims = /* @__PURE__ */ new Map();
    data.hexes.forEach((h) => {
      this.hexes.set(h.name, h);
      h.tokens.forEach((t) => this.tokenHex.set(t, h));
    });
    data.tokens.forEach((t) => this.tokens.set(t.id, t));
    data.terrains.forEach((t) => this.terrains.set(t.name, t));
    data.regions.forEach((r) => this.regions.set(r.name, r));
    data.claims.forEach((c) => this.claims.set(c.name, c));
  }
  distance(a, b) {
    return (Math.abs(a.q - b.q) + Math.abs(a.q + a.r - b.q - b.r) + Math.abs(a.r - b.r)) / 2;
  }
  hexForToken(id) {
    return this.tokenHex.get(id);
  }
  tokensInHex(name) {
    return (this.hexes.get(name)?.tokens ?? []).map((id) => this.tokens.get(id));
  }
  fullHex(name) {
    const h = this.hexes.get(name);
    return h && { ...h, terrainObj: this.terrains.get(h.terrain), regionObj: this.regions.get(h.region), claimObjs: h.claims.map((c) => this.claims.get(c)), tokenObjs: h.tokens.map((t) => this.tokens.get(t)) };
  }
};

// src/main.ts
var API = "";
var PLAYER_NAME = "Player 1";
var app = document.querySelector("#app");
async function apiJson(path, init, attempts = 1) {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    try {
      const r = await fetch(`${API}${path}`, init);
      if (!r.ok) {
        let message = `API request failed: ${r.status}`;
        try {
          const body = await r.json();
          message = body?.message ?? body?.error ?? message;
        } catch {
        }
        throw new Error(message);
      }
      return r.json();
    } catch (err) {
      lastError = err;
      if (i < attempts - 1) await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw lastError;
}
Promise.all([
  apiJson("/api/game", void 0, 20),
  apiJson(`/api/entities/${encodeURIComponent(PLAYER_NAME)}`, void 0, 20),
  apiJson("/api/tableau", void 0, 20)
]).then(([d, player, tableau]) => render(new GameStore(d), player, tableau)).catch((err) => {
  console.error(err);
  app.innerHTML = `<main style="padding:24px"><h2>Unable to load game data</h2><p>${err instanceof Error ? err.message : String(err)}</p><p>Check that the API server is running on port 3001.</p></main>`;
});
function esc(value) {
  return String(value).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);
}
function outcomeLine(rewards, penalties) {
  const parts = [...rewards.map((item) => `+${item}`), ...penalties.map((item) => `-${item}`)];
  return `Outcome: ${parts.join(", ")}`;
}
function skillLine(check) {
  return `${check.name} vs ${check.target}`;
}
function renderEncounterCard(card) {
  const circles = Array.from({ length: 5 }, (_, i) => `<span class="encounter-pip ${i < card.difficulty ? "filled" : ""}" aria-hidden="true"></span>`).join("");
  return `<article class="play-card encounter-card tableau-encounter" data-encounter-id="${esc(card.id)}">
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
   <p>${esc(outcomeLine(card.rewards, card.penalties))}</p>
   <div class="encounter-spacer"></div>
   ${card.skillChecks.map((check) => `<p class="encounter-check">${esc(skillLine(check))}</p>`).join("")}
  </div>
 </article>`;
}
function renderActiveEncounterCard(card) {
  return `<article class="play-card encounter-card active-encounter-card" data-encounter-id="${esc(card.id)}">
  <div class="encounter-header">
   <div class="encounter-title-row">
    <span class="encounter-title">${esc(card.title)}</span>
   </div>
  </div>
  <div class="play-card-body encounter-body">
   <p>${esc(outcomeLine(card.rewards, card.penalties))}</p>
   <div class="encounter-spacer"></div>
   ${card.skillChecks.map((check) => `<p class="encounter-check">${esc(`${check.name} vs ${check.target}`)}</p><p class="encounter-result">${esc(`1d10 (${check.roll}) + ${check.modifier} = ${check.total} .. ${check.success ? "Success! \u2705" : "Failure! \u2620\uFE0F"}`)}</p>`).join("")}
  </div>
 </article>`;
}
function render(store, player, tableau) {
  const encounterById = new Map(tableau.encounters.map((encounter) => [encounter.id, encounter]));
  const encounterByLocation = new Map(tableau.encounters.map((encounter) => [encounter.location, encounter]));
  app.innerHTML = `<div class="layout"><main><section class="top-strip"><div class="bar"><button id="minus">-</button><span id="z"></span><button id="plus">+</button></div></section><div class="map-shell"><div class="map-pane"><div id="map-scroll"><div id="map"></div><section class="tableau">${tableau.encounters.map(renderEncounterCard).join("")}</section></div></div><section class="map-side"><section class="character-summary"><h2>Character</h2><div id="character-stats"></div></section><section class="action-section"><button id="travel" class="action-button" type="button"><img src="/images/actions/boots.svg" alt=""/><span>Travel</span></button><button id="camp" class="action-button" type="button"><img src="/images/actions/campfire.svg" alt=""/><span>Camp</span></button><button id="attack" class="action-button" type="button"><img src="/images/actions/swords.svg" alt=""/><span>Attack</span></button></section><section class="play-section"><div id="play-content"></div></section></section></div></main><aside><h2>Picaro</h2><p>Bogus right-panel intelligence reports, rumors, inventories, and diplomacy notes.</p></aside><footer><b>Log</b><p>Bogus bottom panel: marching orders, dice results, chat, and event feed will appear here.</p></footer></div><div id="tip"></div>`;
  const map = document.querySelector("#map");
  const tip = document.querySelector("#tip");
  const stats = document.querySelector("#character-stats");
  const playContent = document.querySelector("#play-content");
  const tableauEl = document.querySelector(".tableau");
  const actionButtons = [...document.querySelectorAll(".action-button")];
  let zoom = 0.72;
  const size = 44;
  const w = Math.sqrt(3) * size, h = 2 * size;
  const svgNS = "http://www.w3.org/2000/svg";
  let route = null;
  let busy = false;
  function updateActionButtons() {
    const hasPlay = playContent.innerHTML.trim().length > 0;
    actionButtons.forEach((button) => button.disabled = busy || hasPlay);
  }
  function setPlay(html) {
    playContent.innerHTML = html;
    updateActionButtons();
  }
  function clearPlay() {
    playContent.innerHTML = "";
    updateActionButtons();
  }
  function hexCenter(hex) {
    return { x: Math.sqrt(3) * size * (hex.q + hex.r / 2) + 70, y: size * 1.5 * hex.r + 60 };
  }
  function isAdjacent(a, b) {
    return store.distance(a, b) === 1;
  }
  function renderSummary() {
    stats.innerHTML = `<dl><div><dt>Name</dt><dd>${esc(player.name)}</dd></div><div><dt>Health</dt><dd>${player.curHealth}/${player.maxHealth}</dd></div><div><dt>Luck</dt><dd>${player.curLuck}/${player.maxLuck}</dd></div><div><dt>Gold</dt><dd>${player.gold}</dd></div><div><dt>Reputation</dt><dd>${player.reputation}</dd></div><div><dt>Turns</dt><dd>${player.turns}</dd></div><div><dt>Location</dt><dd>${esc(player.location)}</dd></div></dl>`;
  }
  function showGenericCard(card, buttonText = "OK", onClick = clearPlay) {
    setPlay(`<article class="play-card"><h3>${esc(card.title)}</h3><div class="play-card-body">${card.lines.map((line) => `<p>${esc(line)}</p>`).join("")}</div></article><button id="card-ok" class="card-ok" type="button">${esc(buttonText)}</button>`);
    document.querySelector("#card-ok").addEventListener("click", onClick);
  }
  function showEncounterPreview(card) {
    setPlay(`${renderEncounterCard(card)}<div class="encounter-controls"><button id="encounter-ok" class="card-ok" type="button">OK</button><button id="encounter-cancel" class="card-ok" type="button">Cancel</button></div>`);
    document.querySelector("#encounter-cancel").addEventListener("click", clearPlay);
    document.querySelector("#encounter-ok").addEventListener("click", () => void runEncounter(card.id));
  }
  function showActiveEncounter(card) {
    setPlay(`${renderActiveEncounterCard(card)}<div class="encounter-controls"><button id="encounter-finish" class="card-ok" type="button">OK</button></div>`);
    document.querySelector("#encounter-finish").addEventListener("click", () => void finishEncounter(card.id));
  }
  function showEncounterError(message) {
    showGenericCard({ title: "Encounter Error", lines: [message] }, "OK", clearPlay);
  }
  function showEncounterResults(card) {
    showGenericCard(card, "OK", clearPlay);
  }
  async function runEncounter(encounterId) {
    busy = true;
    updateActionButtons();
    try {
      const result = await apiJson(`/api/entities/${encodeURIComponent(player.name)}/actions/run_encounter`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ encounterId }) });
      showActiveEncounter(result.encounter);
    } catch (err) {
      console.error(err);
      showEncounterError(err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
      updateActionButtons();
    }
  }
  async function finishEncounter(encounterId) {
    busy = true;
    updateActionButtons();
    try {
      const result = await apiJson(`/api/entities/${encodeURIComponent(player.name)}/actions/finish_encounter`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ encounterId }) });
      Object.assign(player, result.updates);
      renderSummary();
      showEncounterResults(result.card);
    } catch (err) {
      console.error(err);
      showEncounterError(err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
      updateActionButtons();
    }
  }
  function enterTravelMode() {
    if (busy || playContent.innerHTML.trim().length > 0) return;
    route = [player.location];
    map.classList.add("travel-mode");
    tip.style.display = "none";
    showTravelCard();
    draw();
  }
  function showTravelCard() {
    setPlay(`<article class="play-card travel-card"><h3>Travel</h3><div class="play-card-body route-body"><p>${esc(route.join(" - "))}</p></div></article><div class="travel-controls"><button id="travel-go" class="card-ok" type="button">Go</button><button id="travel-cancel" class="card-ok" type="button">Cancel</button></div>`);
    document.querySelector("#travel-cancel").addEventListener("click", exitTravelMode);
    document.querySelector("#travel-go").addEventListener("click", goTravel);
  }
  function showTravelError(message) {
    setPlay(`<article class="play-card error-card"><h3>Travel Error</h3><div class="play-card-body route-body"><p>${esc(message)}</p></div></article><button id="card-ok" class="card-ok" type="button">OK</button>`);
    document.querySelector("#card-ok").addEventListener("click", clearPlay);
  }
  function exitTravelMode() {
    route = null;
    map.classList.remove("travel-mode");
    clearPlay();
    draw();
  }
  function shortestPath(fromName, toName) {
    const start = store.hexes.get(fromName), target = store.hexes.get(toName);
    if (!start || !target) return [fromName];
    const queue = [start];
    const cameFrom = /* @__PURE__ */ new Map([[start.name, null]]);
    const dirs = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
    for (let qi = 0; qi < queue.length; qi++) {
      const current = queue[qi];
      if (current.name === target.name) break;
      for (const [dq, dr] of dirs) {
        const next = store.data.hexes.find((h2) => h2.q === current.q + dq && h2.r === current.r + dr);
        if (next && !cameFrom.has(next.name)) {
          cameFrom.set(next.name, current.name);
          queue.push(next);
        }
      }
    }
    if (!cameFrom.has(target.name)) return [fromName];
    const path = [];
    for (let name = target.name; name; name = cameFrom.get(name) ?? null) path.push(name);
    return path.reverse();
  }
  function selectRouteHex(hex) {
    if (!route) return;
    const existing = route.indexOf(hex.name);
    if (existing >= 0) route = route.slice(0, existing + 1);
    else {
      const last = store.hexes.get(route[route.length - 1]);
      if (isAdjacent(last, hex)) route.push(hex.name);
      else route.push(...shortestPath(last.name, hex.name).slice(1));
    }
    showTravelCard();
    draw();
  }
  async function goTravel() {
    if (!route) return;
    const submittedRoute = [...route];
    route = null;
    map.classList.remove("travel-mode");
    busy = true;
    updateActionButtons();
    draw();
    try {
      const result = await apiJson(`/api/entities/${encodeURIComponent(player.name)}/actions/travel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ route: submittedRoute }) });
      const oldLocation = player.location;
      Object.assign(player, result.updates);
      if (result.updates.location && result.updates.location !== oldLocation) moveLocalPlayerToken(oldLocation, result.updates.location);
      renderSummary();
      clearPlay();
      draw();
    } catch (err) {
      console.error(err);
      showTravelError(err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
      updateActionButtons();
    }
  }
  function moveLocalPlayerToken(from, to) {
    const fromHex = store.hexes.get(from), toHex = store.hexes.get(to);
    if (!fromHex || !toHex) return;
    fromHex.tokens = fromHex.tokens.filter((id) => id !== player.tokenId);
    if (!toHex.tokens.includes(player.tokenId)) toHex.tokens.push(player.tokenId);
    store.tokenHex.set(player.tokenId, toHex);
  }
  function draw() {
    document.querySelector("#z").textContent = `${Math.round(zoom * 100)}%`;
    map.innerHTML = "";
    const svg = document.createElementNS(svgNS, "svg");
    svg.style.width = `${(20 * w + w) * zoom}px`;
    svg.style.height = `${(20 * size * 1.5 + h) * zoom}px`;
    svg.setAttribute("viewBox", `-50 -50 ${20 * w + w + 100} ${20 * size * 1.5 + h + 100}`);
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
      const pts = [0, 1, 2, 3, 4, 5].map((i) => {
        const a = Math.PI / 180 * (60 * i - 30);
        return `${cx + size * Math.cos(a)},${cy + size * Math.sin(a)}`;
      }).join(" ");
      g.innerHTML = `<polygon points="${pts}" fill="${terr.color}" stroke="#222"/><polygon points="${pts}" fill="url(#p-${terr.icon})" opacity=".35" stroke="#222"/>`;
      if (zoom > 0.45) g.innerHTML += `<text x="${cx}" y="${cy - 24}" text-anchor="middle" class="name">${hex.name}</text>`;
      const toks = hex.tokens.map((id) => store.tokens.get(id));
      toks.forEach((t, i) => {
        const separate = zoom > 0.38;
        g.innerHTML += `<image href="/images/tokens/${t.icon}.svg" x="${cx - 18 + (separate ? (i - (toks.length - 1) / 2) * 24 : 0)}" y="${cy - 18}" width="36" height="36"/>`;
      });
      if (zoom > 0.55) hex.claims.forEach((c, i) => {
        const cl = store.claims.get(c);
        g.innerHTML += `<image href="/images/claims/${cl.icon}.svg" x="${cx - 24 + i * 16}" y="${cy + 22}" width="14" height="14"/>`;
      });
      if (encounterByLocation.has(hex.name)) g.innerHTML += `<text x="${cx}" y="${cy + 10}" text-anchor="middle" class="encounter-star" aria-hidden="true">\u2605</text>`;
      g.onclick = (e) => {
        e.stopPropagation();
        route ? selectRouteHex(hex) : showTip(hex, g.getBoundingClientRect());
      };
      let timer;
      g.onmouseenter = () => timer = setTimeout(() => {
        if (!route) showTip(hex, g.getBoundingClientRect());
      }, 700);
      g.onmouseleave = () => clearTimeout(timer);
      svg.append(g);
    }
    if (route && route.length > 1) {
      const overlay = document.createElementNS(svgNS, "g");
      overlay.classList.add("route-overlay");
      for (let i = 1; i < route.length; i++) {
        const a = store.hexes.get(route[i - 1]), b = store.hexes.get(route[i]);
        const ac = hexCenter(a), bc = hexCenter(b);
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
  }
  function formatClaims(claims) {
    const counts = /* @__PURE__ */ new Map();
    for (const claim of claims) counts.set(claim, (counts.get(claim) ?? 0) + 1);
    return [...counts.entries()].map(([name, count]) => count > 1 ? `${name} (x${count})` : name).join(", ");
  }
  function formatTokens(tokens) {
    return tokens.map((token) => token.entityName).join(", ");
  }
  function showTip(hex, anchor) {
    const f = store.fullHex(hex.name);
    const claimsText = formatClaims(f.claimObjs.filter((claim) => Boolean(claim)).map((claim) => claim.name));
    const tokenText = formatTokens(f.tokenObjs.filter((token) => Boolean(token)));
    const encounter = encounterByLocation.get(hex.name);
    const lines = [["Terrain", esc(f.terrain)], ["Region", esc(f.region)]];
    if (claimsText) lines.push(["Claims", esc(claimsText)]);
    if (tokenText) lines.push(["Tokens", esc(tokenText)]);
    if (encounter) lines.push(["Encounter", `<a class="encounter-link" href="#" data-encounter-id="${esc(encounter.id)}">${esc(encounter.title)}</a>`]);
    const details = lines.map(([label, value]) => `<p><b>${label}:</b> ${value}</p>`).join("");
    tip.style.display = "block";
    tip.style.visibility = "hidden";
    tip.style.left = "0px";
    tip.style.top = "0px";
    tip.innerHTML = `<button id="close">\xD7</button><h3>${f.name}</h3>${details}<a id="move-here" href="#">Move here</a>`;
    const bounds = tip.getBoundingClientRect();
    const gap = 12;
    let x = anchor.right + gap;
    let y = anchor.top;
    if (x + bounds.width > window.innerWidth) x = anchor.left - bounds.width - gap;
    if (y + bounds.height > window.innerHeight) y = window.innerHeight - bounds.height - gap;
    x = Math.max(gap, x);
    y = Math.max(gap, y);
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
    tip.style.visibility = "visible";
    document.querySelector("#close").addEventListener("click", () => tip.style.display = "none");
    document.querySelector("#move-here").addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      enterTravelMode();
      if (route) selectRouteHex(hex);
    });
    document.querySelector(".encounter-link")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const encounterId = e.currentTarget.dataset.encounterId;
      const encounter2 = encounterId ? encounterById.get(encounterId) : void 0;
      if (encounter2) showEncounterPreview(encounter2);
    });
  }
  tableauEl.addEventListener("click", (e) => {
    const card = e.target.closest(".tableau-encounter");
    if (!card) return;
    const encounterId = card.dataset.encounterId;
    const encounter = encounterId ? encounterById.get(encounterId) : void 0;
    if (encounter) showEncounterPreview(encounter);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#tip")) tip.style.display = "none";
  });
  map.addEventListener("scroll", () => {
    tip.style.display = "none";
  });
  map.onwheel = (e) => {
    e.preventDefault();
    zoom = Math.max(0.22, Math.min(1.6, zoom + (e.deltaY < 0 ? 0.08 : -0.08)));
    draw();
  };
  document.querySelector("#plus").addEventListener("click", () => {
    zoom = Math.min(1.6, zoom + 0.1);
    draw();
  });
  document.querySelector("#minus").addEventListener("click", () => {
    zoom = Math.max(0.22, zoom - 0.1);
    draw();
  });
  document.querySelector("#travel").addEventListener("click", enterTravelMode);
  document.querySelector("#camp").addEventListener("click", async () => {
    busy = true;
    updateActionButtons();
    try {
      const result = await apiJson(`/api/entities/${encodeURIComponent(player.name)}/actions/camp`, { method: "POST" });
      Object.assign(player, result.updates);
      renderSummary();
      if (result.card) showGenericCard(result.card);
    } catch (err) {
      console.error(err);
      setPlay(`<p class="action-error">${esc(err instanceof Error ? err.message : String(err))}</p>`);
    } finally {
      busy = false;
      updateActionButtons();
    }
  });
  renderSummary();
  updateActionButtons();
  draw();
}
//# sourceMappingURL=/main.js.map
