# PokeImpostor

A fast-paced social deduction word game bot for Discord inspired by *Spyfall* and *Among Us*, powered by the Pokémon universe.

Trainers receive secret Pokémon clues via Direct Message. One or more players are **Impostors** who receive either vague hints, nothing at all, or a completely different Pokémon depending on the mode. Each player takes turns giving a one-word clue to prove they know the secret Pokémon without giving it away to the Impostor. After each round of clues, the lobby debates and votes to eject suspects before the round limit expires.

---

## Features

- **3 Game Modes**:
  - **Classic**: 1 Impostor who receives a subtle clue. Regular crewmates know the exact Pokémon name, artwork, and types.
  - **Extended**: Multiple Impostors scale with lobby size (1 per 3 players), with configurable accomplice visibility.
  - **Chaos**: Total unpredictability. Rolls 1 of 7 wild variants every round: **0% Impostors** (group paranoia), **1 Impostor**, **50% Impostors**, **75% Impostors**, **100% Impostors**, **Drunk Friends / Chaos Dance** (everyone gets a different Pokémon), or **Human Target** (deduce a real lobby member).
- **Impostor's Last Stand (Spyfall Mechanic)**: When the final Impostor is caught in Classic or Extended mode, they get one dramatic chance to guess the secret Pokémon's name (with spoiler-free autocomplete) to steal the victory!
- **Competitive Tournament Mode (`/torneo-kyu`)**: Host 3, 5, 7, or 10-match series with live point tracking and an official Champion's Podium.
- **Trainer Cards, Ranks & Badges (`/trainer-card`, `/favorito-kyu`)**: Unlock gym badges, climb trainer ranks, and display your favorite companion Pokémon sprite.
- **1,025+ Pokémon + Mega, Regional, Gigantamax & Gimmick Forms**: Fetches live official artwork, Pokédex flavor text, color, habitat, types, and stats via PokéAPI with memory + disk caching.
- **Configurable Round Limit (1–9)**: Host sets the maximum debate rounds before the game starts.
- **Bilingual (English / Spanish)**: Switch server language instantly with `/lang-kyu` or `/implang`.
- **DuckDB Analytics & Top.gg Webhook**: Tracks player win rates, leaderboards, and VIP/Partner licensing (`/redeem-kyu`, `/license-kyu`, `/vote-kyu`).

---

## How to Play

```
1. Host opens lobby (/play-kyu or /impregister)  -->  Players join (3-24 players)
2. Host picks settings (Mode, Clue type, Region/Forms, Round limit 1-9)
3. Secret roles delivered via DM
4. Word Round: Each player gives a clue in chat without saying the name
5. Debate & Vote: Lobby votes anonymously to eject a suspect
6. Next Round or Last Stand:
   - Crewmates catch all Impostors (and survive Last Stand) --> Crew wins!
   - Caught Impostor guesses the exact Pokémon              --> Impostor steals the win!
   - Round counter hits 0 or Impostors reach parity         --> Impostors win!
```

---

## Slash Commands

| Command | Alias | Description |
|---|---|---|
| `/play-kyu` | `/impregister` | Open a new PokeImpostor lobby in the current channel |
| `/torneo-kyu` | `-mimi torneo` | Start a competitive Tournament series (3, 5, 7, or 10 matches) with podium |
| `/role-kyu` | `/impver` | Re-send your secret role card via DM during an active game |
| `/trainer-card` | `/profile-kyu`, `/impprofile` | View Trainer Card, rank, unlocked badges, and favorite Pokémon |
| `/favorito-kyu` | `-mimi fav` | Choose your favorite companion Pokémon with live autocomplete |
| `/leaderboard-kyu` | `/impleaderboard` | Server leaderboard (General, Deadliest Impostors, Best Crewmates) |
| `/stats-kyu` | `/impstats` | Global match statistics and historical records for the server |
| `/setrole-kyu` | `/impsetrole` | Configure or auto-create the official `PokeHost` role (Admin) |
| `/lang-kyu` | `/implang` | Switch server language (`English` / `Español`) |
| `/help-kyu` | `/imphelp` | View game rules, mode breakdown, and instructions |
| `/credits-kyu` | `/impcreditos` | View artist and illustration credits |
| `/license-kyu` | `/implicense` | Check the current server's VIP / Partner status and perks |
| `/redeem-kyu` | `/impredeem` | Redeem a VIP License Key |
| `/vote-kyu` | `-mimi vote` | Vote on Top.gg to unlock 10 free premium matches |
| `/donate-kyu` | `-mimi donate` | Support the bot & get Lifetime VIP ($5 USD) |
| `/invite-kyu` | `-mimi invite` | Get the invite link to add Mimikyu to your server |

