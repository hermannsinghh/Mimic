"""mimic-hub-client — Apache-2.0 SDK for the Mimic Hub scenario registry.

The Hub server is AGPL-3.0; this client is permissively licensed so that any
application can depend on it without inheriting AGPL terms.
"""
from .client import HubClient, HubError, ScenarioManifest

__all__ = ["HubClient", "HubError", "ScenarioManifest"]
