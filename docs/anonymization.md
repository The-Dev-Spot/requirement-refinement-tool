# Anonymization and import boundary

This baseline uses a fresh source tree. No original Git directory, refs, reflogs,
commit authors, remotes or deleted historical objects were imported. Excluding
history matters because removing a file from a working tree does not remove
its earlier contents from Git objects.

The personal version excludes proprietary reference documents, real run records,
learning/decision histories, internal domain glossaries, business-specific risk
registers, authentication pages, local IDE/MCP settings, migration scripts and
project/field/sprint mappings. Do not restore those from the original archive.

Reusable workflow concepts were restated in neutral language. Company names,
internal hosts, project keys, person references and domain-specific examples were
removed. Configuration is local-only; examples use fictional DEMO/RUN identifiers
and reserved example domains. Run artifacts and private grounding are ignored.

Verification combines a targeted case-insensitive scan for known source-specific
identifiers, a tracked-file credential/host/artifact check, text review and tests.
The targeted deny-list is intentionally not shipped: it would itself reintroduce
excluded identifiers. The generic hygiene checker is limited and cannot prove
that every sensitive or identifying detail has been found.

This is a curated personal baseline, not a byte-for-byte mirror or a certified
clean-room implementation. Anonymization does not establish ownership or rights
to reuse source material. Keep the repository private and confirm permission
before any broader distribution. The original uploaded archive remains separate
and unchanged; it must not be uploaded into this repository.
