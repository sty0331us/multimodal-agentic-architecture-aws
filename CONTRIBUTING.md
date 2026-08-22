# Contributing to Multimodal Agentic Architecture on AWS

Thanks for helping improve this project. The canonical repository slug is `multimodal-agentic-architecture-aws`.

## Setup

```bash
git clone https://github.com/<your-username>/multimodal-agentic-architecture-aws.git
cd multimodal-agentic-architecture-aws
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Checks

```bash
ruff check src infra config tests scripts app.py
pytest tests -q -m "not integration and not e2e"
```

Do not commit `.env`, API keys, or stack output secrets. Use `.env.example` as the template.

## Naming

Keep resource names, tags, log groups, and docs aligned with:

- Display name: **Multimodal Agentic Architecture on AWS**
- Project tag / package: `multimodal-agentic-architecture-aws`
- CDK stack: `MultimodalAgenticArchitectureStack`
