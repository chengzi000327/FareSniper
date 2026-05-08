from alembic import op

revision = "20260520_enable_flags"
down_revision = "20260516_promotions"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE feature_flags SET enabled = true, rollout_pct = 100 "
        "WHERE name IN ('ai_value_judge','multi_platform_aggregation','preference_memory')"
    )


def downgrade():
    op.execute(
        "UPDATE feature_flags SET enabled = false, rollout_pct = 0 "
        "WHERE name IN ('ai_value_judge','multi_platform_aggregation','preference_memory')"
    )
