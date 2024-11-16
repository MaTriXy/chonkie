from typing import Any, List, Union, Generator, Tuple

from .base import BaseChunker, Chunk


class TokenChunker(BaseChunker):
    def __init__(
        self,
        tokenizer: Union[str, Any] = "gpt2",
        chunk_size: int = 512,
        chunk_overlap: Union[int, float] = 128,
    ):
        """Initialize the TokenChunker with configuration parameters.

        Args:
            tokenizer: The tokenizer instance to use for encoding/decoding
            chunk_size: Maximum number of tokens per chunk
            chunk_overlap: Number of tokens to overlap between chunks

        Raises:
            ValueError: If chunk_size <= 0 or chunk_overlap >= chunk_size
        """
        super().__init__(tokenizer)
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if isinstance(chunk_overlap, int) and chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if isinstance(chunk_overlap, float) and chunk_overlap >= 1:
            raise ValueError("chunk_overlap must be less than 1")

        self.chunk_size = chunk_size
        self.chunk_overlap = (
            chunk_overlap
            if isinstance(chunk_overlap, int)
            else int(chunk_overlap * chunk_size)
        )

    def chunk(self, text: str) -> List[Chunk]:
        """Split text into overlapping chunks of specified token size.

        Args:
            text: Input text to be chunked

        Returns:
            List of Chunk objects containing the chunked text and metadata
        """
        if not text.strip():
            return []

        # Encode full text
        text_tokens = self._encode(text)
        decoded_text = self._decode(text_tokens)
        chunks = []

        # Calculate chunk positions
        start_indices = range(0, len(text_tokens), self.chunk_size - self.chunk_overlap)

        current_char_pos = 0
        for start_idx in start_indices:
            # Get token indices for this chunk
            end_idx = min(start_idx + self.chunk_size, len(text_tokens))

            # Extract and decode tokens for this chunk
            chunk_tokens = text_tokens[start_idx:end_idx]
            chunk_text = self._decode(chunk_tokens)

            # Calculate character-based indices
            chunk_start_char = decoded_text.find(chunk_text, current_char_pos)
            chunk_end_char = chunk_start_char + len(chunk_text)
            current_char_pos = chunk_end_char

            chunks.append(
                Chunk(
                    text=chunk_text,
                    start_index=chunk_start_char,
                    end_index=chunk_end_char,
                    token_count=len(chunk_tokens),
                )
            )

            # Break if we've reached the end of the text
            if end_idx == len(text_tokens):
                break

        return chunks
    
    def _chunk_generator(self, tokens: List[int]) -> Generator[Tuple[List[int], int, int], None, None]:
        stride = self.chunk_size - self.chunk_overlap
        for start in range(0, len(tokens), stride):
            end = min(start + self.chunk_size, len(tokens))
            yield tokens[start:end], start, end
            if end == len(tokens):
                break

    def _process_batch(self, chunks: List[Tuple[List[int], int, int]]) -> List[Chunk]:
        token_lists = [tokens for tokens, _, _ in chunks]
        texts = self._decode_batch(token_lists)
        
        return [
            Chunk(text=text, start_index=start, end_index=end, token_count=end-start)
            for text, (_, start, end) in zip(texts, chunks)
        ]
    
    def _process_text_batch(self, texts: List[str]) -> List[List[Chunk]]:
        tokens_list = self._encode_batch(texts)
        result = []
        
        for tokens in tokens_list:
            if not tokens:
                result.append([])
                continue

            chunks = []
            chunk_batch = []
            
            for chunk_data in self._chunk_generator(tokens):
                chunk_batch.append(chunk_data)
            
            chunks.extend(self._process_batch(chunk_batch))
            result.append(chunks)
            
        return result
    
    def chunk_batch(self, texts: List[str], batch_size: int = None) -> List[List[Chunk]]:
        """Split a batch of texts into their respective chunks.

        Args:
            texts: List of input texts to be chunked

        Returns:
            List of lists of Chunk objects containing the chunked text and metadata
        """
        if batch_size is not None:
            chunks = []
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:min(i+batch_size, len(texts))]
                chunks.extend(self._process_text_batch(batch_texts))
            return chunks
        else:
            return self._process_text_batch(texts)
    
    def __repr__(self) -> str:
        return (
            f"TokenChunker(chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap})"
        )
