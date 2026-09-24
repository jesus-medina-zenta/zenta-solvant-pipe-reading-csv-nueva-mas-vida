"""
Los campos del archivo de deudores de Nueva Masvida (normalizados en pipe-reading)
llegan a metadata_user. Datos ficticios.
"""
import asyncio

from src.pipeline import Pipeline

# Fila del CSV intermedio que genera pipe-reading (solo las columnas relevantes)
ROW = {
    "rut": "11111111K",
    "rut_deudor": "11111111K",
    "name": "Juan Pérez",
    "nombre_deudor": "PÉREZ MUÑOZ JUAN ANDRÉS",
    "nombre_llamada": "Juan Pérez",
    "primer_nombre": "Juan",
    "email": "juan.perez@correo.cl",
    "personal_phone": "912345678",
    "cell_phone": "",
    "deuda_cotizaciones": "84249",
    "menor_per_deuda": "06-2026",
    "mayor_per_deuda": "07-2026",
    "n_periodos": "2",
    "ciudad": "SANTIAGO",
    "clasificacion_deudor": "Dependiente",
    "tipo_deudor": "Afiliado",
    "estado_vigencia": "Vigente",
    "fin_vigencia": "",
    "tramo_deuda": "Tramos 1 a 2",
    "tipo_cartera": "2",
}


def test_campos_del_cliente_llegan_a_metadata_user():
    pipeline = Pipeline.__new__(Pipeline)
    records, errors = asyncio.run(pipeline.transform_data([ROW], batch_id="23092026-test"))

    assert errors == []
    record = records[0]
    assert record.phone_number == "+56912345678"

    metadata = record.metadata_user
    assert metadata.name == "Juan Pérez"
    assert metadata.nombre_deudor == "PÉREZ MUÑOZ JUAN ANDRÉS"
    assert metadata.primer_nombre == "Juan"
    assert metadata.rut_deudor == "11111111K"
    assert metadata.email_destinatario == "juan.perez@correo.cl"
    assert metadata.deuda_cotizaciones == "84249"
    assert metadata.mayor_per_deuda == "07-2026"
    assert metadata.n_periodos == "2"
    assert metadata.ciudad == "SANTIAGO"
    assert metadata.clasificacion_deudor == "Dependiente"
    assert metadata.estado_vigencia == "Vigente"
    assert metadata.tramo_deuda == "Tramos 1 a 2"
    assert metadata.tipo_cartera == "2"
