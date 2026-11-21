import { createEntity, hydrateEntity } from "./entity";
import type { Entity, GameData, Hex, Region, Token } from "./types";
import { SCHEMAS, schemaExtends } from "@common/schemas.js";

export class GameStore {
  terrains = new Map<string, GameData["terrains"][number]>();
  claims = new Map<string, GameData["claims"][number]>();
  entities = new Map<string, Entity>();
  hexes = new Map<string, Hex>();
  regions = new Map<string, GameData["regions"][number]>();
  // helper data struct mapping hex name to list of entity ids in that hex:
  hexTokens = new Map<string, string[]>();
  // ids of various entity types
  playerIds: string[] = [];
  tokenIds: string[] = []; // have location and icon

  constructor(public data: GameData) {
    data.terrains.forEach((t) => this.terrains.set(t.name, t));
    data.claims.forEach((c) => this.claims.set(c.name, c));
    for (const entity of data.entities) {
      let hydrated = hydrateEntity(entity);
      if (hydrated.schemaId === "hex") {
        // note hexes is keyed by name, not id
        this.hexes.set(hydrated.name, hydrated as Hex);
      } else if (hydrated.schemaId === "region") {
        this.regions.set(hydrated.id, hydrated as Region);
      } else {
        this.entities.set(hydrated.id, hydrated);
        if (hydrated.schemaId === "player") {
          this.playerIds.push(hydrated.id);
        }
        if (schemaExtends(SCHEMAS, hydrated.schemaId, "token")) {
          this.tokenIds.push(hydrated.id);
        }
      }
    }

    for (const locId of this.tokenIds) {
      const entity = this.entities.get(locId)! as Token;
      if (this.hexes.has(entity.location)) {
        let toks = this.hexTokens.get(entity.location);
        if (toks === undefined) {
          this.hexTokens.set(entity.location, [entity.id]);
        } else {
          toks.push(entity.id);
        }
      }
    }
  }

  entity<T extends Entity = Entity>(id: string) {
    return this.entities.get(id) as T | undefined;
  }

  tokensForHex(name: string) {
    const ids = this.hexTokens.get(name) || [];
    return ids
      .map((id) => this.entities.get(id))
      .filter((e): e is NonNullable<typeof e> => Boolean(e));
  }

  moveToken(id: string, fromHex: string, toHex: string) {
    const entity = this.entities.get(id) as Token;
    if (!entity) {
      console.error("Can't find token to move:", id);
    }
    entity.location = toHex;
    const fromTokens = this.hexTokens.get(fromHex);
    if (fromTokens) {
      if (fromTokens.length == 1) {
        this.hexTokens.delete(fromHex);
      }
      {
        this.hexTokens.set(
          fromHex,
          fromTokens.filter((cid) => cid !== id),
        );
      }
    }

    const toTokens = this.hexTokens.get(toHex);
    if (toTokens) {
      if (toTokens.findIndex((i) => i === id) === -1) {
        toTokens.push(id);
      }
    } else {
      this.hexTokens.set(toHex, [id]);
    }
  }

  fullHex(name: string) {
    const h = this.hexes.get(name);
    return (
      h && {
        ...h,
        terrainObj: this.terrains.get(h.terrain),
        regionObj: this.regions.get(h.region_id),
        claimObjs: h.claims.map((c) => this.claims.get(c)),
        tokenObjs: (this.hexTokens.get(name) || [])
          .map((i) => this.entities.get(i))
          .filter((t): t is NonNullable<typeof t> => Boolean(t)),
      }
    );
  }
}
