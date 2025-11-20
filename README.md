#  Pipeline de Procesamiento CSV - Zenta Solvant

**Empresa:** Zenta  
**Versión:** 1.0  
**Estado:** Production Ready 

Pipeline ETL asíncrono para procesamiento de archivos CSV con datos de clientes, diseñado para integrarse con sistemas SFTP y Backend API. Desplegado en Google Cloud Run Jobs con orquestación completa en Firestore.

##  Propósito

Este pipeline transforma datos de clientes desde archivos CSV (provenientes de SFTP o carga manual) hacia una colección de Firestore, aplicando validaciones estrictas de RUT y teléfonos, con trazabilidad completa y notificaciones al backend para continuidad del flujo de negocio

##  Arquitectura del Sistema

### Flujos de Datos

El pipeline soporta **2 flujos de entrada**:

#### 1️ **Flujo SFTP (Automático)**
```
Cloud Scheduler → Cloud Run Job → SFTP → Parser TXT → CSV → GCS → Pipeline → Firestore
```
- Ejecución programada mediante Cloud Scheduler
- Descarga archivos TXT de ancho fijo desde SFTP
- Parser convierte formato fixed-width a CSV
- CSV almacenado en Google Cloud Storage
- Pipeline procesa y valida datos
- Resultados en Firestore con estado `PENDIENTE` → `PROCESANDO` → `PARSEADO`

#### 2️ **Flujo Backend API (Manual)**
```
Frontend → BFF → Backend API → GCS → Cloud Run Job (con batch_id) → Pipeline → Firestore
```
- Usuario sube CSV desde frontend
- Backend guarda CSV en GCS
- Backend registra metadata en Firestore (`batch_collection`)
- Backend dispara Cloud Run Job con `batch_id` como parámetro
- Pipeline procesa archivo específico
- Notifica al backend para continuar flujo

### Estructura del Proyecto

```
📦 zenta-solvant-pipe-reading-csv/
├──  src/
│   ├── main.py                    # Punto de entrada (acepta batch_id como arg)
│   ├── config.py                  # Configuración con Pydantic Settings
│   ├── pipeline.py                # Lógica ETL principal
│   ├──  models/
│   │   ├── data_models.py         # DataRecord con validaciones estrictas
│   │   ├── batch_record.py        # BatchRecord para flujo backend
│   │   ├── log_record.py          # LogRecord para flujo SFTP
│   │   └── metadata_user.py       # MetadataUser (datos del cliente)
│   ├──  services/
│   │   ├── firestore_service.py   # Gestión de Firestore (logs, batch, registros)
│   │   ├── gcs_service.py         # Lectura de CSV desde GCS
│   │   ├── backend_service.py     # Notificaciones al backend
│   │   └── base_service.py        # Servicio base abstracto
│   ├──  utils/
│   │   ├── logger.py              # Logging estructurado
│   │   ├── validators.py          # Validadores personalizados
│   │   └── date_id.py             # Utilidades para manejo de IDs
│   └──  enums/
│       └── status.py              # Estados del pipeline (PENDIENTE, PROCESANDO, etc.)
├──  Dockerfile                  # Containerización para Cloud Run
├──  deploy/google/cloudbuild.yaml # CI/CD con Cloud Build
├──  scripts/                    # Scripts de deployment y testing
└──  tests/                      # Suite de tests Falta implementación
```

### Componentes Clave

####  **Servicios**
- **FirestoreService**: Maneja 3 colecciones (logs SFTP, batch calling, registros procesados)
- **GCSService**: Lee archivos CSV desde Google Cloud Storage con manejo async
- **BackendService**: Notifica completitud/errores con autenticación Google Cloud
- **BaseService**: Patrón abstracto para servicios conectables

####  **Modelos de Datos**
- **DataRecord**: Validación Pydantic estricta (RUT obligatorio, teléfonos con formato +56)
- **BatchRecord**: Metadata de archivos batch (call_name, agent_id, file_path)
- **LogRecord**: Trazabilidad de procesos SFTP (timestamps, duraciones, errores)
- **MetadataUser**: Datos completos del cliente (15 campos: queue, RUT, email, etc.)

