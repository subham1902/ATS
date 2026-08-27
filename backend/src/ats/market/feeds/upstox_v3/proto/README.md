# Upstox Market Data Feed V3 protobuf

`MarketDataFeedV3.proto` is pinned to official `upstox/upstox-python` commit
`8fe5aef48d12ec5813a69dfdc38d446bc72b483f`; the upstream file SHA-256 is
`05d5b83b699bdbe6ff5e60a2a7216400e1167c03628dcc0705f2839e4f612af6`.

Regenerate the checked-in Python module from the repository root with:

```powershell
uvx --python 3.11.15 --from grpcio-tools==1.70.0 python -m grpc_tools.protoc `
  -I backend/src/ats/market/feeds/upstox_v3/proto `
  --python_out=backend/src/ats/market/feeds/upstox_v3/proto `
  backend/src/ats/market/feeds/upstox_v3/proto/MarketDataFeedV3.proto
```

The generated module is mechanical output and must not be hand-edited.
