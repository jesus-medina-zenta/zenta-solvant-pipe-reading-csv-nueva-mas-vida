from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from src.enums.status import StatusType

class LogRecord(BaseModel):
    id: str = Field(..., description="ID único del proceso")
    fecha_inicio: datetime = Field(..., description="Fecha y hora de inicio")
    fecha_fin: datetime = Field(..., description="Fecha y hora de finalización")
    duracion_segundos: int = Field(..., description="Duración en segundos")
    status: StatusType = StatusType.PENDIENTE
    registros_extraidos: int = Field(..., description="Número de registros extraídos")
    registros_transformados: int = Field(0, description="Registros transformados (0 para extracción)")
    registros_cargados: int = Field(0, description="Registros cargados (0 para extracción)")
    errores: List[str] = Field(default_factory=list, description="Lista de errores")
    archivo_sftp: str = Field(..., description="Archivo SFTP procesado")
    csv_generado: Optional[str] = Field(None, description="URL de GCS del CSV generado") 
    pipeline_type: str = Field("EXTRACTION", description="Tipo de pipeline")