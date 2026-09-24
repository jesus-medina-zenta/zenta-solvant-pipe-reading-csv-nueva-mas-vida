"""
Data models using Pydantic for validation.
"""
from datetime import datetime, timezone
from typing import Optional, Any, Dict
import uuid
from src.utils.logger import get_logger
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from src.models.metadata_user import MetadataUser
logger = get_logger(__name__)

class DataRecord(BaseModel):
    fecha: datetime = Field(..., description="Fecha y hora de inicio")
    id: str = Field(..., description="ID de la carga")
    phone_number: str = Field(..., max_length=15, description="Teléfono principal")
    phone_number_2: Optional[str] = Field("", max_length=15, description="Teléfono secundario")
    metadata_user: MetadataUser = Field(..., description="Datos del usuario agrupados")

    track_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único para tracking interno")
    track_status: str = Field(default="queued_call", description="Estado del tracking interno")

    @classmethod
    def from_line(cls, line: str, carga_id: str, fecha_utc: str) -> "DataRecord":
        """Crea un DataRecord desde una línea del archivo TXT con manejo detallado de errores"""
        try:
            logger.debug(f"Procesando línea de {len(line)} caracteres para carga_id: {carga_id}")
            
            # Extraer campos de metadata con manejo de excepciones individual
            metadata_fields = {}
            field_mappings = [
                ('queue', 0, 4),
                ('queue_id_cyber', 0, 4),
                ('rut_number', 4, 12),
                ('rut_digit', 12, 13),
                ('name', 48, 128),
                ('paternal_surname', 128, 208),
                ('maternal_surname', 208, 212),
                ('days_overdue', 473, 478),
                ('monthly_payment', 478, 493),
                ('down_payment_option1', 508, 523),
                ('process_date', 572, 582),
                ('overdue_date1', 586, 596),
                ('overdue_amount1', 596, 611),
                ('email', 822, 882),
                ('card', 902, 908),
                ('expiration_date', 1008, 1018),
                ('gender', 1029, 1030)
            ]
            
            for field_name, start, end in field_mappings:
                try:
                    if field_name == 'rut_number':
                        rut_number = cls._extract_field(line, start, end, field_name)
                    elif field_name == 'rut_digit':
                        rut_digit = cls._extract_field(line, start, end, field_name)
                        metadata_fields['rut'] = f"{rut_number}{rut_digit}"
                    else:
                        metadata_fields[field_name] = cls._extract_field(line, start, end, field_name)
                except ValueError as e:
                    logger.warning(f"Error en campo {field_name}: {e}")
                    metadata_fields[field_name] = ""  # Valor por defecto en caso de error
            
            # Extraer teléfonos con manejo específico
            try:
                personal_phone = cls._extract_field(line, 377, 392, 'personal_phone')
            except ValueError as e:
                logger.warning(f"Error extrayendo personal_phone: {e}")
                personal_phone = ""
            
            try:
                cell_phone = cls._extract_field(line, 397, 412, 'cell_phone')
            except ValueError as e:
                logger.warning(f"Error extrayendo cell_phone: {e}")
                cell_phone = ""
            
            # Crear metadata con validación
            try:
                metadata = MetadataUser(**metadata_fields)
            except Exception as e:
                raise ValueError(f"Error creando MetadataUser: {str(e)}. Campos: {metadata_fields}")
            
            # Aplicar lógica de intercambio de teléfonos
            phone_1 = f"+56{personal_phone}" if personal_phone else ""
            phone_2 = f"+56{cell_phone}" if cell_phone else ""
            
            # Validación y intercambio de teléfonos
            if not phone_1 or phone_1 == "+56":
                if phone_2 and phone_2 != "+56":
                    logger.info(f"Intercambiando teléfonos: cell_phone '{cell_phone}' -> phone_number")
                    phone_1 = phone_2
                    phone_2 = ""
                else:
                    raise ValueError(f"No se encontró número de teléfono válido. personal_phone='{personal_phone}', cell_phone='{cell_phone}'")
            
            # Limpiar phone_2 si está vacío
            if phone_2 == "+56":
                phone_2 = ""
            
            # Extraer ID limpio
            id_parte = carga_id.split('-', 1)[1] if '-' in carga_id else carga_id
            
            logger.debug(f"Registro creado exitosamente: phone_number='{phone_1}', phone_number_2='{phone_2}'")
            
            return cls(
                fecha=fecha_utc,
                id=id_parte,
                phone_number=phone_1[:15],
                phone_number_2=phone_2[:15] if phone_2 else "",
                metadata_user=metadata
            )
            
        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Error inesperado procesando línea (longitud={len(line)}): {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        """Valida que el teléfono principal no esté vacío"""
        if not v or v.strip() == "" or v.strip() == "+56":
            raise ValueError('phone_number es requerido y no puede estar vacío')
        return v.strip()

    @field_validator('phone_number_2')
    @classmethod
    def validate_phone_number_2(cls, v):
        """Valida el teléfono secundario (opcional)"""
        if v is not None and (v.strip() == "" or v.strip() == "+56"):
            return None  
        return v.strip() if v else None

    @model_validator(mode='after')
    def validate_at_least_one_phone(self):
        """Valida que al menos phone_number tenga un valor válido"""
        if not self.phone_number or self.phone_number.strip() == "" or self.phone_number.strip() == "+56":
            raise ValueError('Debe tener al menos un número de teléfono válido (phone_number)')
        return self
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], carga_id: str, fecha_utc: str) -> "DataRecord":
        """Crea un DataRecord desde un diccionario con manejo detallado de errores"""
        try:
            logger.debug(f"Procesando diccionario para carga_id: {carga_id}")
            
            # 🔍 DEBUG: Agregar logging para debuggear el problema del gender
            logger.info(f"🔍 DEBUG - Datos recibidos en from_dict:")
            logger.info(f"🔍 DEBUG - Keys del diccionario: {list(data.keys())}")
            logger.info(f"🔍 DEBUG - Valor de gender: '{data.get('gender', 'NOT_FOUND')}'")
            logger.info(f"🔍 DEBUG - Tipo de gender: {type(data.get('gender', 'NOT_FOUND'))}")
            
            # Lista de campos requeridos para MetadataUser
            required_fields = ['rut', 'name']
            missing_fields = [field for field in required_fields if not data.get(field, '').strip()]
            
            if missing_fields:
                logger.warning(f"Campos faltantes o vacíos: {missing_fields}")
            
            # 🔍 DEBUG: Logging antes de crear MetadataUser
            gender_value = data.get('gender', '').strip()
            logger.info(f"🔍 DEBUG - Valor de gender después de strip: '{gender_value}'")
            
            metadata = MetadataUser(
                rut_deudor=data.get('rut_deudor', '').strip() or data.get('rut', '').strip(),
                nombre_deudor=data.get('nombre_deudor', '').strip() or data.get('name', '').strip(),
                email_destinatario=data.get('email_destinatario', '').strip() or data.get('email', '').strip(),
                deuda_cotizaciones=data.get('deuda_cotizaciones', '').strip() or data.get('overdue_amount1', '').strip(),
                monto_cupon=data.get('monto_cupon', '').strip() or data.get('down_payment_option1', '').strip(),
                monto_posible_compensar=data.get('monto_posible_compensar', '').strip(),
                url_link=data.get('url_link', '').strip(),
                fecha_compromiso=data.get('fecha_compromiso', '').strip() or data.get('process_date', '').strip(),
                monto_compromiso=data.get('monto_compromiso', '').strip(),
                fono_contacto=data.get('fono_contacto', '').strip(),
                menor_per_deuda=data.get('menor_per_deuda', '').strip(),
                mayor_per_deuda=data.get('mayor_per_deuda', '').strip(),
                name=data.get('name', '').strip(),
                primer_nombre=data.get('primer_nombre', '').strip(),
                n_periodos=data.get('n_periodos', '').strip(),
                ciudad=data.get('ciudad', '').strip(),
                clasificacion_deudor=data.get('clasificacion_deudor', '').strip(),
                tipo_deudor=data.get('tipo_deudor', '').strip(),
                estado_vigencia=data.get('estado_vigencia', '').strip(),
                fin_vigencia=data.get('fin_vigencia', '').strip(),
                tramo_deuda=data.get('tramo_deuda', '').strip(),
                tipo_cartera=data.get('tipo_cartera', '').strip(),
            )
            
            # 🔍 DEBUG: Logging después de crear MetadataUser
            logger.info(f"🔍 DEBUG - Gender en metadata creado: '{metadata.gender}'")

            # Extraer y validar teléfonos
            personal_phone = data.get('personal_phone', '').strip() or data.get('fono_contacto', '').strip()
            cell_phone = data.get('cell_phone', '').strip()
            
            logger.debug(f"Teléfonos originales: personal_phone='{personal_phone}', cell_phone='{cell_phone}'")
            
            # Aplicar lógica de intercambio
            phone_1 = f"+56{personal_phone}" if personal_phone else ""
            phone_2 = f"+56{cell_phone}" if cell_phone else ""
            
            if not phone_1 or phone_1 == "+56":
                if phone_2 and phone_2 != "+56":
                    logger.info(f"Intercambiando teléfonos: cell_phone '{cell_phone}' -> phone_number")
                    phone_1 = phone_2
                    phone_2 = ""
                else:
                    raise ValueError(f"No se encontró número de teléfono válido. personal_phone='{personal_phone}', cell_phone='{cell_phone}'")
            
            if phone_2 == "+56":
                phone_2 = ""
            
            # Si el carga_id empieza con fecha (ddmmyyyy-), mantener el ID completo para batch calling
            if carga_id and len(carga_id) > 8 and carga_id[8] == '-' and carga_id[:8].isdigit():
                # Es formato ddmmyyyy-uuid_numero (batch calling) - mantener completo
                id_final = carga_id
                logger.debug(f"ID batch calling detectado - usando ID completo: {id_final}")
            else:
                # Es formato traditional - extraer parte después del primer guión
                id_final = carga_id.split('-', 1)[1] if '-' in carga_id else carga_id
                logger.debug(f"ID tradicional detectado - usando ID cortado: {id_final}")
            
            logger.debug(f"Registro creado exitosamente desde dict: phone_number='{phone_1}', phone_number_2='{phone_2}', id='{id_final}'")
            
            return cls(
                fecha=fecha_utc,
                id=id_final,  # ✅ Usar el ID determinado automáticamente
                phone_number=phone_1[:15],
                phone_number_2=phone_2[:15] if phone_2 else "",
                metadata_user=metadata
            )
            
        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Error inesperado procesando diccionario: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    @classmethod
    def _extract_field(cls, line: str, start: int, end: int, field_name: str, strip: bool = True) -> str:
        """
        Extrae un campo de una línea de texto de ancho fijo con manejo de excepciones.
        
        Args:
            line: Línea de texto de origen
            start: Posición inicial (0-indexed)
            end: Posición final (exclusiva)
            field_name: Nombre del campo para logging de errores
            strip: Si debe remover espacios en blanco
            
        Returns:
            str: Campo extraído
            
        Raises:
            ValueError: Si hay error en la extracción del campo
        """
        try:
            if not line:
                raise ValueError(f"Línea vacía para extraer campo '{field_name}'")
            
            if start < 0 or end < 0:
                raise ValueError(f"Posiciones negativas no permitidas para campo '{field_name}' (start={start}, end={end})")
            
            if start >= end:
                raise ValueError(f"Posición inicial debe ser menor que final para campo '{field_name}' (start={start}, end={end})")
            
            if end > len(line):
                logger.warning(f"Campo '{field_name}': línea más corta que esperado (longitud={len(line)}, end={end})")
                # Ajustar end a la longitud de la línea
                end = len(line)
            
            if start >= len(line):
                logger.warning(f"Campo '{field_name}': posición inicial fuera de rango (start={start}, longitud={len(line)})")
                return ""
            
            extracted = line[start:end]
            result = extracted.strip() if strip else extracted
            
            logger.debug(f"Campo '{field_name}' extraído: posiciones [{start}:{end}] = '{result}'")
            return result
            
        except Exception as e:
            error_msg = f"Error extrayendo campo '{field_name}' en posiciones [{start}:{end}]: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def is_valid(self) -> bool:
        """Validates that critical fields are present, including phone_number."""
        return bool(
            self.phone_number and self.phone_number.strip() and self.phone_number != "+56" and
            (self.metadata_user.rut_deudor or self.metadata_user.rut) and
            (self.metadata_user.nombre_deudor or self.metadata_user.name)
        )
    
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "id": "16092025-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "phone_number": "+56912345678",
                "phone_number_2": "+56987654321",
                "metadata_user": {
                    "queue": "PRA3",
                    "rut": "12345678-9",
                    "name": "Juan Pérez"
                }
            }
        }
    )

