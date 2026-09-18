# Keycloak realm seed

Drop a realm export JSON here (e.g. `magic-boto-realm.json`) and it's imported automatically
when the `keycloak` container starts (`start-dev --import-realm`, wired in `docker-compose.yml`).

Import only happens into an **empty** `keycloak_postgres_data` volume — Keycloak skips a realm
that already exists in its DB. So this is a one-time seed for a fresh clone / fresh volume, not
a sync: editing this file and restarting the container on a machine that already has the realm
does nothing. To pick up new config on an existing machine, either re-import manually (Keycloak
admin console → Realm settings → Action → Partial import) or drop the volume and let it reseed.

## Exporting current config

Admin console → select the `magic-boto` realm → Realm settings → **Action → Partial export** →
check "Include clients" (and "Include groups and roles" if you've set any up) → Export. Save the
downloaded file here.

## Client secrets

Check the exported JSON before committing it. Partial export may or may not include client
secrets in plaintext depending on Keycloak version/config — grep for `"secret"` in the file.

- **If secrets are present:** don't commit them as-is. Either strip those fields (each
  confidential client will need its secret regenerated post-import — Credentials tab — before
  it's usable), or keep this file out of git entirely and distribute it out-of-band instead.
- **If secrets are absent:** safe to commit. Regenerate/set each confidential client's secret
  once per environment after import.

Either way, treat a freshly imported client's secret as unset/untrusted until you've explicitly
set it for that environment.
