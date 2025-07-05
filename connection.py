from groq import Groq
import os

# Initialize Groq client
client = Groq(
    api_key=os.getenv('GROQ_API_KEY', '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')
)

def get_ai_response(question, context=""):
    """
    Get AI response for chatbot
    """
    system_prompt = """You are a smart and friendly data analysis assistant for an e-commerce platform called Prevanalyzer. 
Use the uploaded dataset and system statistics to answer questions clearly and accurately. 
You can explain data columns, summarize insights, detect trends, and clarify protection techniques (like masking, hashing, encryption, tokenization). 
If the data is unavailable or the question is unclear, respond politely and suggest ways to refine the question."""

    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
    ]
    
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            stream=False,
            max_tokens=500,
            temperature=0.7
        )
        
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Error getting AI response: {str(e)}"