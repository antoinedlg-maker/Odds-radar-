"""Bot Discord Odds Radar."""

from __future__ import annotations

import asyncio
import logging
import time
import unicodedata
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import tasks

from .analysis import find_surebets, find_value_bets
from .config import Config, book_name
from .formatting import event_embed, surebet_embed, value_embed
from .models import Event
from .provider import OddsApiClient, OddsApiError

log = logging.getLogger("odds_radar")

MANUAL_SCAN_COOLDOWN = 15 * 60  # secondes, pour ne pas griller les crédits


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().strip()


class OddsRadar(discord.Client):
    def __init__(self, cfg: Config):
        super().__init__(intents=discord.Intents.default())
        self.cfg = cfg
        self.tree = app_commands.CommandTree(self)
        self.api = OddsApiClient(cfg.odds_api_key)
        self.events: dict[str, list[Event]] = {}
        self.last_scan: datetime | None = None
        self.last_manual_scan = 0.0
        self.seen: dict[str, float] = {}  # alertes déjà envoyées -> horodatage
        self._scan_lock = asyncio.Lock()
        self.scan_loop.change_interval(minutes=cfg.scan_interval_minutes)
        _register_commands(self)

    # --- cycle de vie -----------------------------------------------------
    async def setup_hook(self) -> None:
        if self.cfg.guild_id:
            guild = discord.Object(id=self.cfg.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.scan_loop.start()

    async def close(self) -> None:
        await self.api.close()
        await super().close()

    async def on_ready(self) -> None:
        log.info("Connecté en tant que %s", self.user)

    # --- scan ------------------------------------------------------------
    @property
    def all_events(self) -> list[Event]:
        now = datetime.now(timezone.utc)
        return [e for evs in self.events.values() for e in evs if e.commence_time > now]

    async def scan(self) -> None:
        async with self._scan_lock:
            for sport in self.cfg.sports:
                remaining = self.api.usage.remaining
                if remaining is not None and remaining <= self.cfg.min_credits_reserve:
                    log.warning("Plus que %s crédits : scan suspendu.", remaining)
                    break
                try:
                    self.events[sport] = await self.api.odds(
                        sport, self.cfg.fetched_bookmakers, self.cfg.markets
                    )
                except OddsApiError as exc:
                    log.error("Échec %s : %s", sport, exc)
            self.last_scan = datetime.now(timezone.utc)

    def surebets(self):
        return find_surebets(self.all_events, self.cfg.bookmakers, self.cfg.min_surebet_profit)

    def value_bets(self):
        return find_value_bets(
            self.all_events,
            self.cfg.bookmakers,
            reference=self.cfg.reference_bookmaker,
            min_edge_pct=self.cfg.min_value_edge,
            max_odds=self.cfg.max_value_odds,
        )

    async def post_alerts(self) -> None:
        if not self.cfg.alert_channel_id:
            return
        channel = self.get_channel(self.cfg.alert_channel_id) or await self.fetch_channel(
            self.cfg.alert_channel_id
        )
        now = time.time()
        # on oublie les alertes de plus de 2 jours
        self.seen = {k: t for k, t in self.seen.items() if now - t < 2 * 86400}
        for item, make in [*((s, surebet_embed) for s in self.surebets()),
                           *((v, value_embed) for v in self.value_bets())]:
            if item.key in self.seen:
                continue
            self.seen[item.key] = now
            await channel.send(embed=make(item))

    @tasks.loop(minutes=240)
    async def scan_loop(self) -> None:
        await self.scan()
        await self.post_alerts()

    @scan_loop.before_loop
    async def _wait_ready(self) -> None:
        await self.wait_until_ready()


def _register_commands(bot: OddsRadar) -> None:
    tree = bot.tree

    @tree.command(name="cotes", description="Compare les cotes d'un match entre les bookmakers")
    @app_commands.describe(equipe="Nom (ou bout de nom) d'une équipe")
    async def cotes(interaction: discord.Interaction, equipe: str):
        q = _norm(equipe)
        matches = [e for e in bot.all_events if q in _norm(e.home_team) or q in _norm(e.away_team)]
        if not matches:
            await interaction.response.send_message(
                f"Aucun match trouvé pour « {equipe} » dans les championnats suivis.", ephemeral=True
            )
            return
        matches.sort(key=lambda e: e.commence_time)
        embeds = [event_embed(e, bot.cfg.bookmakers) for e in matches[:3]]
        await interaction.response.send_message(embeds=embeds)

    @tree.command(name="surebets", description="Surebets en cours (gain garanti)")
    async def surebets(interaction: discord.Interaction):
        found = bot.surebets()
        if not found:
            await interaction.response.send_message("Aucun surebet pour l'instant.", ephemeral=True)
            return
        await interaction.response.send_message(embeds=[surebet_embed(s) for s in found[:5]])

    @tree.command(name="value", description="Value bets en cours (cote au-dessus de la cote juste)")
    async def value(interaction: discord.Interaction):
        found = bot.value_bets()
        if not found:
            await interaction.response.send_message("Aucun value bet pour l'instant.", ephemeral=True)
            return
        await interaction.response.send_message(embeds=[value_embed(v) for v in found[:5]])

    @tree.command(name="scan", description="Relance une récupération des cotes (consomme des crédits)")
    async def scan(interaction: discord.Interaction):
        wait = MANUAL_SCAN_COOLDOWN - (time.time() - bot.last_manual_scan)
        if wait > 0:
            await interaction.response.send_message(
                f"Doucement, prochain scan manuel possible dans {int(wait // 60) + 1} min.", ephemeral=True
            )
            return
        bot.last_manual_scan = time.time()
        await interaction.response.defer(thinking=True)
        await bot.scan()
        await bot.post_alerts()
        n = len(bot.all_events)
        await interaction.followup.send(
            f"Scan terminé : {n} matchs, {len(bot.surebets())} surebets, {len(bot.value_bets())} value bets."
        )

    @tree.command(name="statut", description="Crédits API restants et réglages")
    async def statut(interaction: discord.Interaction):
        u = bot.api.usage
        last = bot.last_scan.strftime("%d/%m %H:%M UTC") if bot.last_scan else "jamais"
        msg = (
            f"**Bookmakers** : {', '.join(book_name(b) for b in bot.cfg.bookmakers)} "
            f"(référence : {book_name(bot.cfg.reference_bookmaker)})\n"
            f"**Championnats** : {', '.join(bot.cfg.sports)}\n"
            f"**Scan auto** : toutes les {bot.cfg.scan_interval_minutes} min · dernier : {last}\n"
            f"**Crédits API** : {u.remaining if u.remaining is not None else '?'} restants\n"
            f"**Seuils** : surebet ≥ {bot.cfg.min_surebet_profit} % · value ≥ {bot.cfg.min_value_edge} %"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @tree.command(name="sports", description="Liste les championnats disponibles côté API (gratuit)")
    async def sports(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            data = await bot.api.sports()
        except OddsApiError as exc:
            await interaction.followup.send(f"Erreur API : {exc}", ephemeral=True)
            return
        lines = [f"`{s['key']}` — {s['title']}" for s in data if s.get("active") and not s.get("has_outrights")]
        text = "\n".join(lines)
        await interaction.followup.send(text[:1990] or "Rien de dispo.", ephemeral=True)
