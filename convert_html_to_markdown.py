import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def convert_html_to_markdown(html_text, output_filename=None, domain=None, enable_all_plugins=True):
    """
    Convert HTML text to Markdown using the html-to-markdown API and save to a file.
    
    Args:
        html_text (str): The HTML content to convert
        output_filename (str, optional): Name of the output .md file. 
                                       If None, generates a timestamped filename.
        domain (str, optional): Domain to convert relative links to absolute links
        enable_all_plugins (bool): Whether to enable all available plugins for better formatting
    
    Returns:
        dict: Response containing success status, filename, and any error messages
    """
    
    # API endpoint
    url = "https://api.html-to-markdown.com/v1/convert"
    
    # Set API key
    api_key = os.getenv("API_KEY")

     # DEBUG: Check if API key is loaded
    if api_key is None:
        return {
            "success": False,
            "error": "API_KEY not found in environment variables. Check your .env file."
        }
    
    print(f"API Key loaded: {api_key[:10]}..." if len(api_key) > 10 else "API Key is too short")
    
    # Headers - you can also try Accept: text/markdown for direct markdown response
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",  # Change to "text/markdown" for direct response
        "X-API-Key": api_key
    }
    
    # Request body with plugins and options for better formatting
    data = {
        "html": html_text
    }
    
    # Add domain for absolute links if provided
    if domain:
        data["domain"] = domain
    
    # Add plugins for better formatting
    if enable_all_plugins:
        data["plugins"] = {
            "strikethrough": {},  # Enables ~~strikethrough~~ syntax
            "table": {}          # Enables table conversion (GitHub Flavored Markdown)
        }
    
    try:
        # Make the API request
        response = requests.post(url, headers=headers, json=data)
        
        # Check if request was successful
        if response.status_code == 201:
            # Parse the JSON response
            result = response.json()
            markdown_content = result.get("markdown", "")
            
            # Generate filename if not provided
            if output_filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"converted_markdown_{timestamp}.md"
            
            # Ensure the filename has .md extension
            if not output_filename.endswith('.md'):
                output_filename += '.md'
            
            # Save markdown to file
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            return {
                "success": True,
                "filename": output_filename,
                "message": f"HTML successfully converted to Markdown and saved as '{output_filename}'",
                "markdown_content": markdown_content
            }
        
        else:
            return {
                "success": False,
                "error": f"API request failed with status code {response.status_code}",
                "response_text": response.text
            }
    
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}"
        }
    
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse JSON response: {str(e)}"
        }
    
    except IOError as e:
        return {
            "success": False,
            "error": f"Failed to save file: {str(e)}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
