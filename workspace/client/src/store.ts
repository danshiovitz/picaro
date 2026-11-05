import { createEntity, hydrateEntity } from "./entity";
import type { Entity, GameData, Hex, Token } from "./types";

export class GameStore {
  entities = new Map<string, Entity>();
  hexes = new Map<string, Hex>();
  tokens = new Map<string, Token>();
  tokenHex = new Map<string, Hex>();
  terrains = new Map<string, GameData["terrains"][number]>();
  regions = new Map<string, GameData["regions"][number]>();
  claims = new Map<string, GameData["claims"][number]>();

  constructor(public data: GameData) {
    const entities = data.entities ?? [
      ...data.hexes,
      ...data.regions,
      ...data.tokens,
    ];
    for (const entity of entities)
      this.entities.set(entity.id, hydrateEntity(entity));

    for (const h of data.hexes) {
      const hydrated = createEntity("hex", h.name, h);
      this.hexes.set(hydrated.name, hydrated);
      hydrated.tokens.forEach((t) => this.tokenHex.set(t, hydrated));
    }
    for (const t of data.tokens)
      this.tokens.set(t.id, createEntity("city", t.id, t));
    data.terrains.forEach((t) => this.terrains.set(t.name, t));
    for (const r of data.regions)
      this.regions.set(r.id, createEntity("region", r.id, r));
    data.claims.forEach((c) => this.claims.set(c.name, c));
  }

  entity<T extends Entity = Entity>(id: string) {
    return this.entities.get(id) as T | undefined;
  }

  entitiesBySchema<T extends Entity = Entity>(schemaId: T["schemaId"]) {
    return [...this.entities.values()].filter(
      (entity): entity is T => entity.schemaId === schemaId,
    );
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
        regionObj: this.regions.get(h.region_id),
        claimObjs: h.claims.map((c) => this.claims.get(c)),
        tokenObjs: h.tokens.map((t) => this.tokens.get(t)),
      }
    );
  }
}
