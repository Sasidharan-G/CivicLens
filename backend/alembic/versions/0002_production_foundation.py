"""production foundation

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
revision="0002";down_revision="0001";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("users",sa.Column("is_email_verified",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table("auth_tokens",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("token_hash",sa.String(64),nullable=False),sa.Column("purpose",sa.String(30),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("used_at",sa.DateTime(timezone=True)),sa.Column("revoked_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_auth_tokens_user_id","auth_tokens",["user_id"]);op.create_index("ix_auth_tokens_token_hash","auth_tokens",["token_hash"],unique=True);op.create_index("ix_auth_tokens_purpose","auth_tokens",["purpose"]);op.create_index("ix_auth_tokens_expires_at","auth_tokens",["expires_at"])
    op.create_table("audit_logs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("actor_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("action",sa.String(100),nullable=False),sa.Column("entity_type",sa.String(60)),sa.Column("entity_id",sa.String(60)),sa.Column("metadata_json",sa.Text()),sa.Column("ip_address",sa.String(64)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_audit_logs_actor_id","audit_logs",["actor_id"]);op.create_index("ix_audit_logs_action","audit_logs",["action"]);op.create_index("ix_audit_logs_entity_id","audit_logs",["entity_id"]);op.create_index("ix_audit_logs_created_at","audit_logs",["created_at"])
    op.create_table("geocode_cache",sa.Column("id",sa.String(36),primary_key=True),sa.Column("cache_key",sa.String(80),nullable=False),sa.Column("latitude",sa.Float(),nullable=False),sa.Column("longitude",sa.Float(),nullable=False),sa.Column("response_json",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_geocode_cache_cache_key","geocode_cache",["cache_key"],unique=True);op.create_index("ix_geocode_cache_created_at","geocode_cache",["created_at"])
def downgrade():
    op.drop_table("geocode_cache");op.drop_table("audit_logs");op.drop_table("auth_tokens");op.drop_column("users","is_email_verified")

