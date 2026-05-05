# pdf-parser-frontend

Next.js web application for the PDF Parser SaaS. Provides real-time pipeline progress, interactive PDF viewing with bounding-box overlays, and a synchronized Markdown panel where hovering a PDF region highlights the matching text — and vice versa.

## Structure

```
frontend/
├── app/
│   ├── layout.tsx              Root layout — dark theme, TanStack Query provider
│   ├── page.tsx                Home — upload zone + job options + job history
│   ├── providers.tsx           QueryClient provider ("use client")
│   └── jobs/[id]/
│       └── page.tsx            Job detail — step progress / PDF viewer + logs / Markdown
├── components/
│   ├── pdf-viewer/
│   │   ├── PdfViewer.tsx       pdfjs-dist canvas, page navigation, bbox overlay
│   │   └── BboxOverlay.tsx     Absolutely-positioned hover regions over the canvas
│   ├── markdown-viewer/
│   │   └── MarkdownPanel.tsx   Chunked react-markdown with hover highlight + scroll sync
│   └── ui/
│       ├── UploadZone.tsx      Drag-and-drop + click-to-browse PDF uploader
│       ├── JobOptions.tsx      Pre-submit options — page selection + segment refinement
│       ├── StepProgress.tsx    10-step pipeline progress panel (shown while running)
│       └── LogConsole.tsx      Color-coded live log stream with auto-scroll
├── lib/
│   ├── api.ts                  Typed API client (fetch + EventSource SSE)
│   └── store.ts                Zustand store (hoveredSegmentId, currentPage)
└── public/
    └── pdf.worker.min.mjs      pdfjs worker (copied by next.config.ts at build time)
```

## Quick Start

### Prerequisites

- Node.js 22+
- Running backend API (`make dev-api` or `docker compose up api`)

### Install & Run

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000
```

### Configure

```bash
# frontend/.env.local  (defaults to localhost:8000 if not set)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Production Build

```bash
npm run build
npm start
```

### Docker

```bash
# From repo root — build context includes frontend/
docker build -t pdf-parser-frontend -f frontend/Dockerfile .

docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://api:8000/api/v1 \
  pdf-parser-frontend
```

Or with docker compose (includes frontend profile):
```bash
docker compose --profile frontend up --build
```

## User Flow

1. **Upload** — drop a PDF on the upload zone or click to browse
2. **Configure** — choose pages (entire doc or single page N) and which segment types to refine (code, tables, figures)
3. **Submit** — click "Start Processing →"; the job is queued in Redis
4. **Live progress** — left panel shows a 10-step progress indicator; right panel streams live pipeline logs via SSE
5. **Result** — once done, left panel renders the PDF canvas; right panel shows the extracted Markdown
6. **Interact** — hover a bounding box on the PDF → matching Markdown chunk highlights (and vice versa)
7. **Download** — click "Download" in the header to save the Markdown file

## Key Interactions

**Hover sync**
- A single Zustand atom `hoveredSegmentId` is shared between `BboxOverlay` and `MarkdownPanel`
- Hovering a PDF bounding box sets the atom → `MarkdownPanel` highlights and scrolls to that chunk
- Hovering a Markdown chunk sets the atom → `BboxOverlay` highlights the corresponding PDF region

## Tech Stack

| Package | Purpose |
|---------|---------|
| Next.js (App Router) | Framework — `use(params)` for async route params |
| React 19 | UI |
| TypeScript | Type safety |
| Tailwind CSS v4 | Styling |
| TanStack Query v5 | Server state — job polling |
| Zustand | Client state — hover sync between panels |
| pdfjs-dist | PDF rendering to canvas |
| react-markdown + remark-gfm | Full GFM Markdown rendering (tables, code, etc.) |
| Framer Motion | Smooth hover highlight animations |
| lucide-react | Icons |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server |
| `npm run build` | Production build |
| `npm start` | Start production server |
| `npm run lint` | ESLint |
