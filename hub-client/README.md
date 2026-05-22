# mimic-hub-client

Apache-2.0 SDK for talking to a [Mimic Hub](../hub/) instance.

The hub itself is AGPL-3.0 (server-side); this client is intentionally a
separate package under a permissive license so any application can depend on
it without inheriting the hub's AGPL terms.

## Install

```bash
pip install mimic-hub-client
```

## Use

```python
from hub_client import HubClient

client = HubClient(base_url="https://hub.mimic.ai")

# Search for scenarios
results = client.search(query="svb", tier="T1")

# Fetch a manifest (signed) and pull the OCI artifact
manifest = client.get_scenario("svb-replay-2023:0.1.0")
client.pull(manifest, dest_dir="./fetched")

# Publish (requires API key)
client.publish(scenario_dir="./scenarios/my-scenario", api_key="...")
```
