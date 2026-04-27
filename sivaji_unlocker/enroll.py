"""Voice enrollment — captures multiple recordings of you speaking,
then averages their embeddings into a stable voiceprint.

Run once after install:  sivaji-enroll
Re-run anytime to retrain (e.g. if you have a cold and the matcher
starts rejecting you).
"""
from __future__ import annotations

import logging
import sys
import time

import numpy as np

from . import audio, config

log = logging.getLogger(__name__)


PROMPTS = [
    'Hi, I am the boss.',
    'Voice authentication ready.',
    'My laptop, my rules.',
    'Sivaji, the boss.',
    'Open sesame, this is me.',
]


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("\n" + "═" * 60)
    print("  SIVAJI VOICE UNLOCKER — ENROLLMENT")
    print("═" * 60)
    print("\nYou'll record %d short phrases (%.1fs each)." %
          (config.ENROLL_SAMPLES, config.RECORD_SECONDS))
    print("Speak naturally. The matcher learns YOUR VOICE — the words")
    print("don't have to match later. Use a quiet room.\n")

    input("Press ENTER when ready... ")

    samples = []
    for i in range(config.ENROLL_SAMPLES):
        prompt = PROMPTS[i % len(PROMPTS)]
        print(f"\n[{i+1}/{config.ENROLL_SAMPLES}]  Say:  \"{prompt}\"")
        for c in (3, 2, 1):
            print(f"   Recording in {c}...", end="\r", flush=True)
            time.sleep(1)
        print("   ◉ RECORDING NOW                ")
        clip = audio.record_audio()
        samples.append(clip)
        rms = float(np.sqrt(np.mean(clip ** 2)))
        if rms < 0.005:
            print("   ⚠️  Audio looks silent (RMS=%.4f). Check your mic." % rms)
        else:
            print("   ✓ Captured (RMS=%.4f)" % rms)

    print("\nBuilding voiceprint...")
    voiceprint = audio.enroll(samples)
    audio.save_voiceprint(voiceprint)

    # Self-test against the last sample to give the user confidence
    matched, sim = audio.verify(samples[-1], voiceprint)
    print(f"\nSelf-check similarity: {sim:.3f}  (threshold {config.SIMILARITY_THRESHOLD})")
    if matched:
        print("✓ Enrollment complete. You're ready to lock the system.")
    else:
        print("⚠️  Self-check failed. Try re-running in a quieter room.")
    print("\nVoiceprint saved to:", config.EMBEDDING_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
