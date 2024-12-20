"""Adjust some database

Revision ID: c6ee1b82083b
Revises: d74402c3601d
Create Date: 2024-11-18 19:11:40.619677

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6ee1b82083b'
down_revision = 'd74402c3601d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_read', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_column('is_read')

    # ### end Alembic commands ###
