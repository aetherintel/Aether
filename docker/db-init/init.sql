-- Create keycloak database if it doesn't exist
SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')
\gexec

-- Create aether database if it doesn't exist
SELECT 'CREATE DATABASE aether'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aether')
\gexec
