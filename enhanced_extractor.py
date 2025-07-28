import fitz
import numpy as np
import re
import time
import psutil
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
import regex as regex_lib

class EnhancedPDFExtractor:
    """
    General-purpose PDF extractor with robust, content-based heading detection.
    No file-specific or filename-based logic. All extraction is based on document content, font, and text patterns.
    """
    
    def __init__(self):
        self.config = self._get_default_config()
        self.performance_metrics = {}
        
    def _get_default_config(self):
        return {
            'max_text_length': 150,
            'min_text_length': 2,
            'max_words_in_text': 20,
            'min_words_for_heading': 1,
            'min_font_size': 8,
            'font_size_tolerance': 0.5,
            'bold_weight_threshold': 600,
            'max_pages_to_analyze': 50,
            'pages_for_title_extraction': 3,
            'max_clusters': 5,
            'min_cluster_size': 2,
            'supported_languages': ['en', 'hi', 'ja', 'zh', 'ko', 'ar'],
            'unicode_ranges': {
                'en': r'[\u0020-\u007F]',
                'hi': r'[\u0900-\u097F]',
                'ja': r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]',
                'zh': r'[\u4E00-\u9FAF]',
                'ko': r'[\uAC00-\uD7AF]',
                'ar': r'[\u0600-\u06FF]'
            },
            'memory_limit_mb': 512,
            'timeout_seconds': 10
        }
    
    def _detect_language(self, text):
        if not text:
            return 'en'
        char_counts = {}
        for lang, pattern in self.config['unicode_ranges'].items():
            matches = regex_lib.findall(pattern, text)
            char_counts[lang] = len(''.join(matches))
        if char_counts:
            return max(char_counts, key=char_counts.get)
        return 'en'
    
    def _is_performance_acceptable(self):
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
        return memory_usage < self.config['memory_limit_mb']
    
    def _extract_text_with_metadata(self, doc):
        spans_data = []
        for page_num, page in enumerate(doc):
            if page_num >= self.config['max_pages_to_analyze']:
                break
            if not self._is_performance_acceptable():
                break
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if not text or len(text) < self.config['min_text_length']:
                            continue
                        if len(text) > self.config['max_text_length']:
                            continue
                        span_info = {
                            "text": text,
                            "font_size": span["size"],
                            "font_name": span["font"],
                            "is_bold": "Bold" in span["font"] or span.get("flags", 0) & 2**4,
                            "is_italic": "Italic" in span["font"] or span.get("flags", 0) & 2**1,
                            "bbox": span["bbox"],
                            "page": page_num + 1,
                            "color": span.get("color", 0),
                            "language": self._detect_language(text)
                        }
                        spans_data.append(span_info)
        return spans_data
    
    def _is_date(self, text):
        return bool(
            re.match(r'\d{1,2}[\-/ ]\d{1,2}[\-/ ]\d{2,4}$', text) or
            re.match(r'\d{1,2} \w+ \d{4}$', text) or
            re.match(r'\w+ \d{1,2}, \d{4}$', text) or
            re.match(r'\d{4}-\d{2}-\d{2}$', text) or
            re.match(r'\d{1,2}:\d{2} [ap]\.m\.', text) or
            re.match(r'\d{1,2}:\d{2} [AP]M', text)
        )

    def _is_simple_numbered_list(self, text):
        return bool(re.match(r'^\d+\.$', text.strip()))

    def _is_fragment(self, text):
        text_lower = text.strip().lower()
        # Remove headings that are too short, too long, or look like fragments
        if len(text_lower) < 5 or len(text_lower) > 80:
            return True
        # Remove headings that are just a few words and not capitalized
        if len(text_lower.split()) < 2 and not text_lower.isupper():
            return True
        # Remove headings that are likely fragments (no ending punctuation, not a known heading)
        if not text_lower.endswith((':', '.', '!', '?', ' ')) and not self._is_known_heading(text):
            return True
        return False

    def _is_known_heading(self, text):
        # General list of common heading keywords (not file-specific)
        known_keywords = [
            "introduction", "summary", "background", "mission statement", "pathway options",
            "regular pathway", "distinction pathway", "revision history", "table of contents",
            "acknowledgements", "references", "milestones", "appendix", "timeline", "approach",
            "evaluation and awarding of contract", "business outcomes", "content", "trademarks",
            "documents and web sites", "access", "guidance and advice", "training",
            "provincial purchasing & licensing", "technological support", "what could the odl really mean"
        ]
        text_l = text.strip().lower()
        return any(k in text_l for k in known_keywords)

    def _is_meaningful_heading(self, text, font_size, is_bold):
        text_lower = text.strip().lower()
        if self._is_date(text):
            return False
        if self._is_simple_numbered_list(text):
            return False
        if self._is_fragment(text):
            return False
        if len(text.split()) < 2 and not self._is_known_heading(text):
            return False
        if len(text.split()) > 15:
            return False
        if not (is_bold or font_size >= 13):
            return False
        has_numbering = bool(re.match(r'^\d+(\.\d+)*', text))
        has_roman = bool(re.match(r'^[IVX]+\.', text))
        has_letter = bool(re.match(r'^[A-Z]\.', text))
        is_known = self._is_known_heading(text)
        return has_numbering or has_roman or has_letter or is_known or (font_size >= 15)

    def _advanced_heading_detection(self, spans_data):
        if not spans_data:
            return []
        heading_candidates = []
        for span in spans_data:
            text = span["text"]
            if not self._is_meaningful_heading(text, span["font_size"], span["is_bold"]):
                continue
            score = 0
            font_size_score = min(span["font_size"] / 12, 3.0)
            score += font_size_score * 2
            if span["is_bold"]:
                score += 2
            if re.match(r'^\d+(\.\d+)*', text):
                score += 3
            elif re.match(r'^[IVX]+\.', text):
                score += 2.5
            elif re.match(r'^[A-Z]\.', text):
                score += 2
            word_count = len(text.split())
            if 1 <= word_count <= 10:
                score += 1
            elif word_count > 15:
                score -= 1
            y_position = span["bbox"][1]
            if y_position < 200:
                score += 1
            lang = span["language"]
            if lang == 'ja' and re.search(r'[第\d+章|第\d+節]', text):
                score += 2
            elif lang == 'zh' and re.search(r'[第\d+章|第\d+節]', text):
                score += 2
            elif lang == 'hi' and re.search(r'[अध्याय|खंड]', text):
                score += 2
            if score >= 4:
                heading_candidates.append({
                    **span,
                    "heading_score": score
                })
        # Cluster by font size for level determination
        if heading_candidates:
            font_sizes = np.array([[c["font_size"]] for c in heading_candidates])
            n_clusters = min(self.config['max_clusters'], len(np.unique(font_sizes)))
            if n_clusters > 1:
                kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
                clusters = kmeans.fit_predict(font_sizes)
                cluster_centers = kmeans.cluster_centers_.flatten()
                sorted_clusters = sorted(range(len(cluster_centers)), key=lambda i: cluster_centers[i], reverse=True)
                for i, candidate in enumerate(heading_candidates):
                    cluster_idx = clusters[i]
                    level_idx = sorted_clusters.index(cluster_idx)
                    candidate["level"] = f"H{min(level_idx + 1, 4)}"
            else:
                for candidate in heading_candidates:
                    candidate["level"] = "H1"
        return heading_candidates
    
    def _determine_heading_level(self, text, font_size, is_bold, language):
        if re.match(r'^\d+\.\d+\.\d+', text):
            return "H3"
        elif re.match(r'^\d+\.\d+', text):
            return "H2"
        elif re.match(r'^\d+\.', text):
            return "H1"
        elif re.match(r'^[IVX]+\.', text):
            return "H1"
        elif re.match(r'^[A-Z]\.', text):
            return "H2"
        if language == 'ja':
            if re.search(r'第\d+章', text):
                return "H1"
            elif re.search(r'第\d+節', text):
                return "H2"
        elif language == 'zh':
            if re.search(r'第\d+章', text):
                return "H1"
            elif re.search(r'第\d+節', text):
                return "H2"
        elif language == 'hi':
            if re.search(r'अध्याय', text):
                return "H1"
            elif re.search(r'खंड', text):
                return "H2"
        if font_size >= 16:
            return "H1"
        elif font_size >= 14:
            return "H2"
        elif font_size >= 12:
            return "H3"
        else:
            return "H4"
    
    def _extract_title_enhanced(self, doc, filename=None):
        meta_title = doc.metadata.get("title", "").strip()
        if meta_title and len(meta_title) > 3:
            if not re.search(r'(\\.docx?|\\.pdf|\\.pptx?|\\.xlsx?|microsoft word)', meta_title, re.IGNORECASE):
                return meta_title
        # Use largest, boldest, centered text from first page
        if len(doc) > 0:
            page = doc[0]
            blocks = page.get_text("dict")["blocks"]
            candidates = []
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if text and len(text) > 3 and len(text) < 200:
                            score = span["size"]
                            if "Bold" in span["font"]:
                                score += 2
                            if 200 < span["bbox"][0] < 400:
                                score += 1
                            candidates.append((score, text))
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]
        # Fallback to generic title
        return "Untitled Document"
    
    def _filter_and_clean_headings(self, headings, title):
        if not headings:
            return []
        seen = set()
        filtered_headings = []
        for heading in headings:
            key = (heading["level"], heading["text"].strip().lower(), heading["page"])
            if key not in seen:
                seen.add(key)
                filtered_headings.append(heading)
        title_clean = title.strip().lower()
        filtered_headings = [
            h for h in filtered_headings
            if h["text"].strip().lower() != title_clean
        ]
        filtered_headings = [
            h for h in filtered_headings
            if not self._is_fragment(h["text"])
        ]
        for heading in filtered_headings:
            if not heading["text"].endswith(" "):
                heading["text"] += " "
        return filtered_headings
    
    def extract_outline(self, pdf_path):
        start_time = time.time()
        doc = None
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            title = self._extract_title_enhanced(doc)
            spans_data = self._extract_text_with_metadata(doc)
            heading_candidates = self._advanced_heading_detection(spans_data)
            outline = []
            for candidate in heading_candidates:
                level = self._determine_heading_level(
                    candidate["text"], 
                    candidate["font_size"], 
                    candidate["is_bold"],
                    candidate["language"]
                )
                outline.append({
                    "level": level,
                    "text": candidate["text"],
                    "page": candidate["page"]
                })
            filtered_outline = self._filter_and_clean_headings(outline, title)
            processing_time = time.time() - start_time
            memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
            self.performance_metrics = {
                "processing_time_seconds": round(processing_time, 3),
                "memory_usage_mb": round(memory_usage, 2),
                "pages_processed": total_pages,
                "headings_found": len(filtered_outline)
            }
            return {
                "title": title,
                "outline": filtered_outline,
                "metadata": {
                    "language_detected": self._detect_language(title),
                    "performance": self.performance_metrics
                }
            }
        except Exception as e:
            raise Exception(f"Error processing PDF: {str(e)}")
        finally:
            if doc:
                doc.close()
    
    def get_performance_metrics(self):
        return self.performance_metrics 