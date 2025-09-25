from pydantic import BaseModel, Field

class MetadataUser(BaseModel):
    queue: str = Field(..., description="Cola de atención")
    queue_id_cyber: str = Field(..., description="ID de cola en Cyber")
    rut: str = Field(..., description="RUT del usuario")
    name: str = Field(..., description="Nombre del usuario")
    paternal_surname: str = Field(..., description="Apellido paterno")
    maternal_surname: str = Field(..., description="Apellido materno")
    days_overdue: str = Field(..., description="Días de mora")
    monthly_payment: str = Field(..., description="Pago mensual")
    down_payment_option1: str = Field(..., description="Opción de pie 1")
    process_date: str = Field(..., description="Fecha de proceso")
    overdue_date1: str = Field(..., description="Fecha de vencimiento 1")
    overdue_amount1: str = Field(..., description="Monto vencido 1")
    email: str = Field(..., description="Correo electrónico")
    card: str = Field(..., description="Tarjeta")
    expiration_date: str = Field(..., description="Fecha de expiración")