"""
Utilidades para manejo de fechas e IDs.
Centraliza la lógica de validación y limpieza de IDs con fechas.
"""
import re
from datetime import datetime
from typing import Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DateIdUtils:
    """Utilidades para manejo de fechas e IDs."""
    
    @staticmethod
    def is_date_part(part: str) -> bool:
        """
        Verifica si una parte del ID es una fecha en formato DDMMYYYY.
        
        Args:
            part: Parte del ID a verificar
            
        Returns:
            bool: True si es una fecha válida
            
        Examples:
            "03102025" → True (03/10/2025)
            "12345678" → False (no es fecha válida)
            "abcd1234" → False (contiene letras)
        """
        if not part or len(part) != 8 or not part.isdigit():
            return False
        
        # Validar formato DDMMYYYY
        try:
            day = int(part[:2])
            month = int(part[2:4])
            year = int(part[4:8])
            
            # Validar rangos básicos
            if not (1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2035):
                return False
                
            # Validación adicional de fecha válida
            try:
                datetime.strptime(part, "%d%m%Y")
                return True
            except ValueError:
                return False
                
        except (ValueError, IndexError):
            return False
    
    @staticmethod
    def remove_duplicate_dates(id_with_dates: str) -> str:
        """
        Remueve fechas duplicadas del ID, manteniendo solo la primera.
        
        Args:
            id_with_dates: ID que puede contener fechas duplicadas
            
        Returns:
            str: ID con fechas duplicadas removidas
            
        Examples:
            "03102025-03102025-uuid-parts" → "03102025-uuid-parts"
            "03102025-uuid-parts" → "03102025-uuid-parts"
        """
        if not id_with_dates:
            return id_with_dates
        
        parts = id_with_dates.split('-')
        
        # Filtrar fechas duplicadas (mantener solo la primera)
        cleaned_parts = []
        found_date = False
        
        for part in parts:
            if DateIdUtils.is_date_part(part):
                if not found_date:
                    cleaned_parts.append(part)  # Mantener primera fecha
                    found_date = True
                # Saltar fechas adicionales
            else:
                cleaned_parts.append(part)  # Mantener partes no-fecha
        
        result = '-'.join(cleaned_parts)
        logger.debug(f"🧹 Limpiando fechas duplicadas: '{id_with_dates}' → '{result}'")
        return result
    
    @staticmethod
    def extract_pure_uuid(id_with_date: str) -> str:
        """
        Extrae UUID puro sin fechas ni sufijos.
        
        Args:
            id_with_date: ID que puede contener fechas y sufijos
            
        Returns:
            str: UUID puro sin fechas ni sufijos
            
        Examples:
            "03102025-uuid-parts-here_2" → "uuid-parts-here"
            "uuid-parts-here" → "uuid-parts-here"
        """
        if not id_with_date:
            return id_with_date
        
        parts = id_with_date.split('-')
        
        # Buscar primera parte que NO sea fecha
        uuid_parts = []
        for part in parts:
            if not DateIdUtils.is_date_part(part):
                uuid_parts.append(part)
        
        # Si la última parte tiene sufijo (_1, _2), quitarlo
        if uuid_parts and '_' in uuid_parts[-1]:
            uuid_parts[-1] = uuid_parts[-1].split('_')[0]
        
        result = '-'.join(uuid_parts)
        logger.debug(f"🧹 Extrayendo UUID puro: '{id_with_date}' → '{result}'")
        return result
    
    @staticmethod
    def extract_date_from_id(id_with_date: str) -> Optional[str]:
        """
        Extrae la fecha de un ID si existe.
        
        Args:
            id_with_date: ID que puede contener fecha
            
        Returns:
            str|None: Fecha en formato DDMMYYYY o None si no se encuentra
            
        Examples:
            "03102025-uuid-parts" → "03102025"
            "uuid-parts-only" → None
        """
        if not id_with_date:
            return None
        
        parts = id_with_date.split('-')
        
        for part in parts:
            if DateIdUtils.is_date_part(part):
                return part
        
        return None
    
    @staticmethod
    def generate_today_prefix() -> str:
        """
        Genera el prefijo de fecha para hoy en formato DDMMYYYY.
        
        Returns:
            str: Fecha actual en formato DDMMYYYY
            
        Examples:
            → "03102025" (para 3 de octubre de 2025)
        """
        return datetime.now().strftime("%d%m%Y")
    
    @staticmethod
    def validate_uuid_format(uuid_str: str) -> bool:
        """
        Valida si una cadena tiene formato UUID válido.
        
        Args:
            uuid_str: Cadena a validar
            
        Returns:
            bool: True si tiene formato UUID válido
            
        Examples:
            "550e8400-e29b-41d4-a716-446655440000" → True
            "not-a-uuid" → False
        """
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(uuid_str))
    
    @staticmethod
    def clean_id_for_backend(carga_id: str) -> str:
        """
        Limpia un ID para envío al backend (solo UUID puro).
        
        Args:
            carga_id: ID completo que puede contener fecha y sufijos
            
        Returns:
            str: UUID limpio para el backend
            
        Examples:
            "03102025-uuid-parts_1" → "uuid-parts"
            "uuid-parts" → "uuid-parts"
        """
        return DateIdUtils.extract_pure_uuid(carga_id)
    
    @staticmethod
    def clean_id_for_firestore_document(log_id: str) -> str:
        """
        Limpia un ID para usar como documento en Firestore (quita fechas duplicadas).
        
        Args:
            log_id: ID que puede tener fechas duplicadas
            
        Returns:
            str: ID limpio para documento Firestore
            
        Examples:
            "03102025-03102025-uuid-parts" → "03102025-uuid-parts"
        """
        return DateIdUtils.remove_duplicate_dates(log_id)