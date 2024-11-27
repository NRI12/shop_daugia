"""Add some filed

Revision ID: 2ffe0ca0d420
Revises: 72935a90bb77
Create Date: 2024-11-18 15:45:14.519736

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2ffe0ca0d420'
down_revision = '72935a90bb77'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('auctions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('auctions', schema=None) as batch_op:
        batch_op.drop_column('created_at')

    # ### end Alembic commands ###