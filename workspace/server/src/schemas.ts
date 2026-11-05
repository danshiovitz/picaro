export type FieldType =
  | "int"
  | "string"
  | "bool"
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

export const SCHEMAS = {
  city: {
    id: "city",
    name: "City",
    fields: {
      entityName: { type: "string", defaultValue: "" },
      icon: { type: "string", defaultValue: "city" },
    },
  },
  item: {
    id: "item",
    name: "Item",
    fields: {
      name: { type: "string", defaultValue: "" },
    },
  },
  condition: {
    id: "condition",
    name: "Condition",
    fields: {
      name: { type: "string", defaultValue: "" },
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
      tokens: { type: { type: "list", of: "string" }, defaultValue: [] },
    },
  },
  player: {
    id: "player",
    name: "Player",
    fields: {
      name: { type: "string", defaultValue: "" },
      tokenId: { type: "string", defaultValue: "" },
      curHealth: { type: "int", defaultValue: 0 },
      maxHealth: { type: "int", defaultValue: 0 },
      curLuck: { type: "int", defaultValue: 0 },
      maxLuck: { type: "int", defaultValue: 0 },
      speed: { type: "int", defaultValue: 0 },
      gold: { type: "int", defaultValue: 0 },
      reputation: { type: "int", defaultValue: 0 },
      turns: { type: "int", defaultValue: 0 },
      location: { type: "string", defaultValue: "" },
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

type InferLeaf<T> = T extends "int"
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

export type InferValue<T> = T extends FieldType ? InferLeaf<T> : never;

type Mutable<T> = { -readonly [K in keyof T]: T[K] };

export type InferSchema<S extends EntitySchema> = {
  -readonly [K in keyof S["fields"]]: InferValue<S["fields"][K]["type"]>;
};

export type SchemaRegistry = {
  [K in SchemaId]: Mutable<InferSchema<(typeof SCHEMAS)[K]>>;
};

export type EntityOf<S extends SchemaId> = {
  id: string;
  schemaId: S;
  data: SchemaRegistry[S];
} & SchemaRegistry[S];

export type Entity = EntityOf<SchemaId>;
