from typing import Optional, List
from google.cloud import firestore
from src.enums.status import StatusType
from src.models.log_record import LogRecord
from src.models.data_models import DataRecord
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

    def update_log_status(self, log_id: str, status: StatusType, **kwargs) -> bool:
        """
        Actualiza el estado de un registro de log.
        
        Args:
            log_id: ID del log a actualizar
            status: Nuevo estado
            **kwargs: Campos adicionales a actualizar
            
        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            doc_ref = self.client.collection(self.logs_collection).document(log_id)
            
            update_data = {
                "status": status.value,
                **kwargs
            }
            
            doc_ref.update(update_data)
            logger.info(f"✅ Log {log_id} actualizado a estado {status.value}")
            
            # Log adicional si hay errores
            if "errores" in kwargs and kwargs["errores"]:
                error_count = len(kwargs["errores"])
                logger.info(f"📝 Se registraron {error_count} errores en el log")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error actualizando log {log_id}: {e}")
            return False

    def save_transformed_records(self, records: list, log_id: str):
        """Guarda registros transformados en Firestore."""
        try:
            collection_ref = self.client.collection(self.collection)
            batch = self.client.batch()
            
            for idx, record in enumerate(records):
                if isinstance(record, DataRecord):
                    record_dict = record.model_dump(mode="json")
                else:
                    record_dict = record
                
                # Agregar referencia al log original
                record_dict["log_id"] = log_id
                record_dict["processed_at"] = firestore.SERVER_TIMESTAMP
                
                doc_id = f"{log_id}_{idx+1}"
                doc_ref = collection_ref.document(doc_id)
                batch.set(doc_ref, record_dict)
            
            batch.commit()
            logger.info(f"✅ {len(records)} registros guardados en la colección '{self.collection}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error guardando registros transformados: {e}")
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