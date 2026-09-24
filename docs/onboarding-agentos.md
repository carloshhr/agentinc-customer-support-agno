# Onboarding de AgentOS

AgentOS es una plataforma de agentes construida sobre Agno. Su idea central es operar por dos vías complementarias: los agentes de desarrollo modifican el código bajo control de Git, mientras que Platform Builder crea agentes, equipos y workflows en tiempo de ejecución usando un registro seguro de capacidades previamente revisadas.

## Recorrido rápido

1. Hablá con **Agno** cuando no sepas qué componente necesitás.
2. Pedile a **Platform Builder** que construya o cambie un componente creado en Studio.
3. Consultá a **Platform Manager** para entender ejecuciones, costos, errores, evaluaciones y schedules.
4. Consultá a **Platform Engineer** para entender el código y preparar un cambio de fuente.
5. Usá el equipo **Customer Support** para procesar correos simulados de soporte.
6. Ejecutá **deployment-check** para revisar la salud de la instalación.

## Mapa del sistema

```text
Clientes
├── AgentOS UI
├── REST API
├── MCP /mcp
└── Slack (opcional)
        │
        ▼
Agno — equipo principal y puerta de entrada
├── Platform Builder  — construye componentes en Studio
├── Platform Manager  — observa el runtime
├── Platform Engineer — explica el código fuente
└── StudioRunnerTools — ejecuta componentes publicados

Componentes de dominio
├── Customer Support
│   ├── Order Support
│   ├── Product Support
│   └── Returns & Refunds Support
└── Support Insights

Workflows
├── deployment-check
└── run-evals

Persistencia compartida
├── PostgreSQL: sesiones, runs, memoria, componentes y schedules
├── pgvector: bases de conocimiento
├── shared-notes: notas colaborativas
└── ResultStore: resultados grandes de herramientas
```

La composición principal se encuentra en [`app/main.py`](../app/main.py). Ahí se registran agentes, equipos, workflows, interfaces, autenticación, scheduler y el registro de Studio.

## Agentes y equipos

### Agno

**Tipo:** equipo y puerta de entrada principal
**Archivo:** [`teams/lead.py`](../teams/lead.py)

Agno representa a la plataforma frente al usuario. Mantiene la conversación, recuerda contexto, consulta notas, busca en la web y delega la ejecución:

| Necesidad | Destino |
|---|---|
| Crear un agente, equipo o workflow | Platform Builder |
| Revisar actividad, costos, fallos o schedules | Platform Manager |
| Entender código, configuración o arquitectura | Platform Engineer |
| Ejecutar un componente publicado | `StudioRunnerTools` |
| Resolver una ambigüedad real | Pregunta estructurada al usuario |

Agno conserva la responsabilidad por la respuesta final aunque otro componente haga el trabajo. También puede ejecutar componentes creados en Studio por su nombre. La autorreferencia está limitada a un nivel para evitar ciclos de delegación.

### Platform Builder

**Tipo:** agente constructor
**Archivo:** [`agents/builder.py`](../agents/builder.py)

Construye agentes, equipos y workflows mediante `StudioTools`. Sólo puede usar modelos, herramientas, funciones, conocimiento y learning declarados en [`app/registry.py`](../app/registry.py).

Reglas importantes:

- Una creación normal termina publicada y disponible para ejecución.
- Un agente sirve para una responsabilidad autónoma.
- Un equipo coordina especialistas.
- Un workflow modela pasos repetibles, ramas, loops y gates.
- Una capacidad ausente no se improvisa: requiere un cambio de código revisado en el registro.
- No puede agregar shell, lectura de secretos ni escritura irrestricta.
- Los componentes que pueden pausar para pedir una respuesta humana no deberían ejecutarse por schedule.

### Platform Manager

**Tipo:** agente de observabilidad, deliberadamente read-only
**Archivo:** [`agents/manager.py`](../agents/manager.py)

Puede consultar:

- consumo de tokens y modelos;
- actividad y latencia de runs;
- uso y fallos de herramientas;
- historial de evaluaciones;
- schedules y sus ejecuciones;
- componentes creados en Studio;
- aprobaciones pendientes;
- informes de `deployment-check`.

