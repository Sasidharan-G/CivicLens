"""smart duplicate detection

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision="0005";down_revision="0004";branch_labels=None;depends_on=None

def upgrade():
    bind=op.get_bind(); postgres=bind.dialect.name=="postgresql";has_postgis=False;has_vector=False
    if postgres:
        has_postgis=bool(bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='postgis')")))
        has_vector=bool(bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector')")))
        if has_postgis:op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        if has_vector:op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("complaints",sa.Column("image_phash",sa.String(64)))
    op.add_column("complaints",sa.Column("text_embedding",sa.Text()))
    op.create_index("ix_complaints_image_phash","complaints",["image_phash"])
    op.create_table("duplicate_clusters",sa.Column("id",sa.String(36),primary_key=True),sa.Column("primary_complaint_id",sa.String(36),sa.ForeignKey("complaints.id",ondelete="CASCADE"),nullable=False),sa.Column("category",sa.String(60),nullable=False),sa.Column("latitude",sa.Float(),nullable=False),sa.Column("longitude",sa.Float(),nullable=False),sa.Column("member_count",sa.Integer(),nullable=False,server_default="1"),sa.Column("total_support_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("primary_complaint_id"))
    op.create_index("ix_duplicate_clusters_primary_complaint_id","duplicate_clusters",["primary_complaint_id"],unique=True);op.create_index("ix_duplicate_clusters_category","duplicate_clusters",["category"])
    op.create_table("duplicate_cluster_members",sa.Column("id",sa.String(36),primary_key=True),sa.Column("cluster_id",sa.String(36),sa.ForeignKey("duplicate_clusters.id",ondelete="CASCADE"),nullable=False),sa.Column("complaint_id",sa.String(36),sa.ForeignKey("complaints.id",ondelete="CASCADE"),nullable=False),sa.Column("similarity_score",sa.Float(),nullable=False),sa.Column("distance_m",sa.Float(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("cluster_id","complaint_id",name="uq_cluster_complaint"),sa.UniqueConstraint("complaint_id"))
    op.create_index("ix_duplicate_cluster_members_cluster_id","duplicate_cluster_members",["cluster_id"]);op.create_index("ix_duplicate_cluster_members_complaint_id","duplicate_cluster_members",["complaint_id"],unique=True)
    if has_postgis:
        op.execute("ALTER TABLE complaints ADD COLUMN geo geography(Point,4326)")
        op.execute("UPDATE complaints SET geo=ST_SetSRID(ST_MakePoint(longitude,latitude),4326)::geography")
        op.execute("CREATE INDEX ix_complaints_geo_gist ON complaints USING GIST (geo)")
    if postgres:
        op.execute("ALTER TABLE complaints ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || coalesce(category,''))) STORED")
        op.execute("CREATE INDEX ix_complaints_search_gin ON complaints USING GIN (search_vector)")
    if has_vector:
        op.execute("ALTER TABLE complaints ADD COLUMN embedding vector(64)")
        op.execute("CREATE INDEX ix_complaints_embedding_hnsw ON complaints USING hnsw (embedding vector_cosine_ops)")

def downgrade():
    bind=op.get_bind()
    if bind.dialect.name=="postgresql":
        op.execute("ALTER TABLE complaints DROP COLUMN IF EXISTS embedding");op.execute("ALTER TABLE complaints DROP COLUMN IF EXISTS search_vector");op.execute("ALTER TABLE complaints DROP COLUMN IF EXISTS geo")
    op.drop_table("duplicate_cluster_members");op.drop_table("duplicate_clusters");op.drop_index("ix_complaints_image_phash",table_name="complaints");op.drop_column("complaints","text_embedding");op.drop_column("complaints","image_phash")
