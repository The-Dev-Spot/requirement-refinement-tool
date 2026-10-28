import copy
import importlib.util
import unittest
from clarity.guardrails import ValidationError, digest
from clarity.refine import contracts, checks
from clarity.refine.benchmark import evaluate
from refine_fixtures import REFERENCE, ROOT, sample, assessment
import json

PARSER = importlib.util.find_spec('gherkin') is not None


class ContractTests(unittest.TestCase):
    def test_valid_strict_draft(self):
        self.assertEqual(contracts.draft(sample()), sample())

    def test_detached_snapshot(self):
        value = sample(); stored = contracts.draft(value); value['title'] = 'Changed'
        self.assertNotEqual(stored['title'], value['title'])

    def test_unknown_fields_and_self_selected_policy_rejected(self):
        for name in ('risk_ids', 'canonical_steps', 'quality_override', 'experience', 'approved'):
            value = sample(); value[name] = True
            with self.subTest(name=name), self.assertRaises(ValidationError): contracts.draft(value)

    def test_boolean_version_rejected(self):
        value = sample(); value['version'] = True
        with self.assertRaises(ValidationError): contracts.draft(value)

    def test_duplicate_statement_rejected(self):
        value = sample(); value['statements'].append(value['statements'][0])
        with self.assertRaises(ValidationError): contracts.draft(value)

    def test_duplicate_mapping_rejected(self):
        value = sample(); value['scenarios'].append(value['scenarios'][0])
        with self.assertRaises(ValidationError): contracts.draft(value)

    def test_coverage_xor(self):
        value = sample(); value['coverage'][0]['not_applicable_reason'] = 'This is not applicable to the confirmed business scope.'
        with self.assertRaises(ValidationError): contracts.draft(value)

    def test_coverage_reason_cannot_be_empty(self):
        value = sample(); value['coverage'][0].update(scenario_ids=[], not_applicable_reason='N/A')
        with self.assertRaises(ValidationError): contracts.draft(value)

    def test_bad_source_hash_rejected(self):
        value = sample(); value['statements'][0]['citations'][0]['source_digest'] = 'made-up'
        with self.assertRaises(ValidationError): contracts.draft(value)

    def test_missing_semantic_check_rejected(self):
        value = sample(); report = assessment(value); del report['checks']['cold_read']
        with self.assertRaises(ValidationError): contracts.review(report, value, digest(value))

    def test_every_statement_and_scenario_needs_review(self):
        for key in ('statement_support', 'scenario_fidelity'):
            value = sample(); report = assessment(value); report[key].pop(next(iter(report[key])))
            with self.assertRaises(ValidationError): contracts.review(report, value, digest(value))

    def test_stale_semantic_review_rejected(self):
        value = sample(); report = assessment(value); report['draft_digest'] = '0' * 64
        with self.assertRaises(ValidationError): contracts.review(report, value, digest(value))

    def test_short_or_unrecognized_review_is_not_pass(self):
        for result in ({'status': 'PASS', 'rationale': 'fine'}, {'status': 'probably', 'rationale': 'A sufficiently long explanation for a synthetic test'}):
            value = sample(); report = assessment(value); report['checks']['cold_read'] = result
            with self.assertRaises(ValidationError): contracts.review(report, value, digest(value))

    def test_invalid_ambiguity_reference_rejected(self):
        value = sample(); report = assessment(value)
        report['ambiguities'] = [{'statement_ids': ['UNKNOWN'], 'interpretation_a': 'first', 'interpretation_b': 'second', 'material_difference': 'different billing'}]
        with self.assertRaises(ValidationError): contracts.review(report, value, digest(value))

    def test_policy_bounds(self):
        for key, value in (('max_rewrites', True), ('max_rewrites', 100), ('max_model_calls', 0), ('version', True)):
            config = copy.deepcopy(contracts.DEFAULT_POLICY); config[key] = value
            with self.assertRaises(ValidationError): contracts.policy(config)