####  **Utilidades**
- **Logger**: Logging estructurado con contexto de operaciones
- **DateIdUtils**: Limpieza de IDs para Firestore y backend (previene duplicados por timestamp)
- **Validators**: Validación de RUT chileno, formato de teléfonos

##  Funcionamiento del Pipeline

### Proceso ETL Completo

#### 1. **Inicialización** (`Pipeline.__init__`)
- Detecta modo de operación: `batch_id` presente → Backend, ausente → SFTP
- Inicializa servicios: Firestore, GCS, Backend
- Configura logging con contexto del modo

#### 2. **Extracción** (`extract_from_gcs`)
```python
CSV en GCS → Lectura asíncrona → List[Dict[str, Any]]
```
- Lee archivo CSV desde URL de Google Cloud Storage
- Parsea CSV a lista de diccionarios
- Valida existencia del archivo
- **Input**: `gs://bucket/path/file.csv`
- **Output**: Lista de registros crudos

#### 3. **Transformación** (`transform_data`)
```python
Raw Data → Validación Pydantic → DataRecord → List válidos + List errores
```
**Proceso por registro:**
- Parseo de campos desde CSV o TXT (ancho fijo)
- **Validación crítica de RUT**: No vacío, formato chileno válido
- **Validación crítica de teléfonos**: 
  - `phone_number`: obligatorio, formato `+56XXXXXXXXX` (9 dígitos)
  - `phone_number_2`: opcional, mismo formato
  - Intercambio automático si `phone_number` vacío pero `phone_number_2` válido
- Creación de `MetadataUser` con 15 campos (queue, email, amounts, dates, etc.)
- Generación de `track_id` único (UUID v4)
- Conversión de fechas GMT a formato ISO

**Lógica especial:**
- **Batch Calling**: ID final = `ddmmyyyy-uuid_numero`
- **SFTP**: ID final = `uuid` (extrae parte después del guión)

**Retorno:**
- `List[DataRecord]`: Registros válidos
- `List[str]`: Mensajes de error detallados

#### 4. **Carga** (`save_transformed_records`)
```python
List[DataRecord] → Firestore Batch Write → Colección: registros_sftp
```
- Procesa en chunks de 500 registros (límite Firestore batch)
- Limpia IDs con `DateIdUtils` para prevenir duplicados
- Genera ID de documento: `{cleaned_log_id}_{index}`
- Añade metadata: `processed_at`, `source_type` (batch_calling/sftp)
- Serialización JSON-safe con Pydantic

#### 5. **Actualización de Estado**
```python
Firestore Update → Status: PENDIENTE → PROCESANDO → PARSEADO/ERROR
```
- Estado inicial: `PENDIENTE`
- Durante proceso: `PROCESANDO` (con `fecha_inicio`)
- Éxito: `PARSEADO` (con estadísticas: `registros_transformados`, `duracion_segundos`)
- Error: `ERROR` (con lista de errores limitada a 100 mensajes)

#### 6. **Notificación al Backend** (`notify_backend_completion`)
```python
HTTP POST → Backend API → Continúa flujo de negocio
```
**Payload según tipo:**
- **Batch Calling**:
  ```json
  {
    "carga_id": "uuid-limpio",
    "agent_id": "xxx",
    "call_name": "batch_name",
    "agent_phone_number_id": "yyy"
  }
  ```
- **SFTP**:
  ```json
  {
    "carga_id": "uuid-limpio",
    "agent_id": "config.agent",
    "call_name": "ddmmyyyy_config.callname",
    "agent_phone_number_id": "config.phone_id"
  }
  ```

**Autenticación**: Google Cloud ID Token con audience = backend URL

### Manejo de Errores

#### Estrategia de Errores por Nivel

**Errores de Validación (registro individual)**:
- Capturados en `transform_data`
- Registro descartado, error agregado a lista
- Pipeline continúa con siguientes registros
- Errores detallados en Firestore y logs

**Errores Críticos (archivo completo)**:
- Sin datos extraídos: `mark_as_error` con estado `ERROR`
- Transformación sin resultados válidos: `ERROR` con detalles
- Fallo en GCS, Firestore: `ERROR` + notificación backend
- Pipeline termina, no procesa más

