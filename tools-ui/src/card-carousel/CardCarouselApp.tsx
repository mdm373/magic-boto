import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { App, McpUiHostContext } from "@modelcontextprotocol/ext-apps";

import { createOnToolResult } from "../utils/mcpToolResultTextJson";

// ── Tunables ──────────────────────────────────────────────────────────────────

/** Cards per page: cols (from width) × rows (from height), capped at a 3×3 grid. */
const PAGE_ROWS_MAX = 3;
const PAGE_ROWS_MIN = 1;
const GRID_COLS_MAX = 3;
/** Page's own top+bottom padding (1.5rem each, 16px root) + nav row + requested safety
 *  margin so the last visible row never grazes the fold. Approximate, not measured — a
 *  little unused space at the bottom is fine; a clipped row is not. */
const PAGE_VERTICAL_CHROME_PX = 48;
const NAV_ROW_ESTIMATED_HEIGHT_PX = 70;
const HEIGHT_SAFETY_BUFFER_PX = 32;
/**
 * Never shrink a card below its designed size (200, matches CARD_NORMAL_WIDTH below) — a
 * cramped card is unreadable regardless of column count, and it also breaks the focus-zoom
 * effect's proportions (a scaled-up focused card next to undersized siblings looks broken).
 * Drop to fewer columns instead; on a phone-width viewport this correctly lands on 1.
 */
const CARD_MIN_WIDTH = 200;

const CARD_NORMAL_WIDTH = 200;
/** How much wider the focused card is vs normal (was 44%; +20% vs that → 72.8% larger width). */
const FOCUS_EXTRA_WIDTH_PERCENT = 72.8;
const FOCUS_WIDTH_MULTIPLIER = 1 + FOCUS_EXTRA_WIDTH_PERCENT / 100;
/**
 * Soft, wide focus halo — box-shadow avoids layout shift. Two layers: faint
 * solid ring + blurred wash (tweak opacities / px here only).
 */
const FOCUS_RING_BOX_SHADOW =
  "0 0 0 4px color-mix(in srgb, var(--color-border-primary) 28%, transparent), 0 0 22px 6px color-mix(in srgb, var(--color-text-tertiary) 16%, transparent)";

/** Single-row: top/bottom inset inside the frame for ring blur + scaled paint (px each side). */
const SINGLE_ROW_VERTICAL_INSET_PX = 28;

const GAP_PX = 16;
/** Page change: long enough to read; easing keeps motion smooth. */
const NAV_DURATION_MS = 520;
/**
 * Slide distance as % of each grid’s own width (CSS transform % is relative to
 * the element being transformed). Reads as “this whole page moves off” rather
 * than a tiny nudge.
 */
const PAGE_SLIDE_OUT_PERCENT = 48;
const PAGE_SLIDE_IN_FROM_PERCENT = 42;

// Scryfall images ~488×680 — placeholder uses 5:7 (h/w).
const CARD_NORMAL_HEIGHT = Math.ceil((CARD_NORMAL_WIDTH * 7) / 5);

// ── Types ─────────────────────────────────────────────────────────────────────

type CardMeta = Readonly<{
  card_id: string;
  name: string;
  scryfall_id: string;
}>;

type CardsPageResult = Readonly<{
  items: readonly CardMeta[];
  total: number;
}>;

type ImageContent = Readonly<{ type: string; data?: string; mimeType?: string }>;

const CarouselStatusValues = ["idle", "loading", "ready", "error"] as const;
type CarouselStatusValue = (typeof CarouselStatusValues)[number];

type CarouselState = Readonly<{
  status: CarouselStatusValue;
  cards: readonly CardMeta[];
  total: number;
  startIndex: number;
  selectedId: string | null;
}>;

/** Full-page transition: outgoing grid fades/slides away, incoming replaces it. */
type PageNavTransition = Readonly<{
  dir: "left" | "right";
  outgoing: readonly CardMeta[];
  incoming: readonly CardMeta[];
  /** Preserve focus on the page being replaced until it leaves (then cleared at settle). */
  outgoingSelectedId: string | null;
}>;

const INITIAL_STATE: CarouselState = {
  status: "idle",
  cards: [],
  total: 0,
  startIndex: 0,
  selectedId: null,
};

// ── Layout helpers ────────────────────────────────────────────────────────────

/** Largest column count (up to GRID_COLS_MAX) that keeps each card at least CARD_MIN_WIDTH,
 *  falling back to fewer, wider columns as the container narrows (down to a single column). */
