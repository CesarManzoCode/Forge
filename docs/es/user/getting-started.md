# Primeros pasos con Forge

Forge es un agente de IA para la terminal, diseñado exclusivamente para desarrolladores. Esta guía cubre la instalación, configuración y tu primera tarea.

---

## Requisitos

- **Sistema operativo**: Linux (probado en Arch Linux, Ubuntu 24)
- **Python**: 3.11 o superior
- **Clave API de Groq**: Gratuita en [console.groq.com](https://console.groq.com)

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/youruser/forge.git
cd forge
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install groq python-dotenv tiktoken requests beautifulsoup4 html2text
```

### 4. Configurar el entorno

Copia el archivo de ejemplo y completa tus valores:

```bash
cp .env.example .env
```

Configuración mínima requerida:

```env
GROQ_API_KEY=gsk_tu_clave_aqui
GROQ_MODEL=llama-3.3-70b-versatile
FORGE_PROJECT_ROOT=/ruta/absoluta/a/tu/proyecto
FORGE_LANGUAGE=Spanish
```

> **Importante:** `FORGE_PROJECT_ROOT` debe ser la ruta absoluta al directorio en el que quieres que Forge trabaje. Forge no puede acceder a archivos fuera de ese directorio.

### 5. Ejecutar Forge

```bash
python app.py
```

---

## Tu primera tarea

Al iniciar Forge verás el prompt principal:

```
┌─ You ──────────────────────────────────────────────────
│  >
```

Escribe `/task` y presiona Enter. Forge te pedirá que describas lo que quieres:

```
/task
```

```
Describe the task in detail.
Type END on a new line when done.

│  Crea un script llamado hola.py que imprima "Hola desde Forge"
│  y ejecútalo.
│  END
```

Forge generará un plan y te lo mostrará:

```
PLAN  ·  Script hola
─────────────────────────────────────────────
  Risk      ○  LOW
  Subtasks  1
─────────────────────────────────────────────
   1.  Crear hola.py con print statement y ejecutarlo
─────────────────────────────────────────────
  Plan is ready. Review the subtasks above.
  /start — execute the plan as shown
```

Revisa el plan. Si se ve correcto, escribe `/start` para ejecutarlo.

> Forge nunca ejecutará nada sin tu comando explícito `/start`.

---

## Consejos para escribir buenas tareas

**Sé específico.** En lugar de "configura tests", di "crea tests pytest para el módulo `auth.py` cubriendo login, logout y validación de tokens, y ejecútalos."

**Menciona las rutas de archivos.** "Crea `src/utils/logger.py`" es mejor que "crea un archivo de logger."

**Un objetivo por tarea.** Forge funciona mejor cuando el objetivo está claro. Las tareas complejas con múltiples objetivos pueden dividirse en varias invocaciones de `/task`.

**Describe el resultado esperado.** "Corre los tests y reporta cuántos pasaron" ayuda al agente a saber cuándo terminó.

---

## Próximos pasos

- [Referencia de comandos](commands.md) — Todos los comandos disponibles
- [Capacidades](capabilities.md) — Qué puede y qué no puede hacer Forge
- [Riesgos y seguridad](risks.md) — El modelo de seguridad