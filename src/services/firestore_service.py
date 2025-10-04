from typing import Optional, List
from google.cloud import firestore
from src.enums.status import StatusType
from src.models.batch_record import BatchRecord
from src.models.log_record import LogRecord
from src.models.data_models import DataRecord
from src.utils.date_id import DateIdUtils
from src.utils.logger import get_logger
from src.config import get_firestore_config
import os
from dotenv import load_dotenv
load_dotenv()

logger = get_logger(__name__)

class FirestoreService:
    def __init__(self):
        self.client: Optional[firestore.Client] = None
        self.firestore_config = get_firestore_config()
        self.project_id = self.firestore_config.project_id
        self.collection = self.firestore_config.collection
        self.logs_collection = self.firestore_config.logs_collection
        self.database = self.firestore_config.database
        self.batch_collection = self.firestore_config.batch_collection
        self.is_connected = False

    def connect(self) -> bool:
        if self.is_connected and self.client:
            return True
            
        try:
            if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                logger.warning("GOOGLE_APPLICATION_CREDENTIALS no está configurado.")
            
            logger.info("Conectando a Firestore")
            self.client = firestore.Client(
                project=self.project_id, 
                database=self.database
            )
            
            # Validar conexión real
            self.client.collection(self.collection).limit(1).get()
            
            self.is_connected = True
            logger.info("Conexión establecida exitosamente")
            return True
        except Exception as e:
            logger.error("Error conectando a Firestore: %s", e, exc_info=True)
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        if self.client:
            self.client = None
            self.is_connected = False
            logger.info("Conexión a Firestore cerrada")

    def get_pending_logs(self) -> List[LogRecord]:
        """
        Obtiene todos los registros de log con estado PENDIENTE.
        
        Returns:
            List[LogRecord]: Lista de registros pendientes
        """
        try:
            logger.info("🔍 Buscando registros pendientes en Firestore...")
            
            # Consultar registros con status PENDIENTE
            query = self.client.collection(self.logs_collection).where(
                "status", "==", StatusType.PENDIENTE.value
            )
            
            docs = query.get()
            pending_logs = []
            
            for doc in docs:
                try:
                    data = doc.to_dict()
                    log_record = LogRecord(**data)
                    pending_logs.append(log_record)
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando documento {doc.id}: {e}")
            
            logger.info(f"📋 Encontrados {len(pending_logs)} registros pendientes")
            return pending_logs
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo registros pendientes: {e}")
            return []

    def get_batch_record_by_id(self, batch_id: str) -> Optional[BatchRecord]:
        """
        Obtiene un registro de batch por su ID.
        
        Args:
            batch_id: ID del batch a buscar
            
        Returns:
            List[BatchRecord]: Lista de registros pendientes
        """
        try:
            logger.info(f"🔍 Buscando archivo: {batch_id} en Firestore: {self.batch_collection}")
            doc_ref = self.client.collection(self.batch_collection).document(batch_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                batch_record = BatchRecord.from_firestore_dict(data)
                logger.info(f"✅ Archivo encontrado: {batch_id}")
                return batch_record
            else:
                logger.warning(f"⚠️ No se encontró el archivo con ID: {batch_id}")
                return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo archivo {batch_id}: {e}")
            return None

        
    def update_log_status(self, log_id: str, status: StatusType, is_backend: bool = False, **kwargs) -> bool:
        """
        Actualiza el estado de un registro de log.
        
        Args:
            log_id: ID del log a actualizar
            status: Nuevo estado
            is_backend: Si True, actualiza en la colección batch, si False en logs_collection
            **kwargs: Campos adicionales a actualizar
            
        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            # Determinar qué colección usar según el parámetro is_backend
            collection_name = self.batch_collection if is_backend else self.logs_collection
            
            logger.info(f"📝 Actualizando log {log_id} en colección: {collection_name}")
            logger.info(f"📝 Nuevo estado: {status}")
            
            doc_ref = self.client.collection(collection_name).document(log_id)
            
            # Adaptar el formato del status según la colección
            if is_backend:
                # Para batch, usar strings en minúsculas y mapear estados
                status_value = status.value.lower() if hasattr(status, 'value') else str(status).lower()
                
                # Mapear algunos estados específicos para batch
                status_mapping = {
                    "pendiente": "pendiente",
                    "procesando": "procesando", 
                    "parseado": "completado",  # PARSEADO se convierte en COMPLETADO para batch
                    "error": "error"
                }
                status_value = status_mapping.get(status_value, status_value)
                
            else:
                # Para logs SFTP, usar el valor original del enum
                status_value = status.value if hasattr(status, 'value') else str(status)
            
            update_data = {
                "status": status_value,
                "updated_at": firestore.SERVER_TIMESTAMP,
                **kwargs
            }
            
            logger.info(f"📝 Datos a actualizar: {list(update_data.keys())}")
            
            doc_ref.update(update_data)
            
            collection_type = "batch" if is_backend else "logs"
            logger.info(f"✅ Log {log_id} actualizado a estado '{status_value}' en colección {collection_type}")
            
            # Log adicional si hay errores
            if "errores" in kwargs and kwargs["errores"]:
                error_count = len(kwargs["errores"])
                logger.info(f"📝 Se registraron {error_count} errores en el log")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error actualizando log {log_id}: {e}")
            logger.exception("Detalles del error:")
            return False

    def save_transformed_records(self, records: list, log_id: str, is_batch_calling: bool = False):
        """
        Guarda registros transformados en Firestore.
        """
        try:
            logger.info(f"💾 Guardando {len(records)} registros en colección '{self.collection}'")
            logger.info(f"📋 Tipo: {'Batch Calling' if is_batch_calling else 'SFTP'}, Log ID original: {log_id}")
            
            # ✅ USAR servicio centralizado para limpiar fechas duplicadas
            clean_log_id = DateIdUtils.clean_id_for_firestore_document(log_id)
            logger.info(f"🧹 Log ID limpio: {clean_log_id}")
            
            collection_ref = self.client.collection(self.collection)
            
            BATCH_SIZE = 500
            total_saved = 0
            
            # Procesar en chunks
            for chunk_idx in range(0, len(records), BATCH_SIZE):
                chunk = records[chunk_idx:chunk_idx + BATCH_SIZE]
                chunk_number = (chunk_idx // BATCH_SIZE) + 1
                
                logger.info(f"📦 Procesando chunk {chunk_number}: {len(chunk)} registros")
                
                batch = self.client.batch()
                
                for idx, record in enumerate(chunk):
                    try:
                        if isinstance(record, DataRecord):
                            record_dict = record.model_dump(mode="json")
                            
                            # ID del documento con sufijo
                            global_record_idx = chunk_idx + idx + 1
                            firestore_doc_id = f"{clean_log_id}_{global_record_idx}"
                            
                            # USAR servicio centralizado para limpiar ID interno
                            clean_internal_id = DateIdUtils.extract_pure_uuid(record.id)
                            record_dict["id"] = clean_internal_id
                            
                            logger.debug(f"📝 Documento {global_record_idx}: {firestore_doc_id} → id: {clean_internal_id}")
                            
                        else:
                            logger.error(f"❌ Tipo de registro no válido: {type(record)}")
                            continue
                        
                        # Agregar metadatos
                        record_dict["processed_at"] = firestore.SERVER_TIMESTAMP
                        record_dict["source_type"] = "batch_calling" if is_batch_calling else "sftp"
                        
                        # Crear referencia al documento
                        doc_ref = collection_ref.document(firestore_doc_id)
                        batch.set(doc_ref, record_dict)
                        
                    except Exception as e:
                        logger.error(f"❌ Error preparando registro {idx}: {e}")
                        continue
                
                # Ejecutar batch write
                try:
                    batch.commit()
                    total_saved += len(chunk)
                    logger.info(f"✅ Chunk {chunk_number} guardado: {len(chunk)} registros")
                except Exception as e:
                    logger.error(f"❌ Error guardando chunk {chunk_number}: {e}")
                    raise
            
            logger.info(f"✅ {total_saved} registros guardados exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error guardando registros: {e}")
        return False

    def save_log_record(self, log: LogRecord):
        """Guarda o actualiza un registro de log."""
        try:
            doc_ref = self.client.collection(self.logs_collection).document(log.id)
            doc_ref.set(log.model_dump(mode="json"))
            logger.info(f"✅ Log guardado con id {log.id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando log: {e}")
            return False