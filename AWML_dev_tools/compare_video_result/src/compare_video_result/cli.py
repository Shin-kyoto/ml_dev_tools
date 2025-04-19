import argparse
import sys
import yaml
from pathlib import Path
from concat_videos import load_config, verify_videos, process_and_composite_videos

def main():
    """
    Main entry point for the compare-video-result tool.
    Parses arguments, loads config, verifies, and composites videos.
    """
    parser = argparse.ArgumentParser(
        description="Composite multiple videos with identical properties and add model descriptions for comparison."
    )
    parser.add_argument(
        "config_file",
        help="Path to the YAML configuration file."
    )

    args = parser.parse_args()

    try:
        # Convert config file path string to Path object
        config_path = Path(args.config_file)

        # Load and validate configuration
        config = load_config(config_path)

        # Get processed video configs (list of dicts with Path objects)
        video_configs = config['videos']
        output_path = config['output_video'] # This is already a Path object from load_config

        # Verify video properties using the list of video configs
        verify_videos(video_configs)

        # Process and composite the videos
        process_and_composite_videos(video_configs, output_path, config)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration or Video Error: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"YAML Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch any other exceptions during video processing
        print(f"An unexpected error occurred during processing: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
