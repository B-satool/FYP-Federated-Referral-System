# Web app redesign: issues found, new flow, and compliance notes

> **Historical (v1).** This page records the v1 interface redesign. The v2 screens differ: separate doctor and staff work queues, role-template menus, and the receiving doctor accepting or declining with no response form. See [v2-changes.md](v2-changes.md).

Branch: `redesign/web-ui`. Scope: presentation and navigation only. No API, contract, migration, authorization, approval, flag or audit logic was changed (AGENTS.md invariants 1 to 11 are untouched).

## 1. Issues found in the previous interface

### Workflow and navigation
| # | Issue | Where |
|---|---|---|
| 1 | A referral was split into 8 flat tabs with no order, no progress and no sign of what was left. People had to know the sequence. | `ReferralWorkspace.tsx` |
| 2 | The action that moves a referral forward ("Send for clinician approval") lived inside the Overview tab, while approval itself was in "Brief & approval". The blocker list was another card on Overview. | `OverviewTab.tsx` |
| 3 | There was no "what do I do next" anywhere. Status was four overlapping chips (status, approved version, delivered version, delivery). | `ReferralWorkspace.tsx` |
| 4 | The top bar was one wrapping row of up to 9 buttons, with the user name, role chip and Sign out squeezed in. No grouping, no mobile menu, and the logo was not a link. | `Layout.tsx` |
| 5 | Clinic users landed on a bare referral list, not on what needed their attention. | `App.tsx` |
| 6 | Overview repeated the completeness checklist (also in the Checklist tab) and an unbounded timeline (also in Audit trail). | `OverviewTab.tsx` |

### Clutter and hierarchy
| # | Issue | Where |
|---|---|---|
| 7 | The work queue was a grid of seven boxes of different widths, most of them empty most of the time. | `WorkQueue.tsx` |
| 8 | Section titles were `h6` elements directly under the page `h1`, so the heading outline skipped levels for screen reader users. | Theme and all screens |
| 9 | Plain nested outlined boxes everywhere, with no emphasis for the primary action. | All screens |
| 10 | Loading was a spinner, so layout jumped when content arrived. | `common.tsx` |

### Visual design
| # | Issue |
|---|---|
| 11 | Default Material look: Roboto, bright blue app bar, an unused purple secondary colour, pure white surfaces on near white. |
| 12 | Status labels used a check mark icon for "ok", plus MUI default status colours. The default warning orange (3.1:1) and info blue (3.9:1) on white fall below 4.5:1 text contrast. |
| 13 | A sparkle icon on the "generate draft" button. |
| 14 | The focus ring was amber on a light background (about 2:1), below the 3:1 needed for a visible focus indicator. |

### Content and trust
| # | Issue |
|---|---|
| 15 | No privacy notice, terms of use, accessibility statement, cookie and storage information, deletion route, operator or contact details, favicon, page descriptions or per-page titles. |
| 16 | "Page not found" was a small inline alert with no way home. No success confirmations after actions. A rendering error would give a blank window. |
| 17 | About 30 em dashes used as separators and as the "empty value" marker. |

### Technical
| # | Issue |
|---|---|
| 18 | Several tables sat directly in boxes with no scroll container (for example the specialist inbox), so a narrow screen would likely force the whole page to scroll sideways. Not tested on a device. |
| 19 | A tracked build artefact (`web/tsconfig.tsbuildinfo`) changes on every build. Not fixed here; restore it before committing. |

## 2. The new flow

Every referral now opens on one screen with the same four parts, top to bottom:

1. **Header**: reference, patient, destination, current status and package versions.
2. **Next step**: one sentence on what to do now, with a button that goes there. It is worked out from the referral's status, approval blockers and role (a clinician sees "Review and approve the brief"; staff see "Waiting for a clinician to approve").
3. **Journey**: the sections in workflow order, grouped by phase, each showing its own state in words (Complete, Needs attention, To do, Waiting, Optional, Not yet, Ended).
4. **The current step**, with Previous and Next buttons at the bottom.