**Límites de Errores**:
- Máximo 100 mensajes de error por archivo
- Previene overflow en Firestore documents

### Colecciones de Firestore

| Colección | Propósito | Estados |
|-----------|-----------|---------|
| `logs_collection` | Trazabilidad SFTP | PENDIENTE → PROCESANDO → PARSEADO/ERROR |
| `batch_collection` | Metadata batch calling | pendiente → procesando → completado/error |
| `registros_sftp` | Datos transformados finales | N/A (solo inserción) |

**Nota**: Ambos flujos escriben en `registros_sftp` con field `source_type` para diferenciación.

##  Validaciones Críticas

### Validación de RUT
- **Obligatorio**: No puede ser vacío
- **Formato**: Con o sin dígito verificador
- **Limpieza**: Remueve puntos y guiones automáticamente
- **Rechazo**: Registro completo descartado si RUT inválido

### Validación de Teléfonos
- **phone_number**: 
  - Obligatorio
  - Formato: `+56` + 9 dígitos
  - Limpieza: Remueve espacios y guiones
- **phone_number_2**: 
  - Opcional
  - Mismo formato que phone_number
- **Intercambio automático**: Si `phone_number` vacío pero `phone_number_2` válido, se intercambian
- **Rechazo**: Registro descartado si no hay al menos un teléfono válido

### Validación de Metadata
Campos obligatorios en `MetadataUser`:
- `queue`: Cola de procesamiento (4 caracteres, ej: "PRA3")
- `name`: Nombre del cliente (no vacío)
- `paternal_surname`: Apellido paterno
- `rut`: RUT validado

Campos opcionales pero validados:
- `email`: Formato de email, descarta valores como `[object Object]`, `NaN`
- `overdue_amount1`: Debe ser numérico positivo
- `process_date`, `overdue_date1`: Formato de fecha válido

## 🚀 Ejecución

### Modo SFTP (Automático)
```bash
# Sin parámetros - procesa registros pendientes de SFTP
python -m src.main
```

### Modo Backend (Manual con batch_id)
```bash
# Con UUID de batch específico
python -m src.main c10ed9e3-e666-4d41-a75b-e351c080332b
```

### Variables de Entorno Requeridas

```bash
# Firestore
FIRESTORE_PROJECT_ID=znt-solvant-dev
FIRESTORE_DATABASE=znt-solvant-local-db
FIRESTORE_COLLECTION=registros_sftp
FIRESTORE_LOGS_COLLECTION=logs_extraccion_sftp
FIRESTORE_BATCH_COLLECTION=registro_archivos

# Google Cloud Storage
GCS_PROJECT_ID=znt-solvant-dev
GCS_BUCKET_NAME=znt-solvant-dev-csv-files

# Backend API
BACKEND_SERVICE_URL=https://backend.example.com
BACKEND_PAYLOAD_AGENT=agent-id
BACKEND_PAYLOAD_CALLNAME=SFTP_BATCH
BACKEND_PAYLOAD_AGENT_PHONE_NUMBER_ID=phone-id
BACKEND_ENDPOINT_BATCH_CALLING=batch-calling/notify

# Google Cloud Authentication
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json

# Configuración general
LOG_LEVEL=INFO
ENVIRONMENT=dev
```

## 📦 Deployment en Google Cloud Run

### CI/CD Automático con Terraform + GitHub Triggers

El proyecto utiliza **infraestructura como código (Terraform)** con triggers automáticos desde GitHub:

```
Push/Merge a dev → GitHub → Cloud Build Trigger → cloudbuild.yaml → Deploy a GCP
```

**Flujo de deployment:**
1. Developer hace push o merge a rama `dev`
2. GitHub notifica al trigger configurado en GCP
3. Cloud Build ejecuta `deploy/google/cloudbuild.yaml` automáticamente
4. Pipeline completo: build → test → push → deploy
5. Cloud Run Job actualizado en entorno productivo

