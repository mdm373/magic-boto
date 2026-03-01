--
-- PostgreSQL database dump
--

\restrict pF16GIyJHlslmywul3M1rlRtYwzP6gqw9UAS31bBd9exsq7e6XeHbrMQfZmAiVM

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: mtgjson; Type: SCHEMA; Schema: -; Owner: magicboto
--

CREATE SCHEMA mtgjson;


ALTER SCHEMA mtgjson OWNER TO magicboto;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: cardForeignData; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."cardForeignData" (
    uuid text,
    "faceName" text,
    "flavorText" text,
    identifiers text,
    language text,
    "multiverseId" bigint,
    name text,
    text text,
    type text
);


ALTER TABLE mtgjson."cardForeignData" OWNER TO magicboto;

--
-- Name: cardIdentifiers; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."cardIdentifiers" (
    uuid text,
    "scryfallId" text,
    "scryfallOracleId" text,
    "scryfallIllustrationId" text,
    "scryfallCardBackId" text,
    "mcmId" text,
    "mcmMetaId" text,
    "mtgArenaId" text,
    "mtgoId" text,
    "mtgoFoilId" text,
    "multiverseId" text,
    "tcgplayerProductId" text,
    "tcgplayerEtchedProductId" text,
    "tcgplayerAlternativeFoilProductId" text,
    "cardKingdomId" text,
    "cardKingdomFoilId" text,
    "cardKingdomEtchedId" text,
    "cardsphereId" text,
    "cardsphereFoilId" text,
    "deckboxId" text,
    "mtgjsonFoilVersionId" text,
    "mtgjsonNonFoilVersionId" text,
    "mtgjsonV4Id" text
);


ALTER TABLE mtgjson."cardIdentifiers" OWNER TO magicboto;

--
-- Name: cardLegalities; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."cardLegalities" (
    uuid text,
    alchemy text,
    brawl text,
    commander text,
    duel text,
    future text,
    gladiator text,
    historic text,
    legacy text,
    modern text,
    oathbreaker text,
    oldschool text,
    pauper text,
    paupercommander text,
    penny text,
    pioneer text,
    predh text,
    premodern text,
    standard text,
    standardbrawl text,
    timeless text,
    vintage text
);


ALTER TABLE mtgjson."cardLegalities" OWNER TO magicboto;

--
-- Name: cardPurchaseUrls; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."cardPurchaseUrls" (
    uuid text,
    "cardKingdom" text,
    "cardKingdomFoil" text,
    "cardKingdomEtched" text,
    cardmarket text,
    tcgplayer text,
    "tcgplayerEtched" text,
    "tcgplayerAlternativeFoil" text
);


ALTER TABLE mtgjson."cardPurchaseUrls" OWNER TO magicboto;

--
-- Name: cardRulings; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."cardRulings" (
    uuid text,
    date date,
    text text
);


ALTER TABLE mtgjson."cardRulings" OWNER TO magicboto;

--
-- Name: cards; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson.cards (
    artist text,
    "artistIds" text,
    "asciiName" text,
    "attractionLights" text,
    availability text,
    "boosterTypes" text,
    "borderColor" text,
    "cardParts" text,
    "colorIdentity" text,
    "colorIndicator" text,
    colors text,
    defense text,
    "duelDeck" text,
    "edhrecRank" bigint,
    "edhrecSaltiness" double precision,
    "faceConvertedManaCost" double precision,
    "faceFlavorName" text,
    "faceManaValue" double precision,
    "faceName" text,
    "facePrintedName" text,
    finishes text,
    "flavorName" text,
    "flavorText" text,
    "frameEffects" text,
    "frameVersion" text,
    hand text,
    "hasAlternativeDeckLimit" boolean,
    "hasContentWarning" boolean,
    "isAlternative" boolean,
    "isFullArt" boolean,
    "isFunny" boolean,
    "isGameChanger" boolean,
    "isOnlineOnly" boolean,
    "isOversized" boolean,
    "isPromo" boolean,
    "isRebalanced" boolean,
    "isReprint" boolean,
    "isReserved" boolean,
    "isStorySpotlight" boolean,
    "isTextless" boolean,
    "isTimeshifted" boolean,
    keywords text,
    language text,
    layout text,
    "leadershipSkills" text,
    life text,
    loyalty text,
    "manaCost" text,
    "manaValue" double precision,
    name text,
    number text,
    "originalPrintings" text,
    "originalReleaseDate" text,
    "originalText" text,
    "otherFaceIds" text,
    power text,
    "printedName" text,
    "printedText" text,
    "printedType" text,
    printings text,
    "producedMana" text,
    "promoTypes" text,
    rarity text,
    "rebalancedPrintings" text,
    "relatedCards" text,
    "securityStamp" text,
    "setCode" text,
    side text,
    signature text,
    "sourceProducts" text,
    subsets text,
    subtypes text,
    supertypes text,
    text text,
    toughness text,
    type text,
    types text,
    uuid text,
    variations text,
    watermark text
);


