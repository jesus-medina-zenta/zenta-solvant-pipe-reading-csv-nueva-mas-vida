"""
Configuración de la aplicación usando Pydantic para validación.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class AppConfig(BaseSettings):
    """Configuración principal de la aplicación."""

    # Configuración general
    app_name: str = Field(default="zenta-template-pipe-python", description="Nombre de la aplicación")
    log_level: str = Field(default="INFO", description="Nivel de logging")
    environment: str = Field(default="dev", description="Entorno de ejecución")

    # Configuración de procesamiento
    batch_size: int = Field(default=1000, description="Tamaño del lote para procesamiento")
    max_retries: int = Field(default=3, description="Número máximo de reintentos")
    retry_delay: int = Field(default=5, description="Delay entre reintentos en segundos")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # Ignora variables de entorno adicionales
    }


class CloudStorageConfig(BaseSettings):
    """Configuración para Google Cloud Storage."""
    
    project_id: str = Field(default="", description="ID del proyecto de Google Cloud")
    bucket_name: str = Field(default="", description="Nombre del bucket")
    
    model_config = {
        "env_prefix": "GCS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

class FirestoreConfig(BaseSettings):
    project_id: str
    collection: str
    database: str
    logs_collection: str
    batch_collection: str

    model_config = {
        "env_prefix": "FIRESTORE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

class BackendConfig(BaseSettings):
    service_url: str = Field(description="URL del servicio backend")
    payload_agent: Optional[str] = Field(default=None, description="ID del agente para payload por defecto")
    payload_callname: Optional[str] = Field(default=None, description="Nombre de la llamada para payload por defecto")
    payload_agent_phone_number_id: Optional[str] = Field(default=None, description="ID del número de teléfono del agente para payload por defecto")

    model_config = {
        "env_prefix": "BACKEND_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

def get_config() -> AppConfig:
    """
    Obtiene la configuración de la aplicación.
    Útil para testing y para evitar errores en importación.
    """
    return AppConfig()


def get_cloud_storage_config() -> CloudStorageConfig:
    """
    Obtiene la configuración de Google Cloud Storage.
    """
    return CloudStorageConfig()

def get_firestore_config() -> FirestoreConfig:
    return FirestoreConfig()
# Instancia global de configuración (solo se crea cuando se necesita)
config: Optional[AppConfig] = None

def get_backend_config() -> BackendConfig:
    return BackendConfig()

def init_config() -> AppConfig:
    """
    Inicializa la configuración global.
    """
    global config
    if config is None:
        config = AppConfig()
    return config
