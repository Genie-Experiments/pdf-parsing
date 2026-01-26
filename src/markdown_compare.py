#!/usr/bin/env python3
"""
Markdown Comparison Tool for RAG Pipeline
Compares ground truth markdown with generated markdown files.
Performs structure-aware, content-aware comparison with detailed metrics.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import argparse

@dataclass
class Element:
    """Base class for markdown elements"""
    type: str
    content: Any
    line_number: int


@dataclass
class Section:
    """Represents a markdown section with heading and elements"""
    level: int
    title: str
    elements: List[Element]
    line_number: int


@dataclass
class ComparisonMetrics:
    """Metrics for comparison results"""
    overall_similarity: float
    section_similarities: Dict[str, float]
    element_mismatches: Dict[str, int]
    total_elements_golden: int
    total_elements_generated: int
    missing_sections: List[str]   # List of section titles missing in generated file
    extra_sections: List[str]      # List of extra section titles in generated file


class MarkdownParser:
    """Parse markdown into structured sections and elements"""
    
    def __init__(self):
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self.code_block_pattern = re.compile(r'^```(\w*)\n(.*?)^```', re.MULTILINE | re.DOTALL)
        self.table_pattern = re.compile(r'^\|(.+)\|$', re.MULTILINE)
        self.latex_pattern = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$', re.DOTALL)
        self.image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        self.link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    def detect_headers_footers(self, content: str) -> Tuple[int, int]:
        """
        Detect repeated header/footer content automatically.
        Returns (header_lines, footer_lines) to skip.
        """
        lines = content.split('\n')
        if len(lines) < 10:
            return 0, 0
        
        # Simple heuristic: look for repeated patterns at start/end
        # Check first/last 5 lines for repetition patterns
        line_freq = {}
        for i, line in enumerate(lines):
            normalized = line.strip()
            if len(normalized) < 5:
                continue
            if normalized not in line_freq:
                line_freq[normalized] = []
            line_freq[normalized].append(i)
        
        header_lines = 0
        footer_lines = 0
        
        # Find repeated lines in first 20% of document
        threshold = len(lines) // 5
        for line, positions in line_freq.items():
            if len(positions) > 2:  # Repeated at least 3 times
                first_pos = min(positions)
                if first_pos < threshold:
                    # Check if it looks like page number or boilerplate
                    if re.search(r'page\s+\d+|\d+\s*$|^©|copyright', line, re.I):
                        header_lines = max(header_lines, first_pos + 1)
        
        return header_lines, footer_lines
    
    def parse(self, content: str, skip_header_footer: bool = True) -> List[Section]:
        """Parse markdown content into sections"""
        if skip_header_footer:
            header_lines, footer_lines = self.detect_headers_footers(content)
            lines = content.split('\n')
            if footer_lines > 0:
                content = '\n'.join(lines[header_lines:-footer_lines])
            else:
                content = '\n'.join(lines[header_lines:])
        
        sections = []
        lines = content.split('\n')
        current_section = None
        current_content = []
        line_num = 0
        
        for i, line in enumerate(lines):
            heading_match = self.heading_pattern.match(line)
            if heading_match:
                # Save previous section
                if current_section is not None:
                    current_section.elements = self._parse_elements('\n'.join(current_content), line_num)
                    sections.append(current_section)
                
                # Start new section
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_section = Section(level=level, title=title, elements=[], line_number=i)
                current_content = []
                line_num = i + 1
            else:
                current_content.append(line)
        
        # Don't forget last section
        if current_section is not None:
            current_section.elements = self._parse_elements('\n'.join(current_content), line_num)
            sections.append(current_section)
        elif current_content:
            # Content before first heading
            preamble = Section(level=0, title="__preamble__", elements=[], line_number=0)
            preamble.elements = self._parse_elements('\n'.join(current_content), 0)
            sections.append(preamble)
        
        return sections
    
    def _parse_elements(self, content: str, start_line: int) -> List[Element]:
        """Parse elements within a section"""
        elements = []
        
        # Track positions to avoid double-parsing
        parsed_ranges = []
        
        # Parse code blocks
        for match in self.code_block_pattern.finditer(content):
            lang = match.group(1) or 'text'
            code = match.group(2).strip()
            elements.append(Element('code', {'language': lang, 'code': code}, start_line))
            parsed_ranges.append((match.start(), match.end()))
        
        # Parse tables
        table_lines = []
        in_table = False
        for i, line in enumerate(content.split('\n')):
            if self.table_pattern.match(line):
                table_lines.append(line)
                in_table = True
            elif in_table:
                if table_lines:
                    table_data = self._parse_table('\n'.join(table_lines))
                    elements.append(Element('table', table_data, start_line + i - len(table_lines)))
                table_lines = []
                in_table = False
        
        if table_lines:
            table_data = self._parse_table('\n'.join(table_lines))
            elements.append(Element('table', table_data, start_line))
        
        # Parse LaTeX formulas
        for match in self.latex_pattern.finditer(content):
            formula = match.group(1) or match.group(2)
            normalized = self._normalize_latex(formula)
            elements.append(Element('latex', {'raw': formula, 'normalized': normalized}, start_line))
        
        # Parse images
        for match in self.image_pattern.finditer(content):
            alt_text = match.group(1)
            path = match.group(2)
            image_id = self._get_image_identity(path)
            elements.append(Element('image', {'alt': alt_text, 'path': path, 'id': image_id}, start_line))
        
        # Parse links
        for match in self.link_pattern.finditer(content):
            if match.start() > 0 and content[match.start() - 1] == '!':
                continue  # Skip images
            text = match.group(1)
            url = match.group(2)
            elements.append(Element('link', {'text': text, 'url': url}, start_line))
        
        # Parse remaining text (remove code blocks, tables, etc.)
        text_content = content
        for start, end in sorted(parsed_ranges, reverse=True):
            text_content = text_content[:start] + text_content[end:]
        
        # Remove images, links, latex from text
        text_content = self.image_pattern.sub('', text_content)
        text_content = self.link_pattern.sub('', text_content)
        text_content = self.latex_pattern.sub('', text_content)
        text_content = self.table_pattern.sub('', text_content)
        
        text_content = text_content.strip()
        if text_content:
            elements.append(Element('text', text_content, start_line))
        
        return elements
    
    def _parse_table(self, table_str: str) -> Dict:
        """Parse markdown table into structured data"""
        lines = [l for l in table_str.split('\n') if l.strip()]
        if len(lines) < 2:
            return {'headers': [], 'rows': []}
        
        def parse_row(row_str):
            return [cell.strip() for cell in row_str.split('|')[1:-1]]
        
        headers = parse_row(lines[0])
        # Skip separator line (line 1)
        rows = [parse_row(line) for line in lines[2:]]
        
        return {'headers': headers, 'rows': rows}
    
    def _normalize_latex(self, latex: str) -> str:
        """Normalize LaTeX for comparison"""
        # Remove whitespace variations
        normalized = re.sub(r'\s+', ' ', latex.strip())
        # Normalize common variations
        normalized = normalized.replace('\\left', '').replace('\\right', '')
        normalized = normalized.replace('\\;', ' ').replace('\\,', ' ')
        return normalized
    
    def _get_image_identity(self, path: str) -> str:
        """Extract image identity from path (filename without extension)"""
        # Handle both figures/image.png and ../figures/image.png
        filename = Path(path).name
        return Path(filename).stem


class MarkdownComparator:
    """Compare two markdown documents"""
    
    def __init__(self, figures_dir_golden: Optional[Path] = None, 
                 figures_dir_generated: Optional[Path] = None):
        self.parser = MarkdownParser()
        self.figures_dir_golden = figures_dir_golden
        self.figures_dir_generated = figures_dir_generated
    
    def compare(self, golden_content: str, generated_content: str) -> Tuple[ComparisonMetrics, Dict]:
        """Compare golden and generated markdown, return metrics and detailed diff"""
        golden_sections = self.parser.parse(golden_content)
        generated_sections = self.parser.parse(generated_content)
        
        # Build section maps
        golden_map = {self._section_key(s): s for s in golden_sections}
        generated_map = {self._section_key(s): s for s in generated_sections}
        
        section_similarities = {}
        element_mismatches = {
            'text': 0, 'table': 0, 'code': 0, 'latex': 0, 
            'image': 0, 'link': 0, 'missing': 0, 'extra': 0
        }
        
        detailed_diff = {
            'sections': [],
            'summary': {}
        }
        
        # Compare matching sections
        all_section_keys = set(golden_map.keys()) | set(generated_map.keys())
        
        # Track which sections have actual content
        total_weighted_similarity = 0.0
        total_weight = 0.0
        
        # Track structural differences (sections that became subsections or vice versa)
        structural_issues = []
        
        for section_key in all_section_keys:
            golden_sec = golden_map.get(section_key)
            generated_sec = generated_map.get(section_key)
            
            section_diff = {
                'section_title': section_key,
                'similarity': 0.0,
                'elements': []
            }
            
            if golden_sec and generated_sec:
                # Both sections exist
                golden_has_content = len(golden_sec.elements) > 0
                generated_has_content = len(generated_sec.elements) > 0
                
                if not golden_has_content and not generated_has_content:
                    # Both empty - perfect match
                    similarity = 1.0
                    section_diff['similarity'] = similarity
                    # Don't add misleading note for main titles (H1 with level 1)
                    if golden_sec.level > 1:
                        section_diff['note'] = 'Both sections empty (header only)'
                elif not golden_has_content or not generated_has_content:
                    # One empty, one has content
                    similarity = 0.0
                    section_diff['similarity'] = similarity
                    section_diff['note'] = 'Content mismatch: one section empty'
                else:
                    # Both have content - compare normally
                    similarity, elem_diff, elem_counts = self._compare_sections(golden_sec, generated_sec)
                    section_diff['similarity'] = similarity
                    section_diff['elements'] = elem_diff
                    
                    for elem_type, count in elem_counts.items():
                        element_mismatches[elem_type] = element_mismatches.get(elem_type, 0) + count
                
                section_similarities[section_key] = similarity
                # Weight by element count (sections with more content matter more)
                weight = max(len(golden_sec.elements), len(generated_sec.elements), 1)
                total_weighted_similarity += similarity * weight
                total_weight += weight
            
            elif golden_sec:
                # Section missing in generated
                if len(golden_sec.elements) > 0:
                    # This is a structural difference - content that should be a section isn't
                    # For RAG: This affects chunking boundaries significantly
                    section_similarities[section_key] = 0.0
                    section_diff['similarity'] = 0.0
                    section_diff['status'] = 'missing_in_generated'
                    section_diff['note'] = f'Section has {len(golden_sec.elements)} elements in golden'
                    section_diff['rag_impact'] = 'MEDIUM-HIGH: Missing section affects chunking strategy and retrieval boundaries'
                    element_mismatches['missing'] += len(golden_sec.elements)
                    
                    # Apply penalty weight (0.3 similarity for structural mismatch instead of 0.0)
                    weight = len(golden_sec.elements)
                    total_weighted_similarity += 0.3 * weight  # 30% credit for content existing elsewhere
                    total_weight += weight
                    
                    structural_issues.append({
                        'section': section_key,
                        'issue': 'Section boundary missing - likely merged into parent or became plain text',
                        'impact': 'medium-high'
                    })
                else:
                    # Empty section missing - not critical
                    section_similarities[section_key] = 1.0
                    section_diff['similarity'] = 1.0
                    section_diff['note'] = 'Empty section missing (low impact)'
            
            else:  # generated_sec only
                # Extra section in generated - could be content reorganization
                if len(generated_sec.elements) > 0:
                    section_diff['status'] = 'extra_in_generated'
                    section_diff['note'] = f'Section has {len(generated_sec.elements)} elements - content reorganized from golden'
                    section_diff['rag_impact'] = 'MEDIUM-HIGH: Extra section creates different chunking boundaries'
                    
                    # Apply penalty for structural difference
                    section_similarities[section_key] = 0.3  # 30% credit
                    section_diff['similarity'] = 0.3
                    
                    element_mismatches['extra'] += len(generated_sec.elements)
                    
                    # Add weight with partial credit
                    weight = len(generated_sec.elements)
                    total_weighted_similarity += 0.3 * weight
                    total_weight += weight
                    
                    structural_issues.append({
                        'section': section_key,
                        'issue': 'Extra section boundary - content split from parent or plain text became section',
                        'impact': 'medium-high'
                    })
                else:
                    section_diff['note'] = 'Empty section added (low impact)'
                    section_similarities[section_key] = 0.9  # Minor penalty
                    section_diff['similarity'] = 0.9
            
            detailed_diff['sections'].append(section_diff)
        
        # Calculate overall similarity using weighted average
        if total_weight > 0:
            overall_similarity = total_weighted_similarity / total_weight
        else:
            overall_similarity = 0.0
        
        # Count total elements
        total_golden = sum(len(s.elements) for s in golden_sections)
        total_generated = sum(len(s.elements) for s in generated_sections)
        
        missing_sections = [k for k in golden_map.keys() if k not in generated_map and len(golden_map[k].elements) > 0]
        extra_sections = [k for k in generated_map.keys() if k not in golden_map and len(generated_map[k].elements) > 0]
        
        metrics = ComparisonMetrics(
            overall_similarity=overall_similarity,
            section_similarities=section_similarities,
            element_mismatches=element_mismatches,
            total_elements_golden=total_golden,
            total_elements_generated=total_generated,
            missing_sections=missing_sections,
            extra_sections=extra_sections
        )
        
        detailed_diff['summary'] = asdict(metrics)
        if structural_issues:
            detailed_diff['structural_issues'] = structural_issues
        
        return metrics, detailed_diff
    
    def _section_key(self, section: Section) -> str:
        """Generate a normalized key for section matching"""
        # Normalize title for matching
        return f"H{section.level}:{section.title.lower().strip()}"
    
    def _compare_sections(self, golden: Section, generated: Section) -> Tuple[float, List, Dict]:
        """Compare two sections, return similarity, diff, and mismatch counts"""
        # Group elements by type
        golden_by_type = self._group_elements_by_type(golden.elements)
        generated_by_type = self._group_elements_by_type(generated.elements)
        
        element_diffs = []
        mismatch_counts = {}
        similarities = []
        
        all_types = set(golden_by_type.keys()) | set(generated_by_type.keys())
        
        for elem_type in all_types:
            golden_elems = golden_by_type.get(elem_type, [])
            generated_elems = generated_by_type.get(elem_type, [])
            
            if elem_type == 'text':
                sim, diff = self._compare_text_elements(golden_elems, generated_elems)
            elif elem_type == 'table':
                sim, diff = self._compare_table_elements(golden_elems, generated_elems)
            elif elem_type == 'code':
                sim, diff = self._compare_code_elements(golden_elems, generated_elems)
            elif elem_type == 'latex':
                sim, diff = self._compare_latex_elements(golden_elems, generated_elems)
            elif elem_type == 'image':
                sim, diff = self._compare_image_elements(golden_elems, generated_elems)
            elif elem_type == 'link':
                sim, diff = self._compare_link_elements(golden_elems, generated_elems)
            else:
                sim, diff = 0.0, []
            
            similarities.append(sim)
            element_diffs.extend(diff)
            
            # Count mismatches - only count as mismatch if similarity is below threshold
            if elem_type == 'text':
                mismatches = sum(1 for d in diff if d.get('similarity', 0) < 0.95)
            else:
                mismatches = sum(1 for d in diff if d.get('match', True) == False)
            mismatch_counts[elem_type] = mismatches
        
        section_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        
        return section_similarity, element_diffs, mismatch_counts
    
    def _group_elements_by_type(self, elements: List[Element]) -> Dict[str, List[Element]]:
        """Group elements by their type"""
        grouped = {}
        for elem in elements:
            if elem.type not in grouped:
                grouped[elem.type] = []
            grouped[elem.type].append(elem)
        return grouped
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison - handle formatting variations"""
        # Fix common HTML entity corruption (UTF-8 encoding issues)
        normalized = text.replace('â€"', '—')  # Corrupted em dash
        normalized = normalized.replace('â€™', "'")  # Corrupted right single quote
        normalized = normalized.replace('â€˜', "'")  # Corrupted left single quote
        normalized = normalized.replace('â€œ', '"')  # Corrupted left double quote
        normalized = normalized.replace('â€�', '"')  # Corrupted right double quote
        
        # Replace em dashes with regular hyphens
        normalized = normalized.replace('—', '-')
        # Replace special Unicode characters
        normalized = normalized.replace('\u2014', '-')  # Em dash
        normalized = normalized.replace('\u2013', '-')  # En dash
        
        # Normalize quotes
        normalized = normalized.replace('"', '"').replace('"', '"')
        normalized = normalized.replace(''', "'").replace(''', "'")
        
        # Remove blockquote markers - these are formatting only, not semantic differences
        # Pattern: > at start of line with optional whitespace
        normalized = re.sub(r'^\s*>\s*', '', normalized, flags=re.MULTILINE)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Normalize bullet points (both list markers)
        normalized = re.sub(r'^\s*[-\u2014\u2013]\s+', '- ', normalized, flags=re.MULTILINE)
        
        return normalized.strip()
    
    def _find_text_differences(self, golden_text: str, generated_text: str) -> List[Dict]:
        """Find specific differences between two texts"""
        differences = []
        
        # Check for corrupted HTML entities (encoding issues)
        corruption_patterns = {
            'â€"': '— (em dash)',
            'â€™': "' (apostrophe)",
            'â€˜': "' (apostrophe)",
            'â€œ': '" (quote)',
            'â€�': '" (quote)'
        }
        
        golden_has_corruption = any(pattern in golden_text for pattern in corruption_patterns.keys())
        generated_has_corruption = any(pattern in generated_text for pattern in corruption_patterns.keys())
        
        if golden_has_corruption and not generated_has_corruption:
            corrupted_chars = [char for char in corruption_patterns.keys() if char in golden_text]
            differences.append({
                'type': 'encoding',
                'issue': 'character_encoding_corruption',
                'impact': 'low',
                'note': 'Golden has corrupted UTF-8 characters, generated has proper Unicode',
                'corrupted_sequences': [f'{c} → {corruption_patterns[c]}' for c in corrupted_chars]
            })
        
        # Check for blockquote usage
        golden_has_blockquote = bool(re.search(r'^\s*>\s+', golden_text, re.MULTILINE))
        generated_has_blockquote = bool(re.search(r'^\s*>\s+', generated_text, re.MULTILINE))
        
        if golden_has_blockquote != generated_has_blockquote:
            blockquote_count = len(re.findall(r'^\s*>\s+', 
                                               generated_text if generated_has_blockquote else golden_text, 
                                               re.MULTILINE))
            differences.append({
                'type': 'formatting',
                'issue': 'blockquote_usage',
                'impact': 'low',
                'note': 'Blockquote markers present in one version but not the other',
                'detail': f'{blockquote_count} blockquote line(s) in {"generated" if generated_has_blockquote else "golden"}',
                'rag_impact': 'Low - semantic content identical, embeddings will be nearly the same'
            })
        
        # Check for em dash vs regular dash at start of lines (bullet points)
        golden_lines = golden_text.split('\n')
        generated_lines = generated_text.split('\n')
        
        # Count bullet-style dashes (at start of lines)
        # Check for both corrupted (â€") and proper (—) em dashes
        golden_emdash_bullets = sum(1 for line in golden_lines 
                                     if re.match(r'^\s*[—\u2014â€"]\s+', line))
        generated_dash_bullets = sum(1 for line in generated_lines 
                                      if re.match(r'^\s*-\s+', line))
        generated_emdash_bullets = sum(1 for line in generated_lines 
                                        if re.match(r'^\s*[—\u2014â€"]\s+', line))
        golden_dash_bullets = sum(1 for line in golden_lines 
                                   if re.match(r'^\s*-\s+', line))
        
        if golden_emdash_bullets > 0 and generated_emdash_bullets == 0 and generated_dash_bullets > 0:
            differences.append({
                'type': 'formatting',
                'issue': 'bullet_style',
                'impact': 'low',
                'golden': f'{golden_emdash_bullets} em dash bullet(s) (—)',
                'generated': f'{generated_dash_bullets} regular dash bullet(s) (-)',
                'note': 'List item markers differ',
                'rag_impact': 'Low - bullet style does not affect semantic meaning'
            })
        
        return differences
    
    def _split_text_by_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs for preview"""
        # Split by double newline or significant breaks
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _compare_text_elements(self, golden: List[Element], generated: List[Element]) -> Tuple[float, List]:
        """Compare text elements using semantic similarity"""
        if not golden and not generated:
            return 1.0, []
        if not golden or not generated:
            return 0.0, [{'type': 'text', 'match': False, 'reason': 'missing'}]
        
        # Combine all text
        golden_text = ' '.join(e.content for e in golden)
        generated_text = ' '.join(e.content for e in generated)
        
        # Normalize for comparison
        golden_normalized = self._normalize_text(golden_text)
        generated_normalized = self._normalize_text(generated_text)
        
        # Calculate similarity on normalized text
        similarity = SequenceMatcher(None, golden_normalized.lower(), generated_normalized.lower()).ratio()
        
        # Find specific differences
        text_diffs = self._find_text_differences(golden_text, generated_text)
        
        # Create previews - if there are multiple bullet points, show them in array
        golden_paras = self._split_text_by_paragraphs(golden_text)
        generated_paras = self._split_text_by_paragraphs(generated_text)
        
        # If multiple paragraphs/bullets exist, show first few
        if len(golden_paras) > 1 or len(generated_paras) > 1:
            golden_preview = [p[:150] + '...' if len(p) > 150 else p for p in golden_paras[:3]]
            generated_preview = [p[:150] + '...' if len(p) > 150 else p for p in generated_paras[:3]]
        else:
            golden_preview = golden_text[:200]
            generated_preview = generated_text[:200]
        
        diff = [{
            'type': 'text',
            'match': similarity > 0.95,
            'similarity': similarity,
            'golden_preview': golden_preview,
            'generated_preview': generated_preview,
            'differences': text_diffs if text_diffs else None
        }]
        
        return similarity, diff
    
    def _compare_table_elements(self, golden: List[Element], generated: List[Element]) -> Tuple[float, List]:
        """Compare table elements"""
        if not golden and not generated:
            return 1.0, []
        
        diffs = []
        total_similarity = 0.0
        
        # Match tables by position or content similarity
        matched = set()
        for i, g_elem in enumerate(golden):
            best_match = None
            best_sim = 0.0
            
            for j, gen_elem in enumerate(generated):
                if j in matched:
                    continue
                sim = self._table_similarity(g_elem.content, gen_elem.content)
                if sim > best_sim:
                    best_sim = sim
                    best_match = j
            
            if best_match is not None and best_sim > 0.3:
                matched.add(best_match)
                total_similarity += best_sim
                diffs.append({
                    'type': 'table',
                    'match': best_sim > 0.8,
                    'similarity': best_sim,
                    'golden_shape': f"{len(g_elem.content['rows'])}x{len(g_elem.content['headers'])}",
                    'generated_shape': f"{len(generated[best_match].content['rows'])}x{len(generated[best_match].content['headers'])}"
                })
            else:
                diffs.append({'type': 'table', 'match': False, 'reason': 'no_match_found'})
        
        avg_similarity = total_similarity / len(golden) if golden else 0.0
        return avg_similarity, diffs
    
    def _table_similarity(self, table1: Dict, table2: Dict) -> float:
        """Calculate similarity between two tables"""
        # Compare headers
        h1, h2 = table1['headers'], table2['headers']
        header_sim = SequenceMatcher(None, h1, h2).ratio()
        
        # Compare dimensions
        rows1, rows2 = table1['rows'], table2['rows']
        if len(rows1) != len(rows2):
            dim_sim = 0.5
        else:
            dim_sim = 1.0
        
        # Compare cell content
        cell_matches = 0
        total_cells = 0
        for r1, r2 in zip(rows1, rows2):
            for c1, c2 in zip(r1, r2):
                total_cells += 1
                if c1.strip().lower() == c2.strip().lower():
                    cell_matches += 1
        
        cell_sim = cell_matches / total_cells if total_cells > 0 else 0.0
        
        return (header_sim + dim_sim + cell_sim) / 3.0
    
    def _compare_code_elements(self, golden: List[Element], generated: List[Element]) -> Tuple[float, List]:
        """Compare code blocks with normalization"""
        if not golden and not generated:
            return 1.0, []
        
        diffs = []
        total_sim = 0.0
        
        for i, g_elem in enumerate(golden):
            if i < len(generated):
                gen_elem = generated[i]
                g_code = self._normalize_code(g_elem.content['code'])
                gen_code = self._normalize_code(gen_elem.content['code'])
                
                sim = SequenceMatcher(None, g_code, gen_code).ratio()
                total_sim += sim
                
                diffs.append({
                    'type': 'code',
                    'match': sim > 0.9,
                    'similarity': sim,
                    'language': g_elem.content['language']
                })
            else:
                diffs.append({'type': 'code', 'match': False, 'reason': 'missing_in_generated'})
        
        avg_sim = total_sim / len(golden) if golden else 0.0
        return avg_sim, diffs
    
    def _normalize_code(self, code: str) -> str:
        """Normalize code for comparison"""
        # Remove extra whitespace, normalize line endings
        lines = [line.strip() for line in code.split('\n')]
        return '\n'.join(line for line in lines if line)
    
    def _compare_latex_elements(self, golden: List[Element], generated: List[Element]) -> Tuple[float, List]:
        """Compare LaTeX formulas using normalized form"""
        if not golden and not generated:
            return 1.0, []
        
        diffs = []
        total_sim = 0.0
        
        for i, g_elem in enumerate(golden):
            if i < len(generated):
                gen_elem = generated[i]
                g_norm = g_elem.content['normalized']
                gen_norm = gen_elem.content['normalized']
                
                sim = SequenceMatcher(None, g_norm, gen_norm).ratio()
                total_sim += sim
                
                diffs.append({
                    'type': 'latex',
                    'match': sim > 0.95,
                    'similarity': sim
                })
            else:
                diffs.append({'type': 'latex', 'match': False, 'reason': 'missing'})
        
        avg_sim = total_sim / len(golden) if golden else 0.0
        return avg_sim, diffs
    
    def _compare_image_elements(self, golden: List[Element], generated: List[Element]) -> Tuple[float, List]:
        """Compare images by identity (filename), not placeholder text"""
        if not golden and not generated:
            return 1.0, []
        
        golden_ids = {e.content['id'] for e in golden}
        generated_ids = {e.content['id'] for e in generated}
        
        matched = golden_ids & generated_ids
        missing = golden_ids - generated_ids
        extra = generated_ids - golden_ids
        
        similarity = len(matched) / len(golden_ids) if golden_ids else 0.0
        
        diffs = []
        for img_id in matched:
            diffs.append({'type': 'image', 'match': True, 'image_id': img_id})
        for img_id in missing:
            diffs.append({'type': 'image', 'match': False, 'reason': 'missing', 'image_id': img_id})
        for img_id in extra:
            diffs.append({'type': 'image', 'match': False, 'reason': 'extra', 'image_id': img_id})
        
        return similarity, diffs
    
    def _compare_link_elements(self, golden: List[Element], generated: List[Element]) -> Tuple[float, List]:
        """Compare links by URL and anchor text"""
        if not golden and not generated:
            return 1.0, []
        
        diffs = []
        matched = 0
        
        for g_elem in golden:
            g_url = g_elem.content['url']
            found = False
            for gen_elem in generated:
                if gen_elem.content['url'] == g_url:
                    found = True
                    matched += 1
                    text_match = g_elem.content['text'] == gen_elem.content['text']
                    diffs.append({
                        'type': 'link',
                        'match': text_match,
                        'url': g_url,
                        'text_match': text_match
                    })
                    break
            
            if not found:
                diffs.append({'type': 'link', 'match': False, 'reason': 'url_missing', 'url': g_url})
        
        similarity = matched / len(golden) if golden else 0.0
        return similarity, diffs


def compare_documents(golden_dir: Path, generated_dir: Path, markdown_filename: str, 
                      output_file: Optional[Path] = None) -> Dict:
    """
    Compare a single markdown document.
    
    Args:
        golden_dir: Path to groundtruthdata directory
        generated_dir: Path to llamaparsedata directory
        markdown_filename: Name of the markdown file to compare (e.g., 'document.md')
        output_file: Optional path to save JSON results
    
    Returns:
        Comparison results as dictionary
    """
    # Extract document_id from the markdown filename (without extension)
    document_id = Path(markdown_filename).stem
    
    # Find the markdown file in both directories
    golden_doc = golden_dir / markdown_filename
    generated_doc = generated_dir / markdown_filename
    
    # Try to find figures directory (assuming it's in the same parent directory)
    golden_figures = golden_dir / "figures"
    generated_figures = generated_dir / "figures"
    
    if not golden_doc.exists():
        raise FileNotFoundError(f"Golden document not found: {golden_doc}")
    if not generated_doc.exists():
        raise FileNotFoundError(f"Generated document not found: {generated_doc}")
    
    with open(golden_doc, 'r', encoding='utf-8') as f:
        golden_content = f.read()
    
    with open(generated_doc, 'r', encoding='utf-8') as f:
        generated_content = f.read()
    
    comparator = MarkdownComparator(
        figures_dir_golden=golden_figures if golden_figures.exists() else None,
        figures_dir_generated=generated_figures if generated_figures.exists() else None
    )
    
    metrics, detailed_diff = comparator.compare(golden_content, generated_content)
    
    results = {
        'markdown_file': markdown_filename,
        'document_id': document_id,
        'metrics': asdict(metrics),
        'detailed_diff': detailed_diff
    }
    
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {output_file}")
    
    return results


def print_summary(results: Dict):
    """Print a human-readable summary of comparison results"""
    metrics = results['metrics']
    
    print(f"\n{'='*60}")
    print(f"Comparison Results for: {results['markdown_file']}")
    print(f"{'='*60}")
    print(f"\nOverall Similarity: {metrics['overall_similarity']:.2%}")
    print(f"\nElement Counts:")
    print(f"  Golden:    {metrics['total_elements_golden']}")
    print(f"  Generated: {metrics['total_elements_generated']}")
    
    print(f"\nElement Mismatches:")
    for elem_type, count in metrics['element_mismatches'].items():
        if count > 0:
            print(f"  {elem_type}: {count}")
    
    if metrics['missing_sections']:
        print(f"\nMissing Sections ({len(metrics['missing_sections'])}):")
        for sec in metrics['missing_sections'][:5]:
            print(f"  - {sec}")
        if len(metrics['missing_sections']) > 5:
            print(f"  ... and {len(metrics['missing_sections']) - 5} more")
    
    if metrics['extra_sections']:
        print(f"\nExtra Sections ({len(metrics['extra_sections'])}):")
        for sec in metrics['extra_sections'][:5]:
            print(f"  - {sec}")
        if len(metrics['extra_sections']) > 5:
            print(f"  ... and {len(metrics['extra_sections']) - 5} more")
    
    print(f"\nTop 5 Section Similarities:")
    sorted_sections = sorted(metrics['section_similarities'].items(), 
                            key=lambda x: x[1], reverse=True)
    for sec, sim in sorted_sections[:5]:
        print(f"  {sec}: {sim:.2%}")
    
    print(f"{'='*60}\n")


PARSER_NAME = "pdfparsingpipelinedata"
DATA_DIR = Path("data")
GOLDEN_DIR = DATA_DIR / "groundtruthdata"
GENERATED_DIR = DATA_DIR / PARSER_NAME
OUTPUT_DIR = DATA_DIR / "comparison_reports" / PARSER_NAME

def main():
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    golden_md_files = list(GOLDEN_DIR.glob("*.md"))
    if not golden_md_files:
        print(f"No markdown files found in {GOLDEN_DIR}")
        return 1

    generated_md_files = list(GENERATED_DIR.glob("*.md"))
    if not generated_md_files:
        print(f"No markdown files found in {GENERATED_DIR}")
        return 1

    # Build lookup for generated files by stem
    generated_by_stem = {
        md.stem: md for md in generated_md_files
    }

    for golden_md in golden_md_files:
        file_stem = golden_md.stem

        if file_stem not in generated_by_stem:
            print(f"Skipping {golden_md.name} — no matching generated file")
            continue

        output_file = OUTPUT_DIR / f"{file_stem}_comparison.json"

        try:
            results = compare_documents(
                GOLDEN_DIR,        # golden folder
                GENERATED_DIR,     # generated folder
                golden_md.name,    # filename
                output_file
            )
            print_summary(results)

        except Exception as e:
            print(f"Error comparing {golden_md.name}: {e}")

    print("Comparison done.")
    return 0


if __name__ == '__main__':
    exit(main())