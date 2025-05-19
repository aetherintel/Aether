from pydantic import BaseSettings


class Settings(BaseSettings):
    KEYCLOAK_URL: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str
    SWAGGER_TOKEN_URL: str
    KEYCLOAK_BASE_URL: str
    KEYCLOAK_ADMIN_CLIENT_ID: str
    KEYCLOAK_ADMIN_CLIENT_SECRET: str

    class Config:
        env_file = None  # Let Docker or the OS set env vars


settings = Settings()
