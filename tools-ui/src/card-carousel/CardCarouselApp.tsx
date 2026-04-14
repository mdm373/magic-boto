import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { App, McpUiHostContext } from "@modelcontextprotocol/ext-apps";

import { createOnToolResult } from "../utils/mcpToolResultTextJson";

// ── Constants ─────────────────────────────────────────────────────────────────

const VISIBLE_COUNT = 3;
const CARD_NORMAL_WIDTH = 200;
const CARD_SELECTED_WIDTH = 288; // ~44% larger than normal
const GAP_PX = 16;
const NAV_DURATION_MS = 220;

// Scryfall images are ~488×680px (aspect ratio ≈ 1.394 h/w).
// We size the card area to comfortably contain the selected card so the
// nav row never shifts when selection changes.
const CARD_SELECTED_HEIGHT = Math.ceil(CARD_SELECTED_WIDTH * 7 / 5); // 404 (5:7 placeholder ratio)
const CARD_AREA_HEIGHT = CARD_SELECTED_HEIGHT + 16; // 420 — breathing room

const CARD_STEP_PX = CARD_NORMAL_WIDTH + GAP_PX; // row shift per nav step (216)
// No selection: 3×200 + 2×16 = 632
const CLIP_PX = VISIBLE_COUNT * CARD_NORMAL_WIDTH + (VISIBLE_COUNT - 1) * GAP_PX;
// With selection: 1×288 + 2×200 + 2×16 = 720 (selected card is always a middle card, never the exiting/entering one)
const CLIP_SELECTED_PX = CARD_SELECTED_WIDTH + (VISIBLE_COUNT - 1) * CARD_NORMAL_WIDTH + (VISIBLE_COUNT - 1) * GAP_PX;

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

/**
 * During navigation we render a 4-card window and slide the whole row.
 * `dir: "left"` → next (row shifts left;  card[0] exits, card[3] enters)
 * `dir: "right"` → prev (row shifts right; card[3] exits, card[0] enters)
 *
 * `selectedId` is the card that was focused and remains in view — it keeps
 * its CARD_SELECTED_WIDTH during the slide so the card never visually shrinks.
 * The exiting and entering edge cards are always normal-width, so CARD_STEP_PX
 * is constant regardless of where the selected card sits in the row.
 */
type NavTransition = Readonly<{
  dir: "left" | "right";
  cards: readonly CardMeta[]; // always 4 cards
  selectedId: string | null;
}>;

const INITIAL_STATE: CarouselState = {
  status: "idle",
  cards: [],
  total: 0,
  startIndex: 0,
  selectedId: null,
};

// ── Styles ────────────────────────────────────────────────────────────────────

// Page is a flex column that fills its panel; the card area grows (flex:1) so
// the nav row is always pinned to the bottom regardless of panel height.
const PAGE_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100%",
  padding: "1.5rem",
  gap: "1.5rem",
  backgroundColor: "var(--color-background-tertiary)",
  color: "var(--color-text-tertiary)",
};

// Card area: grows to fill available space; min-height prevents it from ever
// being smaller than the tallest possible card state (selected card + breathing
// room), so the nav row never moves when selection changes.
const CARD_AREA_STYLE: React.CSSProperties = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: CARD_AREA_HEIGHT,
  paddingBottom: "1.25rem",
};

// alignItems:"center" so sibling cards vertically center on the selected card
// rather than aligning to the bottom.
const CARD_ROW_STABLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "row",
  justifyContent: "center",
  alignItems: "center",
  gap: `${GAP_PX}px`,
};

const CARD_ROW_TRANSITION: React.CSSProperties = {
  display: "flex",
  flexDirection: "row",
  alignItems: "center",
  gap: `${GAP_PX}px`,
};

const NAV_ROW_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "1.25rem",
  flexShrink: 0,
  paddingTop: "0.25rem",
  paddingBottom: "1.25rem",
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

// ── Card image slot (reused by both stable and transition renders) ─────────────

