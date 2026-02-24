# Solution

## Key decisions / tradeoffs

**Schemaless data model (nosql)** Since EDIFACT formats evolve; a schemaless store adapts as message formats evolve. **Tradeoff**: no schema enforcement, so we use TypedDicts and type hints to document expected shapes. This also means if we need transactions in the future, it might make things complicated.

**MongoDB over a stream-based system** For convenience MongoDB fits well in a single-service setup. If multiple services needed to consume this (e.g. streaming aggregates), a log-based approach  with tail reads could be better, so every service can move at their own pace and be crash recoverable.

**Bitemporality and versioning** `valid_from` / `valid_to` plus version numbers address reprocessing: when a file is re-ingested, old versions are superseded (stamped with `valid_to`) and a new version is inserted, preserving an audit trail and enabling rollbacks to a point in time we know is consistent.

**Nested document structure** `parsed_edifact` stores one document per file with nested messages. Since the raw content doesn't evolve this means we are storing it redundantly.

---

## Scaling

**Parser** Today the full file is loaded into memory. A streaming parser (read until segment terminator `'`) would reduce memory use for large files, at the cost of more developer time (complexity).

**Connection pooling** MongoClient uses pooling; `maxPoolSize` and `minPoolSize` are configurable via settings/env.

**Horizontal scaling** Since we are using NoSQL this makes sharding easier. A gateway (e.g. nginx) can load-balance across multiple app instances. RAID or similar can improve **write** throughput and availability. Partitioning by timestamp can help as the load increases.


**Async I/O** For heavy write workloads, async DB writes would avoid blocking the server when there are particularly large files.
