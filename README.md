🇪🇸 Español | [🇬🇧 English](README.en.md)

# Hermes Stack

La mayoría de la gente ejecuta modelos de IA locales en modo chat. Este stack los ejecuta como un **ecosistema de ingeniería completo** — desde una idea en bruto hasta código verificado y respaldado por artefactos — con cada fase enrutada al modelo más adecuado para esa tarea cognitiva, todo observable y persistido en memoria entre sesiones.

Esto no es un setup de chatbot. Es un entorno de ingeniería de IA local.

---

## El pipeline completo

```
Idea
 │
 ▼  Capa de planificación BMAD
 ├─ analyze    → contexto de negocio, restricciones, riesgos
 ├─ prd        → documento de requisitos de producto
 ├─ ux         → brief de diseño UI/UX (opcional, fases orientadas a diseño)
 ├─ architect  → decisiones de arquitectura técnica
 └─ stories    → historias de usuario estructuradas
       │
       ▼  Capa de implementación SDD
       ├─ explore   → investigación del codebase, comparación de enfoques
       ├─ propose   → propuesta formal de cambio con alcance y tradeoffs
       ├─ spec      → requisitos y escenarios de aceptación
       ├─ design    → decisiones de arquitectura y desglose de componentes
       ├─ tasks     → checklist de implementación ordenado por dependencias
       ├─ apply     → implementación con commits por unidad de trabajo
       └─ verify    → validación contra la spec, informe CRITICAL / WARNING
             │
             ▼
          Código verificado y respaldado por artefactos
          persistido en Engram para sesiones futuras
```

La mayoría de herramientas te dan un asistente de código. Esto te da el proceso de ingeniería completo — estructurado, reproducible y consciente del modelo en cada paso.

---

## ¿Qué es Hermes?

