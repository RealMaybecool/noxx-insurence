import discord, os, aiohttp, random, string, asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
verified = {}
gamepasses = {}

async def roblox_get_user_info(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
            return await resp.json()

async def roblox_check_bio(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
            data = await resp.json()
            return data.get("description", "")

async def roblox_verify_gamepass_ownership(user_id, gamepass_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://inventory.roblox.com/v1/users/{user_id}/items/GamePass/{gamepass_id}") as resp:
            data = await resp.json()
            return len(data.get("data", [])) > 0

async def roblox_buy_gamepass(gamepass_id):
    cookie = os.getenv("ROBLOX_COOKIE")
    headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": ""
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post("https://auth.roblox.com/v2/logout") as csrf_req:
            headers["X-CSRF-TOKEN"] = csrf_req.headers.get("x-csrf-token")
        async with session.post(f"https://economy.roblox.com/v1/purchases/products/{gamepass_id}", json={"expectedCurrency": 1, "expectedPrice": 100, "expectedSellerId": 0}) as resp:
            return resp.status == 200 or resp.status == 201

@bot.event
async def on_ready():
    await tree.sync()
    print("noxx bot ready")

@tree.command(name="setup")
async def setup(interaction: discord.Interaction, gamepass_id: str):
    user_id = interaction.user.id
    gamepasses[user_id] = gamepass_id
    await interaction.response.send_message("Your gamepass has been saved for payment after verification.")

@tree.command(name="verify")
async def verify(interaction: discord.Interaction, roblox_user_id: str):
    phrase = "noxx-" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    verified[interaction.user.id] = {"phrase": phrase, "roblox_id": roblox_user_id}
    await interaction.response.send_message(f"Put this in your Roblox bio: `{phrase}` then run `/verifydone`.")

@tree.command(name="verifydone")
async def verify_done(interaction: discord.Interaction):
    user = interaction.user
    data = verified.get(user.id)
    if not data: return await interaction.response.send_message("No phrase found. Run /verify first.")
    bio = await roblox_check_bio(data["roblox_id"])
    if data["phrase"] in bio:
        role = discord.utils.get(user.guild.roles, name="Verified")
        if role: await user.add_roles(role)
        await interaction.response.send_message("Verified successfully.")
    else:
        await interaction.response.send_message("Verification failed. Phrase not found.")

@tree.command(name="premium")
async def premium(interaction: discord.Interaction, roblox_user_id: str, gamepass_id: str):
    owns = await roblox_verify_gamepass_ownership(roblox_user_id, gamepass_id)
    if owns:
        role = discord.utils.get(interaction.guild.roles, name="Premium")
        if role: await interaction.user.add_roles(role)
        await interaction.response.send_message("Premium verified and role granted.")
    else:
        await interaction.response.send_message("You do not own the required gamepass.")

@tree.command(name="claim")
async def claim(interaction: discord.Interaction):
    if not discord.utils.get(interaction.user.roles, name="Premium"):
        return await interaction.response.send_message("You need Premium to open a claim.", ephemeral=True)
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        discord.utils.get(guild.roles, name="Staff"): discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    channel = await guild.create_text_channel(f"claim-{interaction.user.name}", overwrites=overwrites)
    await channel.send(f"{interaction.user.mention} opened a claim. Staff will assist you.")
    await interaction.response.send_message(f"Claim created: {channel.mention}", ephemeral=True)

@tree.command(name="accept")
async def accept(interaction: discord.Interaction):
    user_mentions = interaction.channel.topic
    user_id = None
    for member in interaction.channel.members:
        if not member.bot and not discord.utils.get(member.roles, name="Staff"):
            user_id = member.id
    if user_id not in gamepasses:
        return await interaction.response.send_message("Gamepass not found for this user.")
    gamepass_id = gamepasses[user_id]
    success = await roblox_buy_gamepass(gamepass_id)
    if success:
        await interaction.channel.send("Payment sent.")
    else:
        await interaction.channel.send("Payment failed.")
    await interaction.channel.delete()

@tree.command(name="denie")
async def denie(interaction: discord.Interaction):
    await interaction.channel.send("Claim denied.")
    await asyncio.sleep(3)
    await interaction.channel.delete()

bot.run(os.getenv("DISCORD_TOKEN"))
