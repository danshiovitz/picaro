import type { GameData, Hex, Token } from "./types";
export class GameStore {
  hexes = new Map<string, Hex>();
  tokens = new Map<string, Token>();
  tokenHex = new Map<string, Hex>();
  terrains = new Map();
  regions = new Map();
  claims = new Map();
  constructor(public data: GameData) {
    data.hexes.forEach((h) => {
      this.hexes.set(h.name, h);
      h.tokens.forEach((t) => this.tokenHex.set(t, h));
    });
    data.tokens.forEach((t) => this.tokens.set(t.id, t));
    data.terrains.forEach((t) => this.terrains.set(t.name, t));
    data.regions.forEach((r) => this.regions.set(r.name, r));
    data.claims.forEach((c) => this.claims.set(c.name, c));
  }
  distance(a: Hex, b: Hex) {
    return (
      (Math.abs(a.q - b.q) +
        Math.abs(a.q + a.r - b.q - b.r) +
        Math.abs(a.r - b.r)) /
      2
    );
  }
  hexForToken(id: string) {
    return this.tokenHex.get(id);
  }
  tokensInHex(name: string) {
    return (this.hexes.get(name)?.tokens ?? []).map((id) =>
      this.tokens.get(id),
    );
  }
  fullHex(name: string) {
    const h = this.hexes.get(name);
    return (
      h && {
        ...h,
        terrainObj: this.terrains.get(h.terrain),
        regionObj: this.regions.get(h.region),
        claimObjs: h.claims.map((c) => this.claims.get(c)),
        tokenObjs: h.tokens.map((t) => this.tokens.get(t)),
      }
    );
  }
}