class ProcessingStats(BaseModel):
    """
    Model for pipeline processing statistics.
    """
    
    total_records: int = Field(0, description="Total records processed")
    successful_records: int = Field(0, description="Successfully processed records")
    failed_records: int = Field(0, description="Failed records")
    processing_time_seconds: float = Field(0.0, description="Total processing time in seconds")
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_records == 0:
            return 0.0
        return (self.successful_records / self.total_records) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_records == 0:
            return 0.0
        return (self.failed_records / self.total_records) * 100
    
    def add_success(self) -> None:
        """Increments the successful records counter."""
        self.successful_records += 1
        self.total_records += 1
    
    def add_failure(self) -> None:
        """Increments the failed records counter."""
        self.failed_records += 1
        self.total_records += 1
    
    def finish(self) -> None:
        """Marks processing as finished."""
        self.end_time = datetime.now(timezone.utc)
        if self.start_time:
            delta = self.end_time - self.start_time
            self.processing_time_seconds = delta.total_seconds()


class ErrorRecord(BaseModel):
    """
    Model for recording errors during processing.
    """
    
    record_id: Optional[str] = Field(None, description="ID of the record that caused the error")
    error_type: str = Field(..., description="Error type")
    error_message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")
    stage: str = Field(..., description="Pipeline stage where the error occurred")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw data that caused the error")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "record_id": "123",
                "error_type": "ValidationError",
                "error_message": "Field 'name' is required",
                "timestamp": "2023-01-01T12:00:00Z",
                "stage": "transform",
                "raw_data": {"id": 123, "value": 100}
            }
        }
    )


class PipelineConfig(BaseModel):
    """
    Model for pipeline-specific configuration.
    """
    
    source_query: Optional[str] = Field(None, description="SQL query to extract data")
    batch_size: int = Field(1000, gt=0, description="Batch size for processing")
    max_retries: int = Field(3, ge=0, description="Maximum number of retries")
    enable_validation: bool = Field(True, description="Enable data validation")
    output_format: str = Field("json", description="Output format")
    custom_filters: Optional[Dict[str, Any]] = Field(None, description="Custom filters")
    
    @field_validator('output_format')
    @classmethod
    def validate_output_format(cls, v):
        """Validates that the output format is supported."""
        supported_formats = ['json', 'csv', 'parquet']
        if v not in supported_formats:
            raise ValueError(f'Unsupported format. Use one of: {supported_formats}')
        return v