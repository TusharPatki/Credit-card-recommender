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
    
    # Fix spacing issues
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Remove extra blank lines
    text = re.sub(r'[ \t]+', ' ', text)  # Remove extra spaces and tabs
    
    # Process text line by line
    lines = text.split('\n')
    processed_lines = []
    for line in lines:
        line = line.strip()
        if line:
            # Fix first word spacing without affecting markdown
            if not line.startswith(('#', '-', '*', '1.', '>')):
                line = re.sub(r'^([A-Za-z]+)\s+', r'\1 ', line)
            processed_lines.append(line)
    
    text = '\n'.join(processed_lines)
    
    # Clean up markdown formatting
    text = re.sub(r'\*\*\s+(\w)', r'**\1', text)  # Remove space after opening bold
    text = re.sub(r'(\w)\s+\*\*', r'\1**', text)  # Remove space before closing bold
    text = re.sub(r'\*\s+(\w)', r'*\1', text)     # Remove space after opening italic
    text = re.sub(r'(\w)\s+\*', r'\1*', text)     # Remove space before closing italic
    
    # Ensure proper spacing around headers and lists
    text = re.sub(r'(^|\n)(#{1,6})\s*([^\n]+)', r'\1\2 \3', text)  # Fix header spacing
    text = re.sub(r'(^|\n)-\s*([^\n]+)', r'\1- \2', text)  # Fix list item spacing
    
    # Final cleanup
    text = text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)  # Maximum two consecutive newlines
    
    return text

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

def format_text_section(text):
    """Format text sections with proper styling and structure"""
    if not text:
        return ""
    
    # First clean up any malformed HTML
    soup = BeautifulSoup(text, 'html.parser')
    
    # Remove unwanted elements
    for element in soup.find_all(['script', 'style', 'meta']):
        element.decompose()
    
    # Handle lists first
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
    
    # Replace HTML elements with markdown
    replacements = [
        # Headers
        (r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n'),
        (r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n'),
        (r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n'),
        (r'<h4[^>]*>(.*?)</h4>', r'#### \1\n\n'),
        (r'<h5[^>]*>(.*?)</h5>', r'##### \1\n\n'),
        (r'<h6[^>]*>(.*?)</h6>', r'###### \1\n\n'),
        
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
    
    # Split into sections
    sections = []
    current_section = []
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            if current_section:
                sections.append('\n'.join(current_section))
                current_section = []
        else:
            # Handle first word spacing without affecting markdown
            if not any(line.startswith(prefix) for prefix in ['#', '-', '*', '1.', '>', '|']):
                line = re.sub(r'^([A-Za-z]+)\s+', r'\1 ', line)
            current_section.append(line)
    
    if current_section:
        sections.append('\n'.join(current_section))
    
    # Process each section
    formatted_sections = []
    for section in sections:
        # Clean up markdown formatting
        section = re.sub(r'\*\*\s+(\w)', r'**\1', section)  # Fix bold
        section = re.sub(r'(\w)\s+\*\*', r'\1**', section)
        section = re.sub(r'\*\s+(\w)', r'*\1', section)     # Fix italic
        section = re.sub(r'(\w)\s+\*', r'\1*', section)
        
        # Fix header spacing
        section = re.sub(r'^(#{1,6})\s*(\w)', r'\1 \2', section)
        
        # Fix list spacing
        section = re.sub(r'^-\s*(\w)', r'- \1', section)
        section = re.sub(r'^\d+\.\s*(\w)', r'\1. \1', section)
        
        formatted_sections.append(section)
    
    return '\n\n'.join(formatted_sections)

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
                # Apply styling
                styled_df = df.style.set_properties(**{
                    'text-align': 'left',
                    'white-space': 'pre-wrap',
                    'overflow-wrap': 'break-word',
                    'max-width': '0',
                })
                styled_df = styled_df.set_table_styles([
                    {'selector': 'th', 'props': [
                        ('background-color', '#009879'),
                        ('color', 'white'),
                        ('font-weight', 'bold'),
                        ('text-align', 'left'),
                        ('padding', '12px 15px'),
                        ('white-space', 'pre-wrap'),
                        ('overflow-wrap', 'break-word'),
                    ]},
                    {'selector': 'td', 'props': [
                        ('padding', '12px 15px'),
                        ('white-space', 'pre-wrap'),
                        ('overflow-wrap', 'break-word'),
                    ]},
                    {'selector': 'tr:nth-of-type(even)', 'props': [
                        ('background-color', 'rgba(0, 152, 121, 0.05)')
                    ]},
                    {'selector': 'tr:hover', 'props': [
                        ('background-color', 'rgba(0, 152, 121, 0.1)')
                    ]}
                ])
                
                st.dataframe(
                    styled_df,
                    hide_index=True,
                    use_container_width=True
                )
        else:
            # Format and render text content
            formatted_text = format_text_section(part)
            if formatted_text:
                sections = formatted_text.split('\n\n')
                for section in sections:
                    if section.strip():
                        if re.match(r'^#{1,6}\s', section):
                            # Render headers with special styling
                            header_level = len(re.match(r'^(#+)\s', section).group(1))
                            margin_top = '2em' if header_level == 1 else '1.5em' if header_level == 2 else '1.2em'
                            margin_bottom = '0.8em' if header_level == 1 else '0.6em' if header_level == 2 else '0.4em'
                            st.markdown(f'<div style="margin-top: {margin_top}; margin-bottom: {margin_bottom}; font-weight: bold;">{section}</div>', unsafe_allow_html=True)
                        elif section.startswith('- ') or re.match(r'^\d+\.', section):
                            # Render lists with proper spacing
                            st.markdown(f'<div style="margin-left: 1em; margin-bottom: 1em;">{section}</div>', unsafe_allow_html=True)
                        else:
                            # Render regular paragraphs
                            st.markdown(f'<div style="margin-bottom: 1em;">{section}</div>', unsafe_allow_html=True) 