Puede ejecutar un diagnóstico determinista como `deployment-check`, pero no cambia código, componentes ni schedules.

### Platform Engineer

**Tipo:** agente de lectura del repositorio
**Archivo:** [`agents/engineer.py`](../agents/engineer.py)

Explica cómo está construido el sistema usando herramientas de lectura, listado y búsqueda sobre el workspace. No edita archivos. Cuando se necesita un cambio, identifica el workflow de desarrollo apropiado dentro de [`.agents/skills/`](../.agents/skills/).

### Customer Support

**Tipo:** equipo público de dominio
**Archivo:** [`teams/customer_support.py`](../teams/customer_support.py)

Procesa un `CustomerEmail` validado y coordina tres especialistas privados:

| Especialista | Responsabilidad | Archivo |
|---|---|---|
| Order Support | Estado, fulfillment y tracking desde datos persistidos | [`agents/order_support.py`](../agents/order_support.py) |
| Product Support | Productos, materiales, talles y políticas desde conocimiento dedicado | [`agents/product_support.py`](../agents/product_support.py) |
| Returns & Refunds Support | Validación y ejecución de reintegros | [`agents/refund_support.py`](../agents/refund_support.py) |

El equipo devuelve un `CustomerEmailReply` estructurado. La respuesta incluye categoría, código de problema, resultado y, cuando corresponde, identificadores de orden o producto.

### Support Insights

**Tipo:** agente administrativo de reporting
**Archivo:** [`agents/support_insights.py`](../agents/support_insights.py)

Consulta agregados calculados en SQL y devuelve un `InsightsReport` tipado. Sus recomendaciones deben derivar de los conteos observados; no redacta respuestas para clientes ni programa informes.

## Cómo funciona la orquestación

La orquestación combina cuatro mecanismos:

1. **Delegación entre miembros.** Agno dirige cada pedido al especialista adecuado.
2. **Ejecución dinámica.** `StudioRunnerTools` localiza y ejecuta la versión publicada de un componente creado en Studio.
3. **Equipos de dominio.** Customer Support coordina especialistas privados y combina sus resultados.
4. **Workflows deterministas.** Las tareas repetibles usan pasos, condiciones, routers y loops. Las expresiones CEL gobiernan las ramas creadas en Studio.

Una delegación no amplía permisos. Cada componente conserva únicamente sus herramientas, conocimiento y límites declarados.

## Memoria, notas y conocimiento

Estas superficies tienen propósitos diferentes y no deberían duplicar información.

### Perfil y memoria por usuario

[`app/learning.py`](../app/learning.py) declara `shared-learning`, una `LearningMachine` compartida por los agentes de plataforma.

- **Perfil:** preferencias y datos relativamente estables del usuario.
- **Memoria:** hechos y contexto acumulados sobre ese usuario.
- Ambas superficies se separan por `user_id`.
- Los componentes que usan `shared-learning` comparten el mismo “yo” del usuario dentro de la misma base de datos.

Agno usa una máquina propia que agrega memoria de entidades compartidas. Las entidades representan personas, proyectos y sistemas mediante hechos breves y enlaces hacia notas más extensas.

### Notas compartidas

[`app/notes.py`](../app/notes.py) define el namespace `shared-notes`.

Las notas contienen decisiones, razonamiento y documentos de trabajo compartidos. Agno tiene el toolkit completo; los componentes creados reciben una versión acotada que permite leer, agregar, listar, buscar y comprobar líneas, pero no reemplazar ni borrar el trabajo de otros.

### Bases de conocimiento

[`app/knowledge.py`](../app/knowledge.py) declara `shared-knowledge`, respaldada por PostgreSQL y pgvector. Se carga desde la página Knowledge de AgentOS o mediante su API.

El dominio de soporte también posee una base dedicada para el catálogo. Product Support debe consultar esa base antes de responder sobre productos o talles.

**Diferencia práctica:**

