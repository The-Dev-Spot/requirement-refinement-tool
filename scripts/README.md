# Optional toolkit helper

The agents operate through your assistant and its configured MCP tools. There is
no application installation or background Python service in this repository.

`build-logbook-page.py` is the original small, dependency-free rendering helper:

```sh
python3 scripts/build-logbook-page.py DEMO-1234
```

It reads the local run's Markdown files and assembles a Confluence page body with
the configured inline sections included verbatim. It does not connect to a server,
read credentials, approve anything or publish a page. Publishing and read-back
verification belong to skill-confluence-log, scoped to the configured evidence root.

If Python is unavailable, skill-confluence-log can assemble the same page from
the files while obeying its verbatim and completeness checks. Do not claim that
this helper ran or that attachments were uploaded when they were not.
