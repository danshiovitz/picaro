import { SCHEMAS, type Entity, type EntityOf, type SchemaId } from "./schemas";

type AnyEntity = Entity;

function cloneDefaultValue<T>(value: T): T {
  if (Array.isArray(value))
    return value.map((item) => cloneDefaultValue(item)) as T;
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

export function hydrateEntity<T extends SchemaId>(
  entity: AnyEntity,
): EntityOf<T> {
  const extras = Object.fromEntries(
    Object.entries(entity as Record<string, unknown>).filter(
      ([key]) => key !== "id" && key !== "schemaId" && key !== "data",
    ),
  );
  return createEntity<T>(entity.schemaId as T, entity.id, {
    ...(entity.data as Record<string, unknown>),
    ...extras,
  });
}

export function createEntity<T extends SchemaId>(
  schemaId: T,
  id: string,
  initialData: Record<string, unknown> = {},
): EntityOf<T> {
  const schema = SCHEMAS[schemaId];
  const data: Record<string, unknown> = {};
  for (const [fieldName, field] of Object.entries(schema.fields)) {
    data[fieldName] = cloneDefaultValue(field.defaultValue);
  }
  for (const [fieldName, value] of Object.entries(initialData)) {
    data[fieldName] = value;
  }
  const entity = { id } as EntityOf<T> & Record<string, unknown>;
  Object.defineProperty(entity, "schemaId", {
    value: schemaId,
    enumerable: true,
    writable: false,
    configurable: false,
  });
  Object.defineProperty(entity, "data", {
    value: data,
    enumerable: true,
    writable: false,
    configurable: false,
  });
  for (const [fieldName] of Object.entries(schema.fields)) {
    Object.defineProperty(entity, fieldName, {
      enumerable: true,
      configurable: true,
      get: () => data[fieldName],
      set: (value) => {
        data[fieldName] = value;
      },
    });
  }
  return entity as EntityOf<T>;
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

export function entityEntries(entity: Entity) {
  return Object.entries(entity.data ?? {});
}
