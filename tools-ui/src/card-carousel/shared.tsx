import { useMemo } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";

/**
 * Layout/rendering primitives shared by the card-carousel variants (`CardCarouselApp` —
 * paged/keyframe — and `CardCarouselAppV2` — embla scroll-snap). Keep both variants visually
 * and structurally identical wherever behavior doesn't need to differ, so an A/B swap between
 * them isn't also an unintentional design change.
 */

// ── Tunables ──────────────────────────────────────────────────────────────────

/** Cards per page: cols (from width) × rows (from height), capped at a 3×3 grid. */
export const PAGE_ROWS_MAX = 3;
export const PAGE_ROWS_MIN = 1;
export const GRID_COLS_MAX = 3;
/** Page's own top+bottom padding (1.5rem each, 16px root) + nav row + requested safety
 *  margin so the last visible row never grazes the fold. Approximate, not measured — a
 *  little unused space at the bottom is fine; a clipped row is not. */
export const PAGE_VERTICAL_CHROME_PX = 48;
export const NAV_ROW_ESTIMATED_HEIGHT_PX = 70;
export const HEIGHT_SAFETY_BUFFER_PX = 32;
/**
 * Never shrink a card below its designed size (200, matches CARD_NORMAL_WIDTH below) — a
 * cramped card is unreadable regardless of column count, and it also breaks the focus-zoom
 * effect's proportions (a scaled-up focused card next to undersized siblings looks broken).
 * Drop to fewer columns instead; on a phone-width viewport this correctly lands on 1.
 */
export const CARD_MIN_WIDTH = 200;

export const CARD_NORMAL_WIDTH = 200;
/** How much wider the focused card is vs normal (was 44%; +20% vs that → 72.8% larger width). */
export const FOCUS_EXTRA_WIDTH_PERCENT = 72.8;
export const FOCUS_WIDTH_MULTIPLIER = 1 + FOCUS_EXTRA_WIDTH_PERCENT / 100;
/**
 * Soft, wide focus halo — box-shadow avoids layout shift. Two layers: faint
 * solid ring + blurred wash (tweak opacities / px here only).
 */
export const FOCUS_RING_BOX_SHADOW =
  "0 0 0 4px color-mix(in srgb, var(--color-border-primary) 28%, transparent), 0 0 22px 6px color-mix(in srgb, var(--color-text-tertiary) 16%, transparent)";

/** Single-row: top/bottom inset inside the frame for ring blur + scaled paint (px each side). */
export const SINGLE_ROW_VERTICAL_INSET_PX = 28;

export const GAP_PX = 16;

/**
 * Embla variant only: fraction of the scroller's width used to size the grid itself (via
 * `useGridLayout`'s `gridWidthFraction`) — i.e. peeking is allowed to cost a column on a
 * borderline-width desktop screen, same as it already does on mobile, rather than fighting to
 * preserve one. This is *only* a budget for column/card-size math, not the slide's own CSS
 * width — see `gridContentWidthPx`/the slide's inline width in `CardCarouselAppV2`. Sizing the
 * slide box itself to this fraction (instead of the grid's actual resulting content width)
 * previously left empty margin between the grid and its own slide edge whenever the grid didn't
 * fully use the budget (e.g. after a column drop) — `justifyContent: "center"` then centered
 * the cards inside that oversized box, so the peeking sliver near the boundary could land
 * entirely in that empty margin: blank space instead of the neighbor's actual cards.
 */
export const SLIDE_WIDTH_FRACTION = 0.8;

/**
 * Embla variant only: real blank gap (CSS `gap` on the slide track, not padding/margin on each
 * slide) between every pair of adjacent pages. Without an explicit gap, the peeking neighbor's
 * card can end up flush against the current page's edge card with no breathing room, reading as
 * an overlap rather than a clean partial-card peek.
 */
export const PAGE_GUTTER_PX = 20;

/** Natural width of a fixed-`cols` grid at `cardWidth` — used to size each embla slide to its
 *  actual content instead of a fixed fraction, so there's no empty margin inside the slide
 *  between the cards and the slide's own edge (see `SLIDE_WIDTH_FRACTION` above). */
export function gridContentWidthPx(cols: number, cardWidth: number): number {
  return cols * cardWidth + (cols - 1) * GAP_PX;
}

