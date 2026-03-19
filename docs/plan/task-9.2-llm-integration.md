# Task 9.2 — LLM Integration & Prompt Design

## Summary

Integrate with an LLM API to clean up and structure extracted text into Markdown.

## Dependencies

- Task 9.1 (PyMuPDF extraction)
- Task 1.2 (configuration — needs `llm_model` setting)

## Acceptance Criteria

- [ ] Extracted text segments are sent to an LLM with a formatting prompt.
- [ ] LLM model is configurable via `llm_model` config parameter.
- [ ] System prompt instructs the LLM to: preserve headings, lists, tables; remove headers/footers/page numbers; output only Markdown.
- [ ] LLM responses are collected and written as chunk Markdown files.
- [ ] API errors are retried (max 3 retries with exponential backoff).
- [ ] Rate limiting: a semaphore limits concurrent LLM calls (configurable, default: 2).
- [ ] Token usage per chunk is logged for cost tracking.
- [ ] Total token usage is included in the run summary.
- [ ] Unit tests mock the LLM API; integration test uses a real endpoint with a small sample.

## Implementation Notes

### System prompt

```
You are a document formatting assistant. Convert the following extracted PDF
text into clean GitHub-Flavored Markdown. Rules:
- Preserve all headings as Markdown headings (# ## ### etc.)
- Preserve bullet and numbered lists
- Format tables as Markdown tables
- Remove page headers, footers, and page numbers
- Do not add, remove, or rephrase content
- Output only the Markdown, no commentary
```

### API integration

Keep the LLM client abstracted behind an interface so different providers (OpenAI, Anthropic, local models) can be swapped:

```python
class LLMClient:
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        ...

@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
```

### Rate limiting

```python
import asyncio

semaphore = asyncio.Semaphore(config.llm_concurrent_requests or 2)

async def call_llm(segment):
    async with semaphore:
        return await llm_client.complete(SYSTEM_PROMPT, segment)
```

### Cost estimation

Before processing, estimate total tokens and log expected cost:

```python
def estimate_tokens(text):
    return len(text) // 4  # rough approximation
```

## References

- [technical-design.md §6.3 — LLM Prompt Design](../technical-design.md)
- [technical-design.md §6.5 — Cost & Rate Considerations](../technical-design.md)