ALTER TABLE mtgjson.cards OWNER TO magicboto;

--
-- Name: meta; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson.meta (
    date text,
    version text
);


ALTER TABLE mtgjson.meta OWNER TO magicboto;

--
-- Name: setBoosterContentWeights; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."setBoosterContentWeights" (
    "setCode" text,
    "boosterName" text,
    "boosterIndex" bigint,
    "boosterWeight" bigint
);


ALTER TABLE mtgjson."setBoosterContentWeights" OWNER TO magicboto;

--
-- Name: setBoosterContents; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."setBoosterContents" (
    "setCode" text,
    "boosterName" text,
    "boosterIndex" bigint,
    "sheetName" text,
    "sheetPicks" bigint
);


ALTER TABLE mtgjson."setBoosterContents" OWNER TO magicboto;

--
-- Name: setBoosterSheetCards; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."setBoosterSheetCards" (
    "setCode" text,
    "boosterName" text,
    "sheetName" text,
    "cardUuid" text,
    "cardWeight" bigint
);


ALTER TABLE mtgjson."setBoosterSheetCards" OWNER TO magicboto;

--
-- Name: setBoosterSheets; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."setBoosterSheets" (
    "setCode" text,
    "boosterName" text,
    "sheetName" text,
    "sheetIsFoil" boolean,
    "sheetHasBalanceColors" boolean,
    "sheetTotalWeight" bigint
);


ALTER TABLE mtgjson."setBoosterSheets" OWNER TO magicboto;

--
-- Name: setTranslations; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."setTranslations" (
    code text,
    language text,
    translation text
);


ALTER TABLE mtgjson."setTranslations" OWNER TO magicboto;

--
-- Name: sets; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson.sets (
    code text,
    name text,
    "mtgoCode" text,
    block text,
    "tokenSetCode" text,
    "releaseDate" text,
    type text,
    "isOnlineOnly" boolean,
    "isFoilOnly" boolean,
    "tcgplayerGroupId" bigint,
    "isNonFoilOnly" boolean,
    "parentCode" text,
    "totalSetSize" bigint,
    "baseSetSize" bigint,
    "keyruneCode" text,
    "mcmId" bigint,
    "mcmName" text,
    "mcmIdExtras" bigint,
    "isForeignOnly" boolean,
    "isPartialPreview" boolean
);


ALTER TABLE mtgjson.sets OWNER TO magicboto;

--
-- Name: tokenIdentifiers; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson."tokenIdentifiers" (
    uuid text,
    "scryfallId" text,
    "scryfallOracleId" text,
    "scryfallIllustrationId" text,
    "scryfallCardBackId" text,
    "mcmId" text,
    "mcmMetaId" text,
    "mtgArenaId" text,
    "mtgoId" text,
    "mtgoFoilId" text,
    "multiverseId" text,
    "tcgplayerProductId" text,
    "tcgplayerEtchedProductId" text,
    "tcgplayerAlternativeFoilProductId" text,
    "cardKingdomId" text,
    "cardKingdomFoilId" text,
    "cardKingdomEtchedId" text,
    "cardsphereId" text,
    "cardsphereFoilId" text,
    "deckboxId" text,
    "mtgjsonFoilVersionId" text,
    "mtgjsonNonFoilVersionId" text,
    "mtgjsonV4Id" text
);


ALTER TABLE mtgjson."tokenIdentifiers" OWNER TO magicboto;

--
-- Name: tokens; Type: TABLE; Schema: mtgjson; Owner: magicboto
--

