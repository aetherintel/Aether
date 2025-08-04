from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    KEYCLOAK_URL: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str
    SWAGGER_TOKEN_URL: str
    KEYCLOAK_BASE_URL: str
    KEYCLOAK_ADMIN_CLIENT_ID: str
    KEYCLOAK_ADMIN_CLIENT_SECRET: str
    
    # Auth0 settings
    AUTH0_DOMAIN: str
    AUTH0_CLIENT_ID: str
    AUTH0_CLIENT_SECRET: str
    AUTH0_AUDIENCE: str
    AUTH0_MANAGEMENT_CLIENT_ID: str
    AUTH0_MANAGEMENT_CLIENT_SECRET: str
    AUTH0_BASE_URL: str

    class Config:
        env_file = None  # Let Docker or the OS set env vars


settings = Settings()
