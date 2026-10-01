from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # API Configuration
    API_BASE_URL: str = "http://localhost:8000"
    APP_NAME: str = "AI Quiz Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # DeepSeek API Configuration
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TEMPERATURE: float = 0.4

    # LLM Configuration
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 2

    # Web Search / Retrieval Configuration
    TAVILY_API_KEY: str = ""
    SEARCH_ENABLED: bool = True
    AGENT_RECURSION_LIMIT: int = 8
    AGENT_TIMEOUT_SECONDS: int = 60
    TAVILY_MAX_RESULTS: int = 6

    # Quiz Configuration
    DEFAULT_QUESTION_COUNT: int = 5
    DEFAULT_DIFFICULTY: str = "mixed"

    # Logging
    LOG_LEVEL: str = "INFO"

    # MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "ai_learn"
    MYSQL_POOL_MIN_SIZE: int = 1
    MYSQL_POOL_MAX_SIZE: int = 10
    MYSQL_CONNECT_TIMEOUT: int = 5

    # WeChat Login Configuration
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_LOGIN_URL: str = "https://api.weixin.qq.com/sns/jscode2session"
    WECHAT_TIMEOUT: int = 10

    # Avatar Upload Configuration
    AVATAR_UPLOAD_DIR: str = "uploads/avatars"
    AVATAR_MAX_SIZE_MB: int = 5

    # JWT Configuration
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
