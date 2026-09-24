import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { App, McpUiHostContext } from "@modelcontextprotocol/ext-apps";

import { createOnToolResult } from "../utils/mcpToolResultTextJson";
import {
  CardGrid,
  COUNTER_STYLE,
  type CardMeta,
  type CardsPageResult,
  type ImageContent,
  NAV_BUTTON_BASE,
  NAV_ROW_STYLE,
  fixedCardFrameHeightPx,
  lastPageStart,
  layoutTierRowCount,
  pageStyleWithInsets,
  slicePage,
  useGridLayout,
} from "./shared";

// ── Tunables (specific to this paged/keyframe variant) ─────────────────────────

/** Page change: long enough to read; easing keeps motion smooth. */
const NAV_DURATION_MS = 520;
/**
 * Slide distance as % of each grid’s own width (CSS transform % is relative to
 * the element being transformed). Reads as “this whole page moves off” rather
 * than a tiny nudge.
 */
const PAGE_SLIDE_OUT_PERCENT = 48;
const PAGE_SLIDE_IN_FROM_PERCENT = 42;

// ── Types ─────────────────────────────────────────────────────────────────────

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
  const { cols, cardWidth, cardHeight, pageSize } = useGridLayout(hostContext);
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

  const pageStyle = pageStyleWithInsets(hostContext?.safeAreaInsets);

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
        paddingTop: 28,
        paddingBottom: 28,
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
