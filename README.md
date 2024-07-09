# Metafold SDK for Python

[![PyPi](https://img.shields.io/pypi/v/metafold.svg)](https://pypi.python.org/pypi/metafold)

> [!IMPORTANT]
> Until the package is at major version one (1.x.x) the API should be considered unstable.

## Installation

```
pip install metafold
```

## Usage

```python
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
