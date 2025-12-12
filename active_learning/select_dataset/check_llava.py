# check_llava.py (変更版)
from transformers import LlavaProcessor # LlavaNextProcessor から変更
import os

hf_cache_home = os.path.expanduser(os.getenv("HF_HOME", os.path.join("~", ".cache", "huggingface")))
print(f"Hugging Face cache directory (HF_HOME or default): {hf_cache_home}")

model_id = "liuhaotian/llava-v1.6-mistral-7b"

print(f"\nAttempting to load processor for {model_id} using LlavaProcessor...")
try:
    processor = LlavaProcessor.from_pretrained(model_id, revision="edf96c5e9776fdd3f4ef324b5b7831b8b389c440")
    print(f"Processor for {model_id} loaded successfully.")
    print(f"Processor config: {processor.processor_config if hasattr(processor, 'processor_config') else 'N/A'}")
except Exception as e:
    print(f"An error occurred while loading processor for {model_id}:")
    import traceback
    traceback.print_exc()

print("\nScript finished.")
