import re
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

def convert_html_to_markdown(html):
    """Convert HTML formatting to markdown with enhanced text cleaning"""
    if not html:
        return ""
        
    # First clean up any malformed HTML
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove unwanted elements
    for element in soup.find_all(['script', 'style', 'meta']):
        element.decompose()
    
    # Handle lists first (before other replacements)
    for ul in soup.find_all('ul'):
        items = []
        for li in ul.find_all('li'):
            items.append(f"- {li.get_text().strip()}")
        new_tag = soup.new_string('\n' + '\n'.join(items) + '\n\n')
        ul.replace_with(new_tag)
    
    for ol in soup.find_all('ol'):
        items = []
        for i, li in enumerate(ol.find_all('li'), 1):
            items.append(f"{i}. {li.get_text().strip()}")
        new_tag = soup.new_string('\n' + '\n'.join(items) + '\n\n')
        ol.replace_with(new_tag)
    
    # Convert HTML to string
    text = str(soup)
    
    # Replace common HTML elements with markdown
    replacements = [
        # Headers (must come before bold/italic)
        (r'<h1[^>]*>(.*?)</h1>', r'# \1\n'),
        (r'<h2[^>]*>(.*?)</h2>', r'## \1\n'),
        (r'<h3[^>]*>(.*?)</h3>', r'### \1\n'),
        (r'<h4[^>]*>(.*?)</h4>', r'#### \1\n'),
        (r'<h5[^>]*>(.*?)</h5>', r'##### \1\n'),
        (r'<h6[^>]*>(.*?)</h6>', r'###### \1\n'),
        
        # Text formatting
        (r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>', r'**\1**'),
        (r'<(?:i|em)[^>]*>(.*?)</(?:i|em)>', r'*\1*'),
        (r'<code[^>]*>(.*?)</code>', r'`\1`'),
        
        # Links and images
        (r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)'),
        (r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*/>', r'![\2](\1)'),
        
        # Line breaks and paragraphs
        (r'<br[^>]*/>', '\n'),
        (r'<br>', '\n'),
        (r'</br>', ''),
        (r'<p[^>]*>(.*?)</p>', r'\1\n\n'),
        
        # Divs and spans
        (r'<div[^>]*>(.*?)</div>', r'\1\n'),
        (r'<span[^>]*>(.*?)</span>', r'\1'),
        
        # HTML entities
        (r'&nbsp;', ' '),
        (r'&amp;', '&'),
        (r'&lt;', '<'),
        (r'&gt;', '>'),
        (r'&quot;', '"'),
        (r'&apos;', "'"),
        (r'&#8377;', '₹'),
        (r'&#x20b9;', '₹'),
        (r'&mdash;', '—'),
        (r'&ndash;', '–'),
        (r'&bull;', '•'),
    ]
    
    # Apply replacements
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    return text.strip()

def format_table(table_html):
    """Convert HTML table to DataFrame with enhanced formatting"""
    try:
        soup = BeautifulSoup(table_html, 'html.parser')
        
        # Extract headers
        headers = []
        header_row = soup.find('thead').find('tr') if soup.find('thead') else soup.find('tr')
        for th in header_row.find_all(['th', 'td']):
            header_text = convert_html_to_markdown(str(th))
            headers.append(header_text.strip())
        
        # Extract rows
        data = []
        tbody = soup.find('tbody') if soup.find('tbody') else soup
        for tr in tbody.find_all('tr'):
            if tr != header_row:  # Skip header row if it's in tbody
                row = []
                for td in tr.find_all(['td', 'th']):
                    cell_content = convert_html_to_markdown(str(td))
                    row.append(cell_content.strip())
                if row:  # Only add non-empty rows
                    data.append(row)
        
        # Create DataFrame
        if headers and data:
            # Ensure all rows have the same number of columns
            max_cols = max(len(headers), max(len(row) for row in data))
            headers.extend([''] * (max_cols - len(headers)))
            for row in data:
                row.extend([''] * (max_cols - len(row)))
            
            df = pd.DataFrame(data, columns=headers)
            return df
        return None
    except Exception as e:
        print(f"Error formatting table: {e}")
        return None

def format_and_render_response(text):
    """Format and render the response with enhanced handling"""
    if not text:
        return
    
    # Split into tables and non-tables
    parts = re.split(r'(<table.*?</table>)', text, flags=re.DOTALL)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        if part.startswith('<table'):
            # Handle table
            df = format_table(part)
            if df is not None:
                # Apply custom styling with dark theme
                st.markdown("""
                <style>
                .stDataFrame {
                    background-color: #262730 !important;
                    color: #FAFAFA !important;
                }
                .stDataFrame th {
                    background-color: #1E1E1E !important;
                    color: #FAFAFA !important;
                    font-weight: bold !important;
                }
                .stDataFrame tr:nth-child(even) {
                    background-color: #262730 !important;
                }
                .stDataFrame tr:nth-child(odd) {
                    background-color: #1E1E1E !important;
                }
                .stDataFrame tr:hover {
                    background-color: #0E1117 !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                st.dataframe(
                    df.style.set_properties(**{
                        'color': '#FAFAFA',
                        'background-color': '#262730',
                    }),
                    hide_index=True, 
                    use_container_width=True
                )
        else:
            # Clean up and convert HTML to plain text
            cleaned_text = convert_html_to_markdown(part)
            
            # Custom rendering with dark theme
            st.markdown(f"""
            <div style="
                background-color: #262730; 
                color: #FAFAFA; 
                padding: 15px; 
                border-radius: 5px; 
                margin-bottom: 10px;
            ">
            {cleaned_text}
            </div>
            """, unsafe_allow_html=True)