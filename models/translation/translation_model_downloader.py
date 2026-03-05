"""
Download NLLB-200-Distilled-600M from HuggingFace Hub.
Output: ./translation/nllb-200-distilled-600M/
"""
import os
from huggingface_hub import snapshot_download

output_dir = "./translation/nllb-200-distilled-600M"
os.makedirs(output_dir, exist_ok=True)

print("Downloading facebook/nllb-200-distilled-600M ...")
snapshot_download(
    repo_id="facebook/nllb-200-distilled-600M",
    local_dir=output_dir,
    ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "rust_model*"],
)
print(f"Done. Model saved to {output_dir}")