class ProvenanceTests(unittest.TestCase):
    def flags(self, value, sources=None):
        return {f['code'] for f in checks.check(value, sources or {'POLICY1': REFERENCE['source']}, contracts.DEFAULT_POLICY)['findings']}

    def test_fabricated_quote_fails(self):
        value = sample(); value['statements'][0]['citations'][0]['quote'] = 'A statement never present in the source.'
        self.assertIn('fabricated_quote', self.flags(value))

    def test_stale_source_revision_fails(self):
        value = sample(); value['statements'][0]['citations'][0]['source_digest'] = '0' * 64
        self.assertIn('stale_or_missing_source', self.flags(value))

    def test_reference_without_authority_is_not_a_requirement(self):
        source = copy.deepcopy(REFERENCE['source']); source['authority'] = None
        source['digest'] = digest({k: v for k, v in source.items() if k != 'digest'})
        self.assertIn('unconfirmed_authority', self.flags(sample(source), {'POLICY1': source}))

    def test_no_citation_cannot_hide_unsupported_scope(self):
        value = sample(); value['statements'][3]['citations'] = []
        self.assertIn('unsupported_statement', self.flags(value))

    def test_duplicate_citation_flagged(self):
        value = sample(); value['statements'][0]['citations'] *= 2
        self.assertIn('duplicate_citation', self.flags(value))

    def test_missing_negative_and_boundary_coverage(self):
        for category in ('negative', 'boundary'):
            value = sample(); value['coverage'] = [r for r in value['coverage'] if r['category'] != category]
            self.assertIn('missing_coverage', self.flags(value))

    def test_every_category_cannot_be_declared_inapplicable(self):
        value = sample()
        for row in value['coverage']:
            row.update(scenario_ids=[], not_applicable_reason='A synthetic claim that all these categories are inapplicable.')
        self.assertIn('untested_rule', self.flags(value))

    def test_coverage_cannot_reference_other_scenarios(self):
        value = sample(); value['coverage'][0]['scenario_ids'] = ['SC2']
        self.assertIn('incorrect_coverage', self.flags(value))

    def test_scenarios_cannot_claim_support_from_problem_instead_of_rule(self):
        value = sample(); value['scenarios'][0]['statement_ids'] = ['BR1']
        self.assertIn('invalid_scenario_support', self.flags(value))

    def test_proposals_always_block_handoff(self):
        value = sample(); value['proposals'] = ['Assume cancellation is allowed after the booking starts.']
        self.assertIn('unconfirmed_proposal', self.flags(value))

    def test_missing_value_or_scope_flagged(self):
        value = sample(); value['statements'] = [s for s in value['statements'] if s['kind'] != 'value']
        self.assertIn('missing_section', self.flags(value))

    def test_signals_are_not_a_claim_of_attack(self):
        found = checks.signals({'requirement': 'The application must never reveal the password.'})
        self.assertEqual(found[0]['severity'], 'security')
        self.assertNotIn('password', found[0]['message'])

    def test_signal_is_bound_to_exact_text_and_location(self):
        a = checks.signals({'a': 'Never reveal the password.'})
        b = checks.signals({'b': 'Never reveal the password.'})
        self.assertNotEqual(a[0]['id'], b[0]['id'])

    def test_missing_parser_cannot_yield_ready_machine_result(self):
        from unittest.mock import patch
        with patch('clarity.refine.checks.feature_index', side_effect=ImportError):
            self.assertIn('parser_not_run', self.flags(sample()))


