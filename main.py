import discord
from discord import app_commands
from discord.ext import tasks
import requests
from bs4 import BeautifulSoup
import datetime
import random
import sqlite3
import uuid
import os
from typing import List

# --- Configuration ---
TOKEN = 'MTUzMTk5NDAyMjg5MjAxNTcwNw.Gwdnfj.2Sm3OVd-xpU9e7WwJoFBsY3Clq92iYVPwK1ePo'
GUILD_ID = 1500804768514183269  # Replace with your actual Server ID

# Note: Railway requires a persistent data directory path to keep your data safe across restarts
DB_PATH = "/app/data/blox_master_matrix.db"

# --- Static Game Engine Metadata ---
FRUIT_RARITIES = {
    "kitsune": {"rarity": "Mythical", "gacha_chance": 0.05, "price": "$8,000,000", "value": "130M", "demand": "10/10 🔥"},
    "dragon": {"rarity": "Mythical", "gacha_chance": 0.1, "price": "$5,000,000", "value": "110M", "demand": "10/10 📈"},
    "leopard": {"rarity": "Mythical", "gacha_chance": 0.25, "price": "$5,000,000", "value": "40M", "demand": "8/10 ⭐"},
    "dough": {"rarity": "Mythical", "gacha_chance": 0.5, "price": "$2,800,000", "value": "25M", "demand": "9/10 ✨"},
    "t-rex": {"rarity": "Mythical", "gacha_chance": 0.6, "price": "$2,700,000", "value": "20M", "demand": "7/10 🦖"},
    "portal": {"rarity": "Legendary", "gacha_chance": 1.2, "price": "$1,900,000", "value": "6M", "demand": "9/10 🌌"},
    "buddha": {"rarity": "Legendary", "gacha_chance": 2.5, "price": "$1,200,000", "value": "7M", "demand": "9.5/10 🌟"},
    "magma": {"rarity": "Rare", "gacha_chance": 5.0, "price": "$850,000", "value": "1.5M", "demand": "6/10 🌋"},
    "light": {"rarity": "Rare", "gacha_chance": 6.5, "price": "$650,000", "value": "1M", "demand": "7/10 ⚡"},
    "ice": {"rarity": "Uncommon", "gacha_chance": 12.0, "price": "$350,000", "value": "500K", "demand": "5/10 ❄️"},
    "rocket": {"rarity": "Common", "gacha_chance": 25.0, "price": "$5,000", "value": "50K", "demand": "1/10 🚀"}
}

