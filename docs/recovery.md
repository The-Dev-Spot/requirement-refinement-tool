# Backup and recovery

Stop active model work or allow it to finish before taking a backup. Backups use a
consistent SQLite read transaction and include requirements, history, sealed
exports, source versions, settings and job records. Credentials are excluded.

## Create an encrypted backup

```sh
clarity backup --state /absolute/private/state --key-file /absolute/private/operator.key --output /absolute/private/clarity.backup.json
```

The command prompts twice for a passphrase of at least 12 characters. It derives
an encryption key using scrypt and encrypts with AES-GCM. Keep the passphrase and
the printed digest receipt separately from the file. Do not put a passphrase in
shell arguments. Output creation is exclusive and never overwrites an existing file.

The lower-level Python backup API returns plaintext JSON for compatibility.
Handle it as sensitive. The user-facing command always encrypts it.

## Test restoration

```sh
clarity restore --input /absolute/private/clarity.backup.json --destination /absolute/private/restored-clarity --digest DIGEST_FROM_RECEIPT
clarity setup --state /absolute/private/restored-clarity
clarity doctor --state /absolute/private/restored-clarity
clarity start --state /absolute/private/restored-clarity
```

The destination must not exist. A failed restore may leave an initialized directory;
inspect it and use a new destination rather than overwriting evidence. Restore
validates hashes, record chains and the separately retained receipt.

Old login credentials are disabled. Setup creates fresh role keys. Reconnect
service credentials in Setup; the vault key and encrypted secret rows are never
included in the backup. Interrupted jobs do not restart. Unsealed approvals cannot
survive as authority; obtain current review/approval before another seal.
Historical sealed bundles remain immutable and retrievable with new authorized keys.

No automatic backup schedule or deletion policy is configured. Test recovery before
relying on a backup for important evidence. The supported backup size is 20 MB of
plaintext data; exceeding it fails rather than producing a partial backup.
