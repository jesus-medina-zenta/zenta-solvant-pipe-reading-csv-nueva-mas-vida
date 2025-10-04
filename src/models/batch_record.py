"""
Modelo para registros de batch (colección backend).
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, validator
import re

from src.utils.date_id import DateIdUtils

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
    # Campos del CSV de batch calling (tal como vienen en el CSV)
    phone_number: str = Field(..., description="Número de teléfono (sin prefijo +56)")
    name: str = Field(..., description="Nombre del cliente")
    overdue_date1: str = Field(..., description="Fecha de vencimiento en formato GMT")
    overdue_amount1: int = Field(..., description="Monto vencido")
    down_payment_option1: int = Field(..., description="Opción de pago inicial")
    paternal_surname: str = Field(..., description="Apellido paterno")
    rut: str = Field(..., description="RUT completo con dígito verificador")
    email: str = Field(..., description="Email del cliente")
    
    # Campos adicionales para compatibilidad con DataRecord
    id_carga: str = Field(..., description="ID de carga desde registro_archivos")
    fecha_carga: datetime = Field(..., description="Fecha de procesamiento")
    
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "phone_number": "937752692",
                "name": "Nicolás",
                "overdue_date1": "Wed Oct 15 2025 00:00:00 GMT+0000 (Coordinated Universal Time)",
                "overdue_amount1": 800000,
                "down_payment_option1": 8000,
                "paternal_surname": "Gomez",
                "rut": "193338399",
                "email": "nicolas.fernandez@zentagroup.com",
                "id_carga": "c10ed9e3-e666-4d41-a75b-e351c080332b",
                "fecha_carga": "2025-09-29T16:25:14.178000Z"
            }
        }
    )
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Valida formato de número de teléfono."""
        # Limpiar el número (remover espacios)
        clean_number = str(v).strip().replace(' ', '').replace('-', '')
        # Validar que sea numérico y tenga 9 dígitos
        if not clean_number.isdigit() or len(clean_number) != 9:
            raise ValueError(f'Formato de teléfono inválido: {v}. Debe tener 9 dígitos')
        return clean_number
    
    @validator('email', pre=True)
    def validate_email(cls, v):
        """Valida y limpia el email."""
        v_str = str(v).strip()
        # Manejar casos especiales de emails malformados
        if v_str in ['[object Object]', 'NaN', 'null', 'undefined', '']:
            return ""
        # Validación básica de email
        if v_str and '@' not in v_str:
            return ""  # Email inválido, devolver vacío
        return v_str
    
    @validator('rut')
    def validate_rut(cls, v):
        """Valida que el RUT tenga formato correcto."""
        rut_str = str(v).strip().replace('.', '').replace('-', '')
        if not rut_str:
            raise ValueError('RUT no puede estar vacío')
        return rut_str
    
    def get_full_rut(self) -> str:
        """Retorna RUT completo (ya viene completo del CSV)."""
        return self.rut
    
    def get_phone_with_prefix(self) -> str:
        """Retorna el teléfono con prefijo +56."""
        return f"+56{self.phone_number}"
    
    def parse_due_date(self) -> tuple[str, int]:
        """Parsea la fecha GMT y calcula días vencidos."""
        try:
            # Extraer la fecha del formato GMT
            if "GMT" in self.overdue_date1:
                date_part = self.overdue_date1.split(" GMT")[0]
                parsed_date = datetime.strptime(date_part, "%a %b %d %Y %H:%M:%S")
                formatted_date = parsed_date.strftime("%d-%m-%Y")
                
                # Calcular días vencidos
                today = datetime.now().date()
                due_date_obj = parsed_date.date()
                days_overdue = max(0, (today - due_date_obj).days)
                return formatted_date, days_overdue
            else:
                return self.overdue_date1, 0
        except Exception:
            return self.overdue_date1, 0
    
    def is_valid(self) -> bool:
        """Verifica si el registro es válido."""
        return (
            bool(self.phone_number) and
            bool(self.name) and
            bool(self.rut) and
            self.overdue_amount1 > 0 and
            self.email not in ['[object Object]', '', 'NaN', 'null']
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
            overdue_amount1=int(row.get('overdue_amount1', 0)),
            down_payment_option1=int(row.get('down_payment_option1', 0)),
            paternal_surname=str(row.get('paternal_surname', '')).strip(),
            rut=str(row.get('rut', '')).strip(),
            email=str(row.get('email', '')).strip(),
            id_carga=id_carga,
            fecha_carga=fecha_carga
        )
    
    def to_firestore_dict(self) -> dict:
        """
        Convierte el registro a diccionario para Firestore (registros_sftp).
        Aquí es donde se hace la transformación de los datos del CSV.
        """
        # Procesar datos del CSV
        due_date, days_overdue = self.parse_due_date()
        clean_id_carga = DateIdUtils.clean_id_for_backend(self.id_carga)
        return {
            "phone_number": self.get_phone_with_prefix(),  # Agregar +56
            "agent_name": "",  # No viene en el CSV, campo vacío
            "client_name": self.name,
            "client_surname": self.paternal_surname,
            "full_name": f"{self.name} {self.paternal_surname}",
            "rut_completo": self.get_full_rut(),  # RUT ya viene completo
            "rut": self.rut,  # RUT completo
            "email": self.email,  # Viene directo del CSV
            "due_date": due_date,  # Fecha procesada
            "days_overdue": days_overdue,  # Días calculados
            "monthly_payment": self.overdue_amount1,  # Mapear overdue_amount1 a monthly_payment
            "overdue_amount1": self.overdue_amount1,  # Mantener campo original
            "down_payment_option1": self.down_payment_option1,
            "overdue_date1": self.overdue_date1,  # Mantener fecha original GMT
            "id_carga": clean_id_carga,
            "fecha_carga": self.fecha_carga.isoformat(),
            "tipo_flujo": "batch_calling",
            "processed_at": datetime.now().isoformat()
        }