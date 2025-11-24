import asyncio
import os
import io
import csv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

from google.cloud import storage
from google.cloud.exceptions import NotFound, Forbidden

from src.utils.logger import get_logger

logger = get_logger(__name__)

class CloudStorageService:
    """
    Servicio para manejar exiones y operaciones con Google Cloud Storage.
    """
    
    def __init__(self, project_id: Optional[str] = None, bucket_name: Optional[str] = None):
        """
        Inicializa el servicio de Cloud Storage.
        
        Args:
            project_id: ID del proyecto de Google Cloud
            bucket_name: Nombre del bucket
        """
        self.is_connected = False
        self.client: Optional[storage.Client] = None
        self.project_id = project_id or os.getenv('FIRESTORE_PROJECT_ID', 'znt-solvant-dev')
        self.bucket_name = bucket_name or os.getenv('GCS_BUCKET_NAME', f'{self.project_id}-csv-files')
        self.bucket = None
        
    async def connect(self) -> bool:
        """
        Establece conexión con Cloud Storage.
        
        Returns:
            bool: True si la conexión fue exitosa
        """
        if self.is_connected and self.client:
            return True
            
        try:
            logger.info("Conectando a Cloud Storage...")
            logger.info(f"Project ID: {self.project_id}")
            logger.info(f"Bucket: {self.bucket_name}")
            
            #  Verificar credenciales
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path and not os.path.exists(credentials_path):
                logger.error(f" Archivo de credenciales no existe: {credentials_path}")
                return False
            
            # Crear cliente de Cloud Storage
            if self.project_id:
                self.client = storage.Client(project=self.project_id)
            else:
                self.client = storage.Client()
            
            # Configurar bucket de forma segura
            if self.bucket_name:
                self.bucket = self.client.bucket(self.bucket_name)
            
            self.is_connected = True
            logger.info(" Conexión a Cloud Storage establecida exitosamente")
            return True
            
        except Exception as e:
            logger.error(f" Error conectando a Cloud Storage: {e}")
            logger.error(f" Project ID: {self.project_id}")
            logger.error(f" Bucket Name: {self.bucket_name}")
            logger.error(f" Credentials: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'NO CONFIGURADO')}")
            self.is_connected = False
            return False

    async def read_csv_from_gcs_url(self, gcs_url: str) -> List[Dict[str, Any]]:
        """
        Lee un archivo CSV desde una URL de GCS.
        
        Args:
            gcs_url: URL completa del archivo en GCS (ej: gs://bucket/path/file.csv)
            
        Returns:
            List[Dict[str, Any]]: Lista de registros del CSV
        """
        try:
            # Extraer bucket y path de la URL
            if not gcs_url.startswith('gs://'):
                raise ValueError(f"URL inválida, debe empezar con 'gs://': {gcs_url}")
            
            # Remover 'gs://' y dividir en bucket y path
            path_without_protocol = gcs_url[5:]  # Remover 'gs://'
            parts = path_without_protocol.split('/', 1)
            
            if len(parts) != 2:
                raise ValueError(f"URL mal formateada: {gcs_url}")
            
            bucket_name, blob_path = parts
            logger.info(f" Leyendo CSV desde: {gcs_url}")
            logger.info(f"Bucket: {bucket_name}, Path: {blob_path}")
            
            # Obtener el bucket correcto
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            # Verificar que el archivo existe
            if not blob.exists():
                logger.error(f" Archivo no encontrado en GCS: {gcs_url}")
                return []
            
            # Descargar contenido
            content = blob.download_as_text(encoding='utf-8')
            
            # Leer CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            records = list(csv_reader)
            
            logger.info(f" Leídos {len(records)} registros del CSV")
            return records
            
        except Exception as e:
            logger.error(f" Error leyendo CSV desde GCS: {e}")
            logger.error(f"URL problemática: {gcs_url}")
            return []

    async def disconnect(self) -> None:  
        """Cierra conexión con GCS."""
        if self.client:
            # ✅ Google Cloud Storage client no necesita close() explícito
            self.client = None
            self.bucket = None
            self.is_connected = False
            logger.info(" Conexión a GCS cerrada")
