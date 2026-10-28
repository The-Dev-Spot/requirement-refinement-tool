"""Delivery limits must not weaken evidence, coverage or exact-byte approval."""
import copy
import io
import json
import unittest
import zipfile

from clarity.guardrails import ValidationError
from clarity.refine.checks import check, feature_index
from clarity.refine.contracts import DEFAULT_POLICY
from clarity.refine.handoff import archive
from clarity.refine.payload import payload_metrics, requirement_text
from clarity.refine.worker import request_packet
from refine_fixtures import REFERENCE, assessment, sample
from test_refine_controller import Fixture, PARSER


def with_scenarios(value, count):
    """Add synthetic, fully mapped cases; they are not semantic-quality claims."""
    for n in range(5, count + 1):
        sid = 'SC' + str(n)
        value['feature'] += ('\n  @case_' + sid + '\n  Scenario: Synthetic cancellation case ' + str(n)
                             + '\n    Given a confirmed booking owned by Alice starts at 12:00'
                               '\n    When Alice requests cancellation before 12:00'
                               '\n    Then the booking status is cancelled\n')
        mapping = {**value['scenarios'][0], 'id': sid}
        value['scenarios'].append(mapping)
        for row in value['coverage']:
            if row['statement_id'] in mapping['statement_ids'] and row['category'] == mapping['category']:
                row['scenario_ids'].append(sid)
    return value


def sized(value, total):
    # Comments preserve grammar and make it possible to test exact character
    # boundaries without inventing extra acceptance behavior.
    current = payload_metrics(value, None)['delivery_characters']
    value['feature'] += '\n# ' + 'x' * (total - current - 3)
    assert payload_metrics(value, None)['delivery_characters'] == total
    return value


class CompactTextTests(unittest.TestCase):
    def test_every_statement_is_preserved_and_audit_scaffolding_is_absent(self):
        value = sample(); before = copy.deepcopy(value)
        rendered = requirement_text(value)
        self.assertIn('[acceptance.feature](acceptance.feature)', rendered)
        for statement in value['statements']:
            self.assertIn(statement['text'], rendered)
            self.assertNotIn('### ' + statement['id'], rendered)
        self.assertNotIn('Sources: POLICY1', rendered)
        self.assertEqual(value, before)

    def test_optional_build_data_and_dependencies_are_not_cut(self):
        value = sample()
        for kind, body in [('definition', 'A booking is a confirmed reservation.'),
                           ('constraint', '| Host | Port |\n| --- | --- |\n| example.test | 443 |'),
                           ('dependency', 'The identity service must be available.')]:
            value['statements'].append({'id': kind, 'kind': kind, 'text': body, 'citations': []})
        rendered = requirement_text(value)
        for statement in value['statements']:
            self.assertIn(statement['text'], rendered)
        self.assertIn('## Dependencies', rendered)
        self.assertNotIn('## Sources', rendered)


@unittest.skipUnless(PARSER, 'official Gherkin parser is required')
class BudgetTests(unittest.TestCase):
    def checked(self, value):
        return check(value, {'POLICY1': REFERENCE['source']}, DEFAULT_POLICY)

    def test_eight_scenarios_pass_budget_and_nine_block(self):
        for count in (8, 9):
            checked = self.checked(with_scenarios(sample(), count))
            self.assertEqual(checked['payload_metrics']['scenario_count'], count)
            failures = [f for f in checked['findings'] if f['code'] == 'ac_budget']
            self.assertEqual(bool(failures), count == 9)
            if failures: self.assertEqual(failures[0]['severity'], 'blocker')

    def test_outline_counts_once_and_preserves_expanded_cases(self):
        index = feature_index(sample()['feature'])
        self.assertEqual(payload_metrics(sample(), index)['scenario_count'], 4)
        self.assertEqual(index['compiled_cases'], 6)

    def test_exact_size_boundaries(self):
        for count, expected in [(8_000, None), (10_000, None), (10_001, 'warning'),
                                (20_000, 'warning'), (20_001, 'blocker')]:
            checked = self.checked(sized(sample(), count))
            self.assertEqual(checked['payload_metrics']['delivery_characters'], count)
            findings = [f['severity'] for f in checked['findings'] if f['code'] == 'payload_size']
            self.assertEqual(findings, [] if expected is None else [expected])

    def test_both_files_and_unicode_are_measured_without_truncation(self):
        value = sample(); value['statements'][0]['text'] += ' café 日本語'
        checked = self.checked(value); metrics = checked['payload_metrics']
        self.assertEqual(metrics['delivery_characters'], len(requirement_text(value)) + len(value['feature']))
        self.assertGreater(len(requirement_text(value).encode()), metrics['requirement_characters'])
        value = sized(value, 20_001); before = copy.deepcopy(value)
        self.checked(value)
        self.assertEqual(value, before)

    def test_invalid_feature_still_has_size_check(self):
        value = sized(sample(), 20_001); value['feature'] = 'invalid grammar' + value['feature']
        checked = self.checked(value)
        self.assertIsNone(checked['payload_metrics']['scenario_count'])
        self.assertTrue({'invalid_gherkin', 'payload_size'} <= {f['code'] for f in checked['findings']})


@unittest.skipUnless(PARSER, 'official Gherkin parser is required')
class LeanControllerTests(Fixture):
    def test_hard_budget_cannot_be_waived_or_approved(self):
        value = with_scenarios(self.confirmed(), 9)
        self.c.submit(self.a, 'REQ1', self.version(), value)
        result = self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        self.assertEqual(result['review']['quality']['verdict'], 'NOT READY')
        with self.assertRaises(ValidationError): self.c.plan(self.o, 'REQ1')
        report = assessment(value)
        report['warning_resolutions'] = {f['id']: 'A reviewer cannot waive an objective acceptance-scenario budget.'
                                         for f in result['checks']['findings'] if f['code'] == 'ac_budget'}
        with self.assertRaises(ValidationError): self.c.review(self.r, 'REQ1', self.version(), report)

    def test_sealed_compact_text_and_full_evidence_share_exact_approval(self):
        value = self.confirmed(); value['feature'] = value['feature'].replace('\n', '\r\n')
        self.c.submit(self.a, 'REQ1', self.version(), value)
        self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        plan = self.c.plan(self.o, 'REQ1')
        self.assertEqual(plan['files']['requirement.md'], requirement_text(value))
        approved = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        bundle = self.c.seal(self.o, 'REQ1', approved['approval_id'])
        for full in (False, True):
            with zipfile.ZipFile(io.BytesIO(archive(bundle, full_audit=full))) as z:
                self.assertEqual(z.read('acceptance.feature'), value['feature'].encode())
                self.assertEqual(z.read('requirement.md').decode(), requirement_text(value))
                if full:
                    self.assertEqual(json.loads(z.read('traceability.json'))['statements'], value['statements'])
                    self.assertIn('POLICY1', json.loads(z.read('sources.json'))['sources'])
                    self.assertIn('quality-review.json', z.namelist())
                else:
                    self.assertEqual(set(z.namelist()), {'requirement.md', 'acceptance.feature'})

    def test_author_and_reviewer_receive_lean_contract(self):
        self.ready(); status = self.status()
        for stage in ('draft', 'revise'):
            instruction = request_packet(status, stage)['instruction']
            self.assertIn('maximum 8', instruction)
            self.assertIn('never silently remove scope', instruction)
        packet = request_packet(status, 'review')
        self.assertIn('cold_read', packet['instruction'])
        self.assertIn('concrete unanswered questions', packet['instruction'])
        self.assertEqual(packet['draft']['feature'], status['draft']['feature'])


if __name__ == '__main__':
    unittest.main()
