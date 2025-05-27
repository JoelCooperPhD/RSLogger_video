import asyncio
import logging
import sys

from src.recorder import RecordingConfig
from src.config import ConfigManager
from src.cli import parse_args
from src.modes import run_standalone_recording, run_controlled_mode


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for RSLogger Audio recorder."""
    # Load config
    config_manager = ConfigManager()
    default_config = config_manager.load()
    
    # Parse command line arguments
    args = parse_args(default_config)
    
    # Handle config management commands first
    if args.show_config:
        print("Current configuration:")
        print(f"  Sample rate: {default_config.samplerate} Hz")
        print(f"  Channels: {default_config.channels}")
        print(f"  Output directory: {default_config.output_dir}")
        print(f"  Data type: {default_config.dtype}")
        print(f"  Device: {default_config.device or 'Default'}") 
        print(f"\nConfig file: {config_manager.config_path}")
        return
        
    if args.reset_config:
        config_manager.reset()
        print("Configuration reset to defaults")
        return
    
    # Create recorder configuration
    config = RecordingConfig(
        samplerate=args.samplerate,
        channels=args.channels,
        dtype=default_config.dtype,
        output_dir=args.output_dir,
        device=args.device
    )
    
    # Save config if requested
    if args.save_config:
        config_manager.save(config)
        print(f"Configuration saved to {config_manager.config_path}")
        return
    
    # Determine operation mode
    if args.controlled:
        # Controlled mode - expose recorder via WebSocket
        await run_controlled_mode(args.control_url, args.device)
    else:
        # Standalone recording mode
        await run_standalone_recording(config, args)


def run() -> None:
    """Entry point that runs the async main function."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")


if __name__ == "__main__":
    run()