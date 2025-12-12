import argparse
import yaml
import os
import cv2
from PIL import Image
import torch
from transformers import (
    LlavaNextProcessor,
    LlavaNextForConditionalGeneration,
    BitsAndBytesConfig,
    MarianMTModel,
    MarianTokenizer
)
import time

# --- 翻訳モデルロード関数 ---
def load_translation_model(model_name="Helsinki-NLP/opus-mt-en-jap"):
    print(f"Loading translation model {model_name}...")
    try:
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        print(f"Translation model loaded on {device}.")
        return model, tokenizer
    except Exception as e:
        print(f"Error loading translation model: {e}. Translation will be skipped.")
        return None, None

# --- テキスト翻訳関数 ---
def translate_text_en_to_ja(text: str, model, tokenizer) -> str:
    if not text or not model or not tokenizer:
        return "翻訳できませんでした (モデル未ロードまたは原文なし)"
    try:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(model.device)
        translated_tokens = model.generate(**inputs)
        translated_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        return translated_text
    except Exception as e:
        print(f"  Error during translation: {e}")
        return "翻訳中にエラーが発生しました"

# --- LLaVAモデルロード関数 ---
def load_llava_model(model_id: str, quantization: str = "fp16", revision: str = "edf96c5e9776fdd3f4ef324b5b7831b8b389c440"): # revision引数を追加
    dtype = torch.float16
    quantization_config = None
    if quantization == "8bit":
        quantization_config = BitsAndBytesConfig(load_in_8bit=True)
    elif quantization == "4bit":
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16
        )
    elif quantization != "fp16":
        raise ValueError("Invalid quantization option. Choose from 'fp16', '8bit', '4bit'.")

    print(f"Loading LLaVA model {model_id} (revision: {revision}) with {quantization} precision...") # revision情報をログに追加
    model = LlavaNextForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        quantization_config=quantization_config,
        device_map="auto",
        revision=revision, # revision を指定
        trust_remote_code=True
    )
    # プロセッサも同じrevisionからロードする
    processor = LlavaNextProcessor.from_pretrained(model_id, revision=revision, trust_remote_code=True) # revision を指定
    print("LLaVA Model and processor loaded.")
    print("LLaVA Model and processor loaded.")
    if hasattr(model, 'config') and hasattr(model.config, 'vocab_size'):
        print(f"  DEBUG: Model vocabulary size: {model.config.vocab_size}")
    if hasattr(processor, 'tokenizer') and hasattr(processor.tokenizer, 'vocab_size'):
        print(f"  DEBUG: Processor/Tokenizer vocabulary size: {processor.tokenizer.vocab_size}")
    # <image> トークンがどのように扱われるか（デバッグ用、必須ではない）
    try:
        image_token_str = "<image>" # プロンプトで使っている文字列
        # LLaVAプロセッサは<image>を特別扱いするので、直接ID変換が期待通りでない可能性あり
        # image_token_id = processor.tokenizer.convert_tokens_to_ids(image_token_str)
        # print(f"  DEBUG: '{image_token_str}' token ID (direct conversion): {image_token_id}")
        if hasattr(processor, 'image_token_id'): # プロセッサが特別なIDを保持しているか
             print(f"  DEBUG: Processor's special image_token_id: {processor.image_token_id}")
    except Exception as e_tok:
        print(f"  DEBUG: Error getting image token info: {e_tok}")
    return model, processor