BOSS_POOL = {
    "rip_indra": {"hp": 5000, "min_players": 1, "beli_reward": 500000, "frag_reward": 1500},
    "blackbeard": {"hp": 8000, "min_players": 2, "beli_reward": 850000, "frag_reward": 2500},
    "cake_queen": {"hp": 4000, "min_players": 1, "beli_reward": 350000, "frag_reward": 1000}
}

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, beli INTEGER DEFAULT 500000, 
        fragments INTEGER DEFAULT 0, last_daily TEXT, last_work TEXT, crew_name TEXT DEFAULT NULL
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, item_type TEXT
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS alerts (
        user_id INTEGER, fruit_name TEXT, PRIMARY KEY (user_id, fruit_name)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS server_config (
        guild_id INTEGER PRIMARY KEY, alert_channel_id INTEGER
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS marketplace (
        trade_id TEXT PRIMARY KEY, user_id INTEGER, username TEXT, offer TEXT, request TEXT, timestamp TEXT
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS crews (
        crew_name TEXT PRIMARY KEY, leader_id INTEGER, total_bounty INTEGER DEFAULT 0, emblem TEXT
    )""")
    conn.commit()
    conn.close()

def get_user_profile(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT beli, fragments, crew_name FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        row = (500000, 0, None)
    conn.close()
    return row

def update_currency(user_id, beli_change, frag_change=0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET beli = beli + ?, fragments = fragments + ? WHERE user_id = ?", (beli_change, frag_change, user_id))
    conn.commit()
    conn.close()

class MasterBotFramework(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.fallback_channel_id = None

    async def setup_hook(self):
        init_db()
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f'⚡ Massive Core System Online. Connected to {self.user.name}')
        if not check_stock_loop.is_running():
            check_stock_loop.start()

bot = MasterBotFramework()

def fetch_blox_fruit_stock():
    url = "https://fandom.com"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        stock_elements = soup.find("table", {"class": "article-table"})
        fruits_in_stock = []
        if stock_elements:
            rows = stock_elements.find_all("tr")
            for row in rows[1:]:
                cols = row.find_all("td")
                if cols:
                    fruits_in_stock.append((cols[0].text.strip(), cols[1].text.strip() if len(cols) > 1 else "Available"))
        return fruits_in_stock
    except Exception:
        return []

async def fruit_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    return [app_commands.Choice(name=n.title(), value=n) for n in FRUIT_RARITIES.keys() if current.lower() in n][:25]

async def boss_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    return [app_commands.Choice(name=b.replace("_", " ").title(), value=b) for b in BOSS_POOL.keys() if current.lower() in b]

@bot.tree.command(name="profile", description="Check your global game balance, tokens, crew, and stats")
async def profile_cmd(interaction: discord.Interaction):
    beli, frags, crew = get_user_profile(interaction.user.id, interaction.user.display_name)
    embed = discord.Embed(title=f"🏴‍☠️ Pirate Profile: {interaction.user.display_name}", color=discord.Color.blue())
    embed.add_field(name="💵 Beli Wallet", value=f"${beli:,} Beli", inline=True)
    embed.add_field(name="🔮 Fragments", value=f"✨ {frags:,}", inline=True)
    embed.add_field(name="🛡️ Crew Affiliation", value=crew if crew else "Crewless Wanderer", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily 150,000 Beli allowance bonus")
async def daily_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    get_user_profile(user_id, interaction.user.display_name)
    today = datetime.date.today().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    last_claim = row[0] if row else None
    
    if last_claim == today:
        conn.close()
        return await interaction.response.send_message("❌ You have already claimed your daily reward package today!", ephemeral=True)
        
    cursor.execute("UPDATE users SET beli = beli + 150000, last_daily = ? WHERE user_id = ?", (today, user_id))
    conn.commit()
    conn.close()
    await interaction.response.send_message("💰 **Daily Claimed!** Added **$150,000 Beli** to your wallet profile.")

@bot.tree.command(name="gacha", description="Spend $325,000 virtual Beli to pull a random physical fruit block")
async def gacha_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    beli, _, _ = get_user_profile(user_id, interaction.user.display_name)
    
    if beli < 325000:
        return await interaction.response.send_message("❌ Insufficient funds. You need **$325,000 Beli** to roll Zioles.", ephemeral=True)
        
    rolled_list = random.choices(population=list(FRUIT_RARITIES.keys()), weights=[d["gacha_chance"] for d in FRUIT_RARITIES.values()], k=1)
    rolled = rolled_list[0]
    meta = FRUIT_RARITIES[rolled]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET beli = beli - 325000 WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO inventory (user_id, item_name, item_type) VALUES (?, ?, 'fruit')", (user_id, rolled))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="🎲 Zioles Gacha Roll Matrix Result", color=discord.Color.green())
    embed.description = f"{interaction.user.mention} rolled a **{rolled.title()} Fruit** ({meta['rarity']})!\nStored directly to `/inventory`."
    await interaction.response.send_message(embed=embed)

# --- ⚔️ Multiplayer Boss Raid Simulations ---

@bot.tree.command (name="raid", description="Form a team battle party to raid legendary bosses")
@app_commands.autocomplete (boss=boss_autocomplete)
async def raid_cmd (interaction: discord.Interaction, boss: str):
    if boss.lower() not in BOSS_POOL:
        return await interaction.response.send_message("❌ Target boss profile signature not found.", ephemeral=True)
        
    await interaction.response.defer()
    boss_data = BOSS_POOL[boss.lower()]
    
    success_rate = random.randint(40, 95)
    if success_rate > 55:
        update_currency (interaction.user.id, boss_data["beli_reward"], boss_data["frag_reward"])
        embed = discord.Embed (title="⚔️ RAID BOSS VICTORY!", color=discord.Color.gold())
        embed.description = f"Your raid party defeated {boss.replace('_',' ').title()} cleanly!\n🎁 Reward Payload: +${boss_data['beli_reward']:,} Beli & +{boss_data['frag_reward']:,} Fragments!"
    else:
        embed = discord.Embed(title="💀 RAID PARTY WIPED", color=discord.Color.red())
        embed.description = f"{boss.replace('_',' ').title()} overpowered your defense lines. Better luck next time!"
        
    await interaction.followup.send(embed=embed)
