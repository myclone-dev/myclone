import logging
import re
from collections import Counter
from typing import Any, Dict

import nltk
import numpy as np
from textblob import TextBlob

logger = logging.getLogger(__name__)

try:
    nltk.download("punkt", quiet=True)
    nltk.download("stopwords", quiet=True)
    nltk.download("averaged_perceptron_tagger", quiet=True)
except:
    pass


class PatternExtractor:
    def __init__(self):
        self.stop_words = set(nltk.corpus.stopwords.words("english")) if nltk else set()

    async def extract_all_patterns(self, text: str) -> Dict[str, Any]:
        patterns = {
            "communication_style": await self.extract_communication_style(text),
            "thinking_patterns": await self.extract_thinking_patterns(text),
            "response_structure": await self.extract_response_structure(text),
            "emotional_tone": await self.extract_emotional_tone(text),
            "vocabulary": await self.extract_vocabulary_patterns(text),
        }
        return patterns

    async def extract_communication_style(self, text: str) -> Dict[str, Any]:
        sentences = nltk.sent_tokenize(text) if nltk else text.split(".")
        words = nltk.word_tokenize(text) if nltk else text.split()

        sentence_lengths = (
            [len(nltk.word_tokenize(s)) for s in sentences]
            if nltk
            else [len(s.split()) for s in sentences]
        )
        avg_sentence_length = np.mean(sentence_lengths) if sentence_lengths else 0

        unique_words = set(w.lower() for w in words if w.isalpha())
        unique_ratio = len(unique_words) / len(words) if words else 0

        complex_words = [w for w in unique_words if len(w) > 8]
        complexity_score = len(complex_words) / len(unique_words) if unique_words else 0

        formality_indicators = ["therefore", "however", "furthermore", "moreover", "consequently"]
        informal_indicators = ["gonna", "wanna", "yeah", "ok", "okay", "stuff", "thing"]

        formality_count = sum(1 for w in words if w.lower() in formality_indicators)
        informality_count = sum(1 for w in words if w.lower() in informal_indicators)

        formality_score = (formality_count - informality_count) / len(words) if words else 0
        formality_score = max(0, min(1, (formality_score + 0.1) * 5))

        ngrams = self.extract_ngrams(text, 3)
        common_phrases = [" ".join(gram) for gram, count in ngrams.most_common(10)]

        transition_words = [
            "however",
            "therefore",
            "moreover",
            "furthermore",
            "additionally",
            "consequently",
            "nevertheless",
            "meanwhile",
            "subsequently",
        ]
        used_transitions = [w for w in words if w.lower() in transition_words]

        filler_words = ["um", "uh", "like", "you know", "actually", "basically", "literally"]
        used_fillers = [w for w in words if w.lower() in filler_words]

        return {
            "avg_sentence_length": float(avg_sentence_length),
            "vocabulary_complexity": float(complexity_score),
            "unique_words_ratio": float(unique_ratio),
            "formality_score": float(formality_score),
            "common_phrases": common_phrases[:5],
            "transition_words": list(set(used_transitions))[:5],
            "filler_words": list(set(used_fillers))[:5],
        }

    async def extract_thinking_patterns(self, text: str) -> Dict[str, Any]:
        words = text.lower().split()

        data_keywords = [
            "data",
            "statistics",
            "research",
            "study",
            "evidence",
            "analysis",
            "metrics",
        ]
        narrative_keywords = ["story", "experience", "felt", "believe", "think", "imagine"]

        data_count = sum(1 for w in words if w in data_keywords)
        narrative_count = sum(1 for w in words if w in narrative_keywords)

        if data_count > narrative_count * 1.5:
            evidence_usage = "data-driven"
        elif narrative_count > data_count * 1.5:
            evidence_usage = "narrative"
        else:
            evidence_usage = "mixed"

        abstract_keywords = ["concept", "theory", "principle", "framework", "abstract", "model"]
        concrete_keywords = ["specific", "example", "instance", "case", "practical", "real"]

        abstract_count = sum(1 for w in words if w in abstract_keywords)
        concrete_count = sum(1 for w in words if w in concrete_keywords)

        if abstract_count > concrete_count * 1.5:
            abstraction_level = "conceptual"
        elif concrete_count > abstract_count * 1.5:
            abstraction_level = "concrete"
        else:
            abstraction_level = "balanced"

        causal_keywords = ["because", "therefore", "thus", "hence", "consequently", "so"]
        causal_count = sum(1 for w in words if w in causal_keywords)

        if causal_count > len(words) * 0.02:
            reasoning_style = "deductive"
        elif "for example" in text.lower() or "such as" in text.lower():
            reasoning_style = "inductive"
        else:
            reasoning_style = "mixed"

        frameworks = []
        framework_patterns = [
            r"framework",
            r"model",
            r"methodology",
            r"approach",
            r"system",
            r"SWOT",
            r"PEST",
            r"Porter",
            r"Agile",
            r"Lean",
        ]
        for pattern in framework_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                frameworks.append(pattern)

        return {
            "approach": "top-down" if abstract_count > concrete_count else "bottom-up",
            "evidence_usage": evidence_usage,
            "abstraction_level": abstraction_level,
            "framework_usage": frameworks[:5],
            "reasoning_style": reasoning_style,
        }

    async def extract_response_structure(self, text: str) -> Dict[str, Any]:
        sentences = nltk.sent_tokenize(text) if nltk else text.split(".")

        opening_patterns = []
        if sentences:
            first_words = []
            for s in sentences[:5]:
                words = s.strip().split()
                if words:
                    first_words.append(words[0])
            opening_patterns = list(set(first_words))

        example_keywords = ["for example", "for instance", "such as", "like", "e.g."]
        example_count = sum(1 for keyword in example_keywords if keyword in text.lower())
        example_frequency = example_count / len(sentences) if sentences else 0

        # question_patterns = ["how", "what", "why", "when", "where", "who"]
        question_handling = "direct"

        conclusion_keywords = ["in conclusion", "to summarize", "in summary", "therefore", "thus"]
        has_conclusion = any(keyword in text.lower() for keyword in conclusion_keywords)

        return {
            "typical_opening": opening_patterns[:3],
            "explanation_style": "structured" if len(sentences) > 5 else "concise",
            "example_usage_frequency": float(example_frequency),
            "conclusion_style": "formal" if has_conclusion else "informal",
            "question_handling": question_handling,
        }

    async def extract_emotional_tone(self, text: str) -> Dict[str, Any]:
        try:
            blob = TextBlob(text)
            sentiment = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
        except:
            sentiment = 0
            subjectivity = 0.5

        empathy_markers = ["understand", "feel", "appreciate", "empathize", "relate", "support"]
        found_empathy = [m for m in empathy_markers if m in text.lower()]

        humor_indicators = ["haha", "lol", "funny", "joke", "humor", "😄", "😂"]
        humor_count = sum(1 for h in humor_indicators if h in text.lower())
        sentences = text.split(".")
        humor_frequency = humor_count / len(sentences) if sentences else 0

        return {
            "sentiment_average": float(sentiment),
            "emotional_range": float(subjectivity),
            "empathy_markers": found_empathy[:5],
            "humor_frequency": float(humor_frequency),
            "tone_consistency": 0.8,
        }

    async def extract_vocabulary_patterns(self, text: str) -> Dict[str, Any]:
        words = nltk.word_tokenize(text.lower()) if nltk else text.lower().split()
        words = [w for w in words if w.isalpha() and w not in self.stop_words]

        word_freq = Counter(words)
        signature_words = [word for word, count in word_freq.most_common(20) if count > 2]

        if nltk:
            pos_tags = nltk.pos_tag(words)
            adjectives = [word for word, pos in pos_tags if pos.startswith("JJ")]
            adverbs = [word for word, pos in pos_tags if pos.startswith("RB")]
        else:
            adjectives = []
            adverbs = []

        return {
            "signature_words": signature_words[:10],
            "preferred_adjectives": list(set(adjectives))[:10],
            "preferred_adverbs": list(set(adverbs))[:10],
            "vocabulary_size": len(set(words)),
        }

    def extract_ngrams(self, text: str, n: int = 3) -> Counter:
        words = text.lower().split()
        words = [w for w in words if w.isalpha() and w not in self.stop_words]
        ngrams = zip(*[words[i:] for i in range(n)])
        return Counter(ngrams)
