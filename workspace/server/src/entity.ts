import { randomUUID } from "node:crypto";

import { Entity, EntitySchema, FieldType, SchemaId } from "./schemas.js";

const schemaRegistry = new Map<string, EntitySchema>();
const resolvedSchemaCache = new Map<string, EntitySchema>();

function cloneDefaultValue<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => cloneDefaultValue(item)) as T;
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        cloneDefaultValue(item),
      ]),
    ) as T;
  }
  return value;
}

function resolvedSchema(schemaId: string): EntitySchema {
  const cached = resolvedSchemaCache.get(schemaId);
  if (cached) return cached;
  const schema = schemaRegistry.get(schemaId);
  if (!schema) throw new Error(`Entity schema not found: ${schemaId}`);
  const inheritedFields: Record<string, EntitySchema["fields"][string]> = {};
  for (const parentId of schema.extends ?? []) {
    const parent = resolvedSchema(parentId);
    Object.assign(inheritedFields, parent.fields);
  }
  const resolved: EntitySchema = {
    ...schema,
    fields: { ...inheritedFields, ...schema.fields },
  };
  resolvedSchemaCache.set(schemaId, resolved);
  return resolved;
}

function schemaExtends(schemaId: string, targetSchemaId: string): boolean {
  if (schemaId === targetSchemaId) return true;
  const schema = schemaRegistry.get(schemaId);
  if (!schema) return false;
  return (schema.extends ?? []).some((parentId) =>
    schemaExtends(parentId, targetSchemaId),
  );
}

function fieldError(fieldName: string, message: string) {
  return new Error(`Invalid field ${fieldName}: ${message}`);
}

function validateFieldValue(
  fieldName: string,
  fieldType: FieldType,
  value: unknown,
) {
  if (fieldType === "int") {
    if (typeof value !== "number" || !Number.isInteger(value)) {
      throw fieldError(fieldName, "expected int");
    }
    return;
  }
  if (fieldType === "string") {
    if (typeof value !== "string")
      throw fieldError(fieldName, "expected string");
    return;
  }
  if (fieldType === "bool") {
    if (typeof value !== "boolean")
      throw fieldError(fieldName, "expected bool");
    return;
  }
  if ("type" in fieldType && fieldType.type === "list") {
    if (!Array.isArray(value)) throw fieldError(fieldName, "expected list");
    value.forEach((item, index) =>
      validateFieldValue(`${fieldName}[${index}]`, fieldType.of, item),
    );
    return;
  }
  if ("type" in fieldType && fieldType.type === "map") {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw fieldError(fieldName, "expected map");
    }
    for (const [key, item] of Object.entries(
      value as Record<string, unknown>,
    )) {
      validateFieldValue(`${fieldName}.${key}`, fieldType.value, item);
    }
    return;
  }
  if ("type" in fieldType && fieldType.type === "ref") {
    if (!value || typeof value !== "object") {
      throw fieldError(fieldName, `expected ref to ${fieldType.schemaId}`);
    }
    const entity = value as Entity;
    if (typeof entity.id !== "string" || typeof entity.schemaId !== "string") {
      throw fieldError(fieldName, `expected ref to ${fieldType.schemaId}`);
    }
    if (!schemaExtends(entity.schemaId, fieldType.schemaId)) {
      throw fieldError(fieldName, `expected ref to ${fieldType.schemaId}`);
    }
  }
}

function validateEntityData(
  schema: EntitySchema,
  data: Record<string, unknown>,
) {
  for (const [fieldName, field] of Object.entries(schema.fields)) {
    validateFieldValue(fieldName, field.type, data[fieldName]);
  }
}

export function registerEntitySchema(schema: EntitySchema) {
  schemaRegistry.set(schema.id, schema);
  resolvedSchemaCache.delete(schema.id);
}

export function createEntity<T extends Entity = Entity>(
  schemaId: SchemaId | string,
  id: string = randomUUID(),
  initialData: Record<string, unknown> = {},
): T {
  const schema = resolvedSchema(schemaId);
  const data: Record<string, unknown> = {};
  for (const [fieldName, field] of Object.entries(schema.fields)) {
    data[fieldName] = cloneDefaultValue(field.defaultValue);
  }
  for (const [fieldName, value] of Object.entries(initialData)) {
    data[fieldName] = value;
  }
  validateEntityData(schema, data);

  const entity = { id } as Entity & Record<string, unknown>;
  Object.defineProperty(entity, "schemaId", {
    value: schemaId,
    enumerable: false,
    writable: false,
    configurable: false,
  });
  Object.defineProperty(entity, "data", {
    value: data,
    enumerable: false,
    writable: false,
    configurable: false,
  });
  Object.defineProperty(entity, "get", {
    enumerable: false,
    configurable: false,
    value: (fieldName: string) => data[fieldName],
  });
  Object.defineProperty(entity, "set", {
    enumerable: false,
    configurable: false,
    value: (fieldName: string, value: unknown) => {
      const field = schema.fields[fieldName];
      if (!field) throw fieldError(fieldName, "unknown field");
      validateFieldValue(fieldName, field.type, value);
      data[fieldName] = value;
    },
  });

  for (const [fieldName, field] of Object.entries(schema.fields)) {
    Object.defineProperty(entity, fieldName, {
      enumerable: true,
      configurable: true,
      get: () => data[fieldName],
      set: (value) => {
        validateFieldValue(fieldName, field.type, value);
        data[fieldName] = value;
      },
    });
  }

  return entity as T;
}

export function getField<T extends Entity, K extends keyof T & string>(
  entity: T,
  fieldName: K,
): T[K] {
  return entity[fieldName];
}

export function setField<T extends Entity, K extends keyof T & string>(
  entity: T,
  fieldName: K,
  value: T[K],
) {
  (entity as Record<string, unknown>)[fieldName] = value;
}

export function hydrateEntity<T extends Entity = Entity>(entity: Entity): T {
  return createEntity<T>(entity.schemaId, entity.id, entity.data);
}

export function serializeEntity(entity: Entity): Entity {
  return {
    ...entity,
    id: entity.id,
    schemaId: entity.schemaId,
    data: cloneDefaultValue(entity.data),
  } as Entity;
}

export class EntityStore {
  private readonly entities = new Map<string, Entity>();

  add(entity: Entity) {
    this.entities.set(entity.id, entity);
    return entity;
  }

  getById<T extends Entity = Entity>(id: string) {
    return this.entities.get(id) as T | undefined;
  }

  get<T extends Entity = Entity>(id: string) {
    return this.getById<T>(id);
  }

  has(id: string) {
    return this.entities.has(id);
  }

  delete(id: string) {
    return this.entities.delete(id);
  }

  values<T extends Entity = Entity>() {
    return Array.from(this.entities.values()) as T[];
  }

  getBySchema<T extends Entity = Entity>(schemaId: string) {
    return this.values<T>().filter((entity) =>
      schemaExtends(entity.schemaId, schemaId),
    );
  }

  replaceSchema<T extends Entity = Entity>(schemaId: string, next: T[]) {
    for (const [id, entity] of this.entities) {
      if (schemaExtends(entity.schemaId, schemaId)) this.entities.delete(id);
    }
    for (const entity of next) this.add(entity);
  }
}