| Phase | Step (tab name, unchanged) | SRS | Done when |
|---|---|---|---|
| Prepare | 1 Overview | 4.1 | Reason, referring clinician and procedure status are set |
| Prepare | 2 Sources & evidence | 4.2 | Linked sources retrieved, with any denied or unavailable source shown |
| Prepare | 3 Documents | 4.3 | Optional. Uploaded records extracted and verified |
| Verify | 4 Medications & flags | 4.5 | Rules evaluated and every flag reviewed |
| Verify | 5 Checklist & clarifications | 4.4 | No blocking items remain |
| Approve and send | 6 Brief & approval | 4.6 | A clinician approved a version and it was delivered |
| Follow through | 7 Specialist & follow-up | 4.7, 4.8 | Response reviewed, tasks dispositioned, referral closed |
| Record | Audit trail | FR-59, FR-60 | Always available |

Step states are computed from data the page already loads (`approval_blockers`, `sources`, `status`, `delivery_status`). No new requests. Logic lives in `features/referrals/steps.ts`.

Other screens:
- **Start page**: clinic roles now land on the **Work queue**, a single prioritised column (information requests, approvals, responses to review, tasks, delivery problems, then waiting items). Empty sections collapse into one line. The sidebar shows a live count of items needing action.
- **Navigation**: left sidebar grouped as Work, Records and rules, Administration, with the signed-in user and Sign out at the bottom. On a phone it becomes a menu button and drawer.
- **Sign in**: explains the six stages of a referral, links the terms and privacy notice.
- **Policy pages**: privacy notice, terms of use, accessibility statement, readable before sign-in.

## 3. Design system

One file, `web/src/theme.ts`. System font stack (no font downloads and no licensing questions), 4px corners, no shadows, no animated hover states, deep teal brand colour, off-white page and surface colours.

All text and boundary colours were checked against WCAG 2.2 AA (4.5:1 text, 3:1 input borders and focus rings). Lowest text pair is 6.2:1; the form border colour is at least 3.7:1 on the page and 4.0:1 on surfaces; the focus ring is 7.7:1 on the page.

## 4. Your three checklists

### "30 reasons your site looks vibecoded"
| Tell | Status |
|---|---|
| 1 harsh gradients, 22 radial orbs, 23 dot grids, 8 liquid glass, 29 neon | None used |
| 2 lucide icons, 24 sparkle icons | Few Material icons, all functional. Sparkle icon replaced |
| 3 pure white background | Page `#EBF0EE`, surfaces `#F7F9F8`. The only white is behind scanned paper pages |
| 4 rainbow colouring, 20 purple and black, 30 basic pastels | Teal brand with near-black ink. Status tints appear only behind dark text |
| 5 drop shadows | Theme shadows set to none |
| 6 three feature cards in a row, 13 bento grids | Work queue is a single column. Sign in uses a numbered list |
| 7 emojis | None |
| 9 em dashes | Removed from all screen text and from this document |
| 10 Inter, Geist, Space Grotesk | System font stack |
| 11 coloured left stripe | None. Selected items use a full border |
| 12 fake testimonials, 17 pricing tiers, 14 terminal window | Not present |
| 15 "it's not x, it's y" | Not used in copy |
| 16 checkmark bullets | Check icon removed from status labels. Plain bullets and numbered squares |
| 18 no real product demos | Internal tool. The sign-in page describes the real workflow |
| 19 soft corner radius | 4px |
| 21 no skeleton loaders | Skeleton placeholders |
| 25 animated arrows, 28 hover animations | Transitions disabled. Hover is an instant colour change |
| 26 no TOS, 27 no privacy policy | Added |

