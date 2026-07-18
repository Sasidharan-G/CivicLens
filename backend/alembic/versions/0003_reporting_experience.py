"""phase two reporting experience

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
revision="0003";down_revision="0002";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("complaints",sa.Column("is_anonymous",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column("complaints",sa.Column("hide_exact_location",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table("complaint_media",sa.Column("id",sa.String(36),primary_key=True),sa.Column("complaint_id",sa.String(36),sa.ForeignKey("complaints.id",ondelete="CASCADE"),nullable=False),sa.Column("url",sa.String(500),nullable=False),sa.Column("public_id",sa.String(200)),sa.Column("media_type",sa.String(30),nullable=False),sa.Column("mime_type",sa.String(80),nullable=False),sa.Column("uploaded_by_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_complaint_media_complaint_id","complaint_media",["complaint_id"])
def downgrade():
    op.drop_table("complaint_media");op.drop_column("complaints","hide_exact_location");op.drop_column("complaints","is_anonymous")
