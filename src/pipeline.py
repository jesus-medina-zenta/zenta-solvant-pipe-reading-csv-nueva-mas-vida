"""
Lógica principal del pipeline ETL.
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from src.config import init_config
from src.enums.status import PipelineType, StatusType
from src.models.data_models import DataRecord
from src.models.log_record import LogRecord
from src.services.firestore_service import FirestoreService
from src.services.gcs_service import CloudStorageService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Pipeline:
    """
    Pipeline principal para procesamiento ETL.
    """
    
    def __init__(self):
        """Inicializa el pipeline con los servicios necesarios."""
        self.firestore_service = FirestoreService()
        self.gcs_service = CloudStorageService()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
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
                
                # Obtener registros pendientes de Firestore
                pending_logs = self.firestore_service.get_pending_logs()
                
                if not pending_logs:
                    logger.info("📭 No hay archivos pendientes para procesar")
                    return True
                
                logger.info(f"📋 Procesando {len(pending_logs)} archivos pendientes")
                
                # Procesar cada archivo pendiente
                processed_count = 0
                error_count = 0
                
                for log_record in pending_logs:
                    try:
                        success = await self.process_single_file(log_record)
                        if success:
                            processed_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        logger.error(f"❌ Error procesando archivo {log_record.id}: {e}")
                        error_count += 1
                
                # Resumen final
                logger.info(f"✅ Pipeline completado: {processed_count} exitosos, {error_count} errores")
                return error_count == 0
                
            except Exception as e:
                logger.exception(f"❌ Error crítico en el pipeline: {e}")
                return False
            finally:
                await self.cleanup()
        
    async def process_single_file(self, log_record: LogRecord) -> bool:
        """
        Procesa un solo archivo CSV.
        
        Args:
            log_record: Registro de log del archivo a procesar
            
        Returns:
            bool: True si el procesamiento fue exitoso
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"📁 Procesando archivo: {log_record.id}")
        
        try:
            # Actualizar estado a PROCESANDO y cambiar pipeline_type 
            self.firestore_service.update_log_status(
                log_record.id, 
                StatusType.PROCESANDO,
                fecha_inicio=start_time.isoformat(),
                pipeline_type=PipelineType.TRANSFORMATION.value
            )
            
            # 1. Extraer datos del CSV en GCS
            raw_data = await self.extract_from_gcs(log_record.csv_generado)
            if not raw_data:
                error_msg = "No se pudieron extraer datos del CSV"
                await self.mark_as_error(log_record, error_msg)
                return False
            
            logger.info(f"📖 Extraídos {len(raw_data)} registros del CSV")
            
            # 2. Transformar datos (ahora retorna tupla con errores)
            transformed_data, transformation_errors = await self.transform_data(raw_data)
            
            if not transformed_data:
                error_msg = "Error en la transformación de datos - no se pudieron procesar registros"
                # Agregar errores específicos de transformación
                all_errors = [error_msg] + transformation_errors
                await self.mark_as_error(log_record, all_errors)
                return False
            
            logger.info(f"🔄 Transformados {len(transformed_data)} registros")
            
            # 3. Cargar datos transformados en Firestore
            save_success = self.firestore_service.save_transformed_records(transformed_data, log_record.id)
            if not save_success:
                error_msg = "Error guardando datos transformados en Firestore"
                all_errors = [error_msg] + transformation_errors if transformation_errors else [error_msg]
                await self.mark_as_error(log_record, all_errors)
                return False
            
            # 4. Actualizar estado a COMPLETADO con información completa
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            # Preparar datos de actualización
            update_data = {
                "fecha_fin": end_time.isoformat(),
                "duracion_segundos": duration,
                "registros_transformados": len(transformed_data),
                "registros_cargados": len(transformed_data),
                "pipeline_type": PipelineType.TRANSFORMATION.value
            }
            
            if transformation_errors:
                update_data["errores"] = transformation_errors
                logger.warning(f"⚠️ Procesamiento completado con {len(transformation_errors)} errores de transformación")
            
            # Actualizar estado
            self.firestore_service.update_log_status(
                log_record.id,
                StatusType.PARSEADO,
                **update_data
            )
            
            logger.info(f"✅ Archivo {log_record.id} procesado exitosamente en {duration:.2f}s")
            logger.info(f"📊 Estadísticas: {len(raw_data)} extraídos, {len(transformed_data)} transformados, {len(transformed_data)} cargados")
            
            if transformation_errors:
                logger.info(f"⚠️ {len(transformation_errors)} registros fallaron en la transformación")
            
            return True
            
        except Exception as e:
            logger.exception(f"❌ Error procesando archivo {log_record.id}: {e}")
            await self.mark_as_error(log_record, [f"Error crítico en procesamiento: {str(e)}"])
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

    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> Tuple[List[DataRecord], List[str]]:
        """
        Transforma los datos extraídos del CSV.
        
        Args:
            raw_data: Datos en bruto del CSV
            
        Returns:
            List[DataRecord]: Datos transformados y validados
        """
        try:
            transformed_data = []
            transformation_errors = []
            
            if not raw_data:
                logger.warning("⚠️ No hay datos para transformar")
                return [], ["No hay datos para transformar"]
            
            # Generar fecha actual en UTC
            fecha_utc = datetime.now(timezone.utc)
            
            logger.info(f"🔄 Iniciando transformación de {len(raw_data)} registros")
            
            for idx, row in enumerate(raw_data):
                try:
                    # Extraer extraction_id del registro actual
                    extraction_id = row.get('extraction_id', '')
                    if not extraction_id:
                        error_msg = f"Fila {idx + 1}: extraction_id faltante"
                        transformation_errors.append(error_msg)
                        continue
                    
                    # Crear el registro usando el método from_dict
                    record = DataRecord.from_dict(
                        data=row,
                        carga_id=extraction_id,
                        fecha_utc=fecha_utc
                    )
                    
                    # Validar que el registro sea válido
                    if record.is_valid():
                        transformed_data.append(record)
                        logger.debug(f"✅ Registro {idx + 1} transformado exitosamente")
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
            
            logger.info(f"📊 Resultados transformación: {success_count}/{total_records} exitosos ({success_rate:.1f}%)")
            
            if transformation_errors:
                logger.warning(f"⚠️ {error_count} errores en transformación:")
                # Mostrar primeros 10 errores para debugging
                sample_errors = transformation_errors[:10]
                for error in sample_errors:
                    logger.warning(f"   - {error}")
                
                if len(transformation_errors) > 10:
                    logger.warning(f"   ... y {len(transformation_errors) - 10} errores más")
            
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
    async def mark_as_error(self, log_record: LogRecord, error_messages) -> None:
        """
        Marca un registro como error.
        
        Args:
            log_record: Registro de log
            error_messages: Mensaje de error (str) o lista de mensajes (List[str])
        """
        end_time = datetime.now(timezone.utc)
        
        # Normalizar errores a lista
        if isinstance(error_messages, str):
            errors_list = [error_messages]
        elif isinstance(error_messages, list):
            errors_list = error_messages
        else:
            errors_list = [str(error_messages)]
        
        # Limitar número de errores para evitar documentos muy grandes
        max_errors = 100
        if len(errors_list) > max_errors:
            truncated_errors = errors_list[:max_errors]
            truncated_errors.append(f"... y {len(errors_list) - max_errors} errores más (truncado)")
            errors_list = truncated_errors
        
        self.firestore_service.update_log_status(
            log_record.id,
            StatusType.ERROR,
            fecha_fin=end_time.isoformat(),
            errores=errors_list,
            pipeline_type=PipelineType.TRANSFORMATION.value 
        )
        
        logger.error(f"❌ Archivo {log_record.id} marcado como ERROR con {len(errors_list)} mensajes")
        
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
