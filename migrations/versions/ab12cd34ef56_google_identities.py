"""Add Google identities and short-lived OAuth state; existing accounts unchanged."""
import sqlalchemy as sa
from alembic import op

revision = "ab12cd34ef56"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", "subject", name="uq_auth_identity_subject"),
        sa.UniqueConstraint("provider", "user_id", name="uq_auth_identity_user"),
    )
    op.create_table(
        "google_oauth_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("verifier", sa.String(128), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("return_path", sa.String(1024), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("google_oauth_states")
    op.drop_table("auth_identities")
