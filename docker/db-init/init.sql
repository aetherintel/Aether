-- Create keycloak database if it doesn't exist
SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')
\gexec

-- Create monitor database if it doesn't exist
SELECT 'CREATE DATABASE monitor'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'monitor')
\gexec
