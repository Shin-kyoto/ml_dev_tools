import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Union
import yaml
from moviepy.editor import VideoFileClip, ColorClip, TextClip, clips_array
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip # Used by clips_array

# Define type aliases for clarity
VideoConfig = Dict[str, Union[str, Path, str]] # Type hint for video entry in config
ColorType = Union[str, Tuple[int, int, int]]

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
    (size, fps, duration).

    Args:
        video_configs: A list of dictionaries, each with 'path' (Path object) and 'description'.

    Raises:
        FileNotFoundError: If any video file does not exist.
        ValueError: If video properties (size, fps, or duration) do not match.
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
        if not base_video_path.exists():
             raise FileNotFoundError(f"Video file not found: {base_video_path}")
        base_clip = VideoFileClip(str(base_video_path)) # moviepy often expects string paths
        base_size = base_clip.size
        base_fps = base_clip.fps
        base_duration = base_clip.duration
        clips.append(base_clip)

        print(f"Base properties: Size={base_size}, FPS={base_fps}, Duration={base_duration:.2f}s")

        # Check subsequent videos against the base
        for i, video_entry in enumerate(video_configs[1:], start=2):
            path = video_entry['path']
            print(f"Checking video {i}: {path}")
            if not path.exists():
                 raise FileNotFoundError(f"Video file not found: {path}")

            clip = VideoFileClip(str(path)) # moviepy often expects string paths
            if clip.size != base_size:
                raise ValueError(
                    f"Video size mismatch: '{path}' has size {clip.size}, "
                    f"expected {base_size} from '{base_video_path}'"
                )
            if clip.fps != base_fps:
                 # Allow for minor floating point differences
                if abs(clip.fps - base_fps) > 0.001:
                    raise ValueError(
                        f"Video FPS mismatch: '{path}' has FPS {clip.fps}, "
                        f"expected {base_fps} from '{base_video_path}'"
                    )
            if abs(clip.duration - base_duration) > 0.1: # Allow minor duration difference
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
    Loads videos, adds text descriptions in a bottom margin, and composites them horizontally.

    Args:
        video_configs: A list of dictionaries, each with 'path' (Path object) and 'description'.
        output_path: The path where the composite video will be saved (Path object).
        config: The full configuration dictionary containing text_area_height etc.

    Raises:
        Exception: If an error occurs during video processing or writing.
    """
    print(f"Loading video clips for composition: {[str(v['path']) for v in video_configs]}")

    text_area_height = config['text_area_height']
    text_area_color = config['text_area_color']
    font_size = config['font_size']
    font_color = config['font_color']

    # Load the first clip to get dimensions for composition
    # Verification ensures all others match these dimensions
    first_clip = VideoFileClip(str(video_configs[0]['path']))
    original_width, original_height = first_clip.size
    first_clip.close() # Close after getting dimensions

    combined_vertical_clips = [] # List to hold [Video + Text Area] clips

    loaded_clips = [] # Keep track of clips to close
    for i, video_entry in enumerate(video_configs):
        video_path = video_entry['path']
        description = video_entry['description']

        print(f"Processing video {i+1}: {video_path}")

        # 1. Load the video clip
        video_clip = VideoFileClip(str(video_path))
        loaded_clips.append(video_clip) # Add to list to close later

        # 2. Create the colored background clip for text
        # Ensure it has the same duration as the video clip
        color_clip = ColorClip(
            size=(original_width, text_area_height),
            color=(255, 255, 255),
            ismask=False,
            duration=video_clip.duration
        )

        loaded_clips.append(color_clip) # Add to list to close later


        # 3. Create the text clip
        # Ensure it has the same duration as the video clip
        text_clip = TextClip(
            description,
            fontsize=font_size,
            color=font_color,
            method='caption', # Use 'caption' for basic auto-wrapping if text is too wide
            size=(original_width * 0.9, None) # Limit text width to avoid edge issues
        )
        # Center the text clip on the color clip
        text_clip = text_clip.set_position('center').set_duration(video_clip.duration)
        loaded_clips.append(text_clip) # Add to list to close later

        # 4. Composite the text clip onto the color clip
        # This places the text centered on the colored background
        text_area_composite = CompositeVideoClip([color_clip, text_clip], use_bgclip=True)
        loaded_clips.append(text_area_composite) # Add to list to close later


        # 5. Stack the original video clip above the text area composite
        # Use clips_array to stack vertically
        combined_vertical = clips_array([
            [video_clip],          # Row 1: The original video
            [text_area_composite]  # Row 2: The colored text area
        ])
        # Duration is automatically set by clips_array based on the duration of components
        combined_vertical_clips.append(combined_vertical)


    if not combined_vertical_clips:
            raise ValueError("No combined vertical clips created.")

    if len(combined_vertical_clips) == 1:
        print("Only one video processed. Outputting the single composite video.")
        final_composite = combined_vertical_clips[0]
    else:
        print(f"Compositing {len(combined_vertical_clips)} videos horizontally...")
        # Arrange the combined vertical clips horizontally
        # Use clips_array to place them side-by-side
        final_composite = clips_array([combined_vertical_clips]) # Pass list of clips as a single row


    print(f"Writing output video: {output_path}")
    # Use libx264 codec for broad compatibility with MP4 container
    # fps should be set to the original video's fps
    final_composite.write_videofile(
        str(output_path), # moviepy expects string path for write_videofile
        codec='libx264',
        fps=video_clip.fps, # Use the verified FPS
        threads=4, # Optional: Use multiple threads for faster encoding
        preset='medium' # Optional: Encoding speed/compression trade-off
    )

    print("Video composition and writing complete.")
