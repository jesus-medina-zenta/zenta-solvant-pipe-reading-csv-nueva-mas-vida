from enum import Enum


class PipelineType(str, Enum):
    EXTRACTION = "EXTRACTION"
    TRANSFORMATION = "TRANSFORMATION"

class StatusType(str, Enum):
    PENDIENTE = "PENDIENTE"
    PROCESANDO = "PROCESANDO"
    PARSEADO = "PARSEADO"
    COMPLETADO = "COMPLETADO"
    ERROR = "ERROR"