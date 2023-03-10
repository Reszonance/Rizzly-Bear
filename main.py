import discord
from discord.ext import commands
import openai
import os
from dotenv import load_dotenv
import pymongo

load_dotenv()

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")

# Set up MongoDB client and database
mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
mongo_db = mongo_client['rizzults']

# Set up MongoDB collection
conversation_history_collection = mongo_db['convseration-history']

# Set up Discord bot credentials
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# GUILD = os.getenv("DISCORD_GUILD_ID")

# Set up Discord client
intents = discord.Intents.all()
intents.members = True
intents.presences = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Define initial prompt
question = os.getenv("QUESTION")
initial_prompt = os.getenv("INITIAL_PROMPT") + question


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

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    # Check if there are any arguments passed
    if args:
        # Get the topic from the argument
        topic = ' '.join(args)
        # Create a new conversation prompt based on the topic
        prompt = os.getenv("INITIAL_PROMPT") + f"Can you give me a pickup line about {topic}?\n"
    else:
        # Get the most recent conversation prompt
        if user_id not in conversation_history:
            conversation_history[user_id] = {
                'prompts': [initial_prompt],
                'responses': ['']
            }

        prompt = conversation_history[user_id]['prompts'][-1]

        # Wait for user to respond
        await ctx.send("Type 'continue' to continue the conversation or 'new' to start a new one.")
        response = await bot.wait_for('message', check=check)

        # Handle "new" command
        while response.content.lower() not in ['continue', 'new']:
            await ctx.send("Invalid response. Type 'continue' to continue the conversation or 'new' to start a new one.")
            response = await bot.wait_for('message', check=check)

        if response.content.lower() == 'new':
            await ctx.send("Okay, let's start a new conversation!")
            conversation_history[user_id] = {
                'prompts': [initial_prompt],
                'responses': ['']
            }
            prompt = initial_prompt
            print('new')
        else:
            # Get the most recent conversation prompt
            new_prompt = conversation_history[user_id]['responses'][-1]
            prompt = new_prompt + question
            print('continuing')

    print("\n" + prompt)
    prompt = prompt.replace('\n', '').replace(',', '').replace('.', '').replace('!', '').replace('?', '')
    # Generate response using OpenAI API
    response = await generate_pickup_line(prompt)

    # Update conversation history
    conversation_history[user_id]['prompts'].append(prompt)
    conversation_history[user_id]['responses'].append(response)

    # Store conversation history in MongoDB
    conversation_history_collection.update_one(
        {"user_id": user_id},
        {"$set": {"conversation_history": conversation_history[user_id]}},
        upsert=True,
    )

    # Send response to user
    await ctx.send(response)

bot.run(TOKEN)