import re
from typing import Dict, List, Tuple
from pathlib import Path


class MarkdownHierarchyParser:
    """
    A class to parse markdown files and extract section hierarchy based on heading levels.
    """
    
    def __init__(self, filepath: str = None, markdown_content: str = None):
        """
        Initialize the parser with either a file path or markdown content.
        
        Args:
            filepath: Path to the markdown file
            markdown_content: Raw markdown content as string
        """
        if filepath:
            self.filepath = Path(filepath)
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.content = f.read()
        elif markdown_content:
            self.content = markdown_content
            self.filepath = None
        else:
            raise ValueError("Either filepath or markdown_content must be provided")
    
    def _extract_headings(self) -> List[Tuple[int, str]]:
        """
        Extract all headings from the markdown content.
        
        Returns:
            List of tuples containing (level, title) for each heading
        """
        headings = []
        # Match markdown headings (# Heading)
        pattern = r'^(#{1,6})\s+(.+?)(?:\s*\{[^}]*\})?$'
        
        for line in self.content.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                level = len(match.group(1))  # Number of # characters
                title = match.group(2).strip()
                headings.append((level, title))
        
        return headings
    
    def _build_hierarchy(self, headings: List[Tuple[int, str]]) -> Dict:
        """
        Build a nested dictionary representing the section hierarchy.
        
        Args:
            headings: List of (level, title) tuples
            
        Returns:
            Nested dictionary representing the hierarchy
        """
        if not headings:
            return {}
        
        root = {}
        stack = [(0, root)]  # Stack of (level, dict_reference)
        
        for level, title in headings:
            # Pop stack until we find the parent level
            while stack and stack[-1][0] >= level:
                stack.pop()
            
            # Get the parent dictionary
            if stack:
                parent_dict = stack[-1][1]
            else:
                parent_dict = root
            
            # Create new entry for this heading
            parent_dict[title] = {}
            
            # Push this level onto the stack
            stack.append((level, parent_dict[title]))
        
        return root
    
    def get_hierarchy(self) -> Dict:
        """
        Parse the markdown file and return the section hierarchy.
        
        Returns:
            Nested dictionary where keys are section titles and values are
            dictionaries of subsections
        """
        headings = self._extract_headings()
        return self._build_hierarchy(headings)
    
    def get_hierarchy_json(self, indent: int = 2) -> str:
        """
        Get the hierarchy as a JSON string.
        
        Args:
            indent: Number of spaces for JSON indentation
            
        Returns:
            JSON string representation of the hierarchy
        """
        import json
        hierarchy = self.get_hierarchy()
        return json.dumps(hierarchy, indent=indent, ensure_ascii=False)
    
    def print_hierarchy(self, hierarchy: Dict = None, level: int = 0):
        """
        Print the hierarchy in a readable tree format.
        
        Args:
            hierarchy: The hierarchy dict to print (uses self.get_hierarchy() if None)
            level: Current indentation level (used for recursion)
        """
        if hierarchy is None:
            hierarchy = self.get_hierarchy()
        
        for title, children in hierarchy.items():
            print("  " * level + f"- {title}")
            if children:
                self.print_hierarchy(children, level + 1)
    
    def save_hierarchy_json(self, output_filepath: str = None, indent: int = 2):
        """
        Save the hierarchy to a JSON file.
        
        Args:
            output_filepath: Path for the output JSON file. 
                           If None, uses the markdown filename with .json extension
            indent: Number of spaces for JSON indentation
        """
        import json
        
        if output_filepath is None:
            # Use the same name as the markdown file but with .json extension
            output_filepath = self.filepath.with_suffix('.json')
        
        hierarchy = self.get_hierarchy()
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(hierarchy, f, indent=indent, ensure_ascii=False)
        
        print(f"Hierarchy saved to: {output_filepath}")


# Example usage
if __name__ == "__main__":

    file_name = "AP510e_Installation_Guide_fixed"    
    # Parse from string
    parser = MarkdownHierarchyParser(filepath=f"{file_name}.md")

    # Get hierarchy as dict
    hierarchy = parser.get_hierarchy()
    print("Hierarchy as dictionary:")
    print(hierarchy)
    print("\n" + "="*50 + "\n")
    
    # Print as JSON
    print("Hierarchy as JSON:")
    print(parser.get_hierarchy_json())
    print("\n" + "="*50 + "\n")
    
    # Print as tree
    print("Hierarchy as tree:")
    parser.print_hierarchy()

    # Save hierarchy to JSON file
    parser.save_hierarchy_json(output_filepath=f"{file_name}_hierarchy.json")