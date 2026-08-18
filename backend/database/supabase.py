import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL


SUPABASE_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.environ["SUPABASE_DB_USER"],
    password=os.environ["SUPABASE_DB_PASSWORD"],
    host=os.environ["SUPABASE_DB_HOST"],
    port=int(os.environ["SUPABASE_DB_PORT"]),
    database=os.environ["SUPABASE_DB_NAME"],
)

supabase_engine = create_engine(
    SUPABASE_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "prepare_threshold": None,
    },
)