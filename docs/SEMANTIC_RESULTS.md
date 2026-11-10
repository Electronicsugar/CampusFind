# Semantic regression results

Reference: supplied case-query.jpg. Inference used full frames and no filename-based logic.

| Candidate | Predicted content | CLIP cosine | Routing |
|---|---|---:|---|
| case-close.jpg | earbuds | 0.7262 | relevant |
| case-distant.jpg | earbuds | 0.8302 | relevant |
| graph-negative.png | chart or diagram | 0.4955 | excluded |

The old appearance heuristic gave case-query vs graph-negative 93.9%, despite unrelated contents. The semantic check excludes that candidate rather than changing or inflating the earlier score. A regression also uploads the graph under an earbuds filename and the case under a graph filename to verify content, not names, determines routing.

Initial label-vs-runner-up margin gating placed all cases into uncertain. The policy was corrected: agreeing predicted physical-item categories are retrieval candidates without an identity claim, and non-item categories are compared together against physical-item evidence. This is an implementation refinement on a known development example, not a held-out accuracy evaluation. More independent negatives are required.

No photos leave the computer. Model parameters are downloaded once; inference is local. Scores are not calibrated probabilities. The full image model is generic and does not prove exact physical-object identity.
