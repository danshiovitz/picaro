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
    const hydratedHexes = data.hexes.map((hex) =>
      createEntity("hex", hex.name, hex),
    );
    const hydratedTokens = data.tokens.map((token) =>
      createEntity("city", token.id, token),
    );
    const hydratedRegions = data.regions.map((region) =>
      createEntity("region", region.id, region),
    );

    this.data.hexes = hydratedHexes;
    this.data.tokens = hydratedTokens;
    this.data.regions = hydratedRegions;

    const entities = data.entities ?? [
      ...hydratedHexes,
      ...hydratedRegions,
      ...hydratedTokens,
    ];
    for (const entity of entities)
      this.entities.set(entity.id, hydrateEntity(entity));

    for (const h of hydratedHexes) {
      this.hexes.set(h.name, h);
      h.tokens.forEach((t) => this.tokenHex.set(t, h));
      this.entities.set(h.id, h);
    }
    for (const t of hydratedTokens) {
      this.tokens.set(t.id, t);
      this.entities.set(t.id, t);
    }
    for (const r of hydratedRegions) {
      this.regions.set(r.id, r);
      this.entities.set(r.id, r);
    }
    data.terrains.forEach((t) => this.terrains.set(t.name, t));
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
