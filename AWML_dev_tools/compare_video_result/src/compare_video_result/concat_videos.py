import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Union
import yaml
from moviepy.editor import VideoFileClip, ColorClip, TextClip, clips_array
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip # Used by clips_array
from moviepy.video.VideoClip import VideoClip
from PIL import Image
import numpy as np

# Define type aliases for clarity
VideoConfig = Dict[str, Union[str, Path, str]] # Type hint for video entry in config
ColorType = Union[str, Tuple[int, int, int]]

def resize_video_clip(clip: VideoClip, target_size: Tuple[int, int]) -> VideoClip:
    """
    Resize a video clip using PIL's LANCZOS resampling method.
    
    Args:
        clip: The video clip to resize
        target_size: The target size as (width, height)
        
    Returns:
        The resized video clip
    """
    def resize_frame(frame):
        # Convert numpy array to PIL Image
        pil_image = Image.fromarray(frame)
        # Resize using LANCZOS resampling
        resized_image = pil_image.resize(target_size, Image.Resampling.LANCZOS)
        # Convert back to numpy array
        return np.array(resized_image)
    
    return clip.fl_image(resize_frame)

def load_config(yaml_path: Path) -> Dict[str, Any]:
    """
    Loads and validates the configuration from a YAML file.

    Args:
        yaml_path: The path to the YAML configuration file (Path object).

    Returns:
        A dictionary containing the configuration, with video paths as Path objects.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the YAML file is invalid.
        ValueError: If the configuration structure or values are invalid.
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {yaml_path}")

    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing YAML file: {e}")

    if not isinstance(config, dict):
        raise ValueError("Invalid configuration format. Expected a dictionary.")

    # Validate 'videos' section structure
    if 'videos' not in config or not isinstance(config['videos'], list):
         raise ValueError("Invalid configuration: 'videos' key missing or not a list.")

    if not 1 <= len(config['videos']) < 5:
        raise ValueError(f"Invalid number of videos: {len(config['videos'])}. Must be between 1 and 4.")

    # Validate each video entry and convert path to Path object
    processed_videos_config: List[VideoConfig] = []
    for i, video_entry in enumerate(config['videos']):
        if not isinstance(video_entry, dict):
             raise ValueError(f"Invalid configuration: videos entry {i} is not a dictionary.")
        if 'path' not in video_entry or not isinstance(video_entry['path'], str):
             raise ValueError(f"Invalid configuration: videos entry {i} missing 'path' key or it's not a string.")
        if 'description' not in video_entry or not isinstance(video_entry['description'], str):
             # Allow empty description string
             if 'description' not in video_entry:
                 print(f"Warning: videos entry {i} missing 'description' key. Using empty string.")
                 video_entry['description'] = ""
             elif not isinstance(video_entry['description'], str):
                 print(f"Warning: videos entry {i} 'description' is not a string. Using empty string.")
                 video_entry['description'] = ""

        video_path = Path(video_entry['path'])
        processed_videos_config.append({
            'path': video_path, # Store as Path object
            'description': video_entry['description']
        })

    config['videos'] = processed_videos_config # Replace with processed list

    # Validate output path and ensure directory exists
    if 'output_video' not in config or not isinstance(config['output_video'], str):
        raise ValueError("Invalid configuration: 'output_video' key missing or not a string.")
    output_path = Path(config['output_video'])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config['output_video'] = output_path # Store as Path object

    # Validate text area parameters with default values
    config['text_area_height'] = config.get('text_area_height', 100)
    if not isinstance(config['text_area_height'], (int, float)) or config['text_area_height'] < 0:
        print("Warning: 'text_area_height' invalid or missing. Using default 100.")
        config['text_area_height'] = 100

    config['text_area_color'] = config.get('text_area_color', "white")
    # Basic type check, detailed color validation could be added if needed
    if not isinstance(config['text_area_color'], (str, tuple)):
         print("Warning: 'text_area_color' invalid or missing. Using default 'white'.")
         config['text_area_color'] = "white"

    config['font_size'] = config.get('font_size', 30)
    if not isinstance(config['font_size'], (int, float)) or config['font_size'] <= 0:
         print("Warning: 'font_size' invalid or missing. Using default 30.")
         config['font_size'] = 30

    config['font_color'] = config.get('font_color', "black")
    # Basic type check
    if not isinstance(config['font_color'], (str, tuple)):
         print("Warning: 'font_color' invalid or missing. Using default 'black'.")
         config['font_color'] = "black"


    return config

def verify_videos(video_configs: List[VideoConfig]):
    """
    Verifies that all videos in the list have the same properties
    (fps, duration).

    Args:
        video_configs: A list of dictionaries, each with 'path' (Path object) and 'description'.

    Raises:
        FileNotFoundError: If any video file does not exist.
        ValueError: If video properties (fps or duration) do not match.
        Exception: For other errors encountered while loading video clips.
    """
    if not video_configs:
        raise ValueError("No video configurations provided for verification.")

    print("Verifying video properties...")

    # Use Path objects directly
    base_video_path = video_configs[0]['path']

    clips = []
    try:
        # Load the first video to establish baseline properties
        print(f"Loading and checking base video: {base_video_path}")
        base_clip = VideoFileClip(str(base_video_path)) # moviepy often expects string paths
        base_fps = base_clip.fps
        base_duration = base_clip.duration
        clips.append(base_clip)

        print(f"Base properties: FPS={base_fps}, Duration={base_duration:.2f}s")

        # Check subsequent videos against the base
        for i, video_entry in enumerate(video_configs[1:], start=2):
            path = video_entry['path']
            print(f"Checking video {i}: {path}")
            if not path.exists():
                 raise FileNotFoundError(f"Video file not found: {path}")

            clip = VideoFileClip(str(path)) # moviepy often expects string paths
            if clip.fps != base_fps:
                 # Allow for minor floating point differences
                if abs(clip.fps - base_fps) > 0.001:
                    raise ValueError(
                        f"Video FPS mismatch: '{path}' has FPS {clip.fps}, "
                        f"expected {base_fps} from '{base_video_path}'"
                    )
            if abs(clip.duration - base_duration) > 0.5: # Allow up to 0.5 seconds difference
                 raise ValueError(
                    f"Video duration mismatch: '{path}' has duration {clip.duration:.2f}s, "
                    f"expected {base_duration:.2f}s from '{base_video_path}'"
                )
            clips.append(clip) # Keep track of clips to close

        print("All video properties match.")

    except Exception as e:
        # Close any opened clips before raising the error
        for clip in clips:
             if clip and clip.reader is not None:
                clip.close()
        raise e # Re-raise the exception after cleanup
    finally:
         # Ensure clips are closed even on success
        for clip in clips:
             if clip and clip.reader is not None:
                clip.close()


def process_and_composite_videos(video_configs: List[VideoConfig], output_path: Path, config: Dict[str, Any]):
    """
    Loads videos, adds text descriptions in a bottom margin, and composites them in a grid.
    Videos with different sizes will be resized to match the first video's size.

    Arrangement:
    - N=1: Single video + text area
    - N=2: [Video1+Text] [Video2+Text] (1 row, 2 columns)
    - N=3: [Video1+Text] [Video2+Text]
           [Video3+Text] [Blank Area  ] (2 rows, 2 columns)
    - N=4: [Video1+Text] [Video2+Text]
           [Video3+Text] [Video4+Text] (2 rows, 2 columns)

    Args:
        video_configs: A list of dictionaries, each with 'path' (Path object) and 'description'.
        output_path: The path where the composite video will be saved (Path object).
        config: The full configuration dictionary containing text_area_height etc.

    Raises:
        Exception: If an error occurs during video processing or writing.
    """
    print(f"Loading video clips for composition: {[str(v['path']) for v in video_configs]}")

    text_area_height = config['text_area_height']
    text_area_color = (255, 255, 255)
    font_size = config['font_size']
    font_color = config['font_color']

    # Load the first clip to get dimensions and duration for composition
    first_clip = VideoFileClip(str(video_configs[0]['path']))
    target_width, target_height = first_clip.size
    clip_duration = first_clip.duration
    clip_fps = first_clip.fps
    first_clip.close()

    combined_vertical_clips: List[VideoClip] = []
    loaded_clips = []

    for i, video_entry in enumerate(video_configs):
        video_path = video_entry['path']
        description = video_entry['description']

        print(f"Processing video {i+1}: {video_path}")

        # 1. Load the video clip and resize if necessary
        video_clip = VideoFileClip(str(video_path))
        if video_clip.size != (target_width, target_height):
            print(f"Resizing video {i+1} from {video_clip.size} to {(target_width, target_height)}")
            video_clip = resize_video_clip(video_clip, (target_width, target_height))
        video_clip = video_clip.set_duration(clip_duration).set_fps(clip_fps)
        loaded_clips.append(video_clip)

        # 2. Create the colored background clip for text
        color_clip = ColorClip(
            size=(target_width, text_area_height),
            color=(255, 255, 255),
            ismask=False,
            duration=clip_duration
        )
        loaded_clips.append(color_clip)

        try:
            color_clip = color_clip.add_mask()
        except Exception as e:
            print(f"Warning: Could not add mask to color clip: {e}", file=sys.stderr)

        # 3. Create the text clip
        text_clip = TextClip(
            description,
            fontsize=font_size,
            color=font_color,
            method='label',
            size=(target_width * 0.9, None),
            bg_color='white',
        ).set_position('center').set_duration(clip_duration)
        loaded_clips.append(text_clip)

        # 4. Composite the text clip onto the color clip
        text_area_composite = CompositeVideoClip(
            [color_clip, text_clip],
            size=(target_width, text_area_height),
            use_bgclip=True
        ).set_duration(clip_duration)
        loaded_clips.append(text_area_composite)

        # 5. Stack the original video clip above the text area composite
        combined_vertical = clips_array([
            [video_clip],
            [text_area_composite]
        ]).set_duration(clip_duration).set_fps(clip_fps)

        combined_vertical_clips.append(combined_vertical)

    # --- Arrangement Logic based on number of videos (N) ---
    N = len(combined_vertical_clips)

    if N == 0: # Should be caught by load_config, but safety check
            raise ValueError("No video clips processed.")
    elif N == 1:
        print("Arranging 1 video...")
        final_composite = combined_vertical_clips[0]
    elif N == 2:
        print("Arranging 2 videos side-by-side...")
        # Arrange as a single row: [V1+T1, V2+T2]
        final_composite = clips_array([combined_vertical_clips])
    elif N == 3:
        print("Arranging 3 videos in a 2x2 grid with a blank space...")
        # Create a blank white clip with the same size and duration as the combined vertical clips
        blank_clip_size = (target_width, target_height + text_area_height)
        blank_clip = ColorClip(
            size=blank_clip_size,
            color=(255, 255, 255), # White color
            ismask=False,
            duration=clip_duration # Use determined duration
        ).set_fps(clip_fps) # Set FPS
        loaded_clips.append(blank_clip) # Add to list to close later

        # Arrange in a 2x2 grid:
        # [V1+T1, V2+T2]
        # [V3+T3, Blank ]
        final_composite = clips_array([
            [combined_vertical_clips[0], combined_vertical_clips[1]], # Row 1
            [combined_vertical_clips[2], blank_clip]                 # Row 2
        ])
    elif N == 4:
            print("Arranging 4 videos in a 2x2 grid...")
            # Arrange in a 2x2 grid:
            # [V1+T1, V2+T2]
            # [V3+T3, V4+T4]
            final_composite = clips_array([
                [combined_vertical_clips[0], combined_vertical_clips[1]], # Row 1
                [combined_vertical_clips[2], combined_vertical_clips[3]]  # Row 2
            ])
    else: # N should be < 5 based on load_config validation, but safety check
            raise ValueError(f"Unsupported number of videos: {N}")


    print(f"Writing output video: {output_path}")
    # Use libx264 codec for broad compatibility with MP4 container
    # fps should be set to the original video's fps
    final_composite.write_videofile(
        str(output_path), # moviepy expects string path for write_videofile
        codec='libx264',
        fps=clip_fps, # Use the determined FPS
        threads=4, # Optional: Use multiple threads for faster encoding
        preset='medium', # Optional: Encoding speed/compression trade-off
        # Add audio=True/False depending on if you want audio from the first clip
        audio=(len(video_configs) > 0) # Include audio from the first clip if available
    )

    print("Video composition and writing complete.")

