-- Runs once on first Postgres container init (docker-entrypoint-initdb.d).
-- POSTGRES_DB already created `maavar`; create the second app DB here.
-- Two databases keep Maavar and Maayan fully isolated on one instance.
CREATE DATABASE maayan;
