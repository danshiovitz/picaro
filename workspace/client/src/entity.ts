import {
  SCHEMAS,
  resolveSchemaFields,
  type Entity,
  type EntityOf,
  type SchemaId,
} from "./schemas";

type AnyEntity = Record<string, unknown> & {
  id: string;
  schemaId: string;
  data?: Record<string, unknown>;
};

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

export function hydrateEntity<T extends AnyEntity>(entity: T): T {
  const extras = Object.fromEntries(
    Object.entries(entity as Record<string, unknown>).filter(
      ([key]) => key !== "id" && key !== "schemaId" && key !== "data",
    ),
  );
  return createEntity(entity.schemaId as SchemaId, entity.id, {
    ...(entity.data as Record<string, unknown>),
    ...extras,
  }) as unknown as T;
}

export function createEntity<T extends SchemaId>(
  schemaId: T,
  id: string,
  initialData: Record<string, unknown> = {},
): EntityOf<T> {
  const fields = resolveSchemaFields(SCHEMAS, schemaId);
  const data: Record<string, unknown> = {};
  for (const [fieldName, field] of Object.entries(fields)) {
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
  for (const [fieldName] of Object.entries(fields)) {
    Object.defineProperty(entity, fieldName, {
      enumerable: true,
      configurable: true,
      get: () => data[fieldName],
      set: (value) => {
        data[fieldName] = value;
      },
    });
  }
  for (const fieldName of Object.keys(initialData)) {
    if (fieldName in fields) continue;
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

export function getField<
  T extends Record<string, unknown>,
  K extends keyof T & string,
>(entity: T, fieldName: K): T[K] {
  return entity[fieldName];
}

export function setField<
  T extends Record<string, unknown>,
  K extends keyof T & string,
>(entity: T, fieldName: K, value: T[K]) {
  (entity as Record<string, unknown>)[fieldName] = value;
}

export function entityEntries(
  entity: Record<string, unknown> & { data?: Record<string, unknown> },
) {
  return Object.entries(entity.data ?? {});
}
