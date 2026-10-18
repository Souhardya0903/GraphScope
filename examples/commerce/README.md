# Synthetic commerce fixture

For mapping and impact analysis, use the dashboard or CLI described in the
[project README](../../README.md). This application does not need to run for analysis.

To run the synthetic application itself, execute from the repository root:


```powershell
.\.venv\Scripts\python.exe -m uvicorn examples.commerce.app:app --reload --port 8090
```

In a separate terminal, run its behavior tests:

```powershell
.\.venv\Scripts\python.exe -m pytest examples/commerce/tests -q
```

Open <http://localhost:8090/docs> to call the routes. For either POST route use:

```json
{"product_id": "keyboard", "quantity": 2}
```

Known dependency paths:

```text
POST /orders -> orders.create_order -> orders.place_order -> inventory.validate_stock
POST /reservations -> reservations.reserve_stock -> inventory.validate_stock
inventory.validate_stock -> inventory.read_inventory -> redis_adapter.read_stock
GET /products -> products.list_products
```

`app.py` mounts three APIRouters without prefixes. Imports within this package are
relative; the extractor resolves these and the router includes. Products have no
application call path to inventory. `dispatch.dispatch` deliberately invokes
`getattr(handlers, event_name)()`; never guess its target during extraction.
Framework calls and other unsupported call sites may also remain unresolved.

The Redis adapter uses fixed in-memory stock, makes no network connections, and
does not modify stock. Orders and reservations are synthetic validation responses,
not persisted transactions. This adapter is a fake boundary, not a real Redis service.
Use the workspace fixture for a literal Redis/cache resource example. Tests require neither
Redis, FalkorDB, nor model credentials. Ingestion must parse this application
without importing it or running its tests.
