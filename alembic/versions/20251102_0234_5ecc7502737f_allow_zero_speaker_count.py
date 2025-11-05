"""allow_zero_speaker_count

Revision ID: 5ecc7502737f
Revises: 002_seed_projects
Create Date: 2025-11-02 02:34:56.611770

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ecc7502737f'
down_revision: Union[str, None] = '002_seed_projects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old constraint that required speaker_count > 0
    with op.batch_alter_table('transcripts', schema=None) as batch_op:
        batch_op.drop_constraint('speaker_count_positive', type_='check')
        batch_op.create_check_constraint('speaker_count_non_negative', 'speaker_count >= 0')


def downgrade() -> None:
    # Restore the old constraint
    with op.batch_alter_table('transcripts', schema=None) as batch_op:
        batch_op.drop_constraint('speaker_count_non_negative', type_='check')
        batch_op.create_check_constraint('speaker_count_positive', 'speaker_count > 0')
