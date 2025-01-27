import google.generativeai as genai
import os
from dotenv import load_dotenv

class Chatbot:
    def __init__(self):
        load_dotenv()
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Initialize the model and chat
        self.model = genai.GenerativeModel('gemini-pro')
        self.chat = self.model.start_chat(history=[])
    
    def get_response(self, prompt):
        try:
            # Format the prompt for educational context
            formatted_prompt = f"""As a helpful educational assistant, please help with this homework question:
            {prompt}
            
            Please provide a clear, educational response that helps the student understand the concept."""
            
            # Get response from the model
            response = self.chat.send_message(formatted_prompt)
            return response.text
        except Exception as e:
            print(f"Error getting AI response: {str(e)}")
            raise

# For testing
if __name__ == "__main__":
    chatbot = Chatbot()
    while True:
        prompt = input("Ask me anything (type 'exit' to quit): ")
        if prompt.lower() == 'exit':
            break
        try:
            response = chatbot.get_response(prompt)
            print("\nAI:", response)
        except Exception as e:
            print(f"Error: {str(e)}")