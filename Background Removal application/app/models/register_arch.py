"""Architecture verification helpers (no weights needed)."""
from __future__ import annotations


def build_u2net_smoke_check(torch=None) -> bool:
    """Instantiate U2-Net and verify a forward pass yields valid output.

    Used by tests and at load-time validation. Never downloads weights.
    """
    import numpy as np

    if torch is None:
        import torch

    from app.models import u2net

    for lite in (False, True):
        net = u2net.build_u2net(lite=lite)
        net.eval()
        with torch.no_grad():
            x = torch.zeros(1, 3, 96, 96)
            out = net(x)
        first = out[0].detach().cpu().numpy()
        if first.shape != (1, 1, 96, 96):
            return False
        if not np.isfinite(first).all():
            return False
    return True