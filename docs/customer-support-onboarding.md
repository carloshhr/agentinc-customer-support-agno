# Onboarding de Customer Support

Customer Support es un equipo multiagente que procesa correos simulados, consulta datos controlados de órdenes y productos, ejecuta reintegros con límites deterministas y devuelve respuestas tipadas. Su frontera pública es el equipo `customer-support`; los tres especialistas que lo integran permanecen privados.

## Recorrido rápido

1. Enviá un correo con `message_id`, `thread_id`, `from_email`, `subject` y `body`.
2. Customer Support identifica qué especialista necesita.
3. El especialista consulta una fuente controlada o ejecuta una herramienta específica.
4. El equipo compone una respuesta `CustomerEmailReply`.
5. Si un reintegro requiere autorización, el run queda pausado.
6. Una vez completado, un post-hook guarda metadata de la interacción para Support Insights.

## Arquitectura

```text
Support Inbox / API / AgentOS UI / MCP
                │
                ▼
      Customer Support Team
      teams/customer_support.py
         │        │        │
         ▼        ▼        ▼
 Order Support  Product Support  Returns & Refunds Support
      │               │                    │
      ▼               ▼                    ▼
StoreRepository   Product Knowledge   StoreRepository
 órdenes propias  catálogo dedicado   + aprobación HITL
         │                                │
         └────────── PostgreSQL ──────────┘
                          │
                          ▼
              Support interaction hook
                          │
                          ▼
                   Support Insights
```

## Componentes

### Customer Support

**Archivo:** [`teams/customer_support.py`](../teams/customer_support.py)
**ID:** `customer-support`
**Tipo:** equipo público en modo coordinador

Responsabilidades:

- validar la entrada mediante `CustomerEmail`;
- delegar órdenes, productos y reintegros al especialista correcto;
- combinar únicamente datos validados y resultados de herramientas;
- devolver una respuesta breve, profesional y empática;
- preservar el `message_id` original;
- no exponer herramientas, taxonomías, razonamiento ni aprobaciones internas.

El equipo no debe estimar montos, métodos de pago ni tiempos de reintegro.

### Order Support

**Archivo:** [`agents/order_support.py`](../agents/order_support.py)
**ID:** `order-support`

Resuelve:

- estado de una orden;
- fulfillment;
- tracking;
- entrega estimada.

Su única fuente es `lookup_order`. La consulta exige `order_id` y `customer_email`; si la orden no pertenece al correo proporcionado, no devuelve información. Esto evita cruces entre clientes.

### Product Support

**Archivo:** [`agents/product_support.py`](../agents/product_support.py)
**ID:** `product-support`

Resuelve:

- información de producto;
- materiales y cuidado;
- medidas y talles;
- precios y políticas presentes en el catálogo.

Consulta exclusivamente la base `store-product-knowledge`, declarada en [`app/store_knowledge.py`](../app/store_knowledge.py). Si la búsqueda no respalda un detalle, devuelve un fallback controlado en lugar de inventarlo.

### Returns & Refunds Support

**Archivo:** [`agents/refund_support.py`](../agents/refund_support.py)
**ID:** `refund-support`

Ejecuta dos rutas:

| Ruta | Condición | Aprobación |
|---|---|---|
| `refund_order_automatically` | Orden elegible de hasta USD 50,00 | No |
| `refund_order_with_admin_approval` | Orden elegible superior a USD 50,00 | Sí |

El agente nunca recibe el monto como argumento. Ambas herramientas vuelven a leer el total persistido para impedir que el modelo o el usuario alteren la decisión.

### Support Insights

**Archivo:** [`agents/support_insights.py`](../agents/support_insights.py)
**ID:** `support-insights`

Es un agente administrativo separado. Lee agregados SQL de interacciones completadas y devuelve un `InsightsReport` con:

- período consultado;
- total de interacciones;
- problemas más frecuentes;
- productos afectados;
- resultados de reintegros.

No accede al texto completo de los clientes para generar el informe y no redacta respuestas de soporte.

## Flujo de un correo

```text
1. Llega SupportEmailRequest
2. Pydantic valida identidad y contenido básico
3. thread_id se usa como session_id
4. Customer Support decide el especialista
5. El especialista consulta datos o ejecuta una herramienta
6. Customer Support produce CustomerEmailReply
7. El post-hook persiste metadata analítica
8. Support Inbox devuelve el thread seguro
```

El endpoint de envío está en [`app/support_inbox.py`](../app/support_inbox.py):

```http
POST /api/support/emails
```

Ejemplo:

