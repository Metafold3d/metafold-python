# Metafold SDK for Python

## Installation

```
pip install metafold
```

## Usage

```
from metafold import MetafoldClient

access_token = "..."
project_id = "123"

metafold = MetafoldClient(access_token, project_id)

assets = metafold.assets.list()
print(assets[0].name)

asset = metafold.assets.get("123")
print(asset.name)
```

Read the [documentation][] for more info or play around with one of the
[examples](examples).

[documentation]: https://Metafold3d.github.io/metafold-python/
