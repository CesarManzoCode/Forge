# Referencia de Comandos

Referencia completa de todos los comandos del CLI de Forge.

---

## Comandos de tarea

### `/task`

Abre el editor de tareas. Escribe la descripción de tu tarea con todo el detalle necesario, luego escribe `END` en una nueva línea para enviarla.

Forge va a:
1. Enviar la descripción al planificador
2. Generar una lista cronológica de subtareas
3. Mostrarte el plan con nivel de riesgo y número de subtareas
4. Esperar tu confirmación antes de hacer cualquier cosa

```
/task
```

Si ya existe una tarea, Forge te preguntará si quieres sobreescribirla. Una tarea en estado `running` (ejecución activa) no puede sobreescribirse — usa `/stop` primero.

**Descripción de tarea efectiva:**

```
Bien: Crea un endpoint FastAPI en POST /users que acepte nombre y email,
      valide ambos campos y guarde en SQLite. Incluye manejo de errores
      para emails duplicados.

Mal:  Haz un endpoint de usuarios.
```

---

### `/start`

Ejecuta el plan actual. Solo funciona si existe un plan con estado `planned` o `paused`.

```
/start
```

Una vez iniciado, Forge ejecuta cada subtarea en orden. Puedes monitorear el progreso con `/status`. Cada subtarea se ejecuta hasta completarse antes de pasar a la siguiente.

---

### `/stop`

Solicita una pausa después de que termine la subtarea actual. Forge no interrumpe una subtarea a mitad de ejecución.

```
/stop
```

Después de detenerse, el estado de la tarea cambia a `paused`. Puedes reanudar con `/start`.

> **Nota:** `/stop` no interrumpe la subtarea actual. Si necesitas forzar la detención inmediata, usa `Ctrl+C`. La tarea quedará en estado `running` y necesitarás usar `/reset` para limpiarla.

---

### `/status`

Muestra el estado actual de la tarea, el progreso de las subtareas y el uso del context window.

```
/status
```

Ejemplo de salida:

```
── EXECUTION STATUS ─────────────────────────────
  Task    : Crear módulo de auth
  Status  : ▶  Running

  ✓  [ 1]  Crear src/auth.py con lógica JWT
         └─ Archivo creado con login, logout, token...
  ▶  [ 2]  Escribir tests para el módulo auth
  ○  [ 3]  Ejecutar tests y reportar resultados

  Context : [████░░░░░░░░░░░░░░░░░░░░░░░░░░] 14.2%
              18,176 / 128,000 tokens
```

Íconos de subtareas:
- `✓` Completada
- `▶` En progreso
- `○` Pendiente
- `✗` Error

---

## Comandos de sesión

### `/reset`

Limpia el historial de conversación del AI. El system prompt se preserva. Si una tarea está en estado `running` o `error` sin executor activo, Forge también ofrecerá limpiar el archivo de tarea.

```
/reset
```

Úsalo cuando:
- La conversación se desvió del tema
- Quieres empezar de cero sin reiniciar Forge
- Una tarea quedó atascada en estado `running` después de un crash

---

### `/help`

Muestra un resumen de todos los comandos disponibles.

```
/help
```

---

### `/exit`

Sale de Forge limpiamente. Al salir, Forge borra automáticamente todo el estado de sesión:

- `context/task/` — resultados de subtareas de la sesión actual
- `context/project/` — resúmenes de tareas de la sesión actual
- `tasks/project/task.json` — el archivo de tarea actual

> `memory/user.json` **no** se borra al salir — tus preferencias persisten entre sesiones.

```
/exit
```

---

## Comandos en modo desarrollador

Solo visibles cuando `DEV_MODE=true` en tu `.env`.

Cuando el modo desarrollador está activo, Forge muestra un bloque detallado antes y después de cada llamada a la API:

```
┌─[DEV:REQUEST]──────────────────────────────────
│  model    : llama-3.3-70b-versatile
│  messages : 6
│  [0] SYSTEM (461 chars)  ...
│  [5] USER  ...
└────────────────────────────────────────────────

┌─[DEV:RESPONSE]─────────────────────────────────
│  time     : 0.63s
│  length   : 244 chars
│  ── json payload
│    { "thought": "...", "tool": "...", "args": {...} }
└────────────────────────────────────────────────
```

Cuando el gestor de context window comprime el historial, se muestra un bloque de compresión:

```
┌─[DEV:COMPRESSION]──────────────────────────────
│  before : 104,320 tokens
│  after  : 18,240 tokens
│  saved  : 86,080 tokens
└────────────────────────────────────────────────
```