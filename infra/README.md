# Mimic Infrastructure

Terraform + Pulumi modules for the runtime stack.

## Components (Plan §4.3)

| Service | Purpose |
|---|---|
| Temporal Cloud | Durable workflow runtime (self-host fallback) |
| Modal | GPU/CPU burst for MC shards (per-second billing, preferred) |
| Ray Serve | Alternative compute |
| Harbor or GHCR | OCI artifact registry — Mimic Hub backend |
| Sigstore (Fulcio + Rekor) | Signing + transparency log |
| Postgres | Hub metadata + run logs |
| S3 / R2 | Object storage |
| OpenTelemetry → Tempo/Honeycomb | Tracing |

## Layout

```
infra/
├── terraform/        # Cloud resources (Temporal Cloud, RDS, R2, Modal accounts)
├── modal/            # Modal app definitions + GPU image (mimic/runtime:gpu)
└── README.md
```

## The pinned GPU runtime image

`mimic/runtime:gpu` pins (Plan §7.4):

- CUDA 12.4, cuDNN 9.x
- PyTorch 2.5.x with `torch.use_deterministic_algorithms(True)`
- BFloat16 forced; FP16 forbidden without explicit flag
- vLLM in batch-invariant mode

If a user runs outside this image, `mimic.framework.determinism.check_env()` warns and
refuses to emit a `world_state_hash`.
