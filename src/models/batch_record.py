"""
Modelo para registros de batch (colección backend).
"""
from datetime import datetime
from typing import Optional
import uuid
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
    #  CAMPOS REALES del CSV de batch calling
    phone_number: str = Field(..., description="Número de teléfono")
    name: str = Field(..., description="Nombre del cliente")
    overdue_date1: str = Field(..., description="Fecha de vencimiento")
    overdue_amount1: float = Field(..., description="Monto vencido")
    down_payment_option1: float = Field(..., description="Opción de pago inicial")
    paternal_surname: str = Field(..., description="Apellido paterno")
    rut: str = Field(..., description="RUT completo (con guión y DV)")
    email: str = Field(..., description="Email del cliente")
    
    # Campos adicionales para compatibilidad con DataRecord
    id_carga: str = Field(..., description="ID de carga desde registro_archivos")
    fecha_carga: datetime = Field(..., description="Fecha de procesamiento")

    # TRACK PARA CONTROL INTERNO
    track_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único para tracking interno")
    track_status: str = Field(default="queued_call", description="Estado del tracking interno")

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "phone_number": "+56937752692",
                "name": "Nicolás",
                "overdue_date1": "15-09-2025",
                "overdue_amount1": 800000.0,
                "down_payment_option1": 8000.0,
                "paternal_surname": "Gomez",
                "rut": "19333839-9",
                "email": "nicolas.fernandez@zentagroup.com",
                "id_carga": "c10ed9e3-e666-4d41-a75b-e351c080332b",
                "fecha_carga": "2025-09-29T16:25:14.178000Z"
            }
        }
    )
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Valida formato de número de teléfono."""
        if not v:
            raise ValueError('Número de teléfono requerido')
        
        # Limpiar el número
        clean_number = str(v).strip().replace(' ', '').replace('-', '')
        
        # Si no tiene +56, agregarlo si es un número chileno válido
        if not clean_number.startswith('+56'):
            if clean_number.startswith('56') and len(clean_number) == 11:
                clean_number = '+' + clean_number
            elif len(clean_number) == 9:
                clean_number = '+56' + clean_number
            else:
                raise ValueError('Formato de teléfono inválido')
        
        # Validar formato final
        if not re.match(r'^\+56\d{9}$', clean_number):
            raise ValueError('Formato de teléfono inválido. Debe ser +56XXXXXXXXX')
        
        return clean_number
    
    @validator('email')
    def validate_email(cls, v):
        """Valida formato básico de email."""
        if v and '@' not in v:
            raise ValueError('Formato de email inválido')
        return str(v).strip() if v else ""
    
    @validator('rut')
    def validate_rut(cls, v):
        """Valida formato de RUT chileno completo."""
        if not v:
            raise ValueError('RUT requerido')
        
        # Limpiar RUT
        clean_rut = str(v).strip().upper().replace('.', '')
        
        # Validar formato básico
        if '-' not in clean_rut:
            raise ValueError('RUT debe incluir guión y dígito verificador (ej: 12345678-9)')
        
        rut_parts = clean_rut.split('-')
        if len(rut_parts) != 2:
            raise ValueError('Formato de RUT inválido')
        
        rut_number, dv = rut_parts
        
        # Validar que la parte numérica sea válida
        if not rut_number.isdigit() or len(rut_number) < 7:
            raise ValueError('Parte numérica del RUT inválida')
        
        # Validar dígito verificador
        if dv not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'K']:
            raise ValueError('Dígito verificador inválido')
        
        return clean_rut
    
    @validator('overdue_amount1', 'down_payment_option1')
    def validate_amounts(cls, v):
        """Valida que los montos sean números positivos."""
        try:
            amount = float(v) if v else 0.0
            if amount < 0:
                raise ValueError('Los montos no pueden ser negativos')
            return amount
        except (ValueError, TypeError):
            raise ValueError('Monto debe ser un número válido')
    
    @validator('name', 'paternal_surname')
    def validate_names(cls, v):
        """Valida que los nombres no estén vacíos."""
        if not v or not str(v).strip():
            raise ValueError('Nombre y apellido son requeridos')
        return str(v).strip()
    
    def get_rut_parts(self) -> tuple[str, str]:
        """
        Retorna las partes del RUT por separado.
        
        Returns:
            tuple: (rut_sin_dv, dv)
        """
        if '-' in self.rut:
            parts = self.rut.split('-')
            return parts[0], parts[1]
        return self.rut, ""
    
    def get_full_name(self) -> str:
        """Retorna el nombre completo."""
        return f"{self.name} {self.paternal_surname}".strip()
    
    def is_valid(self) -> bool:
        """Verifica si el registro es válido."""
        return (
            bool(self.phone_number) and
            bool(self.name) and
            bool(self.paternal_surname) and
            bool(self.rut) and
            self.overdue_amount1 >= 0 and
            self.down_payment_option1 >= 0
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
            name=str(row.get('name', '')).strip(),
            overdue_date1=str(row.get('overdue_date1', '')).strip(),
            overdue_amount1=float(row.get('overdue_amount1', 0)) if row.get('overdue_amount1') else 0.0,
            down_payment_option1=float(row.get('down_payment_option1', 0)) if row.get('down_payment_option1') else 0.0,
            paternal_surname=str(row.get('paternal_surname', '')).strip(),
            rut=str(row.get('rut', '')).strip(),
            email=str(row.get('email', '')).strip(),
            id_carga=id_carga,
            fecha_carga=fecha_carga
        )
    
    def to_firestore_dict(self) -> dict:
        """
        Convierte el registro a diccionario para Firestore (registros_sftp).
        """
        rut_sin_dv, dv = self.get_rut_parts()
        
        return {
            "phone_number": self.phone_number,
            "client_name": self.name,
            "client_surname": self.paternal_surname,
            "full_name": self.get_full_name(),
            "rut_completo": self.rut,
            "rut": rut_sin_dv,
            "dv": dv,
            "email": self.email,
            "overdue_date": self.overdue_date1,  # Mapear a campo estándar
            "overdue_amount": self.overdue_amount1,
            "down_payment_option": self.down_payment_option1,
            "id_carga": self.id_carga,
            "fecha_carga": self.fecha_carga.isoformat(),
            "tipo_flujo": "batch_calling",  # Identificar el origen
            "processed_at": datetime.now().isoformat(),
            "track_id": self.track_id,
            "track_status": self.track_status
        }