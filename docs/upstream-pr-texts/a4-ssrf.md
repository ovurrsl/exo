# A4 — `fix/ssrf-image-url`

Compare: https://github.com/exo-explore/exo/compare/main...ovurrsl:exo:fix/ssrf-image-url?expand=1

## Title

```
fix(api): reject image URLs pointing at private or loopback addresses (SSRF)
```

## Description

```markdown
## Motivation

`fetch_image_url()` fetches any URL supplied in a chat request's `image_url`
content block. The API listens on the LAN without authentication, so that value
is attacker-controlled and the node will fetch on the caller's behalf — the
classic server-side request forgery shape.

Concretely, a request today can make an exo node read
`http://169.254.169.254/latest/meta-data/` on a cloud instance, reach
`http://127.0.0.1:<port>/` on the node itself, or probe hosts on the LAN that
the caller cannot route to. The response comes back base64-encoded in the
completion, so it is an exfiltration channel and not only a blind request.

This is reached from three adapters (`chat_completions`, `claude`, `responses`),
all of which route through the same function.

## Changes

- `src/exo/api/adapters/chat_completions.py`:
  - `validate_image_url()` rejects any scheme other than `http`/`https`, a URL
    with no host, and any host that resolves to a non-public address —
    loopback, private, link-local, multicast or unspecified.
  - Hostnames are resolved before the check, so a name pointing at a private
    address is caught as well as a literal one. DNS resolution is injected via a
    `resolve` parameter so the logic is testable without touching DNS.
  - `fetch_image_url()` validates first, then requests with
    `allow_redirects=False` and raises on a 3xx. Without that, a public URL
    could bounce the request to an address validation had just rejected.
- `src/exo/api/tests/test_image_url_validation.py`: new.

## Why It Works

The check happens before any socket is opened, and the redirect block closes the
one path that could reach a rejected address after a successful validation. All
addresses a hostname resolves to are checked, not just the first, so a
DNS-rebinding record that mixes a public and a private answer is rejected rather
than partially accepted.

Fixing it in `fetch_image_url` covers all three adapters at once, since they all
call it.

## Test Plan

### Manual Testing
- Hardware: Ubuntu x86_64, Python 3.13 (no Apple Silicon available)
- Confirmed that on `main` an `image_url` of
  `http://169.254.169.254/latest/meta-data/` is fetched, and that with this
  change it is refused before any connection is attempted.

### Automated Testing
New file `src/exo/api/tests/test_image_url_validation.py`, 13 cases, no network
and no MLX required:

- Non-HTTP schemes (`file:`, `gopher:`, `data:`) rejected.
- A URL with no host rejected.
- Ten literal non-public addresses rejected, including `169.254.169.254`,
  `127.0.0.1`, `::1`, `10.0.0.1` and `192.168.1.1`.
- A hostname resolving to a private address rejected.
- A hostname resolving to both a public and a private address rejected, which is
  the DNS-rebinding case.
- An unresolvable hostname rejected.
- Ordinary public URLs accepted, so the change is not over-broad.
- One test asserts the refusal happens before any socket is opened.
```
