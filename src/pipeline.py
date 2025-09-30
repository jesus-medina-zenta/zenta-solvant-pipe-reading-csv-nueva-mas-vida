"""
Lógica principal del pipeline ETL.
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone

from src.config import init_config
from src.enums.status import PipelineType, StatusType
from src.models.batch_record import BatchCallingRecord, BatchRecord
from src.models.data_models import DataRecord
from src.models.log_record import LogRecord
from src.services.backend_service import BackendApiService
from src.services.firestore_service import FirestoreService
from src.services.gcs_service import CloudStorageService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Unir types
RecordType = Union[LogRecord, BatchRecord]

class Pipeline:
    """
    Pipeline principal para procesamiento ETL.
    """
    
    def __init__(self, batch_id: Optional[str] = None):
        """Inicializa el pipeline con los servicios necesarios."""

        self.firestore_service = FirestoreService()
        self.gcs_service = CloudStorageService()
        self.backend_service = BackendApiService()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.batch_id = batch_id
        logger.info(f"⚙️ Modo de operación del pipeline: {batch_id} (backend)" if batch_id else "⚙️ Modo de operación del pipeline: SFTP")

    async def initialize_services(self) -> bool:
        """
        Inicializa y conecta todos los servicios necesarios.
        
        Returns:
            bool: True si todos los servicios se conectaron exitosamente
        """
        try:
            logger.info("🚀 Inicializando servicios...")
            
            # Conectar Firestore
            if not self.firestore_service.connect():
                logger.error("❌ Error conectando a Firestore")
                return False
            
            # Conectar GCS
            if not await self.gcs_service.connect():
                logger.error("❌ Error conectando a GCS")
                return False
            
            logger.info("✅ Todos los servicios inicializados correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando servicios: {e}")
            return False

    async def run(self) -> bool:
        """
        Ejecuta el pipeline completo.
        
        Returns:
            bool: True si el pipeline fue exitoso, False en caso contrario
        """
        self.start_time = datetime.now(timezone.utc)
        logger.info("🔄 Iniciando pipeline integrado de procesamiento CSV")

        try:
            # Inicializar servicios
            if not await self.initialize_services():
                return False
            
            # Flujo específico para archivo batch
            if self.batch_id:
                logger.info(f"📋 Obteniendo archivo específico: {self.batch_id}")
                specific_record = self.firestore_service.get_batch_record_by_id(self.batch_id)

                print("="*100)
                print(specific_record)
                print("="*100)
                
                if specific_record is None:
                    logger.error(f"❌ No se encontró el archivo con ID: {self.batch_id}")
                    return False
                
                print("PendingLogsID: ", specific_record.id_carga)
                
                # Procesar archivo específico con parámetro batch_record
                success = await self.process_single_file(batch_record=specific_record)
                
                if success:
                    logger.info(f"✅ Pipeline específico ({self.batch_id}) completado exitosamente")
                else:
                    logger.error(f"❌ Pipeline específico ({self.batch_id}) falló")
                
                return success
            
            # Flujo normal para archivos SFTP
            else:
                logger.info("📋 Obteniendo archivos pendientes en modo SFTP")
                pending_logs = self.firestore_service.get_pending_logs()
                
                if not pending_logs:
                    logger.info("📭 No hay archivos SFTP pendientes para procesar")
                    return True
                
                logger.info(f"📋 Procesando {len(pending_logs)} archivos SFTP pendientes")
                
                # Procesar cada archivo SFTP
                processed_count = 0
                error_count = 0
                
                for log_record in pending_logs:
                    try:
                        # Procesar archivo SFTP con parámetro log_record
                        success = await self.process_single_file(log_record=log_record)
                        if success:
                            processed_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        logger.error(f"❌ Error procesando archivo {log_record.id}: {e}")
                        error_count += 1
                
                # Resumen final SFTP
                logger.info(f"✅ Pipeline SFTP completado: {processed_count} exitosos, {error_count} errores")
                return error_count == 0
                
        except Exception as e:
            logger.exception(f"❌ Error crítico en el pipeline: {e}")
            return False
        finally:
            await self.cleanup()
        
    async def process_single_file(self, log_record: Optional[LogRecord] = None, batch_record: Optional[BatchRecord] = None) -> bool:
        """
        Procesa un solo archivo CSV.
        
        Args:
            log_record: Registro de log SFTP (opcional)
            batch_record: Registro de batch calling (opcional)
            
        Returns:
            bool: True si el procesamiento fue exitoso
        """
        # Validar que se reciba exactamente uno de los dos tipos
        if (log_record is None and batch_record is None) or (log_record is not None and batch_record is not None):
            logger.error("❌ Debe proporcionarse exactamente un tipo de registro (LogRecord o BatchRecord)")
            return False
        
        # Determinar qué tipo de registro estamos procesando
        if batch_record:
            original_record = batch_record
            record = batch_record
            is_backend_mode = True
            is_batch_calling = True
            record_type = "BATCH_CALLING"
            original_batch_id = record.id_carga
            logger.info(f"📁 Procesando archivo batch calling: {record.id_carga}")
            logger.info(f"📊 Batch: {record.call_name}, Tipo: {record.file_type}, Tamaño: {record.file_size} bytes")
        else:
            original_record = log_record
            record = log_record
            is_backend_mode = False
            is_batch_calling = False
            record_type = "SFTP"
            original_batch_id = record.id
            logger.info(f"📁 Procesando archivo SFTP: {record.id}")
            logger.info(f"📊 SFTP: {record.archivo_sftp}")

        start_time = datetime.now(timezone.utc)
        
        try:
            # 1. Actualizar estado a PROCESANDO en la colección correcta
            self.firestore_service.update_log_status(
                original_batch_id,  # Para batch: id_carga, Para SFTP: id
                StatusType.PROCESANDO,
                is_backend=is_backend_mode,  # True = registro_archivos, False = logs_csv
                fecha_inicio=start_time.isoformat(),
                pipeline_type=PipelineType.TRANSFORMATION.value
            )
            
            # 2. Extraer datos del CSV desde GCS
            raw_data = await self.extract_from_gcs(record.csv_generado)  # Para batch: file_path, Para SFTP: csv_generado
            if not raw_data:
                error_msg = "No se pudieron extraer datos del CSV"
                await self.mark_as_error(record, error_msg, is_backend_mode)
                return False
            
            logger.info(f"📖 Extraídos {len(raw_data)} registros del CSV")
            
            # 3. Transformar datos según el tipo de flujo
            if is_batch_calling:
                # Para batch calling: crear DataRecord con IDs formato ddmmyyyy-uuid_numero
                transformed_data, transformation_errors = await self.transform_data(
                    raw_data, 
                    is_batch_calling=True, 
                    batch_id=original_batch_id  # Pasar el UUID del batch
                )
            else:
                # Para SFTP: usar el flujo original con extraction_id
                transformed_data, transformation_errors = await self.transform_data(
                    raw_data, 
                    is_batch_calling=False,
                    batch_id=original_batch_id
                )
            
            if not transformed_data:
                error_msg = "Error en la transformación de datos - no se pudieron procesar registros"
                all_errors = [error_msg] + transformation_errors
                await self.mark_as_error(record, all_errors, is_backend_mode)
                return False
            
            logger.info(f"🔄 Transformados {len(transformed_data)} registros")
            if is_batch_calling and transformed_data:
                logger.info("🔍 DEBUGGING - Primeros registros transformados:")
                for i, record in enumerate(transformed_data[:2]):
                    logger.info(f"  Registro {i+1}:")
                    logger.info(f"    ID: {record.id}")
                    logger.info(f"    Teléfono: {record.phone_number}")
                    logger.info(f"    Metadata User: {record.metadata_user}")
                    logger.info(f"    Tipo: {type(record)}")
                    
                    # Verificar que se puede serializar
                    try:
                        dumped = record.model_dump(mode="json")
                        logger.info(f"    ✅ Serialización exitosa, tamaño: {len(str(dumped))} chars")
                    except Exception as e:
                        logger.error(f"    ❌ Error en serialización: {e}")
            # 4. Guardar datos transformados en registros_sftp (ambos flujos van a la misma colección)
            save_success = self.firestore_service.save_transformed_records(
                transformed_data,          # Lista de DataRecord
                original_batch_id,                # ID para metadatos (log_id)
                is_batch_calling=is_batch_calling  # Para usar el ID correcto del documento
            )
            
            if not save_success:
                error_msg = "Error guardando datos transformados en Firestore"
                all_errors = [error_msg] + transformation_errors if transformation_errors else [error_msg]
                await self.mark_as_error(record, all_errors, is_backend_mode)
                return False
            
            # 5. Actualizar estado final en la colección original
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            update_data = {
                "fecha_fin": end_time.isoformat(),
                "duracion_segundos": duration,
                "registros_extraidos": len(raw_data),
                "registros_transformados": len(transformed_data),
                "registros_cargados": len(transformed_data),
                "pipeline_type": PipelineType.TRANSFORMATION.value
            }
            
            if transformation_errors:
                update_data["errores"] = transformation_errors
                logger.warning(f"⚠️ Procesamiento completado con {len(transformation_errors)} errores de transformación")
            
            # Actualizar estado final (PARSEADO para SFTP, se mapea a "completado" para batch)
            self.firestore_service.update_log_status(
                original_batch_id,
                StatusType.PARSEADO,  
                is_backend=is_backend_mode,  # True = registro_archivos, False = logs_csv
                **update_data
            )
            
            logger.info(f"✅ Archivo {original_batch_id} ({record_type}) procesado exitosamente en {duration:.2f}s")
            logger.info(f"📊 Estadísticas: {len(raw_data)} extraídos, {len(transformed_data)} transformados, {len(transformed_data)} cargados")
            #6. Notificar al backend 
            await self.notify_backend_completion(
                original_batch_id,
                record_type,
                original_record
            )
            return True
            
        except Exception as e:
            logger.exception(f"❌ Error procesando archivo {original_batch_id}: {e}")
            await self.notify_backend_error(
                original_batch_id, 
                original_record
            )
            
            await self.mark_as_error(record, [f"Error crítico en procesamiento: {str(e)}"], is_backend_mode, original_batch_id)
            return False
        
    async def extract_from_gcs(self, gcs_url: str) -> List[Dict[str, Any]]:
        """
        Extrae datos de un archivo CSV en GCS.
        
        Args:
            gcs_url: URL del archivo CSV en GCS
            
        Returns:
            List[Dict[str, Any]]: Datos extraídos del CSV
        """
        try:
            if not gcs_url:
                logger.error("❌ URL de GCS vacía")
                return []
            
            data = await self.gcs_service.read_csv_from_gcs_url(gcs_url)
            return data
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo datos de GCS: {e}")
            return []

    async def transform_data(self, raw_data: List[Dict[str, Any]], is_batch_calling: bool = False, batch_id: Optional[str] = None) -> Tuple[List[DataRecord], List[str]]:
        """
        Transforma los datos extraídos del CSV.
        
        Args:
            raw_data: Datos en bruto del CSV
            is_batch_calling: True si es batch calling, False si es SFTP
            batch_id: ID del batch/archivo para usar como base en los IDs
            
        Returns:
            Tuple[List[DataRecord], List[str]]: Tupla con datos transformados y lista de errores
        """
        try:
            transformed_data = []
            transformation_errors = []
            
            if not raw_data:
                logger.warning("⚠️ No hay datos para transformar")
                return [], ["No hay datos para transformar"]
            
            # Generar fecha actual en UTC
            fecha_utc = datetime.now(timezone.utc)
            # Formato de fecha para IDs: ddmmyyyy
            fecha_ddmmyyyy = fecha_utc.strftime("%d%m%Y")
            
            logger.info(f"🔄 Iniciando transformación de {len(raw_data)} registros")
            logger.info(f"📅 Fecha para IDs: {fecha_ddmmyyyy}")
            
            if is_batch_calling:
                logger.info(f"🎯 Modo batch calling - usando batch_id: {batch_id}")
            else:
                logger.info(f"🎯 Modo SFTP - usando batch_id: {batch_id}")
            
            for idx, row in enumerate(raw_data):
                try:
                    if is_batch_calling:
                        # Lógica para batch calling (sin cambios)
                        carga_id = f"{fecha_ddmmyyyy}-{batch_id}_{idx + 1}"
                        
                        # Mapear campos de batch calling a estructura DataRecord
                        mapped_data = {
                            'queue': 'BATCH',
                            'queue_id_cyber': 'BATCH',
                            'rut': f"{row.get('rut', '').strip()}-{row.get('dv', '').strip()}",
                            'name': row.get('name', '').strip(),
                            'paternal_surname': row.get('paternal_surname', '').strip(),
                            'maternal_surname': '',
                            'days_overdue': str(row.get('days_overdue', '')).strip(),
                            'monthly_payment': str(row.get('monthly_payment', '')).strip(),
                            'down_payment_option1': str(row.get('down_payment_option1', '')).strip(),
                            'process_date': '',
                            'overdue_date1': row.get('due_date', '').strip(),
                            'overdue_amount1': '',
                            'email': row.get('mail', '').strip(),
                            'card': '',
                            'expiration_date': '',
                            'personal_phone': row.get('phone_number', '').strip().replace('+56', ''),
                            'cell_phone': ''
                        }
                        
                        logger.debug(f"📋 Registro batch {idx + 1} - ID: {carga_id}")
                        
                    else:
                        # CORREGIDO: Lógica para SFTP - usar el UUID del archivo CSV como base
                        carga_id = f"{fecha_ddmmyyyy}-{batch_id}_{idx + 1}"
                        
                        # Para SFTP, usar los datos tal como vienen del CSV
                        mapped_data = row
                        
                        logger.debug(f"📋 Registro SFTP {idx + 1} - ID: {carga_id}")
                        logger.debug(f"📋 extraction_id original: {row.get('extraction_id', 'N/A')}")
                    
                    logger.debug(f"🔍 DEBUG Antes de from_dict - carga_id: {carga_id}")
                    
                    # Crear el registro usando el método from_dict
                    record = DataRecord.from_dict(
                        data=mapped_data,
                        carga_id=carga_id,
                        fecha_utc=fecha_utc
                    )
                    
                    logger.debug(f"🔍 DEBUG Después de from_dict - record.id: {record.id}")
                    
                    # Validar que el registro sea válido
                    if record.is_valid():
                        transformed_data.append(record)
                        logger.debug(f"✅ Registro {idx + 1} transformado exitosamente - ID: {record.id}")
                    else:
                        error_msg = f"Fila {idx + 1}: Registro inválido después de transformación"
                        transformation_errors.append(error_msg)
                    
                except ValueError as ve:
                    error_msg = f"Error de validación en fila {idx + 1}: {str(ve)}"
                    transformation_errors.append(error_msg)
                    logger.debug(error_msg)
                    
                except Exception as e:
                    error_msg = f"Error inesperado en fila {idx + 1}: {str(e)}"
                    transformation_errors.append(error_msg)
                    logger.debug(error_msg)
            
            # Evaluación de resultados
            total_records = len(raw_data)
            success_count = len(transformed_data)
            error_count = len(transformation_errors)
            success_rate = (success_count / total_records * 100) if total_records > 0 else 0
            
            record_type = "batch calling" if is_batch_calling else "SFTP"
            logger.info(f"📊 Resultados transformación {record_type}: {success_count}/{total_records} exitosos ({success_rate:.1f}%)")
            
            if transformation_errors:
                logger.warning(f"⚠️ {error_count} errores en transformación:")
                # Mostrar primeros 5 errores para debugging
                sample_errors = transformation_errors[:5]
                for error in sample_errors:
                    logger.warning(f"   - {error}")
                
                if len(transformation_errors) > 5:
                    logger.warning(f"   ... y {len(transformation_errors) - 5} errores más")
            
            # Mostrar algunos IDs generados para verificación
            if transformed_data:
                logger.info(f"📋 IDs generados para {record_type}:")
                for i, record in enumerate(transformed_data[:3]):  # Mostrar primeros 3
                    logger.info(f"   {i+1}. {record.id}")
                if len(transformed_data) > 3:
                    logger.info(f"   ... y {len(transformed_data) - 3} registros más")
            
            # Solo fallar si hay menos del 20% de éxito
            if success_rate < 20:
                error_summary = f"Tasa de éxito muy baja: {success_rate:.1f}% ({success_count}/{total_records})"
                logger.error(f"❌ {error_summary}")
                transformation_errors.insert(0, error_summary)
                return [], transformation_errors
            
            return transformed_data, transformation_errors
            
        except Exception as e:
            logger.error(f"❌ Error crítico en transformación: {e}")
            return [], [f"❌ Error crítico en transformación: {e}"]
    async def notify_backend_completion(self, carga_id: str, pipeline_type: str, record: RecordType) -> None:
        """
        Notifica al backend que el pipeline se completó exitosamente.
        
        Args:
            carga_id: ID de la carga procesada (UUID original del batch/archivo)
            pipeline_type: Tipo de pipeline ("BATCH_CALLING" o "SFTP")
            stats: Estadísticas del procesamiento
        """
        try:
            logger.info(f"📡 Iniciando notificación de completion al backend...")
            logger.info(f"🆔 ID de carga a notificar: {carga_id}")
            
            # Ejecutar notificación en thread separado para no bloquear
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.backend_service.notify_pipeline_completion,
                carga_id,
                pipeline_type,
                record
            )
            
            if success:
                logger.info(f"✅ Backend notificado exitosamente para {record.pipeline_type}: {carga_id}")
            else:
                logger.warning(f"⚠️ Falló notificación al backend para {record.pipeline_type}: {carga_id}")
                logger.warning(f"⚠️ El procesamiento fue exitoso, pero el backend no fue notificado")
                
        except Exception as e:
            logger.error(f"❌ Error notificando completion al backend: {e}")
            logger.warning(f"⚠️ El procesamiento fue exitoso, pero falló la notificación al backend")

    async def notify_backend_error(self, carga_id: str, pipeline_type: str, error_details: Dict[str, Any], record: RecordType) -> None:
        """
        Notifica al backend que el pipeline falló.
        
        Args:
            carga_id: ID de la carga procesada (UUID original)
            pipeline_type: Tipo de pipeline ("BATCH_CALLING" o "SFTP")
            error_details: Detalles del error
        """
        try:
            logger.info(f"🚨 Notificando error al backend...")
            logger.info(f"🆔 ID de carga con error: {carga_id}")
            logger.info(f"📋 Tipo de pipeline: {pipeline_type}")
            
            # Ejecutar notificación en thread separado
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.backend_service.notify_pipeline_error,
                carga_id,
                pipeline_type,
                error_details,
                record
            )
            
            logger.info(f"✅ Error notificado al backend para {pipeline_type}: {carga_id}")
            
        except Exception as e:
            logger.error(f"❌ Error notificando error al backend: {e}")
        
    async def mark_as_error(self, record: RecordType, error_messages, is_backend_mode: bool, original_id: str = None) -> None:
        """
        Marca un registro como error.
        
        Args:
            record: Registro de log (LogRecord o BatchRecord)
            error_messages: Mensaje de error (str) o lista de mensajes (List[str])
            is_backend_mode: True si es batch, False si es SFTP
            original_id: ID original para actualizar (opcional)
        """
        end_time = datetime.now(timezone.utc)
        
        # Normalizar errores a lista
        if isinstance(error_messages, str):
            errors_list = [error_messages]
        elif isinstance(error_messages, list):
            errors_list = error_messages
        else:
            errors_list = [str(error_messages)]
        
        # Limitar número de errores
        max_errors = 100
        if len(errors_list) > max_errors:
            truncated_errors = errors_list[:max_errors]
            truncated_errors.append(f"... y {len(errors_list) - max_errors} errores más (truncado)")
            errors_list = truncated_errors
        
        # Determinar tipo y ID
        record_type = "BATCH_CALLING" if is_backend_mode else "SFTP"
        update_id = original_id if original_id else record.id
        
        # Actualizar estado en Firestore
        self.firestore_service.update_log_status(
            update_id, 
            StatusType.ERROR,
            is_backend=is_backend_mode,
            fecha_fin=end_time.isoformat(),
            errores=errors_list,
            pipeline_type=PipelineType.TRANSFORMATION.value 
        )
        
        # Notificar error al backend
        await self.notify_backend_error(
            update_id,
            record_type,
            {
                "errores": errors_list,
                "error_count": len(errors_list),
                "fecha_fin": end_time.isoformat(),
                "pipeline_stage": "error_handling",
                "error_type": "processing_error"
            }
        )
        
        logger.error(f"❌ Archivo {update_id} ({record_type}) marcado como ERROR con {len(errors_list)} mensajes")
    
    async def cleanup(self):
        """Limpia recursos y cierra conexiones."""
        try:
            if self.firestore_service:
                self.firestore_service.disconnect()
            
            if self.gcs_service:
                await self.gcs_service.disconnect()
            
            if self.end_time is None:
                self.end_time = datetime.now(timezone.utc)
            
            if self.start_time:
                duration = (self.end_time - self.start_time).total_seconds()
                logger.info(f"🏁 Pipeline finalizado. Duración total: {duration:.2f} segundos")
                
        except Exception as e:
            logger.error(f"❌ Error en cleanup: {e}")