CREATE TABLE mtgjson.tokens (
    artist text,
    "artistIds" text,
    "asciiName" text,
    "attractionLights" text,
    availability text,
    "boosterTypes" text,
    "borderColor" text,
    "colorIdentity" text,
    "colorIndicator" text,
    colors text,
    "edhrecSaltiness" double precision,
    "faceName" text,
    finishes text,
    "flavorName" text,
    "flavorText" text,
    "frameEffects" text,
    "frameVersion" text,
    "isFullArt" boolean,
    "isFunny" boolean,
    "isOversized" boolean,
    "isPromo" boolean,
    "isReprint" boolean,
    "isTextless" boolean,
    keywords text,
    language text,
    layout text,
    "manaCost" text,
    name text,
    number text,
    orientation text,
    "originalText" text,
    "otherFaceIds" text,
    power text,
    "printedType" text,
    "producedMana" text,
    "promoTypes" text,
    "relatedCards" text,
    "securityStamp" text,
    "setCode" text,
    side text,
    signature text,
    "sourceProducts" text,
    subtypes text,
    supertypes text,
    text text,
    toughness text,
    type text,
    types text,
    uuid text,
    watermark text
);


ALTER TABLE mtgjson.tokens OWNER TO magicboto;

--
-- Name: idx_cardForeignData_language; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_cardForeignData_language" ON mtgjson."cardForeignData" USING btree (language);


--
-- Name: idx_cardForeignData_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_cardForeignData_uuid" ON mtgjson."cardForeignData" USING btree (uuid);


--
-- Name: idx_cardIdentifiers_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_cardIdentifiers_uuid" ON mtgjson."cardIdentifiers" USING btree (uuid);


--
-- Name: idx_cardLegalities_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_cardLegalities_uuid" ON mtgjson."cardLegalities" USING btree (uuid);


--
-- Name: idx_cardPurchaseUrls_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_cardPurchaseUrls_uuid" ON mtgjson."cardPurchaseUrls" USING btree (uuid);


--
-- Name: idx_cardRulings_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_cardRulings_uuid" ON mtgjson."cardRulings" USING btree (uuid);


--
-- Name: idx_cards_name; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX idx_cards_name ON mtgjson.cards USING btree (name);


--
-- Name: idx_cards_setCode; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_cards_setCode" ON mtgjson.cards USING btree ("setCode");


--
-- Name: idx_cards_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX idx_cards_uuid ON mtgjson.cards USING btree (uuid);


--
-- Name: idx_setBoosterContentWeights_setCode; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_setBoosterContentWeights_setCode" ON mtgjson."setBoosterContentWeights" USING btree ("setCode");


--
-- Name: idx_setBoosterContents_setCode; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_setBoosterContents_setCode" ON mtgjson."setBoosterContents" USING btree ("setCode");


--
-- Name: idx_setBoosterSheetCards_cardUuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_setBoosterSheetCards_cardUuid" ON mtgjson."setBoosterSheetCards" USING btree ("cardUuid");


--
-- Name: idx_setBoosterSheetCards_setCode; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_setBoosterSheetCards_setCode" ON mtgjson."setBoosterSheetCards" USING btree ("setCode");


--
-- Name: idx_setBoosterSheets_setCode; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_setBoosterSheets_setCode" ON mtgjson."setBoosterSheets" USING btree ("setCode");


--
-- Name: idx_setTranslations_code; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_setTranslations_code" ON mtgjson."setTranslations" USING btree (code);


--
-- Name: idx_sets_code; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX idx_sets_code ON mtgjson.sets USING btree (code);


--
-- Name: idx_sets_name; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX idx_sets_name ON mtgjson.sets USING btree (name);


--
-- Name: idx_tokenIdentifiers_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_tokenIdentifiers_uuid" ON mtgjson."tokenIdentifiers" USING btree (uuid);


--
-- Name: idx_tokens_name; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX idx_tokens_name ON mtgjson.tokens USING btree (name);


--
-- Name: idx_tokens_setCode; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX "idx_tokens_setCode" ON mtgjson.tokens USING btree ("setCode");


--
-- Name: idx_tokens_uuid; Type: INDEX; Schema: mtgjson; Owner: magicboto
--

CREATE INDEX idx_tokens_uuid ON mtgjson.tokens USING btree (uuid);


--
-- PostgreSQL database dump complete
--

\unrestrict pF16GIyJHlslmywul3M1rlRtYwzP6gqw9UAS31bBd9exsq7e6XeHbrMQfZmAiVM