**Ventajas del enfoque:**
- ✅ Deployment automático sin intervención manual
- ✅ Infraestructura versionada en Terraform
- ✅ Trazabilidad completa de cambios (git commits → deploys)
- ✅ Rollback simple mediante revert de commit
- ✅ Variables de entorno gestionadas por Terraform

### Build y Deploy Manual (Opcional)

```bash
# Deploy manual con cloudbuild.yaml (solo si es necesario)
gcloud builds submit --config deploy/google/cloudbuild.yaml

# Variables de substitución requeridas:
# _REGION: us-central1
# _DOCKER_REPOSITORY: docker-repo-name
# _COMPONENT_NAME: pipe-reading-csv
# _ENV: dev
# _RUN_SERVICE_ACCOUNT_EMAIL: service-account@project.iam.gserviceaccount.com
# ... (resto de variables de entorno)
```

### Configuración del Cloud Build

El `cloudbuild.yaml` incluye 5 pasos:
1. **Instalación de dependencias** (Python 3.9)
2. **Tests** (pendiente de implementación)
3. **Build de imagen Docker** con tag por BUILD_ID
4. **Push a Artifact Registry**
5. **Deploy a Cloud Run Jobs** con variables de entorno

**Nota:** La configuración de Terraform gestiona:
- Cloud Build triggers vinculados a GitHub
- Service accounts y permisos IAM
- Variables de entorno del Cloud Run Job
- Artifact Registry repository
- Networking y seguridad

### Configuración de Cloud Scheduler (Flujo SFTP)

```bash
# Crear job programado para ejecutar cada hora
gcloud scheduler jobs create http pipe-reading-csv-schedule \
  --location=us-central1 \
  --schedule="0 * * * *" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/pipe-reading-csv-dev:run" \
  --http-method=POST \
  --oauth-service-account-email=SERVICE_ACCOUNT@project.iam.gserviceaccount.com
```

## 🧪 Testing (Pendiente de Implementación)

Actualmente el paso de tests en `cloudbuild.yaml` está comentado. Tests recomendados:

```python
# tests/test_pipeline.py
- test_extract_from_gcs()
- test_transform_data_valid_records()
- test_transform_data_invalid_rut()
- test_transform_data_invalid_phone()
- test_save_to_firestore()
- test_backend_notification()

# tests/test_services.py
- test_firestore_connection()
- test_gcs_read_csv()
- test_backend_authentication()
```

## 🔍 Monitoreo y Observabilidad

### Logs Estructurados

El pipeline genera logs detallados en cada etapa:

```
Iniciando pipeline integrado de procesamiento CSV
Parámetro de UUID de destino recibido: {batch_id}
Buscando archivo: {batch_id} en Firestore
Archivo encontrado: {batch_id}
Actualizando log {id} a estado PROCESANDO
Extraídos {n} registros del CSV
Transformados {n} registros
Guardando {n} registros en colección 'registros_sftp'
Procesando chunk {n}: {count} registros
{n} registros guardados exitosamente
Notificando al backend completion de carga
Pipeline ejecutado exitosamente
```

### Métricas Clave

- `registros_extraidos`: Total de registros en CSV
- `registros_transformados`: Registros validados exitosamente
- `registros_cargados`: Registros guardados en Firestore
- `duracion_segundos`: Tiempo total de procesamiento
- `errores`: Lista de errores de validación (max 100)

### Trazabilidad en Firestore

Cada proceso actualiza su documento con:
- `status`: PENDIENTE → PROCESANDO → PARSEADO/ERROR
- `fecha_inicio`, `fecha_fin`: Timestamps UTC
- `duracion_segundos`: Performance metrics
- `pipeline_type`: EXTRACTION o TRANSFORMATION
- `errores[]`: Detalles de fallos por registro

##  Problemas Comunes y Soluciones

### Error: "Archivo no encontrado en GCS"
**Causa**: URL de GCS incorrecta o permisos insuficientes  
**Solución**: Verificar formato `gs://bucket/path/file.csv` y service account con rol `Storage Object Viewer`

### Error: "RUT no puede estar vacío"
**Causa**: Registro con RUT inválido en CSV  
**Solución**: Revisar archivo origen, el registro será descartado automáticamente

