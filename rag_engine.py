from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence
import re

import numpy as np
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class RetrievalResult:
    chunk: str
    score: float


class PDFRAG:
    def __init__(self, chunk_size: int = 900, overlap: int = 120) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.vectorizer: TfidfVectorizer | None = None
        self.chunk_matrix = None
        self.chunks: list[str] = []

    def ingest_pdfs(self, pdf_paths: Sequence[str]) -> int:
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

        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=25000)
        self.chunk_matrix = self.vectorizer.fit_transform(self.chunks)
        return len(self.chunks)

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievalResult]:
        if self.vectorizer is None or self.chunk_matrix is None:
            raise ValueError("Knowledge base is empty. Please upload and process PDF files first.")

        query_vec = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vec, self.chunk_matrix).flatten()
        if len(scores) == 0:
            return []

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            RetrievalResult(chunk=self.chunks[i], score=float(scores[i]))
            for i in top_indices
            if float(scores[i]) > 0
        ]

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

        sent_vectorizer = TfidfVectorizer(stop_words="english")
        sent_matrix = sent_vectorizer.fit_transform(sentences)
        qv = sent_vectorizer.transform([question])
        sent_scores = cosine_similarity(qv, sent_matrix).flatten()

        ranked = np.argsort(sent_scores)[::-1][:max_sentences]
        chosen = [sentences[idx] for idx in ranked if sent_scores[idx] > 0]
        if not chosen:
            chosen = sentences[:max_sentences]

        return " ".join(chosen)

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