```json
{
  "thread_id": "THREAD-1001",
  "message_id": "EMAIL-1001",
  "from_email": "alice@example.test",
  "subject": "¿Dónde está mi orden?",
  "body": "Necesito el tracking de ORD-LUMEN-1001."
}
```

Los mensajes posteriores del mismo thread deben reutilizar `thread_id` y usar un `message_id` nuevo.

## Contratos de entrada y salida

Los contratos viven en [`app/support_models.py`](../app/support_models.py).

### CustomerEmail

| Campo | Uso |
|---|---|
| `message_id` | Identificador único del correo |
| `thread_id` | Identificador de conversación; obligatorio en Support Inbox |
| `from_email` | Identidad del cliente usada también para validar propiedad de órdenes |
| `subject` | Asunto del correo |
| `body` | Contenido del pedido |

### CustomerEmailReply

| Campo | Uso |
|---|---|
| `message_id` | Debe coincidir con el correo de entrada |
| `subject` | Asunto de la respuesta |
| `body` | Mensaje visible para el cliente |
| `category` | Categoría estable para reporting |
| `issue_code` | Código estable del problema |
| `outcome` | Resultado de la interacción |
| `order_id` | Orden relacionada, cuando corresponda |
| `product_id` | Producto relacionado, cuando corresponda |

Categorías disponibles:

- `order`
- `product`
- `sizing`
- `return`
- `refund`
- `other`

Resultados disponibles:

- `answered`
- `needs_information`
- `refund_completed`
- `refund_rejected`

## Flujo de reintegros

La política real se implementa en [`app/store.py`](../app/store.py), no en el prompt del agente.

Antes de modificar una orden, el repositorio valida:

- que la orden exista;
- que pertenezca al correo del cliente;
- que use USD;
- que sea elegible para devolución;
- que el plazo no haya vencido;
- que no haya sido reintegrada anteriormente;
- que la ruta automática o aprobada corresponda al total persistido.

### Reintegro automático

```text
Solicitud completa
    │
    ▼
refund_order_automatically
    │
    ├── elegible y total <= 50,00 ──► reintegro completado
    │
    └── total > 50,00 ──────────────► requiere aprobación
```

### Reintegro con aprobación

```text
refund_order_with_admin_approval
                │
                ▼
          RunStatus.PAUSED
                │
        decisión administrativa
           │                │
       aprobado         rechazado
           │                │
revalidar y mutar   mantener la orden
           │                │
           └──── respuesta determinista ────┘
```

La continuación está implementada en [`app/support_continuations.py`](../app/support_continuations.py). Después de la decisión humana, la respuesta final se construye sin otra llamada al modelo.

## Estados visibles en Support Inbox

| Estado | Significado |
|---|---|
| `completed` | Todos los runs visibles terminaron con respuestas válidas |
| `approval_pending` | Existe un reintegro esperando decisión humana |
| `incomplete` | El thread no tiene todavía una salida completa y válida |

Cuando un envío pausa, el endpoint responde HTTP `202`:

```json
{
  "session_id": "THREAD-1001",
  "run_id": "...",
  "status": "approval_pending"
}
```

La aprobación se resuelve desde AgentOS UI, Slack o `continue_run` por MCP. El cliente debe devolver el requerimiento original con su identificador, no solamente un booleano de confirmación.

## Persistencia

Customer Support utiliza dos capas de persistencia en PostgreSQL.

### Sesiones y runs de AgentOS

Guardan:

- el correo de entrada validado;
- la ejecución del equipo y sus miembros;
- el estado del run;
- los requerimientos de aprobación;
- la respuesta tipada.

### StoreRepository

[`app/store.py`](../app/store.py) administra `store_records` con dos tipos de registro:

- `order`: estado comercial mutable de la orden;
- `support_interaction`: metadata analítica de una interacción completada.

[`app/support_hooks.py`](../app/support_hooks.py) persiste interacciones completadas de forma idempotente usando `message_id`. Si falla la persistencia analítica, registra el error pero no oculta una respuesta válida al cliente.

No se persisten interacciones pausadas ni salidas que no cumplan `CustomerEmailReply`.

## Support Inbox

La API segura vive en [`app/support_inbox.py`](../app/support_inbox.py).

| Endpoint | Resultado |
|---|---|
| `GET /api/support/threads` | Lista resumida de threads |
| `GET /api/support/threads/{session_id}` | Detalle seguro de un thread |
| `POST /api/support/emails` | Procesa un correo simulado |

La API nunca entrega sesiones o runs crudos. Sólo expone campos permitidos mediante `ThreadSummary`, `ThreadDetail` e `InboxMessage`. La metadata de clasificación aparece únicamente en mensajes salientes.

En producción, las rutas requieren el principal de servicio `sa:support-inbox-bff` y scopes separados de lectura y envío.

