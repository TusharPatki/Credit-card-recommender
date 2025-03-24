import os
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import time
import re
from urllib.parse import urlparse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import random
from crawl4ai import (
    AsyncWebCrawler, 
    BrowserConfig, 
    CrawlerRunConfig, 
    CacheMode,
    RateLimiter,
    CrawlerMonitor,
    DisplayMode
)
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
import pandas as pd
from response_formatter import format_and_render_response

# Load environment variables
load_dotenv()

# Define official bank and trusted domains
PRIMARY_SOURCES = [
    "cardinsider.com",  # Primary source
    "bankbazaar.com",   # Secondary source
]

BANK_DOMAINS = [
    "hdfcbank.com",
    "sbicard.com",
    "icicibank.com",
    "axisbank.com",
    "idfcfirstbank.com",
    "indusind.com",
    "hsbc.co.in",
    "sc.com",
    "kotak.com",
    "yesbank.in",
    "rblbank.com",
    "creditcardinsider.in",
    "cardexpert.in",
]

def is_trusted_domain(url):
    """Check if the URL belongs to a trusted domain"""
    try:
        domain = urlparse(url).netloc.lower()
        # Remove 'www.' if present
        domain = domain.replace('www.', '')
        return domain in PRIMARY_SOURCES or domain in BANK_DOMAINS
    except:
        return False

# Streamlit page configuration
st.set_page_config(
    page_title="Indian Credit Card Recommender", 
    page_icon=":credit_card:", 
    layout="wide"
)

# Enhanced CSS for better table formatting
st.markdown("""
<style>
    div[data-testid="stTable"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 1rem 0 !important;
        background-color: transparent !important;
    }
    
    div[data-testid="stTable"] thead tr {
        background-color: #009879 !important;
        color: white !important;
    }
    
    div[data-testid="stTable"] th {
        background-color: #009879 !important;
        color: white !important;
        font-weight: bold !important;
        text-align: left !important;
        padding: 12px 15px !important;
        border: 1px solid #dddddd !important;
    }
    
    div[data-testid="stTable"] td {
        padding: 12px 15px !important;
        border: 1px solid #dddddd !important;
    }
    
    div[data-testid="stTable"] tbody tr:nth-of-type(even) {
        background-color: rgba(0, 0, 0, 0.05) !important;
    }
    
    div[data-testid="stTable"] tbody tr:hover {
        background-color: rgba(0, 0, 0, 0.075) !important;
    }
    
    div[data-testid="stTable"] tbody tr:last-of-type {
        border-bottom: 2px solid #009879 !important;
    }
</style>
""", unsafe_allow_html=True)

# Credit card expert prompt with improved table formatting
CREDIT_CARD_EXPERT_PROMPT = """You are a concise credit card expert focusing on the Indian market. When presenting card comparisons or multiple card information, use simple HTML tables with minimal formatting.

TABLE FORMATTING RULES:

1. FOR CARD COMPARISONS:
| Feature | [First Card Name] | [Second Card Name] |
|---------|------------------|-------------------|
| Annual Fee | ₹XXX | ₹YYY |
| Reward Rate | X% on [category] | Y% on [category] |
| Welcome Benefits | [Details] | [Details] |
| Key Features | [List top 3] | [List top 3] |

2. FOR MULTIPLE CARD LISTINGS:
| Card Name | Key Benefits | Annual Fee | Best For |
|-----------|--------------|------------|----------|
| [Card Name] | [Top 2-3 benefits] | ₹XXX | [Primary use case] |

WHEN TO USE TABLES:
✓ ALWAYS for comparing two or more cards
✓ ALWAYS for listing features of multiple cards
✓ ALWAYS for showing reward rate comparisons
✓ ALWAYS for displaying fee structures across cards

FORMATTING RULES:
- Use ₹ symbol for all amounts
- Bold (**text**) for time-sensitive information
- Include specific numbers and percentages
- Keep each cell concise but informative
- Use proper markdown table syntax with aligned columns

RESPONSE STRUCTURE:
1. Start with a brief introduction
2. Present the comparison/information in a table
3. Add any additional context below the table
4. Include time-sensitive disclaimers if applicable

Remember:
- Focus on Indian market context
- Use verified information only
- Keep responses factual
- Include latest features and benefits
- Use proper markdown table formatting"""

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

