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
  apiJson(`/api/entities/${encodeURIComponent(PLAYER_NAME)}`, void 0, 20)
]).then(([d, player]) => render(new GameStore(d), player)).catch((err) => {
  console.error(err);
  app.innerHTML = `<main style="padding:24px"><h2>Unable to load game data</h2><p>${err instanceof Error ? err.message : String(err)}</p><p>Check that the API server is running on port 3001.</p></main>`;
});
function esc(value) {
  return String(value).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);
}
function render(store, player) {
  app.innerHTML = `<div class="layout"><main><div class="bar"><button id="minus">-</button><span id="z"></span><button id="plus">+</button></div><div class="map-shell"><div id="map"></div><section class="map-side"><section class="character-summary"><h2>Character</h2><div id="character-stats"></div></section><section class="action-section"><button id="travel" class="action-button" type="button"><img src="/images/actions/boots.svg" alt=""/><span>Travel</span></button><button id="camp" class="action-button" type="button"><img src="/images/actions/campfire.svg" alt=""/><span>Camp</span></button><button id="attack" class="action-button" type="button"><img src="/images/actions/swords.svg" alt=""/><span>Attack</span></button></section><section class="play-section"><div id="play-content"></div></section></section></div></main><aside><h2>Picaro</h2><p>Bogus right-panel intelligence reports, rumors, inventories, and diplomacy notes.</p></aside><footer><b>Log</b><p>Bogus bottom panel: marching orders, dice results, chat, and event feed will appear here.</p></footer></div><div id="tip"></div>`;
  const map = document.querySelector("#map");
  const tip = document.querySelector("#tip");
  const stats = document.querySelector("#character-stats");
  const playContent = document.querySelector("#play-content");
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
    stats.innerHTML = `<dl><div><dt>Name</dt><dd>${esc(player.name)}</dd></div><div><dt>Health</dt><dd>${player.curHealth}/${player.maxHealth}</dd></div><div><dt>Luck</dt><dd>${player.curLuck}/${player.maxLuck}</dd></div><div><dt>Reputation</dt><dd>${player.reputation}</dd></div><div><dt>Turns</dt><dd>${player.turns}</dd></div><div><dt>Location</dt><dd>${esc(player.location)}</dd></div></dl>`;
  }
  function showPlayCard(card) {
    setPlay(`<article class="play-card"><h3>${esc(card.title)}</h3><div class="play-card-body">${card.lines.map((line) => `<p>${esc(line)}</p>`).join("")}</div></article><button id="card-ok" class="card-ok" type="button">OK</button>`);
    document.querySelector("#card-ok").addEventListener("click", clearPlay);
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
  function enterTravelMode() {
    if (busy || playContent.innerHTML.trim().length > 0) return;
    route = [player.location];
    map.classList.add("travel-mode");
    tip.style.display = "none";
    showTravelCard();
    draw();
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
      g.onclick = (e) => {
        e.stopPropagation();
        route ? selectRouteHex(hex) : showTip(hex, cx * zoom - map.scrollLeft + 20, cy * zoom - map.scrollTop + 20);
      };
      let timer;
      g.onmouseenter = () => timer = setTimeout(() => {
        if (!route) showTip(hex, cx * zoom - map.scrollLeft + 20, cy * zoom - map.scrollTop + 20);
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
  function showTip(hex, x, y) {
    const f = store.fullHex(hex.name);
    tip.style.display = "block";
    tip.style.left = x + "px";
    tip.style.top = y + "px";
    tip.innerHTML = `<button id="close">\xD7</button><h3>${f.name}</h3><p><b>Terrain:</b> ${f.terrain}</p><p><b>Region:</b> ${f.region}</p><p><b>Claims:</b> ${f.claims.join(", ") || "None"}</p><p><b>Tokens:</b> ${f.tokenObjs.map((t) => t.entityName).join(", ") || "None"}</p><a id="move-here" href="#">Move here</a>`;
    document.querySelector("#close").addEventListener("click", () => tip.style.display = "none");
    document.querySelector("#move-here").addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      enterTravelMode();
      if (route) selectRouteHex(hex);
    });
  }
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#tip")) tip.style.display = "none";
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
      if (result.card) showPlayCard(result.card);
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
