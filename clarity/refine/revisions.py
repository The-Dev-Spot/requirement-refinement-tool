"""Digest-bound edits assembled into a complete draft before normal validation."""
import copy

from ..guardrails import digest
from .contracts import CATEGORIES, draft, fields, items, require


def apply_revision(current, value):
    fields(value, {'base_draft_digest', 'title', 'statements', 'feature', 'scenarios', 'coverage', 'proposals'}, 'targeted revision')
    require(value['base_draft_digest'] == digest(current), 'Revision base changed; retrieve a fresh task')
    result = copy.deepcopy(current)
    for key in ('title', 'feature', 'proposals'):
        if value[key] is not None:
            result[key] = value[key]
    for key in ('statements', 'scenarios', 'coverage'):
        change = fields(value[key], {'upsert', 'remove'}, key + ' changes')
        upserts = items(change['upsert'], key + ' upserts', 800)
        removed = items(change['remove'], key + ' removals', 800)
        def identity(item):
            require(isinstance(item, dict), 'Invalid revision item')
            if key == 'coverage':
                require(isinstance(item.get('statement_id'), str) and item.get('category') in CATEGORIES, 'Invalid coverage identity')
                return (item['statement_id'], item['category'])
            require(isinstance(item.get('id'), str), 'Missing revision item ID')
            return item['id']
        removal_ids = []
        for item in removed:
            if key == 'coverage':
                fields(item, {'statement_id', 'category'}, 'coverage removal')
                removal_ids.append(identity(item))
            else:
                require(isinstance(item, str), 'Invalid removal ID')
                removal_ids.append(item)
        replacement_ids = [identity(item) for item in upserts]
        require(len(set(removal_ids)) == len(removal_ids) and len(set(replacement_ids)) == len(replacement_ids), 'Duplicate revision operation')
        require(not set(removal_ids) & set(replacement_ids), 'Cannot remove and replace the same item')
        originals = {identity(item): item for item in result[key]}
        require(set(removal_ids) <= set(originals), 'Revision removes an unknown item')
        replacements = dict(zip(replacement_ids, upserts))
        result[key] = [replacements.pop(identity(item), item) for item in result[key] if identity(item) not in removal_ids]
        result[key].extend(replacements.values())
    result = draft(result)
    require(digest(result) != digest(current), 'Revision made no changes; no new draft was recorded')
    return result
