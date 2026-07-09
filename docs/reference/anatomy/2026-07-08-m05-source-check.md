# M05 Source Check: LLM Anatomy Control Contract

Date: 2026-07-08

Milestone: M05 LLM anatomy control contract.

## Sources Checked

| Claim Used By M05 | Source |
| --- | --- |
| Ollama supports structured outputs by passing `format: "json"` or a JSON schema object to local chat/generate requests. | Ollama Structured Outputs documentation: https://docs.ollama.com/capabilities/structured-outputs |
| Ollama recommends supplying the JSON schema in the prompt too, then validating the structured response in code. | Ollama Structured Outputs documentation: https://docs.ollama.com/capabilities/structured-outputs |
| The `/api/chat` endpoint accepts `messages`, `format`, `stream`, `keep_alive`, and `options`, and returns assistant content under `message.content`. | Ollama Chat API documentation: https://docs.ollama.com/api/chat |
| The `/api/generate` endpoint also documents `format` as either `"json"` or a JSON schema object. | Ollama Generate API documentation: https://docs.ollama.com/api/generate |
| Tool calling exists, but M05 uses structured output instead of tool invocation because the contract is a single bounded control object validated locally. | Ollama Tool Calling documentation: https://docs.ollama.com/capabilities/tool-calling |

## M05 Design Consequences

- The durable path is JSON Schema structured output, not free-form JSON mode.
- The prompt repeats the schema and exact allowed anatomy handles to ground local models.
- The code still owns authority: schema version, node existence, source ids,
  capability membership, value clamps, durations, and diagnostics.
- The LLM owns the semantic choice of which allowed controls to use for the
  requested action.
- Unknown nodes and unsupported capabilities are rejected with diagnostics, not
  silently repaired into fake controls.
- The browser evidence can use a deterministic sample plan, but the production
  contract path is the same validator used for real Ollama responses.

## Local Ollama Probe

- Endpoint: `http://127.0.0.1:11434/api/tags`
- Available model: `llama3.1:8b`
- Model family: `llama`
- Quantization: `Q4_K_M`
- Context length reported by Ollama: `131072`
- Capabilities reported by Ollama: `completion`, `tools`

## Local Ollama Contract Test

M05 sent a real `/api/chat` request to local `llama3.1:8b` using the generated
JSON schema as `format`. The response parsed through
`parse_anatomy_control_response` and produced:

- Valid controls: `3`
- Valid node ids: `region:right_hand`, `digit:right_pollex`,
  `digit:right_index_finger`
- All valid controls retained source ids from OpenStax A&P 2e 8.2 and FIPAT TA2.
- Existing bundle diagnostics remained visible for requested capabilities that
  specific digit nodes do not support.
