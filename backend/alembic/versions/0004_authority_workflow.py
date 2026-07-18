"""authority workflow

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
revision="0004";down_revision="0003";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("users",sa.Column("department",sa.String(120)));op.add_column("users",sa.Column("ward_scope",sa.String(200)))
    op.add_column("complaints",sa.Column("sla_due_at",sa.DateTime(timezone=True)));op.add_column("complaints",sa.Column("resolution_summary",sa.Text()));op.add_column("complaints",sa.Column("citizen_confirmed_at",sa.DateTime(timezone=True)));op.add_column("complaints",sa.Column("reopened_count",sa.Integer(),nullable=False,server_default="0"));op.create_index("ix_complaints_sla_due_at","complaints",["sla_due_at"])
    op.create_table("internal_notes",sa.Column("id",sa.String(36),primary_key=True),sa.Column("complaint_id",sa.String(36),sa.ForeignKey("complaints.id",ondelete="CASCADE"),nullable=False),sa.Column("author_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_internal_notes_complaint_id","internal_notes",["complaint_id"]);op.create_index("ix_internal_notes_created_at","internal_notes",["created_at"])
def downgrade():
    op.drop_table("internal_notes");op.drop_index("ix_complaints_sla_due_at",table_name="complaints");op.drop_column("complaints","reopened_count");op.drop_column("complaints","citizen_confirmed_at");op.drop_column("complaints","resolution_summary");op.drop_column("complaints","sla_due_at");op.drop_column("users","ward_scope");op.drop_column("users","department")