### Error: "No se encontró número de teléfono válido"
**Causa**: Ambos teléfonos vacíos o formato inválido  
**Solución**: Corregir datos en CSV, debe tener al menos un teléfono con 9 dígitos

### Error: "Error obteniendo token de autenticación"
**Causa**: GOOGLE_APPLICATION_CREDENTIALS no configurado o inválido  
**Solución**: 
```bash
export GOOGLE_APPLICATION_CREDENTIALS="./service-account-key.json"
gcloud auth application-default login  # Para desarrollo local
```

### Pipeline procesa 0 registros
**Causa**: Sin registros `PENDIENTE` en Firestore  
**Solución**: Verificar que existen registros con `status: "PENDIENTE"` en la colección correspondiente

##  Mejoras Potenciales Identificadas

### 1. **Implementación de Tests**
-  Actualmente sin tests automatizados
-  Recomendación: Agregar pytest con fixtures para Firestore y GCS mocks
-  Prioridad: **ALTA**

### 2. **Retry Logic**
-  No hay reintentos automáticos en fallos transitorios (GCS timeout, Firestore rate limits)
-  Recomendación: Implementar `tenacity` con backoff exponencial
-  Prioridad: **MEDIA**


### 4. **Validación de Duplicados**
-  No verifica si un `id_carga` ya fue procesado
-  Recomendación: Consultar Firestore antes de procesar para evitar reprocesamiento
-  Prioridad: **MEDIA**

### 5. **Límite de Errores Configurable**
-  Hardcoded a 100 errores en `mark_as_error`
-  Recomendación: Mover a configuración (`config.py`)
-  Prioridad: **BAJA**

### 6. **Monitoreo de Performance**
-  Sin métricas de Cloud Monitoring
-  Recomendación: Integrar `google-cloud-monitoring` para alertas
-  Prioridad: **MEDIA**

### 7. **Manejo de Archivos Grandes**
-  Lee todo el CSV en memoria
-  Recomendación: Implementar streaming para archivos > 100MB
-  Prioridad: **BAJA** (depende del tamaño típico)

### 8. **Idempotencia en Firestore**
-  Usa `set()` sin merge, puede sobrescribir datos
-  Recomendación: Usar `set(merge=True)` o verificar existencia previa
-  Prioridad: **MEDIA**

### 9. **Documentación de Modelos**
-  Algunos campos sin descripción clara (ej: `queue_id_cyber`)
-  Recomendación: Documentar significado de negocio de cada campo
-  Prioridad: **BAJA**

### 10. **Circuit Breaker para Backend**
-  Reintentos infinitos si backend está caído
-  Recomendación: Implementar circuit breaker (pybreaker)
-  Prioridad: **MEDIA**

## 📋 Checklist de Deployment

Antes de desplegar a producción:

### Infraestructura (Terraform)
- [ ] Terraform aplicado con triggers de GitHub configurados
- [ ] Rama `dev` protegida con revisión de código obligatoria
- [ ] Service Account con permisos: `Firestore User`, `Storage Object Viewer`, `Cloud Run Invoker`
- [ ] Variables de entorno configuradas en Terraform para Cloud Run Job
- [ ] Artifact Registry repository creado y accesible
- [ ] Networking y políticas de seguridad validadas

### Aplicación
- [ ] Credenciales de backend actualizadas en variables de Terraform
- [ ] Cloud Scheduler configurado (si flujo SFTP activo)
- [ ] Tests ejecutados exitosamente (cuando se implementen)
- [ ] Logs de prueba revisados sin errores críticos
- [ ] Firestore collections creadas con índices apropiados
- [ ] GCS bucket con archivos de prueba validados
- [ ] Backend endpoint disponible y respondiendo
- [ ] Documentación de APIs actualizada

## 📄 Licencia

Este proyecto es propiedad de **Zenta Group**.

---

**Desarrollado por:** Equipo Zenta  
**Contacto:** Para consultas técnicas, revisar logs en Cloud Logging o contactar al equipo de desarrollo.

---

*Documentación generada: Noviembre 2025*
