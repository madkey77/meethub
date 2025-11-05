#!/usr/bin/env python3
"""Example usage of chunking strategies.

This script demonstrates how to use MeetingChunker and DocumentChunker
for different types of content. Run this after installing dependencies.
"""

# Example 1: MeetingChunker with Deepgram response
print("=" * 80)
print("Example 1: MeetingChunker with Deepgram utterances")
print("=" * 80)

from src.services.chunking import MeetingChunker

# Sample Deepgram response structure
deepgram_response = {
    "results": {
        "utterances": [
            {
                "speaker": 0,
                "start": 0.5,
                "end": 5.2,
                "transcript": "Hello everyone, let's start the meeting. Today we'll discuss the quarterly results."
            },
            {
                "speaker": 1,
                "start": 5.8,
                "end": 12.3,
                "transcript": "Thanks for joining. I've prepared a detailed presentation covering our achievements."
            },
            {
                "speaker": 0,
                "start": 13.0,
                "end": 18.5,
                "transcript": "Great! Before we begin, let's do a quick round of introductions for new team members."
            },
            {
                "speaker": 2,
                "start": 19.0,
                "end": 24.2,
                "transcript": "Hi everyone, I'm Sarah from the engineering team. Excited to be here!"
            },
            {
                "speaker": 1,
                "start": 25.0,
                "end": 35.8,
                "transcript": "Welcome Sarah! Let's dive into the numbers. Our revenue increased by 25% this quarter, and customer satisfaction scores are up significantly."
            },
        ]
    }
}

# Create chunker with small chunk size for demonstration
chunker = MeetingChunker(chunk_size=200, chunk_overlap=50)

# Chunk with speaker name mapping
participant_mapping = {
    0: "Alice Johnson",
    1: "Bob Smith",
    2: "Sarah Chen"
}

chunks = chunker.chunk_from_deepgram(deepgram_response, participant_mapping)

print(f"\nCreated {len(chunks)} chunks from {len(deepgram_response['results']['utterances'])} utterances")
print()

for chunk in chunks:
    print(f"Chunk #{chunk.chunk_index}")
    print(f"  Offsets: {chunk.char_offset_start} - {chunk.char_offset_end}")
    print(f"  Speaker: {chunk.metadata['speaker']} ({chunk.metadata['speaker_name']})")
    print(f"  Timestamp: {chunk.metadata['timestamp']}")
    print(f"  Text: {chunk.text_content[:80]}...")
    print()


# Example 2: DocumentChunker with structured text
print("=" * 80)
print("Example 2: DocumentChunker with structured document")
print("=" * 80)

from src.services.chunking import DocumentChunker

# Sample document text with structure
document_text = """# Project Status Report

## Executive Summary

This report provides an overview of the project status for Q4 2024. The project
has made significant progress across all major workstreams, with several key
milestones achieved ahead of schedule.

Our team has successfully delivered the core platform infrastructure, completed
initial user testing, and gathered valuable feedback that will inform the next
development phase.

## Technical Architecture

The system architecture follows a microservices pattern with the following components:

### Backend Services

The backend consists of multiple microservices written in Python and FastAPI.
Each service is containerized using Docker and orchestrated with Kubernetes.

Key services include:
- Authentication Service: Handles user authentication and authorization
- Data Processing Service: Manages data ingestion and transformation
- API Gateway: Routes requests to appropriate microservices

### Frontend Application

The frontend is built using React and TypeScript, providing a responsive and
intuitive user interface. It communicates with the backend via RESTful APIs.

## Next Steps

Moving forward, the team will focus on:
1. Performance optimization
2. Enhanced monitoring and observability
3. User onboarding improvements
4. Documentation updates
"""

# Create chunker
doc_chunker = DocumentChunker(chunk_size=300, chunk_overlap=50)

# Chunk with source metadata
chunks = doc_chunker.chunk(
    text=document_text,
    source_metadata={
        "document_id": "status-report-2024-q4",
        "document_type": "markdown",
        "author": "Project Team",
        "page": 1
    }
)

print(f"\nCreated {len(chunks)} chunks from document")
print(f"Total document length: {len(document_text)} characters")
print()

for chunk in chunks:
    print(f"Chunk #{chunk.chunk_index}")
    print(f"  Offsets: {chunk.char_offset_start} - {chunk.char_offset_end}")
    print(f"  Length: {len(chunk.text_content)} chars")
    print(f"  Document: {chunk.metadata['document_id']}")
    print(f"  Type: {chunk.metadata['document_type']}")
    print(f"  Text preview: {chunk.text_content[:100].strip()}...")
    print()


# Example 3: Plain text chunking with MeetingChunker fallback
print("=" * 80)
print("Example 3: Plain text chunking (fallback)")
print("=" * 80)

plain_text = "This is a simple plain text document without speaker information. " * 20

chunks = chunker.chunk(plain_text)

print(f"\nCreated {len(chunks)} chunks from plain text")
print(f"Chunk size: {chunker.chunk_size}, Overlap: {chunker.chunk_overlap}")
print()

for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
    print(f"Chunk #{chunk.chunk_index}")
    print(f"  Offsets: {chunk.char_offset_start} - {chunk.char_offset_end}")
    print(f"  Metadata: {chunk.metadata}")
    print(f"  Text: {chunk.text_content[:80]}...")
    print()


print("=" * 80)
print("All examples completed successfully!")
print("=" * 80)
