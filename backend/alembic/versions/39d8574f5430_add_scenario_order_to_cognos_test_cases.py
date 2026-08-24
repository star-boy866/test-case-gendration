"""add_scenario_order_to_cognos_test_cases

Revision ID: 39d8574f5430
Revises: 76e5755e462e
Create Date: 2026-08-25 00:07:52.922307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39d8574f5430'
down_revision: Union[str, Sequence[str], None] = '76e5755e462e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'cognos_test_cases',
        sa.Column('scenario_order', sa.Integer(), nullable=True, server_default='0')
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('cognos_test_cases') as batch_op:
        batch_op.drop_column('scenario_order')
