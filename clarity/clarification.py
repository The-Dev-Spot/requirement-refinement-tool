"""Load the same PO clarification contract for editor and executable workflows."""
from pathlib import Path

from .guardrails import ValidationError


def clarification_contract() -> str:
    package = Path(__file__).resolve().parent
    root = package.parent
    path = (root / '.github/skills/po-clarification/SKILL.md'
            if (root / 'pyproject.toml').is_file()
            else package / 'resources/po-clarification.md')
    try:
        content = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise ValidationError('The shared PO clarification contract is missing') from exc
    # Host discovery metadata is not part of the model's task instructions.
    if content.startswith('---\n'):
        parts = content.split('\n---\n', 1)
        if len(parts) != 2:
            raise ValidationError('The shared PO clarification contract is malformed')
        content = parts[1]
    if not content.strip():
        raise ValidationError('The shared PO clarification contract is empty')
    return content.strip()
