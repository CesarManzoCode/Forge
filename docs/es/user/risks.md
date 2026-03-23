# Riesgos y Seguridad

Entendiendo qué puede y qué no puede hacer Forge desde una perspectiva de seguridad.

---

## El modelo de seguridad

Forge opera bajo un principio de mínima confianza. El agente nunca tiene autorización para auto-aprobar operaciones peligrosas. Toda operación sensible pasa por una capa de validación antes de ejecutarse.

### Capas de protección

```
Descripción de la tarea
      ↓
  Planificador LLM (propone herramientas y argumentos)
      ↓
  Registry (valida que la herramienta existe y los args son correctos)
      ↓
  Security Guards (valida path, tamaño, permisos)
      ↓
  La herramienta se ejecuta
```

El agente no puede saltarse ninguna de estas capas desde una descripción de tarea.

---

## Seguridad de paths

Toda operación de archivo pasa por `guard_path()` antes de ejecutarse. Esta función:

1. Resuelve el path a su forma absoluta para prevenir ataques de directory traversal (`../../etc/passwd`)
2. Verifica que el path resuelto esté dentro de `FORGE_PROJECT_ROOT`
3. Verifica el path contra una lista de directorios del sistema permanentemente bloqueados
4. Verifica el nombre del archivo contra una lista de nombres permanentemente bloqueados

**Directorios permanentemente bloqueados:**
`/etc`, `/usr`, `/bin`, `/sbin`, `/boot`, `/sys`, `/proc`, `/root`, `/var`

**Nombres de archivo permanentemente bloqueados:**
`.env`, `.ssh`, `.gnupg`, `id_rsa`, `id_ed25519`, `authorized_keys`, `passwd`, `shadow`, `sudoers`

No hay forma de desbloquear estos desde `.env` ni desde una descripción de tarea. Están hardcodeados.

---

## Seguridad de comandos

Los comandos de terminal pasan por una whitelist antes de ejecutarse. La whitelist tiene dos capas:

1. **Whitelist de binarios** — solo los ejecutables permitidos pueden correr
2. **Whitelist de subcomandos** — para `git`, solo subcomandos específicos están permitidos

**Comandos permanentemente bloqueados** (no pueden agregarse a la whitelist):
`rm`, `rmdir`, `dd`, `mkfs`, `sudo`, `su`, `chmod`, `chown`, `systemctl`, `passwd`, `useradd`, `nc`, `bash`, `sh`

Estos están bloqueados independientemente de lo que diga la descripción de la tarea.

---

## Sandbox de ejecución

Cuando Forge ejecuta snippets de código via `run_code()`, los ejecuta en un directorio temporal creado específicamente para esa ejecución. El sandbox:

- No tiene acceso a los archivos de tu proyecto
- Se elimina después de la ejecución
- Tiene un timeout configurable (por defecto: 30 segundos)

Cuando ejecuta archivos existentes del proyecto via `run_file()`, el archivo corre con la raíz del proyecto como directorio de trabajo. Tiene acceso al proyecto pero no a directorios del sistema.

---

## Protección de secretos

Las siguientes variables de entorno están permanentemente bloqueadas para el agente:

`GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`, `NPM_TOKEN`, `PYPI_TOKEN`

Además, cualquier variable cuyo nombre contenga: `PASSWORD`, `PASSWD`, `TOKEN`, `API_KEY`, `PRIVATE_KEY`, `CERT`, `SSL`

El agente no puede leer estos valores aunque una descripción de tarea lo solicite explícitamente.

---

## Operaciones destructivas

La eliminación de archivos y directorios requiere `confirmed=True` pasado explícitamente. El agente no puede pasar este flag por iniciativa propia — debe preguntarte primero y tú debes aprobar.

Además, `delete_dir()` tiene una protección adicional: nunca eliminará el directorio raíz del proyecto aunque se pase `confirmed=True`.

---

## Riesgos a tener en cuenta

### El agente puede modificar tu código

Forge puede leer y escribir archivos dentro de tu proyecto. Si le pides que refactorice un archivo, lo hará. Si el resultado no es el que querías, usa `git diff` para revisar y `git checkout` para revertir.

**Mejor práctica:** Asegúrate de tener un estado git limpio antes de ejecutar Forge en archivos importantes.

### El agente puede ejecutar código

Forge puede ejecutar archivos Python y snippets de código. Una tarea como "ejecuta `deploy.py`" realmente ejecutará ese archivo. Revisa lo que hace un archivo antes de pedirle a Forge que lo ejecute.

### El agente puede hacer commits de git

Forge puede agregar archivos al stage y hacer commits. Estos commits aparecen en tu historial de git. Revisa con `git log` y `git diff HEAD~1` después de cualquier tarea que involucre git.

### El planificador puede equivocarse

El planificador LLM no es perfecto. Revisa el plan antes de escribir `/start`. Si una subtarea se ve incorrecta o peligrosa, escribe `/task` de nuevo con una descripción más clara.

### Contexto largo

Para sesiones largas, el gestor de context window comprime el historial de conversación anterior. Esto es necesario para prevenir errores de la API pero significa que el agente puede ocasionalmente perder el rastro de contexto muy temprano en la sesión.

---

## Recuperación de incidentes

**Si Forge modifica algo que no querías:**
```bash
git diff          # Ver qué cambió
git checkout .    # Revertir todos los cambios sin commit
```

**Si una tarea queda atascada en estado `running`:**
```bash
# Dentro de Forge
/reset
# Cuando pregunte si limpiar la tarea, responde y
```

**Si Forge falla y pierdes el contexto:**
El contexto está guardado en `context/task/` y `context/project/`. Son archivos Markdown planos que puedes leer directamente para entender qué se hizo.

**Revisando los logs:**
```bash
cat logs/errors.log    # Errores del sistema y crashes
cat logs/tasks.log     # Resúmenes de tareas completadas
cat logs/actions.log   # Llamadas a herramientas y resultados
```