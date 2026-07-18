"""notifications and escalation

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
revision="0006";down_revision="0005";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("notifications",sa.Column("kind",sa.String(40),nullable=False,server_default="general"));op.create_index("ix_notifications_kind","notifications",["kind"])
    op.create_table("notification_preferences",sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),sa.Column("email_enabled",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("push_enabled",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("whatsapp_enabled",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("status_alerts",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("nearby_critical_alerts",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("ward_digest",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("push_subscriptions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("endpoint",sa.Text(),nullable=False,unique=True),sa.Column("p256dh",sa.Text(),nullable=False),sa.Column("auth",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("last_used_at",sa.DateTime(timezone=True)));op.create_index("ix_push_subscriptions_user_id","push_subscriptions",["user_id"])
    op.create_table("notification_deliveries",sa.Column("id",sa.String(36),primary_key=True),sa.Column("notification_id",sa.String(36),sa.ForeignKey("notifications.id",ondelete="CASCADE"),nullable=False),sa.Column("channel",sa.String(20),nullable=False),sa.Column("status",sa.String(20),nullable=False,server_default="pending"),sa.Column("error",sa.Text()),sa.Column("attempted_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_notification_deliveries_notification_id","notification_deliveries",["notification_id"]);op.create_index("ix_notification_deliveries_channel","notification_deliveries",["channel"]);op.create_index("ix_notification_deliveries_status","notification_deliveries",["status"])
def downgrade():
    op.drop_table("notification_deliveries");op.drop_table("push_subscriptions");op.drop_table("notification_preferences");op.drop_index("ix_notifications_kind",table_name="notifications");op.drop_column("notifications","kind")
