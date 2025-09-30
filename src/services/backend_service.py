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
        self.backend_url = backend_config.backend_service_url

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
            endpoint = f"{self.backend_url}/batchcalls/send-batch-calling"
            fecha_actual = datetime.now()
            fecha_str = fecha_actual.strftime("%d%m%Y")
            if pipeline_type == "BATCH_CALLING":
                payload = {
                    "id_carga": carga_id,
                    "agent_id": record.agent_id,
                    "call_name": record.call_name,
                    "agent_phone_number_id": record.agent_phone_number_id,
                }
            else: 
                payload = {
                    "id_carga": carga_id,
                    "agent_id": get_backend_config().backend_payload_agent,
                    "call_name": f"{fecha_str}_{get_backend_config().backend_payload_callname}",
                    "agent_phone_number_id": get_backend_config().backend_payload_agent_phone_number_id
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
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Backend notificado exitosamente para carga {carga_id}")
                logger.debug(f"📄 Respuesta: {response_data}")
                return True
            
            elif response.status_code == 202:
                # Accepted - procesamiento asíncrono
                logger.info(f"✅ Backend aceptó la notificación para procesamiento asíncrono: {carga_id}")
                return True
            
            else:
                # Error del servidor
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
    
    def notify_pipeline_error(self, carga_id: str, pipeline_type: str, error_details: Dict[str, Any]) -> bool:
        """
        Notifica al backend que el pipeline falló.
        
        Args:
            carga_id: ID de la carga procesada
            pipeline_type: Tipo de pipeline
            error_details: Detalles del error
            
        Returns:
            bool: True si la notificación fue exitosa
        """
        try:
            endpoint = f"{self.backend_url}/api/pipeline/error"
            
            payload = {
                "carga_id": carga_id,
                "pipeline_type": pipeline_type,
                "status": "error",
                "error_details": error_details,
                "timestamp": error_details.get('fecha_fin')
            }
            
            logger.info(f"🚨 Notificando error al backend para carga: {carga_id}")
            logger.debug(f"📋 Error payload: {payload}")
            
            # Obtener headers con autenticación
            headers = self._get_authenticated_headers()
            
            # Realizar solicitud POST
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 202]:
                logger.info(f"✅ Error notificado al backend para carga {carga_id}")
                return True
            else:
                logger.error(f"❌ Error notificando error al backend ({response.status_code}): {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error notificando error al backend para carga {carga_id}: {e}")
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