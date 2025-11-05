"""Seed default projects

Revision ID: 002_seed_projects
Revises: 001_initial_schema
Create Date: 2025-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '002_seed_projects'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed default projects."""
    # Get current timestamp
    now = datetime.utcnow()

    # Insert default projects
    # Note: folder IDs should be updated after initial setup
    op.execute(
        sa.text("""
            INSERT INTO projects (name, drive_folder_id, classification_rules, is_default, created_at)
            VALUES
                ('VNO', 'folder_id_for_vno_replace_me', '[]', 0, :now),
                ('CLIENTE_X', 'folder_id_for_cliente_x_replace_me', '[]', 0, :now),
                ('NOVOS_CLIENTES', 'folder_id_for_novos_clientes_replace_me', '[]', 0, :now),
                ('GERAL', 'folder_id_for_geral_replace_me', '[]', 1, :now)
        """).bindparams(now=now)
    )


def downgrade() -> None:
    """Remove seeded projects."""
    op.execute(
        """
        DELETE FROM projects WHERE name IN ('VNO', 'CLIENTE_X', 'NOVOS_CLIENTES', 'GERAL')
        """
    )
