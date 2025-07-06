# Import the Groq AI library and operating system module
from groq import Groq
import os

# Create a connection to the Groq AI service
# Uses API key from environment variable or falls back to hardcoded key
client = Groq(
    api_key=os.getenv('GROQ_API_KEY', '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')
)

# Function to get AI responses for user questions about their data
def get_ai_response(question, context=""):
    """
    Get AI response for chatbot
    """
    # Instructions that tell the AI how to behave and what it should do
    system_prompt = """You are a smart and friendly data analysis assistant for an e-commerce platform called Prevanalyzer. 
Use the uploaded dataset and system statistics to answer questions clearly and accurately. 
You can explain data columns, summarize insights, detect trends, and clarify protection techniques (like masking, hashing, encryption, tokenization). 
If the data is unavailable or the question is unclear, respond politely and suggest ways to refine the question."""

    # Create the conversation structure for the AI
    # System message: tells AI how to behave
    # User message: includes data context and the user's question
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
    ]

    print("Sending question to AI:", question)  # Debugging output

    print(context,"********")





    try:
        # Send the question to the AI and get a response
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",  # Which AI model to use
            stream=False,                     # Get complete response at once
            max_tokens=500,                   # Maximum length of response
            temperature=0.7                   # How creative/random the response should be
        )
        
        # Extract and return the AI's response
        return chat_completion.choices[0].message.content
    except Exception as e:
        # If something goes wrong, return an error message
        return f"Error getting AI response: {str(e)}"