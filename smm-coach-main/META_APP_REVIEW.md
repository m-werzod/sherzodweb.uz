# Meta App Review — Instagram Advanced Access submission guide

This is the exact checklist to get **Advanced Access** for the Instagram
permissions SMM Coach needs. The code side is done (OAuth, callbacks, legal
pages); the rest is configuration in the Meta dashboard + a screencast. Plan
for **2–6 weeks** of review — submit early, build everything else in parallel.

App: **smm.brotech.uz** · Meta product: **Instagram API with Instagram Login**
(Instagram Business login, NOT the deprecated Basic Display).

---

## 0. What the code already provides

| Purpose | URL (production) | File |
|---|---|---|
| OAuth redirect | `https://smm.brotech.uz/api/auth/callback/instagram` | `app/api/auth/callback/instagram/route.ts` |
| Deauthorize callback | `https://smm.brotech.uz/api/meta/deauthorize` | `app/api/meta/deauthorize/route.ts` |
| Data deletion callback | `https://smm.brotech.uz/api/meta/data-deletion` | `app/api/meta/data-deletion/route.ts` |
| Webhook verify + receive | `https://smm.brotech.uz/api/webhooks/instagram` | `app/api/webhooks/instagram/route.ts` |
| Privacy Policy | `https://smm.brotech.uz/privacy` | `(marketing)/privacy` |
| Terms of Service | `https://smm.brotech.uz/terms` | `(marketing)/terms` |
| Data Deletion instructions | `https://smm.brotech.uz/data-deletion` | `(marketing)/data-deletion` |

All three callbacks verify Meta's `signed_request` HMAC with `INSTAGRAM_APP_SECRET`.

---

## 1. Environment (Coolify → web service)

```
INSTAGRAM_APP_ID=<from Meta dashboard>
INSTAGRAM_APP_SECRET=<from Meta dashboard>
INSTAGRAM_REDIRECT_URI=https://smm.brotech.uz/api/auth/callback/instagram
INSTAGRAM_WEBHOOK_VERIFY_TOKEN=<any long random string you also paste in the dashboard>
NEXTAUTH_URL=https://smm.brotech.uz      # callbacks build their URLs off this
```

The agents service also reads `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET` (config.py).

---

## 2. Meta dashboard configuration

**App settings → Basic**
- App domains: `smm.brotech.uz`
- Privacy Policy URL: `https://smm.brotech.uz/privacy`
- Terms of Service URL: `https://smm.brotech.uz/terms`
- User data deletion: choose **Data deletion request callback URL** →
  `https://smm.brotech.uz/api/meta/data-deletion`
  (or "Data deletion instructions URL" → `https://smm.brotech.uz/data-deletion`)
- Category: Business / Productivity
- App icon, contact email.

**Instagram → API setup with Instagram login → Business login settings**
- OAuth redirect URI: `https://smm.brotech.uz/api/auth/callback/instagram`
- Deauthorize callback URL: `https://smm.brotech.uz/api/meta/deauthorize`
- Data deletion request URL: `https://smm.brotech.uz/api/meta/data-deletion`

**Webhooks (Instagram)**
- Callback URL: `https://smm.brotech.uz/api/webhooks/instagram`
- Verify token: the same value as `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`
- Subscribe to: `comments`, `mentions` (as needed)

---

## 3. Permissions to request (with justification to paste)

| Permission | Why we need it (paste into the use-case box) |
|---|---|
| `instagram_business_basic` | Read the connected Business/Creator profile and media to build a personalized content roadmap and show the user their own account in the dashboard. |
| `instagram_business_manage_insights` | Read reach, saves, views and audience demographics of the user's own posts to measure progress toward their follower goal and forecast growth. Data is shown only to the account owner. |
| `instagram_business_manage_comments` | Read comments on the user's own posts so the assistant can summarize sentiment and suggest replies. We never comment without the user's explicit action. |
| `instagram_business_content_publish` | Publish a reel the user has explicitly reviewed and approved from within the app (one-tap "Avtomatik chiqarish"). The publish flow IS shipped (`lib/instagram/publish.ts::publishTaskNow`) and in `REQUIRED_SCOPES`, so demo it in the screencast and request it now. |