function CardImageSlot({
  card,
  imageState,
  cardAnimation,
  isSelected,
}: {
  card: CardMeta;
  imageState: string | undefined;
  cardAnimation?: string;
  isSelected?: boolean;
}) {
  return (
    <div style={{ width: isSelected ? CARD_SELECTED_WIDTH : CARD_NORMAL_WIDTH, flexShrink: 0, animation: cardAnimation }}>
      {imageState && imageState !== "error" ? (
        <img
          src={imageState}
          alt={card.name}
          style={{ width: "100%", display: "block", borderRadius: "var(--border-radius-md, 6px)" }}
        />
      ) : imageState === "error" ? (
        <div style={PLACEHOLDER_STYLE}>{card.name}</div>
      ) : (
        <div style={PLACEHOLDER_STYLE}>Loading…</div>
      )}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function CardCarouselApp() {
  const [state, setState] = useState<CarouselState>(INITIAL_STATE);
  const [images, setImages] = useState<Readonly<Record<string, string>>>({});
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [navTransition, setNavTransition] = useState<NavTransition | null>(null);
  const [navigating, setNavigating] = useState(false);

  const appRef = useRef<App | null>(null);
  const navigatingRef = useRef(false);
  const fetchedRef = useRef<Set<string>>(new Set());
  // Tracks card_ids whose images have already been shown in the stable row.
  // Prevents imageAppear from re-firing on cards that were already visible
  // in the preceding transition row.
  const shownImagesRef = useRef<Set<string>>(new Set());
  // Stable ref so navigate() can read current state without a stale closure
  const stateRef = useRef(state);
  stateRef.current = state;
  // Mirrors images state so navigate()'s setTimeout can read current values
  // without a stale closure.
  const imagesRef = useRef(images);
  imagesRef.current = images;

  const { app, isConnected, error } = useApp({
    appInfo: { name: "CardCarouselApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (createdApp) => {
      appRef.current = createdApp;

      createdApp.ontoolinput = async () => {
        fetchedRef.current.clear();
        shownImagesRef.current.clear();
        setImages({});
        setNavTransition(null);
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

  // Load images for cards that are currently visible (stable or in-flight transition)
  const { status, startIndex, cards } = state;
  useEffect(() => {
    if (status !== "ready") return;
    const currentApp = appRef.current;
    if (!currentApp) return;

    const toLoad = navTransition
      ? navTransition.cards
      : cards.slice(startIndex, startIndex + VISIBLE_COUNT);

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
  }, [status, startIndex, cards, navTransition]);

  /**
   * Slide the 4-card conveyor-belt row, then settle on the new startIndex.
   *
   * If the currently selected card will still be visible after navigation,
   * selection is preserved; otherwise it is cleared.
   *
   * next (dir=left):  [A B C D] — row shifts left  — viewport ends on [B C D]
   * prev (dir=right): [Z A B C] — row starts at -CARD_STEP, shifts right — viewport ends on [Z A B]
   */
  const navigate = useCallback((dir: "prev" | "next") => {
    if (navigatingRef.current) return;
    navigatingRef.current = true;
    setNavigating(true);

    const s = stateRef.current;

    // Reset shownImagesRef to only the cards currently visible in the stable
    // row.  The entering card is never in this set, so it will always receive
    // imageAppear when it first lands in the stable row — regardless of how
    // many times it has been seen in previous transitions.
    const currentStable = new Set(
      s.cards.slice(s.startIndex, s.startIndex + VISIBLE_COUNT).map((c) => c.card_id),
    );
    shownImagesRef.current = currentStable;

    const newIndex =
      dir === "next"
        ? Math.max(0, Math.min(s.cards.length - VISIBLE_COUNT, s.startIndex + 1))
        : Math.max(0, s.startIndex - 1);

    const fourCards =
      dir === "next"
        ? s.cards.slice(s.startIndex, s.startIndex + VISIBLE_COUNT + 1)
        : s.cards.slice(s.startIndex - 1, s.startIndex + VISIBLE_COUNT);

    // Determine which cards are visible after the transition and whether the
    // selected card survives.  The selected card keeps its width in the
    // transition row (never collapses to normal size mid-animation).
    const nextVisible = dir === "next" ? fourCards.slice(1) : fourCards.slice(0, VISIBLE_COUNT);
    const nextSelectedId =
      s.selectedId !== null && nextVisible.some((c) => c.card_id === s.selectedId)
        ? s.selectedId
        : null;

    // Don't touch state.selectedId here — it's irrelevant while we're
    // rendering the transition row.  We update it atomically when settling.
    setNavTransition({ dir: dir === "next" ? "left" : "right", cards: fourCards, selectedId: nextSelectedId });

    setTimeout(() => {
      // Cards whose images were already loaded during the transition were
      // visible at full opacity via cardFadeIn / the stable non-animated slot.
      // Mark them shown so imageAppear doesn't blink them on stable-row mount.
      // Cards whose images are still loading are left out so imageAppear fires
      // naturally when they arrive in the stable row.
      const snap = imagesRef.current;
      for (const card of fourCards) {
        if (snap[card.card_id] && snap[card.card_id] !== "error") {
          shownImagesRef.current.add(card.card_id);
        }
      }
      setState((prev) => ({ ...prev, startIndex: newIndex, selectedId: nextSelectedId }));
      setNavTransition(null);
      navigatingRef.current = false;
      setNavigating(false);
    }, NAV_DURATION_MS);
  }, []);

  // ── Computed values ─────────────────────────────────────────────────────────

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

  // ── Early returns ───────────────────────────────────────────────────────────

  if (error) return <div style={pageStyle}><strong>Error:</strong> {error.message}</div>;
  if (!isConnected || state.status === "idle") return <div style={pageStyle}>Connecting…</div>;
  if (state.status === "loading") return <div style={pageStyle}>Loading cards…</div>;
  if (state.status === "error") return <div style={pageStyle}>Could not load cards.</div>;
  if (state.cards.length === 0) return <div style={pageStyle}>No cards found.</div>;

  const visibleCards = state.cards.slice(startIndex, startIndex + VISIBLE_COUNT);
  const visibleCount = visibleCards.length;
  const canPrev = startIndex > 0;
  const canNext = startIndex + VISIBLE_COUNT < state.cards.length;

  return (
    <>
      {/*
        rowSlideLeft:  [A B C D] row at 0 → -CARD_STEP_PX  (viewport shows B C D)
        rowSlideRight: [Z A B C] row at -CARD_STEP_PX → 0  (viewport shows Z A B)
        cardFadeOut / cardFadeIn: edge cards only
      */}
      <style>{`
        @keyframes rowSlideLeft {
          from { transform: translateX(0); }
          to   { transform: translateX(-${CARD_STEP_PX}px); }
        }
        @keyframes rowSlideRight {
          from { transform: translateX(-${CARD_STEP_PX}px); }
          to   { transform: translateX(0); }
        }
        @keyframes cardFadeOut {
          from { opacity: 1; }
          to   { opacity: 0; }
        }
        @keyframes cardFadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes imageAppear {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>

      <div style={pageStyle}>
        {/*
          Card area: grows to fill the panel (flex:1) and has a fixed min-height
          equal to CARD_AREA_HEIGHT so the nav row never shifts when a card is
          selected or deselected.
        */}
        <div style={CARD_AREA_STYLE}>
          {navTransition ? (
            // Clip window — overflow:hidden trims the horizontal slide.
            // Width is wider when a selected card rides through the transition.
            <div style={{ width: navTransition.selectedId ? CLIP_SELECTED_PX : CLIP_PX, overflow: "hidden" }}>
              <div
                style={{
                  ...CARD_ROW_TRANSITION,
                  animation: `${navTransition.dir === "left" ? "rowSlideLeft" : "rowSlideRight"} ${NAV_DURATION_MS}ms ease forwards`,
                }}
              >
                {navTransition.cards.map((card, i) => {
                  const len = navTransition.cards.length;
                  const isExiting = navTransition.dir === "left" ? i === 0 : i === len - 1;
                  const isEntering = navTransition.dir === "left" ? i === len - 1 : i === 0;
                  return (
                    <CardImageSlot
                      key={card.card_id}
                      card={card}
                      imageState={images[card.card_id]}
                      isSelected={navTransition.selectedId === card.card_id}
                      cardAnimation={
                        isExiting
                          ? `cardFadeOut ${NAV_DURATION_MS}ms ease forwards`
                          : isEntering
                            ? `cardFadeIn ${NAV_DURATION_MS}ms ease forwards`
                            : undefined
                      }
                    />
                  );
                })}
              </div>
            </div>
          ) : (
            // Stable row — cards clickable; selected card expands, peers center on it
            <div style={CARD_ROW_STABLE}>
              {visibleCards.map((card) => {
                const isSelected = state.selectedId === card.card_id;
                const imageState = images[card.card_id];
                // Only fade-in on first appearance; re-mounting after a
                // transition must not re-trigger the animation.
                const isNewImage =
                  imageState != null &&
                  imageState !== "error" &&
                  !shownImagesRef.current.has(card.card_id);
                if (isNewImage) shownImagesRef.current.add(card.card_id);
                return (
                  <div
                    key={card.card_id}
                    onClick={() =>
                      setState((s) => ({
                        ...s,
                        selectedId: s.selectedId === card.card_id ? null : card.card_id,
                      }))
                    }
                    style={{
                      width: isSelected ? CARD_SELECTED_WIDTH : CARD_NORMAL_WIDTH,
                      flexShrink: 0,
                      transition: "width 0.25s ease",
                      cursor: "pointer",
                    }}
                  >
                    {imageState && imageState !== "error" ? (
                      <img
                        src={imageState}
                        alt={card.name}
                        style={{
                          width: "100%",
                          display: "block",
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
                );
              })}
            </div>
          )}
        </div>

        {/* Nav row — always at the bottom of the panel (page is flex-column, card area is flex:1) */}
        <div style={NAV_ROW_STYLE}>
          <button
            onClick={() => navigate("prev")}
            disabled={!canPrev || navigating}
            style={{
              ...NAV_BUTTON_BASE,
              opacity: canPrev && !navigating ? 1 : 0.3,
              cursor: canPrev && !navigating ? "pointer" : "default",
            }}
            aria-label="Previous"
          >
            ‹
          </button>

          <span style={COUNTER_STYLE}>
            {startIndex + 1}–{startIndex + visibleCount} of {state.cards.length}
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
            aria-label="Next"
          >
            ›
          </button>
        </div>
      </div>
    </>
  );
}
