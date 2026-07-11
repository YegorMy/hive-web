# hive-web-runtime agent rules

- Keep the module boundary: `static-web` must not import `action-web`; `action-web` may import `static-web`.
- Default outputs must be token-cheap compact snapshots, not full HTML/DOM/screenshots.
- Raw payloads belong in the artifact store and should be referenced by `artifact_id`.
- Do not add secrets to config files. Use env vars or client-specific secret stores.
- Run `uv run pytest -q` before declaring changes complete.
- For live browser changes, also smoke-test a headless session against `https://example.com`.
- Never remove the safety gate around payment/password/2FA/captcha-looking actions without explicit user request.
