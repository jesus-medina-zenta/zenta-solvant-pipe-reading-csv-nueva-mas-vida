from pydantic import BaseModel, Field, field_validator, model_validator

class MetadataUser(BaseModel):
    queue: str = Field(default="", description="Cola de atención")
    queue_id_cyber: str = Field(default="", description="ID de cola en Cyber")
    rut: str = Field(default="", description="RUT del usuario")
    name: str = Field(default="", description="Nombre del usuario")
    paternal_surname: str = Field(default="", description="Apellido paterno")
    maternal_surname: str = Field(default="", description="Apellido materno")
    days_overdue: str = Field(default="", description="Días de mora")
    monthly_payment: str = Field(default="", description="Pago mensual")
    down_payment_option1: str = Field(default="", description="Opción de pago inicial")
    process_date: str = Field(default="", description="Fecha de proceso")
    overdue_date1: str = Field(default="", description="Fecha de vencimiento original")
    overdue_amount1: str = Field(default="", description="Monto vencido")
    email: str = Field(default="", description="Email del cliente")
    card: str = Field(default="", description="Tarjeta")
    expiration_date: str = Field(default="", description="Fecha de expiración")
    gender: str = Field(default="", description="Género del usuario")

    rut_deudor: str = Field(default="", description="RUT del afiliado")
    nombre_deudor: str = Field(default="", description="Nombre del afiliado")
    email_destinatario: str = Field(default="", description="Correo del afiliado")
    deuda_cotizaciones: str = Field(default="", description="Monto total de la deuda")
    monto_cupon: str = Field(default="", description="Monto con descuento")
    monto_posible_compensar: str = Field(default="", description="Saldo disponible para compensar")
    url_link: str = Field(default="", description="Link único de pago por deudor")
    fecha_compromiso: str = Field(default="", description="Fecha de compromiso de pago")
    monto_compromiso: str = Field(default="", description="Monto comprometido por el afiliado")
    fono_contacto: str = Field(default="", description="Número de contacto del afiliado")
    menor_per_deuda: str = Field(default="", description="Período mínimo de la deuda")
    mayor_per_deuda: str = Field(default="", description="Período máximo de la deuda")

    # Archivo de deudores de Nueva Masvida (normalizado en pipe-reading, utils/client_record.py)
    primer_nombre: str = Field(default="", description="Primer nombre, para dirigirse al deudor")
    n_periodos: str = Field(default="", description="Número de períodos adeudados")
    ciudad: str = Field(default="", description="Ciudad de residencia o asignada")
    clasificacion_deudor: str = Field(default="", description="Dependiente, Voluntario, Pensionado, etc.")
    tipo_deudor: str = Field(default="", description="Tipo de deudor (Afiliado)")
    estado_vigencia: str = Field(default="", description="Estado de vigencia del contrato")
    fin_vigencia: str = Field(default="", description="Fin de vigencia del contrato")
    tramo_deuda: str = Field(default="", description="Tramo del menor período de deuda")
    tipo_cartera: str = Field(default="", description="Tipo de cartera")

    @model_validator(mode='after')
    def sync_alias_fields(self) -> "MetadataUser":
        """Mantiene sincronía entre campos legacy y encabezados reales del Excel."""
        if not self.rut and self.rut_deudor:
            self.rut = self.rut_deudor
        if not self.rut_deudor and self.rut:
            self.rut_deudor = self.rut

        if not self.name and self.nombre_deudor:
            self.name = self.nombre_deudor
        if not self.nombre_deudor and self.name:
            self.nombre_deudor = self.name

        if not self.email and self.email_destinatario:
            self.email = self.email_destinatario
        if not self.email_destinatario and self.email:
            self.email_destinatario = self.email

        if not self.overdue_amount1 and self.deuda_cotizaciones:
            self.overdue_amount1 = self.deuda_cotizaciones
        if not self.deuda_cotizaciones and self.overdue_amount1:
            self.deuda_cotizaciones = self.overdue_amount1

        if not self.down_payment_option1 and self.monto_cupon:
            self.down_payment_option1 = self.monto_cupon
        if not self.monto_cupon and self.down_payment_option1:
            self.monto_cupon = self.down_payment_option1

        if not self.process_date and self.fecha_compromiso:
            self.process_date = self.fecha_compromiso
        if not self.fecha_compromiso and self.process_date:
            self.fecha_compromiso = self.process_date

        return self

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