"""
Modelo para registros de batch (colección backend).
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, validator
import re

class BatchRecord(BaseModel):
    """
    Modelo para registros de batch de archivos subidos por el backend.
    """
    id_carga: str = Field(..., description="UUID del archivo")
    call_name: str = Field(..., description="Nombre del batch")
    agent_id: str = Field(..., description="ID del agente")
    agent_phone_number_id: str = Field(..., description="ID del teléfono")
    file_name: str = Field(..., description="Nombre del archivo")
    file_path: str = Field(..., description="Ruta del archivo en GCS")
    file_type: str = Field(..., description="Tipo de archivo (csv, xlsx)")
    file_size: int = Field(..., description="Tamaño del archivo en bytes")
    status: str = Field(..., description="Estado del registro")
    created_at: datetime = Field(..., description="Fecha de creación")
    updated_at: datetime = Field(..., description="Fecha de última actualización")
    
    # Campos adicionales para el procesamiento
    fecha_inicio: Optional[datetime] = Field(None, description="Inicio del procesamiento")
    fecha_fin: Optional[datetime] = Field(None, description="Fin del procesamiento")
    registros_extraidos: Optional[int] = Field(0, description="Registros extraídos")
    registros_transformados: Optional[int] = Field(0, description="Registros transformados")
    registros_cargados: Optional[int] = Field(0, description="Registros cargados")
    errores: Optional[list] = Field(default_factory=list, description="Lista de errores")
    pipeline_type: Optional[str] = Field(None, description="Tipo de pipeline")
    duracion_segundos: Optional[float] = Field(None, description="Duración en segundos")
    
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,  # Para manejar DatetimeWithNanoseconds
        json_schema_extra={
            "example": {
                "id_carga": "265c9384-2d85-4170-bbf3-9d1894dfa0c7",
                "call_name": "prueba4",
                "agent_id": "sdasd4s4",
                "phone_idagent_phone_number_id": "asd4454",
                "file_name": "prueba4_2025-09-28T23-27-33-132Z_265c9384-2d85-4170-bbf3-9d1894dfa0c7.csv",
                "file_path": "gs://zenta-solvant-csv-dev/batch-calling/prueba4_2025-09-28T23-27-33-132Z_265c9384-2d85-4170-bbf3-9d1894dfa0c7.csv",
                "file_type": "csv",
                "file_size": 323,
                "status": "pendiente",
                "created_at": "2025-09-28T23:27:33.604000Z",
                "updated_at": "2025-09-28T23:27:33.604000Z"
            }
        }
    )
    
    @property
    def id(self) -> str:
        """Retorna el UUID como ID para compatibilidad."""
        return self.id_carga
    
    @property
    def csv_generado(self) -> str:
        """Retorna la ruta del archivo para compatibilidad con LogRecord."""
        return self.file_path
    
    def is_valid(self) -> bool:
        """Verifica si el registro es válido para procesamiento."""
        return (
            self.id_carga and 
            self.file_path and 
            self.file_path.startswith('gs://') and
            self.status == "pendiente"
        )
    
    @classmethod
    def from_firestore_dict(cls, data: dict) -> "BatchRecord":
        """
        Crea una instancia desde un diccionario de Firestore.
        
        Args:
            data: Diccionario con datos de Firestore
            
        Returns:
            BatchRecord: Instancia del modelo
        """
        # Convertir DatetimeWithNanoseconds a datetime si es necesario
        if 'created_at' in data and hasattr(data['created_at'], 'replace'):
            data['created_at'] = data['created_at'].replace(tzinfo=data['created_at'].tzinfo)
        
        if 'updated_at' in data and hasattr(data['updated_at'], 'replace'):
            data['updated_at'] = data['updated_at'].replace(tzinfo=data['updated_at'].tzinfo)
        
        return cls(**data)
    
class BatchCallingRecord(BaseModel):
    """
    Modelo para registros de batch calling manual con estructura específica.
    """
    # Campos del CSV de batch calling
    phone_number: str = Field(..., description="Número de teléfono")
    agent_name: str = Field(..., description="Nombre del agente")
    name: str = Field(..., description="Nombre del cliente")
    due_date: str = Field(..., description="Fecha de vencimiento")
    days_overdue: int = Field(..., description="Días vencidos")
    monthly_payment: int = Field(..., description="Pago mensual")
    down_payment_option1: int = Field(..., description="Opción de pago inicial")
    paternal_surname: str = Field(..., description="Apellido paterno")
    rut: str = Field(..., description="RUT sin dígito verificador")
    dv: str = Field(..., description="Dígito verificador")
    mail: str = Field(..., description="Email")
    
    # Campos adicionales para compatibilidad con DataRecord
    id_carga: str = Field(..., description="ID de carga desde registro_archivos")
    fecha_carga: datetime = Field(..., description="Fecha de procesamiento")
    
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "phone_number": "+56937752692",
                "agent_name": "Javier",
                "name": "Nicolás",
                "due_date": "15-09-2025",
                "days_overdue": 1,
                "monthly_payment": 800000,
                "down_payment_option1": 8000,
                "paternal_surname": "Gomez",
                "rut": "19333839",
                "dv": "9",
                "mail": "nicolas.fernandez@zentagroup.com",
                "id_carga": "c10ed9e3-e666-4d41-a75b-e351c080332b",
                "fecha_carga": "2025-09-29T16:25:14.178000Z"
            }
        }
    )
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Valida formato de número de teléfono."""
        if not v.startswith('+56'):
            raise ValueError('El número debe comenzar con +56')
        # Remover espacios y validar que tenga el formato correcto
        clean_number = v.replace(' ', '')
        if not re.match(r'^\+56\d{9}$', clean_number):
            raise ValueError('Formato de teléfono inválido. Debe ser +56XXXXXXXXX')
        return clean_number
    
    @validator('mail')
    def validate_email(cls, v):
        """Valida formato básico de email."""
        if v and '@' not in v:
            raise ValueError('Formato de email inválido')
        return v
    
    @validator('rut')
    def validate_rut(cls, v):
        """Valida que el RUT sea numérico."""
        if not v.isdigit():
            raise ValueError('RUT debe contener solo números')
        return v
    
    @validator('dv')
    def validate_dv(cls, v):
        """Valida dígito verificador."""
        if v not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'K', 'k']:
            raise ValueError('Dígito verificador inválido')
        return v.upper()
    
    def get_full_rut(self) -> str:
        """Retorna RUT completo con dígito verificador."""
        return f"{self.rut}-{self.dv}"
    
    def is_valid(self) -> bool:
        """Verifica si el registro es válido."""
        return (
            bool(self.phone_number) and
            bool(self.name) and
            bool(self.rut) and
            bool(self.dv) and
            self.days_overdue >= 0 and
            self.monthly_payment > 0
        )
    
    @classmethod
    def from_csv_row(cls, row: dict, id_carga: str, fecha_carga: datetime) -> "BatchCallingRecord":
        """
        Crea una instancia desde una fila del CSV de batch calling.
        
        Args:
            row: Diccionario con datos de la fila del CSV
            id_carga: ID de carga desde registro_archivos
            fecha_carga: Fecha de procesamiento
            
        Returns:
            BatchCallingRecord: Instancia del modelo
        """
        return cls(
            phone_number=str(row.get('phone_number', '')).strip(),
            agent_name=str(row.get('agent_name', '')).strip(),
            name=str(row.get('name', '')).strip(),
            due_date=str(row.get('due_date', '')).strip(),
            days_overdue=int(row.get('days_overdue', 0)),
            monthly_payment=int(row.get('monthly_payment', 0)),
            down_payment_option1=int(row.get('down_payment_option1', 0)),
            paternal_surname=str(row.get('paternal_surname', '')).strip(),
            rut=str(row.get('rut', '')).strip(),
            dv=str(row.get('dv', '')).strip(),
            mail=str(row.get('mail', '')).strip(),
            id_carga=id_carga,
            fecha_carga=fecha_carga
        )
    
    def to_firestore_dict(self) -> dict:
        """
        Convierte el registro a diccionario para Firestore (registros_sftp).
        """
        return {
            "phone_number": self.phone_number,
            "agent_name": self.agent_name,
            "client_name": self.name,  # Mapear a client_name para consistencia
            "client_surname": self.paternal_surname,
            "full_name": f"{self.name} {self.paternal_surname}",
            "rut_completo": self.get_full_rut(),
            "rut": self.rut,
            "dv": self.dv,
            "email": self.mail,
            "due_date": self.due_date,
            "days_overdue": self.days_overdue,
            "monthly_payment": self.monthly_payment,
            "down_payment_option1": self.down_payment_option1,
            "id_carga": self.id_carga,
            "fecha_carga": self.fecha_carga.isoformat(),
            "tipo_flujo": "batch_calling",  # Identificar el origen
            "processed_at": datetime.now().isoformat()
        }