"""Real-browser form regression: browser-generated headers, never mocked Origin."""
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

from clarity.refine.web import Workbench
from clarity.refine.worker import request_packet
from test_refine_controller import Fixture
from test_refine_worker_web import FakeProvider


class BrowserWorkbenchTests(Fixture):
    def setUp(self):
        super().setUp()
        self.server = Workbench(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        executable = os.environ.get('CLARITY_BROWSER_EXECUTABLE')
        # CI keeps Playwright's pinned default; an explicit local override must launch.
        launch_options = {'executable_path': executable} if executable else {}
        self.browser = self.playwright.chromium.launch(**launch_options)
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        self.page.set_default_timeout(10000)
        self.posts = []
        self.page.on('request', self.observe_request)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def observe_request(self, request):
        if request.method == 'POST':
            # Never retain form bodies or capability/session values in test logs.
            self.posts.append((urlsplit(request.url).path, request.headers.get('origin')))

    def submit(self, path, button):
        with self.page.expect_response(lambda r: r.request.method == 'POST' and urlsplit(r.url).path == path) as received:
            self.page.get_by_role('button', name=button, exact=True).click()
        self.assertEqual(received.value.status, 303, 'Form request origins: ' + repr(self.posts))

    def test_browser_login_capture_and_logout(self):
        response = self.page.goto(self.server.origin)
        self.assertEqual(response.status, 200)
        old_cookie = self.page.context.cookies()[0]['value']
        self.page.locator('input[name=token]').fill(self.a)
        self.submit('/login', 'Sign in')
        self.assertEqual(self.posts[-1], ('/login', self.server.origin))
        self.assertNotEqual(old_cookie, self.page.context.cookies()[0]['value'])
        self.assertEqual(self.page.get_by_role('heading', name='Start with the problem').count(), 1)
        self.assertNotIn(self.a, self.page.content())

        self.page.locator('input[name=id]').fill('BROWSER1')
        self.page.locator('input[name=project]').fill('PERSONAL')
        self.page.locator('textarea[name=brief]').fill('People need to cancel their own bookings.')
        self.submit('/create', 'Capture request')
        self.assertEqual(self.posts[-1], ('/create', self.server.origin))
        self.assertEqual(self.c.status(self.a, 'BROWSER1')['run']['state'], 'captured')

        self.page.goto(self.server.origin)
        self.submit('/logout', 'Sign out')
        self.assertEqual(self.posts[-1], ('/logout', self.server.origin))
        self.assertEqual(self.page.get_by_role('heading', name='Sign in to this local workspace').count(), 1)

    def test_browser_setup_source_file_and_responsive_layout(self):
        self.page.goto(self.server.origin)
        self.page.locator('input[name=token]').fill(self.o)
        self.submit('/login', 'Sign in')
        self.page.get_by_role('link', name='Setup', exact=True).click()
        editor = self.page.locator('form[action="/settings/model"]')
        editor.locator('input[name=id]').fill('LOCAL')
        editor.locator('select[name=provider]').select_option('ollama')
        editor.locator('input[name=model]').fill('synthetic-local-model')
        self.submit('/settings/model', 'Save model profile')
        self.assertEqual(self.page.get_by_text('LOCAL · ollama · synthetic-local-model', exact=True).count(), 1)
        self.page.get_by_role('link', name='Sources', exact=True).click()
        self.page.locator('input[name=title]').fill('Synthetic policy')
        self.page.locator('input[name=locator]').fill('local:synthetic')
        self.page.locator('input[type=file]').set_input_files({'name': 'policy.txt', 'mimeType': 'text/plain', 'buffer': b'Only the owner can cancel a booking.'})
        self.page.wait_for_function("document.querySelector('textarea[name=text]').value.includes('Only the owner')")
        self.submit('/sources/save', 'Save source version')
        self.assertEqual(self.page.locator('summary').filter(has_text='Synthetic policy').count(), 1)
        saved = self.server.workspace.records(self.o, 'source')
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['text'], 'Only the owner can cancel a booking.')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.goto(self.server.origin + '/help')
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        self.assertNotIn(self.o, self.page.content())

    def test_navigation_to_another_origin_does_not_send_referrer(self):
        observed = []

        class Destination(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(self.headers.get('Referer'))
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'External destination')

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(('127.0.0.1', 0), Destination) as destination:
            thread = threading.Thread(target=destination.serve_forever, daemon=True)
            thread.start()
            try:
                self.page.goto(self.server.origin)
                target = 'http://127.0.0.1:' + str(destination.server_port) + '/outside'
                self.page.evaluate("url => { const a = document.createElement('a'); a.href = url; a.textContent = 'External destination'; document.body.append(a); }", target)
                self.page.get_by_role('link', name='External destination').click()
                self.assertEqual(observed, [None])
            finally:
                destination.shutdown()
                thread.join(timeout=2)

    def test_browser_stage_limits_budget_and_optional_intake(self):
        self.page.goto(self.server.origin)
        self.page.locator('input[name=token]').fill(self.o)
        self.submit('/login', 'Sign in')
        self.page.get_by_role('link', name='Setup', exact=True).click()
        editor = self.page.locator('form[action="/settings/model"]')
        editor.locator('input[name=id]').fill('INTAKE')
        editor.locator('select[name=provider]').select_option('ollama')
        editor.locator('input[name=model]').fill('synthetic-small-model')
        editor.locator('summary').filter(has_text='Efficiency and stage settings').click()
        editor.locator('select[name=stage]').select_option('intake')
        editor.locator('input[name=context_tokens]').fill('8192')
        editor.locator('input[name=intake_max_tokens]').fill('512')
        self.submit('/settings/model', 'Save model profile')
        saved = self.server.workspace.records(self.o, 'model')[0]
        self.assertEqual((saved['context_tokens'], saved['intake_max_tokens'], saved['stage']), (8192, 512, 'intake'))
        self.page.goto(self.server.origin)
        self.submit('/logout', 'Sign out')
        self.page.locator('input[name=token]').fill(self.a)
        self.submit('/login', 'Sign in')
        self.page.goto(self.server.origin + '/run/REQ1')
        self.page.locator('summary').filter(has_text='Input and output budgets before running').click()
        self.assertEqual(self.page.get_by_role('cell', name='512', exact=True).count(), 1)
        provider = FakeProvider({'questions': [], 'ready_to_draft': True})
        provider.max_tokens, provider.context_tokens = 512, 8192
        with patch.object(self.server.workspace, 'provider', return_value=provider):
            self.submit('/run/REQ1/model-profile', 'Check missing decisions only (optional)')
            self.server.jobs.pool.shutdown(wait=True)
        self.page.reload()
        self.assertEqual(self.c.status(self.a, 'REQ1')['run']['revision'], 0)
        self.assertEqual(self.page.get_by_role('heading', name='Requirement efficiency', exact=True).count(), 1)
        self.assertEqual(self.posts[-1], ('/run/REQ1/model-profile', self.server.origin))

    def test_browser_question_responses_dependencies_and_changed_decision(self):
        parent = self.question('Q1', 'Who may cancel a booking?', 2)
        child = {**self.question('Q2', 'How late may an allowed cancellation be made?', 5),
                 'prerequisites': ['Q1']}
        self.c.ask_many(self.a, 'REQ1', self.version(), [parent, child])
        self.page.goto(self.server.origin)
        self.page.get_by_label('Workspace login key').fill(self.o)
        self.submit('/login', 'Sign in')
        self.page.goto(self.server.origin + '/run/REQ1')
        decision = self.page.locator('section.decision')
        response_form = decision.locator('form[action="/run/REQ1/answer"]')
        response_kind = response_form.get_by_role('combobox', name='Response type', exact=True)
        owner = 'Booking policy <team>'

        # A more consequential child still waits for the prerequisite decision.
        expect(response_form.locator('input[name=question_id]')).to_have_value('Q1')
        self.page.get_by_text('Question and decision history', exact=True).click()
        expect(self.page.get_by_text('Resolve prerequisites first: Q1.', exact=True)).to_be_visible()
        expect(self.page.get_by_role('link', name='Q2 · ' + child['text'], exact=True)).to_have_count(0)

        # Browser validation must require an intentional response classification.
        expect(response_kind).to_have_value('')
        response_form.get_by_label('Your response', exact=True).fill('Only the booking owner may cancel.')
        before = self.version()
        before_posts = len(self.posts)
        response_form.get_by_role('button', name='Record response', exact=True).click()
        self.assertTrue(response_kind.evaluate('(select) => select.required && select.validity.valueMissing'))
        self.assertEqual(len(self.posts), before_posts)
        self.assertEqual(self.version(), before)

        partial_answer = 'Booking owners may cancel; the delegate policy is still unresolved.'
        unknown_answer = 'I do not yet know whether a delegate may cancel a booking.'
        for kind, label, answer in (
            ('partial', 'Partial answer', partial_answer),
            ('unknown', 'Not yet known', unknown_answer),
        ):
            with self.subTest(response_kind=kind):
                response_kind.select_option(kind)
                response_form.get_by_label('Your response', exact=True).fill(answer)
                response_form.get_by_label('Decision owner or team (optional)', exact=True).fill(owner)
                self.submit('/run/REQ1/answer', 'Record response')
                expect(decision.locator('.notice strong')).to_have_text(label)
                expect(decision.locator('.notice').get_by_text('Decision owner: ' + owner, exact=True)).to_be_visible()
                expect(decision.locator('team')).to_have_count(0)
                expect(response_kind).to_have_value('')
                status = self.status()
                question = status['context']['questions']['Q1']
                self.assertEqual(question['state'], 'open')
                self.assertEqual(question['response'], {'kind': kind, 'text': answer, 'decision_owner': owner})
                self.assertNotIn('decision_source', question)
                self.assertFalse(any(source['kind'] == 'decision' for source in status['context']['sources'].values()))
                self.assertEqual({q['id'] for q in status['open_questions']}, {'Q1', 'Q2'})
                self.assertEqual([q['id'] for q in status['ready_questions']], ['Q1'])
                self.assertEqual(status['run']['state'], 'awaiting_decision')

        # Exclude a specific earlier response without losing the current unknown
        # response or deleting its immutable history.
        status = self.status()
        response_events = [event for event in status['events'] if event['kind'] == 'question_response']
        projected = request_packet(status, 'intake')['context']['questions']['Q1']
        self.assertEqual([entry['text'] for entry in projected['response_history']], [partial_answer])
        decision.get_by_text('Earlier responses (history only)', exact=True).click()
        exclusion = decision.locator('form[action="/run/REQ1/exclude-response-history"]')
        expect(exclusion.locator('input[name=question_id]')).to_have_value('Q1')
        expect(decision.get_by_text(partial_answer, exact=False)).to_be_visible()
        exclusion.get_by_label('Why exclude this earlier response?', exact=True).fill(
            'The earlier partial answer is superseded and should not be used in future model context.')
        self.submit('/run/REQ1/exclude-response-history', 'Exclude earlier response from context')
        expect(decision.get_by_text('1 earlier response(s) explicitly excluded from model context; originals remain in the audit.', exact=True)).to_be_visible()
        expect(decision.get_by_text('Earlier responses (history only)', exact=True)).to_have_count(0)
        expect(decision.locator('.notice strong')).to_have_text('Not yet known')
        status = self.status()
        projected = request_packet(status, 'intake')['context']['questions']['Q1']
        self.assertEqual(projected['response_history'], [])
        self.assertEqual(projected['response'], {'kind': 'unknown', 'text': unknown_answer, 'decision_owner': owner})
        self.assertEqual(projected['state'], 'open')
        self.assertNotIn('decision_source', projected)
        self.assertFalse(any(source['kind'] == 'decision' for source in status['context']['sources'].values()))
        self.assertEqual([event for event in status['events'] if event['kind'] == 'question_response'], response_events)
        self.assertEqual(status['run']['state'], 'awaiting_decision')

        response_kind.select_option('confirmed')
        response_form.get_by_label('Your response', exact=True).fill('Only the booking owner may cancel a booking.')
        response_form.get_by_label('Decision owner or team (optional)', exact=True).fill(owner)
        self.submit('/run/REQ1/answer', 'Record response')
        expect(response_form.locator('input[name=question_id]')).to_have_value('Q2')
        status = self.status()
        old_parent_source = status['context']['questions']['Q1']['decision_source']
        self.assertEqual(status['context']['questions']['Q1']['state'], 'answered')
        self.assertEqual([q['id'] for q in status['ready_questions']], ['Q2'])
        # The label describes an owner; the authenticated operator supplies authority.
        self.assertEqual(status['context']['sources'][old_parent_source]['authority'], 'owner')

        child_answer = 'Cancellation is allowed only before the booking start time.'
        response_kind.select_option('confirmed')
        response_form.get_by_label('Your response', exact=True).fill(child_answer)
        response_form.get_by_label('Decision owner or team (optional)', exact=True).fill(owner)
        self.submit('/run/REQ1/answer', 'Record response')
        expect(response_form).to_have_count(0)
        status = self.status()
        old_child_source = status['context']['questions']['Q2']['decision_source']
        self.assertEqual(status['open_questions'], [])
        self.assertEqual(status['run']['state'], 'awaiting_revision')

        self.page.get_by_text('Question and decision history', exact=True).click()
        self.page.get_by_role('link', name='Q1 · ' + parent['text'], exact=True).click()
        expect(decision.get_by_role('heading', name='Review decision', exact=True)).to_be_visible()
        expect(response_form.locator('input[name=question_id]')).to_have_value('Q1')
        expect(response_kind).to_have_value('')
        response_kind.select_option('confirmed')
        response_form.get_by_label('Your response', exact=True).fill('The booking owner or a delegated coordinator may cancel a booking.')
        response_form.get_by_label('Decision owner or team (optional)', exact=True).fill(owner)
        self.submit('/run/REQ1/answer', 'Record response')

        expect(response_form.locator('input[name=question_id]')).to_have_value('Q2')
        expect(decision.get_by_text('This answer needs reconfirmation because Q1 changed.', exact=True)).to_be_visible()
        expect(decision.get_by_text(child_answer, exact=True)).to_be_visible()
        status = self.status()
        reopened = status['context']['questions']['Q2']
        self.assertEqual(reopened['state'], 'open')
        self.assertEqual(reopened['invalidated_by'], ['Q1'])
        self.assertNotIn('decision_source', reopened)
        self.assertNotIn(old_parent_source, status['context']['sources'])
        self.assertNotIn(old_child_source, status['context']['sources'])
        self.assertNotIn(partial_answer, [entry['text'] for entry in status['context']['questions']['Q1']['response_history']])
        self.assertEqual(status['run']['state'], 'awaiting_decision')
        self.assertIsNone(status['draft'])
        answer_posts = [item for item in self.posts if item[0] == '/run/REQ1/answer']
        self.assertEqual(answer_posts, [('/run/REQ1/answer', self.server.origin)] * 5)
        exclusion_posts = [item for item in self.posts if item[0] == '/run/REQ1/exclude-response-history']
        self.assertEqual(exclusion_posts, [('/run/REQ1/exclude-response-history', self.server.origin)])


if __name__ == '__main__':
    unittest.main()
