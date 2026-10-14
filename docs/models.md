# Model connections

Coding assistants are the primary route; see [assistant setup](assistants.md).
For direct local inference, sign in as operator and open **Setup → Models & assistants**.

## Local servers

| Provider | Endpoint | Example port | Required capability |
| --- | --- | --- | --- |
| Ollama | `/api/chat` | 11434 | JSON schema in `format`, non-streaming chat |
| OpenAI-compatible local | `/v1/chat/completions` | 1234 for a typical LM Studio setup; choose your own | Strict `response_format.json_schema`, one complete text response |

The hostname is fixed to `127.0.0.1`. Enter the model's exact advertised ID and the
actual listening port. An optional Bearer key is supported for the local OpenAI-compatible server. Models are not downloaded automatically. For a custom LLM,
serve it with one of these protocols; unsupported custom protocols need an adapter.
A local proxy can forward remotely, so verify the server's data handling yourself.

Set the output budget (256–16384 tokens), timeout (5–120 seconds), and Ollama
keep-alive (0–600 seconds). Large requirements may need a larger output budget,
but context remains bounded to 200 KB per selected model packet. Capture smaller
excerpts rather than dumping an entire knowledge base into the request.

Save the profile, then **Test structured output**. The test sends a fixed synthetic
request. Passing shows that this request worked at that time. It does not certify
model quality, context capacity or adherence to every schema keyword. Provider,
model, parameter or credential changes hide old diagnostic results.

## Optional cloud APIs

OpenAI uses fixed `api.openai.com` Responses requests with `store=false` and a
strict JSON schema. Anthropic uses fixed `api.anthropic.com` Messages requests
with structured output configuration. Choose a model supporting the selected
protocol and schema; Clarity does not maintain an assumed model catalogue.

Saving a cloud profile requires explicitly allowing selected evidence to be sent
to that provider. Enter an API key in the password field; blank preserves the
existing key when the provider and endpoint are unchanged. Changing that connection
requires entering its credential again. You can remove the active credential
reference using the Saved credential control. Historical encrypted rows remain
local until a separately chosen retention policy is implemented. Stored keys never return to the browser. Disabling a profile prevents
new calls. No provider fallback or automatic retry sends data elsewhere.

## Failures and measurements

Truncated output, tool calls, refusals, invalid/duplicate-key JSON and unexpected
contracts cannot become approved content. Reserved attempts remain in the audit
trail. The controller records elapsed time and bounded provider token/timing
metrics when available. Costs are not guessed from model names or current pricing.

Run the [evaluation protocol](evaluation.md) with actual needs before adopting a
new model. Test direct adapters against your actual deployment; transport fixtures
alone do not establish live compatibility.

Protocol references: [Ollama chat](https://docs.ollama.com/api/chat),
[OpenAI Responses](https://developers.openai.com/api/reference/resources/responses/methods/create),
[Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
