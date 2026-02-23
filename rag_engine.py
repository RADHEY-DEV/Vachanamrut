from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log, sqrt
from typing import List, Sequence
import re

try:
    from pypdf import PdfReader
except ModuleNotFoundError:
    PdfReader = None


@dataclass
class RetrievalResult:
    chunk: str
    score: float


class PDFRAG:
    def __init__(self, chunk_size: int = 900, overlap: int = 120) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: list[str] = []
        self.doc_vectors: list[dict[str, float]] = []
        self.idf: dict[str, float] = {}

    def ingest_pdfs(self, pdf_paths: Sequence[str]) -> int:
        self._ensure_pdf_dependency()

        all_text: list[str] = []
        for path in pdf_paths:
            reader = PdfReader(path)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                cleaned = re.sub(r"\s+", " ", page_text).strip()
                if cleaned:
                    all_text.append(cleaned)

        corpus = "\n".join(all_text)
        self.chunks = self._chunk_text(corpus)
        if not self.chunks:
            raise ValueError("No readable text found in uploaded PDF(s).")

        self._build_index()
        return len(self.chunks)

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievalResult]:
        if not self.doc_vectors:
            raise ValueError("Knowledge base is empty. Please upload and process PDF files first.")

        query_vec = self._tfidf_vector(self._tokenize(question), self.idf)
        if not query_vec:
            return []

        scored: list[RetrievalResult] = []
        for idx, doc_vec in enumerate(self.doc_vectors):
            score = self._cosine(query_vec, doc_vec)
            if score > 0:
                scored.append(RetrievalResult(chunk=self.chunks[idx], score=score))

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def answer_without_llm(self, question: str, retrieved: Sequence[RetrievalResult], max_sentences: int = 4) -> str:
        if not retrieved:
            return (
                "I could not find relevant passages in the uploaded Vachanamrut PDF. "
                "Try rephrasing your question or upload clearer scans/text PDFs."
            )

        candidate_text = " ".join(item.chunk for item in retrieved)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", candidate_text) if s.strip()]
        if not sentences:
            return "I found relevant chunks, but could not split them into readable sentences."

        q_tokens = self._tokenize(question)
        sentence_scores: list[tuple[int, float]] = []
        for idx, sentence in enumerate(sentences):
            s_tokens = self._tokenize(sentence)
            overlap = len(set(q_tokens) & set(s_tokens))
            norm = max(1, len(set(s_tokens)))
            sentence_scores.append((idx, overlap / norm))

        sentence_scores.sort(key=lambda item: item[1], reverse=True)
        chosen_indices = [idx for idx, score in sentence_scores[:max_sentences] if score > 0]
        if not chosen_indices:
            chosen_indices = list(range(min(max_sentences, len(sentences))))

        return " ".join(sentences[idx] for idx in chosen_indices)

    def _build_index(self) -> None:
        tokenized_docs = [self._tokenize(chunk) for chunk in self.chunks]
        df: Counter[str] = Counter()
        for tokens in tokenized_docs:
            df.update(set(tokens))

        n_docs = len(tokenized_docs)
        self.idf = {
            term: log((1 + n_docs) / (1 + freq)) + 1.0
            for term, freq in df.items()
        }

        self.doc_vectors = [self._tfidf_vector(tokens, self.idf) for tokens in tokenized_docs]

    def _tfidf_vector(self, tokens: Sequence[str], idf: dict[str, float]) -> dict[str, float]:
        if not tokens:
            return {}

        tf = Counter(tokens)
        total = len(tokens)
        vector: dict[str, float] = {}
        for term, freq in tf.items():
            if term in idf:
                vector[term] = (freq / total) * idf[term]
        return vector

    def _cosine(self, vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        if not vec_a or not vec_b:
            return 0.0

        common_terms = set(vec_a).intersection(vec_b)
        numerator = sum(vec_a[t] * vec_b[t] for t in common_terms)
        norm_a = sqrt(sum(v * v for v in vec_a.values()))
        norm_b = sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return numerator / (norm_a * norm_b)

    def _tokenize(self, text: str) -> list[str]:
        return [
            token
            for token in re.findall(r"[A-Za-z]+", text.lower())
            if len(token) > 2
        ]

    def _chunk_text(self, text: str) -> list[str]:
        if not text:
            return []

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            snippet = text[start:end].strip()
            if snippet:
                chunks.append(snippet)
            if end == len(text):
                break
            start = max(0, end - self.overlap)
        return chunks

    def _ensure_pdf_dependency(self) -> None:
        if PdfReader is None:
            raise ModuleNotFoundError(
                "Missing required package: pypdf. Install dependencies with `pip install -r requirements.txt`."
            )