> Request only what you actively demonstrate in the screencast. All four scopes
> above are now exercised by the live product, so all four can be requested —
> just make sure each one appears in the recording (section 4).

**Competitor data (`business_discovery`) — a SEPARATE, later submission.** It is
NOT in the list above because it belongs to the *other* API variant — **Instagram
API with Facebook Login** (the account links a Facebook Page), queried on
`graph.facebook.com`. The client is already built (`graph_api.fetch_competitor_snapshot`).
When you want official competitor data live, add the "API setup with Facebook
login" product, request `instagram_basic` + `pages_show_list`/`pages_read_engagement`
under that variant, and submit a small separate review demonstrating the
competitor-lookup. Until then competitor intel runs on web-search grounding.

---

## 4. Screencast (the #1 reason reviews fail)

Record a single screen capture (English narration or captions) of a REAL test
user going through the flow, showing each requested permission in use:

1. Open `https://smm.brotech.uz`, sign up, reach onboarding.
2. Click **"Instagram bilan ulanish"** → Meta OAuth dialog → grant.
3. Land back in the app showing the user's **own** profile + media pulled via
   `instagram_business_basic`.
4. Open the dashboard analytics showing reach/saves/audience — call out
   `instagram_business_manage_insights`.
5. Open a post's comments view — call out `instagram_business_manage_comments`.
6. Open a finished task → tap **"Avtomatik chiqarish"** → confirm → show the reel
   posting to the user's own Instagram — call out `instagram_business_content_publish`
   (emphasize: only on the user's OWN account, only after they explicitly approve).
7. Show **Settings → delete / disconnect**, and the `/data-deletion` page, to
   prove the deletion path.

Keep it under ~4 minutes, no dead air, clearly narrate which permission each
screen uses. Record with a real **Creator/Business** test account (personal
accounts can't use the API). Include the OAuth consent dialog on screen — a
review without the consent screen visible is the #1 rejection reason.

---

## 5. Verification — you do NOT need a registered company

Advanced Access requires verification, but there are **two paths**, and a solo
founder without an LLC/MChJ/YaTT can still pass:

1. **Business Verification** — for a registered legal entity. Meta Business
   Settings → **Security Center** → Business Verification → Start. Needs: legal
   business name + address + an official document (registration certificate /
   commercial-register extract, colour, uncropped, < 1 year old). If the document
   isn't in a Meta-supported language, attach a certified English translation.
2. **Admin / Individual Verification** — **when you have NO business entity.** Meta
   "collects personal information to confirm your identity" instead: you read the
   *Responsible-party agreement*, certify you're the authorized representative, and
   verify your personal identity (ID + contact). This is the path for an
   individual developer. (Sources: Meta "Business Verification - App Development",
   developers.facebook.com/docs/development/release/business-verification/.)

So: **no MChJ/YaTT is strictly required** — choose Admin/Individual verification.
A registered YaTT (cheap, fast, online in UZ) makes Business Verification cleaner
later, but it is NOT a blocker to start. Verification can take a few days to a
couple of weeks — start it the same day you submit App Review.

> Reminder: NONE of this blocks building or beta-testing. At Standard Access the
> full product already works for you + accounts you add as **Instagram Testers**
> (section 6). Verification + App Review only gate serving the *public* (non-tester
> users) — i.e. the path to real customers at scale.

---

## 6. Before submission — test in Development mode

While in Development mode, the app works for **roles you add**:
- Add your own IG account as an **Instagram Tester** (App roles → Roles →
  Instagram testers) and accept the invite in the IG app (Settings → Apps and
  websites → Tester invites).
- Verify the full OAuth flow end-to-end with that tester account.
- Hit `GET https://smm.brotech.uz/api/debug/instagram` (signed-in) to confirm the
  redirect URI + env are correct.

Only after the flow works for a tester should you submit for review.

---

## 7. Submit

App Review → Permissions and Features → request the scopes in section 3 →
attach the screencast + justifications → submit. Then switch the app to **Live**
once approved.

## Timeline & fallback

- Review: **2–6 weeks**. Business verification can gate it — do both early.
- Until approved: OAuth returns `scope_not_approved` for non-tester users. The
  onboarding wizard already falls back to a manual follower-count input, so the
  product stays usable for new signups while you wait.
