"""
Servicio para comunicación con el backend API usando Google Cloud Authentication.
"""
from datetime import datetime
import requests
import google.auth.transport.requests
from google.oauth2 import id_token
from typing import Optional, Dict, Any
from src.utils.logger import get_logger
from src.config import get_backend_config, get_config

logger = get_logger(__name__)

class BackendApiService:
    """Servicio para comunicación con el backend API con autenticación Google Cloud."""
    
    def __init__(self):
        backend_config = get_backend_config()
        self.backend_url = backend_config.service_url

        # Preparar autenticación
        self.auth_request = google.auth.transport.requests.Request()
        
        logger.info(f"🔧 Backend API Service inicializado")
        logger.info(f"🌐 Backend URL: {self.backend_url}")
        
    def _get_authenticated_headers(self) -> Dict[str, str]:
        """
        Obtiene headers con token de autenticación de Google Cloud.
        
        Returns:
            Dict con headers incluyendo Authorization
        """
        try:
            # Generar Token de ID usando la URL del backend como audience
            id_token_jwt = id_token.fetch_id_token(
                self.auth_request, 
                audience=self.backend_url
            )
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {id_token_jwt}",
                "User-Agent": "Zenta-Pipeline/1.0"
            }
            
            logger.debug("🔑 Token de autenticación generado exitosamente")
            return headers
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo token de autenticación: {e}")
            raise

    def notify_pipeline_completion(self, carga_id: str, pipeline_type: str, record) -> bool:
        """
        Notifica al backend que el pipeline se completó exitosamente.
        
        Args:
            carga_id: ID de la carga procesada (UUID)
            pipeline_type: Tipo de pipeline ("BATCH_CALLING" o "SFTP")
            stats: Estadísticas del procesamiento
            
        Returns:
            bool: True si la notificación fue exitosa
        """
        try:
            endpoint = f"{self.backend_url}/{get_backend_config().endpoint_batch_calling}"
            fecha_actual = datetime.now()
            fecha_str = fecha_actual.strftime("%d%m%Y")
            if pipeline_type == "BATCH_CALLING":
                payload = {
                    "carga_id": carga_id,
                    "agent_id": record.agent_id,
                    "call_name": record.call_name,
                    "agent_phone_number_id": record.agent_phone_number_id
                }
            else: 
                payload = {
                    "carga_id": carga_id,
                    "agent_id": get_backend_config().payload_agent,
                    "call_name": f"{fecha_str}_{get_backend_config().payload_callname}",
                    "agent_phone_number_id": get_backend_config().payload_agent_phone_number_id
                }
            
            print("="*100)
            print("Payload notificación backend: ", payload)
            print("="*100)

            logger.info(f"🌐 Notificando al backend completion de carga: {carga_id}")
            logger.info(f"📡 Endpoint: {endpoint}")
            logger.debug(f"📋 Payload: {payload}")
            
            # Obtener headers con autenticación
            headers = self._get_authenticated_headers()
            # Realizar solicitud POST
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=payload
            )
            
            logger.info(f"📡 Respuesta del backend: {response.status_code}")
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Backend notificado exitosamente para carga {carga_id}")
                response_data = response.json()
                logger.debug(f"📄 Respuesta: {response_data}")
                return True
            else:
                logger.error(f"❌ Error del backend ({response.status_code}): {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout notificando al backend para carga {carga_id} (>{self.timeout}s)")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Error de conexión con el backend para carga {carga_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"📄 Respuesta del servidor: {e.response.text}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error inesperado notificando al backend para carga {carga_id}: {e}")
            logger.exception("Detalles del error:")
            return False
    
    def test_connection(self) -> bool:
        """
        Prueba la conexión con el backend.
        
        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            endpoint = f"{self.backend_url}/health"  # O tu endpoint de health check
            
            headers = self._get_authenticated_headers()
            
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Conexión con backend exitosa")
                return True
            else:
                logger.warning(f"⚠️ Backend respondió con código: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error probando conexión con backend: {e}")
            return False