from dataclasses import dataclass, field

from app.core.exceptions import Forbidden
from app.models import User


@dataclass
class CurrentUser:
    """Authenticated request context. company_id ALWAYS comes from the validated user, never from the client."""
    user: User
    permissions: set[str] = field(default_factory=set)
    jti: str = ""
    token_exp: object = None

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def company_id(self) -> int:
        return self.user.company_id

    @property
    def scoped(self) -> bool:
        """True when the user only sees customers currently assigned to them."""
        return self.user.role.data_scope == "assigned"

    def has(self, code: str) -> bool:
        return code in self.permissions

    def require(self, code: str) -> None:
        if code not in self.permissions:
            raise Forbidden(f"Missing permission: {code}")
