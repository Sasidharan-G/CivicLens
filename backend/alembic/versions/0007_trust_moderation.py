"""trust and moderation

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
revision="0007";down_revision="0006";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("users",sa.Column("suspended_at",sa.DateTime(timezone=True)));op.add_column("users",sa.Column("suspension_reason",sa.Text()));op.add_column("users",sa.Column("terms_accepted_at",sa.DateTime(timezone=True)));op.add_column("users",sa.Column("privacy_accepted_at",sa.DateTime(timezone=True)))
    op.add_column("comments",sa.Column("is_hidden",sa.Boolean(),nullable=False,server_default=sa.false()));op.create_index("ix_comments_is_hidden","comments",["is_hidden"])
    op.create_table("moderation_reports",sa.Column("id",sa.String(36),primary_key=True),sa.Column("reporter_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("target_type",sa.String(30),nullable=False),sa.Column("target_id",sa.String(36),nullable=False),sa.Column("reason",sa.String(60),nullable=False),sa.Column("details",sa.Text()),sa.Column("status",sa.String(30),nullable=False,server_default="pending"),sa.Column("reviewed_by_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("review_note",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("reviewed_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("reporter_id","target_type","target_id",name="uq_moderation_reporter_target"))
    for name,column in [("reporter_id","reporter_id"),("target_type","target_type"),("target_id","target_id"),("reason","reason"),("status","status"),("created_at","created_at")]:op.create_index(f"ix_moderation_reports_{name}","moderation_reports",[column])
    op.create_table("user_blocks",sa.Column("id",sa.String(36),primary_key=True),sa.Column("blocker_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("blocked_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("blocker_id","blocked_id",name="uq_user_block"));op.create_index("ix_user_blocks_blocker_id","user_blocks",["blocker_id"]);op.create_index("ix_user_blocks_blocked_id","user_blocks",["blocked_id"])
    op.create_table("suspension_appeals",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("message",sa.Text(),nullable=False),sa.Column("status",sa.String(30),nullable=False,server_default="pending"),sa.Column("reviewed_by_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("review_note",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("reviewed_at",sa.DateTime(timezone=True)));op.create_index("ix_suspension_appeals_user_id","suspension_appeals",["user_id"]);op.create_index("ix_suspension_appeals_status","suspension_appeals",["status"])
def downgrade():
    op.drop_table("suspension_appeals");op.drop_table("user_blocks");op.drop_table("moderation_reports");op.drop_index("ix_comments_is_hidden",table_name="comments");op.drop_column("comments","is_hidden");op.drop_column("users","privacy_accepted_at");op.drop_column("users","terms_accepted_at");op.drop_column("users","suspension_reason");op.drop_column("users","suspended_at")
