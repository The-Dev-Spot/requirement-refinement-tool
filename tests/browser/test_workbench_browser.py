"""Real-browser form regression: browser-generated headers, never mocked Origin."""
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

from clarity.refine.web import Workbench
from test_refine_controller import Fixture


class BrowserWorkbenchTests(Fixture):
    def setUp(self):
        super().setUp()
        self.server = Workbench(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        self.browser = self.playwright.chromium.launch()
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


if __name__ == '__main__':
    unittest.main()