function computeGridMetrics(containerWidth: number): {
  cols: number;
  cardWidth: number;
  cardHeight: number;
} {
  if (containerWidth <= 0) {
    return { cols: GRID_COLS_MAX, cardWidth: CARD_NORMAL_WIDTH, cardHeight: CARD_NORMAL_HEIGHT };
  }
  for (let cols = GRID_COLS_MAX; cols > 1; cols--) {
    const perCard = (containerWidth - (cols - 1) * GAP_PX) / cols;
    if (perCard >= CARD_MIN_WIDTH) {
      const cardWidth = Math.min(CARD_NORMAL_WIDTH, Math.floor(perCard));
      return { cols, cardWidth, cardHeight: Math.ceil((cardWidth * 7) / 5) };
    }
  }
  const cardWidth = Math.min(CARD_NORMAL_WIDTH, Math.floor(containerWidth));
  return { cols: 1, cardWidth, cardHeight: Math.ceil((cardWidth * 7) / 5) };
}

/** How many card rows fit in the available viewport height, from 1 up to PAGE_ROWS_MAX.
 *  A height of 0 means "host hasn't told us" (not "host gave us zero space") — assume
 *  generous desktop space, same fallback stance as computeGridMetrics takes for width. */
function computeRowsPerPage(viewportHeight: number, cardHeight: number): number {
  if (viewportHeight <= 0) return PAGE_ROWS_MAX;
  const budget =
    viewportHeight - PAGE_VERTICAL_CHROME_PX - NAV_ROW_ESTIMATED_HEIGHT_PX - HEIGHT_SAFETY_BUFFER_PX;
  if (budget <= 0) return PAGE_ROWS_MIN;
  const rows = Math.floor((budget + GAP_PX) / (cardHeight + GAP_PX));
  return Math.min(PAGE_ROWS_MAX, Math.max(PAGE_ROWS_MIN, rows));
}

/** Host gives either an exact size or just a cap (width/height independently) — resolve
 *  both to a usable number, 0 meaning "host hasn't told us yet" (caller applies a fallback). */
function resolveContainerSize(
  dimensions: McpUiHostContext["containerDimensions"],
): { width: number; height: number } {
  if (!dimensions) return { width: 0, height: 0 };
  const width = "width" in dimensions ? dimensions.width : (dimensions.maxWidth ?? 0);
  const height = "height" in dimensions ? dimensions.height : (dimensions.maxHeight ?? 0);
  return { width, height };
}

function slicePage(
  cards: readonly CardMeta[],
  startIndex: number,
  pageSize: number,
): readonly CardMeta[] {
  return cards.slice(startIndex, startIndex + pageSize);
}

/** First index of the last page (aligned to pageSize steps from 0). */
function lastPageStart(cardsLength: number, pageSize: number): number {
  if (cardsLength <= 0) return 0;
  if (cardsLength <= pageSize) return 0;
  return Math.floor((cardsLength - 1) / pageSize) * pageSize;
}

/** Rows needed for `visibleCount` cards at the current column count. */
function layoutTierRowCount(visibleCount: number, cols: number): number {
  if (visibleCount <= 0) return 1;
  return Math.ceil(visibleCount / cols);
}

/**
 * Fixed outer frame height. Multi-row tiers use normal row heights (scale overlaps).
 * Single-row tier: scaled card height + vertical insets for the soft ring and paint safety.
 */
function fixedCardFrameHeightPx(visibleCount: number, cols: number, cardHeight: number): number {
  const rows = layoutTierRowCount(visibleCount, cols);
  if (rows === 1) {
    return Math.ceil(cardHeight * FOCUS_WIDTH_MULTIPLIER) + 2 * SINGLE_ROW_VERTICAL_INSET_PX;
  }
  return rows * cardHeight + (rows - 1) * GAP_PX;
}

/** `transform-origin` so scale grows inward / stays in view by grid position. */
function focusTransformOrigin(
  rowIndex: number,
  totalRows: number,
  colIndex: number,
  colsInThisRow: number,
): string {
  const y: "top" | "center" | "bottom" =
    totalRows <= 1 ? "top" : rowIndex === 0 ? "top" : rowIndex >= totalRows - 1 ? "bottom" : "center";
  const x: "left" | "center" | "right" =
    colsInThisRow <= 1 ? "center" : colIndex === 0 ? "left" : colIndex >= colsInThisRow - 1 ? "right" : "center";
  return `${x} ${y}`;
}

