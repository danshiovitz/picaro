export type PrimitiveType = "int" | "string" | "bool";

export type FieldType =
  | PrimitiveType
  | { type: "list"; of: FieldType }
  | { type: "map"; value: FieldType }
  | { type: "ref"; schemaId: string };

export interface SchemaField {
  type: FieldType;
  defaultValue: unknown;
}

export interface EntitySchema {
  id: string;
  name: string;
  extends?: readonly string[];
  fields: Record<string, SchemaField>;
}

export type SchemaCatalog = Record<string, EntitySchema>;
export type SchemaCatalogLike = SchemaCatalog | Map<string, EntitySchema>;

type Mutable<T> = { -readonly [K in keyof T]: T[K] };

type UnionToIntersection<U> = (
  U extends unknown ? (value: U) => void : never
) extends (value: infer I) => void
  ? I
  : never;

type InferFieldValue<T> = T extends "int"
  ? number
  : T extends "string"
    ? string
    : T extends "bool"
      ? boolean
      : T extends { type: "ref"; schemaId: infer S }
        ? S extends SchemaId
          ? EntityOf<S>
          : never
        : T extends { type: "list"; of: infer U }
          ? InferValue<U>[]
          : T extends { type: "map"; value: infer V }
            ? Record<string, InferValue<V>>
            : never;

export type InferValue<T> = T extends FieldType ? InferFieldValue<T> : never;

type InferFieldValues<Fields extends Record<string, SchemaField>> = {
  [K in keyof Fields]: InferValue<Fields[K]["type"]>;
};

type ResolvedSchemaData<
  Catalog extends SchemaCatalog,
  Id extends keyof Catalog & string,
  Seen extends string = never,
> = Id extends Seen
  ? {}
  : Catalog[Id] extends {
        extends?: readonly (infer ParentId extends keyof Catalog & string)[];
        fields: infer Fields extends Record<string, SchemaField>;
      }
    ? UnionToIntersection<
        ParentId extends unknown
          ? ResolvedSchemaData<Catalog, ParentId, Seen | Id>
          : never
      > &
        InferFieldValues<Fields>
    : InferFieldValues<Catalog[Id]["fields"]>;

export const SCHEMAS = {
  token: {
    id: "token",
    name: "Token",
    fields: {
      icon: { type: "string", defaultValue: "" },
      location: { type: "string", defaultValue: "" },
    },
  },
  city: {
    id: "city",
    name: "City",
    extends: ["token"],
    fields: {
      name: { type: "string", defaultValue: "" },
    },
  },
  item: {
    id: "item",
    name: "Item",
    fields: {
      name: { type: "string", defaultValue: "" },
      speed_boost: { type: "int", defaultValue: 0 },
      use_function: { type: "string", defaultValue: "" },
      is_artifact: { type: "bool", defaultValue: false },
    },
  },
  condition: {
    id: "condition",
    name: "Condition",
    extends: ["item"],
    fields: {
      duration: { type: "int", defaultValue: 0 },
    },
  },
  region: {
    id: "region",
    name: "Region",
    fields: {
      name: { type: "string", defaultValue: "" },
      base_difficulty: { type: "int", defaultValue: 0 },
    },
  },
  hex: {
    id: "hex",
    name: "Hex",
    fields: {
      name: { type: "string", defaultValue: "" },
      x: { type: "int", defaultValue: 0 },
      y: { type: "int", defaultValue: 0 },
      q: { type: "int", defaultValue: 0 },
      r: { type: "int", defaultValue: 0 },
      terrain: { type: "string", defaultValue: "" },
      region_id: { type: "string", defaultValue: "" },
      claims: { type: { type: "list", of: "string" }, defaultValue: [] },
    },
  },
  player: {
    id: "player",
    name: "Player",
    extends: ["token"],
    fields: {
      name: { type: "string", defaultValue: "" },
      curHealth: { type: "int", defaultValue: 0 },
      maxHealth: { type: "int", defaultValue: 0 },
      curLuck: { type: "int", defaultValue: 0 },
      maxLuck: { type: "int", defaultValue: 0 },
      speed: { type: "int", defaultValue: 0 },
      gold: { type: "int", defaultValue: 0 },
      reputation: { type: "int", defaultValue: 0 },
      turns: { type: "int", defaultValue: 0 },
      resources: {
        type: { type: "map", value: "int" },
        defaultValue: {},
      },
      inventory: {
        type: { type: "list", of: { type: "ref", schemaId: "item" } },
        defaultValue: [],
      },
      conditions: {
        type: { type: "list", of: { type: "ref", schemaId: "condition" } },
        defaultValue: [],
      },
      skill_xp: {
        type: { type: "map", value: "int" },
        defaultValue: {},
      },
    },
  },
} as const satisfies Record<string, EntitySchema>;

export type SchemaId = keyof typeof SCHEMAS;

export type InferSchema<S extends EntitySchema> = Mutable<
  InferFieldValues<S["fields"]>
>;

export type SchemaRegistry = {
  [K in SchemaId]: Mutable<ResolvedSchemaData<typeof SCHEMAS, K>>;
};

export type EntityOf<S extends SchemaId> = {
  id: string;
  schemaId: S;
  data: SchemaRegistry[S];
} & SchemaRegistry[S];

export type Entity = EntityOf<SchemaId>;

function fieldError(message: string) {
  return new Error(message);
}

function getSchemaFromCatalog(
  catalog: SchemaCatalogLike,
  schemaId: string,
): EntitySchema | undefined {
  return catalog instanceof Map
    ? catalog.get(schemaId)
    : catalog[schemaId as keyof SchemaCatalog];
}

export function resolveSchemaFields<
  Catalog extends SchemaCatalogLike,
  Id extends string,
>(
  catalog: Catalog,
  schemaId: Id,
  visited = new Set<string>(),
): Record<string, SchemaField> {
  if (visited.has(schemaId)) {
    throw fieldError(
      `Circular schema inheritance detected: ${[...visited, schemaId].join(" -> ")}`,
    );
  }
  const schema = getSchemaFromCatalog(catalog, schemaId);
  if (!schema) throw fieldError(`Entity schema not found: ${schemaId}`);

  const nextVisited = new Set(visited);
  nextVisited.add(schemaId);

  const fields: Record<string, SchemaField> = {};
  for (const parentId of schema.extends ?? []) {
    Object.assign(fields, resolveSchemaFields(catalog, parentId, nextVisited));
  }
  Object.assign(fields, schema.fields);
  return fields;
}

export function schemaExtends(
  catalog: SchemaCatalogLike,
  schemaId: string,
  targetSchemaId: string,
  visited = new Set<string>(),
): boolean {
  if (schemaId === targetSchemaId) return true;
  if (visited.has(schemaId)) return false;
  const schema = getSchemaFromCatalog(catalog, schemaId);
  if (!schema) return false;

  const nextVisited = new Set(visited);
  nextVisited.add(schemaId);
  return (schema.extends ?? []).some((parentId) =>
    schemaExtends(catalog, parentId, targetSchemaId, nextVisited),
  );
}

export function resolveSchema<
  Catalog extends SchemaCatalogLike,
  Id extends string,
>(catalog: Catalog, schemaId: Id) {
  const schema = getSchemaFromCatalog(catalog, schemaId);
  if (!schema) throw fieldError(`Entity schema not found: ${schemaId}`);
  return {
    ...schema,
    fields: resolveSchemaFields(catalog, schemaId),
  };
}
