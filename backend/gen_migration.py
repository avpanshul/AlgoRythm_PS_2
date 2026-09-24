import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alembic.config import Config
from alembic import command
import app.core.config
app.core.config.settings.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
import app.core.database
app.core.database.engine = app.core.database.create_engine("sqlite:///:memory:")

alembic_cfg = Config("alembic.ini")
alembic_cfg.set_main_option("sqlalchemy.url", "sqlite:///:memory:")
command.revision(alembic_cfg, message="Auto-generated migration", autogenerate=True)
