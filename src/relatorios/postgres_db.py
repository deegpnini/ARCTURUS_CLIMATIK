import os


def postgres_connection_params():
    params = {
        "dbname": os.getenv("ARCTURUS_DB_NAME", "arcturus"),
        "user": os.getenv("ARCTURUS_DB_USER", "oikos"),
    }
    host = os.getenv("ARCTURUS_DB_HOST")
    port = os.getenv("ARCTURUS_DB_PORT")
    password = os.getenv("ARCTURUS_DB_PASSWORD")
    if host:
        params["host"] = host
    if port:
        params["port"] = port
    if password:
        params["password"] = password
    return params


def get_postgres_connection():
    import psycopg2

    return psycopg2.connect(**postgres_connection_params())
