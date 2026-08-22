#!/usr/bin/env python3
"""CDK app entrypoint for Multimodal Agentic Architecture on AWS."""

from __future__ import annotations

import aws_cdk as cdk
from infra.stacks.multimodal_agentic_architecture_stack import MultimodalAgenticArchitectureStack


def main() -> None:
    app = cdk.App()
    env = cdk.Environment(
        account=app.node.try_get_context("account") or None,
        region=app.node.try_get_context("region") or None,
    )
    MultimodalAgenticArchitectureStack(
        app,
        app.node.try_get_context("stackName") or "MultimodalAgenticArchitectureStack",
        env=env,
        description="Multimodal Agentic Architecture on AWS.",
    )
    app.synth()


if __name__ == "__main__":
    main()