function chunkIntoRows(
  pageCards: readonly CardMeta[],
  cols: number,
): readonly (readonly CardMeta[])[] {
  const rows: CardMeta[][] = [];
  for (let i = 0; i < pageCards.length; i += cols) {
    rows.push(pageCards.slice(i, i + cols) as CardMeta[]);
  }
  return rows;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const PAGE_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100%",
  minWidth: 0,
  maxWidth: "100%",
  boxSizing: "border-box",
  overflowX: "clip",
  padding: "1.5rem",
  gap: "1.5rem",
  backgroundColor: "var(--color-background-tertiary)",
  color: "var(--color-text-tertiary)",
};

const NAV_ROW_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "1.25rem",
  flexShrink: 0,
  paddingTop: "0.25rem",
  paddingBottom: "1.25rem",
  position: "relative",
  zIndex: 5,
};

const NAV_BUTTON_BASE: React.CSSProperties = {
  background: "none",
  border: "1px solid currentColor",
  borderRadius: "var(--border-radius-md, 6px)",
  color: "currentColor",
  fontSize: "2rem",
  lineHeight: 1,
  padding: "0.375rem 1rem",
};

const COUNTER_STYLE: React.CSSProperties = {
  fontSize: "0.8125rem",
  opacity: 0.65,
  minWidth: "10ch",
  textAlign: "center",
};

const PLACEHOLDER_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "rgba(128,128,128,0.15)",
  borderRadius: "var(--border-radius-md, 6px)",
  fontSize: "0.75rem",
  opacity: 0.6,
  aspectRatio: "5 / 7",
  width: "100%",
};

type CardGridProps = Readonly<{
  pageCards: readonly CardMeta[];
  selectedId: string | null;
  images: Readonly<Record<string, string>>;
  onToggleSelect: (cardId: string) => void;
  /** When false, skip imageAppear bookkeeping (transition clone). */
  trackShownImages: boolean;
  shownImagesRef: React.MutableRefObject<Set<string>>;
  cols: number;
  cardWidth: number;
  cardHeight: number;
}>;