# --- 1フレーム処理関数 ---
def process_frame_with_llava(
    model,
    processor,
    image: Image.Image,
    prompt: str,
    positive_keywords: list,
    negative_keywords: list
) -> tuple[bool, str, str]:
    raw_response_text = "LLaVAからの応答なし"
    try:
        inputs = processor(text=prompt, images=image, return_tensors="pt").to(model.device, dtype=torch.float16 if model.dtype == torch.float16 else model.dtype)
        
        # --- ここからデバッグ情報追加 ---
        print(f"  DEBUG: --- Input tensor details ---")
        for key, value in inputs.items():
            if torch.is_tensor(value): # torch.is_tensor を使う
                print(f"  DEBUG: Key: {key}, Shape: {value.shape}, Dtype: {value.dtype}, Device: {value.device}")
                if value.numel() > 0: 
                    if value.dtype in [torch.long, torch.int, torch.int64, torch.int32, torch.int16, torch.int8]:
                        try:
                            print(f"  DEBUG:         Min value: {value.min().item()}, Max value: {value.max().item()}")
                        except RuntimeError as re:
                            print(f"  DEBUG:         Could not get min/max for {key}: {re}")
                    elif value.dtype in [torch.float16, torch.float32, torch.bfloat16]:
                        try:
                            print(f"  DEBUG:         Min value: {value.min().item():.4f}, Max value: {value.max().item():.4f}, Mean value: {value.float().mean().item():.4f}")
                        except RuntimeError as re:
                            print(f"  DEBUG:         Could not get stats for {key}: {re}")
            else:
                print(f"  DEBUG: Key: {key}, Type: {type(value)}, Value: str(value)[:100]")
        print(f"  DEBUG: --- End input tensor details ---")
        # --- デバッグ情報ここまで ---

        try:
            generate_ids = model.generate(**inputs, max_new_tokens=150)
        except RuntimeError as e:
            print(f"  RUNTIME ERROR during model.generate: {e}")
            if "CUDA error" in str(e) or "device-side assert" in str(e):
                import traceback
                traceback.print_exc() # CUDAエラーの場合、詳細なスタックトレースを表示
            return False, f"LLaVA処理エラー (RuntimeError): {e}", "LLaVAからの応答なし"
        
        raw_response_text = processor.batch_decode(generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        
        assistant_keyword_full = "ASSISTANT:"
        assistant_keyword_lower = assistant_keyword_full.lower()
        response_payload_lower = raw_response_text.strip().lower()
        
        reason_text_en = raw_response_text
        if assistant_keyword_lower in response_payload_lower:
            payload_start_index = response_payload_lower.find(assistant_keyword_lower) + len(assistant_keyword_lower)
            response_payload_lower = response_payload_lower[payload_start_index:].strip()
            original_payload_start_index = raw_response_text.lower().find(assistant_keyword_lower) + len(assistant_keyword_lower)
            reason_text_en = raw_response_text[original_payload_start_index:].strip()

        print(f"  LLaVA Response (payload): {reason_text_en[:200]}...")

        for kw in positive_keywords:
            if response_payload_lower.startswith(kw):
                reason_after_kw = reason_text_en[len(kw):].strip()
                if reason_after_kw.startswith(',') or reason_after_kw.startswith('.'):
                    reason_after_kw = reason_after_kw[1:].strip()
                return True, reason_after_kw if reason_after_kw else reason_text_en, raw_response_text
        
        for kw in negative_keywords:
            if response_payload_lower.startswith(kw):
                return False, "", raw_response_text

        print(f"  Warning: LLaVA response did not clearly start with expected keywords. Assuming no critical issue based on this frame.")
        return False, "", raw_response_text

    except Exception as e:
        print(f"  Error processing frame with LLaVA: {e}")
        return False, f"LLaVA処理エラー: {e}", raw_response_text

# --- 動画分析関数 ---
def analyze_video_with_llava(
    model,
    processor,
    video_path: str,
    config: dict
) -> tuple[bool, str]:
    print(f"\nAnalyzing video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return False, "動画ファイルが開けませんでした"

    frame_interval = config.get('frame_interval', 30)
    vlm_prompt = config.get('vlm_settings', {}).get('prompt')
    positive_keywords = [kw.lower() for kw in config.get('vlm_settings', {}).get('positive_keywords', ["yes"])]
    negative_keywords = [kw.lower() for kw in config.get('vlm_settings', {}).get('negative_keywords', ["no"])]

    frame_count = 0
    first_critical_reason_en = ""

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            print(f" Processing frame {frame_count}...")
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb_frame)
                is_critical_frame, reason_en, _ = process_frame_with_llava(
                    model, processor, pil_image, vlm_prompt, positive_keywords, negative_keywords
                )
                if is_critical_frame:
                    print(f"  Critical issue FOUND in frame {frame_count}. Reason: {reason_en}")
                    first_critical_reason_en = reason_en if reason_en else "詳細な理由不明 (LLaVA応答より)"
                    cap.release()
                    return True, first_critical_reason_en
            except Exception as e:
                print(f"  Error processing frame {frame_count}: {e}")
        frame_count += 1
    cap.release()
    return False, ""

def main():
    parser = argparse.ArgumentParser(description="Analyze videos with LLaVA for critical detection errors and provide reasons.")
    parser.add_argument("--config", type=str, required=True, help="Path to the config.yaml file.")
    args = parser.parse_args()

    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {args.config}")
        return
    except yaml.YAMLError as e:
        print(f"Error loading config file: {e}")
        return

    # --- video_dir_path から動画ファイルリストを取得 ---
    video_dir_path_from_config = config.get('video_dir_path')
    if not video_dir_path_from_config:
        print("Error: 'video_dir_path' not found in config file.")
        return

    abs_video_dir_path = os.path.abspath(video_dir_path_from_config)
    if not os.path.isdir(abs_video_dir_path):
        print(f"Error: Path specified in 'video_dir_path' is not a valid directory: {abs_video_dir_path}")
        return

    print(f"Searching for video files in directory: {abs_video_dir_path}")
    allowed_video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm') # 対象とする動画拡張子
    video_files_to_process = []
    for filename in os.listdir(abs_video_dir_path):
        if filename.lower().endswith(allowed_video_extensions):
            full_path = os.path.join(abs_video_dir_path, filename)
            video_files_to_process.append(full_path)

    if not video_files_to_process:
        print(f"No video files with allowed extensions {allowed_video_extensions} found in {abs_video_dir_path}.")
        return
    
    print(f"Found {len(video_files_to_process)} video file(s) to process:")
    for vf in video_files_to_process:
        print(f"  - {vf}")
    # --- 動画ファイルリスト取得ここまで ---
    
    vlm_config = config.get('vlm_settings', {})
    model_id = vlm_config.get('model_id', 'liuhaotian/llava-v1.6-mistral-7b')
    quantization = vlm_config.get('quantization', 'fp16').lower()

    try:
        llava_model, llava_processor = load_llava_model(model_id, quantization)

    except Exception as e:
        print(f"Error loading LLaVA model: {e}")
        return

    translation_model_name = "Helsinki-NLP/opus-mt-en-jap"
    trans_model, trans_tokenizer = load_translation_model(translation_model_name)

    critical_incidents_data = []
    start_time_all = time.time()

    for video_path in video_files_to_process: # 処理対象リストを変更
        # video_path は既に絶対パスになっているはず
        video_start_time = time.time()
        is_critical_video, reason_en = analyze_video_with_llava(
            llava_model, llava_processor, video_path, config # video_path を直接渡す
        )
        video_end_time = time.time()
        print(f"Finished processing {video_path} in {video_end_time - video_start_time:.2f} seconds.")

        if is_critical_video:
            print(f"  Translating reason for {video_path}...")
            reason_ja = translate_text_en_to_ja(reason_en, trans_model, trans_tokenizer)
            print(f"    EN: {reason_en}")
            print(f"    JA: {reason_ja}")
            critical_incidents_data.append({
                "video_path": video_path, # 元のパスをそのまま使用
                "reason_en": reason_en,
                "reason_ja": reason_ja
            })

    output_data = {"critical_incidents": critical_incidents_data}
    output_file_path = "output.yaml"
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, allow_unicode=True, sort_keys=False, indent=2)
        print(f"\nAnalysis complete. Results saved to {output_file_path}")
        if critical_incidents_data:
            print("Critical incidents found:")
            for incident in critical_incidents_data:
                print(f"- Video: {incident['video_path']}")
                print(f"  Reason (EN): {incident['reason_en']}")
                print(f"  Reason (JA): {incident['reason_ja']}")
        else:
            print("No critical incidents found.")
            
    except IOError as e:
        print(f"Error writing output file: {e}")
    
    end_time_all = time.time()
    print(f"Total execution time: {end_time_all - start_time_all:.2f} seconds.")

if __name__ == "__main__":
    try:
        import cv2
        from PIL import Image
        import yaml
        # transformers, torch は load_... 関数内で import されるが、
        # メインの ImportError チェックのためにも記述しておく
        import transformers
        import torch 
    except ImportError as e:
        print(f"Missing required library: {e.name}. Please install it.")
        print("You might need: pip install opencv-python Pillow PyYAML transformers torch torchvision torchaudio bitsandbytes accelerate sentencepiece sacremoses")
        exit(1)
    main()