Hermes es un agente [OpenCode](https://github.com/opencode-ai/opencode) configurado como orquestador SDD. OpenCode es un asistente de código IA de terminal de código abierto — similar a Claude Code, pero auto-hospedable e independiente del modelo.

Por defecto, OpenCode es un agente de código capaz. Hermes añade sobre él:

- Un **alma** (`soul.md`) que define su rol: orquestador delgado, coordina fases, nunca implementa inline
- Un **proxy LiteLLM** que enruta cada fase al modelo local o en la nube más óptimo
- Un **sistema de memoria dual** para contexto de sesión y persistencia entre sesiones
- Un **inyector de skills** que carga automáticamente los estándares de código por petición
- Un **Design MCP** para conocimiento UI/UX sin llamadas externas
- Un **flujo BMAD + SDD completo** implementado en Schema Service

---

## Enrutamiento por modelo y fase

Cada fase tiene un perfil cognitivo distinto. Los modelos de razonamiento destacan en tradeoffs y arquitectura; los modelos de código son más rápidos y precisos en output estructurado e implementación; los modelos de contexto amplio gestionan la exploración y el juicio cualitativo.

```
BMAD analyze / prd / architect   →  DeepSeek R1 32B      (razonamiento profundo)
BMAD ux                          →  Qwen3 32B             (diseño + contexto amplio)
BMAD stories                     →  Qwen 2.5-Coder 32B   (output estructurado)

SDD explore / verify             →  Qwen3 32B             (juicio cualitativo)
SDD propose / design             →  DeepSeek R1 32B       (decisiones arquitectónicas)
SDD spec / tasks / apply         →  Qwen 2.5-Coder 32B   (precisión + generación de código)
```

Todo el enrutamiento se configura mediante alias en `litellm/litellm_config.yaml`. Cambia un modelo, un puerto, o apunta un alias a Anthropic — sin ningún cambio en el agente.

---

## Sistema de memoria dual

Hermes tiene dos capas de memoria que trabajan juntas:

### Memoria de sesión (OpenCode nativo)
Dentro de una sesión, contexto completo de conversación: llamadas a herramientas, lecturas de ficheros, decisiones tomadas. Estándar en cualquier agente de código IA.

### Memoria entre sesiones (Engram)
Engram es un servidor MCP de memoria persistente en `:7437`. Hermes escribe en él mediante herramientas MCP y lo lee al inicio de cada sesión. Qué se persiste:

- **Artefactos BMAD + SDD** — output de cada fase almacenado por topic key, recuperable en sesiones futuras
- **Decisiones** — elecciones arquitectónicas, tradeoffs considerados, dirección tomada
- **Bugs resueltos** — causa raíz + solución, para que el agente no repita los mismos errores
- **Descubrimientos** — hallazgos no obvios sobre el codebase, gotchas, casos edge
- **Resúmenes de sesión** — guardados al final de cada sesión para que la siguiente empiece informada

Esto es lo que separa los flujos agénticos del chat. El chat olvida. Hermes no.

---

## Inyección automática de skills

Antes de cada petición LLM, `skill_injector.py` (un `CustomLogger` de LiteLLM) escanea `~/.claude/skills/` y antepone los estándares de código relevantes al mensaje de sistema — automáticamente, sin ninguna instrucción del agente.

La biblioteca de skills cubre actualmente:

| Dominio | Skills |
|---------|--------|
| **Frontend** | React 19, React Enterprise SPA, Next.js 15, Angular (arquitectura, core, formularios, rendimiento), Tailwind 4, Zustand 5, Zod 4, AI SDK 5 |
| **UI/UX** | frontend-design, web-designer-expert |
| **Backend** | Django DRF, .NET backend, .NET MCP server, Go testing, pytest |
| **Lenguaje** | TypeScript, Playwright |
| **Flujo de trabajo** | SDD (9 fases), branch-pr, chained-pr, github-pr, work-unit-commits, Jira (epic, tarea), issue-creation |
| **Calidad de código** | comment-writer, cognitive-doc-design, project-review, lessons-learnt, judgment-day |

Todos los modelos detrás de LiteLLM — locales o en la nube — se benefician de esta inyección automáticamente.

---

## Base de conocimiento UI/UX

`hermes-design-mcp` es un servidor FastMCP SSE respaldado por un motor de búsqueda BM25 sobre 14 datasets CSV curados que cubren sistemas de diseño, paletas de color, tipografía, iconos, guías UX, patrones de componentes y guía específica por framework.

Hermes lo consulta antes de responder cualquier pregunta de diseño o generar UI. Tres herramientas:

- `design_search(query, domain?)` — búsqueda concreta (color, tipografía, iconos, UX, landing, gráficos...)
- `design_search_stack(query, stack)` — guía específica por framework (React, Next.js, Tailwind, shadcn, SwiftUI...)
- `design_system(query, project_name?)` — genera un sistema de diseño completo para un proyecto nuevo

Sin llamadas externas. Sin tokens de diseño inventados a partir de datos de entrenamiento.

---

## Arquitectura

```
Tú
 │  Launcher macOS (Spotlight → HermesAgent.app)
 ▼
Hermes (Docker)  ─────────────────────────────────────────────────
  Agente OpenCode (orquestador BMAD + SDD)    puerto 9119 (web TUI)
  soul.md → persona + reglas de orquestación (montado :ro)
  │
  ├──► Schema Service  :8010  (FastAPI — ejecuta fases BMAD + SDD)
  │      /v1/bmad/*  — analyze, prd, ux, architect, stories
  │      /v1/sdd/*   — explore, propose, spec, design, tasks, apply, verify
  │
  │  Todas las llamadas LLM → proxy LiteLLM
  ▼
Proxy LiteLLM  :8002 ─────────────────────────────────────────────
  skill_injector.py → inyecta estándares de código por petición
  Enruta por alias:
    local-hermes      → Qwen3 32B           :8006  (explore, verify, bmad-ux)
    local-thinking    → DeepSeek R1 32B     :8001  (propose, design, bmad-analyze/prd/architect)
    local-coder       → Qwen 2.5-Coder 32B  :8000  (spec, tasks, apply, bmad-stories)
    claude-sonnet     → API de Anthropic          (fallback en la nube)
  │
  ├──► Langfuse  :3000  (trazas, costes, evals — cada petición registrada)
  │
  ├──► Engram  :7437  (memoria entre sesiones — MCP via proxy :7438)
  │
  └──► hermes-design-mcp  :8012  (base de conocimiento UI/UX — 14 datasets)
```

---

## Componentes

| Directorio | Función |
|------------|---------|
| `hermes-docker/` | Agente OpenCode en Docker — config, soul.md, launchers, RUNBOOK |
| `schema-service/` | FastAPI que ejecuta todas las fases BMAD y SDD via LLM estructurado |
| `hermes-design-mcp/` | Servidor MCP para base de conocimiento UI/UX |
| `langfuse-docker/` | Dashboard de observabilidad (trazas, costes, evals) |
| `litellm/` | Config del proxy LiteLLM + inyector de skills + script de arranque |
| `bin/` | Scripts de gestión del stack (arranque, proxies, Engram) |

---

## Requisitos previos

- **Docker Desktop** — para Hermes y Langfuse
- **Python 3.11+** — para el proxy LiteLLM y el servidor Design MCP
- **LiteLLM** — `pip install litellm`
- **API keys** — Anthropic (necesaria para fallback en la nube), modelos MLX locales (opcional)

Los modelos locales se ejecutan con `mlx_lm.server` en Apple Silicon. Si solo tienes claves de Anthropic, apunta los alias a `claude-sonnet` / `claude-haiku` en `litellm_config.yaml` — el resto del stack funciona de forma idéntica.

---

## Configuración de secretos

Los secretos viven fuera del repositorio en `~/.config/litellm/env`, cargados en tiempo de ejecución:

```bash
mkdir -p ~/.config/litellm
cat > ~/.config/litellm/env <<EOF
ANTHROPIC_API_KEY=sk-ant-...
TOGETHER_API_KEY=...           # opcional
LITELLM_MASTER_KEY=hermes-local-dev
EOF
```

`litellm/bin/litellm-launch.sh` carga este fichero automáticamente. Nunca lo incluyas en el repositorio.

Para las variables de Docker Compose, copia `.env.example` → `.env`. `bash install.sh` lo hace automáticamente.

---

## Schema Service

`schema-service/` es la capa de ejecución del stack. Hermes orquesta, pero nunca genera contenido SDD o BMAD por sí mismo — siempre delega en Schema Service via `curl`.

Es una API FastAPI + [Instructor](https://github.com/jxnl/instructor) + Pydantic v2. Instructor fuerza a los modelos locales a devolver JSON estructurado validado por esquema — sin alucinaciones de formato, sin parsing frágil.

```
schema-service/
├── app/
│   ├── routes/
│   │   ├── sdd.py       # endpoints /v1/sdd/* (explore, propose, spec, design, tasks, apply, verify)
│   │   └── bmad.py      # endpoints /v1/bmad/* (analyze, prd, ux, architect, stories)
│   ├── schemas/         # modelos Pydantic de entrada/salida por fase
│   ├── prompts/         # prompts de sistema por fase (.txt)
│   └── registry.py      # tabla modelo→alias→endpoint (fuente autoritativa de routing)
└── calibration/         # harness de evaluación de calidad por fase
```

Arranque:
```bash
cd schema-service
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

O via `bin/agentic-up.sh`, que lo levanta automáticamente en el orden correcto.

---

## Engram — memoria persistente

Engram es el servidor de memoria del stack, desarrollado por [Gentleman Programming](https://github.com/Gentleman-Programming/engram). Proporciona persistencia entre sesiones via herramientas MCP — Hermes lo usa para guardar artefactos SDD/BMAD, decisiones, bugs resueltos y resúmenes de sesión.

**Instalación:**
```bash
brew install engram
```

**Arquitectura de acceso:**

Hermes corre en Docker y no puede llamar directamente a un proceso stdio. El stack usa `mcp-proxy` como puente:

```
Hermes (Docker)
  │  MCP HTTP/SSE  →  :7438
  ▼
mcp-proxy (:7438)     ← bin/engram-mcp-proxy-run.sh (gestionado por launchd)
  │  stdio
  ▼
engram mcp --tools=agent
  │  REST
  ▼
Engram (:7437)        ← proceso principal de Engram
```

`bin/engram-mcp-proxy-run.sh` lee el workspace activo desde `~/.hermes-current-workspace` y arranca `mcp-proxy` desde ese directorio — así Engram detecta automáticamente el proyecto correcto.

La gestión la hace **launchd** (macOS). Los plists de `com.pirito.litellm` y `com.pirito.engram-mcp-proxy` arrancan estos servicios automáticamente al iniciar sesión.

---

## Inicio rápido

> **Modelos locales**: si quieres usar modelos MLX locales en lugar de APIs en la nube, consulta primero → [docs/local-models.md](docs/local-models.md)

```bash
# 1. Clonar y configurar
git clone git@github.com:toniJC/hermes-stack.git
cd hermes-stack
bash install.sh

# 2. Configurar secretos (ver sección anterior)

# 3. Instalar Engram
brew install engram

# 4. Instalar servicios launchd (arranque automático al iniciar sesión)
mkdir -p ~/bin
cp bin/agentic-up.sh bin/engram-mcp-proxy-run.sh ~/bin/
cp litellm/bin/litellm-launch.sh ~/bin/
bash bin/launchd/install.sh

# 5. Arrancar todo el stack
bash bin/agentic-up.sh
```

`agentic-up.sh` levanta los servicios en orden con health-gating entre tiers:

```
T0  LiteLLM proxy     :8002   (launchd — arranca automáticamente al iniciar sesión)
T1  Engram            :7437
T1b Engram MCP proxy  :7438
T2  Modelos MLX       :8000 :8001 :8006  (en paralelo)
T4  Schema Service    :8010
```

Es idempotente — los servicios ya activos se saltan. Modo diagnóstico: `bash bin/agentic-up.sh --check`

Luego arranca Hermes:
```bash
cd hermes-docker && docker compose up -d
```

Opcional — Design MCP:
```bash
cd hermes-design-mcp && bash run.sh
```

Interfaz web de Hermes → http://localhost:9119

Para comprobaciones de salud, resolución de problemas y procedimientos de actualización → [hermes-docker/RUNBOOK.md](hermes-docker/RUNBOOK.md)

---

## soul.md

`hermes-docker/hermes-config/soul.md` es la persona e instrucciones operativas de Hermes — el equivalente de `CLAUDE.md` en Claude Code, pero para este agente. Se monta de solo lectura en el contenedor al arrancar. Los cambios se aplican en el próximo `docker compose up`.

Son 20 secciones que definen contratos explícitos. Los más importantes:

### El principio fundamental: cliente delgado

Hermes **coordina**, nunca implementa. Toda la lógica de ejecución vive en Schema Service. Toda la persistencia vive en Engram. Hermes es el director de orquesta — nunca toca un instrumento.

```
NUNCA generes contenido SDD tú mismo.
SIEMPRE llama a Schema Service via curl.
NUNCA uses curl para llegar a Engram — solo MCP.
```

### Primera acción: detección de proyecto

Lo primero que hace Hermes al arrancar:

```bash
echo $HERMES_PROJECT
```

Este valor se pasa explícitamente en **todas** las llamadas MCP a Engram. Sin él, la memoria no sabe a qué proyecto pertenece el artefacto.

### Protocolo Engram (memoria)

Guardado proactivo obligatorio — sin esperar a que se lo pidan — tras cualquiera de estos eventos:
- Resultado de fase recibido y validado
- Decisión arquitectónica tomada
- Bug o error resuelto
- Descubrimiento no obvio sobre el codebase
- Fin de sesión (`mem_session_summary`)

Recuperación siempre en dos pasos — los resultados de búsqueda son previsualizaciones truncadas a 300 caracteres y **nunca** pueden usarse como fuente:

```
1. mem_search(query: "sdd/{cambio}/{fase}", project: "$HERMES_PROJECT") → obtener ID
2. mem_get_observation(id: <ID>) → contenido completo
```

### Disciplina de fase

Los modelos locales tienden a mezclar responsabilidades entre fases. El soul.md lo previene con una regla simple: **una fase por turno, nombrada explícitamente al inicio**.

| Fase | Tu trabajo en este turno | No harás |
|------|--------------------------|----------|
| explore | Leer ficheros, mapear estructura | Modificar o proponer soluciones |
| propose | Problema, alcance, enfoque | Escribir spec, diseño o código |
| spec | QUÉ (requisitos, criterios) | Decidir CÓMO ni arquitectura |
| design | CÓMO (arquitectura, tradeoffs) | Listas de tareas o implementar |
| tasks | Desglose ordenado del diseño | Implementarlas |
| apply | Implementar el lote actual | Rediseñar o ampliar alcance |
| verify | Comparar implementación con spec | Corregir código inline |
| archive | Cerrar y persistir estado final | Reabrir decisiones |

### Handoff BMAD → SDD

Cuando BMAD completa `stories`, Hermes recupera los tres artefactos clave de Engram (`prd`, `architect`, `stories`), los ensambla con `jq` y llama a `POST /v1/sdd/propose` — arrancando el ciclo SDD con contexto de negocio completo ya incorporado.

### Cierre de sesión

Antes de terminar cualquier sesión, `mem_session_summary` es **obligatorio**. Si se omite, la siguiente sesión empieza a ciegas.

---

## Repositorio complementario

La configuración de Claude Code (CLAUDE.md, agentes SDD, slash commands, más de 40 skills) vive en:
[https://github.com/toniJC/dotfiles](https://github.com/toniJC/dotfiles)

Clónalo y ejecuta `bash install.sh` para crear el symlink `~/.claude` desde la config versionada.
