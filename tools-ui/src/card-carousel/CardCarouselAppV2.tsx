import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useEmblaCarousel from "embla-carousel-react";
import type { App, McpUiHostContext } from "@modelcontextprotocol/ext-apps";

import {
  CardGrid,
  COUNTER_STYLE,
  type CardMeta,
  type CardsPageResult,
  type ImageContent,
  PAGE_GUTTER_PX,
  SLIDE_WIDTH_FRACTION,
  chunkIntoPages,
  fixedCardFrameHeightPx,
  gridContentWidthPx,
  layoutTierRowCount,
  pageStyleWithInsets,
  useGridLayout,
} from "./shared";

/**
 * Embla-backed variant of the card carousel: a real horizontal scroller (drag/swipe with
 * momentum) instead of the paged keyframe-transition grid in `CardCarouselApp`. As you swipe
 * toward the last loaded grid page, the next batch of cards is fetched from the server and
 * appended so scrolling doesn't run out of content; releasing a swipe always settles on
 * whichever grid page best fits the current scroll position (embla's native snap behavior).
 *
 * Kept as a sibling of `CardCarouselApp` (not a replacement) so the two can be A/B toggled at
 * runtime — see `main.tsx` — without a server-side or resource-wiring change either way.
 */

// How many grid pages of runway to keep ahead of the current page before fetching more cards
// from the server. 1 = start fetching once the user is on the second-to-last loaded page.
const PREFETCH_PAGES_AHEAD = 1;

type ToolInputArguments = Readonly<{
  filters?: unknown;
  pagination?: Readonly<{ page_size?: number; page_number?: number }>;
  flags?: unknown;
}>;

const CarouselStatusValues = ["idle", "loading", "ready", "error"] as const;
type CarouselStatusValue = (typeof CarouselStatusValues)[number];

type CarouselState = Readonly<{
  status: CarouselStatusValue;
  cards: readonly CardMeta[];
  total: number;
  selectedId: string | null;
}>;

const INITIAL_STATE: CarouselState = {
  status: "idle",
  cards: [],
  total: 0,
  selectedId: null,
};

function dedupeAppend(
  existing: readonly CardMeta[],
  incoming: readonly CardMeta[],
): readonly CardMeta[] {
  const seen = new Set(existing.map((c) => c.card_id));
  const fresh = incoming.filter((c) => !seen.has(c.card_id));
  return fresh.length === 0 ? existing : [...existing, ...fresh];
}

