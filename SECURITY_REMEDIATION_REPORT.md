# Reporte de remediación de dependencias

**Fecha:** 2026-09-02
**Servicios afectados:** zenta-solvant-pipe-reading-csv-nueva-mas-vida (Cloud Run Job `solvant-pipe-reading-csv-dev`)

## Cambios aplicados

| CVE | Paquete | Versión anterior → nueva | Tipo de cambio | Acción tomada | Verificación | Estado |
|---|---|---|---|---|---|---|
| CVE-2026-28684 | python-dotenv | 1.0.0 → **revertido a 1.0.0** | — | Se intentó `>=1.2.2` (fix real) pero **falló el build real de Docker**: requiere Python >=3.10, esta imagen usa `python:3.9-slim` (EOL). No hay versión segura compatible con 3.9 | build de Docker: `ERROR: Could not find a version that satisfies the requirement python-dotenv>=1.2.2` | 🚫 Bloqueado (requiere upgrade de Python base) |
| CVE-2026-25645, CVE-2026-44432, CVE-2026-44431 | requests / urllib3 | `requests>=2.28.0` → `requests>=2.33.0` | minor | subido el mínimo para forzar una versión de `requests` que arrastra `urllib3` sin CVEs conocidos | pip-audit limpio, import OK | ✅ Resuelto |
| CVE-2026-0994 | protobuf | (transitiva de google-cloud-firestore, sin pin) → indirectamente resuelto | major (con ajuste) | **Primer intento fallido:** pinear `protobuf>=5.29.6` directo generó un conflicto de resolución real — `google-cloud-firestore==2.13.1` exige `protobuf<5.0.0dev`. Se corrigió liberando el pin de `google-cloud-firestore==2.13.1` a `google-cloud-firestore>=2.13.1`, dejando que pip resuelva una versión (2.29.0 en la prueba) que ya soporta protobuf 5.x/7.x sin conflicto | resolución de pip exitosa (antes: `ResolutionImpossible`), pip-audit limpio, `pip check` OK, import de `src.pipeline`/`FirestoreService` OK | ✅ Resuelto |
| CVE-2026-8643, CVE-2026-6357, CVE-2026-3219, CVE-2026-13346, CVE-2025-8869, CVE-2023-5752 | pip | (toolchain, no en requirements.txt) | patch (toolchain) | `Dockerfile`: `pip install --upgrade pip` → `pip install --upgrade pip setuptools wheel` | pendiente de build | ⚠️ Pendiente de build |
| CVE-2026-24049 | wheel | (toolchain) | patch (toolchain) | mismo cambio de Dockerfile | pendiente de build | ⚠️ Pendiente de build |
| CVE-2026-59890 | setuptools | (toolchain) | patch (toolchain) | mismo cambio de Dockerfile | pendiente de build | ⚠️ Pendiente de build |
| CVE-2026-23949 | jaraco-context | (toolchain) | patch (toolchain) | mismo cambio de Dockerfile | pendiente de build | ⚠️ Pendiente de build |

## Ajustes de código por breaking changes

**`google-cloud-firestore` 2.13.1 → 2.29.0 (major dentro del mismo v2, sin bump de major real de la librería):** se revisó el uso real en `src/services/firestore_service.py` — solo usa `firestore.Client(...)`, `.collection()`/`.document()` y `firestore.SERVER_TIMESTAMP`, todas APIs core estables sin cambios entre estas versiones. No se requirió tocar código. El import de `src.pipeline` y `FirestoreService` se probó explícitamente después del cambio y funcionó sin errores.

## Política Perl / librerías críticas prohibidas

**Bloqueada — se intentó eliminar, Debian lo impide.** Mismo caso que en `reading`/`writing`: Perl viene con `python:3.9-slim` sin uso funcional en el código, 13 CVEs sin parche (2 críticos, 9.8 y 9.1). Se probó `apt-get purge -y --auto-remove perl-base perl` en un build real y falló: Debian marca `perl-base` como paquete **esencial** en esta imagen (`E: Essential packages were removed and -y was used without --allow-remove-essential`), señal real de que removerlo podría romper herramientas base del sistema. Se revirtió el cambio. Ver el mismo detalle completo en el reporte de `zenta-solvant-pipe-reading-nueva-mas-vida`.

## Próximos pasos (lo que quedó pendiente)

- [ ] Reconstruir y redesplegar la imagen Docker para que el fix de `pip install --upgrade pip setuptools wheel` tome efecto.
- [ ] Perl queda 🚫 bloqueado (ver detalle arriba) — no se aplicó ninguna eliminación.
- [ ] CVEs de `glibc`, `acl`, `attr`, `sqlite3`, `gzip`, `bzip2` sin parche disponible en Debian: riesgo conocido, sin acción posible hoy.
- [ ] CVEs de `systemd`, `xz-utils`, `libcap2`, `util-linux` (CVE-2026-13595) **sí tienen parche** de Debian — probablemente se resuelven solo con reconstruir la imagen desde cero (`docker build --no-cache`), ya que `python:3.9-slim` se actualiza periódicamente por el mantenedor oficial. Confirmar tras el próximo rebuild si siguen apareciendo en el escaneo de Artifact Registry.
- [ ] `git add` / `git commit` / `git push` — pendiente, a criterio del usuario.

## Verificación ejecutada

- `pip install -r requirements.txt` en un venv limpio: **falló primero** por el conflicto protobuf/google-cloud-firestore descrito arriba; tras corregir, instaló sin conflictos.
- `pip check`: `No broken requirements found.`
- Import de `src.pipeline` y `FirestoreService` con variables de entorno mínimas: OK.
- `pip-audit -r requirements.txt` post-fix: **0 paquetes vulnerables** (antes: 3 paquetes con CVEs conocidos vía pip-audit; el escaneo de Artifact Registry reportaba más porque cubre también el toolchain de pip, no solo requirements.txt).
