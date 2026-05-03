from contextlib import contextmanager

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from flowboard.config import DATABASE_URL, DB_PATH

if DATABASE_URL:
    # Railway supplies postgres://...; SQLAlchemy needs postgresql://
    _url = DATABASE_URL.replace("postgres://", "postgresql://", 1) if DATABASE_URL.startswith("postgres://") else DATABASE_URL
    engine = create_engine(_url, echo=False)
else:
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _connection_record) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def init_db() -> None:
    from sqlalchemy import inspect

    from flowboard.db import models

    if not DATABASE_URL:
        # SQLite-only migrations for existing local databases.
        with engine.connect() as conn:
            insp = inspect(conn)
            if insp.has_table("asset"):
                cols = {c["name"] for c in insp.get_columns("asset")}
                if "url" not in cols:
                    models.Asset.__table__.drop(conn, checkfirst=True)
                    conn.commit()
            if insp.has_table("edge"):
                edge_cols = {c["name"] for c in insp.get_columns("edge")}
                if "source_variant_idx" not in edge_cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE edge ADD COLUMN source_variant_idx INTEGER"
                    )
                    conn.commit()

    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session():
    with Session(engine) as session:
        yield session