export function CardCarouselAppV2() {
  const [state, setState] = useState<CarouselState>(INITIAL_STATE);
  const [images, setImages] = useState<Readonly<Record<string, string>>>({});
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [selectedIndex, setSelectedIndex] = useState(0);

  const appRef = useRef<App | null>(null);
  const fetchedImageRef = useRef<Set<string>>(new Set());
  const shownImagesRef = useRef<Set<string>>(new Set());
  const stateRef = useRef(state);
  stateRef.current = state;
  const baseArgsRef = useRef<ToolInputArguments | undefined>(undefined);
  const nextPageNumberRef = useRef(2);
  const fetchInFlightRef = useRef(false);

  // Grid sized to the narrower peeking slide, not the full container — on a borderline-width
  // desktop screen this can cost a column (same tradeoff peeking already makes on mobile).
  const { cols, cardWidth, cardHeight, rowsPerPage, pageSize } = useGridLayout(
    hostContext,
    SLIDE_WIDTH_FRACTION,
  );

  // Center align + a sub-100% slide basis (below) is what makes the previous/next page peek in
  // at both edges as a swipe hint; the track's `gap` (below) keeps a clean gutter between pages
  // instead of the peeking neighbor's card ending up flush against the current page's edge card.
  //
  // containScroll: false (embla's own internal default is "trimSnaps", *not* falsy — merely
  // omitting the option still gets trimSnaps). trimSnaps/keepSnaps unconditionally force the
  // first/last snap flush to the scroll bounds (fine — that's the intended edge behavior) but
  // *also* merge any snap within a small tolerance of a bound into that bound, discarding it.
  // With a wide slide (small peek zone) that tolerance check swallows most non-edge pages too,
  // so they never resolve to their true centered position and render with no peek on either
  // side. Explicitly disabling it uses the raw centered snap for every page; the tradeoff is
  // the very first/last page can show a sliver of dead space instead of being pinned flush —
  // acceptable since it only affects the two ends, not every page in between.
  const [emblaRef, emblaApi] = useEmblaCarousel({
    loop: false,
    align: "center",
    containScroll: false,
  });

  const { app, isConnected, error } = useApp({
    appInfo: { name: "CardCarouselAppV2", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (createdApp) => {
      appRef.current = createdApp;

      createdApp.ontoolinput = async (params) => {
        baseArgsRef.current = params.arguments as ToolInputArguments | undefined;
        nextPageNumberRef.current = (baseArgsRef.current?.pagination?.page_number ?? 1) + 1;
        fetchedImageRef.current.clear();
        shownImagesRef.current.clear();
        setImages({});
        setSelectedIndex(0);
        setState({ ...INITIAL_STATE, status: "loading" });
      };

      createdApp.ontoolresult = async (result) => {
        try {
          const textBlock = (result.content as readonly { type: string; text?: string }[]).find(
            (c) => c.type === "text",
          );
          if (!textBlock?.text) throw new Error("no text block");
          const data = JSON.parse(textBlock.text) as CardsPageResult;
          const cards = data.items ?? [];
          setState({
            status: "ready",
            cards,
            total: data.total ?? 0,
            selectedId: cards.length === 1 ? cards[0].card_id : null,
          });
        } catch {
          setState((s) => ({ ...s, status: "error" }));
        }
      };

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

  const { status, cards, total } = state;
  const pages = useMemo(() => chunkIntoPages(cards, pageSize), [cards, pageSize]);

  // Re-measure snap points whenever the slide count or per-slide layout changes (embla does
  // not observe DOM mutations on its own — it must be told).
  useEffect(() => {
    emblaApi?.reInit();
  }, [emblaApi, pages.length, cols, cardWidth, rowsPerPage]);

  useEffect(() => {
    if (!emblaApi) return;
    const onSelect = () => setSelectedIndex(emblaApi.selectedScrollSnap());
    emblaApi.on("select", onSelect);
    emblaApi.on("reInit", onSelect);
    onSelect();
    return () => {
      emblaApi.off("select", onSelect);
      emblaApi.off("reInit", onSelect);
    };
  }, [emblaApi]);

  const fetchMore = useCallback(async () => {
    const currentApp = appRef.current;
    if (!currentApp || fetchInFlightRef.current) return;
    if (stateRef.current.cards.length >= stateRef.current.total) return;

    fetchInFlightRef.current = true;
    const baseArgs = baseArgsRef.current;
    const fetchPageSize = baseArgs?.pagination?.page_size ?? 100;
    const pageNumber = nextPageNumberRef.current;

    try {
      const result = await currentApp.callServerTool({
        name: "search_cards",
        arguments: {
          ...baseArgs,
          pagination: { ...baseArgs?.pagination, page_size: fetchPageSize, page_number: pageNumber },
        },
      });
      const textBlock = (result.content as readonly { type: string; text?: string }[]).find(
        (c) => c.type === "text",
      );
      if (!textBlock?.text) return;
      const data = JSON.parse(textBlock.text) as CardsPageResult;
      nextPageNumberRef.current = pageNumber + 1;
      setState((prev) => ({
        ...prev,
        cards: dedupeAppend(prev.cards, data.items ?? []),
        total: data.total ?? prev.total,
      }));
    } catch {
      // Leave nextPageNumberRef untouched so the next scroll-triggered check retries the same page.
    } finally {
      fetchInFlightRef.current = false;
    }
  }, []);

  // Prefetch one grid page of runway ahead of where the user currently is.
  useEffect(() => {
    if (status !== "ready") return;
    if (cards.length >= total) return;
    if (selectedIndex >= pages.length - 1 - PREFETCH_PAGES_AHEAD) {
      void fetchMore();
    }
  }, [status, selectedIndex, pages.length, cards.length, total, fetchMore]);

  // Lazily fetch card art for the visible page plus the next one, same one-tool-call-per-card
  // pattern as the original variant.
  useEffect(() => {
    if (status !== "ready") return;
    const currentApp = appRef.current;
    if (!currentApp) return;

    const toLoad = [pages[selectedIndex] ?? [], pages[selectedIndex + 1] ?? []].flat();
    for (const card of toLoad) {
      if (fetchedImageRef.current.has(card.card_id)) continue;
      fetchedImageRef.current.add(card.card_id);
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
  }, [status, selectedIndex, pages]);

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

  // Nominal page height, capped to the actual result count so a result set that fits on one
  // under-full page doesn't reserve blank rows it'll never use. Still uses the full `pageSize`
  // once there's more than one page, so every slide is the same height and swiping doesn't
  // cause the frame to jump; only the final partially-filled page leaves a little unused space
  // at the bottom (see CARD_MIN_WIDTH note in shared.tsx).
  const frameCapacity = total > 0 ? Math.min(pageSize, total) : pageSize;
  const cardFramePx = fixedCardFrameHeightPx(frameCapacity, cols, cardHeight);
  const pinGridToTop = layoutTierRowCount(frameCapacity, cols) === 1;
  const gridAlignItems: React.CSSProperties["alignItems"] = pinGridToTop ? "flex-start" : "center";
  const singleRowInnerChrome: React.CSSProperties = pinGridToTop
    ? { paddingTop: 28, paddingBottom: 28, boxSizing: "border-box" }
    : {};

  const shownCount = Math.min(
    (selectedIndex + 1) * pageSize,
    cards.length,
  );

  // Fixed `cols` (not the possibly-shorter last page's card count) so every slide is the same
  // width, matching how cardFramePx already keeps every slide the same height.
  const slideWidthPx = gridContentWidthPx(cols, cardWidth);

  return (
    <div style={pageStyle}>
      <div
        ref={emblaRef}
        style={{
          overflow: "hidden",
          width: "100%",
          maxWidth: "100%",
          minWidth: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            gap: PAGE_GUTTER_PX,
            height: cardFramePx,
          }}
        >
          {pages.map((pageCards, pi) => {
            const isActive = pi === selectedIndex;
            return (
              <div
                key={pi}
                style={{
                  flex: `0 0 ${slideWidthPx}px`,
                  minWidth: 0,
                  display: "flex",
                  alignItems: gridAlignItems,
                  justifyContent: "center",
                  pointerEvents: isActive ? "auto" : "none",
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
                  interactive={isActive}
                />
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "center", paddingTop: "0.25rem", paddingBottom: "1.25rem" }}>
        <span style={COUNTER_STYLE}>
          {shownCount} of {cards.length}
          {total > cards.length ? ` (${total} total)` : ""}
        </span>
      </div>
    </div>
  );
}
