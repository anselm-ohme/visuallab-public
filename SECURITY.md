# Security Policy

## Reporting a vulnerability

If you find a security issue in VisualLab — for example a way to extract
secrets from the running service, bypass the rate limiter, or get the LLM
backend to run unintended code — please **do not open a public GitHub
issue**.

Instead, email the maintainer directly:

**aohme@escp.eu**

Please include:

- A description of the issue and its impact.
- Steps to reproduce (a minimal request / payload is ideal).
- Any suggested mitigation, if you have one.

You can expect an initial reply within ~7 days. Once the issue is
confirmed and fixed, you'll be credited in the release notes unless you
prefer to remain anonymous.

## Scope

In scope:

- The deployed instance at `https://visuallab.onrender.com` and its
  Flask / NDJSON streaming endpoints.
- The code in this repository.

Out of scope:

- Findings against the upstream services VisualLab integrates with
  (NVIDIA NIM, Wikipedia, arXiv, Semantic Scholar, GitHub, Met Museum).
  Please report those to the respective vendors.
- Content the LLM happens to generate — VisualLab streams whatever the
  model produces, and the model is the responsible party for hallucinated
  facts or unsafe content. (That said, please flag any output that bypasses
  the safety filters of the underlying model, since it may indicate a
  prompt-injection vector.)
- DoS via volume — there is per-IP rate limiting, but a sustained
  high-volume attack against a free-tier hosted service is not novel.

Thank you for helping keep VisualLab safe.
