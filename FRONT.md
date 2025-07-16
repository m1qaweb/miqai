# FRONT.md

Comprehensive Front‑End Implementation Plan for *The Insight Engine*
*Target AI: Gemini 2.5 pro  •  Date: July 11, 2025*

---

## Prelude: Optimized Prompt Injection

> **Role:** You are a senior React architect and performance engineer specializing in Next.js 14, Tailwind CSS, and cutting‑edge front‑end ecosystems.
> **Task:** Produce a **detailed**, **example‑rich**, **code‑annotated** FRONT.md plan covering architecture, UI/UX, integrations, testing, and deployment.
> **Tone:** Expert consultative—concise yet comprehensive, with best‑practice rationales.

**Insert this preamble when invoking Gemini 2.5 pro** to unlock maximal detail, sample snippets, and actionable insights.

---

## 1. Strategic Objectives

1. **Performance First:** Achieve LCP < 1.2 s, TBT < 100 ms, CLS < 0.02.
2. **Scalable UX:** Modular, theme‑aware components with dynamic theming.
3. **Dev DX:** Developer‑friendly architecture: auto‑typed APIs, visual component library, CI‑guarded quality.

---

## 2. Refined Tech Ecosystem

| Category                | Toolset                                         | Rationale                                           |
| ----------------------- | ----------------------------------------------- | --------------------------------------------------- |
| Framework & SSR/SSG     | Next.js 14 (App Router, RSC)                    | Hybrid SSG/SSR, partial hydration, Turbopack optics |
| Styling                 | Tailwind CSS JIT + Stitches + Shadcn/UI         | Ultra‑fast JIT, zero‑runtime styling, UI primitives |
| UI Primitives           | Radix UI + Headless UI + @ariakit/react         | Unstyled, accessible building blocks                |
| State & Data            | Zustand + TanStack Query + SWR for ISR          | Local/global state, cache‑first & revalidation      |
| API Contracts           | tRPC + Zod schemas                              | End‑to‑end type safety, input validation            |
| Animations              | Framer Motion + Motion One                      | High‑performance, interruptible animations          |
| Forms & Validation      | React Hook Form + Zod + Yup                     | Minimal rerenders, declarative schemas              |
| Icons & Graphics        | Lucide‑React + unDraw API                       | Lightweight, dynamic SVGs                           |
| Dev Environment         | Turborepo Monorepo + pnpm                       | Workspace scaling, fast CI                          |
| Component Documentation | Storybook v7 + MDX + Chromatic                  | Living style guide, visual regression tests         |
| Testing                 | Jest + React Testing Library + Playwright + Axe | Unit, integration, E2E, and accessibility checks    |
| Monitoring & Metrics    | web-vitals + Sentry + LogRocket                 | Real‑time metrics and error insights                |
| CI/CD                   | GitHub Actions → Vercel → Cloudflare CDN        | Automated checks, edge distribution                 |

---

## 3. Design System & UX Blueprint

1. **Design Tokens & Theming**

   * Central JSON of colors, fonts, spacings.
   * Two-level theming: light/dark + high‑contrast.
2. **Atomic Component Library**

   * Define atoms, molecules, organisms in Storybook.
   * Example:

   ```tsx
   // Button.tsx (atom)
   import { forwardRef } from 'react';
   import { cva } from 'class-variance-authority';

   const buttonStyles = cva('inline-flex items-center justify-center rounded-lg', {
     variants: { size: { sm: 'px-3 py-1.5', md: 'px-4 py-2' } },
     defaultVariants: { size: 'md' },
   });

   export const Button = forwardRef(({ size, children, ...props }, ref) => (
     <button ref={ref} className={buttonStyles({ size })} {...props}>{children}</button>
   ));
   ```
3. **Accessibility & Internationalization**

   * ARIA roles, keyboard nav, screen‑reader labels.
   * i18n via `next-intl`, locale routing.
4. **Micro‑Interactions**

   * Use Framer Motion’s `animatePresence` for modals, `useScroll` for header transitions.

---

## 4. Architecture & Code Organization

```
/my-app
 ├─ /app
 │   ├─ layout.tsx            # Global providers, theme
 │   ├─ page.tsx              # Marketing SSG pages
 │   └─ /playground
 │       ├─ /summarization     # Chat UI & streaming data
 │       └─ /clips             # Clip carousel & filters
 ├─ /components               # Reusable atoms/molecules
 ├─ /hooks                    # useUploadVideo, useSummary
 ├─ /lib
 │   ├─ api.ts                # tRPC client + auth
 │   └─ queryClient.ts        # React Query config
 ├─ /styles                   # globals.css, stitches config
 ├─ /tests                    # unit + integration + axe tests
 └─ /scripts                  # prebuild, lint, analyze
```

**Key Patterns:**

* **Colocation** of tests and CSS modules.
* **Barrel exports** in `/components/index.ts`.

---

## 5. Data & Integration Flow

1. **tRPC Router**: `appRouter` with procedures for `upload`, `summarize`, `clips` (Zod schemas).
2. **Client Hooks**: Prefetch summary on upload success; staleTime = 5 min.
3. **WebSocket Streaming**: SSE for real‑time summary; fallback to polling.

Sample Hook:

```ts
export function useSummary(videoId: string) {
  return trpc.summarize.useInfiniteQuery({ videoId }, {
    getNextPageParam: (last) => last.nextCursor,
  });
}
```

---

## 6. Performance & Optimization

* **Edge Caching**: ISR with `revalidate: 30` on static pages.
* **Resource Hints**: `<link rel="preconnect">` on APIs, `<link rel="preload">` for LCP image.
* **Lazy Module Loading**: `dynamic(() => import('chart.js'), { ssr: false })`.
* **Asset Compression**: Brotli via Vercel settings.

---

## 7. Testing & QA Protocol

* **Unit Tests:** Jest + RTL; snapshot minimal.
* **E2E Scenarios:** Playwright CI with cross‑browser matrix.
* **Accessibility:** `@axe-core/playwright` hooks in CI.
* **Visual Regression:** Chromatic gating on PR.

---

## 8. CI/CD & Observability

1. **GitHub Actions**:

   * `lint` → `build` → `test` → `storybook` → `deploy-preview`.
   * Secrets: `VERCEL_TOKEN`, Sentry DSN.
2. **Vercel & Cloudflare**:

   * Edge functions for data‑heavy routes.
   * Custom cache rules for static assets.
3. **Monitoring**:

   * Sentry release tagging via Git SHA.
   * Web Vitals Dashboard in Vercel Analytics.

---

## 9. Roadmap & Sprint Breakdown

| Sprint | Focus                          | Output                               |
| ------ | ------------------------------ | ------------------------------------ |
| 1      | Design System & Monorepo Setup | Tokens, Storybook, CI baseline       |
| 2–3    | Playground 1 Core UI           | Chat interface, streaming components |
| 4–5    | Playground 2 Core UI           | Clip carousel, filter panel          |
| 6      | Perf & Accessibility           | Lighthouse ≥ 95, WCAG AA compliance  |
| 7      | Testing & QA                   | Full test suite, visual regressions  |
| 8      | Deployment & Observability     | Production rollout, monitoring setup |

---

## 10. Continuous Improvement

* **Monthly Audits:** Lighthouse, Sentry trends, user feedback.
* **Component Versioning:** Semantic versioning and changelogs.
* **UX Research:** Bi‑weekly user testing sessions.

---
