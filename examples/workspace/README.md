# Service mapping fixture

These files are source-analysis fixtures, not running services. Indexing never
imports them or contacts the illustrative broker, cache, or SQL database.

From the project root:

```powershell
npm ci --prefix tools/javascript --ignore-scripts
.\.venv\Scripts\python.exe -m graphscope.analysis workspace examples/workspace/workspace.json --service stock --target app.validate_stock --output reports/workspace-impact.json
```

Expected reverse path: `client/api.renderOrder` calls `client/api.loadStock`, whose
literal HTTP request matches stock's `GET /stock/{item}`, whose handler calls
`app.validate_stock`. Qualified client symbols use dots: `api.renderOrder` and
`api.loadStock`. The HTTP edge is inferred from the declared origin, method and
route pattern; the report carries evidence from both sides.

For messaging impact select stock's `app.publish_order`. The consumer
`consumer.process_order` depends on this producer under the manifest's shared
`demo-orders` broker identity and literal `orders.created` topic. Delivery,
serialization and runtime routing are not proven by this static contract.

Service roots may point to separate local Git repositories. Optional `revision`
fields pin each service to a commit/ref; the default is its current worktree.