### Frontend y BFF

- [`frontend/support-inbox/`](../frontend/support-inbox/) contiene la interfaz React.
- [`support-inbox/bff/`](../support-inbox/bff/) contiene el Backend for Frontend desplegable por separado.
- El navegador se autentica contra el BFF y usa protección CSRF.
- El BFF conserva el PAT de AgentOS del lado servidor y valida respuestas antes de entregarlas al frontend.
- Los errores upstream se transforman en mensajes seguros sin filtrar detalles internos.

## Seguridad y límites

1. **Aislamiento de clientes:** una orden sólo se devuelve o modifica si coincide con `customer_email`.
2. **Montos persistidos:** el modelo nunca decide el total del reintegro.
3. **Aprobación humana:** los reintegros superiores al límite no pueden automatizarse.
4. **Revalidación:** una aprobación no evita que la orden se vuelva a validar antes de mutar.
5. **Knowledge aislado:** Product Support no usa la base general de la plataforma.
6. **API allow-listed:** Support Inbox no expone trazas, herramientas ni datos internos del run.
7. **Especialistas privados:** los usuarios interactúan con el equipo, no con sus miembros directamente.
8. **Analítica fail-soft:** una falla de reporting no convierte una respuesta válida en un error para el cliente.

## Cómo probarlo

### Desde AgentOS

Ejecutá el equipo `customer-support` con una entrada JSON:

```json
{
  "message_id": "EMAIL-TEST-1",
  "from_email": "alice@example.test",
  "subject": "Tracking request",
  "body": "Please check ORD-LUMEN-1001."
}
```

`thread_id` es opcional al ejecutar directamente el equipo, pero obligatorio cuando se usa Support Inbox.

### Casos útiles

| Caso | Fixture sugerida | Resultado esperado |
|---|---|---|
| Tracking válido | `ORD-LUMEN-1001` + `alice@example.test` | Respuesta basada en `lookup_order` |
| Orden ajena | `ORD-LUMEN-1001` + otro correo | No revelar la orden |
| Reintegro automático | Orden elegible de hasta USD 50,00 | `refund_completed` sin pausa |
| Reintegro aprobado | Orden elegible superior a USD 50,00 | Pausa y aprobación administrativa |
| Orden ya reintegrada | `ORD-LUMEN-1007` | Rechazo sin segunda mutación |
| Producto conocido | Mosslight Tee | Respuesta desde knowledge |
| Detalle inexistente | Dato ausente del catálogo | Fallback controlado |

### Evals existentes

[`evals/cases.py`](../evals/cases.py) contiene cobertura para:

- routing de tracking y uso de `lookup_order`;
- grounding de talles y precios en el catálogo dedicado;
- informes SQL de Support Insights sin datos inventados.

Para ejecutar el conjunto release:

```bash
python -m evals --tag release
```

Este comando consume llamadas al modelo y debe ejecutarse cuando no haya otros escritores sobre las stores compartidas.

## Archivos principales

| Archivo | Responsabilidad |
|---|---|
| [`teams/customer_support.py`](../teams/customer_support.py) | Coordinación y respuesta final |
| [`agents/order_support.py`](../agents/order_support.py) | Órdenes y tracking |
| [`agents/product_support.py`](../agents/product_support.py) | Productos y talles |
| [`agents/refund_support.py`](../agents/refund_support.py) | Reintegros |
| [`agents/support_insights.py`](../agents/support_insights.py) | Reporting administrativo |
| [`app/support_models.py`](../app/support_models.py) | Contratos y taxonomía |
| [`app/store.py`](../app/store.py) | Persistencia y reglas comerciales |
| [`app/store_knowledge.py`](../app/store_knowledge.py) | Knowledge del catálogo |
| [`app/support_hooks.py`](../app/support_hooks.py) | Persistencia de interacciones |
| [`app/support_continuations.py`](../app/support_continuations.py) | Finalización posterior a aprobaciones |
| [`app/support_inbox.py`](../app/support_inbox.py) | API y DTOs públicos del inbox |
| [`frontend/support-inbox/`](../frontend/support-inbox/) | Interfaz web |
| [`support-inbox/bff/`](../support-inbox/bff/) | Autenticación y proxy seguro |

## Primeras tareas recomendadas

1. Ejecutar un caso de tracking con una fixture válida.
2. Probar que un correo incorrecto no pueda leer una orden ajena.
3. Recorrer un reintegro automático.
4. Recorrer un reintegro que pause y resolverlo desde la UI.
5. Consultar Support Insights después de completar interacciones.
6. Revisar los evals antes de cambiar prompts, taxonomías o políticas de reintegro.