# Function to perform web search using aiohttp
async def perform_web_search(query, num_results=3):
    try:
        # Primary source paths (more specific to detailed)
        primary_paths = [
            "/credit-card/compare/",
            "/credit-cards/details/",
            "/credit-card-reviews/",
            "/credit-cards/search",
            "/credit-cards"
        ]
        
        # Verification source paths
        verification_paths = [
            "/credit-cards/benefits",
            "/credit-card/offers",
            "/credit-card/rewards",
            "/cards/compare"
        ]
        
        # First try primary sources
        primary_urls = [
            f"https://{domain}{path}{query.replace(' ', '-').lower()}"
            for domain in PRIMARY_SOURCES
            for path in primary_paths
        ]
        
        # Then verification sources
        verification_urls = [
            f"https://{domain}{path}"
            for domain in BANK_DOMAINS[:5]  # Limit to top 5 banks for speed
            for path in verification_paths
        ]
        
        formatted_results = []
        timeout = aiohttp.ClientTimeout(total=10)  # Reduced timeout to 10 seconds
        
        # Essential credit card indicators with weights
        credit_card_indicators = {
            "reward rate": 3,
            "cashback": 3,
            "annual fee": 3,
            "welcome offer": 2,
            "lounge access": 2,
            "credit limit": 2,
            "joining fee": 2,
            "benefits": 1,
            "eligibility": 1
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            # First search primary sources
            primary_tasks = [
                asyncio.create_task(fetch_url(session, url, credit_card_indicators))
                for url in primary_urls
            ]
            
            primary_results = await asyncio.gather(*primary_tasks, return_exceptions=True)
            
            # Process primary results
            for result in primary_results:
                if isinstance(result, dict) and result.get('snippet'):
                    formatted_results.append({**result, 'source_type': 'primary'})
                    if len(formatted_results) >= num_results:
                        return formatted_results
            
            # If needed, try verification sources
            if len(formatted_results) < num_results:
                verification_tasks = [
                    asyncio.create_task(fetch_url(session, url, credit_card_indicators))
                    for url in verification_urls
                ]
                
                verification_results = await asyncio.gather(*verification_tasks, return_exceptions=True)
                
                for result in verification_results:
                    if isinstance(result, dict) and result.get('snippet'):
                        formatted_results.append({**result, 'source_type': 'verification'})
                        if len(formatted_results) >= num_results:
                            break
        
        return formatted_results
                
    except Exception:
        return []

async def fetch_url(session, url, credit_card_indicators):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Quick cleanup
                for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()
                
                # Find credit card specific content
                card_content = soup.find('div', class_=lambda x: x and any(term in x.lower() for term in ['card-details', 'product-info', 'card-comparison', 'card-benefits']))
                
                if not card_content:
                    card_content = soup
                
                # Extract text from paragraphs and lists
                texts = []
                for elem in card_content.find_all(['p', 'li', 'h2', 'h3', 'td']):
                    text = elem.get_text(strip=True)
                    if text and len(text) > 30:  # Minimum length check
                        # Calculate relevance score
                        score = sum(
                            weight
                            for term, weight in credit_card_indicators.items()
                            if term in text.lower()
                        )
                        if score > 0:
                            texts.append((text, score))
                
                if texts:
                    # Sort by relevance score and combine top snippets
                    texts.sort(key=lambda x: x[1], reverse=True)
                    best_snippets = [text for text, _ in texts[:2]]
                    
                    # Clean up title
                    title = soup.title.string if soup.title else ""
                    title = re.sub(r'\s+', ' ', title).strip()
                    title = re.sub(r'^(.*?)\s*[|\-]\s*.*$', r'\1', title)
                    
                    return {
                        "title": title,
                        "link": str(response.url),
                        "snippet": " | ".join(best_snippets)[:250],
                        "relevance_score": sum(score for _, score in texts[:2])
                    }
    except Exception:
        pass
    return None

# Function to enhance credit card response with web search
async def enhance_with_web_search(query):
    try:
        search_query = f"{query} credit card features rewards"
        search_results = await perform_web_search(search_query)
        
        if search_results:
            # Sort results by relevance score
            search_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            # Remove duplicates based on snippet content
            seen_snippets = set()
            unique_results = []
            for result in search_results:
                snippet = result.get('snippet', '').strip()
                # Create a simplified version of the snippet for comparison
                simple_snippet = ' '.join(snippet.lower().split())
                if simple_snippet and simple_snippet not in seen_snippets:
                    seen_snippets.add(simple_snippet)
                    unique_results.append(result)
            
            meaningful_results = [
                result for result in unique_results
                if result.get('snippet') and len(result['snippet'].strip()) > 50
                and not any(term in result['snippet'].lower() for term in ['cookie', 'privacy', 'terms of use'])
            ]
            
            if meaningful_results:
                enhancement = "\n\nRecent Credit Card Updates from Major Indian Banks\n\n"
                
                # Group results by source type
                primary_results = [r for r in meaningful_results if r['source_type'] == 'primary'][:1]  # Limit to 1 primary result
                verification_results = [r for r in meaningful_results if r['source_type'] == 'verification'][:1]  # Limit to 1 verification result
                
                # Add primary source information
                if primary_results:
                    result = primary_results[0]
                    domain = urlparse(result['link']).netloc.replace('www.', '')
                    snippet = result['snippet'].strip()
                    enhancement += f"• From {domain}: {snippet}\n\n"
                
                # Add verification information if available and different from primary
                if verification_results:
                    verification_result = verification_results[0]
                    if not primary_results or verification_result['snippet'] != primary_results[0]['snippet']:
                        domain = urlparse(verification_result['link']).netloc.replace('www.', '')
                        snippet = verification_result['snippet'].strip()
                        enhancement += f"• From {domain}: {snippet}\n\n"
                
                # Add disclaimer
                enhancement += "\n*Please verify the latest terms and conditions on the official bank website.*"
                
                return enhancement
        return ""
                
    except Exception:
        return ""

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
                "parts": ["""Hello! 👋 I'm your Indian Credit Card Expert, and I'm here to help you make informed decisions about credit cards in India. Here's how I can assist you:

1. Card Comparisons: I can compare different credit cards side by side, showing you:
   - Annual fees and charges
   - Reward rates and benefits
   - Welcome offers
   - Eligibility criteria

2. Card Reviews: I can provide detailed reviews of specific cards with:
   - Feature analysis
   - Benefits breakdown
   - Best use cases
   - Current offers

3. General Advice: I can answer questions about:
   - Card recommendations based on your spending
   - Latest credit card offers in India
   - Application requirements
   - Credit card features and terms

You can ask me anything about Indian credit cards, and I'll provide accurate, up-to-date information from trusted sources. How may I assist you today?"""]
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

**How to use:**
- Ask for card comparisons (e.g., "Compare HDFC Regalia vs Diners Club Black")
- Request card reviews (e.g., "Tell me about the Amazon Pay ICICI card")
- Seek recommendations (e.g., "Best cards for online shopping")
- Ask about features (e.g., "Which cards offer best airport lounge access?")
""")

# Display chat history
for message in st.session_state.chat_session.history[2:]:  # Skip the system prompt
    with st.chat_message(translate_role_for_streamlit(message.role)):
        if message.role == "model":
            format_and_render_response(message.parts[0].text)
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
        enhanced_prompt = f"For Indian credit cards only: {user_prompt}"
        
        # Show a spinner while waiting for the response
        with st.spinner("Analyzing Indian credit card options..."):
            async def process_request():
                try:
                    # Get web search results
                    web_info = await enhance_with_web_search(user_prompt)
                    
                    # Get Gemini response
                except Exception as e:
                    st.error(f"Error getting web search results: {str(e)}")
                    st.session_state.requests_in_minute -= 1  # Don't count failed requests
                    return
                gemini_response = st.session_state.chat_session.send_message(enhanced_prompt)
                # Combine Gemini response with web search results
                combined_response = gemini_response.text + web_info
                
                # Display assistant response with properly formatted tables
                try:
                    with st.chat_message("assistant"):
                        format_and_render_response(combined_response)
                except Exception as e:
                    st.error(f"Error getting response: {str(e)}")
                    st.session_state.requests_in_minute -= 1  # Don't count failed requests
            asyncio.run(process_request())