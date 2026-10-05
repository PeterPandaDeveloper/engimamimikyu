# PokeImpostor

A fast-paced social deduction word game bot for Discord inspired by *Spyfall* and *Among Us*, powered by the Pokémon universe.

Trainers receive secret Pokémon clues via Direct Message. One or more players are **Impostors** who receive either vague hints, nothing at all, or a completely different Pokémon depending on the mode. Each player takes turns giving a one-word clue to prove they know the secret Pokémon without giving it away to the Impostor. After each round of clues, the lobby debates and votes to eject suspects before the round limit expires.

---

## Features

- **3 Game Modes**:
  - **Classic**: 1 Impostor who knows nothing. Regular crewmates know the exact Pokémon name, types, and generation.
  - **Extended**: Multiple Impostors scale with lobby size. Impostors receive partial hints (e.g. types or region) to blend in.
  - **Chaos**: Total unpredictability. Can spawn 0 Impostors (group paranoia), random Impostor counts, **Target Human** (deduce a real lobby member), or **Chaos Dance** (everyone gets a different Pokémon).
- **Configurable Round Limit (1–9)**: Host sets the maximum rounds before the game starts using a Discord select menu. If players fail to catch all impostors before rounds reach zero, the Impostors win automatically.
- **1,025+ Pokémon**: Fetches live official artwork, Pokédex flavor text, habitat, types, and stats via PokéAPI.
- **Bilingual (English / Spanish)**: Switch server language instantly with `/lang`.
- **DuckDB Analytics & Leaderboards**: Tracks player win rates, favorite Pokémon, most lethal impostor Pokémon, and server leaderboards.
- **VIP & Partner Licensing**: Built-in cryptographic key redemption system (`/canjear`, `/licencia`).

---

## How to Play

```
1. Host opens lobby (/impregister)  -->  Players join (3-12 players)
2. Host picks settings (Mode, Clue type, Region, Round limit 1-9)
3. Secret roles delivered via DM
4. Word Round: Each player says one word/clue in the chat
5. Debate & Vote: Lobby votes to eject a suspect
6. Next Round: Remaining rounds tick down (3 -> 2 -> 1)
   - Crewmates catch all Impostors  --> Crew wins!
   - Round counter hits 0           --> Impostors win!
```

---

## Slash Commands

| Command | Description |
|---|---|
| `/impregister` | Open a new PokeImpostor lobby in the current channel |
| `/impver` | Re-send your secret role card via DM during an active game |
| `/lang` / `/implanguage` | Switch server language (`English` / `Español`) |
| `/imphelp` | View game rules, mode breakdown, and instructions |
| `/perfil` | View trainer stats, games played, win rate, and favorite Pokémon |
| `/ranking` | Server leaderboard (Crew wins, Impostor wins, Win rate) |
| `/stats_partidas` | Global match statistics and historical records for the server |
| `/licencia` | Check the current server's VIP / Partner status and perks |
| `/canjear` | Redeem a VIP License Key |

*Owner administration commands (`/generarkey`, `/partner_add`) require bot ownership and cryptographic master password authentication.*

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
