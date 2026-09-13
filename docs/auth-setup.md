# Auth setup

**Read this only if you need it.** Reading a public or unlisted playlist needs nothing
at all — no key, no project, no consent screen.

| What you want to do | What you need |
|---|---|
| Read a public or unlisted playlist | nothing |
| Read a **private** playlist | OAuth |
| Create, edit or delete a playlist | OAuth |
| Read via the official API instead of the keyless reader | an API key |

> **Shortcut:** switching a playlist from Private to **Unlisted** makes it readable with
> no credentials while keeping it out of search and recommendations. If you only want to
> *read* your own list, this is far less work than OAuth.

## API key (reads only)

1. Open the [Google Cloud console](https://console.cloud.google.com/) and create a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **Credentials → Create credentials → API key**.
4. Put it in `.env` as `YT_API_KEY` and set `YTPS_PREFER_API=true`.

Restrict the key to the YouTube Data API. It cannot write, and it cannot read private
playlists — that is OAuth's job.

## OAuth client (private reads + all writes)

1. Same project → **APIs & Services → OAuth consent screen**.
   - User type **External** is fine.
   - While the app is in *Testing*, add your own Google account under **Test users** —
     otherwise consent is refused.

2. **Set Publishing status to "In production."** Do not skip this.

   > ### The 7-day trap
   >
   > Google issues apps in **Testing** status a refresh token that **expires after 7
   > days** ([docs](https://developers.google.com/identity/protocols/oauth2)). The
   > exemption is only for apps requesting nothing beyond name/email/profile — any
   > YouTube scope is well outside that.
   >
   > So in Testing, a long publish job dies with `invalid_grant` about a week in, and
   > you have to re-consent. Since the API can only add ~200 songs a day, **any library
   > over ~1,400 songs will outlive a Testing-status token.**
   >
   > "In production" issues a non-expiring refresh token. Google will show a
   > **"Google hasn't verified this app"** screen the first time — expected for a
   > personal tool. Click **Advanced → Go to (app name)**. Verification is only needed
   > if you distribute the app to other people.

3. **Credentials → Create credentials → OAuth client ID → Desktop app**.
4. Copy the client ID and secret into `.env`:

```dotenv
YT_OAUTH_CLIENT_ID=xxxx.apps.googleusercontent.com
YT_OAUTH_CLIENT_SECRET=xxxx
```

5. First run opens your browser for consent. The refresh token is cached at
   `YT_OAUTH_TOKEN_PATH` (default `.tokens/token.json`, written `chmod 600`, gitignored).

**This tool never sees your Google password.** Consent happens on Google's own pages.

### Scopes

| Operation | Scope |
|---|---|
| Read private | `youtube.readonly` |
| Create / edit / delete | `youtube.force-ssl` |

### Revoking

Delete `.tokens/token.json`, and remove the app at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## Reusing an OAuth client you already have

If you already have a Google Cloud project with the YouTube Data API enabled, **reuse
the project** — you keep the API enablement, the consent screen and the quota. You only
need to check one thing about the **client**.

Open your client in the console and look at **Application type**:

| Your client type | What to do |
|---|---|
| **Desktop app** | Works as-is. Paste the ID and secret into `.env` and you are done. |
| **Web application** | Either create a second client of type *Desktop app* in the same project (30 seconds, nothing else changes) — or keep this one and pin the callback port, below. |

### Keeping a Web application client

A Desktop client accepts a redirect on any loopback port, which is why this tool uses a
random one. A Web client only accepts redirect URIs you have registered, so pin the port:

```dotenv
YT_OAUTH_PORT=8080
```

Then in the console, on that client, add this to **Authorised redirect URIs** — exactly,
including the trailing slash:

```
http://localhost:8080/
```

### Two cautions when sharing a project

- **Quota is per project, not per client.** If anything else in that project calls the
  YouTube Data API, you are sharing the same 10,000 units/day. This tool's ledger only
  counts its own spending, so your real remaining quota may be lower than `ytps quota`
  reports.
- **Check the consent screen's publishing status.** An existing project may still be in
  *Testing*, which brings the 7-day refresh-token expiry described above.

## Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `access_denied` during consent | app in Testing, you are not a test user | add your account under Test users |
| `quotaExceeded` | 10,000 units spent today | wait for midnight US/Pacific, or use `ytps publish links` |
| `playlistNotFound` on your own list | it is Private and you are reading keyless | set up OAuth, or make it Unlisted |
| `invalid_grant` after it worked for days | app is in **Testing**, refresh token hit its 7-day expiry | set Publishing status to **In production**, delete `.tokens/token.json`, re-run to re-consent |
| `Google hasn't verified this app` | expected for a personal tool in production | **Advanced → Go to (app name)** |
| `redirect_uri_mismatch`, or consent hangs after you approve | using a **Web application** client with a random port | set `YT_OAUTH_PORT` and register `http://localhost:<port>/` on the client — see above |
| `The Data API path needs extra packages` | optional deps missing | `pip install "yt-playlist-studio[api]"` |