function CardGrid({
  pageCards,
  selectedId,
  images,
  onToggleSelect,
  trackShownImages,
  shownImagesRef,
  cols,
  cardWidth,
  cardHeight,
}: CardGridProps) {
  const rows = useMemo(() => chunkIntoRows(pageCards, cols), [pageCards, cols]);
  const totalRows = rows.length;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: `${GAP_PX}px`,
        width: "100%",
        maxWidth: "100%",
        minWidth: 0,
        overflowX: "clip",
        overflowY: "visible",
      }}
    >
      {rows.map((row, ri) => (
        <div
          key={`row-${ri}`}
          style={{
            display: "flex",
            flexDirection: "row",
            justifyContent: "center",
            alignItems: "center",
            gap: `${GAP_PX}px`,
            flexWrap: "nowrap",
            maxWidth: "100%",
            minWidth: 0,
            minHeight: cardHeight,
            height: cardHeight,
            overflow: "visible",
          }}
        >
          {row.map((card, ci) => {
            const isSelected = selectedId === card.card_id;
            const imageState = images[card.card_id];
            const isNewImage =
              trackShownImages &&
              imageState != null &&
              imageState !== "error" &&
              !shownImagesRef.current.has(card.card_id);
            if (isNewImage) shownImagesRef.current.add(card.card_id);

            const origin = focusTransformOrigin(ri, totalRows, ci, row.length);
            const scale = isSelected ? FOCUS_WIDTH_MULTIPLIER : 1;

            return (
              <div
                key={card.card_id}
                role="button"
                tabIndex={0}
                onClick={() => onToggleSelect(card.card_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onToggleSelect(card.card_id);
                  }
                }}
                style={{
                  width: cardWidth,
                  height: cardHeight,
                  flexShrink: 0,
                  position: "relative",
                  zIndex: isSelected ? 40 : 1,
                  cursor: "pointer",
                  overflow: "visible",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <div
                  style={{
                    width: cardWidth,
                    borderRadius: "var(--border-radius-md, 6px)",
                    transform: `scale(${scale})`,
                    transformOrigin: origin,
                    boxShadow: isSelected ? FOCUS_RING_BOX_SHADOW : "none",
                    transition:
                      "transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.28s ease",
                    willChange: "transform",
                  }}
                >
                  {imageState && imageState !== "error" ? (
                    <img
                      src={imageState}
                      alt={card.name}
                      style={{
                        width: "100%",
                        maxWidth: "100%",
                        height: "auto",
                        display: "block",
                        verticalAlign: "top",
                        objectFit: "cover",
                        aspectRatio: "5 / 7",
                        borderRadius: "var(--border-radius-md, 6px)",
                        animation: isNewImage ? "imageAppear 200ms ease" : undefined,
                      }}
                    />
                  ) : imageState === "error" ? (
                    <div style={PLACEHOLDER_STYLE}>{card.name}</div>
                  ) : (
                    <div style={PLACEHOLDER_STYLE}>Loading…</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function CardCarouselApp() {
  const [state, setState] = useState<CarouselState>(INITIAL_STATE);
  const [images, setImages] = useState<Readonly<Record<string, string>>>({});
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [pageNavTransition, setPageNavTransition] = useState<PageNavTransition | null>(null);
  const [navigating, setNavigating] = useState(false);

  const appRef = useRef<App | null>(null);
  const navigatingRef = useRef(false);
  const fetchedRef = useRef<Set<string>>(new Set());
  const shownImagesRef = useRef<Set<string>>(new Set());
  const stateRef = useRef(state);
  stateRef.current = state;
  const imagesRef = useRef(images);
  imagesRef.current = images;

  // Host-reported container size, not a DOM measurement: this SDK's apps report their own
  // size to the host (see McpUiSizeChangedNotification) rather than being handed a fixed
  // viewport — an auto-height iframe model where our own rendered size isn't an external
  // constraint at all. containerDimensions is the host's actual allotted space for us.
  const { width: containerWidth, height: containerHeight } = useMemo(
    () => resolveContainerSize(hostContext?.containerDimensions),
    [hostContext?.containerDimensions],
  );
  const { cols, cardWidth, cardHeight } = useMemo(
    () => computeGridMetrics(containerWidth),
    [containerWidth],
  );
  const rowsPerPage = useMemo(
    () => computeRowsPerPage(containerHeight, cardHeight),
    [containerHeight, cardHeight],
  );
  const pageSize = cols * rowsPerPage;
  const pageSizeRef = useRef(pageSize);
  pageSizeRef.current = pageSize;

  const { app, isConnected, error } = useApp({
    appInfo: { name: "CardCarouselApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (createdApp) => {
      appRef.current = createdApp;

      createdApp.ontoolinput = async () => {
        fetchedRef.current.clear();
        shownImagesRef.current.clear();
        setImages({});
        setPageNavTransition(null);
        setState({ ...INITIAL_STATE, status: "loading" });
      };

      createdApp.ontoolresult = createOnToolResult<CardsPageResult>(
        (data) => {
          const cards = data.items ?? [];
          setState({
            status: "ready",
            cards,
            total: data.total ?? 0,
            startIndex: 0,
            selectedId: cards.length === 1 ? cards[0].card_id : null,
          });
        },
        () => setState((s) => ({ ...s, status: "error" })),
      );

      createdApp.onteardown = async () => ({});
      createdApp.onerror = console.error;
      createdApp.onhostcontextchanged = (ctx) =>
        setHostContext((prev) => ({ ...prev, ...ctx }));
    },
  });

  useEffect(() => {
    if (app) {
      appRef.current = app;
      setHostContext(app.getHostContext());
    }
  }, [app]);

  useHostStyles(app, app?.getHostContext());

  const { status, startIndex, cards } = state;
  useEffect(() => {
    if (status !== "ready") return;
    const currentApp = appRef.current;
    if (!currentApp) return;

    const stablePage = slicePage(cards, startIndex, pageSize);
    const toLoad = pageNavTransition
      ? [...pageNavTransition.outgoing, ...pageNavTransition.incoming]
      : stablePage;

    for (const card of toLoad) {
      if (fetchedRef.current.has(card.card_id)) continue;
      fetchedRef.current.add(card.card_id);
      void currentApp
        .callServerTool({ name: "get_card_image", arguments: { scryfall_id: card.scryfall_id } })
        .then((result) => {
          const imgContent = result.content as readonly ImageContent[];
          const img = imgContent.find((c) => c.type === "image");
          const dataUrl =
            img?.data && img.mimeType ? `data:${img.mimeType};base64,${img.data}` : "error";
          setImages((prev) => ({ ...prev, [card.card_id]: dataUrl }));
        })
        .catch(() => {
          setImages((prev) => ({ ...prev, [card.card_id]: "error" }));
        });
    }
  }, [status, startIndex, cards, pageNavTransition, pageSize]);

  const navigate = useCallback((dir: "prev" | "next") => {
    if (navigatingRef.current) return;
    const s = stateRef.current;
    const size = pageSizeRef.current;
    const lastStart = lastPageStart(s.cards.length, size);
    const newIndex =
      dir === "next" ? Math.min(s.startIndex + size, lastStart) : Math.max(0, s.startIndex - size);
    if (newIndex === s.startIndex) return;

    navigatingRef.current = true;
    setNavigating(true);

    const outgoing = slicePage(s.cards, s.startIndex, size);
    const incoming = slicePage(s.cards, newIndex, size);
    const currentStable = new Set(outgoing.map((c) => c.card_id));
    shownImagesRef.current = currentStable;

    const outgoingSelectedId =
      s.selectedId !== null && outgoing.some((c) => c.card_id === s.selectedId)
        ? s.selectedId
        : null;

    setPageNavTransition({
      dir: dir === "next" ? "left" : "right",
      outgoing,
      incoming,
      outgoingSelectedId,
    });

    setTimeout(() => {
      const imgSnap = imagesRef.current;
      for (const card of [...outgoing, ...incoming]) {
        if (imgSnap[card.card_id] && imgSnap[card.card_id] !== "error") {
          shownImagesRef.current.add(card.card_id);
        }
      }
      setState((prev) => ({ ...prev, startIndex: newIndex, selectedId: null }));
      setPageNavTransition(null);
      navigatingRef.current = false;
      setNavigating(false);
    }, NAV_DURATION_MS);
  }, []);

  const toggleSelect = useCallback((cardId: string) => {
    setState((prev) => ({
      ...prev,
      selectedId: prev.selectedId === cardId ? null : cardId,
    }));
  }, []);

  const insets = hostContext?.safeAreaInsets;
  const pageStyle: React.CSSProperties = insets
    ? {
        ...PAGE_STYLE,
        padding: undefined,
        paddingTop: `max(1.5rem, ${insets.top}px)`,
        paddingRight: `max(1.5rem, ${insets.right}px)`,
        paddingBottom: `max(1.5rem, ${insets.bottom}px)`,
        paddingLeft: `max(1.5rem, ${insets.left}px)`,
      }
    : PAGE_STYLE;

  if (error) return <div style={pageStyle}><strong>Error:</strong> {error.message}</div>;
  if (!isConnected || state.status === "idle") return <div style={pageStyle}>Connecting…</div>;
  if (state.status === "loading") return <div style={pageStyle}>Loading cards…</div>;
  if (state.status === "error") return <div style={pageStyle}>Could not load cards.</div>;
  if (state.cards.length === 0) return <div style={pageStyle}>No cards found.</div>;

  const pageCards = slicePage(state.cards, startIndex, pageSize);
  const visibleCount = pageCards.length;
  const lastStart = lastPageStart(state.cards.length, pageSize);
  const canPrev = startIndex > 0;
  const canNext = startIndex < lastStart;

  const cardFramePx = pageNavTransition
    ? Math.max(
        fixedCardFrameHeightPx(pageNavTransition.outgoing.length, cols, cardHeight),
        fixedCardFrameHeightPx(pageNavTransition.incoming.length, cols, cardHeight),
      )
    : fixedCardFrameHeightPx(visibleCount, cols, cardHeight);

  const maxCardsInFrame = pageNavTransition
    ? Math.max(pageNavTransition.outgoing.length, pageNavTransition.incoming.length)
    : visibleCount;
  const pinGridToTop = layoutTierRowCount(maxCardsInFrame, cols) === 1;
  const gridAlignItems: React.CSSProperties["alignItems"] = pinGridToTop ? "flex-start" : "center";
  const singleRowInnerChrome: React.CSSProperties = pinGridToTop
    ? {
        paddingTop: SINGLE_ROW_VERTICAL_INSET_PX,
        paddingBottom: SINGLE_ROW_VERTICAL_INSET_PX,
        boxSizing: "border-box",
      }
    : {};

  const outName = pageNavTransition?.dir === "left" ? "pageOutLeft" : "pageOutRight";
  const inName = pageNavTransition?.dir === "left" ? "pageInLeft" : "pageInRight";

  const cardAreaStyle: React.CSSProperties = {
    flex: "0 0 auto",
    height: cardFramePx,
    minHeight: cardFramePx,
    minWidth: 0,
    width: "100%",
    maxWidth: "100%",
    overflowX: "clip",
    overflowY: "visible",
    overscrollBehavior: "contain",
    display: "flex",
    alignItems: gridAlignItems,
    justifyContent: "center",
    boxSizing: "border-box",
    position: "relative",
    zIndex: 1,
    transition: "height 0.35s ease, min-height 0.35s ease",
  };

  return (
    <>
      <style>{`
        @keyframes pageOutLeft {
          from { opacity: 1; transform: translateX(0); }
          to   { opacity: 0; transform: translateX(-${PAGE_SLIDE_OUT_PERCENT}%); }
        }
        @keyframes pageInLeft {
          from { opacity: 0; transform: translateX(${PAGE_SLIDE_IN_FROM_PERCENT}%); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes pageOutRight {
          from { opacity: 1; transform: translateX(0); }
          to   { opacity: 0; transform: translateX(${PAGE_SLIDE_OUT_PERCENT}%); }
        }
        @keyframes pageInRight {
          from { opacity: 0; transform: translateX(-${PAGE_SLIDE_IN_FROM_PERCENT}%); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes imageAppear {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>

      <div style={pageStyle}>
        <div style={cardAreaStyle}>
          {pageNavTransition ? (
            <div
              style={{
                position: "relative",
                width: "100%",
                height: cardFramePx,
                minHeight: cardFramePx,
                overflowX: "clip",
                overflowY: "visible",
                ...singleRowInnerChrome,
              }}
            >
              {/* Absolutely stacked so the (invisible) outgoing layer does not widen/tall the box after opacity hits 0. */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: gridAlignItems,
                  justifyContent: "center",
                  pointerEvents: "none",
                  zIndex: 0,
                  animation: `${outName} ${NAV_DURATION_MS}ms cubic-bezier(0.22, 1, 0.36, 1) forwards`,
                }}
              >
                <CardGrid
                  pageCards={pageNavTransition.outgoing}
                  selectedId={pageNavTransition.outgoingSelectedId}
                  images={images}
                  onToggleSelect={() => {}}
                  trackShownImages={false}
                  shownImagesRef={shownImagesRef}
                  cols={cols}
                  cardWidth={cardWidth}
                  cardHeight={cardHeight}
                />
              </div>
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: gridAlignItems,
                  justifyContent: "center",
                  pointerEvents: "auto",
                  zIndex: 1,
                  animation: `${inName} ${NAV_DURATION_MS}ms cubic-bezier(0.22, 1, 0.36, 1) forwards`,
                }}
              >
                <CardGrid
                  pageCards={pageNavTransition.incoming}
                  selectedId={null}
                  images={images}
                  onToggleSelect={() => {}}
                  trackShownImages={false}
                  shownImagesRef={shownImagesRef}
                  cols={cols}
                  cardWidth={cardWidth}
                  cardHeight={cardHeight}
                />
              </div>
            </div>
          ) : (
            <div
              style={{
                height: "100%",
                minHeight: "100%",
                width: "100%",
                maxWidth: "100%",
                minWidth: 0,
                overflowX: "clip",
                overflowY: "visible",
                display: "flex",
                alignItems: gridAlignItems,
                justifyContent: "center",
                ...singleRowInnerChrome,
              }}
            >
              <CardGrid
                pageCards={pageCards}
                selectedId={state.selectedId}
                images={images}
                onToggleSelect={toggleSelect}
                trackShownImages
                shownImagesRef={shownImagesRef}
                cols={cols}
                cardWidth={cardWidth}
                cardHeight={cardHeight}
              />
            </div>
          )}
        </div>

        <div style={NAV_ROW_STYLE}>
          <button
            onClick={() => navigate("prev")}
            disabled={!canPrev || navigating}
            style={{
              ...NAV_BUTTON_BASE,
              opacity: canPrev && !navigating ? 1 : 0.3,
              cursor: canPrev && !navigating ? "pointer" : "default",
            }}
            aria-label="Previous page"
          >
            ‹
          </button>

          <span style={COUNTER_STYLE}>
            {visibleCount === 0 ? "0" : `${startIndex + 1}–${startIndex + visibleCount}`} of{" "}
            {state.cards.length}
            {state.total > state.cards.length ? ` (${state.total} total)` : ""}
          </span>

          <button
            onClick={() => navigate("next")}
            disabled={!canNext || navigating}
            style={{
              ...NAV_BUTTON_BASE,
              opacity: canNext && !navigating ? 1 : 0.3,
              cursor: canNext && !navigating ? "pointer" : "default",
            }}
            aria-label="Next page"
          >
            ›
          </button>
        </div>
      </div>
    </>
  );
}
