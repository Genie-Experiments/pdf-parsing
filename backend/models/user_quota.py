from sqlmodel import Field, SQLModel


class UserQuota(SQLModel, table=True):
    """
    Per-user page quota.  One row per user, keyed by email.
    Admins can adjust page_quota directly in the DB:
        UPDATE user_quota SET page_quota = 50 WHERE email = 'user@example.com';
    """

    __tablename__ = "user_quota"

    email: str = Field(primary_key=True)
    page_quota: int = Field(
        default=10, description="Maximum pages this user may process in total."
    )
    pages_used: int = Field(
        default=0, description="Cumulative pages consumed across all jobs."
    )
