---
status: proposed
---

# The integration ships its own public OAuth client

Signing in to Digital Factory uses a dedicated public OAuth client registered for this integration (authorization code with PKCE `S256`, no secret, redirect `https://my.home-assistant.io/redirect/oauth`, scopes `account.user.read`, `connect.cluster.read`, `connect.cluster.write`). Its client ID is bundled, so users never enter application credentials. OAuth is the default because it is the only route for free and lower-tier accounts; an API token is offered as a second option for workspaces whose plan allows one.

## Considered Options

- **Cura's client ID or the SDK examples client**: rejected because their redirect is `http://localhost:32118/callback`, which fails when the browser is not on the Home Assistant host, and because borrowing another product's identity can break or be revoked without notice.
- **User-supplied application credentials**: rejected because the account server has no self-service client registration.
- **API token only**: rejected because token creation needs a workspace admin on Business, Business Plus, Unlimited, Excellence or Campus, which excludes most home users.

## Consequences

- The client must be registered by UltiMaker's cloud team before the cloud connection can ship; changing its redirect or scopes later needs them again.
- The account server's PKCE default in Cura is the non-standard `S512`; this client relies on the server also accepting `S256`.

This is not implemented in 2.0: the client has to be registered by UltiMaker's cloud team first, so 2.0 signs in with an API token only.
