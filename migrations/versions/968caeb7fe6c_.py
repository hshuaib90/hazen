"""empty message

Revision ID: 968caeb7fe6c
Revises: e0d83f3b0cd9
Create Date: 2019-01-02 11:45:14.465713

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = '968caeb7fe6c'
down_revision = 'e0d83f3b0cd9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('acquisition', sa.Column('description', sa.String(length=140), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('acquisition', 'description')
    # ### end Alembic commands ###