### "20 things so your app doesn't get sued"
| Item | Status |
|---|---|
| Privacy policy, terms of service, cookie policy | Added. Cookie and storage use is a section of the privacy notice |
| Refund policy | Not applicable. The terms state there are no fees |
| Cookie consent banner | Not needed. Only strictly necessary sign-in storage is used, and the notice says so |
| Check form consents | Sign in states acceptance of terms and privacy notice. There are no marketing consents to collect |
| No unnecessary data, audit third-party SDKs | Dependencies reviewed: React, MUI, TanStack Query, React Router, React Hook Form, oidc-client-ts. No analytics or tracking. Notice lists them |
| Remove dark patterns, hidden fees, fake reviews, unsupported claims | None present. Copy limited to what the system does |
| Accessibility alt text, colour contrast, keyboard navigation | Checked and fixed as above. Accessibility statement added, with the honest note that no formal audit has been done |
| Add business details | Operator name and contact are build settings (`VITE_OPERATOR_NAME`, `VITE_CONTACT_EMAIL`), shown on the policy pages. Nothing is invented |
| Age consent for kids' data | Explained in the privacy notice. Not built, because the prototype uses synthetic data only |
| Unsubscribe link in emails | Not applicable. The application sends no email |
| License fonts and images | System fonts, no images. Icons are Material icons (Apache 2.0) |
| Data deletion request | Route described in the privacy notice. No in-app form, because deletion of clinical and audit records needs a decision from the operating institution |

### "20 things to fix on a vibecoded website"
Done: horizontal scroll (tables scroll inside their box), mobile menu, favicon, page titles, meta description, footer links, custom 404, copyright year (current year), success messages, error messages (inline messages kept, plus an error screen for crashes), clickable logo, clickable email (when configured), mobile layout. Not applicable: compress images (no images), broken links and buttons (all 20 internal link targets in the code point at defined routes; nav items exist only for roles that can use them), placeholder text (none), clickable phone number (none published).

## 5. What was and was not verified

Verified here:
- `npm run typecheck` and `npm run build` pass.
- A server-render harness (kept outside the repo) rendered the shell, work queue, referral workspace, step list, sign-in, policy pages and 404 against fixture data for clinician, staff, administrator and specialist roles, at desktop and phone widths. It checked: one `h1` per page, no skipped heading levels, tab list semantics (8 tabs, one selected, one tab stop), no em dashes or emoji, footer and skip link present, navigation per role, and that the strings the existing Playwright suite asserts are not duplicated by new text.
- The state logic produced sensible steps and next actions for 11 referral situations, for clinicians and non-clinicians.
- Colour contrast ratios, computed.

Not verified (no browser could be installed in the build environment):
- How it actually looks. No screenshots were taken.
- The Playwright suite (`npx playwright test e2e/smoke.spec.ts`) was not run. Tab names, button names, field labels and the single `h1` the tests depend on were kept.
- Phone-width visual check, keyboard walk-through and a screen reader pass.

## 6. Suggested next steps for the team
1. Run the stack, look at every screen on a desktop and a phone, and run the smoke suite. Regenerate `docs/screenshots` (the old ones show the previous design).
2. Set `VITE_OPERATOR_NAME` and `VITE_CONTACT_EMAIL`. The Dockerfile accepts them; add them under `web.build.args` in `docker-compose.prod.yml` (owned by Member 2).
3. Have the institution's legal and clinical governance advisers review the three policy pages before any real data is used.
4. Add Playwright checks for the journey (step states change as blockers clear) and for the policy pages and 404.

## 7. Files
New: `theme.ts`, `components/{Brand,Notify,ErrorBoundary}.tsx`, `features/referrals/{Journey.tsx,steps.ts}`, `features/workqueue/queue.ts`, `features/auth/{SignIn,NotFound}.tsx`, `features/legal/LegalPages.tsx`, `public/favicon.svg`.
Rewritten: `App.tsx`, `main.tsx`, `index.html`, `styles.css`, `components/{Layout,common}.tsx`, `features/referrals/{ReferralWorkspace,OverviewTab}.tsx`, `features/workqueue/WorkQueue.tsx`.
Light edits: `ReferralList.tsx`, `hooks.ts`, `Dockerfile`, and em dash or icon replacements in `FlagCard`, `EvidenceRef`, `BriefTab`, `RulesReview`, `MedicationsTab`, `DocumentsTab`, `DocumentReview`, `AuditTab`, `FollowThroughTab`, `SpecialistCase`, `LabWorkspace`.

Because the redesign crosses the three members' UI folders (docs/architecture.md section 5), each owner should review their files before merge.
