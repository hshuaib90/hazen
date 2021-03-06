"""empty message

Revision ID: e0d83f3b0cd9
Revises: 9c6384cd2c43
Create Date: 2019-01-02 11:34:37.483994

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e0d83f3b0cd9'
down_revision = '9c6384cd2c43'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('acquisition', sa.Column('files', sa.Integer(), nullable=True))
    op.add_column('acquisition', sa.Column('series_instance_uid', sa.String(length=140), nullable=True))
    op.drop_index('ix_acquisition_timestamp', table_name='acquisition')
    op.drop_column('acquisition', 'body')
    op.drop_column('acquisition', 'timestamp')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('acquisition', sa.Column('timestamp', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
    op.add_column('acquisition', sa.Column('body', sa.VARCHAR(length=140), autoincrement=False, nullable=True))
    op.create_index('ix_acquisition_timestamp', 'acquisition', ['timestamp'], unique=False)
    op.drop_column('acquisition', 'series_instance_uid')
    op.drop_column('acquisition', 'files')
    # ### end Alembic commands ###
