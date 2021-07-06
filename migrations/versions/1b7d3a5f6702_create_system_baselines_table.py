"""create system_baselines table

Revision ID: 1b7d3a5f6702
Revises:
Create Date: 2019-06-19 09:56:21.450626

"""
import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "1b7d3a5f6702"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "system_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account", sa.String(length=10), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("created_on", sa.DateTime(), nullable=True),
        sa.Column("modified_on", sa.DateTime(), nullable=True),
        sa.Column("baseline_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("system_baselines")
    # ### end Alembic commands ###