*Owner administration commands (`/genkey-kyu` / `/impgenkey`, `/partner-kyu` / `/imppartner_add`) require bot ownership, central admin server verification, and cryptographic master password authentication.*

---

## Getting Started

### Prerequisites

- Python 3.10+
- A Discord Bot Application ([Discord Developer Portal](https://discord.com/developers/applications))
  - Required Privileged Gateway Intents: **Server Members Intent**, **Message Content Intent**.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PeterPandaDeveloper/engimamimikyu.git
   cd engimamimikyu
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   ADMIN_MASTER_HASH=6f27fad91d72d87c37223c13f431e09e0aa5a13eb3f4c115be54a95e98b9c9ae
   OWNER_ID=your_discord_user_id_optional
   TOPGG_WEBHOOK_PORT=5000
   TOPGG_WEBHOOK_SECRET=your_topgg_webhook_secret_optional
   ```

5. **Run the bot**:
   ```bash
   python main.py
   ```

---

## Tech Stack

- **[discord.py 2.x](https://github.com/Rapptz/discord.py)**: Async Discord API wrapper with modern UI Components (Modals, Select Menus, Buttons).
- **[DuckDB](https://duckdb.org/)**: Embedded fast analytical database for zero-latency player stats and match persistence.
- **[aiohttp](https://github.com/aio-libs/aiohttp)**: Asynchronous HTTP client for non-blocking PokéAPI requests.
- **[PokéAPI](https://pokeapi.co/)**: Pokémon database for stats, sprites, and Pokédex descriptions.

---

## Disclaimer

Pokémon and Pokémon character names are trademarks of Nintendo, Creatures Inc., and Game Freak. This project is a non-profit fan-made game for educational and community entertainment purposes.

---

## Terms of Service

By inviting or playing **PokeImpostor (Mimikyu)**, you agree to the following terms:
1. **Usage**: The bot is provided "as is" for entertainment and community deduction gameplay in Discord servers.
2. **Fair Play**: Users must not exploit, flood, or abuse the bot's commands, APIs, or infrastructure.
3. **Purchases & Donations**: Donations made via Buy Me a Coffee or VIP license keys support hosting, development, and server upkeep.
4. **Modifications**: The developers reserve the right to update features, balance modes, or modify rules to ensure service stability.

---

## Privacy Policy

**PokeImpostor (Mimikyu)** respects your privacy and adheres to strict minimal data collection:
1. **Data Collected**:
   - Discord User IDs, Display Names, and Server IDs strictly to record match statistics, leaderboard rankings, and VIP status.
   - Message content is processed strictly in-memory to execute text-based bot commands (e.g., `-mimi play`). No personal chats, private DMs, or server messages are ever recorded or stored.
2. **Data Storage**: Match analytics and stats are stored securely in a local DuckDB analytical database and are never sold or shared with any third party.
3. **Data Removal**: Server owners or players may request the deletion of their match history at any time by contacting the bot developers.
4. **Third-Party APIs**: Pokémon artwork and metadata are fetched in real time from public PokéAPI endpoints.

