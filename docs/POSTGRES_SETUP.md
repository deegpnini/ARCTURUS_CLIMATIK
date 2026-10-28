# PostgreSQL and PostGIS on WSL

From the project root, run:

```bash
./setup_postgres_wsl.sh
```

The script installs PostgreSQL, PostGIS, and SQLite tools; starts the
PostgreSQL service; creates the `oikos` login role and `arcturus` database if
they do not already exist; and enables the PostGIS extension. The database
role is deliberately not a PostgreSQL superuser.

The application uses PostgreSQL's local Unix socket and peer authentication:
run the Dash app, scheduled writer, and backup as the Linux user `oikos`.
This permits passwordless local access without enabling unauthenticated TCP
connections. To use TCP instead, set `ARCTURUS_DB_HOST` and configure
PostgreSQL authentication securely; do not put a database password in Git.
