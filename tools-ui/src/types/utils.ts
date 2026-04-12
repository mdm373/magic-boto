/** Key–value map frozen at the type level (`Readonly<Record<…>>`). */
export type ReadonlyRecord<K extends PropertyKey, V> = Readonly<Record<K, V>>;
