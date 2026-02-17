"""add category classification system

Revision ID: 0011
Revises: 0010
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create schemas table
    op.create_table(
        'schemas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), server_default='', nullable=False),
        sa.Column('json_schema', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_schemas_active', 'schemas', ['is_active'])

    # Create categories table
    op.create_table(
        'categories',
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('intent_description', sa.Text(), nullable=False),
        sa.Column('example_inputs', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('key_outputs', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('name')
    )

    # Create schema_categories junction table
    op.create_table(
        'schema_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schema_id', sa.Integer(), nullable=False),
        sa.Column('category_name', sa.String(50), nullable=False),
        sa.Column('priority', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['schema_id'], ['schemas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_name'], ['categories.name'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schema_id', 'category_name', name='uq_schema_category')
    )
    op.create_index('idx_schema_categories_schema', 'schema_categories', ['schema_id'])
    op.create_index('idx_schema_categories_category', 'schema_categories', ['category_name'])

    # Update incidents table
    op.add_column('incidents', sa.Column('categories', postgresql.JSONB(), server_default='[]', nullable=False))
    op.add_column('incidents', sa.Column('schema_id', sa.Integer(), nullable=True))
    op.add_column('incidents', sa.Column('classification_reasoning', sa.Text(), nullable=True))
    op.create_foreign_key('fk_incidents_schema', 'incidents', 'schemas', ['schema_id'], ['id'], ondelete='SET NULL')
    op.create_index('idx_incidents_categories', 'incidents', ['categories'], postgresql_using='gin')
    op.create_index('idx_incidents_schema', 'incidents', ['schema_id'])


def downgrade() -> None:
    # Drop incidents table modifications
    op.drop_index('idx_incidents_schema', 'incidents')
    op.drop_index('idx_incidents_categories', 'incidents', postgresql_using='gin')
    op.drop_constraint('fk_incidents_schema', 'incidents', type_='foreignkey')
    op.drop_column('incidents', 'classification_reasoning')
    op.drop_column('incidents', 'schema_id')
    op.drop_column('incidents', 'categories')

    # Drop schema_categories table
    op.drop_index('idx_schema_categories_category', 'schema_categories')
    op.drop_index('idx_schema_categories_schema', 'schema_categories')
    op.drop_table('schema_categories')

    # Drop categories table
    op.drop_table('categories')

    # Drop schemas table
    op.drop_index('idx_schemas_active', 'schemas')
    op.drop_table('schemas')
