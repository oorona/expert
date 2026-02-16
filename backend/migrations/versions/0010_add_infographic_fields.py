"""add infographic fields to incidents

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('incidents', sa.Column('infographic_data', sa.Text(), nullable=True))
    op.add_column('incidents', sa.Column('infographic_prompt', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('incidents', 'infographic_prompt')
    op.drop_column('incidents', 'infographic_data')
