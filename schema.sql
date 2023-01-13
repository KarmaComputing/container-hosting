-- key_value_store.db
-- yes really
-- Usage:
-- key example: CONTAINER_HOSTING_API_KEY:setting
-- value example: abc
CREATE TABLE key_value_store (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- containers.db
CREATE TABLE container (container TEXT NOT NULL, CONTAINER_HOSTING_API_KEY TEXT, AMBER_SECRET TEXT);
