-- Run as the owner on a dedicated CASS database after schema/seed setup.
-- Assign a strong password separately; never use the owner role in the app.
CREATE ROLE cass_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
DO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO cass_reader', current_database()); END $$;
GRANT USAGE ON SCHEMA public TO cass_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO cass_reader;
ALTER ROLE cass_reader SET default_transaction_read_only = on;
ALTER ROLE cass_reader SET statement_timeout = '10s';
