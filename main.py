import os
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import time
import re

# Load environment variables
load_dotenv()

# Streamlit page configuration
st.set_page_config(
    page_title="Indian Credit Card Recommender", 
    page_icon=":credit_card:", 
    layout="wide"
)

# Enhanced CSS for better table formatting
st.markdown("""
<style>
    table {
        width: 100%;
        border-collapse: collapse !important;
        margin: 25px 0;
        font-size: 0.9em;
        font-family: sans-serif;
        background: transparent;
    }
    
    table thead tr {
        background-color: #009879;
        color: #ffffff;
        text-align: left;
    }
    
    table th,
    table td {
        padding: 12px 15px;
        border: 1px solid #dddddd !important;
    }
    
    table tbody tr {
        border-bottom: 1px solid #dddddd;
        background: transparent;
    }
    
    table tbody tr:nth-of-type(even) {
        background: transparent;
    }
    
    table tbody tr:last-of-type {
        border-bottom: 2px solid #009879;
    }
    
    h3 {
        margin-top: 30px;
        margin-bottom: 10px;
        color: #009879;
    }
    
    .stMarkdown {
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)

# Credit card expert prompt with improved table formatting
CREDIT_CARD_EXPERT_PROMPT = """You are a concise credit card expert focusing on the Indian market. ALWAYS use HTML tables for comparisons, never use markdown tables, bullet points or paragraphs for comparing features.

RESPONSE FORMAT RULES:
1. ALL comparisons MUST be in HTML table format
2. NEVER use bullet points or paragraphs for comparisons
3. Use HTML tables with the following structure:

<h3>Basic Features</h3>
<table>
  <thead>
    <tr>
      <th>Feature</th>
      <th>Card 1</th>
      <th>Card 2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Annual Fee</td>
      <td>₹XXX</td>
      <td>₹YYY</td>
    </tr>
    <tr>
      <td>Welcome Benefits</td>
      <td>Detail</td>
      <td>Detail</td>
    </tr>
    <tr>
      <td>Income Required</td>
      <td>₹XXX</td>
      <td>₹YYY</td>
    </tr>
  </tbody>
</table>

<h3>Reward Rates</h3>
<table>
  <thead>
    <tr>
      <th>Category</th>
      <th>Card 1</th>
      <th>Card 2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>General Spend</td>
      <td>X%</td>
      <td>Y%</td>
    </tr>
    <tr>
      <td>Dining</td>
      <td>X%</td>
      <td>Y%</td>
    </tr>
    <tr>
      <td>Travel</td>
      <td>X%</td>
      <td>Y%</td>
    </tr>
    <tr>
      <td>Shopping</td>
      <td>X%</td>
      <td>Y%</td>
    </tr>
  </tbody>
</table>

<h3>Additional Benefits</h3>
<table>
  <thead>
    <tr>
      <th>Benefit</th>
      <th>Card 1</th>
      <th>Card 2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Lounge Access</td>
      <td>Detail</td>
      <td>Detail</td>
    </tr>
    <tr>
      <td>Insurance</td>
      <td>Detail</td>
      <td>Detail</td>
    </tr>
    <tr>
      <td>Offers</td>
      <td>Detail</td>
      <td>Detail</td>
    </tr>
  </tbody>
</table>

<h3>Best Suited For</h3>
<table>
  <thead>
    <tr>
      <th>Use Case</th>
      <th>Best Card</th>
      <th>Reason</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Overall</td>
      <td>Name</td>
      <td>Why</td>
    </tr>
    <tr>
      <td>Rewards</td>
      <td>Name</td>
      <td>Why</td>
    </tr>
    <tr>
      <td>Travel</td>
      <td>Name</td>
      <td>Why</td>
    </tr>
    <tr>
      <td>Shopping</td>
      <td>Name</td>
      <td>Why</td>
    </tr>
  </tbody>
</table>

IMPORTANT:
- Use ₹ symbol for all amounts
- Include actual numbers/percentages
- Present ALL comparisons in HTML tables
- No markdown tables, bullet points or paragraphs for comparing features
- Add table headers for each comparison section
- Ensure proper HTML table formatting with thead and tbody sections

Remember to:
- Keep Indian context central
- Use local examples
- Reference local regulations
- Consider Indian spending patterns
"""

# Configure API access
google_api_key = os.getenv("GOOGLE_API_KEY")

if not google_api_key:
    st.error("Google API key not found. Please set the GOOGLE_API_KEY environment variable.")
    st.stop()
    
genai.configure(api_key=google_api_key)

# Function to translate role for Streamlit
def translate_role_for_streamlit(user_role):
    if user_role == "model":
        return "assistant"
    else:
        return user_role

# Function to process response and fix any table issues
def process_response(text):
    # If response contains HTML tables, render them directly
    if "<table>" in text:
        return text
    
    # Try to fix markdown tables by converting them to HTML
    # This is a fallback if the model doesn't follow HTML table instructions
    markdown_table_pattern = r'(\|[^\n]+\|\n\|[\s\-:]+\|\n(?:\|[^\n]+\|\n)+)'
    
    def replace_with_html_table(match):
        markdown_table = match.group(1)
        rows = markdown_table.strip().split('\n')
        
        # Get header
        header_cells = [cell.strip() for cell in rows[0].split('|') if cell.strip()]
        
        # Start HTML table
        html_table = '<table>\n  <thead>\n    <tr>\n'
        
        # Add header cells
        for cell in header_cells:
            html_table += f'      <th>{cell}</th>\n'
        
        html_table += '    </tr>\n  </thead>\n  <tbody>\n'
        
        # Add data rows (skip header and separator rows)
        for row in rows[2:]:
            cells = [cell.strip() for cell in row.split('|') if cell]
            html_table += '    <tr>\n'
            for cell in cells:
                html_table += f'      <td>{cell}</td>\n'
            html_table += '    </tr>\n'
        
        html_table += '  </tbody>\n</table>'
        return html_table
    
    # Replace markdown tables with HTML tables
    text = re.sub(markdown_table_pattern, replace_with_html_table, text, flags=re.DOTALL)
    
    # Add section headers where needed
    section_titles = ["Basic Features", "Reward Rates", "Additional Benefits", "Best Suited For"]
    for title in section_titles:
        if title in text and f"<h3>{title}</h3>" not in text:
            text = text.replace(title, f"<h3>{title}</h3>")
    
    return text

# Initialize session state for chat history and system prompt
if "chat_session" not in st.session_state:
    # Initialize chat with system prompt
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.1,  # Lower temperature for more factual responses
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 4096,  # Increased for complex tables
        }
    )
    
    # Start chat with the system prompt
    st.session_state.chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [CREDIT_CARD_EXPERT_PROMPT]
            },
            {
                "role": "model",
                "parts": ["I understand. I'll act as a concise credit card expert focusing on the Indian market. I'll always use HTML tables for comparisons and follow the specified format rules. I'll keep the Indian context central in all my responses."]
            }
        ]
    )
    
    # Rate limit tracking
    st.session_state.last_request_time = 0
    st.session_state.requests_in_minute = 0

# Display app header
st.title("Indian Credit Card Advisor 💳")
st.markdown("""
Get expert recommendations on the best credit cards in India based on your preferences and needs.
All information is specific to the Indian market and includes the latest offers and benefits.
""")

# Display chat history
for message in st.session_state.chat_session.history[2:]:  # Skip the system prompt
    with st.chat_message(translate_role_for_streamlit(message.role)):
        if message.role == "model":
            st.markdown(process_response(message.parts[0].text), unsafe_allow_html=True)
        else:
            st.markdown(message.parts[0].text)

# Get user input
user_prompt = st.chat_input("Ask about credit cards in India...")

# Process user input
if user_prompt:
    # Check rate limiting (10 requests per minute)
    current_time = time.time()
    if current_time - st.session_state.last_request_time > 60:
        st.session_state.requests_in_minute = 0
        st.session_state.last_request_time = current_time
    
    if st.session_state.requests_in_minute >= 10:
        time_to_wait = 60 - (current_time - st.session_state.last_request_time)
        st.error(f"Rate limit exceeded. Please wait approximately {int(time_to_wait)} seconds before trying again.")
    else:
        st.session_state.requests_in_minute += 1
        
        # Display user message
        st.chat_message("user").markdown(user_prompt)
        
        # Enhanced user prompt to focus on Indian credit cards
        enhanced_prompt = f"For Indian credit cards only: {user_prompt}. Remember to use HTML tables with proper <table>, <thead>, and <tbody> tags for all comparisons, NOT markdown tables."
        
        # Show a spinner while waiting for the response
        with st.spinner("Analyzing Indian credit card options..."):
            try:
                gemini_response = st.session_state.chat_session.send_message(enhanced_prompt)
                
                # Display assistant response with properly formatted tables
                with st.chat_message("assistant"):
                    processed_response = process_response(gemini_response.text)
                    st.markdown(processed_response, unsafe_allow_html=True)
                    
            except Exception as e:
                st.error(f"Error getting response: {str(e)}")
                st.session_state.requests_in_minute -= 1  # Don't count failed requests