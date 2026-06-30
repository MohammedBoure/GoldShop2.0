from .base import ClientCreditBaseMixin
from .manual import ClientCreditManualMixin
from .publish import ClientCreditPublishMixin
from .security import (
    CLIENT_CREDIT_CREATE,
    CLIENT_CREDIT_PUBLISH,
    CLIENT_CREDIT_UPDATE,
    require_credit_permission,
)
from .staging import ClientCreditStagingMixin


class ClientCreditManager(
    ClientCreditManualMixin,
    ClientCreditStagingMixin,
    ClientCreditPublishMixin,
    ClientCreditBaseMixin,
):
    LEGACY_SOURCE = "LEGACY_CLIENT_CREDIT"

    def __init__(self, db_instance):
        self.db = db_instance


__all__ = [
    "ClientCreditManager",
    "CLIENT_CREDIT_CREATE",
    "CLIENT_CREDIT_PUBLISH",
    "CLIENT_CREDIT_UPDATE",
    "require_credit_permission",
]