| Superficie | Qué guarda | Alcance |
|---|---|---|
| Perfil/memoria | Quién es el usuario y cómo trabaja | Privado por usuario |
| Entidades | Índice de personas, proyectos y sistemas | Compartido |
| Notas | Decisiones y razonamiento extensos | Compartido |
| Knowledge | Documentos recuperables mediante búsqueda semántica | Según la base conectada |
| Historial de sesión | Conversación y runs recientes | Sesión/componente |

### Resultados grandes de herramientas

[`app/offload.py`](../app/offload.py) configura un `ResultStore`. Cuando una herramienta devuelve un payload demasiado grande, el contenido se persiste y la conversación conserva solamente una vista previa y un `result_id`. El agente puede recuperar fragmentos con herramientas de búsqueda y lectura. Los resultados expiran después de siete días.

## Aprobaciones y Human-in-the-Loop

Las aprobaciones se reservan para operaciones que descartan estado o producen efectos sensibles.

### Aprobaciones de Platform Builder

Estas operaciones pausan el run y requieren confirmación humana:

- archivar un componente;
- borrar una versión;
- borrar un schedule.

Crear, editar y publicar no requieren confirmación porque producen versiones auditables y reversibles.

La aprobación puede resolverse desde la UI, Slack o `continue_run` por MCP. Un cliente MCP debe devolver el requerimiento original con su identificador; enviar solamente un booleano de confirmación no identifica qué operación se está aprobando.

### Aprobaciones de reintegros

El flujo de reintegros mantiene una separación estricta:

1. El agente intenta la ruta automática.
2. La herramienta vuelve a leer el total persistido de la orden.
3. Si supera el límite automático, el run pausa para aprobación administrativa.
4. Al continuar, el sistema vuelve a validar la orden y usa el identificador persistido de la aprobación.
5. La finalización aprobada o rechazada se construye de forma determinista en [`app/support_continuations.py`](../app/support_continuations.py), sin otra decisión del modelo.

La aprobación humana nunca debería reemplazarse por una clasificación probabilística.

## Entradas, salidas y estados de ejecución

### Entradas

Un componente puede recibir:

- texto libre;
- un modelo Pydantic validado, como `CustomerEmail`;
- estado de sesión e información adicional;
- la salida previa de un paso de workflow.

### Salidas

| Tipo | Ejemplo |
|---|---|
| Texto | Respuesta habitual de los agentes de plataforma |
| Modelo tipado | `CustomerEmailReply`, `InsightsReport` |
| JSON de herramienta | Consultas de órdenes, métricas y diagnósticos |
| Markdown | Informe de `run-evals` |
| Artefacto descargable | JSON, CSV, TXT, HTML o código generado |
| Resultado de workflow | Contenido final más salidas y errores de pasos |
| Run pausado | Estado más requerimientos de aprobación pendientes |

Los contratos tipados del soporte están en [`app/support_models.py`](../app/support_models.py).

### Estados relevantes

- **COMPLETED:** la ejecución terminó.
- **PAUSED:** espera una aprobación o respuesta humana.
- **ERROR/FAILURE:** el componente o un paso no pudo completar su trabajo.
- **CANCELLED:** la ejecución fue cancelada.

Los workflows pueden completar técnicamente aunque un paso haya sido omitido por error; por eso Platform Manager revisa tanto el estado global como los errores de pasos antes de declarar saludable una ejecución.

## Registro seguro de Studio

[`app/registry.py`](../app/registry.py) es la frontera entre código revisado y composición en tiempo de ejecución.

Actualmente ofrece, de forma controlada:

- documentación de Agno por MCP;
- búsqueda web;
- Slack con permisos acotados;
- generación de imágenes y voz;
- generación de archivos de texto;
- preguntas estructuradas al usuario;
- calculadora;
- notas compartidas;
- funciones deterministas para workflows;
- modelo, base de datos, learning y knowledge compartidos;
- Platform Manager como agente componible.

Que una herramienta sea descubierta por AgentOS no significa que Platform Builder pueda entregársela a un componente. Sólo los recursos admitidos explícitamente en el registro son construibles.

## Workflows y schedules

### deployment-check

**Archivo:** [`workflows/deployment_check.py`](../workflows/deployment_check.py)