@unittest.skipUnless(PARSER, 'Official parser dependency unavailable locally; CI must run these tests')
class GherkinTests(unittest.TestCase):
    def test_real_parser_and_outline_expansion(self):
        result = checks.feature_index(sample()['feature'])
        self.assertEqual(len(result['scenarios']), 4)
        self.assertEqual(result['compiled_cases'], 6)

    def test_aliases_are_supported(self):
        feature = sample()['feature'].replace('Scenario:', 'Example:').replace('Scenario Outline:', 'Scenario Template:')
        self.assertEqual(checks.feature_index(feature)['compiled_cases'], 6)

    def test_rule_blocks_are_supported(self):
        feature = sample()['feature'].splitlines()
        feature = feature[:1] + ['', '  Rule: Owner cancellation policy'] + ['  ' + line for line in feature[1:]]
        self.assertEqual(checks.feature_index('\n'.join(feature))['compiled_cases'], 6)

    def test_background_supplies_context(self):
        feature = 'Feature: Example\n  Background:\n    Given a confirmed booking exists\n  @case_SC1\n  Scenario: Example\n    When its owner cancels\n    Then it is cancelled\n'
        self.assertEqual(checks.feature_index(feature)['compiled_cases'], 1)

    def test_each_scenario_requires_context_action_and_outcome(self):
        for before, after in (('Given', 'And'), ('When', 'And'), ('Then', 'And')):
            with self.subTest(before=before), self.assertRaises(ValidationError): checks.feature_index(sample()['feature'].replace(before, after))

    def test_outline_without_examples_cannot_hide_behind_other_scenarios(self):
        value = sample()['feature']; start = value.index('    Examples:'); end = value.index('  @case_SC4')
        with self.assertRaises(ValidationError): checks.feature_index(value[:start] + value[end:])

    def test_unresolved_outline_parameter(self):
        with self.assertRaises(ValidationError): checks.feature_index(sample()['feature'].replace('<time>', '<unknown>'))

    def test_empty_example_cell_rejected(self):
        with self.assertRaises(ValidationError): checks.feature_index(sample()['feature'].replace('| 12:01 | confirmed |', '|       | confirmed |'))

    def test_duplicate_case_id_rejected(self):
        with self.assertRaises(ValidationError): checks.feature_index(sample()['feature'].replace('@case_SC4', '@case_SC1'))

    def test_case_tag_must_be_on_scenario(self):
        with self.assertRaises(ValidationError): checks.feature_index('@case_SC1\nFeature: Example\n  Scenario: Example\n    Given A\n    When B\n    Then C\n')

    def test_no_rewrite_between_feature_and_index(self):
        value = sample()['feature'].replace('\n', '\r\n')
        original = value.encode()
        checks.feature_index(value)
        self.assertEqual(original, value.encode())

    def test_risk_register_is_controller_supplied(self):
        value = sample(); value['feature'] = '@risk_RISK-999\n' + value['feature']
        self.assertIn('unknown_risk', {f['code'] for f in checks.check(value, {'POLICY1': REFERENCE['source']}, contracts.DEFAULT_POLICY)['findings']})

    def test_unknown_tags_rejected_without_inferred_tracker_mapping(self):
        value = sample(); value['feature'] = '@PROJECT-123\n' + value['feature']
        self.assertIn('unknown_tag', {f['code'] for f in checks.check(value, {'POLICY1': REFERENCE['source']}, contracts.DEFAULT_POLICY)['findings']})

    def test_quoted_interaction_word_is_a_reviewable_warning(self):
        value = sample(); value['feature'] = value['feature'].replace('Alice requests cancellation\n', 'Alice presses Enter to request cancellation\n', 1)
        # Use exact token included in the vocabulary, rather than a stemming claim.
        value['feature'] = value['feature'].replace('presses', 'press')
        results = checks.check(value, {'POLICY1': REFERENCE['source']}, contracts.DEFAULT_POLICY)['findings']
        self.assertTrue(any(f['code'] == 'interaction_wording' and f['severity'] == 'warning' for f in results))


class ParityTests(unittest.TestCase):
    def setUp(self):
        self.corpus = json.loads((ROOT / 'examples/refinement-parity.json').read_text())

    def test_missing_group_is_not_hidden_by_average(self):
        result = evaluate(self.corpus, {})
        self.assertEqual(set(result['groups']), {'expert', 'partial', 'plain'})
        self.assertTrue(all(g['contract_pass_rate'] == 0 for g in result['groups'].values()))
        self.assertFalse(result['experience_invariance_proven'])

    def test_same_invalid_output_fails_every_input_group(self):
        value = sample(); value['proposals'] = ['Invent a missing business decision.']
        outputs = {case['id']: {'draft': value, 'review': assessment(value)} for case in self.corpus['cases']}
        result = evaluate(self.corpus, outputs)
        self.assertTrue(all(not c['contract_passed'] for c in result['cases']))

    def test_unknown_cases_rejected(self):
        with self.assertRaises(ValidationError): evaluate(self.corpus, {'unknown': {}})

    @unittest.skipUnless(PARSER, 'Official parser unavailable locally')
    def test_reference_passes_identical_contract_for_all_styles_without_claiming_model_accuracy(self):
        value = sample(); outputs = {c['id']: {'draft': value, 'review': assessment(value)} for c in self.corpus['cases']}
        result = evaluate(self.corpus, outputs)
        self.assertTrue(all(c['contract_passed'] for c in result['cases']))
        self.assertFalse(result['semantic_accuracy_measured'])

    def test_output_cannot_replace_trusted_corpus_sources(self):
        outputs = {self.corpus['cases'][0]['id']: {'draft': sample(), 'review': assessment(sample()), 'sources': {'fake': {}}}}
        result = evaluate(self.corpus, outputs)
        self.assertTrue(result['cases'][0]['invalid_output'])
