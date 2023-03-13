import discord
from discord.ext import commands
import openai
import os
from dotenv import load_dotenv
import pymongo
import io
from PIL import Image
import easyocr
import numpy as np
from spellchecker import SpellChecker

load_dotenv()

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")

# Set up MongoDB client and database
mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
mongo_db = mongo_client['rizzults']

# Set up MongoDB collection
convo_history_collection = mongo_db['conversation-history']

# Set up Discord bot credentials
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Set up Discord client
intents = discord.Intents.all()
intents.members = True
intents.presences = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

convo_history = None
channel_id = 1081845107206131743 # Discord Channel ID for Image Processing 

# Initialize the spell checker
spell = SpellChecker()

@bot.event
async def on_ready():
    print(f'{bot.user.name} is ready!')

@bot.event
async def on_message(message):
    if message.author == bot.user or len(message.attachments) == 0 or message.channel.id != channel_id:
        return

    attachment = message.attachments[0]
    if attachment.content_type.startswith('image/'):
        image_bytes = await attachment.read()
        image = Image.open(io.BytesIO(image_bytes))
        reader = easyocr.Reader(['en'])
        text = reader.readtext(np.array(image))
        text = "\n".join([result[1] for result in text])

        # POST PROCESSING TECHNIQUES

        # Split the text into words
        words = text.split()

        # Correct any misspelled words
        corrected_words = []
        for word in words:
            corrected_word = spell.correction(word)
            if corrected_word is not None:
                corrected_words.append(corrected_word)

        # Join the corrected words back into a string
        corrected_text = ' '.join(corrected_words)

        channel = bot.get_channel(channel_id)
        await channel.send(text)

async def generate_pickup_line(prompt):
    # Generate response using OpenAI API
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt,
        temperature=0.7,
        max_tokens=100,
        n=1,
        stop=None,
    )

    return response.choices[0].text.strip()

@bot.command(name='pickup')
async def pickup_command(ctx, *args):
    user_id = str(ctx.author.id)

    # Retrieve conversation history from the database
    convo_history = convo_history_collection.find_one({"user_id": user_id})

    # Check if there are any arguments passed
    if args:
        # Get the topic from the argument
        topic = ' '.join(args)
        # Create a new conversation prompt based on the topic
        prompt = f"Can you give me a unique and witty pickup line about {topic}?"
    else:
        # Get the most recent conversation prompt
        if convo_history_collection.count_documents({"user_id": user_id}) == 0:
            convo_history_collection.insert_one({
                "user_id": user_id,
                "prompts": [""],
                "responses": ['']
            })

        prompt = convo_history['prompts'][-1]

    # Generate response using OpenAI API
    response = await generate_pickup_line(prompt)

    # Update conversation history in the database
    convo_history_collection.update_one(
        {"user_id": user_id},
        {
            "$push": {"prompts": prompt, "responses": response},
            "$set": {"conversation-history": convo_history},
        },
        upsert=True,
    )

    # Send response to user
    await ctx.send(response)

# Maybe add this to the backend so users wont be able to use this
@bot.command(name='reset')
async def reset_collection(ctx):
    user_id = str(ctx.author.id)

    # Check if user has a conversation history collection
    if convo_history_collection.count_documents({"user_id": user_id}) == 0:
        await ctx.send("You don't have any history of conversation.")
    else:
        # Delete user's conversation history collection
        convo_history_collection.delete_one({"user_id": user_id})
        await ctx.send("Your conversation history has been reset.")

bot.run(TOKEN)
