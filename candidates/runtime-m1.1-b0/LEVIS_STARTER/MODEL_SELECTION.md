# Model choice — 2026-10-22

Chosen: **Qwen3.5-4B**, Ollama `qwen3.5:4b`, local quantized package. This is a practical starting choice for this machine, not a measured universal winner. Open weights and the model's Apache-2.0 license do not imply a fully reproducible open training-data pipeline.

Observed hardware: Intel Core Ultra 5 225U, 16,573,128,704 bytes physical RAM (about 15.4 GiB), Intel integrated graphics. Ollama detected no usable dedicated VRAM and selected CPU execution. Approximately 3.1 GiB physical RAM was free during inspection; other applications are using much of memory. Real speed and peak memory must be measured here, not inferred from download size. Keep context at 4,096 tokens for the initial workbench.

| Candidate | Fit assessment |
| --- | --- |
| Qwen3.5-4B | Selected for its relatively small quantized package, permissive model license, general conversation/coding capability and image support for later explicit integration. |
| Qwen3.5-9B | Larger model with more capacity, but approximately twice the package size and less memory headroom on this CPU-only 16 GB machine. A later upgrade candidate, not downloaded now. |
| Gemma 4 E4B | Credible local alternative with native system prompts and multimodal capabilities; Ollama lists a substantially larger package range. Less attractive as the first low-memory baseline here. |
| Existing Phi-3 / TinyLlama / Llama 3 | Preserved unchanged. Available for comparison later; their presence is not evidence of suitability for LEVIS. |

Selection criteria: local operation, adaptable licensing, feasible memory footprint, conversational utility, and compatibility with an independently enforced capability boundary. Publisher benchmarks are not LEVIS acceptance tests. A stronger model never inherits authority over Base admission or execution. The workbench exposes no model tools, cloud fallback, automatic evidence promotion, or shell interpretation.

Primary sources consulted:

- [Qwen3.5-4B model card and Apache-2.0 metadata](https://huggingface.co/Qwen/Qwen3.5-4B)
- [Ollama Qwen3.5-4B package, tensors and license](https://ollama.com/library/qwen3.5:4b)
- [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Ollama Qwen3.5-9B package](https://ollama.com/library/qwen3.5:9b)
- [Ollama Gemma 4 model family](https://ollama.com/library/gemma4)
- [Ollama API implementation documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)

The exact installed tag digest, local blob hashes, license and live smoke-test output are recorded separately after download. They are provenance and bounded execution evidence, not safety certification or an independent review.
