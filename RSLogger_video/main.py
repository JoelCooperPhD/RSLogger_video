import cv2
import argparse
import sys
import asyncio
import websockets
import json
import base64
import time
import concurrent.futures
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Dict, Any
import numpy as np

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False


class CameraInterface(ABC):
    """Abstract base class for camera implementations"""
    
    @abstractmethod
    async def initialize(self, camera_index: int, width: int, height: int, fps: int) -> bool:
        """Initialize the camera with given parameters"""
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """Start the camera"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the camera"""
        pass
    
    @abstractmethod
    async def capture_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Capture a single frame"""
        pass
    
    @abstractmethod
    async def get_actual_properties(self) -> Dict[str, Any]:
        """Get actual camera properties (resolution, fps, etc.)"""
        pass
    
    @abstractmethod
    async def release(self):
        """Release camera resources"""
        pass
    
    @abstractmethod
    async def list_available_cameras(self) -> List[int]:
        """List available camera indices"""
        pass


class USBCameraHandler(CameraInterface):
    """USB/Webcam camera handler using OpenCV"""
    
    def __init__(self, executor):
        self.executor = executor
        self.cap = None
        self.camera_index = 0
        self.width = 640
        self.height = 480
        self.fps = 30
    
    async def initialize(self, camera_index: int, width: int, height: int, fps: int) -> bool:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        return True
    
    async def start(self) -> bool:
        if self.cap is not None:
            await asyncio.get_event_loop().run_in_executor(self.executor, self.cap.release)
        
        loop = asyncio.get_event_loop()
        self.cap = await loop.run_in_executor(self.executor, cv2.VideoCapture, self.camera_index)
        
        is_opened = await loop.run_in_executor(self.executor, self.cap.isOpened)
        if not is_opened:
            return False
        
        await loop.run_in_executor(self.executor, self.cap.set, cv2.CAP_PROP_FRAME_WIDTH, self.width)
        await loop.run_in_executor(self.executor, self.cap.set, cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        await loop.run_in_executor(self.executor, self.cap.set, cv2.CAP_PROP_FPS, self.fps)
        
        return True
    
    async def stop(self):
        if self.cap is not None:
            await asyncio.get_event_loop().run_in_executor(self.executor, self.cap.release)
            self.cap = None
    
    async def capture_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.cap is None:
            return False, None
        return await asyncio.get_event_loop().run_in_executor(self.executor, self.cap.read)
    
    async def get_actual_properties(self) -> Dict[str, Any]:
        if self.cap is None:
            return {'width': self.width, 'height': self.height, 'fps': self.fps}
        
        loop = asyncio.get_event_loop()
        actual_width = await loop.run_in_executor(self.executor, lambda: int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        actual_height = await loop.run_in_executor(self.executor, lambda: int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        actual_fps = await loop.run_in_executor(self.executor, lambda: int(self.cap.get(cv2.CAP_PROP_FPS)))
        
        return {'width': actual_width, 'height': actual_height, 'fps': actual_fps}
    
    async def release(self):
        await self.stop()
    
    async def list_available_cameras(self) -> List[int]:
        cameras = []
        loop = asyncio.get_event_loop()
        for i in range(10):
            cap = await loop.run_in_executor(self.executor, cv2.VideoCapture, i)
            is_opened = await loop.run_in_executor(self.executor, cap.isOpened)
            if is_opened:
                cameras.append(i)
            await loop.run_in_executor(self.executor, cap.release)
        return cameras


class PiCameraHandler(CameraInterface):
    """Raspberry Pi camera handler using PiCamera2"""
    
    def __init__(self, executor):
        self.executor = executor
        self.picam2 = None
        self.camera_index = 0
        self.width = 640
        self.height = 480
        self.fps = 30
        self.config = None
    
    async def initialize(self, camera_index: int, width: int, height: int, fps: int) -> bool:
        if not PICAMERA2_AVAILABLE:
            return False
        
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        return True
    
    async def start(self) -> bool:
        if not PICAMERA2_AVAILABLE:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            self.picam2 = await loop.run_in_executor(self.executor, Picamera2, self.camera_index)
            
            # Configure camera
            def configure_camera():
                config = self.picam2.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "RGB888"},
                    controls={"FrameRate": self.fps}
                )
                self.picam2.configure(config)
                return config
            
            self.config = await loop.run_in_executor(self.executor, configure_camera)
            await loop.run_in_executor(self.executor, self.picam2.start)
            
            return True
        except Exception:
            return False
    
    async def stop(self):
        if self.picam2 is not None:
            try:
                await asyncio.get_event_loop().run_in_executor(self.executor, self.picam2.stop)
                await asyncio.get_event_loop().run_in_executor(self.executor, self.picam2.close)
            except Exception:
                pass
            finally:
                self.picam2 = None
    
    async def capture_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.picam2 is None:
            return False, None
        
        try:
            frame = await asyncio.get_event_loop().run_in_executor(self.executor, self.picam2.capture_array)
            # Convert RGB to BGR for OpenCV compatibility
            frame_bgr = await asyncio.get_event_loop().run_in_executor(self.executor, cv2.cvtColor, frame, cv2.COLOR_RGB2BGR)
            return True, frame_bgr
        except Exception:
            return False, None
    
    async def get_actual_properties(self) -> Dict[str, Any]:
        return {'width': self.width, 'height': self.height, 'fps': self.fps}
    
    async def release(self):
        await self.stop()
    
    async def list_available_cameras(self) -> List[int]:
        if not PICAMERA2_AVAILABLE:
            return []
        
        try:
            # PiCamera2 typically has cameras 0 and 1 (if dual camera setup)
            cameras = []
            for i in range(2):
                try:
                    loop = asyncio.get_event_loop()
                    picam2 = await loop.run_in_executor(self.executor, Picamera2, i)
                    await loop.run_in_executor(self.executor, picam2.close)
                    cameras.append(i)
                except Exception:
                    break
            return cameras
        except Exception:
            return []


class CameraController:
    def __init__(self, camera_type: str = 'usb'):
        self.camera_type = camera_type
        self.camera_index = 0
        self.width = 640
        self.height = 480
        self.fps = 30
        self.output_file = 'output.avi'
        self.duration = 10
        self.recording = False
        self.out = None
        self.clients = set()
        self.frame_queue = asyncio.Queue()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.capture_task = None
        self.camera_handler: Optional[CameraInterface] = None
        self.status = {
            'recording': False,
            'camera_type': camera_type,
            'camera_index': 0,
            'resolution': [640, 480],
            'fps': 30,
            'output_file': None
        }
        self._initialize_camera_handler()
    
    def _initialize_camera_handler(self):
        """Initialize the appropriate camera handler based on camera type"""
        if self.camera_type == 'picamera':
            if PICAMERA2_AVAILABLE:
                self.camera_handler = PiCameraHandler(self.executor)
            else:
                raise ValueError("PiCamera2 not available. Install with: pip install picamera2")
        else:  # 'usb' or any other type defaults to USB
            self.camera_handler = USBCameraHandler(self.executor)

    async def start_camera(self):
        if not self.camera_handler:
            return False
        
        # Initialize and start camera
        await self.camera_handler.initialize(self.camera_index, self.width, self.height, self.fps)
        
        if not await self.camera_handler.start():
            return False
        
        # Get actual properties
        properties = await self.camera_handler.get_actual_properties()
        self.status['resolution'] = [properties['width'], properties['height']]
        self.status['fps'] = properties['fps']
        self.status['camera_index'] = self.camera_index
        
        return True

    async def start_recording(self, filename=None, duration=None):
        if self.recording:
            return False
        
        if filename:
            self.output_file = filename
        if duration:
            self.duration = duration
            
        if not await self.start_camera():
            return False
        
        loop = asyncio.get_event_loop()
        fourcc = await loop.run_in_executor(self.executor, cv2.VideoWriter_fourcc, *'XVID')
        self.out = await loop.run_in_executor(
            self.executor, 
            cv2.VideoWriter, 
            self.output_file, 
            fourcc, 
            self.status['fps'], 
            (self.status['resolution'][0], self.status['resolution'][1])
        )
        
        self.recording = True
        self.status['recording'] = True
        self.status['output_file'] = self.output_file
        return True

    async def stop_recording(self):
        if not self.recording:
            return False
        
        self.recording = False
        self.status['recording'] = False
        self.status['output_file'] = None
        
        if self.capture_task:
            self.capture_task.cancel()
            try:
                await self.capture_task
            except asyncio.CancelledError:
                pass
            self.capture_task = None
        
        loop = asyncio.get_event_loop()
        if self.out:
            await loop.run_in_executor(self.executor, self.out.release)
            self.out = None
        if self.camera_handler:
            await self.camera_handler.stop()
        return True

    async def capture_frames(self):
        frame_count = 0
        max_frames = self.status['fps'] * self.duration if self.duration > 0 else float('inf')
        loop = asyncio.get_event_loop()
        
        try:
            while self.recording and frame_count < max_frames:
                ret, frame = await self.camera_handler.capture_frame()
                if not ret or frame is None:
                    break
                
                if self.out:
                    await loop.run_in_executor(self.executor, self.out.write, frame)
                
                _, buffer = await loop.run_in_executor(self.executor, cv2.imencode, '.jpg', frame)
                frame_data = await loop.run_in_executor(self.executor, base64.b64encode, buffer)
                frame_data_str = frame_data.decode('utf-8')
                
                await self.frame_queue.put({
                    'type': 'frame',
                    'data': frame_data_str,
                    'timestamp': time.time(),
                    'frame_num': frame_count
                })
                
                frame_count += 1
                await asyncio.sleep(0.001)  # Small yield to allow other tasks
                
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop_recording()

    async def handle_client(self, websocket, path):
        self.clients.add(websocket)
        try:
            async for message in websocket:
                try:
                    command = json.loads(message)
                    response = await self.handle_command(command)
                    await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON'
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)

    async def handle_command(self, command):
        cmd = command.get('cmd')
        
        if cmd == 'start_recording':
            filename = command.get('filename', self.output_file)
            duration = command.get('duration', self.duration)
            success = await self.start_recording(filename, duration)
            if success:
                self.capture_task = asyncio.create_task(self.capture_frames())
            return {'type': 'response', 'cmd': cmd, 'success': success}
        
        elif cmd == 'stop_recording':
            success = await self.stop_recording()
            return {'type': 'response', 'cmd': cmd, 'success': success}
        
        elif cmd == 'set_resolution':
            if not self.recording:
                self.width = command.get('width', self.width)
                self.height = command.get('height', self.height)
                return {'type': 'response', 'cmd': cmd, 'success': True}
            return {'type': 'response', 'cmd': cmd, 'success': False, 'message': 'Cannot change while recording'}
        
        elif cmd == 'set_fps':
            if not self.recording:
                self.fps = command.get('fps', self.fps)
                return {'type': 'response', 'cmd': cmd, 'success': True}
            return {'type': 'response', 'cmd': cmd, 'success': False, 'message': 'Cannot change while recording'}
        
        elif cmd == 'set_camera':
            if not self.recording:
                self.camera_index = command.get('index', self.camera_index)
                return {'type': 'response', 'cmd': cmd, 'success': True}
            return {'type': 'response', 'cmd': cmd, 'success': False, 'message': 'Cannot change while recording'}
        
        elif cmd == 'get_status':
            return {'type': 'status', **self.status}
        
        elif cmd == 'list_cameras':
            if self.camera_handler:
                cameras = await self.camera_handler.list_available_cameras()
            else:
                cameras = []
            return {'type': 'response', 'cmd': cmd, 'cameras': cameras}
        
        return {'type': 'error', 'message': f'Unknown command: {cmd}'}

    async def broadcast_frames(self):
        while True:
            try:
                frame_data = await asyncio.wait_for(self.frame_queue.get(), timeout=0.1)
                disconnected = set()
                for client in self.clients:
                    try:
                        await client.send(json.dumps(frame_data))
                    except websockets.exceptions.ConnectionClosed:
                        disconnected.add(client)
                for client in disconnected:
                    self.clients.discard(client)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.01)


def main():
    parser = argparse.ArgumentParser(description='Record video from webcam')
    parser.add_argument('-o', '--output', default='output.avi', help='Output video file (default: output.avi)')
    parser.add_argument('-d', '--duration', type=int, default=10, help='Recording duration in seconds (default: 10)')
    parser.add_argument('-c', '--camera', type=int, default=0, help='Camera index (default: 0)')
    parser.add_argument('--camera-type', choices=['usb', 'picamera'], default='usb', 
                        help='Camera type: usb for webcams, picamera for Raspberry Pi camera (default: usb)')
    parser.add_argument('--width', type=int, default=640, help='Video width (default: 640)')
    parser.add_argument('--height', type=int, default=480, help='Video height (default: 480)')
    parser.add_argument('--fps', type=int, default=30, help='Frames per second (default: 30)')
    parser.add_argument('--serve', action='store_true', help='Start websocket server')
    parser.add_argument('--host', default='localhost', help='Websocket server host (default: localhost)')
    parser.add_argument('--port', type=int, default=8765, help='Websocket server port (default: 8765)')
    parser.add_argument('--no-save', action='store_true', help='Stream only, do not save to file')
    args = parser.parse_args()

    try:
        controller = CameraController(camera_type=args.camera_type)
        controller.camera_index = args.camera
        controller.width = args.width
        controller.height = args.height
        controller.fps = args.fps
        controller.output_file = args.output
        controller.duration = args.duration
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    async def run_async():
        if args.serve:
            print(f"Starting websocket server on {args.host}:{args.port}")
            server = await websockets.serve(controller.handle_client, args.host, args.port)
            
            broadcast_task = asyncio.create_task(controller.broadcast_frames())
            
            if not args.no_save:
                print(f"Auto-starting recording to {args.output} for {args.duration} seconds")
                success = await controller.start_recording()
                if success:
                    controller.capture_task = asyncio.create_task(controller.capture_frames())
            
            try:
                await server.wait_closed()
            except KeyboardInterrupt:
                print("\nShutting down...")
            finally:
                if controller.capture_task:
                    controller.capture_task.cancel()
                    try:
                        await controller.capture_task
                    except asyncio.CancelledError:
                        pass
                broadcast_task.cancel()
                try:
                    await broadcast_task
                except asyncio.CancelledError:
                    pass
                controller.executor.shutdown(wait=True)
        else:
            # Original CLI behavior
            success = await controller.start_recording()
            if success:
                print(f"Recording {args.duration} seconds to {args.output}...")
                await controller.capture_frames()
                print(f"Video saved to {args.output}")
            else:
                print(f"Error: Cannot open camera {args.camera}")
                sys.exit(1)
    
    asyncio.run(run_async())


if __name__ == "__main__":
    main()