// Scryfall images ~488×680 — placeholder uses 5:7 (h/w).
export const CARD_NORMAL_HEIGHT = Math.ceil((CARD_NORMAL_WIDTH * 7) / 5);

// ── Types ─────────────────────────────────────────────────────────────────────

export type CardMeta = Readonly<{
  card_id: string;
  name: string;
  scryfall_id: string;
}>;

export type CardsPageResult = Readonly<{
  items: readonly CardMeta[];
  total: number;
}>;

export type ImageContent = Readonly<{ type: string; data?: string; mimeType?: string }>;

// ── Layout helpers ────────────────────────────────────────────────────────────

/** Largest column count (up to GRID_COLS_MAX) that keeps each card at least CARD_MIN_WIDTH,
 *  falling back to fewer, wider columns as the container narrows (down to a single column). */
export function computeGridMetrics(containerWidth: number): {
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
export function computeRowsPerPage(viewportHeight: number, cardHeight: number): number {
  if (viewportHeight <= 0) return PAGE_ROWS_MAX;
  const budget =
    viewportHeight - PAGE_VERTICAL_CHROME_PX - NAV_ROW_ESTIMATED_HEIGHT_PX - HEIGHT_SAFETY_BUFFER_PX;
  if (budget <= 0) return PAGE_ROWS_MIN;
  const rows = Math.floor((budget + GAP_PX) / (cardHeight + GAP_PX));
  return Math.min(PAGE_ROWS_MAX, Math.max(PAGE_ROWS_MIN, rows));
}

/** Host gives either an exact size or just a cap (width/height independently) — resolve
 *  both to a usable number, 0 meaning "host hasn't told us yet" (caller applies a fallback). */
export function resolveContainerSize(
  dimensions: McpUiHostContext["containerDimensions"],
): { width: number; height: number } {
  if (!dimensions) return { width: 0, height: 0 };
  const width = "width" in dimensions ? dimensions.width : (dimensions.maxWidth ?? 0);
  const height = "height" in dimensions ? dimensions.height : (dimensions.maxHeight ?? 0);
  return { width, height };
}

/** Resolve container size + grid metrics (cols/card size/rows-per-page/page size) from host
 *  context in one place, so every variant derives the same grid from the same inputs.
 *  `gridWidthFraction` (default 1, i.e. full container) lets a variant size its grid to a
 *  narrower slide than the full scroller width — e.g. the embla variant's peeking pages. */
export function useGridLayout(
  hostContext: McpUiHostContext | undefined,
  gridWidthFraction = 1,
): {
  containerWidth: number;
  containerHeight: number;
  cols: number;
  cardWidth: number;
  cardHeight: number;
  rowsPerPage: number;
  pageSize: number;
} {
  const { width: containerWidth, height: containerHeight } = useMemo(
    () => resolveContainerSize(hostContext?.containerDimensions),
    [hostContext?.containerDimensions],
  );
  const gridWidth = containerWidth * gridWidthFraction;
  const { cols, cardWidth, cardHeight } = useMemo(
    () => computeGridMetrics(gridWidth),
    [gridWidth],
  );
  const rowsPerPage = useMemo(
    () => computeRowsPerPage(containerHeight, cardHeight),
    [containerHeight, cardHeight],
  );
  return { containerWidth, containerHeight, cols, cardWidth, cardHeight, rowsPerPage, pageSize: cols * rowsPerPage };
}

export function slicePage(
  cards: readonly CardMeta[],
  startIndex: number,
  pageSize: number,
): readonly CardMeta[] {
  return cards.slice(startIndex, startIndex + pageSize);
}

/** First index of the last page (aligned to pageSize steps from 0). */
export function lastPageStart(cardsLength: number, pageSize: number): number {
  if (cardsLength <= 0) return 0;
  if (cardsLength <= pageSize) return 0;
  return Math.floor((cardsLength - 1) / pageSize) * pageSize;
}

/** Rows needed for `visibleCount` cards at the current column count. */
export function layoutTierRowCount(visibleCount: number, cols: number): number {
  if (visibleCount <= 0) return 1;
  return Math.ceil(visibleCount / cols);
}

/**
 * Fixed outer frame height. Multi-row tiers use normal row heights (scale overlaps).
 * Single-row tier: scaled card height + vertical insets for the soft ring and paint safety.
 */
export function fixedCardFrameHeightPx(visibleCount: number, cols: number, cardHeight: number): number {
  const rows = layoutTierRowCount(visibleCount, cols);
  if (rows === 1) {
    return Math.ceil(cardHeight * FOCUS_WIDTH_MULTIPLIER) + 2 * SINGLE_ROW_VERTICAL_INSET_PX;
  }
  return rows * cardHeight + (rows - 1) * GAP_PX;
}

/** `transform-origin` so scale grows inward / stays in view by grid position. */
export function focusTransformOrigin(
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

export function chunkIntoRows(
  pageCards: readonly CardMeta[],
  cols: number,
): readonly (readonly CardMeta[])[] {
  const rows: CardMeta[][] = [];
  for (let i = 0; i < pageCards.length; i += cols) {
    rows.push(pageCards.slice(i, i + cols) as CardMeta[]);
  }
  return rows;
}

/** Split a flat card list into fixed-size grid pages (last page may be shorter). */
export function chunkIntoPages(
  cards: readonly CardMeta[],
  pageSize: number,
): readonly (readonly CardMeta[])[] {
  if (pageSize <= 0) return cards.length > 0 ? [cards] : [];
  const pages: (readonly CardMeta[])[] = [];
  for (let i = 0; i < cards.length; i += pageSize) {
    pages.push(cards.slice(i, i + pageSize));
  }
  return pages;
}

// ── Styles ────────────────────────────────────────────────────────────────────

export const PAGE_STYLE: React.CSSProperties = {
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

export const NAV_ROW_STYLE: React.CSSProperties = {
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

export const NAV_BUTTON_BASE: React.CSSProperties = {
  background: "none",
  border: "1px solid currentColor",
  borderRadius: "var(--border-radius-md, 6px)",
  color: "currentColor",
  fontSize: "2rem",
  lineHeight: 1,
  padding: "0.375rem 1rem",
};

export const COUNTER_STYLE: React.CSSProperties = {
  fontSize: "0.8125rem",
  opacity: 0.65,
  minWidth: "10ch",
  textAlign: "center",
};

export const PLACEHOLDER_STYLE: React.CSSProperties = {
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

export function pageStyleWithInsets(
  insets: McpUiHostContext["safeAreaInsets"] | undefined,
): React.CSSProperties {
  if (!insets) return PAGE_STYLE;
  return {
    ...PAGE_STYLE,
    padding: undefined,
    paddingTop: `max(1.5rem, ${insets.top}px)`,
    paddingRight: `max(1.5rem, ${insets.right}px)`,
    paddingBottom: `max(1.5rem, ${insets.bottom}px)`,
    paddingLeft: `max(1.5rem, ${insets.left}px)`,
  };
}

// ── CardGrid ──────────────────────────────────────────────────────────────────

export type CardGridProps = Readonly<{
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
  /** False for a peeking (not the current) page in the embla variant — cards render inert:
   *  no click/keyboard activation, not tab-focusable. Defaults to true. */
  interactive?: boolean;
}>;

export function CardGrid({
  pageCards,
  selectedId,
  images,
  onToggleSelect,
  trackShownImages,
  shownImagesRef,
  cols,
  cardWidth,
  cardHeight,
  interactive = true,
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
        // Let the focus-zoom scale spill outside this grid's own box (e.g. into a peeking
        // neighbor page in the embla variant) — the real edge clipping is each variant's own
        // outer container (cardAreaStyle in CardCarouselApp, the embla scroller in V2).
        overflow: "visible",
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
                tabIndex={interactive ? 0 : -1}
                aria-hidden={!interactive}
                onClick={interactive ? () => onToggleSelect(card.card_id) : undefined}
                onKeyDown={
                  interactive
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onToggleSelect(card.card_id);
                        }
                      }
                    : undefined
                }
                style={{
                  width: cardWidth,
                  height: cardHeight,
                  flexShrink: 0,
                  position: "relative",
                  zIndex: isSelected ? 40 : 1,
                  cursor: interactive ? "pointer" : "default",
                  pointerEvents: interactive ? "auto" : "none",
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
