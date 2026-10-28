# Preparing Clarity for another person

Share the reviewed source checkout or package. Each recipient runs `clarity setup`
to create their own private workspace and login keys.

Keep runtime state, credentials, source documents, local editor settings, exports,
logs and backups out of source control. The ignore rules cover common locations;
the tracked-file checker rejects private artifacts and unexpected hosts.

```sh
git add PATHS_YOU_INTEND_TO_SHARE
python -m clarity check-repo
```

Inspect the staged diff and run a private, targeted scan for any names, domains or
identifiers that should not be shared. Keep that private deny-list out of the
project. Also inspect screenshots, sample data, commit messages and repository
metadata. The generic scanner cannot establish that every identifying detail has
been found.

From a clean committed checkout, create a source-only ZIP outside the repository:

```sh
clarity source-bundle --root /absolute/path/to/clarity --output /absolute/private/clarity-source.zip
```

The command refuses uncommitted tracked changes, runs the hygiene check, excludes
Git metadata and untracked runtime data, and includes a per-file SHA-256 manifest.
Retain its printed archive checksum separately. Inspect the extracted snapshot
with your private identifier deny-list before giving it to someone.

Removing a file from the current tree does not remove earlier versions from Git
history. For a clean handoff, distribute the reviewed current snapshot without
runtime state or unrelated repository history. Any destructive history rewrite
must be handled separately and intentionally.
