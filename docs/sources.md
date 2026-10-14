# Source library

Capture only material needed to understand a requirement. A source in the library
is not automatically selected for a requirement and does not establish its authority.

## Text and files

As author or operator, open **Sources → Capture text or a file**. Enter a title,
project and locator. A locator can be a label or URL; it is never fetched. Paste
text or select a UTF-8 text/Markdown file smaller than 100 KB. The file contents
appear in the form for review before saving. PDF and Word extraction are not
implemented; paste the relevant verified text instead.

Record the original revision and effective date when known. Retrieval time is
recorded on save. Editing saves a new immutable library version and preserves the
previous version. Source text remains escaped when displayed.

## Read-only imports

An operator saves credentials in **Setup → Source connections**. An author then
selects that connection and one object in **Sources → Import**.

| Service | Scope | Selected object | Capture |
| --- | --- | --- | --- |
| Linear | Exact team ID and optional project ID | Issue ID/key | Issue and bounded comment pages |
| Jira Cloud | Exact project key | Issue key | Summary, description and bounded comment pages |
| Confluence Cloud | Exact numeric space ID | Numeric page ID | One page's storage body converted to text |

Atlassian connections accept only a tenant hostname ending in `.atlassian.net`.
Email and API token use Basic authentication over HTTPS. Linear uses its read-only
adapter. No arbitrary URLs, self-hosted tracker endpoints, bulk crawl or remote
updates are exposed. Use manual capture for other services.

The adapters recheck source revision after reading and reject a changed capture.
Oversized, incomplete or excessive pagination fails instead of silently truncating.
Rich text is reduced to text; check tables, links and embedded content manually
because attachments and linked pages are not recursively imported.

## Attach, confirm and update

On a requirement, expand **Attach a source from the library** and select a version
from the same project. Choose whether it supplements existing context or replaces
an old reference. Replacement preserves the audit history and removes the old
reference from active evidence. It does not edit a sealed handoff.

Use operator login to explain why the captured reference is authoritative and
applicable. The draft cites exact source IDs, hashes and quotations. Changing a
source, decision or policy makes old draft/review context stale; regenerate and
review. The current draft exposes invalidated citation IDs so affected claims can
be inspected. A matching quote proves existence, not semantic support.

Official API references: [Jira Cloud](https://developer.atlassian.com/cloud/jira/platform/rest/v3/),
[Confluence Cloud](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/),
[Linear GraphQL](https://linear.app/developers/graphql).
