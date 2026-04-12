import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useEffect, useState } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";

const CardAppStatusValues = ["idle", "loading", "ready", "error"] as const;
type CardAppStatusValue = (typeof CardAppStatusValues)[number];

type CardState = Readonly<{
  imageDataUrl: string | null;
  status: CardAppStatusValue;
}>;

type ImageToolContentPart = Readonly<{ type: string; data?: string; mimeType?: string }>;
type TextToolContentPart = Readonly<{ type: string; text?: string }>;

const PAGE_STYLE: React.CSSProperties = {
  display: "flex",
  justifyContent: "center",
  padding: "1.5rem",
  minHeight: "100%",
  backgroundColor: "var(--color-background-tertiary)",
  color: "var(--color-text-tertiary)",
};

export function CardApp() {
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [card, setCard] = useState<CardState>({ imageDataUrl: null, status: "idle" });

  const { app, isConnected, error } = useApp({
    appInfo: { name: "CardApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (app) => {
      app.ontoolinput = async () => {
        setCard({ imageDataUrl: null, status: "loading" });
      };

      app.ontoolresult = async (result) => {
        const content = result.content as readonly (ImageToolContentPart & TextToolContentPart)[];

        // Direct image result (from show_card_image)
        const imageBlock = content.find((c) => c.type === "image");
        if (imageBlock?.data && imageBlock.mimeType) {
          setCard({
            imageDataUrl: `data:${imageBlock.mimeType};base64,${imageBlock.data}`,
            status: "ready",
          });
          return;
        }

        // Card JSON result (from get_card) — extract scryfall_id, fetch image via callServerTool
        const textBlock = content.find((c) => c.type === "text");
        if (textBlock?.text) {
          try {
            const data = JSON.parse(textBlock.text) as { scryfall_id?: string };
            if (data.scryfall_id) {
              setCard({ imageDataUrl: null, status: "loading" });
              const imgResult = await app.callServerTool({
                name: "get_card_image",
                arguments: { scryfall_id: data.scryfall_id },
              });
              const imgContent = imgResult.content as readonly ImageToolContentPart[];
              const img = imgContent.find((c) => c.type === "image");
              if (img?.data && img.mimeType) {
                setCard({
                  imageDataUrl: `data:${img.mimeType};base64,${img.data}`,
                  status: "ready",
                });
                return;
              }
            }
          } catch {
            // fall through to error
          }
        }

        setCard((c) => ({ ...c, status: "error" }));
      };

      app.onteardown = async () => ({});
      app.onerror = console.error;
      app.onhostcontextchanged = (ctx) => setHostContext((prev) => ({ ...prev, ...ctx }));
    },
  });

  useEffect(() => {
    if (app) setHostContext(app.getHostContext());
  }, [app]);

  useHostStyles(app, app?.getHostContext());

  const insets = hostContext?.safeAreaInsets;
  const pageStyle: React.CSSProperties = insets
    ? { ...PAGE_STYLE, padding: `${insets.top}px ${insets.right}px ${insets.bottom}px ${insets.left}px` }
    : PAGE_STYLE;

  if (error) {
    return <div style={pageStyle}><strong>Error:</strong> {error.message}</div>;
  }

  if (!isConnected || card.status === "idle") {
    return <div style={pageStyle}>Connecting…</div>;
  }

  if (card.status === "loading") {
    return <div style={pageStyle}>Loading card…</div>;
  }

  if (card.status === "error" || !card.imageDataUrl) {
    return <div style={pageStyle}>Could not load card image.</div>;
  }

  return (
    <div style={pageStyle}>
      <img
        src={card.imageDataUrl}
        alt="Magic card"
        style={{
          width: 260,
          borderRadius: "var(--border-radius-md)",
          alignSelf: "flex-start",
          margin: "0.5rem 0",
        }}
      />
    </div>
  );
}
