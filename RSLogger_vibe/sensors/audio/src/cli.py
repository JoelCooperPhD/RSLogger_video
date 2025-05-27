"""Command-line interface module for RSLogger Audio."""

import argparse
from typing import Optional, Union
from dataclasses import dataclass

from .recorder import RecordingConfig


@dataclass
class CLIArgs:
    """Parsed command-line arguments."""
    filename: Optional[str]
    duration: Optional[float]
    samplerate: int
    output_dir: str
    channels: int
    device: Optional[Union[int, str]]
    info: bool
    list_devices: bool
    save_config: bool
    show_config: bool
    reset_config: bool
    controlled: bool
    control_url: str


def create_parser(default_config: RecordingConfig) -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="RSLogger Audio - Simple audio recording CLI"
    )
    
    parser.add_argument(
        "filename",
        nargs="?",
        help="Output filename (default: timestamp-based name)"
    )
    
    parser.add_argument(
        "-d", "--duration",
        type=float,
        help="Recording duration in seconds (default: record until Ctrl+C)"
    )
    
    parser.add_argument(
        "-r", "--samplerate",
        type=int,
        default=default_config.samplerate,
        help=f"Sample rate in Hz (default: {default_config.samplerate})"
    )
    
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=default_config.output_dir,
        help=f"Output directory (default: {default_config.output_dir})"
    )
    
    parser.add_argument(
        "-c", "--channels",
        type=int,
        default=default_config.channels,
        help=f"Number of channels (1=mono, 2=stereo, default: {default_config.channels})"
    )
    
    parser.add_argument(
        "--device",
        type=str,
        default=default_config.device,
        help="Audio input device (name or ID)"
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show audio device information"
    )
    
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List all available input devices"
    )
    
    # Config management arguments
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="Save current settings as defaults"
    )
    
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration"
    )
    
    parser.add_argument(
        "--reset-config",
        action="store_true",
        help="Reset configuration to defaults"
    )
    
    # Controlled mode
    parser.add_argument(
        "--controlled",
        action="store_true",
        help="Run in controlled mode - expose recorder controls via WebSocket"
    )
    
    parser.add_argument(
        "--control-url",
        type=str,
        default="ws://localhost:8080/recorder",
        help="WebSocket URL for control connection (default: ws://localhost:8080/recorder)"
    )
    
    return parser


def parse_device(device_arg: Optional[str]) -> Optional[Union[int, str]]:
    """Parse device argument to int or string."""
    if device_arg and device_arg.isdigit():
        return int(device_arg)
    return device_arg


def parse_args(default_config: RecordingConfig) -> CLIArgs:
    """Parse command-line arguments and return CLIArgs."""
    parser = create_parser(default_config)
    args = parser.parse_args()
    
    # Parse device
    device = parse_device(args.device)
    
    return CLIArgs(
        filename=args.filename,
        duration=args.duration,
        samplerate=args.samplerate,
        output_dir=args.output_dir,
        channels=args.channels,
        device=device,
        info=args.info,
        list_devices=args.list_devices,
        save_config=args.save_config,
        show_config=args.show_config,
        reset_config=args.reset_config,
        controlled=args.controlled,
        control_url=args.control_url
    )