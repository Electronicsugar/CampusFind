# Baseline findings

Eight automated checks passed: synthetic rotation/scale/brightness, featureless-image behavior, invalid crops, malformed uploads, and successful API comparison.

On the two supplied case photographs, all three configurations (full image, manual crop, crop with CLAHE) produced zero geometric inliers. CLAHE increased detected features but did not produce surviving mutual descriptor matches. The cropped outputs were visually inspected and include the intended case in both views.

This is a negative baseline result, not evidence that the objects differ. Do not relax thresholds just to make this positive pair match. Next compare learned visual retrieval and local learned matching, including different cases and identical-model negatives. Retrieval accuracy is not established by this experiment.

The server started and API tests passed. In-app browser navigation timed out; browser interaction and layout QA remain unverified.

A separate loopback HTTP check also timed out in the execution environment. The development server was stopped after verification. Start it from a local terminal using start.ps1; live browser access still needs verification. In-process API tests passed.