Es un diagnóstico determinista y sin llamadas al modelo. Verifica base de datos, credenciales, autenticación, URL del scheduler, MCP, Slack, imports, recursos del registro y actividad del poller. Su schedule diario está habilitado por defecto.

### run-evals

**Archivo:** [`workflows/run_evals.py`](../workflows/run_evals.py)

Ejecuta un subconjunto de evaluaciones seleccionado por `EVALS_TAG` y devuelve un resumen Markdown. Consume llamadas a modelos; por eso su schedule existe pero está deshabilitado inicialmente.

Los schedules se registran en [`app/schedules.py`](../app/schedules.py). Un componente que pueda pedir intervención humana es un mal objetivo para ejecución desatendida.

## Interfaces y autenticación

- **REST API:** superficie programática principal.
- **MCP en `/mcp`:** permite operar AgentOS desde clientes compatibles.
- **AgentOS UI:** administración, conversación, conocimiento y aprobaciones.
- **Slack:** se habilita cuando existen el token y el signing secret requeridos.

En desarrollo, la autorización puede estar deshabilitada. En producción, JWT protege la API. MCP también admite cuentas de servicio y puede habilitar su propio flujo OAuth cuando se configura `MCP_CONNECT_SECRET`.

La identidad efectiva del run determina qué perfil y memoria privada utiliza el sistema. Las notas y entidades compartidas no son privadas por usuario.

## Dónde encaja Jev de TypeSafe AI

Jev no debería tratarse como un agente de razonamiento general. Está diseñado para decisiones atómicas con salidas tipadas:

- **Choice:** elegir una opción conocida;
- **Score:** puntuar una dimensión con una rúbrica;
- **Noul:** evaluar una afirmación como probabilidad entre 0 y 1.

### Mejor primer caso: clasificación del inbox de soporte

El punto de integración recomendado está antes de `customer_support_team.arun(...)` en [`app/support_inbox.py`](../app/support_inbox.py).

Una sola evaluación podría producir:

| Pregunta | Primitiva |
|---|---|
| Área responsable: orden, producto, reintegro u otra | Choice |
| Nivel de frustración | Score |
| Presencia de urgencia | Noul |
| Tipo probable de problema | Choice |

La confianza debería gobernar el comportamiento:

- **Alta:** agregar clasificación y prioridad como metadata.
- **Media:** dejar que Customer Support resuelva la ambigüedad.
- **Baja:** pedir revisión humana o información adicional.

La primera versión debería ser asesora y read-only: no debe ejecutar reintegros, aprobar acciones ni modificar componentes.

### Casos secundarios

1. Preclasificación barata para evaluaciones y guardrails atómicos.
2. Priorización administrativa de tendencias en Support Insights.
3. Un toolkit acotado en el registro de Studio, solamente después de validar privacidad, retención, límites, disponibilidad y manejo de errores.
4. Clasificación inicial de solicitudes para orientar a Platform Builder entre agente, equipo o workflow.

### Dónde no usarlo

- elegibilidad o monto de reintegros;
- reemplazo de aprobaciones humanas;
- publicación, borrado o archivado de componentes;
- autorización de deploys;
- remediación automática.

Las salidas tipadas evitan respuestas malformadas, pero no garantizan que la decisión sea correcta. Las probabilidades y la confianza sirven para decidir cuándo automatizar y cuándo escalar.

Referencias oficiales:

- [Introducción a Jev](https://docs.typesafe.ai/)
- [Quick start con clasificación de tickets](https://docs.typesafe.ai/introduction/quickstart)
- [Uso de confianza](https://docs.typesafe.ai/confidence)
- [Patrones de integración](https://docs.typesafe.ai/patterns)

## Próximos pasos recomendados

1. Usar este documento como mapa inicial del sistema.
2. Ejecutar `deployment-check` para validar el entorno.
3. Probar Agno, Platform Manager y Customer Support desde la UI o MCP.
4. Si se desea evaluar Jev, crear primero un wrapper read-only fuera del registro global.
5. Comparar sus clasificaciones contra casos representativos antes de permitir routing automático.
