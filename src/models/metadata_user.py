from pydantic import BaseModel, Field, field_validator

class MetadataUser(BaseModel):
    queue: str = Field(..., description="Cola de atención")
    queue_id_cyber: str = Field(..., description="ID de cola en Cyber")
    rut: str = Field(..., description="RUT del usuario")
    name: str = Field(..., description="Nombre del usuario")
    paternal_surname: str = Field(..., description="Apellido paterno")
    maternal_surname: str = Field(..., description="Apellido materno")
    days_overdue: str = Field(..., description="Días de mora")
    monthly_payment: str = Field(..., description="Pago mensual")
    down_payment_option1: str = Field(..., description="Opción de pago inicial")
    process_date: str = Field(..., description="Fecha de proceso")
    overdue_date1: str = Field(..., description="Fecha de vencimiento original")
    overdue_amount1: str = Field(..., description="Monto vencido")
    email: str = Field(..., description="Email del cliente")
    card: str = Field(..., description="Tarjeta")
    expiration_date: str = Field(..., description="Fecha de expiración")
    gender: str = Field(..., description="Género del usuario")

    @field_validator('gender')
    @classmethod
    def transform_gender(cls, v: str) -> str:
        """Transforma el código de género a su representación textual"""
        if not v:
            return v
        
        v_upper = v.upper().strip()
        if v_upper == 'F':
            return 'DOÑA'
        elif v_upper == 'M':
            return 'DON'
        return v  # Mantener el valor original si no es F o M