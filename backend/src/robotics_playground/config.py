from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    rerun_grpc_port: int = 9876
    rerun_web_port: int = 9090


settings = Settings()
