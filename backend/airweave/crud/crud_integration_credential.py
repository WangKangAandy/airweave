"""CRUD operations for integration credentials."""

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.integration_credential import IntegrationCredential
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


class CRUDIntegrationCredential(
    CRUDBaseOrganization[
        IntegrationCredential, IntegrationCredentialCreateEncrypted, IntegrationCredentialUpdate
    ]
):
    """CRUD operations for integration credentials."""


integration_credential = CRUDIntegrationCredential(IntegrationCredential)
